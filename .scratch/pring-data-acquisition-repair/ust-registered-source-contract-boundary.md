# UST 2Y/10Y：新注册目录的最小来源合同与消费边界

只读研究，2026-09-09；读取工作树基点 `99c495a217b66d4bca9d6ceae4688ee69d4382bb`，包含其后未提交增量，文件指纹见末表。仅读取源码、测试和已保存材料，未运行应用、测试、WSL、数据库或网络；下面的公开反例均是待执行设计，不能称已复现、正式认证或真实回放完成。

## 1. 最早拒绝点与已经具备的能力

1. **采集首拒绝是目录解析参数。** [refresh_treasury_yields](../../src/pring_cycle/treasury_context.py#L168) 在请求捕获前的 179–182 行调用 `metric_definition`，没有传 `database_path=paths.database`。[metric_definition](../../src/pring_cycle/catalog.py#L397) 只有带数据库路径才解析登记目录。因此新版本将先遇到 `unknown_metric_definition_version`；该调用还在采集异常处理之外。已有 CLI [treasury-csv-refresh](../../src/pring_cycle/cli.py#L208) 可直接作为公开 RED 入口，无须新命令。
2. **修正目录查询后，真实 CSV 合法结果仍是待认证。** [采集建声明](../../src/pring_cycle/treasury_context.py#L244) 固定 `awaiting_source_certification`、`release_at=None`、`public_available_at=None`。[_validate_claim](../../src/pring_cycle/evidence.py#L1294) 仅对 `certified` 声明调用新目录来源守卫；不能把下一条守卫缺口误写成阻止待认证入库。
3. **已审查候选的第二层拒绝是缺 Treasury 来源合同。** [require_registered_source_contract](../../src/pring_cycle/source_contract_review.py#L211) 未登记两项 UST，具备认证状态的来源声明会遇到 `registered_source_contract_not_implemented`。仅加 provider 白名单不足以绑定 CSV 语义和物理原件。
4. **成员解析已有正确标量回退。** 两项 UST 的 `dimensions=()`、声明 `{}`；[required_dimension_members](../../src/pring_cycle/metric_contracts.py#L222) 返回 `None`，但 [ModelInputSelector](../../src/pring_cycle/search_evidence.py#L176) 对空维度回退 `({},)`。这里没有 `dimension_contract_unavailable` 缺陷。2Y 和 10Y 是两个指标，不应改造成一个带 tenor 的指标或强制全年固定成员。利差才需要两个同日父项。

## 2. 已有官方接口的精确形状

公开入口来自已存官方日表下载链接：[2026 年名义收益率 CSV](https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/2026/all?type=daily_treasury_yield_curve&field_tdr_date_value=2026&page&_format=csv)。本轮没有请求该地址。既有[来源研究](treasury-followup.md#L9)及[正式候选采集记录](implementation-14-treasury.md#L27)已保存身份与取得证据；早期研究第 55 行“无 CSV 适配器”属于旧源码快照，现已被实现取代。

| 合同项 | 当前实现及最小约束 |
|---|---|
| Provider / API | `U.S. Department of the Treasury` / `treasury_nominal_yields_csv`；精确见 [常量及字段](../../src/pring_cycle/treasury_context.py#L21)、[capture](../../src/pring_cycle/treasury_context.py#L230)。 |
| 指标列 | `UST2Y_NOMINAL_YIELD ← 2 Yr`；`UST10Y_NOMINAL_YIELD ← 10 Yr`。按列名定位，不按 CSV 或 HTML 数字位置。 |
| 数值含义 / 单位 | 名义固定期限 par/CMT 收益率，`percent`，4.34 表示 4.34%；不是 TIPS、零息曲线或单只债券收益率。`allowed_units` 应等价于仅 `percent`。 |
| 日期 / 频率 / 成员 | CSV `Date` 为 `MM/DD/YYYY`；规范 `business_day`、同一 ISO 日期起止、`daily`、`{}`。来源日不等于中国目标日或抓取日。 |
| 请求 | 一次一个年度；`endpoint/source_year/start_date/period/definition_version` 写入请求元数据，`period` 是窗口结束日；字段字符串为 `Date,2 Yr,10 Yr`。 |
| 传输 / parser | 无重定向公开 GET；精确 final URL、HTTP 200、`text/csv`；`treasury-nominal-csv-parser-v0001`。原件最大 4,000,000 字节；UTF-8/ASCII 与单一 charset 约束。 |
| source_reference | `年度 endpoint#date=YYYY-MM-DD`，自身不含 raw hash；必须借精确 claim–acquisition 关联找到物理原件，不能仅验证域名。 |
| 合法空值 | `N/A` 和空字符串各有状态、值为 `None`，不创建数值声明。真实 0 合法；负值、非有限数、重复日期/列、错年、错宽、截断等拒绝。[解析器](../../src/pring_cycle/treasury_context.py#L88)已有这些边界。 |
| 时间 | batch `source_timezone=America/New_York`；真实逐日 PUBLIC 仍未知，SYSTEM 为实际接收、校验及追加完成时钟。 |

当前目录两项的 `source_codes` 是 `us_tycr.y2` / `us_tycr.y10`，release family 分别是指标小写，release rule 是 `source_schedule_required`，timezone 是 `source_local_timezone`，见[代码映射](../../src/pring_cycle/catalog.py#L113)、[发布属性](../../src/pring_cycle/catalog.py#L661)。这是现有 TuShare 字段身份；[旧适配器](../../src/pring_cycle/tushare_context.py#L569)实际请求 `us_tycr` 的 `date,y2,y10`，不能把 Treasury CSV 原件说成该供应商响应。

**最窄新合同建议：** 保持指标、角色、优先级、单位、频率、维度及利差公式不变；仅在新登记定义明确 Treasury transport 与 `Date/2 Yr/10 Yr` 的绑定。可使用 `treasury_nominal_yields_csv.2 Yr` / `.10 Yr` 作为新 `source_codes`、共用 `treasury_nominal_yields_csv` 发布家族、`America/New_York` 时区、继续 `source_schedule_required`。这些名称是待实施的软件标识建议，不是已存在或已冻结的合同。若选择保留旧逻辑 source code，须显式说明并测试两种 transport 的字段映射，不能仅复用 TuShare provider 守卫。无需为本切片另选收益率经济口径，也不改旧目录或旧 v3 隔离。

## 3. 真实 raw 与 normalized：可复用材料及不能误拒的差异

已重新以 Windows 标准库读取并核哈希：

| 材料 | 字节 / SHA256 | 本轮独立字面检查 |
|---|---|---|
| [年度 CSV](evidence-14-treasury-followup/a14a321adffded36dfd9ab1aec72cc81423aeca271110f76569d37dd02ca4ee5#L7) | 13961 / `a14a321adffded36dfd9ab1aec72cc81423aeca271110f76569d37dd02ca4ee5` | 表头 15 列；171 行。第 7 行 08/28/2026：`2 Yr=4.34`、`10 Yr=4.73`；第 2 行 09/04/2026：4.37、4.78。 |
| [既有采集 normalized](evidence-14-live-treasury/e6c3fb3d34c90f5fa115971f32dc755020a11d9d8983b65e29c72d61d4d7d10f) | 3194 / `e6c3fb3d34c90f5fa115971f32dc755020a11d9d8983b65e29c72d61d4d7d10f` | 08-24..09-04 的 10 日、20 cells；两个 `latest_reported_periods` 为 09-04，`total_source_rows=171`。 |

独立十进制期望：08-28 `(4.73−4.34)×100=39.00 bp`；09-04 `(4.78−4.37)×100=41.00 bp`。原 CSV 报到百分数小数点后两位，测试不能把显示尾数放大成别的单位。

normalized 顶层是 `TreasuryYieldBatch` 的 `source_year/endpoint/source_timezone/unit/cells/total_source_rows/latest_reported_periods`，另加 `http_response`；cell 为 `metric_id/business_date/value/state/source_text`。它**不是** `ContextScalar[]`、LPR 公告或 NBS 多指标文档。raw 为年度全量；cells 仅包含请求窗口；最新来源期扫描整份 raw。重解析必须使用收据中的起止窗口、媒体类型等，再比完整 batch 和 HTTP 元数据，不能要求 raw 171 行等于 normalized 20 格，也不能把窗口外 09-04 元数据当 08-28 可用值。完整源表仍需通过错年、重复等现有解析检查。

[既有真实采集收据](evidence-14-live-treasury/result.json#L73)属于 `metric-catalog-v0002`，接收 `2026-09-07T09:42:28.124070+00:00`、校验 `09:42:28.166537+00:00`，20 条声明均待认证、PUBLIC 未知。新目录测试应再次经隔离 transport 捕获，产生自身新版本请求收据；不要给这份旧收据换标签、改 normalized 或回填历史 SYSTEM。

时间证据也不能借实现补齐：[官方方法说明](https://home.treasury.gov/policy-issues/financing-the-government/interest-rate-statistics/treasury-yield-curve-methodology)在[已存研究](treasury-followup.md#L38)中区分约 15:30 ET 报价采样与通常 18:00 ET 前可用、可能延迟。两者均不是逐日实际发布时刻。`America/New_York` 是处理夏令时的工程映射；本 CSV 没有可分配给每行的首次发布日期或时间。不要从采样、HTML 日期属性、Last-Modified 或后日取得推导历史 PUBLIC。

## 4. 实际消费者：最小需要串接之处

| 入口 | 已有行为 | 本切片的缺口与最小复用 |
|---|---|---|
| CLI 官方采集 → 声明 → trace | [refresh](../../src/pring_cycle/treasury_context.py#L168)保存 raw、normalized、真实接收与校验，再 append；[现有集成正例](../../tests/integration/test_treasury_csv_acquisition.py#L19)核两项值、SYSTEM/未知 PUBLIC、原件与血缘。 | 补登记目录查询参数；新增 Treasury 精确来源合同。不得顺便把实际采集状态改为 certified。 |
| 检索采用 | [selector](../../src/pring_cycle/search_evidence.py#L143)识别登记定义、标量成员和质量/认证。 | 当前没有 Treasury 重解析资格检查；保存值仍可能在制品损坏后被选中，是静态待 RED 风险。复用下述批量制品 API 后核精确 selected claim。 |
| 原始上下文 | [_metric_rows](../../src/pring_cycle/context_projection.py#L1389)保留状态与来源；Treasury 获取状态及两父项 [input_acquisition](../../src/pring_cycle/context_projection.py#L405)已经展示。 | Treasury 不在现有物理原件资格家族中；需要将资格结果影响实际可用状态与模型采用 ID，保留诊断来源/观测引用。 |
| 2S10S 派生 | [公式启用门](../../src/pring_cycle/context_projection.py#L339)要求两父项 certified，输出 certified 或 derived；[公式](../../src/pring_cycle/context_projection.py#L905)取最新共同统计期，10Y−2Y 再乘 100。 | [_certified_points_by_period](../../src/pring_cycle/context_projection.py#L1318)对 UST 仅过滤质量/认证，没有 raw+normalized 资格；坏最新质量可能先被过滤、继而取旧共同期，需公开反例辨明，不称已复现。应先固定可见最新父项期/版本再判资格，不能坏最新后退回旧两期，也不能错日相减。 |
| PUBLIC 组件回放 | [evaluate_context_replay](../../src/pring_cycle/model_evaluation.py#L666)逐 cutoff 投影；[_context_selection_gaps](../../src/pring_cycle/model_evaluation.py#L1092)检查来源选择、认证、质量、期次与鲜度。 | 缺 Treasury 制品重解析资格共享；只修页面行不足以阻止回放资格误通过。旧 PUBLIC 结果必须不受后来 revision 污染；不能把缺背景方向升级为核心阶段硬门。 |
| Worker / 定向刷新 | [Worker](../../src/pring_cycle/worker.py#L1471)、[targeted_context](../../src/pring_cycle/targeted_context.py#L76)仍调用 TuShare `adapter.treasury_yields`。 | 官方 CSV CLI 可先完成纵向切片，但不能称 Worker 已自动走官方渠道。若纳入这两条流程，应按新定义明确路由 CSV 与实际回执，不把 TuShare 静默视为官方 CSV。 |

不需新增 CAS schema。[EvidenceRepository.source_claim_acquisitions_many](../../src/pring_cycle/evidence.py#L303)已经按真实 claim–request 关联读取 validated 收据的 raw 和 normalized、核物理内容；一个关联失败使该 claim 返回空，单批同收据仅读一次。[source_claim_originals_many](../../src/pring_cycle/evidence.py#L294)也已通过此 API 检查两种制品，但仅返回 raw。`source_claim_publication` 是公告协议，不适合强行套 annual CSV。

最小新增能力可放 Treasury 模块：纯“收据 + raw + normalized → 已校验 Treasury batch”函数，及批量“候选 claims → 合格 claim IDs”适配。前者复用 `parse_treasury_yield_csv`，核 provider/API、精确 endpoint 与 `#date` 身份、请求年/窗口/定义版本/字段/parser、HTTP 元数据、完整 normalized 形状；后者逐声明核 metric/日期/维度/单位/字面数值与该原行关联。每批按 acquisition 缓存重解析，单张年度原件不应为每个标量、每天重复解析。缓存限单次评估，后续读取仍须发现文件损坏。四处消费者共用资格，勿各自实现不同“有效”标准。CSV 没有 PUBLIC 字段，不能因缺公告页头而误拒正确 raw；历史时间资格仍由证据时间与点时选择负责。

## 5. 可直接实施的公开测试顺序

1. **登记候选 → 官方 CLI 获取 → 候选读回。** 复用 [prepared_request](../../tests/models/test_candidate_admission.py#L57)，保留完整目录、全部八公式、核心角色、120 日窗口与执行指纹；修改全部定义版本并通过公开准入提交，不能创建两项专用残缺目录。P2 仍 awaiting 时先调用 `treasury-csv-refresh --start 2026-08-28 --end 2026-08-28 --definition-version <登记版本>`，仅 mock 外部 `open_no_redirects`（见[现成 CLI 用例](../../tests/integration/test_treasury_csv_acquisition.py#L84)）。期望两条待认证原值、两个 trace 均关联真实 capture、公开查询无值；当前预计首拒绝，待运行证实。
2. **经过公开准入的合成已审合同 → 检索/上下文/同日利差。** 同一完整候选中，将两项 UST 定义设为 certified、利差定义设为 derived，并为这三项加入重新计算的 definition bindings；[准入要求](../../src/pring_cycle/candidate_admission.py#L117)对这些 P2 同样检查审查包覆盖。按 [bind_synthetic_review](../../tests/models/test_candidate_admission.py#L5029)重绑 manifest/subject/package，通过公开提交创建；不是改已存候选或绕机器门。实值来自上表年度 raw，transport/时钟/审查结论明确是合成 fixture。获取本身仍保存真实 capture 形状的待认证 claim；另经公开 [append_source_claims](../../src/pring_cycle/evidence.py#L427)构造具有同一 acquisition 关联、合成明确 PUBLIC 的测试来源声明。不得修改私有表或把实际 Treasury 认证状态写死为通过。公开 selector 选两项、投影输出 39 bp 及两个实际采用 ID。
3. **时间正反例。** 真实原件测试保留未知 PUBLIC，不能为了 08-28 阳性测试假称它当时已由系统取得。合成 PUBLIC 用例显式设置来源公开与取得时钟；[TargetBoundEvidenceRepository](../../src/pring_cycle/context_projection.py#L591)即使 SYSTEM 模式也施加中国目标日 23:59 的 PUBLIC 上界：来源日 ≤ 目标日不是充分条件。合成晚发版本仅从后续 cutoff 生效，早日输出全文不变；SYSTEM 不能早于实际 capture/validation/append 可用时间。另验证整个年度最新来源期不改变历史目标期资格。
4. **同一公开纵向路径的制品反例。** 对选中 claim 的 raw、normalized 分别损坏/缺失；换成可读但错列身份、错单位、错窗口/年、错 response metadata、错关联收据的制品也不能通过。正常 15 列/多日期年度 raw、请求窗口裁剪、列换序、额外合法列、合法 0、单父项 N/A 必须保持正确结果。仅一个父项有值时该父项仍可保存/单项检索，利差不能补零。
5. **父项与回放反例。** 先放旧日完整父项，再放新日完整父项；损坏新日 10Y 或使其质量 invalid，断言不能以旧共同日伪装当前可用利差。真实年度 CSV 之后 N/A 的既有语义是保留旧有效 claim，见[回归先例](../../tests/integration/test_treasury_csv_acquisition.py#L452)，不能趁此切片改为“源撤回”或创造新缺值版本。该场景与已存在最新数值 claim 但制品不合格必须分开测试。PUBLIC 组件回放纳入相同资格，而不是只看页面状态。

范围依据：[规格 Testing 2–6、11](spec.md#L130)要求公开链路、真实解析/原件/选值/投影、未知时间与修订反例；[票 14](issues/14-p2-availability.md#L20)保留可选 P2 缺口，不设采购或全部 P2 齐备硬门。以上是软件候选测试；逐日正式 PUBLIC、实际来源审查和完整真实模型验收仍缺，不能由合成测试授予，也不触碰 active gate。

## 6. 读取输入指纹与交付检查

下列为读取快照，不要求后续实现后的工作树仍等于这些 SHA。测试文件包含父代理同批增量；没有为研究重写旧材料。两份制品 SHA/字节见第 3 节。

| 输入 | bytes | SHA256 |
|---|---:|---|
| `src/pring_cycle/treasury_context.py` | 13090 | `0edc0376f9b9b4ab363e82249ef6513521d765ab33c373bc8df26160c960e585` |
| `src/pring_cycle/catalog.py` | 25978 | `fe8dd4e21d563448c31af535f3886fc7fb053133de6346d5d9c4a627a91e7c5c` |
| `src/pring_cycle/metric_contracts.py` | 9849 | `b94d7b0e1da8ca282c53a12779b5bf738d8bf380950189f6569453d8ce598f66` |
| `src/pring_cycle/source_contract_review.py` | 14630 | `c26ee6a06e25dc7b9b3c4c102bc9ce3e780dbc538760ef9318409d28f5ab9772` |
| `src/pring_cycle/evidence.py` | 60796 | `d27332e14065b179f510c6253e06088f376341349657b598bc692070d9c35ec2` |
| `src/pring_cycle/search_evidence.py` | 18966 | `ff00c5d77aedd0559df66260730008cd1f6d1f1e05b37de42d65379b7a31a12a` |
| `src/pring_cycle/context_projection.py` | 87349 | `4f2d4080a857118b693ac1e114a9d086062a879f4e9f87d5a3759383bcfbd568` |
| `src/pring_cycle/model_evaluation.py` | 49636 | `ece7dee6598b18582cf1b35bd4fd518738a7597119d231e6a62be37cc328e2e3` |
| `src/pring_cycle/candidate_admission.py` | 13193 | `681d108eaba822cb538dd828e459e74c64e8909c415f9d3a8f83f17135673bc4` |
| `src/pring_cycle/cli.py` | 39097 | `5ddf9fc308266294ecc1cc9e3f1cf3bc6b332cdbe6730a48f4bd09b06722cfe3` |
| `src/pring_cycle/worker.py` | 58810 | `34a9a9e332872269852a22d7b8f0798a6cb8ab610fd09a9644b4f6739732d96b` |
| `src/pring_cycle/targeted_context.py` | 6396 | `3601a81cd1b505c38f4762cf2c885ee2214851ec8b5f3dd523eb35b124a5cdeb` |
| `src/pring_cycle/tushare_context.py` | 78830 | `ea66afd3b57969fbd2bcf76889e0bfb7e92037bd1ee12e931b4d14dde2b340a4` |
| `tests/integration/test_treasury_csv_acquisition.py` | 20743 | `fcf5056d5dca8fad7d5ca4a8a14c49529be595d0b0358f43a5f81042699d957c` |
| `tests/models/test_candidate_admission.py` | 283112 | `fbc34a2f0b95877c72fa5942d53659416c559053f8b48553e09beb8148d27189` |
| `.scratch/pring-data-acquisition-repair/spec.md` | 27762 | `f5c32c407f216841b2afed0aaab3863868bdc394d9057207d25dbc9e9a561cc4` |
| `.scratch/pring-data-acquisition-repair/treasury-followup.md` | 13974 | `fb581c82729b523efdae919d33a05f1df9c77f9ab1eeaf359d58aafc00bb97c8` |
| `.scratch/pring-data-acquisition-repair/implementation-14-treasury.md` | 5051 | `3ee5e89f1c39c0bf12f43369218b5e600b2eb153e3fc8c253cb6dbc0e0eaa6bf` |
| `.scratch/pring-data-acquisition-repair/evidence-14-live-treasury/result.json` | 66331 | `14c07886dc93d8869441483ef0c03cf52c217a310900c4cb59332250f40578f4` |

唯一新增文件为本 Markdown。交付前以 Windows 标准库检查 UTF-8、所有本地链接文件与 `#L` 行号存在，并独立核对两份制品字节/hash；没有运行本项目模块。最终字节数、SHA256 和链接计数在交付消息报告，不写入本文件以避免自哈希循环。
