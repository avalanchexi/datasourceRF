# 14: 数据质量体检认识 v0016 的宏观结论字段

**What to build:** `tools/quality/audit.py` 的输出一致性检查，对 v0016 投影报出唯一一例不一致，原因是预期结论字典里没有 v0016 新增的 `macro_stage`、`macro_confidence`（投影实际为 `stage_iii`／`tendency`，与报告一致）。体检应对 v0016 投影核对这两个字段，并对 v0015 及更早的投影照旧通过。依据：`../investigations/audit-run-3ebbe323.md` 第 5 节。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] 对 run-3ebbe323（v0016）体检，输出一致性无误报（原 58/59 → 59/59）；`macro_stage`、`macro_confidence` 与投影不一致时报不一致
- [ ] 对 v0015 运行（如 run-153de306）体检结果不变
- [ ] 体检相关测试通过
