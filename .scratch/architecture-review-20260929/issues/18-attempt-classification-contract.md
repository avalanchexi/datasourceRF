# 18: 获取尝试的分类契约

**What to build:** 由执行每一步的适配器当场记录各步结果（源失败、结构拒收、入库拒收、本地处理失败）、三类原始原因（外部码、本地规则原因码、异常类）与交付完整性（完整、部分缺成员、无需新增、来源空交付）；字段词汇由获取结果模块定义。外层不再按 Python 异常类型重新定性。

**Blocked by:** 17（改同一批写入点，串行做）

**勿并行：** 02、04、05、09、10、15、19、20、23、24、25、27、28、30（同改：Worker 编排与取数；缺口清单与时效；逐区明细见 [README](../README.md)「串行约束」）

**Status:** done

来源：[架构评审](../README.md) 候选 4 失败分类归属（用户决定，2026-09-29）；逐来源事实见 [codex-survey-c4b.md](../codex-survey-c4b.md) 第 3–8 条。 规格：[spec.md](../spec.md)「五、获取结果模块」。

## 现状（不一致处）

- `TypeError`：Worker 的 TuShare／EIA 路径记 `adapter_failed`（`worker.py:1591`、`:1952`），官方宏观、国债、EIA HTML、ECB 记 `validation_failed`（`official_context.py:867`、`ecb_reference.py:508`）。
- HTTP 非 200：官方宏观／LPR／EIA API 抛 `ValueError`→`validation_failed`（`official_context.py:2560`、`official_lpr.py:404`、`eia_context.py:216`），国债／EIA HTML／ECB 抛 `OSError`→`source_failed`（`treasury_context.py:366`）；前者不保留 HTTP 数字。
- HTTP 错误正文：回执先记 `received` 再失败，落成 `structure_check=rejected`（`acquisition.py:212`、`:285`），进缺口清单成为"结构拒收"。
- 缺标量：增量／reviewed 家族记 `missing_values`，其他上下文家族记 `validation_failed`（`worker.py:1943`）；`missing_values` 既表示"已全部持有、无需新增"，也表示"来源空交付"。`verified_candidate` 可伴随缺格（`treasury_context.py:432`、`eia_html.py:461`、`ecb_reference.py:615`）。
- 入库结果：国债 CSV、EIA、ECB 不回写 `ingest_result`（`treasury_context.py:413`）；官方宏观有回执入库结果但无指标 `stage`。
- LPR 失败尝试只记期次与提供方，无类名、原因、阶段（`official_lpr.py:430`）。

## 已定决定

- 请求是否发出／收到／本地导入由执行请求的适配器与回执仓库记录；调度上不发（缺凭据、预算、未发布）由 Worker 或检索账本记录。
- 不设全局"异常类型→分类"对照表；适配器在步骤边界翻译，Worker 的异常翻译只作兜底并记为本地处理失败。
- VIX、CFETS 报价文件解析错记源失败，属适配器按规格判定（`.scratch/gap-sources-20260925/issues/06-vix-cboe-official.md:8`），维持。
- 郑商所"答复了但缺文件"与"没连上"的区分（ADR-0032）保留在原因里，调度仍可读取。
- 部分交付不算失败；缺口清单等消费者按新字段映射各自类别，旧 outcome 只作兼容输入。

## 验收

- [x] 各来源适配器按模块定义的字段记录步骤结果、原因与交付完整性；上表各不一致处统一。
- [x] HTTP 错误响应记为源失败（带 HTTP 码），不再落成结构拒收。
- [x] 国债 CSV、EIA、ECB 回写入库结果；LPR 失败带原因。
- [x] 按 TDD 在各来源接口上各补一例：源失败带外部码、结构拒收带规则原因码、入库拒收带契约原因、部分交付列出缺失成员、无需新增与来源空交付区分。
- [x] 受影响测试经 `check.py quick` 通过；切片收尾冒烟通过；涉及 Worker 取数，另加跑完整目录正例，记录退出码与耗时。
- [x] 代码审查无阻断。

## Comments

- **勘察**：Codex 只读，结果在 `t18-survey`。
- **契约（`acquisition_outcome`）**：
  - **结果**写入 outcome 列，取 `succeeded`／`source_failed`／`structure_rejected`／`ingest_rejected`／`local_failed`／`not_attempted`。
  - **明细**由 `attempt_details` 构造：`step` 取 request／response／structure／ingest／local；原因分三类，`external_code` 为来源自己的码，`rule_reason` 为本地规则原因码，`error_type` 为异常类；`completeness` 取 complete／partial_members_missing／nothing_new／source_empty，配合 `missing_members`。
  - 旧 outcome 只作兼容输入，读取集合新旧都认；票 18 之前的记录不迁移。
- **步骤边界上的翻译（不设全局对照表）**：
  - 回执仓库 `capture` 标出失败发生在哪一步（`acquisition.failed_step`）：start（请求未发，如预算拒绝）、request、response（HTTP 错误答复）、store、parse、normalize。只有 parse 一步抛 ValueError（违反规则）或 LookupError（缺字段、缺成员）才把回执记为结构拒收，回执与尝试的结论一致。
  - 适配器在读到失败答复处抛 `SourceFailed`（带外部码）。HTTP 错误与 `SourceFailed` 不再落成结构拒收。
  - `capture_failure` 按标出的步骤翻译 capture 边界：请求未发为未尝试；无答复或失败答复为源失败；解析拒收为结构拒收；保存与规范化失败为本地失败。适配器在 capture 之后对行数据施加规则时，ValueError 仍为结构拒收。
  - `ingest_failure` 翻译入库边界：ValueError 为契约拒收，其余为本地失败。
- **各来源**：
  - **HTTP 状态**：官方宏观、LPR、EIA API、国债、EIA 网页、ECB、报价都先检查状态码，非 200 时抛 `SourceFailed` 并带码。TuShare 的非零业务码（`TushareSourceError`／`TushareRefused`）同样是带码的源失败。
  - **TuShare**：
    - `acquire_scalars` 接收被请求的 `metric_ids` 与附加明细，自己在边界记录失败。被请求包装器翻译前的原始异常先暂存，回执 id 由 `on_started` 收齐。
    - 同时记录空交付：breadth/basket 能证明全部已持有时记 nothing_new，其余记 source_empty；basket 日历没有交易日时记 source_empty。
    - 字段全部被规则拒绝时记结构拒收，带规则原因。
    - 交付里缺被请求的指标时，该指标记 source_empty。
    - 成功时，有被拒字段的指标记 partial_members_missing 并列出成员；没有时不声称完整（TuShare 答复不说明应交哪些成员）。
    - `ContextIngestRejectedError` 只包 ValueError。
    - Worker 不再翻译 TuShare 异常，缺凭据记 `not_attempted`；定向补缺也传入被请求的指标与品种。
  - **EIA API**：适配器自己记录 capture／入库失败并回写入库结果。`data=[]` 记 source_empty。少一个系列不再整批拒收：已交付的系列入库，缺的那个记 source_empty，Worker 只为缺的系列取网页。
  - **国债、ECB**：成功时记完整性，交易日上的空值列为缺失成员；回写入库结果。
  - **EIA 网页**：网页按工作日排格，美国假日是空格，所以空格不算缺失成员，只计入 `missing_cells`；回写入库结果。
  - **官方宏观**：只把 ValueError 记为入库拒收。
  - **LPR**：失败带结果、步骤与原因。
  - **报价、郑商所、核心历史**：接入新字段，报价的 HTTP 失败带码；郑商所 capture 中的 TypeError 记录后照旧上抛。按规格，报价文件解析错仍记源失败（规则原因保留）；郑商所"答复缺文件／连不上"的区分（ADR-0032）沿用原消息，不变。
- **读取方**：
  - **批次失败归并**：新结果参与"最后一条"归并。部分交付与空交付不算失败；`not_attempted` 只有缺凭据（condition 以 `_not_configured` 结尾）才算失败。
  - **缺口清单**：source／local／缺凭据映射 fetch_failed，structure／ingest 映射 ingest_rejected（沿用原有类别，原因码改为规则原因）。
  - **P2**：成功时显示完整性，另外显示来源返回码、拒收原因、异常类与缺失成员数。
  - **ECB 兜底**：只补适配器没记录的本地失败。
  - **检索账本**：`SourceFailed` 带 HTTP 码时按码分类；其余（TuShare 码）不当作可立即重试的传输故障，与改动前一致。
- **只记录、不修**：
  - 结构 ValueError 仍把同次已收到的兄弟回执都标为拒收（无法定位到具体那张）。
  - 适配器入口自身的重入错误不会被记录，Worker 也照样吞掉。
  - 郑商所非 200 状态对象路径维持原消息与调度（ADR-0032）。
  - LPR 本地导入入口未标 `request_sent=false`。
- **审查**（Codex 只读）：第一轮阻断项已修，包括：
  - capture 边界按发生步骤翻译，回执与尝试不再矛盾；
  - 状态码先查；
  - 报价带码；
  - EIA API 部分交付；
  - TuShare 完整性不再虚报；
  - 字段全拒；
  - basket 空日历；
  - 预算拒绝记未尝试；
  - 暂存原始异常只在被包装器翻译时使用；
  - Worker 明细带 period。
- **复审修正**：
  - TuShare 延迟校验中保存已通过检查的内容时失败，记为本地失败，回执不拒收。
  - 字段全被拒时，在回执校验之前就以规则原因拒收，回执与尝试一致。
  - 检索账本对带 HTTP 码的 `SourceFailed` 保留状态码，原有按状态码的退避照旧生效。
  - 各适配器的 capture 失败也捕获 LookupError。
  - 报价、郑商所入库时的本地失败记为 local_failed，郑商所仍上抛。
  - 暂存原始异常只替代请求包装器明确报告的失败：`ContextRequestFailed`，定向补取的 `_RequestFailed` 继承它。其他后续异常照原样读取。
  - TuShare 在规则检查时回读自己存下的原件，失败（`OriginalUnreadable`）记为本地失败，回执不拒收。
  - 补测：Worker 只为 API 漏掉的 EIA 系列取网页；账本对 429 状态页的失败保留状态码与退避。
- **验证**（`PYTHONPATH=src`）：
  - 第四轮回归网：完整运行集合加全部适配器、取数、缺口、留存与新用例文件，共 90 个文件，1141 过 1 败（59.5 分钟），失败为下述时钟偶发。
  - 第三轮复审修正之后，重跑所有引用 TuShare 适配器、定向补取或完整运行的测试文件（52 个），661 过 1 败（84.6 分钟，期间机器负载均值高达 90+）；失败为 `test_search_evidence.py` 的一例 `database is locked`，单独重跑 3 例全过。
  - 完整目录正例 `test_worker_registered_catalog.py` 与三核心反例 `test_core_carry_forward.py` 共 3 例通过（188 秒）。
  - ruff、mypy 通过。
- **偶发失败（只记录）**：第四轮回归网中，`test_czce_warrant_refresh.py::test_an_older_tushare_claim_for_the_same_warehouse_is_not_selected` 失败一次，读到空序列。期间系统时钟发生过跳变，该用例以"当前时间"为截止读取。单独跑、整文件跑均通过，与本票无关。
- **测试**（先红后绿）：新文件 `test_attempt_classification.py` 共 10 例，覆盖：
  - TuShare 40203 带码、回执不拒收；
  - 行规则拒收带规则原因；
  - 契约拒收是入库拒收；
  - 被拒字段列为缺失成员；
  - 字段全拒为结构拒收；
  - nothing_new 与 source_empty 区分；
  - LPR／官方宏观 403 页面是源失败（回执不拒收、保留正文）；
  - EIA API 只答一个系列时另一个照常入库。
  - 另有：`test_acquisition_outcome.py` 一例（新结果映射缺口类别、部分交付清除失败）；国债／EIA 网页／ECB 成功回写 accepted 的断言；EIA 回退测试改由真实适配器 403 驱动。
  - 旧字面值断言按新词汇改写：结构拒收、带码源失败、空交付 source_empty、本地失败。
  - 完整运行 P2 用例中，最新记录现在是缺口日定向补取的结果（票 18 起有记录），刷新本身的记录另按期别断言。
