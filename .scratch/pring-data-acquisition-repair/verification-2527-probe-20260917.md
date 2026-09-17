# 票25 + 票27 合批探测：结果（2026-09-17）

按[请求前冻结的参数](plan-2527-probe-20260917.md)执行。**10 次请求，全部 HTTP 200，未触发任何停止条件**（预算 16 次）。原件按内容寻址存于 [evidence-2527-20260917/](evidence-2527-20260917/)，逐次记录见 [verification-2527-probe-20260917.json](verification-2527-probe-20260917.json)。

## 取得的（可直接用于实现）

| 指标 | URL | 字节 | 依据 |
|---|---|---|---|
| `CN_PPI`、`CN_PMI_ACTIVITY`、`CN_PMI_INVENTORY`、`CN_PMI_PRICES` | `https://www.stats.gov.cn/sj/zxfb/` | 73,001 | 页面实测含"居民消费价格""工业生产者""采购经理"。**该 URL 本就是同族 `CN_CORE_CPI` 在用的**，不是新拼的 |
| `CN_CPI_HEADLINE` | 同上 | — | **无需探测**：它与 `CN_CORE_CPI` 同属 `nbs_core_cpi` 族、同一份文档，后者已配该 URL，只是这一项当初没配上 |
| `CBOE_VIX_INDEX` | `https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv` | 472,717 | 确认是 CSV，表头 `DATE,OPEN,HIGH,LOW,CLOSE`，**覆盖到 2026-09-16**（探测当日前一交易日）。官方、免费、可直接程序化取用 |

## 未取得的（如实记，不伪造）

| 指标 | 探过什么 | 结果 |
|---|---|---|
| `CN_M1_M2` | `pbc.gov.cn/diaochatongjisi/116219/116319/index.html`（`CN_SF_TOTAL` 在用的页）与 `/diaochatongjisi/116219/index.html`（从前一页抓到的真实链接） | 两页均 200，**都不含"货币供应量"或"M2"**。货币供应量的实际发布页未找到，**回退路径对本项仍不通** |
| `CN_GDP` | `stats.gov.cn/sj/zxfb/` 与 `/sj/zxfbhjd/`（`CN_INDUSTRIAL_VA` 在用的页） | 两页均 200，**都不含"国内生产总值"或"GDP"**。GDP 为季度指标，其发布页未找到，**回退路径对本项仍不通** |

两项都**没有再猜路径**——票13 那轮我编造 URL 吃了两个 404，这次改从已抓页面里取真实链接，取不到就停在这里。

## 取用方式未确认的（票27）

| 指标 | 探测结果 | 还差什么 |
|---|---|---|
| `NASDAQ_SOX_INDEX` | `indexes.nasdaq.com/Index/History/SOX` 返回 200 / 69,165 字节，标题 `History for SOX` | 页面可达，但**历史数值是否由服务端渲染、能否稳定解析未确认**。需要进一步核实才能写适配器 |
| USD/CNH（TMA 定盘） | `tma.org.hk/en_market_info.aspx` 返回 200 / 82,389 字节，标题 `Market Data - TMA`，含 CNH/Fixing 迹象 10 处 | 同上：可达，取用方式与具体定盘序列的入口未确认 |

## 一处口径纠正

`CN_USDCNY_CLOSE_1630` 探的是 `chinamoney.com.cn/chinese/bkccpr/`，返回 200、标题为"人民币汇率**中间价**"。**中间价不是 16:30 收盘价**——这个页面对应的是 `CN_USDCNY_CENTRAL_PARITY`，不是本指标。

该指标名为 `CLOSE_1630`，要的是收盘价。**本次没有取得它的发布入口**，记为未取得。这类"看着像、其实是另一个口径"的混淆，正是票13 最初栽过的地方。

## 对两票的影响

**票25**：7 项缺 URL 的指标中，**5 项可立即补上**（CPI 表头、PPI、PMI×3），**2 项仍不通**（M1/M2、GDP）。后者的回退路径保持不通，并在票上记明原因，不以"探过了"冒充"能用了"。

**票27**：VIX 可立即实现；SOX 与 TMA 取用方式待确认；USDCNY 收盘价入口未取得。

## 未做

- 未解析任何页面的数值，未写入任何证据。
- 未改 `catalog.py`，未改任何指标定义。
- 未认证任何来源。
