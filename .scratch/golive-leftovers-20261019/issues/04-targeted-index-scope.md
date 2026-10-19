# 04: 定向补取市场指数时请求、校验、入库范围一致

**What to build:** 定向补取单只债券指数时，原件重解析得六只指数、入库输出被裁成一只，整组比对必然 `registered_market_index_acquisition_values_mismatch`（调查第 4 节，目标值两侧相同）。让请求、原件校验与入库输出采用同一范围（最好按所需指数请求），保留严格数值比对，不放宽容差。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] 集成测试：定向补取 CNY030／930916 成功入库；数值不同时仍拒收
- [ ] 两例冒烟通过
