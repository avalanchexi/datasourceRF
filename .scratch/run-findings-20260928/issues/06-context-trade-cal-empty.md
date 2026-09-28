Status: needs-info
Category: bug
Type: task

# 06 — context 口径的 `trade_cal` 返回 0 行

## 原始发现

- 今天两次 `tushare-context-parser-v0002` 的 `trade_cal` 请求（`is_open=1`，起始日 2025-02）都通过校验，但 `row_count=0`。上一轮同样的请求返回 1560 行。
- 核心口径（`tushare-core-parser-v0002`）的 `trade_cal` 正常，运行日窗口用的是核心口径，所以本轮没有受影响。

## 还需要补充的信息

- 哪些指标依赖 context 口径的交易日历；0 行时它们会怎样。
- TuShare 这个查询 0 行是偶发还是持续，下次运行后再看一次。
