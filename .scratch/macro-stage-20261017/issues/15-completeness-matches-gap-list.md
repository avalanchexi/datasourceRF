# 15: ⑦ 完整度"其他缺失"与全部缺口清单对得上

**What to build:** 读者在 ⑦ 数据说明看到目录口径"其他缺失 N 期"时，能在"全部缺口"里逐期找到这 N 期（或看到为什么某期不列为缺口）。v0016 首个投影（projection-59421326，目标日 10-19）目录口径其他缺失 4 期，缺口清单只能解释 3 期（仓单 07-21、09-09，USDCNY 收盘 10-16）。体检发现 VIX 10-19 在目录 coverage 中缺失、最终计划为 `model_input_missing`，却不在 `cycle_overview.gap_list`（它沿用 10-16 值）；上一投影（10-19 v0015）中两只债券观察指数同样"coverage 缺失却未列缺口"（worker-gap-fixes 07 清单 6 不通过）。先确认差额是哪一期、两处计数口径如何产生，再让两处一致：要么列入缺口清单（注明沿用），要么不计入"其他缺失"并说明归类。依据：`../investigations/browser-v0016-first-day.md` 第 6 条、`../investigations/audit-run-3ebbe323.md` 第 4 节。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] 写明差额那一期的根因（file:line），以及选了哪种一致化办法和理由（Comments）
- [ ] 测试：目录 coverage 有缺失期（含"沿用上期值"的情形）时，⑦"其他缺失"的期数与全部缺口清单能逐期对上
- [ ] 旧投影照旧显示，不前端补算
- [ ] 两例冒烟通过
