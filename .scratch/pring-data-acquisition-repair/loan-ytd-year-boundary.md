Execution: reproduced-not-fixed

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

本反例不在默认tests目录，全套派生鲜度通过也不表示它已修。
草案日志在鲜度全套运行时于另一个原生WSL临时库独立生成，未变更在测应用。
