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

### 源码改动后必须重装

因为装进虚拟环境的是副本而不是链接，改源码**不会**让虚拟环境里的 `pring_cycle` 跟着变。
而 `uv sync` 只按版本号判断是否需要装：`pyproject.toml` 里的版本一直是 `0.1.0`，所以它会
报告 `Audited N packages` 并且什么都不装，即使源码已经改了几十个文件。

于是虚拟环境可以无限期地落后于源码，**没有任何提示**。测试仍然会跑，只是跑的是旧代码：
删掉的模块还在、新增的模块不存在，失败表现为 `ImportError` 或 `ModuleNotFoundError`，看起来
像代码坏了，实际上是环境旧了。一次全套要跑几十分钟，这种失败要到最后才暴露。

拉取、合并、切分支或改动 `src/` 之后，重装项目自身：

```bash
UV_PROJECT_ENVIRONMENT="$PRING_CYCLE_DEV_ENV" \
  uv sync --extra dev --no-editable --reinstall-package pring-cycle
```

`--reinstall-package pring-cycle` 只重装项目本身，依赖仍走锁文件和缓存，实测约 1 秒，
可以无条件执行。`tools/check.py` 开跑前会逐个比对包内全部文件（含子包与资源文件）的
内容，缺少、多出或内容不同都会列出并拒绝运行；只比文件名或个数不够——旧副本通常模块齐全，
只是代码落后（2026-09-25 验收中仓库内旧 `.venv` 有 7 个模块内容与 `src/` 不同，按文件名
比对未报）。环境不一致时，任何测试结果都不可信。

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
`pring-cycle runs --json`。

## 模型、证据与运行操作

初始化登记内置的 `model-v0001`–`model-v0003`，不会隐式激活。模型版本只是版本号加生效指针
（ADR-0022）：`model-register` 登记一份新的版本清单，`model-activate --confirm` 把指针移到该
版本。之后的运行使用它并把版本号记入加工批次；已发布的汇总不重算。回退就是再次激活旧版本，
没有校准、回放或验收步骤。

```bash
pring-cycle models --json
pring-cycle core-history-refresh \
  --start 2026-01-01 --end 2026-08-19 \
  --definition-version metric-catalog-v0001 --json
pring-cycle model-register --manifest /wsl/native/path/model.json --json
pring-cycle model-activate --model MODEL_VERSION --confirm --json
```

证据 JSON 必须包含 metric identity、统计期、单位、来源、公开/抓取/系统可用时间与质量状态。写入及点时查询示例：

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

V1 的首条 P1 注册官方链路是中国货币网 LPR 公告。目录身份固定为
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

显式摄取会把公告作为内容寻址制品保存，并以一个发布事件原子写入两条
source claim；同一正文重复获取保持幂等，后续修订只能从实际抓取修订的时点起进入
`public_as_of`，不会回填到原公告时点。普通 `evidence-ingest` 不能冒充这条注册来源：

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

EIA Brent `RBRTE` 与 WTI `RWTC` 使用官方 API v2
`/v2/petroleum/pri/spt/data/`，固定日频、`Dollars per Barrel` 与两条 series identity。
离线 JSON 契约检查为：

```bash
pring-cycle eia-contract --input /wsl/native/path/eia-response.json \
  --start YYYY-MM-DD --end YYYY-MM-DD --json
```

完整运行只从仓库外 `secrets.env` 读取 `EIA_API_KEY`，在配置该 key 时独立刷新 EIA；没有
TuShare token 也不会阻断 EIA。两条 P2 原油绝不替换 NHII 商品核心。

公开日历史 HTML 可通过 `eia-html-refresh` 显式取得候选，无需 API key。以下示例在独立候选
运行库中执行，不激活模型；两项各请求一次官方完整日表，再选取指定窗口：

```bash
pring-cycle init --runtime-root /home/tywin/.cache/pring-cycle/eia-html-candidate --json
pring-cycle eia-html-refresh --runtime-root /home/tywin/.cache/pring-cycle/eia-html-candidate \
  --series RBRTE --start 2026-08-24 --end 2026-09-04 --definition-version metric-catalog-v0002 --json
pring-cycle eia-html-refresh --runtime-root /home/tywin/.cache/pring-cycle/eia-html-candidate \
  --series RWTC --start 2026-08-24 --end 2026-09-04 --definition-version metric-catalog-v0002 --json
```

结果分别给出数值条数、无数值日期格和 acquisition ID；空窗口返回 `missing_values` 及具体
原因。原件、响应身份、解析版本和批次日期单独保留；日期格不左移，合法负值和数值零不当作
缺失。公开可用时间按时效登记表推算的发布时点与首次取得时间取较早者（ADR-0021），SYSTEM
按本次校验完成时间记录。完整 Worker 在配置 key 时使用 API，未配置时改取这张 HTML 历史表。字段/时间依据见[接入契约](../../.scratch/pring-data-acquisition-repair/eia-html-contract.md)。

美国财政部名义曲线可通过 `treasury-csv-refresh` 显式取得同日2Y、10Y候选，无需账户。
每次读取一个来源年度CSV，再保存所选窗口；跨年窗口应分年调用。以下在独立候选库执行：

```bash
pring-cycle init --runtime-root /home/tywin/.cache/pring-cycle/treasury-csv-candidate --json
pring-cycle treasury-csv-refresh --runtime-root /home/tywin/.cache/pring-cycle/treasury-csv-candidate \
  --start 2026-08-24 --end 2026-09-04 --definition-version metric-catalog-v0002 --json
```

数值以百分数保存，`4.37`代表4.37%；零值与缺失分开，N/A或空格不生成数值声明。
返回数值条数、缺值格数和请求身份；保存原件、各指标最新源有值日期及真实SYSTEM时间。
新快照缺值时，旧声明仍保留原取得时间，本次缺值回执另记，不能计为本次新取得值。
公开可用时间按登记发布时点与首次取得时间取较早者；Worker现有TuShare渠道仍按配置运行。
通常18:00美东时间前可用是发布预期，不能填成实际发布时间。字段/时间依据见
[官方契约](../../.scratch/pring-data-acquisition-repair/treasury-followup.md)。

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

同一发布事件可重复 `--metric`，Worker 只按事件调用每个渠道一次，再由登记解析器拆分观测。
若官方直连需要精确公告位置，另传 `--source-url OFFICIAL_HTTPS_URL`。检索降级链固定为：有效本地
证据、TuShare 数据接口、TuShare 资讯、注册官方直连、Tavily（Exa 只在 Tavily 返回月度限额耗尽
402/432/433 时顶替，缓存到下月 1 日）、AI WebSearch，默认串行，前一级取到完整模型输入即止；
TuShare（数据接口或资讯）取到值后不再去官方或媒体页面。缺失或落后的项只有在时效登记表（或发布
预告）表明本期已发布后才检索；完整运行检索各指标最新一个已发布期（ADR-0023、0026），以及模型回看声明要求的前期（确认度模型按"成员＋读法＋发布期"声明，最远 13 个月、季度至 t−4，ADR-0035、0037）。

**外部接口限频与并发。** 各外部接口一律串行调用，不并发：检索降级链逐级、逐缺口进行，资讯逐页
翻取，Worker 同一时刻只处理一个运行。TuShare 按账户计限额，真实运行、手工探测与取测试样本共用同一额度：
`major_news` 每天 40 次（超限应答 `40203 频率超限`，记 `tushare_rate_limited`；2026-09-24 用满后 9-25 00:04 仍超限，并非零点重置，疑为滚动 24 小时，超限后不要反复试探），首次
或长停后的一次拉取约 20 页，同一目标日重跑再耗约 20 次。因此不同时发起两个真实运行，也不在真实运行
进行中另行调用 TuShare；手工探测一次一个请求，取到即停，不写循环批量调用。

**只搜可检索缺口。** 指标属于检索登记处（`retrieval_registry.py`）的某个家族（国家统计局、人民
银行各家族、LPR、中证核心）才进入搜索级；由 TuShare 计算的派生指标、NHII 等没有网页来源，TuShare
重试后直接列入缺口清单，并带“无网页补缺渠道”属性。

**P2 行情官方文件（ADR-0029）。** VIX 每轮直接取 Cboe 日历史 CSV
（`cdn-api.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv`；原 `cdn.cboe.com` 自 2026-09-26 起 307 跳转到此），USDCNY 16:30 直接取中国货币网
日内走势文件（`rfx-sp-iday-chrt.json` 的 `closeSpotPrice`，须与快照里 16:30 那一点一致；最新价是 03:00
夜盘收盘，不取），二者都不检索；文件结构不符记“来源失败”并附原因码。USDCNY 16:30 持有前一交易日即算
现行；Cboe 文件更新不逐日稳定，VIX 宽限 3 个交易日。SOX 为受限授权，缺口清单列“授权缺失”，不检索。

**郑商所仓单日报（ADR-0032）。** TA（PTA）与 CF（郑棉）的仓单每轮直接取郑商所官网仓单日报
（`www.czce.com.cn/cn/DFSStaticFiles/Future/<年>/<日期>/FutureDataWhsheet.txt`），TuShare `fut_wsr` 只取另外
6 个品种。首轮补齐 120 个交易日里未持有的日子，约 120 个文件；之后每轮只取新的一天。一天只请求一次，
请求串行、相隔约 1 秒。某天没有文件只缺那一天；完全连不上时本轮停止，剩下的留到下一轮。块或表头不符按
品种逐日拒收并附原因码，不检索。

**缺口清单的分类。** 按“为什么缺”分：取数失败（注册来源没应答）、入库校验失败（取到了但被结构校验
或登记契约拒收，附原因码）、检索未通过（附候选网址与原因）、授权缺失、缺失；时效类为时效缺口、未配置
时效。“无网页补缺渠道”是缺口的属性，不是分类。

**TuShare 资讯。** 每次完整运行在检索开始前统一拉取一次 `major_news`（从此前成功完整运行中最近一次
完整拉取读到的终点接着读，至多回看 7 天，首次取 7 天，以目标交易日结束封顶；有失败页的拉取不算读过，
同一目标日重跑也从前一段接着读；每页 400 条上限，按时间倒推翻页，一天约 3 页；接口每天限 40 次，
超限记 `tushare_rate_limited`），整批原文存为本批次取数记录；拉取失败只记在该记录上，运行照常，
下一轮重读该窗口。各缺口按家族登记的
资讯解析规则（`news_rules.py`）在本地筛选：只认发布稿句式，句中或前文须写明应有期，发布时间不晚
于截止时点。原件 3 天后在成功运行末尾的留存清理中删除，被采用的值以命中原话追溯。降准不按缺口检索：每轮拉取后在本轮资讯里按降准句式监测，按句中写明的生效日记期、以稿件发布时间为
公开时间，命中即记新事件；未命中则沿用已持有的最近一次（现行基准，生效至变更），不列缺失、不走后续渠道
（ADR-0028）。公开市场操作利率每轮随操作量检索最新交易日公告，未写利率时沿用已持有值。

**搜索调用。** 查询按家族发布稿标题模板生成（如“2026年8月份居民消费价格”），不再含指标 ID 与来源
编码；Tavily/Exa 请求带域名限定：该家族官方主机加媒体白名单（国内财联社、新华网、人民网、中国政府
网、中国证券报、上海证券报、证券时报、第一财经、财新、华尔街见闻、新浪财经、东方财富；国外路透、
彭博、CNBC、MarketWatch、华尔街日报、金融时报、雅虎财经、Investing.com；不含 Wind），Exa 同时请求
正文。检索记录保存实际查询文字与域名清单。

**候选验证。** 官方主机上的页面仍由登记解析器重抓原文严格解析：须解析出应有统计期与不晚于截止
时点的发布日期，搜索摘要中的数与解析值差 10–1000 倍（疑似小数点错位）时不采纳；国家统计局列表
页按发布稿标题选链，本页未见时向后翻页（至多 10 页，历史期不翻）。白名单媒体页面对 P1/P2 按资讯
解析规则取值，规则未命中记“解析规则未命中”；P0 不采用资讯、媒体与 AI 的值。P2 宽松路径（登记主机或媒体
白名单上采用搜索摘要中的值，须写出应有期日期、恰有一个取值）目前没有登记家族：原先的 USDCNY 16:30、
VIX、SOX 已按 ADR-0029 改走官方文件或列为授权缺失。被采用
的资讯、媒体与 AI 值在明细旁保存命中原话、标题、主语分句（同段离数值最近、带主语的分句）、来源、
发布时间与正文哈希，随明细 120 日留存；标题或主语分句点出地方（且未点出全国）的值不取，读取时也按当前规则重判。
不通过的候选不入库，缺口清单单列“检索未通过”，每项最多列 3 个网址及逐网址原因。

**AI WebSearch。** 降级链最后一级由 Codex CLI 联网搜索（`codex --search exec`）执行，失败或超时改用
Claude Code（只开放 `WebSearch` 工具），均按固定结构返回候选（网址、原话、数值、统计期、发布日期）；
每个候选依次校验白名单主机、家族规则从原话取出的值与返回数值一致、统计期、发布日期，再按网址重取
页面（每个页面每次回答只取一次，串行，记入检索账本），按媒体页面规则连同标题与主语分句读出同一成员的
同一数值后才补齐缺口；页面取不到（含需要 JavaScript、跳转出白名单、超时）或对不上即拒收（票 26）。
此前入库的 AI 声明须用 `search_evidence.restore_suspect_pages` 手动重取一次补上下文，补上前不参与选值。
每缺口每次运行至多一次，单次 300 秒，每次运行合计 60 分钟，用尽后记“AI 时长已用尽”；只依赖 CLI
自身登录，不使用任何模型 API key。只对规则覆盖该家族全部必需成员的缺口调用（否则答案也补不齐）。
默认开启；可在运行配置 `config.toml` 中关闭，测试套件以环境变量 `PRING_CYCLE_AI_WEBSEARCH=off` 关闭：

```toml
[retrieval]
ai_websearch = false
```

预算只按每次运行计：Tavily 16、Exa 8，不设每日上限；AI WebSearch 不计次。同一运行内不重复结果
未知的请求；已完成的请求只受负缓存约束：认证与限额错误（401、402、429、432、433）按来源主机拦截，官方页的 403 只拦同一页面（一次 403 不再停掉整个站点）。只有短暂传输错误在同一级最多再试两次。手动深搜必须恰好
指定一个指标，尝试账本标记 `manual_budget_exemption`，可重复 Tavily/Exa，定时任务不会自动创建
该命令。`pring-cycle runs --json` 和“运行状态”页显示逐级结果、失败分类、延迟、运行余量、负缓存
命中与下一动作，不显示密钥、认证头或外部完整正文。

三核心缺失时先补全：TuShare 重试一次，000985/000012 再取中证官网（NHII 没有可解析的官方页面），
之后进入检索。仍缺时，只落后一个交易日则“核心沿用上一期”，照常产出正式阶段并醒目标注；落后
两期及以上、窗口内缺日或冲突则正式阶段为空（`core_data_pending`），其余投影与报告照常发布
（票 21、22）。P0 未登记时效时运行进入 `action_required`，当前指针继续读取上一完整投影。
查看、取消与显式恢复：

```bash
pring-cycle runs --json
pring-cycle run-cancel --run-id RUN_ID --json
pring-cycle run-resume --run-id RUN_ID --request-id UNIQUE_RESUME_ID \
  --confirm-external-calls --json
```

恢复保留原 `system_as_of`、`report_cutoff`、目标业务日和已消耗预算；没有确认参数时拒绝恢复。
可选盘后计划默认关闭，启用后固定使用 `Asia/Shanghai`、18:30 开始与 21:00 P0 截止。
到点时 Worker 先看已存上交所日历是否写明当天开市：写明开市才提交，写明休市不提交，均不发请求；当天
未被覆盖时先向 TuShare 补取一次 `trade_cal`（当天往前 14 天至当天），确认开市才提交。补取失败则暂缓、写
`worker.jsonl` 事件 `scheduled_run_deferred`，每 10 分钟重试一次，到 21:00 截止或跨日为止；暂缓
只记在运行中的 Worker 内存里，重启不补（体检票 14）：

```bash
pring-cycle schedule --json
pring-cycle schedule --enable --json
pring-cycle schedule --disable --json
```

报告可以由 Worker 在投影后生成，也可显式运行。默认依次尝试已登录的 Codex CLI 与 Claude
Code CLI（单次 300 秒）；两者失败时保存确定性简版。交给 AI 的是“报告输入”（ADR-0027）：正式阶段
或为空的原因、三核心状态与变化、宏观（政策、信用、过热、价格）与库存结论、核心沿用与缺口概况，
每项只附结果值、数据来源名称和是否有异常，不含证据编号、逐条证据与观测序列。报告段落不引用证据；
生成后只校验结构合规与结论未被改写（正式阶段、三核心状态、宏观与库存结论须与输入一致），并保留
禁用词检查。离线维护可明确禁用 AI：

```bash
pring-cycle report-generate --request-id UNIQUE_REPORT_ID --json
pring-cycle report-generate --request-id UNIQUE_REPORT_ID --deterministic-only --json
pring-cycle reports --json
pring-cycle report-read --report-id REPORT_ID --json
```

同日重新生成创建新版本，不覆盖历史。正文保留 30 天；事实骨架、引用、哈希和版本长期保留。

## WSL 虚拟磁盘回收

WSL 内删除不会让 Windows 侧的 C 盘立刻变大——虚拟磁盘只增不减。需要在 Windows 侧执行
`wsl --shutdown` 后压缩 `ext4.vhdx`（`Optimize-VHD -Mode Full`，或 `diskpart` 的
`compact vdisk`）才会真正归还。

压缩脚本若要自己写，注意两处编码：PowerShell 5.1 按系统 ANSI 读 `.ps1`，diskpart 也按
系统 ANSI 读它的脚本文件。路径含非 ASCII 字符（例如中文用户名）时，UTF-8 会让两者分别
报"字符串缺少终止符"和"系统找不到指定的路径"。脚本正文写成纯 ASCII，路径由
`$env:LOCALAPPDATA` 拼出，diskpart 脚本用 `[Text.Encoding]::Default` 写入。

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
