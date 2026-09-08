# 新登记目录三核心消费边界

2026-09-08；读取时 HEAD=`b8cf9b3091074ede751fb7c09e30daa150eb05dc`，下表指纹绑定实际工作树，包含父代理正在推进的其他切片。只读源码、规格及既有核心研究/测试；没有执行应用、测试、网络、账户调用、生产查询或认证。唯一写入本报告。

**三核心的新目录采集尚有两个串行阻断：`refresh_core_history` 未向定义解析传数据库；通过该点后，新目录来源守卫尚无三核心契约。** 数据仓库的版本化点时查询、输入选择、P0 数据结构和输入 trace 已有能力，不需要另建核心目录、换指数或放宽来源认证。

## 1. 已定契约可以直接实施

[实际 API 身份](../../src/pring_cycle/source_adapters.py#L17)、[目录 source_codes](../../src/pring_cycle/catalog.py#L106)和[官方语义复核](research-04.md#L20)一致：

| metric_id | provider / API / ts_code | 保存字段与精确来源身份 | 语义边界 |
|---|---|---|---|
| CN_BOND_CORE_000012 | tushare / index_daily / 000012.SH | close；`tushare:index_daily:000012.SH:YYYY-MM-DD` | 上证国债指数公式含全价市值、利息与再投资，不改成净价、收益率或 CNY030。 |
| CN_EQUITY_CORE_000985 | tushare / index_daily / 000985.CSI | close；`tushare:index_daily:000985.CSI:YYYY-MM-DD` | 中证全指现有核心身份，不换 CSI300、等权全市场或衍生收益指数。 |
| CN_COMMODITY_CORE_NHII | tushare / fut_index_daily / NHII.NH | close；`tushare:fut_index_daily:NHII.NH:YYYY-MM-DD` | 南华工业品指数原序列，不换 NHCI、单合约或自行重建篮子。 |

三项均是 `priority=P0 / role=core_barometer / unit=index_points / allowed_units=(index_points,) / frequency=daily / dimensions=()`；声明维度 `{}`，`period_kind=business_day`、start=end=该 bar 的统计日。release_event_family 分别为小写 metric_id，release_rule=`china_trading_day_source_schedule`，release_timezone=`Asia/Shanghai`，这些规则名**不提供实际日线发布时间**。[目录构造](../../src/pring_cycle/catalog.py#L271)、[单位与允许单位](../../src/pring_cycle/catalog.py#L461)、[频率](../../src/pring_cycle/catalog.py#L540)、[发布规则](../../src/pring_cycle/catalog.py#L661)。

`acquire_core_bars` 已明确请求 `ts_code,trade_date,close,pre_close,pct_chg`，按独立日历严格验完整日序；[解析 L218–247](../../src/pring_cycle/source_adapters.py#L218)对 index_daily 的 pct_chg 除 100，对 fut_index_daily 不除，二者均变成比率形式的 `official_return`。该字段与 pre_close 保留在 raw/normalized bar，当前标量只存 close，不能把收益率直接当指数点位。身份、正价格、重复/缺日检查在[validate_core_market_bars](../../src/pring_cycle/adapters.py#L35)，不是缺失待补项。新来源守卫应复用这些已定约束并比对新定义结构，不迁移旧 certified 标签。

## 2. 实际调用链与最小修复点

| 公共边界 | 当前确定行为 | 下一切片边界 |
|---|---|---|
| 新目录登记 | [registered_definitions / registered_metric_definition](../../src/pring_cycle/catalog_registry.py#L71)已验证目录哈希及与准入模型的对应；同版本异定义在 L49–67 拒绝。 | 已实现，不能为核心再建旁路 registry。测试必须经过现有准入建立真实登记，不只构造同名版本字符串。 |
| 原件取得→定义解析 | [refresh_core_history L78–131](../../src/pring_cycle/core_history.py#L78)先取日历和三核心，保存规范化制品，随后 `metric_definition(... definition_version=...)` **未传 database_path**；[catalog L409–414](../../src/pring_cycle/catalog.py#L409)对真正新版本报 `unknown_metric_definition_version`。 | 给该公开入口传 `paths.database`，最好在外部请求前核三核心定义，避免已知不支持目录仍发请求；失败时已存在原件保留。当前这是静态确定分支，本轮没有新 RED。 |
| 声明写入 | [EvidenceRepository._validate_claim L1207–1231](../../src/pring_cycle/evidence.py#L1207)已用数据库解析定义；certified 声明进入 [require_registered_source_contract L175–185](../../src/pring_cycle/source_contract_review.py#L175)，三核心均未列入支持契约。 | 新增仅这三个精确身份的 TuShare 核心分支，校验定义结构、provider、单位、空维度和严格同日。不能仅加 metric 白名单，也不改 v3 否定性审查。 |
| 来源引用/认证状态 | 守卫当前参数没有 source_reference；真实 adapter 验 ts_code，P0 的 [selected_core_claim_is_valid](../../src/pring_cycle/source_adapters.py#L24)另外核精确 `provider/API/code/date`。parser L236 生成的 MarketBar.certification_status 总是 certified，历史导入 L157 直接取它。 | 若要求直接 Evidence 公共写入口也拒绝错 API/code 的声明，最窄是让核心校验得到 source_reference；不能把来源引用检查仅留到 P0。未认证定义仍受 `evidence_source_not_certified_by_model` 拒绝，不因 parser 字符串而授认证；这批不新增未认证核心目录准入旁路。 |
| 双点时与原件 trace | [core_history L125–159](../../src/pring_cycle/core_history.py#L125)明确 TuShare 日线无可靠 PUBLIC，保留未知；逐 metric/day 关联对应 acquired receipt，收到及校验时钟分别记录，L163 批量 append。仓库 [metric_series](../../src/pring_cycle/evidence.py#L770)支持 definition_version、PUBLIC/SYSTEM；[trace](../../src/pring_cycle/evidence.py#L901)按当时可见 claim 返回对应回执。 | 已具备，不需要另存假发布事件或倒填取得时间。初次新目录原件可 SYSTEM 可读而 PUBLIC 为空。相同日期新取得/修订必须保留新回执与旧可见快照，不能追认旧原件为新请求。 |
| 核心输入选择 | [ModelInputSelector](../../src/pring_cycle/search_evidence.py#L49)先核登记清单；L95–97 已传数据库解析新定义，空维度走 `{}` 一成员。L72–88 对 full_run＋SYSTEM＋核心明确走基础仓库，过滤目标日之后的 bar。 | 无新目录专属拒绝。**保留核心正式 SYSTEM 输入的既有规则**：未知 PUBLIC 不是传输失败，也不自动阻止已认证核心的 SYSTEM 分析。单指标目标检索及 PUBLIC 模式仍按各自 TargetBound/公开时点规则，不能混用结果。 |
| P0/趋势/输入版本 | [Worker._core_readiness L883–969](../../src/pring_cycle/worker.py#L883)按传入 definition_version 取 SYSTEM 序列，核目标日、冲突、来源身份/认证/质量和数值，再调用 evaluate_trend。展示最后 120 条，同时另留完整预热 selected_claim_ids；[L366–383](../../src/pring_cycle/worker.py#L366)将其冻结进 evidence snapshot。 | P0 本身没有目录白名单；既定三核心固定映射与模型一致。保留全部状态预热 trace，不能以 120 条展示误当完整趋势输入。来源缺件时 reason/state 保持不可用。 |
| 独立日历和 P0 发布 | [required_calendar](../../src/pring_cycle/full_run_requirements.py#L16)可从独立 trade_cal 收据取精确 120 日；不是从价格行反造日历。[P0ProjectionService.publish L68–124](../../src/pring_cycle/p0.py#L68)缺资产状态或非 validated 时记录 assessment、返回 action_required；L141/202 保留完整模型输入清单。 | 当前能力足够沿用。`refresh_core_history` 取得日历已有对应 `tushare-core-parser-v0002` 收据，不必制造 P0 运维标量。 |

这里的“来源契约通过”仍只是已批准新定义能被当前 parser 消费。正式准入要求三核心和 42 个 P1 的实际来源包；[候选契约 L15、31、35–37](candidate-admission-contract.md#L15)及[票19验收](issues/19-immutable-candidate-catalog.md#L14)均保持。正式 Worker 的 [active 校验 L223–233](../../src/pring_cycle/worker.py#L223)及发布前再次校验 L392–394 不是本批需解除的阻断。

## 3. 可直接落地的第一个公开纵向测试

使用现有正式准入的 **隔离 synthetic 请求/审查 fixture** 登记一个新完整目录；不借旧 v3 清单改名、不 patch gate、不激活生产。将三核心 transport 构造成实际 bytes JSON，外部数据和 clock 可替换，parser、收据、目录读取、仓库和选择器保持真实。

1. 调 `refresh_core_history(paths, TushareCoreAdapter(...), start=end=某测试交易日, definition_version=新登记版本)`。日历一个请求，三核心各一个请求，共 **4 个物理取件**。三组 bar 用独立固定期待 close=101、pre_close=100；两个 index_daily 的 pct_chg=1，NHII 的 pct_chg=0.01，均归一为 official_return=0.01。先在未修代码观察新版本解析拒绝；补数据库参数后观察核心来源守卫拒绝；最终三条 close 声明与四份原件/回执保留。
2. 对三指标调用 `EvidenceRepository.metric_series(... definition_version=新版本)`：取得/校验完成前 SYSTEM 无值，之后各为101；PUBLIC 仍空。`trace` 核各声明只关联其正确代码请求，raw 为输入原字节，normalized 保留 close/pre_close/official_return；旧版本或别的 API/code 回执不能混入。
3. 用绑定该候选的 **synthetic full_run RunRecord** 调公共 `ModelInputSelector(..., mode=SYSTEM).select(当天核心 scope)`，观察三项均有正确 selected_claim_id。此处只评价输入，不执行 Worker，**不要求或声称候选已生效**；PUBLIC 同范围仍缺。`full_run` 的 SYSTEM 分支是现有语义，不能为让 PUBLIC 正例成功写固定收盘时间。
4. 同一公开取数入口的反例：错 ts_code（NHCI/CNY030 等）、缺一个交易日、重复日期、非正 close、缺 raw bytes、错新定义单位/维度/来源代码，均不形成有效核心输入；未注册版本或未认证定义不能越过准入。日期完整性/单位归一化已有[adapter 测试](../../tests/adapters/test_tushare_core_adapter.py#L45)，未知 PUBLIC 与逐请求 trace 已有[历史取得测试](../../tests/integration/test_core_history_refresh.py#L121)，应把这些行为迁到真正新登记目录，而非只测 guard 函数。

这是一条可立即修到输入 trace 的最小 seam，**单日样本不足以产生 P0 趋势**。下一层采用有足够预热的隔离 fixture，经现有 acceptance/active 流程后调用 `process_pending_run`，验证实际 Worker→readiness→趋势→snapshot→P0 的关联；维持生产 active gate，不将 `P0ProjectionService` 直接喂假 readiness 或 `project_core_fixture` 的成功误称真实采集链已经端到端完成。Worker 当前定向核心取得最多160个最近观测（L1540–1546），展示120与隐藏预热分开；本批不改变既定趋势参数、长期校准或120日目标范围。

## 4. 仍属真实证据/后续验收的前置

- [票04 L17–21、40](issues/04-core-public-time-certification.md#L17)及[研究04 L126–132](research-04.md#L126)：CSI 两核心已有259日数值对照，但历史 PUBLIC/版本证据仍缺；NHII 仅15个正确目标日报，105个目标日未取得正确日报，最小状态预热与更早历史方法边界亦未齐。软件测试不能补这些证据，000012含息语义须进入新正式审查。
- 源代码 `evaluate_history` 可接候选模型 ID、解析新目录版本并查询 PUBLIC；无数据时在[model_evaluation L215–268](../../src/pring_cycle/model_evaluation.py#L215)报 calibration_evidence_incomplete。这是应有数据前置，不能以 SYSTEM 回填取代。当前核心历史算法在 requested_end 的 final_cutoff 一次构建 final_series，再计算全序列趋势（L237–300）；**单次末日 PUBLIC 成功不是逐日修订 cutoff 已验证**。应为后续120日验收保留“期后才公开的修订不得倒改此前 cutoff”公共反例；本轮未执行该反例，不将此静态风险说成已复现生产问题，也不扩大本切片去重写校准算法。
- [规格 L97–101、125、142](spec.md#L97)要求新时间规则、精确窗口和最小预热；[候选契约 L37](candidate-admission-contract.md#L37)固定长期校准自2018-06-01，正式重放边界及认证交集不能靠本次源码接通缩短。synthetic 仅证明软件，正式来源认证、完整候选、重放和真实切换继续各自验收。

## 输入快照与交付

下列为读取时输入快照；父代理后续源码、票19评论可正常演进，不能把本研究指纹称为最终提交指纹。本轮唯一交付 `.scratch/pring-data-acquisition-repair/new-catalog-core-consumption-boundary.md`。

| 输入 | bytes | SHA256 |
|---|---:|---|
| [source_contract_review.py](../../src/pring_cycle/source_contract_review.py) | 13045 | `3bf022318ff950c904d1f775155325e0a58c3294cd240b2d52dc05cf7dfb957d` |
| [source_adapters.py](../../src/pring_cycle/source_adapters.py) | 10018 | `518093f469e09efe69fe60e4b49939aff1e30cea46d788db3710fcc137425868` |
| [core_history.py](../../src/pring_cycle/core_history.py) | 7814 | `dce17e2d957ffe6a5d2175accd19e0fda207dad0a523d8516b44e8d3f09128bc` |
| [p0.py](../../src/pring_cycle/p0.py) | 13580 | `8cc460ce27e5820127af10e16feb11c4291f9c207240242674b86d2c801002c5` |
| [evidence.py](../../src/pring_cycle/evidence.py) | 56496 | `8d00436962c6dc8315f26d64527789945b89f6f0ebc99f2294a8eb1e88a6ff6d` |
| [catalog_registry.py](../../src/pring_cycle/catalog_registry.py) | 4293 | `41ddb91573330a206e388b9b32665e511a286a22a6eb1eeff674803dabda0544` |
| [catalog.py](../../src/pring_cycle/catalog.py) | 25978 | `fe8dd4e21d563448c31af535f3886fc7fb053133de6346d5d9c4a627a91e7c5c` |
| [adapters.py](../../src/pring_cycle/adapters.py) | 1948 | `05e6856cd7bb8e382f17dc36f1f78c4a08cccf6ab7073689f82b23bb7a546ff0` |
| [worker.py](../../src/pring_cycle/worker.py) | 58270 | `e58ef5f21f6159448d959cc1bf5b8092438ed72781d829418e5b79c1b5163c6f` |
| [search_evidence.py](../../src/pring_cycle/search_evidence.py) | 15734 | `dc5d6f00536e7792e49fc19171effa30f0a8af1688c5a491c8c75ccc97c55b45` |
| [model_evaluation.py](../../src/pring_cycle/model_evaluation.py) | 39345 | `20b23474ea193ea8a4a3997a932bb7dc2620afeddda359a2d78361d903b82fa3` |
| [full_run_requirements.py](../../src/pring_cycle/full_run_requirements.py) | 7437 | `5cd78ef07dcc138102457849cd0a5d06d2c7eae5603c9cdb5c30707c0404e2d8` |
| [test_core_history_refresh.py](../../tests/integration/test_core_history_refresh.py) | 23155 | `e1c9814612daecce4cf0e12ab10737761fe381afa573c74c81ad0133825624dc` |
| [test_tushare_core_adapter.py](../../tests/adapters/test_tushare_core_adapter.py) | 3096 | `21e6483e134e0fecd7c4972d584d75d8eaa80ad03ba1ad94f6f60da02c7ee93a` |
| [test_core_fixture_cli.py](../../tests/e2e/test_core_fixture_cli.py) | 7183 | `eef7d8028e26922346f743a2e0f98d669799451546d6645832f28b269d7731b1` |
| [spec.md](spec.md) | 27762 | `f5c32c407f216841b2afed0aaab3863868bdc394d9057207d25dbc9e9a561cc4` |
| [04-core-public-time-certification.md](issues/04-core-public-time-certification.md) | 2990 | `90a4e4da0f55a66e6dce45ffb71503da348949ba4fd089ed6d0b33dd67f9b524` |
| [19-immutable-candidate-catalog.md](issues/19-immutable-candidate-catalog.md) | 9329 | `99137aafa9713b88664658f2d823a3cc05f897c323c315f07836e958c6e7672f` |
| [candidate-admission-contract.md](candidate-admission-contract.md) | 4937 | `649b65963e52f1f1dc2a217dd513427ba0f1d7084c062f1266df56c15ff551fc` |
| [research-04.md](research-04.md) | 41358 | `40d6c8c352948599af6d5ee1e6ec37d83c4aa584b789d568d327315643002ca3` |
