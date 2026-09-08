# 三核心原件在消费时的校验边界

2026-09-09，只读 research。基点 `4084834744b5d5514e0dd5952e847f0d37247c20`；`model_evaluation.py` 包含主线尚在回归的逐日 PUBLIC 修复，按文末工作树指纹绑定。本轮未运行应用或测试、未查询数据库、未联网；唯一写入是本文。**以下是静态结论和反例设计，不是已复现故障或生产数据损坏报告。**

## 已确定的消费缺口

新目录三核心声明在入库前会核对关联原件，但入库后 `ModelInputSelector`、Worker 核心计算和 `evaluate_history` 都没有重新读取其原件。因此，在其余条件不变、有效声明已经入库之后，仅移走或破坏该声明关联的核心原始响应，这三处当前代码不会因该原件故障拒收。这个判断不等于一次完整 Worker 运行必然成功：它仍可能被 active、其他输入、日历或运行环境门挡住。

| 边界与源码 | 已有检查 | 未检查的部分 |
|---|---|---|
| [`EvidenceRepository.append_source_claims` L374–425](../../src/pring_cycle/evidence.py#L374) → [`_validate_core_originals` L245–278](../../src/pring_cycle/evidence.py#L245) | 新目录、已认证三核心必须关联 acquisition；读 raw 并核哈希；按真实 receipt 重解析；逐统计日核 close 等于 claim.value。单批按 `(metric_id, acquisition_id)` 复用解析结果；入库另核 fetched/available 与回执时间 | 只发生于追加声明时；旧声明后续消费不会再次走这里 |
| [`ModelInputSelector.select` L160–184](../../src/pring_cycle/search_evidence.py#L160) | 选中、数值状态、claim 与定义已认证、质量 validated；三核心另调 `selected_core_claim_is_valid` | 不读 acquisition/raw/原表行；`series` 的内存缓存也只有选值结果 |
| [`selected_core_claim_is_valid` L62–75](../../src/pring_cycle/source_adapters.py#L62) | provider=tushare、精确 API/code/日期的 source_reference、index_points、certified、validated | 无仓库参数，无原件读取或原行比较 |
| [`Worker._core_readiness` L883–969](../../src/pring_cycle/worker.py#L883) | SYSTEM 截止、目标日、冲突、上述 source identity、数值；使用全部隐藏预热计算趋势 | 未读 raw；显示末 120 条，但计算与 model input IDs 可能远多于 120 条，不能只查页面显示部分 |
| [`evaluate_history` L280–345](../../src/pring_cycle/model_evaluation.py#L280) | 本批已经按每个中国日末重选 PUBLIC，检查完整前缀、正值、reported、所选 claim certified/validated，并绑定每日输入 hash | 仍不读 raw；本函数也未调用三核心的 provider/API/source_reference 校验函数。新目录写入守卫不能证明消费时原件仍可读取 |

三核心既定身份为 `CN_BOND_CORE_000012 → index_daily/000012.SH`、`CN_EQUITY_CORE_000985 → index_daily/000985.CSI`、`CN_COMMODITY_CORE_NHII → fut_index_daily/NHII.NH`；重解析函数 [`parse_core_acquisition` L25–59](../../src/pring_cycle/source_adapters.py#L25) 已核 provider、API、parser v0002、字段顺序、ts_code、请求起止和返回日范围，无需重新发明解析器或换用其他指数。

上层现有检查不能抵消这个缺口：

- [`EvidenceRepository.trace` L970–1011](../../src/pring_cycle/evidence.py#L970) 的 `linked` 仅表示可见 claim 有 acquisition 关联，不读取原件字节。
- Worker 入口 [`process_pending_run` L144–158](../../src/pring_cycle/worker.py#L144) 的 `mutation_rejection` 调 [`maintenance.py L49–64`](../../src/pring_cycle/maintenance.py#L49)，其 runtime integrity 来自状态表（[L200](../../src/pring_cycle/maintenance.py#L200)），不是逐原件扫描；[`artifact_health` L84–89](../../src/pring_cycle/artifacts.py#L84) 只看目录和登记表是否存在。
- [`require_registered_manifest` L108–114](../../src/pring_cycle/catalog_registry.py#L108) 验证目录与模型定义绑定；它不校验每条已入库市场声明的 acquisition 内容。
- [`AcquisitionRepository.read_content` L302–317](../../src/pring_cycle/acquisition.py#L302) 本身确实会重新读取并比较 SHA256，只是上述三个消费器没有调用它。raw 与 normalized 是不同制品；删除任一者当前均不会被这三处值消费逻辑发现。

## 最小共享校验设计

建议增加一个**单次评价使用的核心来源校验器**，由三个消费器共用同一实现，放在核心来源边界，复用 `parse_core_acquisition`。不要在通用 `metric_series/query` 中改写历史声明的 certification、quality 或选值，也不要扫描整个 CAS。

1. 先保留各消费者既有目录、PUBLIC/SYSTEM、目标日、selected/conflict、reported/正值、认证与质量规则。对**新登记目录**的三核心，检查所选 claim 的精确来源身份，再核该 claim 的 acquisition 关联。内置旧版本保持各自现有行为；尤其不能给 v1 合成回归强加今天才要求的原件，从而重写兼容边界。
2. 至少有一个关联，且所有声明关联的 core acquisition 都须有效，继续沿用入库的全关联约束；不能只找一份可匹配的“好文件”掩盖另一个坏关联。读取 receipt 指定的 raw、核 exact SHA、复用纯 parser，建立 `business_date → MarketBar` 索引，核该日原行、close、metric/API/code、单位与 claim 一致。缺原件、坏哈希、错接口、少原行、值不等或非法回执都返回不可采用，不退回该 provider 的更旧 revision 填平故障。
3. 已有公共 [`source_claim_originals(claim_id)` L280–301](../../src/pring_cycle/evidence.py#L280) 可以完成单 claim 的准确关联与 raw 哈希读取；它的不足是每次调用都会读同一 raw。最小性能扩展是其**批量读取/单次读取会话**：批量取 exact claim→receipt 关系，每个唯一 acquisition 读取一次，保留各 claim 的关联，不把同 provider 或同日期的任意回执混入。无需新表、全局 registry 或重复采集。
4. 校验缓存分层：本次评价已核 claim ID；本次已读 receipt/acquisition；按 `(metric_id, acquisition_id, raw_hash, parser_version)` 复用原行索引。回执的 API/参数等身份必须检查，不能只凭 raw_hash 将不同接口回执视为同一来源。原始字节读完可仅保留紧凑索引及校验结果，避免把每条 claim 又复制一份多年响应。
5. 缓存只在明确的评价/校验批次内有效：Selector 的一次固定截止评价、Worker 的一次就绪计算、一次 `evaluate_history`。下一次公开评价必须新建或清空校验会话；禁止跨运行以 claim ID 永久记“已验证”。同一对象若对外承诺支持后续独立 `select` 评价，也要在新评价边界失效或检测文件状态变化。此设计保证评价时重新取得并验证的输入；不声称持有已验证内存快照后还能即时发现磁盘在同一评价中任意时刻的变化。

性能目标应是**唯一物理原件数/唯一 claim 数**，而不是 `3 × 每日历史前缀长度 × 多年响应大小`。一份 TuShare 响应可能含 2,338 日；只缓存 parser 输出、却每条 claim 调一次 `source_claim_originals`，仍会重复读盘/哈希。逐日 PUBLIC 重选时只校验新遇到的 selected claim；未来不可见 revision 的坏文件不应提前使较早 cutoff 失败。一旦该 revision 在某日成为 selected，才需要对它核验，失败按该日缺口处理。

三个接入点分别是 Selector 加入 accepted 之前、Worker 构造 `PricePoint` 之前、`evaluate_history` 将每日 selected 前缀纳入 input hash/趋势之前。已有 PUBLIC 修复的 cutoff、分段趋势和输入 hash 不应被这次原件校验改回结束日选值。这里检查的是**今天执行时原件是否可验证**，不创造历史 `public_available_at` 或修改已发布结果。

关于 normalized：最小“原行支持数值”校验以 raw 重解析为依据。若本批要同时声称“完整 raw→normalized 证据链仍可读”，还应对同 receipt 的 normalized 用 `read_content(..., "normalized")` 核哈希，并与重解析后的标准化内容核对；它也按唯一 receipt 一次完成。不能把 normalized 丢失等同于 raw 存在、或反过来用 normalized 代替原始响应。当前 `_validate_core_originals` 只核 raw，故 normalized 完整链是应明确陈述的交付边界，不能说现有入库已经核完两者。

## 可直接推进的公开测试入口

**第一条最短纵向 RED：新目录已入库 → 原件损坏 → 新 Selector 评价。** 复用 [`test_registered_core_history_preserves_originals_and_unknown_public` L3609–3710](../../tests/models/test_candidate_admission.py#L3609)：通过已有 synthetic admission helper 创建候选；真实 `refresh_core_history` 使用注入的外部 transport 保存三核心 raw/normalized/回执并入库；`ModelInputSelector(..., SYSTEM).select(scope)` 已有 3 项 complete 正例。随后只在该测试自己的 `tmp_path` 中移走或改写一个核心 raw，再**新建 Selector** 评价。

期望：损坏前 complete；损坏后对应核心不 complete、不返回它的 selected claim ID；其余核心原件仍正常。顺便调用 `source_claim_originals` 应为空，证明测试确实破坏了所选 claim 关联文件。当前代码静态预计 selector 仍 complete，这是应由主代理运行确认的反例，不能用“仅 read_content 抛错”替代消费者断言。缺失/改写 fixture 模式可参考已有 [L2783–2817](../../tests/models/test_candidate_admission.py#L2783)，但该旧测试发生在**候选创建前**，不是本次消费风险的现成覆盖。

第二条 PUBLIC 回放纵向：同一新目录下使用真实 acquisition fixture 的 raw/receipt，并以公共 `append_source_claims` 追加**明确标合成**的可靠 PUBLIC 声明；真实 `refresh_core_history` 的 PUBLIC 仍保持未知，不能改生产解析器为测试伪造发布时间（见 [`core_history.py L129–166`](../../src/pring_cycle/core_history.py#L129)）。为三核心准备 147 个正值合成工作日和原规则预热，公开调用 `evaluate_history`；先成功，再破坏一份 selected 原件，下一次调用应以原件/证据不完整失败。期间不修改认证状态、目录定义或模型 active。再覆盖旧 revision 原件完好、新 revision 原件坏：新 revision PUBLIC 之前的短窗口应仍成功，跨到其可见日的长窗口失败，不能因损坏静默回选旧版本。

| 额外关键例 | 期望/范围 |
|---|---|
| 两个连续评价之间文件损坏，复用进程 | 第二次必须重新校验；防止永久成功缓存 |
| 同一大响应对应 120/2,338 日，多次逐日选值 | 按该评价的唯一 receipt 读/哈希/解析；仍逐 claim 比较原行。可对外部原件读取/纯 parser 加透明计数 wrapper，但不替换解析结果或消费者 |
| 错原件、错 code、错 close、原件缺统计日 | 沿用已有 [L3713–3807](../../tests/models/test_candidate_admission.py#L3713) 的入库负例作为回归；新消费测试必须先合法入库再引入文件故障，不能被入库守卫提前挡住而“绿” |
| 内置 v1 无 raw 的旧 fixture | 保持其已接受的旧版本消费行为；新原件要求仅作用于新目录，不解除 v3 否定守卫 |
| 未认证新目录/非 active 候选 | 仍由原认证/active 门拒绝；不是本次原件校验的通过依据 |

Worker 的真实公开入口为 [`process_pending_run`](../../src/pring_cycle/worker.py#L144)，由 `_execute_run` 在 [L336](../../src/pring_cycle/worker.py#L336) 调核心就绪计算。现有 [Worker L179–234 用例](../../tests/integration/test_worker_execution.py#L179) 可复用“运行→投影/输入 IDs”的断言结构，但它是内置 v1，不能直接声称覆盖新目录原件规则。本轮读取的测试中没有已核实可直接复用的新目录 active Worker fixture；其正式纵向测试需要合法的隔离 active fixture 和回执数据，不能 monkeypatch `_core_readiness`、active 检查或模型清单来制造通过。候选仍不可正式运行，现有 [L509–525 用例](../../tests/integration/test_worker_execution.py#L509) 保留。最窄先实施共享校验并以 Selector/PUBLIC 两个公开路径证实，Worker 必须接同一实现；如果这一批尚未做真实新目录 Worker 纵向，记录为未覆盖，不能把两入口全绿叫三入口均验证。

这些都是软件 fixture 验证，不是来源正式认证、120 日真实回放或激活。模型、发布历史和证据版本不变的依据见 [CONTEXT.md](../../CONTEXT.md)、[ADR0006](../../docs/adr/0006-dual-as-of-and-immutable-evidence-vintages.md)、[ADR0012](../../docs/adr/0012-atomic-model-versions-and-parallel-replay.md)；原件应可读取、历史关联不得捏造，见 [spec.md L93–98](spec.md#L93)。

## 输入指纹与交付

采样时间 `2026-09-08T16:21:30.212456+00:00`（中国时间 09-09 00:21）。以下是 Windows 标准库只读得到的工作树字节，非测试执行指纹。

| 输入（仓库根相对路径） | bytes | SHA-256 |
|---|---:|---|
| `src/pring_cycle/evidence.py` | 58457 | `e2166a8e292f6ee5ac12173d8a28072245eac83837cad5b6d29ac395353b2963` |
| `src/pring_cycle/source_adapters.py` | 11994 | `c0ee39985101e51e5437944bcadef49a92f1f78aab7858a5b4a0e097344e388c` |
| `src/pring_cycle/search_evidence.py` | 15734 | `dc5d6f00536e7792e49fc19171effa30f0a8af1688c5a491c8c75ccc97c55b45` |
| `src/pring_cycle/worker.py` | 58270 | `e58ef5f21f6159448d959cc1bf5b8092438ed72781d829418e5b79c1b5163c6f` |
| `src/pring_cycle/model_evaluation.py` | 41631 | `1bb5170df32985fb7b2b5ba9a9583d40941c11f3ce7faeb90a6f6cc8b8c7b088` |
| `src/pring_cycle/acquisition.py` | 14476 | `bcfb57f76f285e784991f218a45131cab3ed5a8f0732499794a2bf7d6d2e9e71` |
| `src/pring_cycle/maintenance.py` | 9024 | `38bca1b42b4219cd592c980812ea882e4c65a341bc8c93494016fe3aa9f92c29` |
| `src/pring_cycle/artifacts.py` | 3022 | `114427470f2c3f8140eb22d214465620e99a1b2a7baa8c3c1717b8ba4e750ea4` |
| `src/pring_cycle/catalog_registry.py` | 4293 | `41ddb91573330a206e388b9b32665e511a286a22a6eb1eeff674803dabda0544` |
| `src/pring_cycle/core_history.py` | 7944 | `bca200e5d2bdaab71fe3f819e7d0183f6b27bd3b13e2acae17ed64b879764d13` |
| `tests/models/test_candidate_admission.py` | 156956 | `f6c0ab2d79935620d28d7a3c0f31586d5e736f7a2815cd36de13126a5f83b0f5` |
| `tests/integration/test_worker_execution.py` | 36825 | `d9f485be66763f1a4e8bcd00b9b0243abad19e02a7dff6fd94cd7aed719d7905` |
| `.scratch/pring-data-acquisition-repair/spec.md` | 27762 | `f5c32c407f216841b2afed0aaab3863868bdc394d9057207d25dbc9e9a561cc4` |
| `CONTEXT.md` | 20103 | `f0cdf13436e1dd178b86ac6181de916757c3ef59edb7024ec6e980f151e5a102` |
| `docs/adr/0006-dual-as-of-and-immutable-evidence-vintages.md` | 725 | `acb0c307d24518d5e4551f457353535d5398d21c8bd0212c9f9445a82012cf8a` |
| `docs/adr/0012-atomic-model-versions-and-parallel-replay.md` | 1277 | `172a1d28d5d67b7075930872032887fd0c4b5748903ed26a5a8760626681ef12` |

唯一交付：`.scratch/pring-data-acquisition-repair/core-original-consumption-boundary.md`。交付消息给本文精确 bytes/SHA；本地引用按文件所在目录解析并检查行号有效。无新增外部请求或采集原件。
