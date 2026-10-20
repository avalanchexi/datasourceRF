# 16: 残留"正式阶段"文案与报告拒收原因写法

**What to build:** v0016 页面上普通展示文字统一用"价格阶段"，报告退模板时写出的拒收原因与实际校验一致。依据：`../investigations/browser-v0016-first-day.md` 第 4、7 条。

1. ② 债券归因（不计数）抽屉末段："不计入确认度，不由宽松程度推算或改写债券牛熊与正式阶段"作为普通说明呈现时用"价格阶段"（模型数据原文若需保留，在报告详情 JSON 中不改）。
2. 启动壳（Dash 主体加载前的静态占位）曾短暂显示"暂无正式阶段"，改为不含旧术语的占位。
3. 适配器拒收原因：`stage_mutation_rejected` 目前一律显示"输出改写价格阶段被拒"；按审计里的 `rejection.check` 区分：价格阶段改写、宏观判断阶段陈述不符（`macro_stated_stage`）、得分不符（`macro_stated_score`）、把握程度不符（`macro_stated_confidence`）等，写出读者看得懂的原因。旧审计没有 `rejection` 时保持现有写法。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] 页面测试：v0016 投影页面（含抽屉）普通文字不出现"正式阶段"；启动壳不含"正式阶段"
- [ ] 页面测试：拒收原因按 `rejection.check` 分别写出，旧审计照旧
- [ ] 两例冒烟通过
