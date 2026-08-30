# 本机开发与运行

## 环境边界

V1 运行在 WSL2，源码可以位于 `/mnt/d/cursor/datasourcerf`，但 Python 环境和全部可变
运行状态必须位于 WSL 原生文件系统。不要把虚拟环境、SQLite、WAL、日志、制品或密钥放在
`/mnt/c`、`/mnt/d` 等 Windows 挂载目录。

需要已安装的 `uv`。项目的 `.python-version` 会让 `uv` 获取并使用 Python 3.12。源码在
Windows 挂载盘时，按下面方式把项目虚拟环境放入 WSL 原生 XDG 数据目录：

```bash
export PRING_CYCLE_DEV_ENV="${XDG_DATA_HOME:-$HOME/.local/share}/pring-cycle/dev-venv"
UV_PROJECT_ENVIRONMENT="$PRING_CYCLE_DEV_ENV" uv sync --extra dev --no-editable
export PATH="$PRING_CYCLE_DEV_ENV/bin:$PATH"
```

`--no-editable` 是源码位于 Windows 挂载盘时的运行边界：项目会复制安装到 WSL 原生虚拟
环境，正常 Python 导入产生的字节码也留在该环境中，不会写回源码树。后续使用 `uv run` 时
同样保留此选项，避免 uv 把项目切回 editable 安装。

`uv.lock` 固定 FastAPI、Dash 4.2、SQLAlchemy、Alembic 和其他依赖版本。应用启动和日常离线
验收不安装依赖，也不访问包索引。

## 初始化与诊断

首次运行显式初始化，然后执行诊断：

```bash
pring-cycle init
pring-cycle doctor
```

默认目录为：

| 内容 | 默认路径 |
| --- | --- |
| 普通配置与密钥 | `${XDG_CONFIG_HOME:-$HOME/.config}/pring-cycle/` |
| SQLite、WAL 与内容寻址制品 | `${XDG_DATA_HOME:-$HOME/.local/share}/pring-cycle/` |
| JSONL 日志与运行状态 | `${XDG_STATE_HOME:-$HOME/.local/state}/pring-cycle/` |
| 可重建缓存 | `${XDG_CACHE_HOME:-$HOME/.cache}/pring-cycle/` |

测试和一次性验收可以传入 WSL 原生临时目录：

```bash
PRING_CYCLE_VERIFY_ROOT="$(mktemp -d)"
pring-cycle init --runtime-root "$PRING_CYCLE_VERIFY_ROOT"
pring-cycle doctor --runtime-root "$PRING_CYCLE_VERIFY_ROOT" --json
```

`init` 是幂等的。它创建 SQLite WAL、升级到当前 Alembic head，并建立
`artifacts/sha256` 内容寻址目录。制品先写入同目录临时文件，校验 SHA-256 后原子改名，
最后才在 SQLite 登记字节数、媒体类型与来源引用，因此数据库不会指向半文件。Web 和
Worker 不会隐式初始化；未初始化时固定返回 `runtime_not_initialized`，也不会创建运行文件。

`doctor` 会报告 Python 版本、`uv.lock`、运行路径、SQLite/WAL、Alembic、制品注册表和四个
数据源适配器的启用状态。缺少凭据只把对应外部能力标记为 `disabled`，不阻止离线启动。

## 密钥边界

密钥文件为仓库外的 `secrets.env`，权限由应用保持为 `0600`。只允许配置：

```dotenv
TUSHARE_TOKEN=
EIA_API_KEY=
TAVILY_API_KEY=
EXA_API_KEY=
```

不要提交真实值。应用不会把值或认证头写入 CLI 输出、浏览器、日志、报告或验收结果。
Codex CLI 与 Claude Code CLI 的登录状态不由应用读取或保存；Ticket 01 的离线启动不要求任一
CLI 已登录，也不接收模型厂商 API key。

从旧环境迁移密钥时，使用白名单迁移命令；它只导入上述四个键，原子更新仓库外文件并保持
`0600`，输出仅包含适配器名称和 `enabled/disabled` 状态，不回显值：

```bash
pring-cycle secrets-migrate --from /wsl/path/to/original-project/.env --json
pring-cycle doctor --json
```

源文件没有的允许键会保留目标文件中的现有值，其他键一律忽略。也可以用权限为 `0600` 的
编辑器直接打开 `doctor` 所列 `secrets` 路径逐项配置；不要用 `echo TOKEN=...`，避免 shell
历史和终端回显。

## 启动 Web 与 Worker

在两个 WSL 终端中使用同一正式 CLI：

```bash
pring-cycle worker
```

```bash
pring-cycle web --port 8050
```

Windows 浏览器访问 `http://127.0.0.1:8050/`。Web 只绑定 `127.0.0.1`；没有可配置的
局域网监听地址。健康页与 `/api/v1/health` 分别显示 Web、Worker、SQLite/Alembic 和制品
目录状态。Web 先提供带真实投影身份和八页导航的轻量只读首屏，再在后台原子切入完整 Dash
交互子应用；Dash 的正式 HTML 仍保留同一服务端首屏，直到浏览器完成交互布局，不会在后台
加载完成后退回空白 Loading 页面。完整布局失败时首屏和 REST 仍可读并记录本机错误事件。关闭页面或停止 Web 不会
停止独立 Worker。

启动 Web、打开页面或启动 Worker 都不会补跑任务、联网、刷新证据或调用 AI。浏览器命令入口
同时校验 `Host` 和 `Origin`；不受信网页得到脱敏的 `403`，不能进入后续命令追加接缝。

停止服务时在各自终端发送 `Ctrl-C` 或 `SIGTERM`。两个进程都会写停止事件并退出；不要用
`kill -9` 作为正常停止方式。状态检查使用 `pring-cycle doctor --json`、
`pring-cycle runs --json` 和 `pring-cycle cutover-status --json`。

## 模型、证据与运行操作

初始化登记冻结的 `model-v0001` 与新的 `model-v0002` 候选，不会隐式激活。v0001 的目录与
清单哈希保持历史不变；v0002 固定本次 P1/P2 目录身份和派生公式，必须经过来源认证、回放和
用户批准后才能生效。Worker 从该次运行绑定的生效模型清单加载上下文目录和派生公式，不从
进程全局的“最新目录”读取；模型切换与回退因此会同时切换核心趋势和上下文语义。
`model-accept` 从仓库内已认证的三核心
`public_as_of` 历史重新运行冻结趋势与阶段规则；历史不完整或结果不满足冻结基线时直接失败，
不接受人工传入的“通过”布尔值。机器校准通过后再由用户显式批准：

```bash
pring-cycle models --json
pring-cycle core-history-refresh \
  --start 2017-01-01 --end 2026-08-19 \
  --definition-version metric-catalog-v0001 --json
pring-cycle model-accept --model model-v0001 --json
pring-cycle model-activate --model model-v0001 --confirm --json
```

历史刷新按自然年分片调用 TuShare，三条核心必须逐年共享同一上交所交易日历，任一缺口都会在
写入前失败。规范化的 `close/pre_close/official_return` 输入会保存为本机内容寻址制品；校准
从 2017-01-01 起加载 2,338 个共同交易日作为状态机预热与证据输入，但只在
2018-06-01—2026-08-19 的 1,995 个共同交易日内计数验收指标。验收结果同时绑定输入区间、
计数区间、交易日数和规范化证据哈希；预热期不得折算为正式转换。后续实时数据不会静默扩大
`model-v0001` 的冻结校准区间。

证据 JSON 必须包含 metric identity、统计期、单位、来源、公开/抓取/系统可用时间、认证与质量
状态。写入及点时查询示例：

```bash
pring-cycle evidence-ingest --input /wsl/native/path/claim.json --json
pring-cycle evidence-query --observation-id OBSERVATION_ID \
  --mode system_as_of --as-of 2026-08-28T21:00:00+08:00 --json
```

### 确定性三核心 fixture

离线验收可通过正式 CLI 把冻结交易日历和三核心价格生成最小原子投影：

```bash
pring-cycle fixture-project --input /wsl/native/path/core-fixture.json --json
pring-cycle projection --json
pring-cycle stage-history --json
```

fixture 顶层 schema 固定为：

```json
{
  "schema_version": "core-price-fixture-v0001",
  "target_business_date": "2026-08-28",
  "system_as_of": "2026-08-28T21:00:00+08:00",
  "model_version_id": "model-v0001",
  "trading_calendar": ["...按升序排列的中国交易日..."],
  "assets": {
    "bond": {"metric_id": "CN_BOND_CORE_000012", "prices": []},
    "stock": {"metric_id": "CN_EQUITY_CORE_000985", "prices": []},
    "commodity": {"metric_id": "CN_COMMODITY_CORE_NHII", "prices": []}
  }
}
```

每个 `prices` 元素只包含 `business_date` 和正的有限 `value`，日期必须与
`trading_calendar` 完全一致。命令输出 `acceptance_only=true`、不联网、不激活候选模型，投影
带 `acceptance_fixture_only` 警告，不能作为真实 P0、模型校准、真实演练或切换证据。

若 P0 因历史不足、来源冲突、陈旧或身份错误未通过，命令返回 `action_required` 和不可变
`assessment_id`，当前指针继续读取上一完整投影。用户可显式生成不调用 AI 的缺口说明：

```bash
pring-cycle gap-notice --assessment-id P0_ASSESSMENT_ID \
  --request-id UNIQUE_GAP_NOTICE_ID --json
pring-cycle gap-notices --json
```

阶段历史包含正式事件与空档，并保留三资产状态、候选/12M 观察、快照、模型和投影身份；缺口
说明不是正式市场报告，也不出现在 `pring-cycle reports` 中。

### LPR 官方发布与发布日历

V1 的首条 P1 认证官方链路是中国货币网 LPR 公告。目录身份固定为
`CN_LPR_1Y_5Y` / `CHINAMONEY_LPR`，单位为百分比，频率为月度，维度仅允许
`tenor=1y|5y_plus`。发布族是 `chinamoney_lpr`，规则版本固定为
`monthly_day_20_holiday_roll_0900_asia_shanghai`：每月 20 日、节假日顺延、北京时间
09:00 发布。预计窗口只决定等待和检查状态，绝不证明公告已经发布。

先用已脱敏 HTML fixture 执行不联网、不初始化运行目录、不落库的契约检查：

```bash
pring-cycle lpr-contract --input /wsl/native/path/lpr.html \
  --url https://www.chinamoney.com.cn/chinese/rdgz/YYYYMMDD/CONTENT_ID.html \
  --period YYYY-MM --fetched-at 2026-08-20T09:02:00+08:00 --json
```

人工真实烟雾必须显式给出当期公告的精确 HTTPS URL。它只输出来源身份、最终 URL、字段
形状、发布时间、观测数量、字节数、SHA-256 和结论，不保存响应正文；通过结果会登记为
`source-smoke-v0001` 内容寻址制品，供真实演练按哈希核验：

```bash
pring-cycle lpr-smoke \
  --url https://www.chinamoney.com.cn/chinese/rdgz/YYYYMMDD/CONTENT_ID.html \
  --period YYYY-MM --json
```

烟雾通过后，显式摄取会把公告作为内容寻址制品保存，并以一个发布事件原子写入两条认证
source claim；同一正文重复获取保持幂等，后续修订只能从实际抓取修订的时点起进入
`public_as_of`，不会回填到原公告时点。普通 `evidence-ingest` 不能自称这条来源已认证：

```bash
pring-cycle lpr-refresh \
  --url https://www.chinamoney.com.cn/chinese/rdgz/YYYYMMDD/CONTENT_ID.html \
  --period YYYY-MM --json
pring-cycle release-calendar --period YYYY-MM \
  --as-of 2026-08-20T09:05:00+08:00 --json
```

若 20 日之后存在已冻结的法定节假日，可向只读日历命令重复传入
`--holiday YYYY-MM-DD`；周末自动顺延。REST 对应 `/api/v1/catalog`、
`/api/v1/release-calendar?period=YYYY-MM&as_of=...` 和
`/api/v1/evidence/{observation_id}`。页面“发布日历”显示事件族、统计期、时区、上一期沿用、
最近获取、下一检查和关联观测数量，并分别保留实际发布、公开可用与系统首次可用时间。

### PBOC/NBS 官方上下文与 EIA 原油

PBOC/NBS 缺口使用同一严格 HTML 适配器边界。支持的 `family` 为
`pbc_omo_notice`、`pbc_rrr_notice`、`pbc_tool_liquidity_monthly`、
`pbc_social_financing`、`pbc_loan_structure`、`pbc_usdcny_central_parity`、
`nbs_core_cpi`、`nbs_industrial_value_added`、`nbs_industrial_finance` 和
`nbs_capacity_utilization`。先对保存的脱敏样本做无网络契约检查：

```bash
pring-cycle official-context-contract \
  --input /wsl/native/path/official-sample.html \
  --family FAMILY --url OFFICIAL_HTTPS_URL --period PERIOD \
  --fetched-at 2026-08-28T10:05:00+08:00 --json
```

真实 smoke 必须由用户显式给出当期官方页面；结果只保留来源、字段、时间、数量、字节数、
HTTP 状态和内容哈希，不保存正文，并返回真实演练所需的制品哈希：

```bash
pring-cycle official-context-smoke \
  --family FAMILY --url OFFICIAL_HTTPS_URL --period PERIOD --json
```

smoke 通过只证明该次页面满足候选契约，不会自动把目录来源升级为 `certified`。来源认证还需
人工核对历史覆盖、版式族、许可和单位，并通过新的指标目录/模型版本生效；此前候选 claim 会
追加保存但在宏观和库存投影中遮蔽数值。需要摄取精确公告时，使用下述 `targeted_refresh` 并
同时传 `--source-url`，Worker 会按指标集合选择唯一 family。

EIA Brent `RBRTE` 与 WTI `RWTC` 使用官方 API v2
`/v2/petroleum/pri/spt/data/`，固定日频、`Dollars per Barrel` 与两条 series identity。
离线 JSON 契约检查和显式真实 smoke 为：

```bash
pring-cycle eia-contract --input /wsl/native/path/eia-response.json \
  --start YYYY-MM-DD --end YYYY-MM-DD --json
pring-cycle eia-smoke --start YYYY-MM-DD --end YYYY-MM-DD --json
```

后者只从仓库外 `secrets.env` 读取 `EIA_API_KEY`，输出不含 key 或完整响应。完整运行在配置该
key 时独立刷新 EIA；没有 TuShare token 也不会阻断 EIA。两条 P2 原油在真实 smoke 与来源
认证前保持 `awaiting_source_certification`，绝不替换 NHII 商品核心。

TuShare 的 PMI、CPI/PPI、货币、社融、仓单、GDP、美债和资金市场 schema family 使用一条
显式、只输出身份/时点/数量/哈希的汇总 smoke；它不会保存来源正文或回显 token，只登记脱敏
结果制品：

```bash
pring-cycle context-source-smoke --target-date YYYY-MM-DD --json
```

手动完整运行是主路径；命令先持久化，独立 Worker 再领取。定向刷新、手动深搜和报告任务使用
同一账本与幂等键：

```bash
pring-cycle run-submit --target-date YYYY-MM-DD --request-id UNIQUE_ID --json
pring-cycle run-submit --type targeted_refresh --target-date YYYY-MM-DD \
  --release-event RELEASE_EVENT_ID --metric METRIC_ID --period YYYY-MM \
  --request-id UNIQUE_ID --json
pring-cycle run-submit --type manual_deep_search --target-date YYYY-MM-DD \
  --release-event RELEASE_EVENT_ID --metric ONE_EXPLICIT_METRIC --period YYYY-MM \
  --request-id UNIQUE_ID --json
pring-cycle run-submit --type report_generation --target-date YYYY-MM-DD --request-id UNIQUE_ID --json
```

同一发布事件可重复 `--metric`，Worker 只按事件调用每个渠道一次，再由认证适配器拆分观测。
若官方直连需要精确公告位置，另传 `--source-url OFFICIAL_HTTPS_URL`。检索顺序固定为有效本地
证据、TuShare、认证官方直连、Tavily、Exa、受限 AI WebSearch；默认串行，P2 在 Exa 后
停止。Tavily/Exa 只返回并保存候选 URL，不保存完整响应，也不能产生 certified claim 或清除
原缺口。

付费渠道每个发布事件各最多一次；单运行 Tavily/Exa/AI 预算为 8/4/1，上海自然日预算为
16/8/2。有效负缓存和未到预计窗口不会调用外部渠道；只有短暂传输错误在同一级最多再试两
次。手动深搜必须恰好指定一个指标，尝试账本标记 `manual_budget_exemption`，定时任务不会
自动创建该命令。`pring-cycle runs --json` 和“运行状态”页显示逐级结果、失败分类、延迟、
运行/每日余量、负缓存命中与下一动作，不显示密钥、认证头或外部完整正文。

P0 缺失、陈旧、冲突或身份不符时运行进入 `action_required`，当前指针继续读取上一完整投影。
查看、取消与显式恢复：

```bash
pring-cycle runs --json
pring-cycle run-cancel --run-id RUN_ID --json
pring-cycle run-resume --run-id RUN_ID --request-id UNIQUE_RESUME_ID \
  --confirm-external-calls --json
```

恢复保留原 `system_as_of`、`report_cutoff`、目标业务日和已消耗预算；没有确认参数时拒绝恢复。
可选盘后计划默认关闭，启用后固定使用 `Asia/Shanghai`、18:30 开始与 21:00 P0 截止：

```bash
pring-cycle schedule --json
pring-cycle schedule --enable --json
pring-cycle schedule --disable --json
```

报告可以由 Worker 在投影后生成，也可显式运行。默认依次尝试已登录的 Codex CLI 与 Claude
Code CLI；两者失败时保存确定性简版。离线维护可明确禁用 AI：

```bash
pring-cycle report-generate --request-id UNIQUE_REPORT_ID --json
pring-cycle report-generate --request-id UNIQUE_REPORT_ID --deterministic-only --json
pring-cycle reports --json
pring-cycle report-read --report-id REPORT_ID --json
```

同日重新生成创建新版本，不覆盖历史。正文保留 30 天；事实骨架、引用、哈希和版本长期保留。

模型升级需要候选验收、与当前模型的认证区间交集回放，以及用户显式激活。回放命令自己从
证据仓库按各模型冻结的 definition version 计算核心与 PUBLIC-as-of 上下文输出、公式血缘、
质量、稳定性、差异和性能门，不接受调用者声明门禁结果。认证标签但无历史证据或公式输出时
回放仍失败。内部回退还要求首次
发布后少于 30 个交易日和一份明确交易日日历；它不会启动旧系统：

```bash
pring-cycle model-replay --model NEXT_MODEL --compared-with CURRENT_MODEL \
  --start YYYY-MM-DD --end YYYY-MM-DD --json
pring-cycle model-rollback --model NEXT_MODEL --as-of-date YYYY-MM-DD \
  --calendar /wsl/native/path/trading-days.txt --confirm --json
```

## 统一离线验收

以下命令在临时 SQLite 和制品目录中重复初始化，执行原子制品写入/登记/读回，启动正式
Web 与 Worker，执行健康探测和恶意 Origin 负例，最后停止两个进程：

```bash
PRING_CYCLE_VERIFY_ROOT="$(mktemp -d)"
pring-cycle verify --runtime-root "$PRING_CYCLE_VERIFY_ROOT" --json
pring-cycle verify --runtime-root "$PRING_CYCLE_VERIFY_ROOT" --json
```

两次应得到同一稳定文档，包含 `network_requests=0` 和 `processes=stopped`。验收只连接
`127.0.0.1`，不需要项目凭据或 AI CLI 登录。`pring-cycle test` 是同一验收入口的别名，
不会建立第二套测试编排路径。

V1 切换级验收使用 `pring-cycle acceptance --json`。它额外覆盖 35 个 `REG-*`、离线确定性
重放、八类故障注入、REST/首屏/命令/冷启动/回放时间以及 RSS 硬门，并把完整结果写入仓库外
内容寻址制品。进程探测始终在独立临时运行目录中启动 Web 与 Worker，不会处理正式目录中的
排队任务或读取其数据源凭据。任一门失败返回 `status=blocked`，没有强制绕过。

开发检查使用同一 WSL 原生虚拟环境：

```bash
UV_PROJECT_ENVIRONMENT="$PRING_CYCLE_DEV_ENV" uv run --no-editable pytest
UV_PROJECT_ENVIRONMENT="$PRING_CYCLE_DEV_ENV" uv run --no-editable mypy
UV_PROJECT_ENVIRONMENT="$PRING_CYCLE_DEV_ENV" uv run --no-editable ruff check src tests
```

`pring_cycle.domain` 提供框架无关的正式阶段、核心资产状态和证据/模型/投影/运行/报告身份
边界类型；导入它不会加载 Web、SQLite 或网络框架。

## 容量、升级失败与重新初始化

容量水位按可用空间计算：20 GiB 进入警告；10 GiB 限制非核心大任务；5 GiB 停止 Worker
写入但继续只读服务。规则检查与保留清理命令为：

```bash
pring-cycle capacity --free-bytes BYTES --json
pring-cycle cleanup --json
```

保留策略只删除未被引用、非权威的可重建对象；权威证据、模型、投影身份和报告事实骨架不按
容量直接删除。升级失败会把完整性状态记录为 `reinitialize_required`，系统不继续混用旧 schema。

重新初始化是破坏性恢复，没有 RPO/RTO 保证。先停止 Web/Worker，把 `doctor` 列出的整个运行
根目录移动到一个明确命名的隔离目录用于人工取证，再对一个新的 WSL 原生路径执行 `init`。
不要覆盖原目录，不要把旧 SQLite 复制进新运行目录，也不要把旧报告或阶段当成重建真值。

## 无备份风险

`doctor` 固定显示 `backup_mode=none`，运行数据 RPO 与 RTO 均为 `not_guaranteed`。V1 不创建
日常备份、升级前快照、Windows 副本或通用 `backup` 命令。GitHub 只恢复源码、迁移和静态
定义；SQLite、证据、报告、日志或密钥丢失后，只能尽力重新初始化，不能重建原来的系统点时
历史。
