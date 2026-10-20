| 票 | 通过 | 不通过 | 已被取代 | 无法核对 | 建议 |
|---|---:|---:|---:|---:|---|
| 01: 单个核心指标贯通 | 4 | 0 | 1 | 0 | 可关 done |
| 02: 三核心与同类资产 | 4 | 0 | 1 | 0 | 可关 done |
| 03: 海外与汇率 | 4 | 0 | 1 | 0 | 可关 done |
| 04: 周期结论与宏观确认 | 3 | 0 | 3 | 0 | 可关 done |
| 05: 库存周期与仓单 | 5 | 0 | 0 | 0 | 可关 done |
| 06: 阶段历史与发布日历 | 4 | 0 | 1 | 0 | 可关 done |
| 07: 解读与报告工作区 | 3 | 0 | 2 | 0 | 可关 done |
| 08: 完整证据追溯 | 5 | 0 | 0 | 0 | 可关 done |
| 09: 运行健康摘要 | 4 | 0 | 0 | 1 | 需用户看 |
| 10: 取数流向与缺期诊断 | 7 | 0 | 0 | 0 | 可关 done |
| 11: 运行操作与持续观察 | 4 | 0 | 0 | 1 | 需用户看 |
| 12: 访问配置贯通 | 4 | 0 | 0 | 1 | 需用户看 |
| 13: 入口切换与整站验收 | 3 | 0 | 1 | 2 | 需用户看 |
| **合计（69项）** | **54** | **0** | **10** | **5** | 建议不等于已改票状态 |

核对日期：2026-10-20（北京时间）。仅浏览 `http://127.0.0.1:8069/`；所有脚本、证据、截图与本报告均在当前目录。未改仓库/配置/运行库，未发起、停止或恢复应用服务/Worker，未提交表单/命令，未访问外网或其他端口。启动的仅为用户指定的验收Python与无头Chromium。

本次首页冻结身份：目标日 **2026-10-19**，投影 **projection-554b0640f5f9d167fb6a**，产出运行 **run-153de3060fa2b0ebc424**，模型 **model-v0015**，分析截止 **2026-10-19 19:11:32 北京时间**。用户告知v0016已激活；页面显示的是既有v0015投影，不足以推断激活失败。宏观块实际为“该投影生成时尚无宏观判断”。`.scratch/macro-stage-20261017/spec.md:120` 明确规定旧投影保留现状并提示、不补算，因此不将旧板仍显示“正式阶段/宏观事后确认”误判回归。检查期间另有既有run-3ebbe323c86a1eff93ca运行中；未干预。

口径：每个原勾选框只计一项，共69项；“已被取代”仅用于有更晚明确决定的布局/语义要求，未变的剩余要求在证据中继续核对。**通过可基于浏览器实测或只读实现/测试定义**，逐项标明；测试覆盖不等于本次执行。涉及必须实际命令/生命周期/用户签收的综合项仍列无法核对。历史实施/验收记录仅证明当时的检查过程，不冒充当前正式投影的重跑结果。票13总关口C与单票可关闭建议独立，均未改原票。

路径约定：下文 `src/…`、`tests/…`、`.scratch/…` 均以 `/mnt/d/cursor/datasourceRF/` 为根；`file:line` 为只读源码/规格定位。`shots/…`、`evidence/…`、`*-log.json` 为当前目录产物。截图采用 light/dark localStorage 键 `pring-cycle-theme`，设置后reload；等待domcontentloaded与目标选择器，未用networkidle。

浏览器矩阵与异常复核数据见文末。

## 01: 单个核心指标贯通

**01.1 原验收项：** 单日汇总生成债券核心最近 120 个交易日价格、可得 MA120、5/120 日变化、单位、两端日期和观测/选中版本引用；不按窗口首点回退、不虚构缺日或沿用价格。

**→ 通过。** 债券 231.49 点，近 5 日 +0.09%、近 120 日 +2.02%；图有 120 个交易日、实际价格与 MA120。`shots/1440-light-drawer-bond.png`；`src/pring_cycle/display_projection.py:136` 按真实日历取点、完整 120 点才算均线，变化取 6/121 点端点并携带观测/声明 ID；`:194` 缺任何窗口日即返回原因，不退回首点。

**01.2 原验收项：** 首段小图与详情大图复用点列；缺回看、无可靠日历、少点及旧投影未提供字段分别说明。

**→ 已被取代。** “首段小图＋详情大图”位置已改：`.scratch/cockpit-layout-20261016/decisions.md:9` 决定 3–4 将三核心移到②三卡，逐日明细进抽屉；`.scratch/frontend-defects-20261019/issues/01-asset-chart-height-ticks.md:3` 又将卡内图改为 240px、月刻度。当前三卡与抽屉共用冻结 display；缺日/旧字段分支见 `src/pring_cycle/cockpit.py:279`、`tests/integration/test_display_projection.py:49`。

**01.3 原验收项：** 按投影身份读取包络与分域数据，当前指针在读取间前进时不混装；失败保留上次完整视图，历史深链固定上下文。

**→ 通过。** 身份栏固定 `projection-554b0640f5f9d167fb6a`；源码 `src/pring_cycle/web.py:619` 从 query 的 projection 读取整套，`:736` 失败返回 no_update 保留完整视图；`tests/web/test_cockpit_http.py:257` 明确在当前指针前进后检查旧包络、分域、运行和报告均不混入新身份。

**01.4 原验收项：** 一个数值或图点可打开基本观测/选中声明/回执链，刷新及返回保留投影、统计期和位置。

**→ 通过。** 债券数值链接携带 projection、选中版本 `59da31b3…b74b0`、return=assets；证据页展示冻结观测、声明与回执，reload 保持身份，返回链接定位②。`shots/evidence-core.png`、`shots/evidence-core-reload.png`、`shots/evidence-return.png`；`src/pring_cycle/cockpit.py:3190` 保留 projection 和返回段落。

**01.5 原验收项：** 在单日汇总和真实 HTTP 边界用独立端点预期及截止后修订反例验证，完成浏览器路径、受影响测试与切片冒烟。

**→ 通过。** 只读核对测试定义：`tests/integration/test_display_projection.py:21` 独立价格/端点预期，`:49` 沿用不得画点，`:64` 截止后修订反例；`tests/web/test_cockpit_http.py:343` 精确冻结版本证据。本次补实际浏览器路径；既有切片执行记录见 `.scratch/ui-rebuild-20261015/implementation.md:23` 起及 `.scratch/ui-rebuild-20261015/acceptance.md:32` 起。通过指覆盖与既有执行记录，不宣称本次重跑。


## 02: 三核心与同类资产

**02.1 原验收项：** 将票 01 的完整路径扩展到三核心，展示距均线、斜率、噪声带、稳定方向、趋势切换候选及持续天数；30 日即时方向单列且不挂持续天数。

**→ 通过。** ②债/股/商分别牛/熊/牛，距 MA120 为 +1.09% / −12.92% / +1.83%，斜率 +0.35% / −0.97% / +0.02%；30 日候选方向与“资产候选状态”分行，当前均无切换候选，没有把候选方向挂上持续天数。噪声带在逐日抽屉（债券 0.04%）。`shots/1440-light-assets.png`；候选持续分支 `tests/web/test_asset_cards.py:160`、`src/pring_cycle/cockpit.py:279`。

**02.2 原验收项：** 债/股/商按方案排列完整走势图与同类资产表，广度、商品篮子及分项贡献复用现有冻结事实；不新增模型判定。

**→ 已被取代。** 旧“完整大图按债股商排列”改为三列卡内图、同类表限高 320px、明细进抽屉：布局决定 4、25（`.scratch/cockpit-layout-20261016/decisions.md:10`、`:53`）。当前债股商顺序、广度、篮子及贡献均保留；新图高 240px 的取代依据同 01.2。`shots/1440-light-assets.png`。

**02.3 原验收项：** 同口径 120 日收益在核心表、图注、价格内部一致性中一致；同类接口、价格内部一致性与债券归因明确不计入确认度。

**→ 通过。** 三核心 120 日收益 +2.02%、−16.00%、−0.52%；差分别 −18.02、−2.54、−15.48 个百分点，与①及②一致。②价格内部一致性、债券归因均明示“不计数”；同源信号今后展示方式改动不改变“不进确认度”语义（宏观批次决定 20）。`evidence/1440-light-home.txt`。

**02.4 原验收项：** 价格收益、利率/比例差分分别标明百分比、百分点或基点及端点，非核心不强造 MA120 或候选。

**→ 通过。** 收益按 %，美债 10Y 近 5 日 −13.00 基点，家数用“家”、分项贡献用百分点/基点，非核心没有强加 MA120/核心候选。SOX 抽屉明确 5 日 10-09→10-16，120 日 04-27→10-16。`shots/1440-light-drawer-sox.png`；`src/pring_cycle/display_projection.py:300` 单位差分。

**02.5 原验收项：** 以独立可手算数据覆盖缺点、沿用、候选差异与单位；完成页面交互、主题/窄屏和既定切片验证。

**→ 通过。** 本次明暗×1440/390截图及抽屉；独立缺日/沿用/单位反例见 `tests/integration/test_display_projection.py:49`、`:170`、`:238`，页面合约见 `tests/web/test_asset_cards.py`。历史执行记录 `.scratch/ui-rebuild-20261015/acceptance.md:27`、`.scratch/frontend-defects-20261019/issues/01-asset-chart-height-ticks.md:19`。未执行新测试。


## 03: 海外与汇率

**03.1 原验收项：** 表列包括指标、最新值与单位、方向、实际统计期、频率、时效、最近获取与采用来源；每项可进入冻结证据。

**→ 已被取代。** “紧凑表各列”改为卡片核心值＋抽屉全字段：布局决定 5、18、21（`.scratch/cockpit-layout-20261016/decisions.md:11`、`:34`、`:37`）。当前 10 张卡，GDP 已归④、中债030归②；SOX 抽屉含统计期/日频/时效/最近获取/采用来源/冻结证据。`shots/1440-light-overseas.png`、`shots/1440-light-drawer-sox.png`。

**03.2 原验收项：** 保留各市场可靠日历及周/月/事件频率；不把低频铺成日线，也不以工作日猜日历或补足变化。

**→ 通过。** SOX 最新 10-16，油价 10-14，汇率分别 10-19/10-16，没有强行对齐中国目标日。`src/pring_cycle/display_projection.py:272`、`:332` 按成员自身频率/日历；低频保留反例 `tests/integration/test_display_projection.py:132`，美债自身交易日 `:170`。未连接任何外部来源。

**03.3 原验收项：** 后来的失败尝试不冒充选中值的来源；缺失、不适用、未知与旧字段缺失明确显示，枚举配中文说明。

**→ 通过。** SOX 显示最新 11,137.29 点、当前有效、最近获取“来源失败”，采用来源仍为 Nasdaq 留存值；两种身份分开。中间价/16:30 汇率及利差“近5日 —”保留缺值。`shots/1440-light-drawer-sox.png`；`src/pring_cycle/evidence.py:1769` 按精确声明查历史回执，`tests/web/test_cockpit_http.py:419` 防后来修订冒充旧来源。

**03.4 原验收项：** 按对应投影/运行展示 SOX 等来源状态，不固化参考样例的旧授权标签、数量或日期。

**→ 通过。** SOX 当前状态为来源失败，未套用旧样例“授权问题”；日期 2026-10-16、近5日 −11.41%、120日 +7.01%，来源来自当前冻结投影。`shots/1440-light-drawer-sox.png`；`tests/web/test_overseas_cards.py:323` 固定旧投影读取其自己的行。

**03.5 原验收项：** 覆盖不同频率、时差、缺失、单位与来源错配，通过 HTTP/页面及切片验证。

**→ 通过。** 不同频率与基点反例 `tests/integration/test_display_projection.py:132`、`:170`；卡片全字段/日期/缺日 `tests/web/test_overseas_cards.py:166`、`:202`、`:235`；既有 HTTP 切片记录 `.scratch/ui-rebuild-20261015/acceptance.md:32`。本次浏览器核对全部卡片及SOX抽屉、明暗窄屏；未重新执行测试。


## 04: 周期结论与宏观确认

**04.1 原验收项：** 结论板包含阶段/原因、上一确认阶段、转折观察、核心沿用、五维摘要、价格一致性、库存、债券归因和数据边界入口，读取既有冻结结果。

**→ 已被取代。** 旧以正式阶段＋确认度领衔的结论板，被宏观判断主结论与价格验证取代：`.scratch/macro-stage-20261017/decisions.md:7` 决定1–2、`:40` 决定10–11、`:56` 决定17。当前是 v0015 旧投影，保留旧板并提示“该投影生成时尚无宏观判断”，符合该批 `.scratch/macro-stage-20261017/spec.md:120` 的明确兼容决定。`shots/1440-light-conclusion.png`。

**04.2 原验收项：** 覆盖典型、两类非典型、核心不足/冲突、待定方向与首次空库；上一确认阶段不顶替当前阶段。

**→ 通过。** 当前债牛股熊商牛为非典型，“暂无正式阶段”，上次确认III单列，未顶替当前。典型/两非典型/核心不足/空库行为用 `tests/web/test_conclusion_board.py:104`、`:118`、`:133`、`:359` 及 `test_report_board.py:89` 的只读测试定义核对；宏观兜底是新概念，不改写价格阶段。

**04.3 原验收项：** Worker 汇总现有关键指标关系；支持/反证/仅观察/未确认可逐项核对，五维只分组，库存只计一项，派生与同源价格不重复计数。

**→ 通过。** 当前 17 项分组 5/3/5/3/1，库存仅1项；非典型全不计数。`shots/1440-light-confirmation.png`；`tests/integration/test_display_projection.py:85` 核对关键指标只计一次，`tests/web/test_confirmation_cards.py:164` 核对四关系与成员。此项仍适用于价格确认度，没有被宏观五维投票废除。

**04.4 原验收项：** 宏观表展示时序、最新值/期、模型实际读取期、水平/动量/斜率、主辅一致或分化、缺什么、支持命题、成熟度与宽限；读取期不伪造日频。

**→ 已被取代。** 原宏观表/表内明细改为维度卡＋成员抽屉（`.scratch/cockpit-layout-20261016/decisions.md:12` 决定6、20、21）；v0016又将④改“宏观判断依据”、价格确认度移到价格验证抽屉（宏观决定11，`.scratch/macro-stage-20261017/decisions.md:41`）。旧投影社融抽屉仍列来源最新期、模型读取期、时序、主辅分化及实际输入；主成员7.10%、政府债辅助13.70%反向。`shots/detail-credit.png`。

**04.5 原验收项：** 无正式阶段时确认度不适用且事实仍可读；未知不作中性/支持，不引入支持率、概率或评分。

**→ 通过。** 旧投影当前确认度“不适用”，事实仍显示；贷款缺值显示 —/方向未提供，未知没有变成支持。社融抽屉写“非典型组合不判定命题与成熟度”。`shots/1440-light-confirmation.png`、`shots/detail-credit.png`。新宏观“k/5吻合”是另一个模型概念，不是把价格确认度变成概率/评分。

**04.6 原验收项：** 通过单日汇总、HTTP/页面行为及切片冒烟；表内展开和主题/窄屏可用。

**→ 已被取代。** “表内展开”被全站右侧抽屉取代，依据布局决定2（`.scratch/cockpit-layout-20261016/decisions.md:8`）；本次实际打开社融抽屉，Tab/Esc路径见 `details-log.json`。汇总与页面测试定义 `tests/integration/test_display_projection.py:85`、`tests/web/test_confirmation_cards.py:164`；旧执行记录 `.scratch/ui-rebuild-20261015/acceptance.md:32`，未本次重跑。


## 05: 库存周期与仓单

**05.1 原验收项：** 象限、统计期、三线读法、主要/辅助成员及一致分化来自同一投影，未分类说明不足原因。

**→ 通过。** ①与⑤均“主动补库存”，统计期2026-08-31，需求/生产/库存上升；三线主值50.60、5.20%、11.00%，辅助成员在抽屉。`shots/1440-light-inventory.png`；未分类理由分支 `tests/web/test_inventory_section.py:256`。

**05.2 原验收项：** 实际库存近似和单个库存/仓单标明不重复计入确认度；不由一个值重算象限。

**→ 通过。** “注册仓单（附注，不计数）”；实际库存近似70,905.59亿元，明确“不计数，不参与库存象限”，公式只作粗略价格调整代理。`evidence/1440-light-drawer-inventory.txt`；`src/pring_cycle/cockpit.py:2347`。

**05.3 原验收项：** 按品种、统计期显示仓单真实变化、缺失、单位及追溯；吨与桶分列，跨品种汇总仅复用可比的已发布结果。

**→ 通过。** 8品种，最新期10-19，分品种表保留窗口/上期/5日变化与证据；吨与原油桶分别列示，汇总不把原油与吨相加。`shots/1440-light-drawer-inventory.png`、对应txt；`src/pring_cycle/cockpit.py:2250`、`:2300`，`tests/web/test_inventory_section.py:321`、`:365`。仓单历史2期缺6成员另在⑦如实列出。

**05.4 原验收项：** 象限摘要与结论板使用相同事实；异期、未知、辅成员相反均有可读状态。

**→ 通过。** ①与⑤同为8月主动补库存；社融/库存详情可读异期、未知和主辅关系，没有用9月其他数据覆盖8月象限。`evidence/1440-light-home.txt`、`evidence/1440-light-drawer-inventory.txt`；`tests/web/test_inventory_section.py:225`、`:256`。

**05.5 原验收项：** 完成冻结数据、HTTP/页面、展开/返回、主题/窄屏及切片验证。

**→ 通过。** 本次明暗×宽窄页及仓单抽屉/Esc返回；冻结数据/未分类/成员只展示一次的定义见 `tests/web/test_inventory_section.py:208`、`:225`、`:256`；已有 HTTP/仓单/冒烟记录 `.scratch/ui-rebuild-20261015/acceptance.md:29`。未重跑真实取数或测试。


## 06: 阶段历史与发布日历

**06.1 原验收项：** 正式阶段和债/股/商四带共享真实交易日轴，缺日不压缩位置，分类计数与窗口一致；日期、版本和状态有等价表格读法。

**→ 已被取代。** “固定四带”被新增宏观判断一行取代：宏观决定5（`.scratch/macro-stage-20261017/decisions.md:21`）、`.scratch/macro-stage-20261017/spec.md:120`。生效前不倒推，当前旧投影仍四带并提示无宏观判断。4待处理+67第三阶段+49非典型=120；等价表见 `shots/detail-history-table.png`，`tests/integration/test_display_projection.py:145` 验证空日保留位置。

**06.2 原验收项：** 同截止更正按被替代关系选择；区别整日、仅核心、仅上一确认阶段更正、上下文未重算和无法更正。

**→ 通过。** 区间08-04～10-19为49日、其中更正42日；抽屉按日列版本/被更正版本/原因。`shots/detail-history.png`；各更正边界见 `src/pring_cycle/cockpit.py:2884`、`tests/web/test_dashboard_contract.py:483`、`tests/integration/test_core_only_correction.py:157`。这些是读码确认，不借本次单一状态声称覆盖所有实时反例。

**06.3 原验收项：** 回溯阶段明确标识；不沿用样例首次历史全部待处理假设，不借当前宏观填历史。

**→ 通过。** 历史窗口不是全部待处理：4/67/49三类；回溯上下文独立，不借现宏观补史。`shots/1440-light-history.png`；`src/pring_cycle/cockpit.py:2478`、`tests/web/test_stage_history_intervals.py:177`、`:216` 固定投影/窗口前回溯。

**06.4 原验收项：** 发布日历保留预计、实际、首次可用、沿用期、下次检查和关联观测；独立刷新的实际事件与投影事实注明身份/时点。

**→ 通过。** 发布日历抽屉明确投影ID、分析截止、使用投影内事件；LPR预计2026-10-20 09:00，实际/首次可用为空、沿用2026-09、下次检查10-20 09:00、关联观测0、等待发布。`shots/1440-light-drawer-calendar.png`。`src/pring_cycle/dashboard.py:930`、`tests/web/test_report_board.py:95`、`tests/web/test_dashboard_contract.py:517` 区分冻结与运行读模型。

**06.5 原验收项：** 旧阶段史与日历书签可达正确上下文；完成更正反例、HTTP/浏览器与切片验证。

**→ 通过。** 旧 `/stage-history` 映射⑥，`/release-calendar` 保留日历页；`src/pring_cycle/dashboard.py:163`、`:175` 与 `assets/dashboard.js:76`。更正/固定历史用例 `tests/web/test_stage_history_intervals.py:90`、`:177`；已有HTTP/浏览器记录 `.scratch/ui-rebuild-20261015/acceptance.md:38`。浏览器旧入口实测另见 `legacy-log.json`。


## 07: 解读与报告工作区

**07.1 原验收项：** 复用已有非典型依据与受约束报告契约，完整显示全部差一项对照；不排名、不推测正式阶段。

**→ 已被取代。** 新报告以宏观判断为主线，价格非典型改从偏离宏观判断解释：宏观决定12（`.scratch/macro-stage-20261017/decisions.md:42`）及该批spec“报告”部分。旧v0015报告仍列I/III/V三个只差一项对照、不排名、不猜价格阶段；`evidence/1440-light-reading.txt`。旧报告不因新规格重写。

**07.2 原验收项：** AI 成功与确定性模板来源明确；无报告、生成中、旧投影缺依据、正文过期分别显示。

**→ 通过。** 当前来源明确“AI解读 · codex_cli”；报告详情留存身份与正文，未伪装模板。无报告、生成中、旧字段和过期分支 `src/pring_cycle/cockpit.py:1407` 报告渲染、`src/pring_cycle/dashboard.py:2059`、`:2212`；模板反例 `tests/web/test_cockpit_http.py:257`，既有真实双适配器超时模板证据 `.scratch/ui-rebuild-20261015/acceptance.md:72` 起。

**07.3 原验收项：** 首段和历史段只留摘要/全文入口，末段按实际章节展开；不编造参考样例的固定章节数。

**→ 已被取代。** ⑦全文按章节常显已被“摘要＋报告详情抽屉＋历史工作区”取代，布局决定8、21（`.scratch/cockpit-layout-20261016/decisions.md:14`、`:37`）。①/⑥仅全文入口，当前⑦摘要＋抽屉，详情按实际章节不凑固定段数。`shots/1440-light-reading.png`、`shots/1440-light-drawer-report.png`。

**07.4 原验收项：** 生成命令受理时绑定投影并幂等，当前指针变化不改输入；历史选择保持原报告身份和正文。

**→ 通过。** 静态核对 `src/pring_cycle/web.py:941` 的受理绑定、`src/pring_cycle/runs.py:268` 的命令幂等；指针前进反例 `tests/web/test_cockpit_http.py:371`。历史阅读按report_snapshot_id页签选择（`dashboard.py:2101`），正文及模型/输入哈希独立留存。`shots/report-history.png`、`shots/report-history-selected.png`；未提交生成命令。

**07.5 原验收项：** 通过离线适配器及 HTTP/浏览器验证同投影最新版本、AI/模板、历史切换及切片冒烟。

**→ 通过。** 本次只读历史/阅读导航；离线AI/模板、固定投影及选中正文合约 `tests/web/test_dashboard_contract.py:65`、`tests/web/test_cockpit_http.py:257`；既有执行/失败模板与浏览器记录 `.scratch/ui-rebuild-20261015/acceptance.md:27`、`:72` 起。当前生成路径未操作，不把历史记录当成本次新报告生成。


## 08: 完整证据追溯

**08.1 原验收项：** 检索包含指标、维度、统计期与投影/截止上下文；选中、其他来源、冲突、修订和同定义跨目录归并可辨。

**→ 通过。** 证据工作区固定投影和截止，检索表含指标/维度/统计期；精确选中版本、其他声明、修订及同定义归并由 `src/pring_cycle/evidence.py:1769`、`:1829` 和 `cockpit.py:3190` 提供。`shots/evidence-core.png`；未提交检索表单，检索语义为读码确认。

**08.2 原验收项：** 派生树按实际输入版本递归按需展开；重复节点可引用，异常环及缺失父节点明确显示，不重选最新值。

**→ 通过。** `src/pring_cycle/web.py:479` 校验根必须属于冻结快照，逐边验证child属于parent实际输入，重复链报lineage_cycle、缺版本报错，不选最新；`cockpit.py:3280` 派生输入导航带trail。`tests/web/test_cockpit_http.py:524` 检查真实HTTP递归及伪造边。此项主要由源码确认。

**08.3 原验收项：** 查看原文真正打开或下载 raw/normalized 留存内容，安全呈现文本/HTML，不执行来源脚本、不接收任意路径、不触发补抓。

**→ 通过。** 原件链接使用回执ID＋raw/normalized类型；只读打开raw的状态/响应头见 `details-log.json`。`src/pring_cycle/web.py:219` 读取留存，inline text/plain，CSP default-src none; sandbox，nosniff；不执行来源HTML或补抓。截图 `shots/raw-artifact.png`。

**08.4 原验收项：** HTTP/页面区分观测不存在、原件未留存、过期、文件缺失、哈希失败，遵守原有留存与敏感信息保护。

**→ 通过。** `src/pring_cycle/web.py:219` 分别映射缺文件404、过期410、哈希409、非法类型400；观测/版本不存在由冻结证据入口明确报错（`:479`，`cockpit.py:3266`）。`tests/web/test_cockpit_http.py:488` 有三类原件反例，`:524` 处理缺父/非法边。本次不制造损坏原件，按源码通过。

**08.5 原验收项：** 深链刷新、前进后退与返回保留原投影及筛选；通过真实 HTTP、浏览器和切片验证。

**→ 通过。** 本次数值→冻结证据→reload→返回②→浏览器后退/前进，身份保持，截图 `evidence-core-reload.png`、`evidence-return.png`、`evidence-back.png`、`evidence-forward.png`；`cockpit.py:3190` 将筛选透传链接。既有HTTP及切片记录 `.scratch/ui-rebuild-20261015/acceptance.md:33`。未提交检索表单。


## 09: 运行健康摘要

**09.1 原验收项：** Worker 在成功、降级、失败、取消的终态留存适用摘要，包含运行/命令/投影身份、时间、总/分段耗时、请求、结果、预算及已有缺口信息。

**→ 通过。** 终态集合与持久化见 `src/pring_cycle/run_health.py:17`、`:69`、`:103`，按run/attempt插入不可变摘要；当前完成run-153…有1633.90秒、176请求、15失败、预算与缺口，身份关联其投影。`shots/1440-light-data-chain.png`；`tests/web/test_cockpit_http.py:397` 验证取消摘要不重复。

**09.2 原验收项：** 运行中展示真实进度和已知数据，不伪造终态；中断和恢复基于真实记录收尾，未发布新投影时不把旧分析标为本次成功。

**→ 通过。** 本次看到既有run-3ebbe323c86a1eff93ca运行中、77请求（1440-light-runs截取时），耗时/最终计划未形成均不冒充终态；“本次投影：尚未发布新投影”明确，顶部仍旧分析身份。`evidence/1440-light-runs.txt`；`run_health.py:128` 只读取该run的projection/checkpoint。中断恢复其余分支读码核对。

**09.3 原验收项：** 相同类型、模型/目录及摘要口径可比较才显示上次增减，显示对比身份；旧摘要缺失或不可比说明原因。

**→ 通过。** 当前新运行提示“无可比的留存摘要：须同类型、模型、目录和计数口径”；`run_health.py:385` 同schema/type/model/catalog/request_basis且前次已结束才比较，并返回比较run_id。`shots/1440-light-runs.png`。

**09.4 原验收项：** 趋势取留存期内可用运行，可按类型/状态筛选；报告任务不混入完整取数耗时，新增存储遵守窗口且不改写旧运行。

**→ 通过。** 运行页有类型/状态筛选与留存期趋势，当前留存完整摘要显示前次完整运行；报告任务分开比较。`src/pring_cycle/web.py:651`、`run_health.py:57`、`retention.py:41`；终态INSERT OR IGNORE不改旧摘要。筛选未提交，联动按代码核对。

**09.5 原验收项：** 在完整运行公开入口验证终态/恢复/留存与少量生命周期反例，HTTP/页面验证摘要和趋势，完成相应切片验证。

**→ 无法在浏览器核对。** 终态/恢复/留存的完整真实运行验收不能由当前“一条完成＋一条执行中”穷尽。已有定义 `tests/web/test_cockpit_http.py:397` 与历史实施记录，但本次未触发取消/失败/恢复、未到留存边界。仍需同安装版本的完整运行生命周期与清理前后记录、对应测试退出码；不凭旧票勾选宣布现环境这些场景全部复验。


## 10: 取数流向与缺期诊断

**10.1 原验收项：** Worker 最终计划逐指标/维度/统计期记录未发布、已持有/采用、未交付、拒收、请求失败、门禁跳过、预算/流程终止或原因未记录。

**→ 通过。** `src/pring_cycle/run_health.py:280` 从final gaps及实际scope/requests/attempts构造逐指标/期诊断，区分采用/持有、发布门禁、拒收、请求失败、预算/流程停止和未记录。当前链路显示最终计划3065条、已持有3055、等待3、其他缺失7；`evidence/1440-light-data-chain.txt`。

**10.2 原验收项：** 数据链路按运行筛选/关键数、取数流向、降级链、未完成期、证据追溯、候选校验与时效组织；所选运行与分析投影身份分开。

**→ 通过。** 链路依次含运行选择、流向/请求、降级、未完成期、证据与检索/时效，标明“运行run-153…本次投影projection-554…；下方分析证据沿用所选分析投影”。`shots/1440-light-data-chain.png`；`src/pring_cycle/cockpit_operations.py:563`。

**10.3 原验收项：** 主桑基图按请求数唯一归属且守恒；重试算不同请求，缓存和未发请求缺期不算外部请求；声明/候选/缺期明确单位。

**→ 通过。** 主图176次真实请求，来源→环节→结果；`run_health.py:360` 每条请求向两段各贡献1、count=len(requests)，请求单位physical_request；缓存未发不造外部请求。`cockpit_operations.py:105` 仅合并小来源不改总数，`tests/web/test_report_board.py:120` 覆盖缺耗时与共享请求去重。本次图计数与运行摘要176一致。

**10.4 原验收项：** 降级链展示实际层级、跳过/停止原因及渠道结果，Exa 为 Tavily 月限额备用；如用缺口流图，按唯一缺口及真实路径计数。

**→ 通过。** 实际降级表有local→tushare→资讯→official→tavily→exa→ai，含未配置/未尝试/no_searchable_source等真实原因；源码按实际attempt呈现而非补画成功路径。`evidence/1440-light-data-chain.txt`；Exa条件备用规则见 `src/pring_cycle/retrieval.py:139` 的Exa条件分支及 `run_health.py:280`。未实际触发新检索。

**10.5 原验收项：** 来源/环节/结果/指标筛选真实联动图表和明细，计数由读模型提供，清空与无匹配可用。

**→ 通过。** 源码 `run_health.py:360` 同时按channel/phase/result/metric筛选请求，计数、links和明细同源；`cockpit_operations.py:205` 提供清空/表单，`:563` 消费同一结果。遵守禁提交，本次未点“应用筛选”；此项按源码确认，不宣称完成当前页面筛选操作。

**10.6 原验收项：** 首页和链路分别显示仅模型用到/目录全部真正缺失及等待发布等状态；零失败不表示完整，不按指标名手写归因。

**→ 通过。** ⑦模型1015/1013/0/2、目录3065/3055/3/7（应有/持有/等待/缺失），链路同口径；另有5项缺口+3等待发布。零失败不等于完整，实际176请求15失败也与期缺失分开。`shots/1440-light-reading.png`、`shots/1440-light-data-chain.png`；`display_projection.py:38`、`tests/integration/test_display_projection.py:206`。

**10.7 原验收项：** 用一请求多声明、零行、未请求、拒收、取消、条件降级等反例验证 Worker/HTTP/浏览器，并完成切片验证。

**→ 通过。** 静态反例：`tests/web/test_report_board.py:120` 一请求共享声明计一次，`tests/web/test_cockpit_http.py:397` 取消，`tests/integration/test_display_projection.py:206` 等待/真正缺失分离；历史Worker/HTTP切片记录 `.scratch/ui-rebuild-20261015/implementation.md:26` 起、`.scratch/ui-rebuild-20261015/acceptance.md:32`。本次只读图表/明细核对，不重放外部请求。


## 11: 运行操作与持续观察

**11.1 原验收项：** 保留手动完整运行、确认恢复、取消后续步骤和现有定向操作；报告生成入口仍可达，遵守已有状态限制。

**→ 通过。** 运行页可见完整运行、恢复/取消操作与定向运行历史，报告工作区可达；未点击操作按钮。状态约束由 `src/pring_cycle/dashboard.py:2395`、`runs.py:224`、`web.py:941`；`tests/web/test_dashboard_contract.py:580` 覆盖操作与轮询。

**11.2 原验收项：** 受理结果、幂等键、正在执行和待确认明确可见；重复点击/提交只产生一个有效命令。

**→ 通过。** 幂等按(command_type,client_request_id)查已有run，报告输入冲突拒绝（`runs.py:268`）；前端同一命令保存/复用请求键并禁用重复按钮（`assets/dashboard.js:177`）。当前正在执行状态可读；受理反馈的可见性见 `tests/web/test_cockpit_http.py:124`。按源码通过，没有双击或提交实测。

**11.3 原验收项：** 运行约 30 秒、空闲约 300 秒轮询，更新不重置筛选、位置或焦点；无第二调度器和浏览器自动 Worker。

**→ 通过。** `src/pring_cycle/web.py:611` 活动30,000ms/空闲300,000ms；`:649` 指纹不变no_update，`assets/dashboard.js:231` 起保存/恢复焦点、展开和滚动。无前端Worker调度；当前运行页也说明30/300秒。轮询频率按代码确认，未等待5分钟专门测空闲周期。

**11.4 原验收项：** 命令失败、取消、恢复与无新投影均有正确下一步和关联身份。

**→ 通过。** 当前运行写“尚未发布新投影/下一步worker_continue”，旧分析未归给当前成功；各运行记录保留run ID/状态/恢复和取消分支。`shots/1440-light-runs.png`；`src/pring_cycle/dashboard.py:2395`、`runs.py:987`，`tests/web/test_dashboard_contract.py:542`。下一步仍有英文内部码是展示细节，未据此判错误状态迁移。

**11.5 原验收项：** 通过真实 HTTP 幂等/状态反例和浏览器操作验证，完成相应完整运行及切片冒烟。

**→ 无法在浏览器核对。** 本项明确要求真实HTTP幂等/状态反例、浏览器操作和完整运行。硬约束禁止提交与运行操作，因此本次只确认实现/旧记录；需现安装版本的重复提交、失败/取消/恢复链路与完整运行/切片退出码，不能通过读界面证明真实命令只执行一次。


## 12: 访问配置贯通

**12.1 原验收项：** 绑定地址、端口、允许 Host、允许 Origin 是显式统一配置，启动、健康、HTTP 及命令校验都读取它。

**→ 通过。** `src/pring_cycle/web_config.py:33` WebConfig统一host/port/allowed_hosts/allowed_origins，`:40`读配置；`web.py:64`应用、`:754`启动、`:890`命令Origin检查；health返回同配置。`tests/web/test_cockpit_http.py:191`覆盖共享边界。

**12.2 原验收项：** 保持本机可用默认值，允许指定新宿主值；不以通配全部 Host/Origin 绕过校验。

**→ 通过。** `web_config.py:49` 默认127.0.0.1，默认Host/Origin按port构造并支持显式覆盖；`:79` 拒绝含*等非法authority，`:94`限制Origin形态。只读浏览8069实际可用；未访问默认8050或其他端口。

**12.3 原验收项：** 真实 HTTP 覆盖允许与拒绝的 Host/Origin、无效配置和命令行为；配置不依赖页面硬编码。

**→ 通过。** 只读测试定义 `tests/web/test_cockpit_http.py:191` 实际HTTP允许/拒绝Host和Origin、命令幂等，`:217`拒绝通配；`web_config.py:40`校验无效配置。页面不硬编码访问授权。按代码/测试定义通过，未对正式服务发送伪造Host或命令请求。

**12.4 原验收项：** 不指定尚待实测的 dot 隧道/公网/多用户部署，不引入新调度器。

**→ 通过。** 配置只描述本机listener/访问边界，没有把dot隧道、公网、多用户部署宣布可用，也未增加调度器。`web_config.py:33`、`web.py:754`；本次仅同源8069。

**12.5 原验收项：** 完成配置变更的类型检查、相关 HTTP/进程验证及切片冒烟。

**→ 无法在浏览器核对。** 本次未启动配置测试进程、未运行类型检查或切片。旧验收记录有mypy/HTTP通过，但不能证明当前安装已按本票完整复跑；需对应版本的类型检查、HTTP/启动进程与冒烟日志及退出码。代码实现项12.1–12.4已独立判定。


## 13: 入口切换与整站验收

**13.1 原验收项：** 七段首页、数据链路和运行状态完整集成，旧八页导航和重复页面退役；旧有效书签/查询条件正确定位，刷新及前进后退可用。

**→ 通过。** 当前七段首页＋三个一级导航已集成；旧入口/core-assets、/macro、/inventory、/stage-history由同一report_board接管，/release-calendar仍可达冻结日历。`src/pring_cycle/navigation.py:3`、`dashboard.py:163`；浏览器旧路径及查询固定投影见 `legacy-log.json`，证据reload/前进后退截图见08.5。

**13.2 原验收项：** 各页已具备主题/窄屏/键盘功能，整站复核一致性、文字标签、图表等价读法、减少动画、加载/失败/空库/旧字段状态及有意义的初始内容。

**→ 通过。** 明暗×1440/390页面文档scrollWidth均等于视口（细项见矩阵），宽表内滚；drawer宽520/390。源码键盘焦点陷阱/Esc/返回 `assets/drawer.js:93`，reduced-motion `dashboard.css:538`，加载初始内容 `tests/web/test_projection_api.py:118`、旧字段/空库 `test_report_board.py:89`。当前不是空库，空库与读失败分支按源码确认。

**13.3 原验收项：** 对照指定 Claude 方案核对结论板、紧凑表、图表和分区；补齐此前未核对的运行页、配色/间距等视觉证据，不复制样例错误或固定数字。

**→ 已被取代。** 指定Claude旧布局已被结论板10-16、布局10-16/17、图表10-19、宏观10-17/20连续明确调整，不能继续按原首段九列表/四带/全文布局判失败。取代依据：`.scratch/cockpit-layout-20261016/decisions.md:8` 决定2–8及`:53` 决定25–28；`.scratch/macro-stage-20261017/decisions.md:40` 决定10–12与该批 `spec.md` 的Implementation Decisions（第120行）。当前运行页及主题截图均补留，历史参考比对见 `.scratch/ui-rebuild-20261015/visual-followup.md:5`，未访问外网参考站。

**13.4 原验收项：** 贯通正常发布→证据→返回、非典型AI失败模板、运行失败保留上次分析三个场景；版本/投影/测试范围和退出码留档。

**→ 无法在浏览器核对。** 本次完成正常投影→证据→返回，并在历史阅读中查看同投影v1“确定性模板/AI解释不可用”；未制造或观察当前安装的运行失败保留旧分析，因此仍不能覆盖全部三个场景。旧隔离运行 `.scratch/ui-rebuild-20261015/acceptance.md:72` 起有双适配器超时模板记录，但仍需当前安装的失败场景完整投影/报告/运行身份及测试范围、退出码；禁止操作下未复演。

**13.5 原验收项：** 到终点真实完整运行前执行一次全套并遵守时钟、重型锁、磁盘与串行规则；更新隔离安装防止误测旧包。

**→ 通过。** 这是历史过程项：`.scratch/ui-rebuild-20261015/acceptance.md:27` 起记录全套2026-10-15 19:39:50、时钟/锁/磁盘保护、2552通过7失败退出1；后67项针对修复回归通过退出0，未伪称第二次全套全绿。`.scratch/ui-rebuild-20261015/implementation.md:60` 起记重新no-editable安装及真实副本运行前保护。通过表示当时规定的“终点前执行一次”有记录，不代表本次运行过全套或已验证当前安装与仓库逐文件一致。

**13.6 原验收项：** 新代码和新真实投影在本机运行，数据质量体检与逐段用户验收记录完整；关口 C 未经用户验收不标通过，关口 A/B 与迁移独立记录。

**→ 无法在浏览器核对。** 当前正式新代码页面与真实10-19投影可见，但旧批用户逐段表仍待确认（`.scratch/ui-rebuild-20261015/acceptance.md:98`起）；本次不读正式数据库、不重做数据质量体检，也不代替用户签关口C。需当前投影质量体检、逐段用户确认与独立A/B/迁移记录。建议保持需用户看。


## 浏览器矩阵与产物核对

| 宽度 / 主题 | 首页 / 数据链路 / 运行页 scrollWidth | 抽屉宽度 | 证据 |
|---|---|---:|---|
| 1440 / light | 1440 / 1440 / 1440 | 520px | [首页](shots/1440-light-home.png) · [链路](shots/1440-light-data-chain.png) · [运行](shots/1440-light-runs.png) · [SOX抽屉](shots/1440-light-drawer-sox.png) |
| 1440 / dark | 1440 / 1440 / 1440 | 520px | [首页](shots/1440-dark-home.png) · [链路](shots/1440-dark-data-chain.png) · [运行](shots/1440-dark-runs.png) · [SOX抽屉](shots/1440-dark-drawer-sox.png) |
| 390 / light | 390 / 390 / 390 | 390px | [首页](shots/390-light-home.png) · [链路](shots/390-light-data-chain.png) · [运行](shots/390-light-runs.png) · [SOX抽屉](shots/390-light-drawer-sox.png) |
| 390 / dark | 390 / 390 / 390 | 390px | [首页](shots/390-dark-home.png) · [链路](shots/390-dark-data-chain.png) · [运行](shots/390-dark-runs.png) · [SOX抽屉](shots/390-dark-drawer-sox.png) |

390报告历史/阅读页在light/dark下均390px，无整页溢出；[明色阅读](shots/390-light-report-reading.png)、[暗色阅读](shots/390-dark-report-reading.png)。三核心图实测均240px高，价格与MA120各120点；当前旧投影阶段带120日，分类合计120。20次抽屉打开/Esc关闭均成功；社融、阶段区间、等价表格内Tab焦点均落在抽屉内。以上原始数值见 [matrix-log.json](matrix-log.json)、[details-log.json](details-log.json)、[report-mobile-log.json](report-mobile-log.json)。

原件实测：留存raw返回 **HTTP 200，13,200字节**，`Content-Type: text/plain; charset=utf-8`、`Content-Security-Policy: default-src 'none'; sandbox`、`X-Content-Type-Options: nosniff`，未访问回执中的外部来源网址。证据版本reload及返回/后退/前进保持同投影，最后定位 `/?projection=projection-554b0640f5f9d167fb6a#assets`。报告历史有37个页签，实际切换10-19 v2→v1，v1身份为 `report-1e7c260c8f9a4ae6bf1a`，确认为确定性模板。

五个旧入口均在8069实测可达并携带固定projection查询：`/core-assets`、`/macro`、`/inventory`、`/stage-history`、`/release-calendar`；[原始记录](legacy-log.json)。首页与旧首页别名仍使用七段页面；日历旧书签保留日历正文。

成功验收脚本为 [audit_matrix3.py](audit_matrix3.py)、[audit_details2.py](audit_details2.py)、[audit_report_mobile.py](audit_report_mobile.py)，均由系统 `/usr/bin/python3` 的 `playwright.sync_api` 无头Chromium运行，退出码0。三组成功脚本记录的请求仅发往127.0.0.1:8069；非GET/HEAD仅有Dash只读渲染回调 `/_dash-update-component`，**没有命令API请求、没有表单提交、没有外部网络请求**；记录的pageerror均为空。

检查脚本曾因报告默认“生成”页正文较短而误超时、窄屏逐段滚动截图等待超时，以及一次脚本内JS切片写法错误而中断；均未当成产品缺陷。修正后补齐矩阵、报告导航、抽屉与完整页面截图；旧脚本/控制台记录保留供复查。未完成的真实操作/生命周期与用户关口，已逐项记为“无法在浏览器核对”，没有以未见异常替代通过。

收尾建议：01–08、10可按本报告证据关闭旧票；09、11、12需补操作/运行或测试执行证据，13需补失败场景和用户验收关口。本轮未确认需要判为“不通过”的原验收项；这不覆盖未获准执行的命令路径及尚未发布的v0016正式宏观投影。
