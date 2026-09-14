# 票19 完整合法隔离生命周期材料

2026-09-14起。基线HEAD `c566702`（票12 `59b7ce5`及既有成果三批提交之后，见[分批提交记录](wip-batches-commit-20260914.md)）。沿用已确认公开边界：`model-source-certify`准入 → 机器校准 → 对当前active的精确120交易日回放 → 显式激活；只替换外部transport与时钟，合成PUBLIC时间以`synthetic:`发布事件标识，不登记为真实来源认证，不接触正式运行库。

## 探针 probe-19（只读能力摸底，不是验收测试）

[脚本](probe-19-lifecycle-20260914.py)、[日志](probe-19-lifecycle-20260914.log)、[回放缺口](probe-19-lifecycle-20260914-gaps.json)。原生运行库`/home/tywin/.cache/pring-cycle/verification/probe19-20260914`，工作区源码经PYTHONPATH加载。

1. 隔离对照基线沿用既有测试先例：内置`model-v0001`以`CALIBRATION_BASELINE`记录验收后激活（非强化规则）。候选本身不走任何捷径。
2. `prepared_request`合成完整61项请求经公开CLI准入成功。
3. [core-transport-196](core-transport-196/receipts.json)真实原始字节经`TushareCoreAdapter.acquire_core_bars`采集，三核心各2345日；候选目录声明挂接采集收据，v0001对照目录为fixture声明；PUBLIC均为交易日08:00 UTC的合成时间。
4. **机器校准通过**：asset_direction_changes 21、formal_stage_changes 11、fast_reversals_20d 0、median_confirmation_delay_days 23；评估1995日、输入2338日、起点2017-01-03；26.0秒。
5. 回放2026-03-09—08-28：120个共同交易日，`quality_passed=false`，48项缺口，48.7秒（缺口时提前返回，不代表完整回放耗时）：
   - `candidate_context_evidence_missing` 45项：CSI300/500/1000、CNY030、930916、NHCI、估值、融资、日广度2项、窗口广度2项、金额占比、商品篮子/贡献、仓单8品种、DR007、Shibor、OMO利率/金额、RRR、LPR、PMI×3、CPI/核心CPI/PPI、工业增加值/财务、产成品库存、存货周转、产能利用率、M1M2、社融总量/分项、贷款结构、工具流动性。
   - `candidate_context_sources_uncertified:CN_GDP`：GDP为P2但是信用脉冲必需输入，完整材料须按`admitted_gdp_manifest`先例将其定义标为certified并提供合法输入。
   - `comparison_context_evidence_missing:CN_LPR_1Y_5Y`：v0001对照侧也需LPR窗口证据。
   - `candidate_context_formula_output_missing`：7个公式随输入缺失。

## 实施方案

公开验收测试新建于`tests/models/`：完整合法候选经准入、校准、回放、激活成功，旧active被替代、正式投影/发布历史不写；回放缺口必须为空。TDD以探针同形态的实际缺口为RED，按家族逐个接入，每次以缺口清单缩小为观察点；不预先堆全部家族，不镜像实现公式。

家族接入顺序（复用已提交的各家族公开采集/审查辅助，扩展到回放窗口及必要预热）：

1. LPR（候选与对照两侧）、银行间DR007/Shibor、OMO利率/金额、RRR
2. 官方宏观：PMI×3、CPI/核心CPI/PPI、工业、库存、M1M2、社融、贷款、工具流动性；GDP certified及信用脉冲；Q1产能映射
3. 市场：六指数、估值、融资、日广度、窗口广度（120日预热）、金额占比、仓单8品种
4. 商品篮子/贡献（需11期货输入与固定基点）

材料复用：同一源码指纹下将构建完成的隔离运行库及内容寻址目录保存为不可变快照（附清单：源码/依赖/输入/模型身份/各阶段收据），不同状态测试各自复制使用；指纹不符即重建。票17 Worker验证消费同一快照。每次运行按本目录既有`verification-*`形式留终态；重型任务一次一个。

## 公开验收测试RED与家族接入进展

新增`tests/models/test_isolated_lifecycle.py`：初始化隔离运行库并按既有先例激活v0001对照；公开CLI准入完整候选，经`model-accept`、`model-replay`（2026-03-09—08-28）和`model-activate --confirm`，要求回放无缺口、候选成为active且未发布任何投影。

- `red-1`（94.44秒）：`model-accept`已accepted；回放48项缺口与探针一致。这是完整材料能力缺失的RED。
- LPR：复用`evidence-lpr-import-20260908`9期真实公告，经`ingest_lpr_document`分别导入候选目录及v0001对照目录，发布时间由解析器给出。缺口48→46（96.94秒）。
- 官方档案首轮：`import_official_archive`逐份导入a18已校验原件。`acquisition_availability_time_invalid`经独立调试定位为WSL墙钟回拨约7秒（收据validated 04:48:01后读到04:47:54），不是产品缺陷；改为测试注入严格递增的外部时钟，与conftest `acquisition_clock`先例一致，生产守卫不变。
- 随后`registered_capacity_q1_mapping_unresolved`：C批Q1守卫要求准入绑定已审映射；完整候选改用既有`prepared_capacity_mapping_request(side=...)`生成请求。
- `official-3`（125.23秒）：缺口46→28。官方宏观各家族覆盖满足；剩余GDP认证、RRR、DR007/Shibor、市场P1、仓单8品种、商品篮子/贡献及7项公式输出。
- `gdp-1`（110.75秒）：准入时按`admitted_gdp_manifest`先例把GDP定义标为certified并重绑审查；导入信用脉冲清单9期GDP真实发布（2024-Q2—2026-Q2）。缺口28→27。
- `rates-1`（117.33秒）：RRR 2025-05真实通知（730天鲜度内）；DR007/Shibor按真实交易日历合成TuShare行（2026-02-20起，覆盖政策利差10天预热），PUBLIC时间以交易日08:00 UTC合成标注。缺口27→24。
- `market-1`（130.68秒）：六指数、沪深北融资、三指数估值合成日行（2026-03-02起）。缺口24→16：剩余商品篮子/贡献、日广度/窗口广度/金额占比、仓单8品种及7项公式输出。
- `warrants-1`：市场日行采集在墙钟回拨时触发`acquisition_time_invalid`（同代码上一轮已通过），属环境时钟问题。改为整条测试使用conftest既有`runtime_clock`（单调时钟驱动并修补各模块外部时钟），官方导入共用该时钟，删除自定义时钟。
- `warrants-2`（147.00秒）：仓单8品种合成fut_wsr行（按31日分块请求过滤）。缺口16→8：剩余日广度2项、窗口广度2项、金额占比、商品篮子/贡献及7项公式输出。
- 广度：准入时5项广度按注册合同改`source_codes`（breadth-v0002 / breadth-window-v0002 / breadth-amount-v0002），商品2项改为`ex-hog-calendar-settlement-v0002`。3只普通A股审查股票池覆盖120日隐藏预热+输出窗口，逐日发布证据；公司行为覆盖输入无调整。`breadth-1`测试编辑错误（此前`ruff --fix`移除了当时未用的timedelta导入）；`breadth-2`既有`breadth_transport`不按区间过滤`trade_cal`触发区间守卫，改用本地transport；`breadth-3`金额证据发布时间早于所属交易日触发`breadth_amount_publication_precedes_period`，改为逐交易日成交/大宗原件及逐日来源引用。
- `breadth-4`（203.95秒）：缺口8→3，仅剩商品篮子/贡献及随之报告的公式输出缺失。
- `commodity-1`：商品篮子输入经公开期货采集与审查包绑定后，逐交易日`persist_commodity_basket`。前置导入约3.5分钟完成；随后32分钟内仅持久化4个交易日（03-09—03-12），进程CPU约89%持续推进、未卡死，平均每日约6—7分钟且每日从基日重算整链。按计划主动停止（非断言失败、不计通过）；这是实测性能热点，下一步单独剖析一次持久化的耗时分布再做必要局部修复。

## 商品篮子持久化容量修复（用户选择产品级重构）

[剖析脚本](profile-19-commodity-persist-20260914.py)在隔离运行库复用本测试的准入与商品输入构造（仅构造输入时临时屏蔽逐日持久化），以cProfile测真实`persist_commodity_basket`。首轮脚本未套用单调时钟而撞上WSL墙钟回拨（准备错误），改为复用conftest `_clock_datetime`后取得数据。

| 版本 | 03-09 | 03-10 | 03-13 | 主要成本 |
|---|---:|---:|---:|---|
| 修复前 | 295.1秒 | — | — | `select_futures_inputs` 78次；`_load_evidence` 1316次反复解析/序列化约8000条发布的审查包（json 114秒、dumps 940万次）；写入前`require_commodity_results`再完整重算 |
| 审查包结构按原件SHA-256缓存 | 198.7秒 | 315.1秒 | — | 每次选择把76份收据共享的2.8MB规范化批次文档逐份解析76遍 |
| 单次选择内按规范化哈希复用批次文档 | 56.6秒 | 92.0秒 | 186.5秒 | 随链长线性增长：每步约23次选择，每次重建事实并在全量列表中比对 |
| `FuturesInputReader`一次计算共用 | 8.0秒 | 8.2秒 | 8.8秒 | 每个读取器首次按原件重建校验约7秒，之后与链长基本无关 |

改动（`futures_inputs.py`、`commodity_basket.py`）：
- 审查包：解析、主体哈希、证明集合及发布/时段结构校验按原件内容哈希缓存；每次仍重新读取并校验审查文件哈希、比对主体哈希、审查时间不晚于接收，按需复核证明原件。
- `FuturesInputReader`：收据历史读一次；批次文档按规范化哈希缓存（读取失败不缓存，照走损坏批次路径）；按品种/交易所/日期建立事实索引并按文档原位置保序；原件重建结果（含异常）按身份元组缓存，缓存项持有对象引用防止id复用误命中，损坏批次的临时文档不缓存。选择的可见性、版本排序、冲突、缺件与合约失败逻辑原样保留。`select_futures_inputs`签名不变，每次调用新建读取器；商品篮子一次计算（整条固定基点链）共用一个读取器。
- 回归：期货输入、商品篮子及注册商品三文件在缓存阶段99通过/334.06秒，读取器重构后99通过/108.03秒；94源文件mypy、Ruff通过。

## commodity-2 终态与回放阶段问题

`commodity-2`实际**1失败/4583.73秒**：全部家族覆盖检查首次通过，逐截止日上下文评估完整跑完，只剩`credit_impulse`、`real_inventory_approximation`两项公式输出缺失；总耗时远超回放900秒性能门。复用该运行库只读诊断（[诊断记录](verification-lifecycle19-commodity-2.txt)）：

- 信用脉冲：前段截止日`missing_certified_inputs`（需从累计GDP推出8个季度，03-09时要2024-Q1—2025-Q4，而导入从2024-Q2起），末段`incomparable_gdp_vintages`（清单186已标注真实跨发布GDP不相容）。按既有正例先例改用`synthetic_coherent_gdp_release`生成2024-Q1—2026-Q2合成一致发布。
- 实际库存近似：`inventory-ppi-v0001`各取最新一期，PPI月初、库存月末发布，月内约2/3日期`period_mismatch`，与回放“必需公式每个截止日可用”冲突。用户决定**按共同最新月对齐**：新增`inventory-ppi-common-month-v0002`，以库存最新期次为准，取截止时可见的同月PPI；该PPI经期次截断后的同一`_metric_rows`判定（认证、注册原件完整性、鲜度），仅`current`采用。旧版本语义不变。`inventory-red-1`新版本2失败（`context_model_formula_version_unsupported`，能力RED）、旧版本对照通过；`inventory-green-1` 6通过/1.43秒。完整候选准入改用新版本。

## 回放容量剖析

[剖析](profile-19-context-replay-20260914.txt)对08-17—08-28共10个截止日运行`evaluate_context_replay`：**796秒**。主要成本：商品消费复核370秒（每截止日新建读取器并从基日重算整链，45330次期货选择）；官方原件复核195秒（7107次重复HTML解析）；银行间85秒、仓单70秒、广度35秒（同样逐截止日重解析不可变原件）。

已做：官方原件重建按“收据身份+本次读取字节SHA-256”缓存（字节变化不命中，损坏仍被发现）。官方/库存/投影/GDP/派生鲜度相关5文件91通过/22.59秒；94源文件mypy与Ruff通过。

未解决：商品消费复核为结构性平方级（120日回放约7200链步、16万次选择），局部缓存无法降到900秒内，需要回放级快照与链步复用的算法调整；银行间、仓单、广度复核也需同类缓存。

## 回放容量第二轮（用户选择继续）

同一commodity-2运行库、08-17—08-28共10个截止日`evaluate_context_replay`实测：

| 步骤 | 秒 | 改动 |
|---|---:|---|
| 基线 | 796.0 | — |
| 官方重建缓存+期货选择可见性分桶+回放共享读取器 | 331.7 | `FuturesInputReader.select`按“选择会比较的全部时刻”分桶复用结果（同桶结果精确一致）；`evaluate_context_replay`与`persist_commodity_basket`内以ContextVar共享一个读取器（范围外每次新建） |
| 仓单解析缓存、银行间整批一次校验、商品复核同快照/同日一次比对 | 183.8 | 仓单按收据字段+原件/规范化SHA-256缓存解析（含异常）；银行间批级校验按内容缓存，逐声明只匹配本声明字段；商品8个同日声明共享一次快照校验与规范化比对 |
| 批内取数不重复查收据、按哈希只读一次 | 103.3 | `read_receipt_content`对已载入收据执行原有全部检查（种类、保留期、哈希缺失、哈希校验），批内相同哈希只读取校验一次；每份收据的保留期检查仍各自执行 |

共享键`receipt_key`覆盖收据全部字段。仍可继续的热点：期货可见性阈值计算、官方GDP基线复核重复解析、广度复核。期间一次`ruff format src/pring_cycle/*.py`误改6个无关文件格式，已恢复到HEAD；银行间/仓单改动前后语义逐条对照保留批级错误使全批声明无效。

## 生命周期转绿

- `capacity-regression-1`：期货/商品/官方/库存/投影/GDP/派生鲜度/仓单完整性/上下文收据/候选回放/模型生命周期/候选准入13文件**969通过/2056.29秒**。
- `lifecycle-3`：已完成120日商品持久化与校准，回放阶段被系统以内存不足终止（机器9GB）。根因：回放共享读取器的选择结果缓存无上限，每份含当日起数百条日历事实副本。修复：同一存储事实的输出字典在读取器内只构造一次并共享；选择缓存改为LRU（8192项）。
- 在lifecycle-3运行库直测完整`replay_models`（[测量](measure-19-full-replay-20260914.log)）：quality/regression/performance全通过、120日、缺口0、阶段差异0，**369.8秒**，峰值RSS 3451MB。
- `lifecycle-4`：完整公开测试**1通过/1929.88秒**——公开CLI准入、`model-accept` accepted、`model-replay`无缺口passed、`model-activate --confirm`成为active，未发布投影。
- `aligned-ppi-1`：注册目录共同月PPI反例（a18真实6月/7月PPI与6月工业财务原件；独立期望：6月末产成品存货7.11万亿元、6月PPI同比+4.1%，即71100/1.041）正常可用，raw/normalized损坏不可用，恢复后可用；对齐文件9通过/9.49秒。复用最新行同一完整性判定，控制例直接通过，未另改源码。

## 可复用材料（19-8）

`build_complete_isolated_lifecycle`为公开全流程构建器；主测试每次真实执行，成功后`store_isolated_lifecycle_material`在材料根（`PRING_TEST_MATERIALS_ROOT`，默认`~/.cache/pring-cycle/test-materials`）按身份键保存完整运行根及`material.json`。身份含执行指纹的code/配置/库版本/依赖哈希、构建器与所用测试辅助文件哈希、全部输入文件哈希。`isolated_lifecycle_material(destination, capsys, clock)`供票17调用：身份命中则整目录复制（不硬链接，避免测试损坏原件污染材料），未命中就地构建后原子入库。运行库无绝对路径。材料约3.5GB，其中120份商品派生结果占2.8GB（每份保存自基日起整链，存储随天数平方增长），列为后续产品风险。

## 材料内存问题与收尾

- `material-1`、`material-3`在激活阶段被系统以内存不足终止（回放已通过、active仍v0001）。定位：[回放上下文输出文档](measure-19-full-replay-20260914.log)单份约630MB JSON（每截止日嵌入全部来源序列快照，随天数平方增长）；tracemalloc显示Python堆逐截止日累积约18MB。用户决定测试侧缓解，输出格式另立后续容量项（任务#16）。
- 测试把`model-accept`/`model-replay`/`model-activate`改为独立CLI子进程（仍为公开入口）。单独测激活子进程峰值5063MB：`replay_matches_current_evidence`重算回放时仍持有已校验的已存文档。改为取出状态与字段后释放已存文档再重算（比对仍用持久化哈希），激活峰值3458MB/380.5秒。
- `material-2`：主测试1通过/1647.48秒并入库；恢复测试失败——身份键含数据库迁移版本，未初始化目标为空而已迁移运行库有值，键不一致导致重建后读错键。迁移版本由代码哈希覆盖，移出身份键仅记录于清单。
- `material-4`：恢复测试1通过/1639.92秒（未命中→构建入库→两份独立复制校验）。材料键`3d6770fd…`，候选`model-reviewed-2957cd3d…`，数据库版本`0021_context_replay_outputs`。

## 独立检出验证与两轴审查（19-9）

批次`d-ticket19`在HEAD `dcb3ea7`独立检出放入10个源码、2个测试文件及212个夹具文件（a18被导入的248份原件及收据、core-transport-196及`* -text`），暂存blob逐字节一致、删除0。检出中mypy 94源文件、Ruff/格式12文件通过；受影响16个测试文件`related`**1031通过/1147.78秒**。检出生命周期测试在构建阶段约20分钟处被系统以内存不足终止，原记录改名保留为`verification-wip-20260914-d-ticket19-lifecycle-oom.*`。

两轴审查（子代理）：Standards指出材料目录未遵守XDG、整目录复制运行库需与ADR-0011划清边界，另有若干判断性坏味道；Spec核实五条关键不变量成立，指出材料复用缺内容完整性校验、容量缓存缺针对性测试、核心导入未用注入时钟等。处理：
- 材料：遵守`XDG_CACHE_HOME`；`runtime-contents.json`逐文件哈希与准入请求哈希入清单，复用前校验并由清单字段重算身份键；新增篡改已存材料拒绝复用反例；`docs/development/local-runtime.md`新增“隔离生命周期测试材料”说明其为可重建合成测试缓存、非ADR-0011运行备份；清单注明v0001基线引导方式。
- 容量测试：`test_reused_reader_selections_match_fresh_reads_across_revision_cutoffs`覆盖同一读取器乱序跨修订阈值与每次新读一致、共享读取范围外损坏可见；变异（阈值漏公开时刻）确认测试失败后恢复源码。银行间/仓单内容缓存已有同进程损坏前后复核用例。
- 内存：输入准备改在`tests/fixtures/isolated_lifecycle_inputs.py`子进程（沿用conftest单调时钟），校准/回放/激活亦为子进程，测试进程保持轻量。
- 判断性坏味道（公共缓存辅助、读取器拆模块、receipt_key归属、多余None默认值）登记后续任务，不在本批改动以保持已验证源码。
- 检出`futures-reader`（新版期货/库存测试）80通过/41.02秒。检出`lifecycle-2`在激活阶段再次被后台任务管理器以低内存停止（原记录改名`-lifecycle-2-oom`保留），测试进程已轻量、采样可用内存始终>2GB，判断为管理器阈值受页缓存影响。用户同意脱离后台任务管理运行：`setsid nohup`独立执行并以监视器守护（可用内存<1.5GB主动终止进程组）。
- 检出`lifecycle-3`：**2通过/1602.83秒**（完整构建1557.79秒；材料恢复、独立性与篡改拒绝43.87秒），源码/依赖/安装包前后一致；`ruff-2`/`format-2`变更测试4文件通过。
- 主工作区按检出暂存清单暂存227文件（15代码/测试/文档+212夹具），blob逐一一致、删除0，提交`8c79143`。
