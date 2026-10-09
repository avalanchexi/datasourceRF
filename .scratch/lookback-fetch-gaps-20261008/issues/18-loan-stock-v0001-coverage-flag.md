Status: needs-triage
Category: bug
Type: task

# 18：贷款存量版本的"输入覆盖完整"在内置目录下恒为 false

## 现象（票 16 第二轮审查发现，2026-10-09）

票 16 把派生指标的 `input_coverage_complete` 改为只看公式实际使用的成员与期次。`loan_monthly_change` 的存量版本 `loan-stock-monthly-change-v0001` 在内置目录（`BUILTIN_CATALOG_VERSIONS`）下，即使公式所读的连续两月 `stock_end` 都齐全，这个标志仍为 false。

## 根因

- 投影按版本读取贷款成员：存量版本读各（借款人，期限）组合的 `stock_end`，累计版本 `LOAN_YTD_FORMULA` 读 `ytd_increment`（`src/pring_cycle/context_projection.py` 中 `loan_input_measure`）。
- 覆盖判断里，贷款没有登记公式成员（`lookback.FORMULA_MEMBERS` 不含 `loan_monthly_change`），所以回退为"目录要求的全部成员"。内置目录没有贷款成员契约，选择器判 `dimension_contract_unavailable`，结果不完整。
- 新目录（如 v0015 用的 `metric-catalog-v0006`）要求的 9 个组合都是 `ytd_increment`，正好与累计版本一致，所以 v0015 不受影响。

## 与旧行为一致

票 16 之前，这个标志按整个家族的缺口判断，内置目录下的贷款缺口同样因 `dimension_contract_unavailable` 不完整，标志同样为 false。不是票 16 引入的退化，只影响运行审计里的这个标志，不影响投影计算，不阻塞第二轮验收（票 17）。

## 建议

存量版本按版本声明成员：各（借款人，期限）组合的 `stock_end`。组合清单在内置目录下没有契约可查，需要先定下取自哪里（例如按已持有的组合，或给内置目录补贷款成员契约）。

## 验收草案

- [ ] 替身：内置目录、存量版本，连续两月各组合 `stock_end` 齐全时标志为 true；缺一个组合的一个月时为 false。

## Comments
