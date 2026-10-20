import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
import {spawnSync} from 'node:child_process';
const task=path.dirname(fileURLToPath(import.meta.url));
const root=path.resolve(task,'../..'), out=path.join(root,'docs/diagrams');
const base='pring-progress-12h-20260910-0918';
const arch='/mnt/d/cursor/archify/archify';
const data=JSON.parse(fs.readFileSync(path.join(out,base+'.gantt.json'),'utf8'));
const templatePath=path.join(arch,'assets/template.html');
const template=fs.readFileSync(templatePath,'utf8');
const {applyTemplate}=await import(pathToFileURL(path.join(arch,'renderers/shared/utils.mjs')));
const old=fs.readFileSync(path.join(root,'.scratch/pring-execution-gantt/render.mjs'),'utf8');
const sharedCss=old.match(/const css = `([\s\S]*?)`;\nconst controls/)[1];
const css=sharedCss+`
 :root{--gblue:#28699a;--ggray:#77828d;}[data-theme="dark"]{--gblue:#82bcf4;--ggray:#b2bec9;}
 .header h1{font-size:clamp(22px,2vw,30px)}.g-meta{gap:16px}.gt-stage{fill:var(--gpaper);stroke:var(--gline);stroke-width:1.2}
 .gt-row .gt-hit{pointer-events:all}.gt-future{cursor:pointer}.gt-future:hover .gt-stage{stroke:var(--ggreen);stroke-width:2}
 .c-done{--gc:var(--ggreen)}.c-research{--gc:var(--gblue)}.c-issue,.c-blocked{--gc:var(--gamber)}.c-interrupted,.c-pending{--gc:var(--ggray)}
 .g-fill{fill:var(--gc)}.g-stroke{stroke:var(--gc)}.g-window{fill:var(--gc);fill-opacity:.14;stroke:var(--gc);stroke-width:1.2}
 .g-execution{fill:var(--gc);fill-opacity:.75}.g-unknown{stroke-dasharray:5 4;fill-opacity:.06}.g-tag{fill:var(--gc);fill-opacity:.10}
 .g-result{fill:var(--gc);font-weight:600}.g-capsule{fill:var(--gpaper);stroke:var(--gline)}.g-item-id{font-variant-numeric:tabular-nums;font-weight:700}
 .g-links{display:flex;gap:12px;flex-wrap:wrap}.g-detail-meta{padding:12px 0;border-bottom:1px solid var(--gline);line-height:1.7}
 .g-subheading{font-size:15px;font-weight:600;color:var(--gink);margin:16px 0 6px}.g-pending-list{line-height:1.9}.g-provenance{margin-top:2px}
`;

function chart(d,view='overview'){
 const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const txt=(x,y,t,cl='gt-strong',size=17,anchor='start')=>`<text x="${x}" y="${y}" class="${cl}" font-size="${size}" text-anchor="${anchor}">${esc(t)}</text>`;
 const local=s=>{const t=new Date(Date.parse(s)+8*3600000);return String(t.getUTCHours()).padStart(2,'0')+':'+String(t.getUTCMinutes()).padStart(2,'0')};
 let s=`<title>${esc(d.title)} · ${view==='plan'?'后续执行':'12小时推进与后续概览'}</title><desc>${esc(d.time_semantics+' '+d.plan_semantics)}</desc><rect width="1600" height="850" rx="12" class="gt-bg"/>`;
 if(view==='plan'){
  s+=txt(25,36,'后续执行 · 12组事项及建议阶段','gt-strong',23)+txt(1570,36,'阶段轴 · 全部待排期 · 条宽不代表工期','gt-muted',16,'end');
  const x0=430,col=155,y0=105,rh=51;
  for(let i=0;i<6;i++){
   const x=x0+i*col;
   if(i%2===0)s+=`<rect x="${x}" y="93" width="${col}" height="630" class="gt-band"/>`;
   s+=txt(x+col/2,79,d.phases[i],'gt-muted',17,'middle')+`<line x1="${x}" x2="${x}" y1="93" y2="723" class="gt-grid"/>`;
  }
  s+=txt(25,79,'事项 / 点击查看关闭条件','gt-muted',16)+txt(1485,79,'状态','gt-muted',16,'middle');
  d.pending.forEach((p,i)=>{
   const y=y0+i*rh,mid=y+rh/2,x=x0+p.phase*col+12,w=(p.until-p.phase+1)*col-24;
   const state=p.state==='issue'?'正在推进':p.state==='blocked'?'前置待补':'等待前置';
   s+=`<g class="gt-row c-${p.state}" data-plan="${esc(p.id)}" role="button" tabindex="0" aria-label="${esc(p.label)}，${state}，待排期"><rect x="12" y="${y}" width="1567" height="${rh}" rx="5" class="gt-hit"/>`;
   s+=txt(25,mid+2,p.id,'gt-number g-item-id',16)+txt(75,mid-2,p.label,'gt-strong',20)+txt(75,mid+17,p.note,'gt-muted',13);
   s+=`<line x1="25" x2="1570" y1="${y+rh}" y2="${y+rh}" class="gt-rowline"/><rect x="${x}" y="${mid-12}" width="${w}" height="24" rx="5" class="g-window"/>`;
   s+=txt(x+w/2,mid+6,'待排期','g-result',15,'middle')+txt(1485,mid+5,state,'g-result',16,'middle');
   s+=`<title>${esc(p.label+'；'+p.scheduling+'；前置：'+(p.depends.join('、')||p.note))}</title></g>`;
  });
  s+=txt(25,756,'推进关系：来源与规则 → 完整候选 → 固定120日回放 / 真实检索与报告 → 目标日演练与切换','gt-strong',19);
  s+=txt(25,789,'SQLite、Worker、Q1及派生校验按依赖推进；共用验证环境的测试串行。最终全套绑定同一版本。','gt-muted',16);
  s+=txt(25,824,'阶段位置为建议安排，具体前置与验收标准见各行详情；没有预设未来日期或承诺工期。','gt-muted',16);
  return s;
 }
 const start=Date.parse(d.period_start),end=Date.parse(d.snapshot_at),x0=350,x1=1350,y0=94,rh=38,bottom=y0+d.tasks.length*rh;
 const xx=t=>x0+(Date.parse(t)-start)/(end-start)*(x1-x0);
 s+=txt(25,35,'最近12小时 · 实际推进记录','gt-strong',23)+txt(1570,35,'09/09 21:18 — 09/10 09:18 · 北京时间','gt-muted',17,'end');
 s+=txt(25,78,'事项 / 点击查看证据','gt-muted',16)+txt(1485,78,'截至盘点的状态','gt-muted',16,'middle');
 s+=txt(x0,78,'21:18','gt-muted',15);
 const first=Math.ceil(start/3600000)*3600000;
 for(let t=first;t<end;t+=3600000){
  const x=x0+(t-start)/(end-start)*(x1-x0),h=new Date(t+8*3600000).getUTCHours();
  if(h%2===0)s+=`<rect x="${x}" y="89" width="${Math.min(x1-x,(x1-x0)/12)}" height="${bottom-86}" class="gt-band"/>`;
  s+=`<line x1="${x}" x2="${x}" y1="89" y2="${bottom+3}" class="gt-grid"/>`;
  if(h%2===0 && x-x0>85)s+=txt(x,78,h===0?'09/10 00:00':String(h).padStart(2,'0')+':00','gt-muted',15,'middle');
 }
 s+=txt(x1,78,'09:18','gt-muted',15,'end');
 d.tasks.forEach((t,i)=>{
  const y=y0+i*rh,mid=y+rh/2,left=Math.max(x0,xx(t.start)),right=xx(t.end);
  s+=`<g class="gt-row c-${t.state}" data-task="${esc(t.id)}" role="button" tabindex="0" aria-label="${esc(t.label+'，'+t.result)}"><rect x="12" y="${y}" width="1567" height="${rh}" rx="5" class="gt-hit"/>`;
  s+=txt(25,mid+3,String(i+1).padStart(2,'0'),'gt-number',14)+txt(59,mid-2,t.label,'gt-strong',18)+txt(59,mid+15,t.note,'gt-muted',12);
  s+=`<line x1="25" x2="1570" y1="${y+rh}" y2="${y+rh}" class="gt-rowline"/>`;
  if(t.kind!=='milestone'){
   s+=`<rect x="${left}" y="${mid-10}" width="${Math.max(.5,right-left)}" height="20" rx="4" class="${t.kind==='execution'?'g-execution':'g-window'} ${t.kind==='unknown'?'g-unknown':''}"/>`;
   if(Date.parse(t.start)<start)s+=txt(left+5,mid+5,'←','g-result',17);
   if(right-left>220)s+=txt(left+12,mid+5,t.kind==='unknown'?'停止时刻未知':t.kind==='execution'?'已核验执行':'记录覆盖窗口','g-result',14);
  }
  s+=`<path d="M ${right} ${mid-6} l 6 6 -6 6 -6 -6 z" class="g-fill"/>`;
  const anchor=right>x1-80?'end':'start',timeX=anchor==='end'?right-12:right+12;
  s+=txt(timeX,mid+5,local(t.end),'gt-muted',14,anchor);
  s+=`<rect x="1408" y="${mid-12}" width="154" height="25" rx="12" class="g-tag"/>`+txt(1485,mid+5,t.result,'g-result',15,'middle');
  s+=`<title>${esc(t.summary+' '+t.start+' → '+t.end+'；'+d.time_semantics)}</title></g>`;
 });
 s+=`<line x1="${x1}" x2="${x1}" y1="89" y2="${bottom+3}" class="gt-now"/>`;
 s+=txt(25,548,'实线：执行起止　浅色条：记录窗口　虚线：停止时刻未知　◆：结果记录时点','gt-muted',15);
 s+=txt(1570,548,'绿：通过　蓝：对账　橙：待解决　灰：中断','gt-muted',14,'end');
 s+=txt(25,589,'后续执行 · 点击阶段查看事项，或切换到完整计划','gt-strong',22)+txt(1570,589,'待排期 · 无承诺完成日期','gt-muted',16,'end');
 const cards=[
  {id:'software',title:'01  软件修复收口',ids:['S1','S2','S3','S4'],lines:['SQLite锁 / Worker新目录','Q1映射 / 信用脉冲整窗','关闭缺陷后完成关联回归']},
  {id:'sources',title:'02  来源与业务规则',ids:['D1','D2','D3'],lines:['来源认证 / 历史公开时间','股票池、广度与完整金额','商品合约、换月与篮子']},
  {id:'accept',title:'03  完整模型与真实验收',ids:['G1','G2','V1','V2'],lines:['最终全套 / 完整候选与校准','固定120交易日双时点回放','真实检索基准 / 合格AI报告']},
  {id:'release',title:'04  演练与正式切换',ids:['V3'],lines:['目标日端到端结果一致','中断恢复与回退边界','必要前置满足后正式切换']}
 ];
 cards.forEach((c,i)=>{const x=25+i*394;
  s+=`<g class="gt-future" data-stage="${c.id}" role="button" tabindex="0" aria-label="${esc(c.title+'，待排期')}" data-plan-ids="${c.ids.join(',')}"><rect x="${x}" y="610" width="368" height="156" rx="10" class="gt-stage"/>`;
  s+=txt(x+18,641,c.title,'gt-strong',20);
  c.lines.forEach((l,j)=>s+=txt(x+18,677+j*28,l,'gt-muted',17));
  s+='</g>';
 });
 s+=txt(25,802,'服务目标：稳定使用可信、点时正确的数据，形成可验收的Pring输出与真实报告。','gt-strong',18);
 s+=txt(25,833,'测试批次范围重叠，不累加；软件切片通过不等于来源认证、完整候选、120日回放或正式切换。','gt-muted',15);
 return s;
}

const controls=`<div class="g-controls no-print"><div class="g-tabs"><button id="g-overview" aria-pressed="true">12小时推进 + 后续概览</button><button id="g-plan" aria-pressed="false">后续12组执行事项</button></div><div class="g-meta"><span><strong>11</strong>重要过程</span><span><strong>12</strong>后续工作组</span></div></div>`;
const foot=`<div class="g-provenance"><span>固定快照：2026-09-10 09:18:53 · 已有原件与执行记录保持不变</span><span><a href="${base}.gantt.json">数据快照</a> · <a href="${base}-notes.md">来源与口径</a> · Archify 2.17 自定义甘特图</span></div>`;
const dialog=`<dialog id="g-dialog" aria-labelledby="g-dialog-title"><div class="g-dialog-head"><h2 id="g-dialog-title"></h2><button id="g-close" aria-label="关闭详情">×</button></div><div id="g-dialog-content"></div></dialog>`;
const runtime=`(()=>{
 const d=JSON.parse(document.getElementById('gantt-data').textContent),render=${chart.toString()};
 const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const svg=document.getElementById('diagram'),style=svg.querySelector('style').outerHTML,dialog=document.getElementById('g-dialog'),title=document.getElementById('g-dialog-title'),body=document.getElementById('g-dialog-content');
 const links=ss=>ss.map(s=>'<p class="g-links"><a href="../../'+esc(d.sources[s].snapshot)+'" target="_blank" rel="noopener">'+esc(s.split('/').pop())+' · 固定证据</a><a href="../../'+esc(s)+'" target="_blank" rel="noopener">当前记录 ↗</a></p>').join('');
 function showPlan(items,heading){title.textContent=heading;body.innerHTML='<p class="g-dialog-note">'+esc(d.plan_semantics)+'</p>'+items.map(p=>'<article class="g-task"><h3>'+esc(p.id+' · '+p.label)+'</h3><p>'+esc(p.summary)+'</p><p><b>当前 / 前置：</b>'+esc(p.note)+(p.depends.length?'；'+esc(p.depends.join('、')):'')+'</p><p><b>关闭条件：</b>'+esc(p.acceptance)+'</p><p class="g-proof">待排期 · 不预设完成日期</p>'+links(p.sources)+'</article>').join('');dialog.showModal();}
 function open(target){
  if(target.dataset.task){const t=d.tasks.find(x=>x.id===target.dataset.task);title.textContent=t.label;body.innerHTML='<article class="g-task"><p class="g-proof">'+esc(t.result+' · '+t.note)+'</p><p>'+esc(t.summary)+'</p><p><b>服务目标：</b>'+esc(t.goal)+'</p><p class="g-date">'+esc(t.start+' → '+t.end)+'</p>'+t.details.map(x=>'<p>'+esc(x)+'</p>').join('')+'<p class="g-dialog-note">'+esc(d.time_semantics)+'</p>'+links(t.sources)+'</article>';dialog.showModal();}
  else if(target.dataset.plan)showPlan(d.pending.filter(p=>p.id===target.dataset.plan),'待执行事项与关闭条件');
  else if(target.dataset.stage)showPlan(d.pending.filter(p=>target.dataset.planIds.split(',').includes(p.id)),'后续执行 · 阶段事项');
 }
 svg.addEventListener('click',e=>{const target=e.target.closest('[data-task],[data-plan],[data-stage]');if(target){e.stopPropagation();open(target)}});
 svg.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){const target=e.target.closest('[data-task],[data-plan],[data-stage]');if(target){e.preventDefault();open(target)}}});
 function view(name){svg.innerHTML=style+render(d,name);svg.dataset.ganttView=name;document.getElementById('g-overview').setAttribute('aria-pressed',String(name==='overview'));document.getElementById('g-plan').setAttribute('aria-pressed',String(name==='plan'));}
 document.getElementById('g-overview').onclick=()=>view('overview');document.getElementById('g-plan').onclick=()=>view('plan');document.getElementById('g-close').onclick=()=>dialog.close();dialog.addEventListener('click',e=>{if(e.target===dialog)dialog.close()});window.ganttReady=true;
})();`;
const svg=view=>`<svg id="diagram" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 850" role="img" aria-label="${data.title}" data-gantt-view="${view}"><style>${css.replaceAll('&','&amp;')}</style>${chart(data,view)}</svg>`;
let html=applyTemplate(template,{title:data.title,svg:svg('overview'),cards:`<div class="cards g-footer">${foot}</div>`,locale:'zh-CN',visualPreset:'classic',guidedViews:[]});
html=html.replace('</head>',`<style>${css}</style></head>`);
const header=/(<div class="header">[\s\S]*?<\/h1>\s*<\/div>)(\s*<\/div>)/;
if(!header.test(html))throw Error('Archify header insertion point changed');
html=html.replace(header,(_,a,b)=>a+controls+b).replace('</body>',`${dialog}<script id="gantt-data" type="application/json">${JSON.stringify(data).replaceAll('<','\\u003c')}</script><script>${runtime}</script></body>`);
html=html.replace(/<link\b[^>]*href="https:\/\/fonts\.[^>]+>/g,'').replace(/<meta name="generator" content="[^"]+">/,'<meta name="generator" content="archify 2.17.0-dev.1; custom-gantt-template">');
const candidate=path.join(task,'candidate.html');fs.writeFileSync(candidate,html);
const check=spawnSync(process.execPath,[path.join(arch,'bin/archify.mjs'),'check',candidate],{encoding:'utf8',env:{...process.env,ARCHIFY_UPDATE_CHECK_DISABLED:'1'}});
fs.writeFileSync(path.join(task,'archify-check.json'),check.stdout);
if(check.status!==0){process.stderr.write(check.stdout+check.stderr);process.exit(check.status||1)}
const target=path.join(out,base+'.html');
const revise=process.argv.includes('--revise');
if(revise){
 const previous=JSON.parse(fs.readFileSync(path.join(out,base+'.receipt.json'),'utf8'));
 if(createHash('sha256').update(fs.readFileSync(target)).digest('hex')!==previous.artifact.sha256)throw Error('Output changed outside this report');
 const archive=path.join(task,'visual-round-0');fs.mkdirSync(archive,{recursive:true});
 for(const suffix of ['.html','.svg','-pending.svg','.receipt.json','.png','-pending.png']){
  const src=path.join(out,base+suffix);if(fs.existsSync(src))fs.copyFileSync(src,path.join(archive,base+suffix),fs.constants.COPYFILE_EXCL);
 }
}
fs.copyFileSync(candidate,target,revise?0:fs.constants.COPYFILE_EXCL);
for(const [name,view] of [['','overview'],['-pending','plan']])fs.writeFileSync(path.join(out,base+name+'.svg'),svg(view),{flag:revise?'w':'wx'});
const sha=x=>createHash('sha256').update(x).digest('hex');
const receipt={status:'passed',mode:'custom-gantt-template',native_gantt_schema:false,native_deliver_used:false,validation:'Archify basic artifact check; not native 9/9 showcase',
 specification:{path:base+'.gantt.json',sha256:sha(fs.readFileSync(path.join(out,base+'.gantt.json')))},
 artifact:{path:base+'.html',sha256:sha(fs.readFileSync(target)),bytes:fs.statSync(target).size},template:{path:templatePath,sha256:sha(template)},
 archify_check:JSON.parse(check.stdout),snapshot_at:data.snapshot_at,browser_evidence:'pending',visual_review:'pending'};
fs.writeFileSync(path.join(out,base+'.receipt.json'),JSON.stringify(receipt,null,2)+'\n',{flag:revise?'w':'wx'});
console.log(JSON.stringify({output:target,check:check.status,tasks:data.tasks.length,pending:data.pending.length,artifact:receipt.artifact}));
