Execution: completed-code-batch

# 贷款累计增量跨年反例

2026-09-08，在68c87ea之后的派生鲜度在途代码（81文件指纹见
[本批指纹](verification-derived-freshness/code-fingerprint.json)）通过已接受的公开投影入口复现。
隔离fixture，未修改应用、生产或认证。

[独立草案测试](draft-tests/test_loan_ytd_year_boundary.py)和[真实RED日志](verification-loan-ytd-year-boundary-red.txt)：
2失败，3.80秒。只有2026-01累计增量10时没有月增量行；另有2025-12全年累计100时，
2026-01月增量错误输出-90，期望应为一月自身10。
依据[P1准备清单](p1-certification-readiness.md)第26项：同年相邻YTD差分，一月使用自身，跨年不可相减。
此处讨论明确的`loan-ytd-monthly-change-v0002`；`loan-stock-monthly-change-v0001`余额差允许跨年，不能一并禁用。

现 `_derived_market_context_rows` 仅切换读取measure，但两个版本共用连续月份差分；
信用社融 `_monthly_flows_from_ytd` 已处理一月自身及同年相邻，贷款未沿用该语义。
下一批先修这个纵向缺陷，验证一月缺前期/有前一年、同年2月差分、缺同年前月拒绝、
负的真实增量保留、stock版本跨年不变、原件/派生父项血缘及PUBLIC未知传播。

最初这份反例草案不在默认tests目录，当时全套派生鲜度通过不表示它已修。
草案日志在鲜度全套运行时于另一个原生WSL临时库独立生成，未变更在测应用。

## 从375950b继续的修复

基点 `375950b03a0a3ac73c21135a28e283c10afe1030`。现已将该反例提升到
`tests/integration/test_loan_ytd_year_boundary.py`。一月累计版允许单父项，自身即月流量；
其他月份仍要求相邻前月，余额版仍需两期且允许跨年。没有构造上一年末零值来源声明。
差值文档构造支持明确省略对比项，派生身份与PUBLIC/SYSTEM时间只依实际父项。

首轮2项GREEN通过1.40秒。扩展为14项验证一月有/无上年、真实零值、公开时间已知/未知、
只引用一月、同年差分、缺相邻月拒绝、负增量和余额版跨年。
连同派生鲜度与模型认证59项通过6.87秒，见[关联日志](verification-loan-ytd-focused.txt)。
应用代码在规定WSL非editable环境重装退出0后测试。完整套件716通过、0失败、782.66秒，
双轴审查0、Ruff/mypy84/2文件format通过，81安装源文件一致。
[最终收据](verification-loan-ytd/final.json)记录本代码批完成；整票13仍进行中。
