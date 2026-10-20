"""Create an additive, fixed-window evidence snapshot; never write source records."""
import hashlib
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TASK = Path(__file__).resolve().parent
BASE = 'pring-progress-12h-20260910-0918'
OUT = ROOT / 'docs/diagrams'
P = ROOT / '.scratch/pring-data-acquisition-repair'
END = '2026-09-10T09:18:53+08:00'
START = '2026-09-09T21:18:53+08:00'
sources = {}

def capture(name):
    source = P / name
    rel = str(source.relative_to(ROOT))
    if rel not in sources:
        raw = source.read_bytes()
        target = TASK / 'evidence' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            assert target.read_bytes() == raw, str(target)
        else:
            with target.open('xb') as f:
                f.write(raw)
        sources[rel] = {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw),
                        'snapshot': str(target.relative_to(ROOT))}
    return rel

def record(name):
    capture(name)
    return json.loads((TASK / 'evidence' / name).read_text(encoding='utf-8-sig'))

def stamp(name, key='recorded_at'):
    raw = re.sub(r'(\.\d{6})\d+', r'\1', record(name)[key])
    return datetime.fromisoformat(raw).astimezone(datetime.fromisoformat(END).tzinfo).isoformat()

def entry(id, label, note, state, summary, goal, evidence, start=None, end=None, kind='milestone', result='', details=None):
    return dict(id=id, label=label, note=note, state=state, summary=summary, goal=goal,
                sources=[capture(x) for x in evidence], start=start or end, end=end,
                kind=kind, result=result, details=details or [])

tasks = [
 entry('full','全套回归暴露故障','1146通过 / 2失败','issue',
       '完整套件发现SQLite锁与报告时间倒序两项失败。报告时钟后来已有专项修复；SQLite仍未关闭。原失败记录保持不变。',
       '识别妨碍稳定完整运行的真实故障。',
       ['verification-interbank-full-running-59.json','verification-interbank-full-terminal-59.json'],
       start=stamp('verification-interbank-full-running-59.json'), end=stamp('verification-interbank-full-terminal-59.json'),kind='window',result='发现2项故障',
       details=['任务在窗口前已启动，只显示进入最近12小时的记录段。','运行记录到终态记录不是连续pytest工时；日志实际耗时7984.63秒。']),
 entry('clock','报告时钟与隔离验证','38项专项通过','done',
       '耗时改用单调计时，保留实际UTC及回拨标记；按请求ID等查询入口统一还原耗时。验证迁入独立环境。',
       '报告超时和系统校时期间仍能保存可审计结果。',
       ['implementation-report-clock.md','verification-report-clock-running-74.json','verification-report-clock-terminal-74.json'],
       start=stamp('verification-report-clock-running-74.json'),end=stamp('verification-report-clock-terminal-74.json'),kind='window',result='专项通过',
       details=['条形仅为本轮回归运行记录至验收记录窗口，不代表全部修复耗时。','38项用时29.33秒；未替代修复后的全套验收。']),
 entry('gdp','GDP合同与消费修复','95项关联通过','done',
       '补齐GDP八字段新目录合同与原件/规范化消费校验，覆盖单位、当季/累计及价格基础表头。',
       '让GDP候选输入保持明确的口径与可追溯来源。',
       ['implementation-19-gdp-contract.md','verification-gdp-running-87.json','verification-gdp-terminal-87.json'],
       start=stamp('verification-gdp-running-87.json'),end=stamp('verification-gdp-terminal-87.json'),kind='window',result='关联通过',
       details=['95项用时337.12秒；信用脉冲整窗与GDP修订基线仍需独立解决。']),
 entry('ust','美债新目录与来源校验','CLI 28项 / 消费113项','done',
       '修复CLI新目录查找，明确官方CSV来源合同；原件与规范化联合资格接入检索、上下文、派生及组件回放，坏最新父项不能恢复旧利差。',
       '使美债值及中美利差只能采用合格的实际输入。',
       ['implementation-14-ust-catalog.md','verification-ust-catalog-terminal-90.json','implementation-14-ust-consumption.md','verification-ust-consumer-running-98.json','verification-ust-consumer-terminal-98.json'],
       start=stamp('verification-ust-catalog-terminal-90.json'),end=stamp('verification-ust-consumer-terminal-98.json'),kind='window',result='两批通过',
       details=['条形连接CLI和消费两次终态记录，不是连续开发工时。','两批范围有重叠，28与113不相加；Worker官方路由与真实认证尚待完成。']),
 entry('bse','北交所官方入口补证','新目标样本仍为0','blocked',
       '完成3次逻辑搜索及1次有依据的官方GET，新入口返回自指302；没有获得目标日样本和历史公开时间证据。',
       '补齐全市场融资认证所需的北交所证据。',
       ['margin-bse-official-followup-20260910.md','verification-bse-followup-99.json'],
       end=stamp('verification-bse-followup-99.json'),result='仍缺样本'),
 entry('p2fix','P2回放边界修复与复审','认证 / 鲜度 / 双版本范围','done',
       '修复可选P2被误作硬门、输出待认证、比较侧来源遗漏、陈旧值重标current、输出单独降级及双方禁用公式边界。',
       '可选数据缺口诚实降级，必要父项继续严格验证。',
       ['implementation-14-optional-p2-replay.md','verification-p2-running-129.json'],
       end=stamp('verification-p2-running-129.json'),result='复审完成',
       details=['02:37是修复/复审结果已记录并启动合并回归的时点，不是修复起点。','当时mypy94文件、Ruff及两轴复审通过；最终合并结果见持久回归行。']),
 entry('p2lost','P2首次合并回归中断','最后日志14% / 退出码未知','interrupted',
       '第129批工具会话与旧进程后来已不存在，未取得终态；保留原日志和未知结果，按相同范围重新验证。',
       '保证只有真实完成的验证才能成为验收依据。',
       ['verification-p2-running-129.json','verification-p2-interrupted-130.json'],
       start=stamp('verification-p2-running-129.json'),end=stamp('verification-p2-interrupted-130.json'),kind='unknown',result='终态丢失',
       details=['虚线为启动记录至发现中断的观察窗口，实际停止时刻未知。','不能把整个窗口视为持续运行，更不能据此计算损失工时。']),
 entry('p2pass','P2持久回归与最终核验','484项通过 / 前后核验通过','done',
       '独立持久执行器完成五文件合并回归并自行保存终态；后续根验收确认228输入、4受保护文件、91安装源码及53依赖一致。',
       '取得绑定明确版本、可恢复且可核验的回归结果。',
       ['verification-p2-terminal-130.json','verification-p2-acceptance-133.json'],
       start=stamp('verification-p2-terminal-130.json','started_at'),end=stamp('verification-p2-terminal-130.json','finished_at'),kind='execution',result='限定范围通过',
       details=['实线为持久执行器真实起止07:45:49—08:12:04，含前后核验。','pytest为484项、1545.32秒；08:13根验收通过。本批未提交，整票及全套仍未完成。']),
 entry('q1','Q1映射研究到公开反例','规则已明确 / 反例已失败','issue',
       '研究明确同一Jan–Mar区间源格的显式映射与绑定方式；首个公开测试5.09秒失败，命中mapping_unresolved，生产映射尚未实现。',
       '让产能Q1累计值的来源复用有明确、可执行的证据约束。',
       ['capacity-q1-implementation-boundary.md','verification-capacity-q1-boundary-131.json','verification-closure-progress-135.json','verification-capacity-red-134.txt'],
       start=stamp('verification-capacity-q1-boundary-131.json','verified_at'),end=stamp('verification-closure-progress-135.json'),kind='window',result='已复现待修',
       details=['条形为研究验收到反例结果记录的窗口。09:05是汇总记录时间，非反例精确结束时间。','映射需绑定原件、新定义和审查材料；旧字面审计和收据保持原结论。']),
 entry('a18','A18原件与收据对账','250原件 / 268有效收据','research',
       '对账1858标量身份及收据/规范化字段，核对v1/v2唯一M2数值变化已修。分类为1857字面相符与1个Q1映射待绑定。',
       '确认既有采集准备材料覆盖完整、差异清楚且可追溯。',
       ['a18-audit-coverage-reconciliation.md','verification-a18-reconciliation-132.json'],
       end=stamp('verification-a18-reconciliation-132.json','verified_at'),result='对账完成',
       details=['本轮复核承接既有字面审计，不声称重新提取全部1858个官方原格。','对账完成不等于正式来源认证；未新增这250份原件或268份收据。']),
 entry('sqlite','SQLite可控诊断与收口方案','单一交叠未复现 / 根因未知','issue',
       '保持真实心跳写事务未提交，原件查询仍完成；10.45秒诊断证明该交叠未触发原故障。任务补充关闭条件、四消费路径矩阵及分层验收。',
       '建立可控诊断反馈，减少无依据修改与反复整套重跑。',
       ['verification-closure-progress-135.json','verification-sqlite-controlled-135.txt'],
       end=stamp('verification-closure-progress-135.json'),result='继续定位',
       details=['09:05为结果记录时点；诊断未覆盖完整Worker执行，不构成锁问题已修复。'])
]

issue_paths = {p.name[:2]: str(p.relative_to(P)) for p in (P/'issues').glob('*.md')}
for name in issue_paths.values(): capture(name)
for name in ['spec.md','continuation-status.md','credit-impulse-integrity-boundary.md','worker-registered-catalog-public-boundary.md','progress-checkpoint-131.md']:
    capture(name)

def plan(id,label,note,state,phase,until,depends,summary,accept,issues):
    return dict(id=id,label=label,note=note,state=state,phase=phase,until=until,depends=depends,
                summary=summary,acceptance=accept,sources=[capture(issue_paths[x]) for x in issues],
                start=None,end=None,scheduling='待排期；阶段位置为建议顺序，不代表日期或工期')

pending=[
 plan('S1','SQLite锁根因与修复','优先诊断','issue',0,1,[],
      '沿原完整Worker失败路径核对连接、事务、心跳及关闭交叠；已有一种交叠未复现。',
      '建立原故障的可重复证据，修复后相关回归及最终全套通过。',['17','19']),
 plan('S2','Worker新目录与官方路由','待合法执行样本','blocked',0,1,[],
      '修复两处数据库目录传递遗漏，接通官方定向刷新；区分必需失败阻断和可选失败降级。',
      '经合法模型生命周期构建隔离样本，公开正常与异常路径通过，保留原始错误。',['17','19']),
 plan('S3','Q1产能显式映射','反例已建立','issue',0,1,[],
      '将同区间映射材料绑定具体原件、新定义、审查证据和消费校验。',
      '公开正例通过；错原格、错期次、错单位、坏制品及Q2—Q4误复用被拒绝。',['13','19']),
 plan('S4','信用脉冲整窗与GDP修订','依赖兼容修订基线','blocked',0,1,[],
      '校验24个月和8季度所需全部输入及差分基线；研究样本对应25社融+9GDP累计父项。',
      '坏必需父项不被采用，坏最新输入不退回旧窗口；GDP跨修订口径不明时明确不可用。',['13','14','19']),
 plan('D1','来源认证与历史公开时间','多项证据缺口','blocked',0,2,[],
      '补三核心历史公开时间、北交所、CNY030、估值口径与三指数样本；正式绑定PMI等来源包，补RRR事件/前置状态及P2日历鲜度。',
      '来源身份、字段、单位、修订和PUBLIC/SYSTEM资格逐项有据；未知PUBLIC保持未知。',['04','05','06','07','13','14']),
 plan('D2','股票广度与成交金额','依赖历史股票池','blocked',0,1,[],
      '历史股票池、停牌/新股、点时复权、MA120/新高新低预热、完整成交金额与上涨金额占比。',
      '08股票池完成后验收09/10；未知盘后金额不填零，参与分母可复核。',['08','09','10']),
 plan('D3','商品合约与篮子规则','依赖原件及规则冻结','blocked',0,1,[],
      '补PP官方行情、真实月份合约及历史可知映射、仓单单位；冻结选月/换月/权重/基点并重建去生猪篮子。',
      '11真实合约证据支撑12篮子，七袖套贡献及每期血缘可以重建。',['11','12']),
 plan('G1','最终版本软件回归','当前全套仍有失败','pending',2,2,['S1','S2','S3','S4'],
      '统一最终代码、依赖及证据版本，先关联回归再完整套件，检查实际采用集合与四消费路径。',
      '所有已确认软件缺陷关闭，真实退出码通过且前后指纹一致；历史失败保留。',['17','19','22']),
 plan('G2','完整真实候选与校准','依赖完整来源和规则','pending',3,3,['S2','S3','S4','D1','D2','D3'],
      '汇总61项目录，验证42项P1及P2明确状态，绑定认证、公式、执行指纹并完成实际机器校准。',
      '真实完整不可变候选成立；合成组件通过与正式认证分别记录。',['19']),
 plan('V1','固定120交易日双时点回放','候选完成后执行','pending',4,4,['G2'],
      '执行2026-03-09至2026-08-28固定120个中国交易日及预热，分别核PUBLIC与SYSTEM和新旧差异。',
      '逐日输入、阶段及上下文可归因；不缩窗、挪窗或改写已发布历史。',['21']),
 plan('V2','真实检索基准与AI报告','依赖可用模型和运行链','pending',4,4,['G2','S2'],
      '按同组分层真实缺口测Tavily/Exa模型可用补齐率；验证真实CLI网络、报告证据及合格AI解释。',
      '保留成功/失败样本与分母；候选网址、原文取得和模型实际采用分开统计。',['18','20']),
 plan('V3','目标日演练与正式切换','最终验收前置未齐','pending',5,5,['G1','V1','V2'],
      '真实目标日演练、Worker中断恢复、API/Dashboard/报告一致性，完成既有激活与切换验收流程。',
      '18/20/21完成；最终指纹匹配、具体清单及必要授权满足后切换，验证恢复/回退边界。',['22'])
]

data=dict(title='Pring · 最近12小时推进与后续执行',schema='archify-custom-gantt-v1',
          period_start=START,snapshot_at=END,timezone='Asia/Shanghai',tasks=tasks,pending=pending,sources=sources,
          time_semantics='实线表示有起止记录的执行；浅色条表示记录覆盖窗口；虚线表示实际停止时刻未知；菱形表示结果记录时点。条形不等于连续工时。',
          plan_semantics='后续采用阶段轴，不设未经确认的日期；条宽不代表工期，具体前置见各项详情。',
          phases=['立即推进','补齐前置','软件验收','完整候选','真实验收','正式切换'],
          goal='让完整运行稳定使用可信、点时正确的数据，并形成可验证的Pring输出与真实报告。',
          caution='各批测试范围重叠，不累加。软件切片通过不代表真实认证、完整候选、120日回放或正式切换。',
          head='99c495a217b66d4bca9d6ceae4688ee69d4382bb')
for t in tasks:
    assert datetime.fromisoformat(t['start']) <= datetime.fromisoformat(t['end']) <= datetime.fromisoformat(END)
    assert datetime.fromisoformat(t['end']) >= datetime.fromisoformat(START)
assert datetime.fromisoformat(END)-datetime.fromisoformat(START)==timedelta(hours=12)
OUT.mkdir(parents=True,exist_ok=True)
with (OUT/(BASE+'.gantt.json')).open('x',encoding='utf-8') as f:
    json.dump(data,f,ensure_ascii=False,indent=2)
    f.write('\n')
protected={}
for p in OUT.glob('pring-execution-gantt*'):
    if p.is_file(): protected[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
for p in [Path('/mnt/d/cursor/archify/archify/assets/template.html'),Path('/mnt/d/cursor/archify/archify/renderers/shared/utils.mjs')]:
    protected[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
with (TASK/'protected-before.json').open('x') as f:json.dump(protected,f,indent=2)
print(json.dumps({'tasks':len(tasks),'pending':len(pending),'sources':len(sources),'output':str(OUT/(BASE+'.gantt.json'))}))
