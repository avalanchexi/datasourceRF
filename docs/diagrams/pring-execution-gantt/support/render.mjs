import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const archifyRoot = process.env.ARCHIFY_ROOT || '/mnt/d/cursor/archify/archify';
const { applyTemplate } = await import(pathToFileURL(path.join(archifyRoot, 'renderers/shared/utils.mjs')));
const outDir = path.join(root, 'docs/diagrams');
const source = path.join(outDir, 'pring-execution-gantt.gantt.json');
const data = JSON.parse(fs.readFileSync(source, 'utf8'));
const output = path.join(outDir, 'pring-execution-gantt.html');
const templatePath = path.join(archifyRoot, 'assets/template.html');
const template = fs.readFileSync(templatePath, 'utf8');
const escape = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

// This is a custom Gantt compiler using Archify's actual template/i18n/viewer.
// It intentionally does not pretend that Archify has a native Gantt schema.
function svgContent(d, view = 'all') {
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const start = Date.parse(view === 'recent' ? '2026-09-08T00:00:00+08:00' : d.period_start);
  const end = Date.parse('2026-09-09T12:00:00+08:00');
  const groups = d.groups.filter(g => view !== 'recent' || Date.parse(g.end) >= start);
  const x0 = 350, x1 = 1354, y0 = 108, bottom = 630;
  const rowH = (bottom - y0) / groups.length;
  const xx = dt => x0 + (Date.parse(dt) - start) / (end - start) * (x1 - x0);
  const tt = (x, y, text, cls = 'gt-text', size = 17, anchor = 'start') => `<text x="${x}" y="${y}" class="${cls}" font-size="${size}" text-anchor="${anchor}">${esc(text)}</text>`;
  let s = `<title>Pring 近期执行与修复甘特图</title><desc>2026年9月5日至9月9日，12个阶段，条形表示记录覆盖窗口，不是持续工时。点击阶段查看提交和验证依据。</desc>`;
  s += `<rect width="1600" height="706" rx="12" class="gt-bg"/>`;
  s += tt(24, 33, view === 'recent' ? '近期修复放大 · 09/08 起' : '执行全景 · 2026.09.05 — 09.09', 'gt-strong', 22);
  s += tt(1572, 33, '北京时间 UTC+08:00', 'gt-muted', 15, 'end');
  s += tt(24, 82, '执行阶段 / 点击查看证据', 'gt-muted', 15);
  s += tt(1420, 82, '交付状态', 'gt-muted', 15);
  const step = (view === 'recent' ? 6 : 24) * 3600000;
  for (let time = start, index = 0; time <= end; time += step, index++) {
    const x = x0 + (time - start) / (end - start) * (x1 - x0);
    const local = new Date(time + 8 * 3600000);
    const label = view === 'recent' ? `${local.getUTCMonth()+1}/${local.getUTCDate()} ${String(local.getUTCHours()).padStart(2,'0')}:00` : `9 月 ${local.getUTCDate()} 日`;
    if (index % 2 === 0) s += `<rect x="${x}" y="98" width="${Math.min(x1-x, step/(end-start)*(x1-x0))}" height="${bottom-94}" class="gt-band"/>`;
    s += `<line x1="${x}" x2="${x}" y1="94" y2="${bottom+3}" class="gt-grid"/>`;
    s += tt(x + (time === end ? -2 : 7), 82, label, 'gt-muted', 15, time === end ? 'end' : 'start');
  }
  for (const [index, group] of groups.entries()) {
    const y = y0 + index * rowH;
    const mid = y + rowH / 2;
    const left = Math.max(x0, xx(group.start));
    const right = xx(group.end);
    const status = group.status === 'active' ? '进行中' : '软件批已交付';
    s += `<g class="gt-row" data-gantt-group="${esc(group.id)}" tabindex="0" role="button" aria-label="${esc(group.label)}，${status}，查看详情">`;
    s += `<rect x="10" y="${y}" width="1580" height="${rowH}" rx="5" class="gt-hit"/>`;
    s += `<line x1="20" x2="1578" y1="${y+rowH}" y2="${y+rowH}" class="gt-rowline"/>`;
    s += tt(25, mid+5, String(d.groups.indexOf(group)+1).padStart(2,'0'), 'gt-number', 15);
    s += tt(60, mid-3, group.label, 'gt-strong', 18);
    s += tt(60, mid+16, group.note, 'gt-muted', 12);
    const stateClass = group.status === 'active' ? 'gt-active' : 'gt-done';
    s += `<rect x="${left}" y="${mid-11}" width="${Math.max(1,right-left)}" height="22" rx="5" class="gt-bar ${stateClass}"/>`;
    s += `<line x1="${left}" x2="${right}" y1="${mid-11}" y2="${mid-11}" class="gt-top ${stateClass}"/>`;
    // End markers carry exact commit / snapshot positions, even on short bars.
    s += `<circle cx="${right}" cy="${mid}" r="5" class="gt-point ${stateClass}"/>`;
    if (Date.parse(group.start) < start) s += tt(x0+7, mid+5, '←', 'gt-bartext', 16);
    if (right-left > 95) s += tt(left+11, mid+5, `${group.task_ids.length} 个过程`, 'gt-bartext', 14);
    s += `<rect x="1418" y="${mid-12}" width="143" height="25" rx="12" class="gt-status ${stateClass}"/>`;
    s += tt(1489, mid+5, status, group.status === 'active' ? 'gt-active-text' : 'gt-done-text', 14, 'middle');
    s += `<title>${esc(group.label)}\n${esc(group.start.replace('T',' ').slice(0,16))} → ${esc(group.end.replace('T',' ').slice(0,16))}\n${esc(d.time_semantics)}</title></g>`;
  }
  const now = xx(d.snapshot_at);
  s += `<line x1="${now}" x2="${now}" y1="96" y2="${bottom+5}" class="gt-now"/>`;
  s += tt(now-8, bottom+29, '盘点 09/09 10:02', 'gt-active-text', 14, 'end');
  s += `<circle cx="29" cy="${bottom+28}" r="5" class="gt-point gt-done"/>` + tt(42, bottom+33, '已提交的代码 / 文档批次', 'gt-muted', 14);
  s += `<circle cx="284" cy="${bottom+28}" r="5" class="gt-point gt-active"/>` + tt(297, bottom+33, '截至盘点仍在推进', 'gt-muted', 14);
  s += tt(24, 693, '时间条 = 基点至交付的记录窗口，非连续工时；软件批完成不等于来源认证、完整模型或正式切换。', 'gt-muted', 14);
  return s;
}

const css = `
  :root { --ggreen:#166b5b; --gamber:#996006; --gink:#18293b; --gmuted:#687787; --gline:#dce4eb; --gpaper:#fcfdfd; --gband:#f4f7f8; --gstatus:#e4f1eb; --gactivebg:#fff0d1; }
  [data-theme="dark"] { --ggreen:#64d2b2; --gamber:#f7be5b; --gink:#e9f1f8; --gmuted:#95a7b8; --gline:#273748; --gpaper:#101b28; --gband:#132231; --gstatus:#143c35; --gactivebg:#433321; }
  body, #diagram { font-family:Inter,"Noto Sans CJK SC","Microsoft YaHei",system-ui,sans-serif; }
  .container { max-width:var(--archify-reader-width,1820px); }
  .container .header { margin-bottom:.65rem; padding-right:0; }
  .container .header-row { padding-right:29.5rem; }
  .header h1 { font-size:clamp(22px,2.1vw,31px); }
  .pulse-dot { animation:none; }
  .diagram-container { padding:.35rem; padding-bottom:calc(.35rem + var(--archify-nav-reserve)); margin-bottom:.65rem; }
  .cards.g-footer { display:block; margin-top:0; }
  .footer { margin-top:.6rem; }
  .g-controls {display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;margin:.5rem 0 0;}
  .g-tabs {display:flex;gap:6px;}
  .g-tabs button,.g-pending {font:inherit;font-size:13px;padding:8px 13px;border:1px solid var(--gline);border-radius:7px;background:var(--gpaper);color:var(--gink);cursor:pointer;}
  .g-tabs button[aria-pressed="true"] {background:var(--gstatus);border-color:var(--ggreen);color:var(--ggreen);font-weight:650;}
  .g-meta {display:flex;gap:20px;align-items:center;color:var(--gmuted);font-size:12px;}
  .g-meta strong {color:var(--gink);font-size:18px;font-weight:650;margin-right:5px;}
  .g-summary {display:grid;grid-template-columns:1.1fr 1.3fr 1fr;gap:14px;color:var(--gmuted);font-size:12px;line-height:1.65;}
  .g-summary>div {border-top:2px solid var(--gline);padding-top:9px;}
  .g-summary b {display:block;color:var(--gink);font-size:14px;font-weight:600;}
  .g-summary a,.g-provenance a {color:var(--ggreen);text-decoration:underline;text-underline-offset:3px;}
  .g-provenance {display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;font-size:11px;color:var(--gmuted);margin-top:12px;}
  .gt-bg {fill:var(--gpaper);}.gt-band {fill:var(--gband);}.gt-text,.gt-strong {fill:var(--gink);}.gt-strong {font-weight:600;}.gt-muted,.gt-number {fill:var(--gmuted);}.gt-number {font-variant-numeric:tabular-nums;}
  .gt-grid {stroke:var(--gline);stroke-width:1;}.gt-rowline {stroke:var(--gline);stroke-width:.55;}.gt-hit {fill:transparent;}.gt-row {cursor:pointer;outline:none;}.gt-row:hover .gt-hit,.gt-row:focus .gt-hit {fill:var(--ggreen);fill-opacity:.07;}.gt-row:focus .gt-hit {stroke:var(--ggreen);stroke-width:1;}
  .gt-bar.gt-done {fill:var(--ggreen);fill-opacity:.2;}.gt-bar.gt-active {fill:var(--gamber);fill-opacity:.24;}.gt-top {stroke-width:2;}.gt-top.gt-done {stroke:var(--ggreen);}.gt-top.gt-active {stroke:var(--gamber);stroke-dasharray:5 3;}.gt-point.gt-done {fill:var(--ggreen);}.gt-point.gt-active {fill:var(--gamber);}.gt-bartext {fill:var(--gink);}
  .gt-status.gt-done {fill:var(--gstatus);}.gt-status.gt-active {fill:var(--gactivebg);}.gt-done-text {fill:var(--ggreen);}.gt-active-text {fill:var(--gamber);}.gt-now {stroke:var(--gamber);stroke-width:1.5;stroke-dasharray:5 5;opacity:.75;}
  #g-dialog {width:min(840px,92vw);max-height:83vh;margin:auto;border:1px solid var(--gline);border-radius:14px;padding:0;background:var(--gpaper);color:var(--gink);box-shadow:0 25px 90px #0005;}
  #g-dialog::backdrop {background:#09172499;backdrop-filter:blur(3px);}
  .g-dialog-head {position:sticky;top:0;z-index:1;display:flex;gap:20px;align-items:center;justify-content:space-between;padding:20px 24px;border-bottom:1px solid var(--gline);background:var(--gpaper);}
  .g-dialog-head h2 {font-size:20px;margin:0;}.g-dialog-head button {background:transparent;color:var(--gink);border:1px solid var(--gline);border-radius:6px;font-size:22px;cursor:pointer;padding:1px 10px;}
  #g-dialog-content {padding:8px 24px 24px;}.g-task {padding:17px 0;border-bottom:1px solid var(--gline);}.g-task:last-child {border:0;}.g-task h3 {font-size:16px;margin:0 0 7px;}.g-task p {font-size:14px;line-height:1.7;margin:6px 0;}.g-task .g-date {font-size:12px;font-variant-numeric:tabular-nums;color:var(--gmuted);}.g-task a {color:var(--ggreen);}.g-task code {font-size:12px;background:var(--gband);padding:2px 5px;}.g-task .g-proof {font-size:13px;color:var(--ggreen);}.g-dialog-note {font-size:12px;line-height:1.7;color:var(--gmuted);padding:12px 0 0;}
  @media(max-width:750px){.g-summary{grid-template-columns:1fr;}.g-controls{align-items:flex-start;}.g-meta{gap:10px;}.g-provenance{line-height:1.7}.container{padding-top:1rem}.container .header-row{padding-right:0}}
  @media print {.g-controls,.g-provenance{display:none}.g-summary{font-size:10px} #g-dialog{display:none}}
`;
const controls = `<div class="g-controls no-print"><div class="g-tabs" aria-label="甘特图时间范围"><button id="g-all" aria-pressed="true">全部阶段</button><button id="g-recent" aria-pressed="false">近期修复放大</button><button id="g-open">待推进事项</button></div><div class="g-meta"><span><strong>${data.tasks.length}</strong>重要过程</span><span><strong>1053</strong>最近全套通过</span><span>正式切换 <strong style="font-size:13px;color:var(--gamber)">未完成</strong></span></div></div>`;
const foot = `<div class="g-summary"><div><b>最新已提交 · LPR</b>09/09 09:09 · 99c495a<br>376 项关联、1053 项默认全套通过。</div><div><b>当前推进 · PMI</b>原件与声明值、派生回退已有针对验证；<br>更多字段、时间和 PUBLIC 回放仍待收口。</div><div><b>下一道门 · 真实数据验收</b>来源认证 → 完整候选 → 120 日回放；<br>合格 AI 输出与正式切换仍未完成。</div></div><div class="g-provenance"><span>盘点：2026-09-09 10:02 · 条形起点为基点提交，表示记录窗口。</span><span><a href="pring-execution-gantt.gantt.json">数据</a> · <a href="pring-execution-gantt.svg">SVG</a> · <a href="pring-execution-gantt-notes.md">来源与口径</a> · Archify 2.17 自定义甘特图</span></div>`;
const dialog = `<dialog id="g-dialog" aria-labelledby="g-dialog-title"><div class="g-dialog-head"><h2 id="g-dialog-title"></h2><button id="g-close" aria-label="关闭详情">×</button></div><div id="g-dialog-content"></div></dialog>`;
const runtime = `
(() => {
 const data = JSON.parse(document.getElementById('gantt-data').textContent);
 const render = ${svgContent.toString()};
 const esc = s => String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const dialog=document.getElementById('g-dialog');const content=document.getElementById('g-dialog-content');const title=document.getElementById('g-dialog-title');
 const date = s => s.replace('T',' ').slice(0,16);
 function openGroup(id){const group=data.groups.find(g=>g.id===id);if(!group)return;title.textContent=group.label;
  content.innerHTML='<p class="g-dialog-note">'+esc(data.time_semantics)+'</p>'+data.tasks.filter(t=>t.group===id).map(t=>'<article class="g-task"><h3>'+esc(t.title)+(t.status==='active'?' · 进行中':'')+'</h3><div class="g-date">'+esc(date(t.start))+' → '+esc(date(t.end))+(t.status==='active'?'（截至盘点）':'')+'</div><p>'+esc(t.summary)+'</p><p class="g-proof">'+esc(t.verification)+'</p><p><a href="../../'+esc(t.source)+'" target="_blank" rel="noopener">查看实施 / 验证来源 ↗</a>'+ (t.end_commit?' · 完成提交 <code>'+esc(t.end_commit.short)+'</code>':' · 未提交')+'</p></article>').join('');dialog.showModal();}
 const svg=document.getElementById('diagram');const svgStyle=svg.querySelector('style').outerHTML;
 svg.addEventListener('click',e=>{const row=e.target.closest('[data-gantt-group]');if(row){e.stopPropagation();openGroup(row.dataset.ganttGroup);}});
 svg.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){const row=e.target.closest('[data-gantt-group]');if(row){e.preventDefault();openGroup(row.dataset.ganttGroup);}}});
 function view(name){svg.innerHTML=svgStyle+render(data,name);document.getElementById('g-all').setAttribute('aria-pressed',String(name==='all'));document.getElementById('g-recent').setAttribute('aria-pressed',String(name==='recent'));svg.dataset.ganttView=name;}
 document.getElementById('g-all').onclick=()=>view('all');document.getElementById('g-recent').onclick=()=>view('recent');
 document.getElementById('g-open').onclick=()=>{title.textContent='待推进事项 · 尚无承诺完成日期';content.innerHTML='<p class="g-dialog-note">依赖关系决定后续顺序；这里不预设工期，也不把代码测试通过当作来源认证。</p>'+data.pending.map(p=>'<article class="g-task"><h3>'+esc(p.title)+' · '+({active:'进行中',blocked:'有阻塞',pending:'等待前置'}[p.status])+'</h3><p>'+esc(p.description)+'</p><p><a href="../../'+esc(p.source)+'" target="_blank" rel="noopener">查看任务 / 决策依据 ↗</a></p></article>').join('');dialog.showModal();};
 document.getElementById('g-close').onclick=()=>dialog.close();dialog.addEventListener('click',e=>{if(e.target===dialog)dialog.close();});
 window.ganttReady=true;
})();`;

const svg = `<svg id="diagram" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 706" role="img" aria-label="Pring 近期执行与修复甘特图" data-gantt-view="all"><style>${css.replaceAll('&','&amp;')}</style>${svgContent(data)}</svg>`;
let html = applyTemplate(template, { title: data.title, svg, cards: `<div class="cards g-footer">${foot}</div>`, locale: 'zh-CN', visualPreset: 'classic', guidedViews: [] });
html = html.replace('</head>', `<style id="gantt-style">${css}</style></head>`)
  .replace('    <!-- ARCHIFY:GUIDED_VIEWS_DATA -->', '    <!-- ARCHIFY:GUIDED_VIEWS_DATA -->');
// Include controls in the header measured by Archify's adaptive reader.
const headerEnd = /(<div class="header">[\s\S]*?<\/h1>\s*<\/div>)(\s*<\/div>)/;
if (!headerEnd.test(html)) throw new Error('Archify header insertion point changed');
html = html.replace(headerEnd, (_, before, after) => before + controls + after);
html = html.replace('</body>', `${dialog}<script id="gantt-data" type="application/json">${JSON.stringify(data).replaceAll('<','\\u003c')}</script><script>${runtime}</script></body>`);
// Keep the native viewer/export code; omit optional remote font requests.
html = html.replace(/<link\b[^>]*href="https:\/\/fonts\.[^>]+>/g, '');
html = html.replace(/<meta name="generator" content="[^"]+">/, '<meta name="generator" content="archify 2.17.0-dev.1; custom-gantt-template">');

const candidate = path.join(outDir, '.pring-execution-gantt.candidate.html');
fs.writeFileSync(candidate, html);
const check = spawnSync(process.execPath, [path.join(archifyRoot,'bin/archify.mjs'),'check',candidate], {encoding:'utf8',env:{...process.env,ARCHIFY_UPDATE_CHECK_DISABLED:'1'}});
fs.writeFileSync(path.join(outDir,'pring-execution-gantt.archify-check.json'), check.stdout);
if(check.status!==0){process.stderr.write(check.stdout+check.stderr);process.exit(check.status||1);}
fs.renameSync(candidate,output);
const standaloneSvg = svg;
fs.writeFileSync(path.join(outDir,'pring-execution-gantt.svg'),standaloneSvg);
const sha = value => createHash('sha256').update(value).digest('hex');
const receipt = { status:'passed', mode:'custom-gantt-template', native_gantt_schema:false, native_deliver_used:false,
    specification:{path:path.basename(source),sha256:sha(fs.readFileSync(source)),bytes:fs.statSync(source).size},
    artifact:{path:path.basename(output),sha256:sha(fs.readFileSync(output)),bytes:fs.statSync(output).size},
    template:{path:templatePath,sha256:sha(template)},
    archify_check:JSON.parse(check.stdout), snapshot_at:data.snapshot_at, evidence_kind:'git-and-local-execution-records',
    browser_evidence:'pending', visual_review:'pending'};
fs.writeFileSync(path.join(outDir,'pring-execution-gantt.receipt.json'),JSON.stringify(receipt,null,2)+'\n');
console.log(JSON.stringify({output,groups:data.groups.length,tasks:data.tasks.length,check:check.status,sha256:receipt.artifact.sha256}));
