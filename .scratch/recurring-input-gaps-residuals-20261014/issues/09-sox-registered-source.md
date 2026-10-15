Status: done
Category: enhancement
Type: task

# 09：SOX 接入取数路径

**What to build:** `NASDAQ_SOX_INDEX` 有真实取数路径，运行能持有 SOX 收盘值。先查 TuShare 是否有 SOX；没有则从可信网站中选能按日期取收盘值的来源。**不用 ETF 代理，不用近似指数。**选定来源后**先停下回报主 agent，由用户确认**，再实施：补写 ADR-0029 的 SOX 一条或新增 ADR；SOX 由“受限授权、无取数路径”改为“有注册来源、不检索”；仍是 P2、不进模型。落实[来源票 02](02-sox-source.md) 的生产部分；口径见[规格](../spec.md)“SOX”各条。

**Blocked by:** None (can start immediately)；实施段需用户确认来源

**Status:** done

- [x] TuShare 覆盖结论与可信网站候选（来源、按日期可取性、可信依据、样本应答）写入本票 Comments
- [x] 用户确认来源（主 agent 转达）
- [x] ADR 写明来源、可信依据与用户 2026-10-14 决定
- [x] 对应接缝（`refresh_quote_source` 或 TuShare 行情适配器）上的测试：按日期持有收盘值；解析失败记来源失败与原因码
- [x] SOX 期次按美股交易日；不进模型；目录不检索；受影响测试通过

## Comments

### 2026-10-14 调查段结论（实施子代理）

外部请求全部在 `/tmp/pring-external.lock` 下逐个发出（探测脚本内用 `fcntl.flock` 取同一把锁），每个来源只发 1–3 次，取到即停。探测时刻约 2026-10-14 08:00–08:17Z（北京 16:00–16:17），当时无真实运行。

#### 一、TuShare：取不到 SOX

- 文档 [`index_global`](https://tushare.pro/document/2?doc_id=211)（国际主要指数日线，6000 积分）列 21 个代码：XIN9、HSI、HKTECH、HKAH、DJI、SPX、IXIC、FTSE、FCHI、GDAXI、N225、KS11、AS51、SENSEX、IBOVESPA、RTS、TWII、CKLSE、SPTSX、CSX5P、RUT。**没有 SOX**，与 2026-09-17 的调查（`pring-data-acquisition-repair/survey-24-p2-publishers-20260917.md`）一致。
- 实测（本项目令牌）：
  - `index_global ts_code=SOX start_date=20261001 end_date=20261013` → `code 0`，**0 行**；
  - `index_global trade_date=20261009` → 19 行（N225、HSI、IXIC、DJI 等），没有 SOX。说明令牌有该接口权限，只是不覆盖 SOX。
- 据文档（未实测），TuShare 其他指数接口 `index_basic`／`index_daily` 覆盖中证、上交所、深交所、申万、MSCI 等，不含美股行业指数；`us_daily` 是美股个股。都不是 SOX。**结论：TuShare 这条路不通，转可信网站。**

#### 二、可信网站候选

两个候选数值逐日一致（FRED 四舍五入到 2 位小数），均为 SOX 本身（价格指数），不是 ETF 或总回报版本。

| 候选 | 按日期取收盘值 | 格式 | 请求头／登录 | 使用条款 | 可信依据 |
|---|---|---|---|---|---|
| **A. FRED `NASDAQSOX`**（圣路易斯联储） | 能：`observation_start/end` 或 `cosd/coed`，自 2004-09-02 起 | API：JSON；网页下载：CSV `observation_date,NASDAQSOX` | 普通 UA 即可；**正式 API 需免费 API key**（用户注册） | 带版权声明的第三方序列可作**个人用途**；免费 API 明文允许做应用；只禁止“扰乱性”的批量抓取 | 美联储系统官方数据平台；序列注明 `Source: Nasdaq, Inc.`、`Release: Nasdaq Daily Index Data`、`Copyright © 2025, NASDAQ, Inc.`，即指数管理人授权的转载 |
| **B. Nasdaq Global Indexes 官网**（`indexes.nasdaqomx.com`，指数管理人） | 能：`startDate/endDate` | `POST /Index/HistoryData` 返回 JSON；`GET /Index/ExportHistory/SOX?...` 返回 xlsx（日期为 Excel 序号） | 普通 UA 即可，**无需浏览器头**；站点挂 Incapsula 防护，本次未被拦 | `nasdaq.com/legal`：仅许“个人、非商业使用”，但另有一条“不得以任何自动或手动程序从本服务抓取数据”；接口无公开文档 | 指数管理人本人发布，最权威，全精度 |

**样本应答摘录**

A. FRED 网页下载（无 key，`GET https://fred.stlouisfed.org/graph/fredgraph.csv?id=NASDAQSOX&cosd=2026-09-28&coed=2026-10-13`，200，`application/csv`）：

```
observation_date,NASDAQSOX
2026-10-08,12623.71
2026-10-09,12572.42
2026-10-12,12236.79
2026-10-13,12208.79
```

序列页：`Updated: Oct 13, 2026 10:43 PM CDT  Next Release Date: Oct 14, 2026`，即北京时间次日约 11:43 才有当晚收盘值。

A'. FRED 正式 API 不带 key（`GET https://api.stlouisfed.org/fred/series/observations?series_id=NASDAQSOX&file_type=json`）→ 400：`{"error_code":400,"error_message":"Bad Request.  Variable api_key is not set. ..."}`。

B. Nasdaq 官网（`POST https://indexes.nasdaqomx.com/Index/HistoryData`，表单 `id=SOX&startDate=2026-10-01T00:00:00.000&endDate=2026-10-13T00:00:00.000&timeOfDay=EOD`，200，`application/json`）：

```
{"sEcho":1,"iTotalRecords":9,"iTotalDisplayRecords":9,"aaData":[{"TimeStamp":"\/Date(1791864000000)\/", ..., "Close":null,"High":12217.20942243827,"Low":11861.27836184291,"NetChange":-27.99366400668, ..., "Value":12208.79468690783, ...}
```

收盘值在 `Value` 字段（`Close` 为 null）。xlsx 导出列为 `Trade Date, Index Value, Net Change, High, Low`，2026-10-01…10-13 共 9 行，与 JSON 一致。

**已排除**（只记一句）：

- Stooq `^sox` CSV：返回 JavaScript 工作量证明挑战页，需浏览器执行脚本；
- WSJ 历史价格 CSV：401（DataDome 反爬，要求启用 JS）；
- Yahoo `query1.finance.yahoo.com/v8/finance/chart/^SOX`：可取，值一致，但属未公开接口，条款禁止自动抓取，也不是发布方，不算“可信网站发布”；
- 东方财富 `secid=100.SOX`：`data:null`，没有该代码；
- Nasdaq Data Link（原 Quandl）`NASDAQOMX/SOX`：Incapsula 403，且需账户 key。

#### 三、推荐与风险

**推荐 A：FRED 正式 API 取 `NASDAQSOX`。**用户需到 FRED 免费注册一个 API key，写入 `secrets.env`（新增 `FRED_API_KEY`）。理由：

1. 美联储官方平台转载指数管理人 Nasdaq 授权的数据，来源能追溯到 Nasdaq，可信度足够；
2. 接口有公开文档、免费，条款明文允许个人使用带版权的序列、允许用免费 API 写程序，正好解决 ADR-0029 当初“无公开文档、合规不明”的顾虑；
3. 前提与 ADR-0029 对 USDCNY 16:30 的处理相同：本机个人使用、不对外分发。

A 的风险：

- **时效**：FRED 约在美东当晚 22:43（北京次日约 11:43）才更新。09:30 运行时最新一期是前一美股交易日的收盘值。现行规则 `lag=1`、发布时刻 06:00，会把目标日当晚那期算作“已发布”，持有前一期就记“落后 1 期”。实施时要按实测把 SOX 的发布时刻登记为北京约 12:00（与 VIX 按实测登记的做法一致）。这样 09:30 运行持有前一期即为现行；
- **只有 2 位小数**（官网全精度），作为 P2 参考指标足够；
- **下架风险**：FRED 2022 年曾应版权方要求删掉 IBA 金价序列。若 Nasdaq 撤回授权，来源将失效，需改用 B；
- **需用户动作**：注册 key。在 key 到位前，可退而用 FRED 网页下载 CSV（无 key，每天 1 次，负载极低）。但 FRED FAQ 有一句“不要做数据挖掘、抓取或提取”，正式条款只禁止扰乱性抓取，因此不推荐长期使用。

**备选 B：Nasdaq Global Indexes 官网 `HistoryData`。**指数管理人本人发布，全精度，无需 key，可能当晚就有数据（本次未实测发布时刻）。风险：

- `nasdaq.com/legal` 有“不得以任何自动或手动程序抓取数据”一条，与 ADR-0029 当初顾虑的合规问题同类，只是这次不需要浏览器头；
- 接口无公开文档，Incapsula 随时可能改为拦截；
- 选 B 等于推翻 ADR-0029“取得授权或正式接口后再登记”的前提，ADR 中需写明用户接受这一风险。

**待用户确认**：选 A（FRED API，需注册 key）还是 B（Nasdaq 官网）；若选 A，key 到位前是否允许先用 FRED 网页下载 CSV 过渡。确认后按 `tdd` 在 `refresh_quote_source` 接缝实施并补 ADR。

调查段的探测脚本与原始应答只保存在会话临时目录，没有入库。

### 2026-10-14 用户决定（主 agent 转达）

选 B：Nasdaq 指数官网 `HistoryData`，不用 FRED。ADR 写明接口无公开文档、站点有反爬、`nasdaq.com/legal` 禁止自动抓取；用户接受这一风险，前提为本机个人研究、不对外分发（同 USDCNY 先例），前提变化时回到受限授权。

### 2026-10-14 实施

**改动**

- `src/pring_cycle/quote_sources.py`：
  - 新增 `parse_nasdaq_index_history`：读 `aaData` 每行的 `Value`，以 `TimeStamp`（纽约零点）定美股交易日，全精度保存；
  - 整份拒收的情形：结构不符、日期不是纽约零点或越界、日期重复、值不是正数，原因码 `nasdaq_index_*`；
  - 新增注册来源 `NASDAQ_SOX`（POST 表单 `id=SOX`、窗口起止日、`timeOfDay=EOD`；提供方 Nasdaq Global Indexes；渠道 `nasdaq_index_official`；回执接口名 `official_http_post`），加入 `QUOTE_SOURCES`，Worker 每轮照 VIX 一样取一次；
  - `QuoteSource` 加可选 `form`（带表单即 POST）。
- 审查修复：HTTP 失败不再在 `_fetch` 里转换，而是交给回执层保存应答页（如反爬 403 页）作为原件，再在 `refresh_quote_source` 转为原有的 `quote_source_http_<码>` 记录并抛出。三个行情来源都改为这样，对外的原因码、异常类型和结果不变。
- `freshness.py`：SOX 规则改为 `nasdaq:index_history`，去掉 `restricted_license`；美股日历、滞后 1、06:00 不变。缺口清单不再列“授权缺失”。
- 目录定义未变（单位、频率、维度、来源代码），不升目录版本；不检索、不进模型。
- 文档：
  - 新增 [ADR-0042](../../../docs/adr/0042-sox-from-nasdaq-index-site.md)，ADR-0029 末尾加指向；
  - `GLOSSARY.md`“受限授权 P2”改写为“目前无指标，USDCNY、SOX 为用户接受风险后的例外”；
  - `docs/development/local-runtime.md` 的 SOX 段同步改写，合并集成分支时与票 08 的同段冲突，已合并两边内容。
- 测试：
  - `tests/adapters/test_quote_sources.py` 用真实应答夹具（`tests/fixtures/quote_sources/nasdaq-sox-history-20261013.json`）测解析与 9 种拒收；
  - 新增 `tests/integration/test_sox_quote_source.py`，在 `refresh_quote_source` 接缝测四件事：按日期持有、表单只请求 SOX 本身、解析失败记来源失败与原因码、403 保留状态码与应答原件；
  - `tests/integration/test_gap_source_repairs.py` 原“SOX 为授权缺口”改为“完整运行从 Nasdaq 持有 SOX、不在缺口清单、不检索”。

**验证**（venv `dev-venv-rig09`）

- 合入集成分支 `0dc7269` 后：受影响测试与两例冒烟 174 passed（424s）；重型 `test_worker_registered_catalog.py`＋`test_core_carry_forward.py` 在 heavy 锁下 4 passed（305s）；
- `ruff check`、`ruff format --check` 通过；`mypy` 改动的源文件无问题，测试文件只有改动前就有的报错；
- 真实请求一次（外部锁下）：用实装的 `_fetch`＋解析器取 10-05..10-13，得 7 个交易日全精度值，与调查样本一致。

**审查**（Codex 两轴，只读）

- 标准轴：无阻断，3 条非阻断全部采纳——越界时间戳归入 `nasdaq_index_date_invalid`；POST 来源回执记 `official_http_post`；GLOSSARY 写明例外。
- 规格轴：1 条阻断（HTTP 失败未保存应答原件），已修复并补测试。
- 定向复审：通过，阻断：无。复审建议在正例里断言回执接口名，已补上。

**已知残余**

- Nasdaq 的实际发布时刻未测。现按北京 06:00 视为发布，09:30 的计划运行离美股收盘已有 5 小时以上；收尾验收（票 13）会看 SOX 持有的期次。
- 体检的 SOX 口径（`tools/quality` 的 `NO_PATH` 等）属于票 12，本票未改。
