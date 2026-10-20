# 17: AI 报告正文仍写"正式阶段"

**What to build:** v0016 报告里 AI 解读应使用"价格阶段"，不写旧术语"正式阶段"。上线后补生成的 10-19 报告 report-7e4ac01e（codex_cli，第 4 版）第三节"价格验证与偏离"写："……构成非典型组合，正式阶段为空，价格阶段亦为空，不能据此推测某一价格阶段。"页面文案已在宏观 16 清理，这一处是模型输出。依据：`../investigations/browser-after-followups-20261020.md` 第 4 条。先查来源：报告输入（bundle 中的确认度债券归因边界原文 `confirmation.bond_attribution.boundary` 含"正式阶段"）是否把旧术语带给模型，再决定在提示词里说明、在报告输入里改写，还是加入报告校验的禁用词（会让此类输出退回模板，需权衡）。

**Blocked by:** None (can start immediately)

**Status:** needs-triage

- [ ] 写明"正式阶段"进入模型输出的来源（file:line）与选定做法
- [ ] v0016 报告中 AI 解读不再出现"正式阶段"（测试覆盖）；旧投影报告不受影响
