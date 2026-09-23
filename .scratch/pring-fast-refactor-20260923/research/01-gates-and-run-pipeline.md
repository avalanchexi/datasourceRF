# 现有门禁与完整运行流程盘点

日期：2026-09-23。对应票：[01](../issues/01-inventory-gates-and-run-pipeline.md)。
方法：按 [Codex 分工](../../../docs/agents/codex-delegation.md) 以 `codex exec -s read-only` 静态读码（退出 0，约 16 万 tokens），主会话回核关键行号。
**全文均为读码推断，未实测**（未跑测试、未跑应用或采集）。耗时全部引自历史记录，是整场测试或整窗命令的时间，不是单道门的时间。代码路径相对 `src/pring_cycle/`。

## 结论

1. **要删的是一整条“认证→候选准入→校准/回放→激活验收→系统验收/演练→切换”链**，它与完整运行主链（`run-submit` → Worker → 投影 → 报告）基本分开，所以大部分可以整条旁路掉。
2. 能整文件移除的只有 5 个：`material_preflight.py`、`candidate_admission.py`、`model_evaluation.py`、`acceptance.py`、`cutover.py`。另有 2 个在迁出少量函数后可删：`source_certification.py`、`rehearsals.py`。
3. **认证和逐值发布证据是嵌在主链里的**，不能靠删文件去掉：`source_contract_review.py`、`evidence.py`、`search_evidence.py`、`full_run_requirements.py` 这几个文件既有要删的认证门，也有要保留的接口/结构校验和新门①所需逻辑，只能按判断逐处改。
4. 现有检查**不等于**新三道门：①完整性现在按统计期与窗口相交来查（`projections.py:449`），低频指标只展开最新期；②时效现在用 10/95/190/370 自然日的固定年龄（`metric_contracts.py:45`），不是按注册表的“频率＋发布滞后＋宽限”。这两道都得新写。
5. P1 普通缺失现在已经只降级不阻断（`worker.py:1087`），但 TuShare 的非 P2 解析异常会重新抛出，导致整次运行变成 `action_required`（`worker.py:1652–1667`，**已回核**）。要满足“P1 缺失不阻断”，这里必须改。

## 一、现有主流程（公开命令 → 投影 → 报告）

| 顺序 | 步骤 | 函数 file:line | 说明 |
|---|---|---|---|
| A1 | `run-submit --type manual_full` | `cli.py:55 main`、`cli.py:103 _v1_command`；参数定义在 `cli.py:797` | 解析命令、取生效模型 |
| A2 | 创建父运行 | `runs.py:143 submit` | 校验截止模式、做幂等处理、写入队列 |
| A3 | Worker 取任务 | `worker.py:82 run_worker`、`:152 process_pending_run` | 检查运行库、拿租约、启动心跳 |
| A4 | 执行前检查与恢复 | `worker.py:220 _execute_run` | 核对生效模型和来源合同；有检查点就复用 |
| A5 | 刷新三核心 | `worker.py:1700` → `core_history.py:52 refresh_core_history` | 往前取 280 个自然日，截最近 160 个交易日；先查独立日历 |
| A6 | 捕获、解析、入库 | `source_adapters.py:164/176`、`acquisition.py:144 capture`、`evidence.py:502 append_source_claims` | 原始响应＋收据＋来源声明 |
| A7 | 刷新解释性来源 | `worker.py:1409 refresh_context_sources`、`:1319 refresh_eia_context` | EIA / ECB / TuShare 等 |
| A8 | 规划缺口 | `full_retrieval.py:47 retrieve`、`:162 _plan` | 日历、期次、公式父输入 |
| A9 | 检索补缺 | `retrieval.py:83`、`retrieval_ledger.py:97 reserve`、`search_evidence.py:494` | 顺序：本地→TuShare→官方→Tavily→Exa→AI |
| A10 | 冻结截止点、最终评估 | `runs.py:578 freeze_cutoffs`、`full_retrieval.py:377 evaluate` | |
| A11 | 核心状态与上下文加工 | `worker.py:900 _core_readiness`、`domain/trend.py:62`、`context_projection.py:238` | |
| A12 | 冻结输入、组装发布集 | `evidence.py:1280 freeze_snapshot`、`p0.py:54 publish` | 三核心未就绪时只记评估 |
| A13 | 校验并原子发布投影 | `projections.py:364`、`:78 publish` | |
| A14 | 关联产物 | `runs.py:877`、`full_retrieval.py:490`、`models.py:911` | |
| A15 | 报告 | `worker.py:1733` → `reports.py:136`、`:597 generate` | 依次试 Codex CLI、Claude CLI，都不行就出确定性降级报告 |

旁路链（不属于每次完整运行）：B1 各 `*-refresh` 数据准备；B2 `source_history.py:70/297` 历史 smoke；B3 `model-source-certify`（`source_certification.py:105`、`candidate_admission.py:162`）；B4 `model-input-preflight`（`material_preflight.py:47`，Worker 不会调用）；B5 `model-accept/replay/activate`（`model_evaluation.py:140/225`、`models.py:341/616/474`）；B6 系统验收、演练、切换（`acceptance.py:113`、`rehearsals.py:52/103`、`cutover.py:44/179`）。

## 二、门禁清单

耗时代号及来源：
- **T1** = 整窗预检 310.18 秒；单日预检 123.73→26.82 秒；旧整窗 1830.30 秒被中止。来源：`continuation-status.md:579–580`、`:571`。
- **T2** = 准入＋校准＋120 日回放＋激活用例 1741.68 秒（含冷材料构建）。来源：`slow-test-inventory-20260918.md:101`。
- **T3** = Worker 两目标日发布链用例 748.94 / 746.95 秒。来源：同文件 `:102–103`。
- **T4** = 可选 GDP 降级用例 362.44 秒；核心缺失阻断用例 90.37 秒。
- **T5** = 损坏原件上下文回放用例 68.56 秒。
- 另有记录：全套 1848 项共 8865 秒；v2 冷准备 315 秒（旧 1061 秒）。

“附属”指执行、事务层面的基础保护：建议保留，但不算作数据门。

| 门禁 | file:line | 判据 | 阻断后果 | 耗时 | 归属 |
|---|---|---|---|---|---|
| 运行库与磁盘容量 | `worker.py:83`、`:165`；`maintenance.py:61` | 库可用、剩余空间够 | 拒绝启动 | 未记录 | ③附属 |
| 命令、时区、幂等 | `runs.py:164/166/175/203` | 命令合法；同一请求绑定同一范围 | ValueError 或复用 | 未记录 | ③附属 |
| Worker 独占与恢复 | `runs.py:376/495/497` | 租约唯一；恢复状态合法且确认过外部调用 | 拒绝 | 未记录 | ③附属 |
| 生效模型一致 | `worker.py:241`、`:407` | 开始和发布前绑定同一个模型 | action_required | 未记录 | ③附属（保留显式切换） |
| 检查点/报告/投影绑定 | `worker.py:254/263/1777/1779` | 目标日、模型相互匹配 | 抛异常，任务回到待处理 | 未记录 | ③ |
| 定时 P0 截止 | `worker.py:278`、`:1697` | 定时运行没超过截止时刻 | scheduled_p0_deadline_elapsed | 未记录 | ②附属 |
| v3 来源合同封锁 | `source_contract_review.py:120` | v0003 定义被固定拒绝 | 写入、Worker、激活、报告都可能被拒 | 未记录 | **删除** |
| 目录/模型登记绑定 | `catalog_registry.py:65/105/109/137` | 同版本内容不漂移；目录与模型身份一致 | 拒绝 | 未记录 | 版本一致性归③；认证准入绑定删除 |
| 凭据缺失 | `cli.py:372`；`worker.py:1709` | CLI 需要凭据；Worker 缺凭据就跳过刷新 | CLI 拒绝；Worker 记缺口 | 未记录 | ③执行条件 |
| 核心接口结构 | `adapters.py:42–59` | 指标和单位正确、正价格、不重复、不乱序、不缺交易日 | 拒收序列 | 未记录 | ①③；其中 `:50` 的认证标签要求删除 |
| 核心日历 | `core_history.py:88/106/108` | 目标日在日历内；三核心与日历同日 | 抛异常 | 未记录 | ①②③ |
| 获取收据有效 | `acquisition.py:227/232/243/349`；`evidence.py:521/549` | 所属运行、时间、响应哈希一致 | 拒收 | 未记录 | ③（改为批次级追溯） |
| 标量结构 | `evidence.py:1392–1397`、`:1431–1437` | 定义、单位、维度、时间合法，非空有限值 | 拒绝入库 | 未记录 | ③ |
| 标量认证资格 | `evidence.py:1399`、`:1424`；`search_evidence.py:428` | 声明和定义都带合格认证标签 | 拒收或不选用 | 未记录 | **删除** |
| 注册接口/口径合同 | `source_contract_review.py:183/192/196/291/307/668` | 接口、代码、单位、统计期、维度匹配 | 拒绝声明 | 未记录 | ③（与认证同文件，不能一起删） |
| 逐值发布时间证明 | `source_contract_review.py:278/657`；`evidence.py:373`；`published_events.py:34/44` | 没有独立发布证据的值不许赋公开时间 | 拒收或不可采用 | 未记录 | 注册源部分**删除**；搜索原文验证归②③ |
| 消费时原件逐值重验 | `source_adapters.py:97/120`；`search_evidence.py:320/435` | 原始响应重新解析后要与选值一致 | 记缺口；核心缺口最终阻断 | 相关 T3/T5 | 接口/结构部分归③；重复逐值验收**删除**，改成批次校验 |
| 检索前发布门 | `full_retrieval.py:78`；`worker.py:624/635/644` | 已知公开期次，或已到 LPR 预期窗口 | 不检索，记等待缺口 | 未记录 | ②（改为频率＋滞后＋宽限） |
| 检索预算/负缓存 | `retrieval_ledger.py:321–342` | 单事件、单次、每日预算；P2 不用 AI | 跳过渠道，留缺口 | 相关用例 30.22 秒 | ③附属（保留） |
| 搜索结果可采用 | `search_evidence.py:570/608/636` | 下载官方文档并解析出完整输入 | candidate_validation_unresolved | 未记录 | ②③（按新 WebSearch 规则改写） |
| 120 日独立日历 | `full_run_requirements.py:51/82/87`；`worker.py:341–343`（**已回核**） | 正好 120 个交易日，末日为目标日，无冲突 | p0_required_calendar_unavailable | 未记录 | ①②；认证标签条件删除 |
| 核心逐日缺口 | `worker.py:344` | 最终计划里有核心期次不完整 | p0_required_calendar_period_missing，不发布 | 相关 T4 | ① |
| 公式父输入 | `full_run_requirements.py:137/151`；`full_retrieval.py:242/478` | 展开前期、同比、差分所需的输入 | 记缺口，派生结果不可用 | 未记录 | ①③ |
| 维度成员覆盖 | `search_evidence.py:390/394/405/455` | 每个成员恰好有一个合格值 | missing_members | 未记录 | ①③ |
| 多源冲突 | `evidence.py:1373`；`worker.py:941` | 差值超过容差 | conflicted：核心阻断，上下文降级 | 未记录 | ③（“合格来源”要去掉认证含义） |
| 公开时间边界 | `context_projection.py:662/667`；`evidence.py:1338` | 统计期不越界；公开时间早于截止点 | 过滤掉 | 未记录 | ②（保留边界，删除逐值证明） |
| 普通时效 | `context_projection.py:1737`；`metric_contracts.py:45`；`worker.py:943` | 核心要到目标日；上下文按固定年龄阈值 | 核心阻断；上下文 stale | 未记录 | ②（改成注册表频率规则） |
| P1/P2 普通缺失 | `worker.py:1087/1198/1218`；`p0.py:168` | 没有覆盖满目录；P1 日频覆盖 ≥95% | 警告，投影 degraded | 相关 T4 | ①②（保留可见缺口） |
| **P1 刷新异常上抛** | `worker.py:1652–1667`（**已回核**） | 非 P2 的 TypeError/ValueError 重新抛出 | 整次运行 action_required | 相关 T3 | ③保留拒收坏批次；**上升为全运行阻断这一点要改成缺口** |
| 三核心稳定状态 | `worker.py:939/945/952/974`；`domain/trend.py:65/109`；`p0.py:100` | 无缺失、陈旧、冲突，趋势稳定 | 不发布正式投影 | 相关 T4 | ①②③保留；认证标签删除 |
| 投影结构/阶段不变量 | `projections.py:355–414` | 数据集齐全、身份一致、阶段与核心匹配 | 拒绝发布 | 未记录 | ③ |
| 可见窗口 | `projections.py:449`；`reports.py:156` | 统计期与窗口相交；报告要求正好 120 条 | 拒绝 | 未记录 | ①②（要改成“窗口内发布”的语义） |
| 报告前置 | `reports.py:141/176/1167/1173` | 正式阶段或有效非典型组合；三核心齐全 | 不生成报告 | 未记录 | ①②③ |
| AI 输出边界/降级 | `reports.py:638/681/1178/1193/1227` | 不越工具边界、身份不变、引用合法 | 换下一个适配器，最后 completed_degraded | 单适配器上限 300 秒（`:705`） | ③附属（**保留降级**） |
| 独立材料预检 | `material_preflight.py:178/233/396/446/481` | 日历、原件、认证、维度、预热等诊断 | 有缺口就 blocked，否则永远 incomplete | T1 | **删除** |
| smoke 认证材料 | `rehearsals.py:291/323/352/356` | 哈希、指纹、登记、smoke 种类齐全 | 拒绝认证 | 未记录 | **删除** |
| 固定历史覆盖 | `source_history.py:648/662/665` | 固定的历史起止和条数 | smoke 失败 | 未记录 | **删除**（滚动窗口完整性归①） |
| 来源认证包准入 | `candidate_admission.py:181/186/205/206/396/412` | 正式包、审查结论、证据哈希齐全 | 不创建候选 | 含于 T2 | **删除** |
| P1 必须认证/固定范围 | `candidate_admission.py:244/290/292/369–374` | P1/核心已认证；校准/回放范围合法 | 拒绝候选 | 未记录 | **删除**（目录与公式结构校验迁到③） |
| 旧候选刷新 | `source_certification.py:252/255/257` | 只接受 v3，并再过合同门 | 被挡住 | 未记录 | **删除** |
| 校准验收 | `model_evaluation.py:157`；`models.py:387` | 冻结历史齐全，统计匹配基线 | 不能激活 | 含于 T2 | **删除** |
| 120 日候选回放 | `model_evaluation.py:233–347` | 认证交集窗口、无缺口、稳定性不退化、≤900 秒 | 回放失败 | T2 / T5 | **删除** |
| 上下文回放完整性 | `model_evaluation.py:756/847/932/938/1104/1119` | 认证、PUBLIC、原件、父血缘完整 | 验收失败 | T5 | **删除**（父输入逻辑归①③） |
| 激活前复核 | `models.py:489/491/509/558/560` | 有有效验收和回放，且显式批准 | 拒绝激活 | 含于 T2 | 验收部分**删除**；显式切换保留 |
| 30 交易日回退门 | `models.py:950/964/976` | 已确认、有前版本、在 30 个交易日内 | 拒绝回退 | 未记录 | 待定（新回退语义未决） |
| 系统软件/性能验收 | `acceptance.py:161/354/378` | 35 回归、故障注入、8 项性能门 | blocked | 未记录 | **删除**（其中的行为测试可以保留） |
| 真实演练 | `rehearsals.py:112–170` | 三核心 120 条、P1 样本、报告、页面可见 | 拒绝 | 未记录 | **删除** |
| 系统切换清单 | `cutover.py:108/167/189/211` | 验收、演练、指纹、旧系统停用全部满足 | blocked | 未记录 | **删除** |

## 三、删门后可整体移除的模块

| 模块 | 依据（生产代码的 import） | 条件 |
|---|---|---|
| `material_preflight.py` | 只有 `cli.py:389`、`:393`（**已回核**） | 同时删除 `model-input-preflight*` 命令 |
| `candidate_admission.py` | 只有 `cli.py:442`（**已回核**） | 先把目录、三核心、趋势参数的结构校验迁出 |
| `model_evaluation.py` | `cli.py:356/403`；`models.py:854/1095` | 在线趋势计算在 `domain/trend.py`，不受影响 |
| `acceptance.py` | `cli.py:568`；`cutover.py:14` | 与 cutover 一起删 |
| `cutover.py` | `cli.py:585/596/605` | 如果还要旧状态查询，先迁出读取函数 |
| `source_certification.py`（迁出后删） | `cli.py:450/459` | `:235` 编排了数据刷新，底层获取模块保留 |
| `rehearsals.py`（迁出后删） | `cli.py:572/576`；smoke 命令 `cli.py:168/610` | 保留 smoke 命令的话，先迁出 `store_source_smoke_result` |
| 可收缩：`model_outputs.py`、`context_replay_scope.py` | `models.py:22`、`model_evaluation.py:50`、`material_preflight.py:13` | 公式回看知识要先迁到新的需求规划 |

**只能部分修改的模块**：`source_contract_review.py`（被 evidence、worker、models、projections、reports、tushare_context 导入）、`full_run_requirements.py`、`search_evidence.py`、`retrieval_ledger.py`、`full_retrieval.py`、`source_history.py`、`evidence.py`、`acquisition.py`、`models.py`、`catalog_registry.py`、`published_events.py`，以及主链上的 `worker.py`、`projections.py`、`reports.py`、`context_projection.py`。

注意：旧迁移链有依赖，例如 `0004_evidence_extensions.py:8` 依赖 `0003_cutover`。删模块前要先解除这些依赖；数据库迁移单独处理。

## 四、保留的主流程步骤

1. 接收目标交易日，绑定模型版本和显式生效指针；保留幂等、租约、取消、恢复。
2. 用独立交易日历确定滚动 120 日窗口，并加上公式所需回看；不再准备校准/回放用的长历史。
3. 建立加工批次（目标日、接口与参数、代码版本），先读本地有效明细，再刷新注册来源。
4. **③** 校验接口、指标身份、单位、统计期、维度和非空值，记录条数、响应哈希和结构校验结果。
5. **②** 注册源按“频率＋发布滞后＋宽限”推定时效；WebSearch 结果按页面日期和统计期验证。
6. **①** 枚举窗口内应有的发布明细和公式父输入，形成缺口清单：三核心缺失阻断正式阶段，P1 缺失只显示缺口。
7. 在预算内检索补缺；准确性二选一：白名单原文解析，或与注册源交叉核对在容差内。
8. 冻结输入，计算趋势、持续性、三核心状态、正式阶段、特征卡、宏观/库存状态。
9. 校验输出结构，原子发布投影和阶段史；明细与汇总都挂批次 id。
10. 生成报告，保留 AI 降级报告。
11. 清理超过留存期的明细；汇总结果长期保存。

## 五、推断边界与记录冲突

- **已回核**：`worker.py:341–344`（日历门和核心缺口门）、`worker.py:1652–1667`（P1 异常上抛）、`material_preflight.py:481`（永远 incomplete 或 blocked）、`material_preflight`/`candidate_admission` 的 import 范围、T2/T3 的耗时行。其余行号是 Codex 读码给出的，**未逐条回核**。
- 09-22 的 `implementation-context.md:12` 说“尚无 CNY030 优先级迁移”，但当前 `candidate_admission.py:68` 已有这个分支，说明记录已部分过时，行号也有漂移。
- 核心 TuShare 的公开时间是留空的（`core_history.py:135` 附近），完整运行里的核心走 SYSTEM 路径（`search_evidence.py:125`），所以 PUBLIC 逐值门并不是每次运行都会经过。
- 核心就绪检查的是整段读出的序列（`worker.py:941–952`），显示时才截最近 120 条，因此旧历史里的冲突或坏原件可能拖累当前运行。新留存模型可以消除这个问题。
- `retrieval.py:97` 允许 `ai_websearch` 渠道，但 Worker 的生产适配器没有注册它（读码推断），这个渠道实际上是未接通的。
- “全套十分钟”只是目标（`cutover.py:288`）；真正的硬门是 `acceptance.py:354` 的 8 项性能检查，本身也在删除之列。
- 现有 ADR 0006、0012、0016–0019 仍然写着认证、回放、逐值发布证据的要求，需要由票 09 用新 ADR 显式取代。
