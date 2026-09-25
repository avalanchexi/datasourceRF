Status: done
Type: task

# 07 — USDCNY 16:30 由中国货币网直连取得

规格“USDCNY 16:30”一节（用户故事 20–23），依据 ADR-0029。

## 调研结论（2026-09-25）

- 接口：`https://www.chinamoney.com.cn/r/cms/www/chinamoney/data/fx/rfx-sp-iday-chrt.json`（“人民币兑美元日内走势图”，页面 `/chinese/mkdatapfx/` 的片段 `dollar-ask-day-chart.html` 所用）。无需登录与特殊请求头。
- 字段：`data.closeSpotPrice` 为 16:30 收盘价；`data.spotPriceStr` 为最新价（夜盘结束后即 03:00 收盘）；`data.lastDate` 为数据时点（如 `2026-09-25 3:00`）；`data.chartsDataStr` 为 10 分钟快照，其中 16:30 那一点 `time` 为空格（页面脚本把它显示为 “16:30”）。
- 口径核对：2026-09-24 `closeSpotPrice=6.7131`，与“在岸人民币兑美元 9 月 24 日 16:30 收盘报 6.7131”（FX168、星岛）一致；同一文件 `spotPriceStr=6.7125` 为 03:00 夜盘收盘，二者不同。
- 限制：只有最近一个交易时段，没有历史查询；交易日 T 的时段从 T 09:30 到 T+1 03:00，所以 `lastDate` 时刻早于 09:30 时属于前一自然日的交易日。9/25 为中秋休市，文件停在 `2026-09-25 3:00`。
- 参考汇率历史接口 `/ags/ms/cm-u-bk-fx/RefRateHis` 只有整点参考汇率（16 时为 6.7117），不是 16:30 收盘价，不采用；SDDS 汇率接口的“即期”为中间价，也不采用。

## 实施

- 登记为注册官方来源，新写解析器：收盘价须为正数，且须与快照中 16:30 那一点的价格一致，否则拒收（防页面结构变化取到错值）。
- 时效登记改为滞后一个交易日；移除宽松检索家族。
- 结论：找到了稳定接口，资讯规则回退不实施。

## Comments

- 2026-09-25 实施：`quote_sources.py` 的 `CHINAMONEY_USDCNY_1630`，与 VIX 同一接法。`lastDate` 早于 09:30 时归前一自然日的交易时段；未到 16:30（或收盘价为空）时不取值；`closeSpotPrice` 与快照中空格时点（16:30）那一点不一致即拒收（防把 03:00 夜盘收盘当 16:30）。时效登记 `chinamoney:usdcny_1630`，滞后 1 个交易日。单位沿用目录登记的 `scalar`，不换目录版本。`chinamoney_usdcny_1630` 宽松检索家族删除；宽松路径保留但已无登记家族，其测试临时登记原两个家族以保持覆盖。
