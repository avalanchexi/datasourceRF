# 25: 发布预告接入

**What to build:** 推算发布时点优先采用发布预告：TuShare `cn_schedule` → 官方日程页解析器 → WebSearch 取得的白名单官方日程页（须经解析器解析）；都取不到时回落到统计期末后第 N 个交易日推算，不记缺口。

**Blocked by:** 13, 19

**Status:** done

Spec: [spec.md](../spec.md)

- [x] 经公开入口断言：有 `cn_schedule` 预告时按预告日期判定时效
- [x] `cn_schedule` 缺失时使用官方日程页解析结果
- [x] 非白名单或未解析的预告被丢弃并回落推算，不产生缺口
- [x] 受影响测试经 `check.py quick` 通过；切片收尾两例快速冒烟通过（按 ADR-0025）

## Comments

- 2026-09-24 完成。`release_schedule.py`：完整运行在直连刷新后取发布预告并记入本批次（表 `release_schedule`，迁移 0028，留存清理随批次删除）。顺序：TuShare `cn_schedule`（doc_id=461：month/publish_date/title/issuing_org/data_api，无时点，取登记更新时点）→ 国家统计局年度发布日程表页（按年登记网址，2026 为 t20251224_1962137.html；解析器读“序号/内容/1–12月”表及其下一行时点，同格多日如 3 月 PMI“4/三注5 31/二”拆为两次发布）。其余来源一概丢弃。
- 时效：`release_at` 先查本批次预告（按时效登记表的来源键映射到 data_api 或日程表行名；月度取期末后 75 天内、季度 130 天内的第一次发布），没有时回落“期末后第 N 个交易日”推算，不记缺口。检索发布闸门（票 19）也用同一 `release_at`。映射：PMI、CPI（含核心 CPI）、PPI、规上工业、工业经济效益、产能利用率、GDP（国民经济运行情况）、货币/社融（cn_m、sf_month）。
- 未做：WebSearch 取得日程页一步。日程页按年登记网址直取，年度网址未登记（如 2027 年）时回落推算；接入检索取日程页须先有该页的白名单与解析器（本解析器即可复用）。
- 测试：`tests/conftest.py` 会话级默认日程页离线。新增 `test_release_preannouncement.py` 3 例（固定运行时钟于 9 月 18 日 21:00：cn_schedule 9/15 → 未到应有期；无 cn_schedule 用日程页 9/9 → 落后 1 期、时效缺口；两者都不可用 → 回落推算、无记录、无缺口）。
