# 22: 检索账本认出 TuShare 限频

**What to build:** 适配器抛出带分类的来源异常，检索账本读取该分类；TuShare 限频（40203）按限频退避，不再按语义失败退避。

**Blocked by:** 18

**勿并行：** 无

**Status:** ready-for-agent

来源：[架构评审](../README.md) 候选 4 失败分类归属（用户决定，2026-09-29）。 规格：[spec.md](../spec.md)「五、获取结果模块」。

## 现状

- `TushareSourceError` 继承 `ValueError`，40203 在适配器内已单列为 `tushare_rate_limited`（`tushare_context.py:893`），但检索账本 `trace_acquisition` 只按异常类型分类，归为 `semantic_validation_failed`（`retrieval_ledger.py:452`），退避 6／24 小时，而限频应为 60 分钟或按 Retry-After（`retrieval_ledger.py:793`、`:819`）。
- TuShare 核心／日历 helper 对所有非零业务码抛普通 `ValueError("tushare_source_failed")`（`source_adapters.py:394`），业务码丢失；资讯按 `msg` 子串判断限频（`tushare_news.py:133`）。

## 验收

- [ ] 账本按适配器给出的分类退避；TuShare 限频走限频退避。
- [ ] 核心／日历与资讯路径的 TuShare 业务码与上下文路径同样保留。
- [ ] 按 TDD：补缺路径遇 40203 → 账本分类为限频、退避按限频规则；其他业务码不误判为限频。
- [ ] 受影响测试经 `check.py quick` 通过。
- [ ] 代码审查无阻断。
