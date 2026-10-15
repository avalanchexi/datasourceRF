---
status: accepted
---

# SOX 改从 Nasdaq 指数官网取数，用户接受未公开接口的风险

2026-10-14 用户决定（残余批次[票 02](../../.scratch/recurring-input-gaps-residuals-20261014/issues/02-sox-source.md)、[票 09](../../.scratch/recurring-input-gaps-residuals-20261014/issues/09-sox-registered-source.md)）。按 [ADR-0029](0029-p2-quote-sources-and-warrant-members.md)，`NASDAQ_SOX_INDEX` 原为受限授权 P2：没有取数路径，在体检“目录全部”口径下每次都计 1 项真正缺失，把真正的新缺失淹没了。用户要求这一口径也归零，并给出取舍顺序：先用 TuShare；TuShare 取不到时，以可信网站发布的数值为标准口径；不用 ETF 代理，也不用任何近似指数。

## 调查（2026-10-14，外部请求串行）

- **TuShare**：`index_global` 只覆盖 21 个国际指数，其中没有 SOX。用本项目令牌实测，`ts_code=SOX` 返回 0 行，`trade_date=20261009` 返回 19 个指数，也没有 SOX。
- **FRED `NASDAQSOX`**：转载 Nasdaq 授权的数据，有公开文档的免费 API（需注册 key）。不足：北京次日约 11:43 才更新，只保留 2 位小数，且 FRED 曾应版权方要求下架第三方序列。
- **Nasdaq Global Indexes 官网**（`indexes.nasdaqomx.com`，SOX 的指数管理人）：历史页脚本 POST `/Index/HistoryData`，返回 JSON 表格；页面另有“Download”按钮，导出同一份数据的 xlsx。普通 User-Agent 即可取到，不需要浏览器请求头；数值为全精度，与 FRED 逐日一致。
- 已排除：Stooq（浏览器工作量证明挑战）、WSJ（DataDome 401）、Yahoo（非发布方的未公开接口）、东方财富（没有该代码）、Nasdaq Data Link（Incapsula 403，需 key）。

## 决定

SOX 以 **Nasdaq Global Indexes 官网的历史表**为注册来源。它是指数管理人自己发布的数值，可信度最高。

- 每轮运行在行情来源刷新里取一次，与 VIX、16:30 收盘价同在 `refresh_quote_source` 这一接缝：POST `https://indexes.nasdaqomx.com/Index/HistoryData`，表单为 `id=SOX`、窗口起止日（`YYYY-MM-DDT00:00:00.000`）、`timeOfDay=EOD`；回执的提供方为“Nasdaq Global Indexes”，接口名为 `official_http_post`，渠道为 `nasdaq_index_official`。
- 取每行的 `Value`（页面“Index Value”一栏；`Close` 字段为空），按行的 `TimeStamp`（纽约当日零点）定美股交易日，全精度保存，单位为 `index_points`。
- 应答不是这张表（如反爬拦截页、缺 `aaData`）、日期不是纽约零点、日期重复、值不是正数，整份拒收，记来源失败并附原因码（`nasdaq_index_*`）。HTTP 失败照旧以状态码为原因码（`quote_source_http_<码>`），并把应答页（如反爬拦截页）作为回执原件保存。三个行情来源都按这一做法处理。
- 时效规则：美股交易日历，滞后 1 个交易日、北京时间 06:00 视为发布，宽限取默认值。实际发布时刻未测；09:30 的计划运行离美股收盘已有 5 小时以上。
- 不检索、不进模型、仍是 P2。目录定义（单位、频率、维度、来源代码）不变，不升目录版本。

## 用户接受的风险

- 该接口**没有公开文档**，是历史页自身脚本调用的数据接口；字段或地址随时可能改变，变了就记来源失败。
- 站点挂有 **Incapsula 反爬**，本次未被拦截，但随时可能改为拦截。
- `nasdaq.com/legal` 只授予“个人、非商业使用”的许可，另有一条“不得以任何自动或手动程序从本服务抓取数据”。自动取数与这一条有冲突。

用户接受这一风险。前提与 ADR-0029 对 USDCNY 16:30 的处理相同：本机个人研究使用，每轮只发一次请求，只取页面已公布的数值，不对外分发。**前提变化**时（对外分发、Nasdaq 明确拒绝或封禁、改为商用），SOX 回到受限授权，照 ADR-0029 列为透明缺口，冻结规则 `restricted_license` 保留备用。

## 考虑过的方案

- **FRED API**（调查时的推荐）：条款明文允许个人使用带版权的序列，也允许用 API 写程序，合规风险最低。但它是二手转载，北京时间中午前拿不到前一晚的值，只有 2 位小数，还需注册 key。用户选择数值源头。
- **维持受限授权**：“目录全部”口径永远少不了这 1 项缺失，与本批“真正缺失归零”的目标冲突。
- **ETF（SOXX 等）或近似指数代理**：用户明确不用，指标定义不能被悄悄替换。

本 ADR 部分取代 ADR-0029 中 SOX 一条。
