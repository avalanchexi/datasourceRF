Status: needs-triage
Category: bug
Type: task

# 01：每次运行固定出现 12 条失败回执（fut_basic 8、fut_trade_cal 4，ContextObservationsMissingError）

## 现象
2026-10-09 以来，各次真实运行（`run-a1110cb8…`、`run-a04dcc78…`、`run-674411db…`、`run-8186b774…`）都有这 12 条失败回执，错误类型都是 `ContextObservationsMissingError`。历次验收都把它们记作“常规失败”，但从没查过原因。体检票 01 还发现，期货交易所日历引用的原件也出自状态为 failed 的回执。

## 待分流确认
是上游接口的正常空应答，还是取数参数或解析有缺陷；是否影响仓单、期货日历等下游；修法与外部调用次数。

## Comments
