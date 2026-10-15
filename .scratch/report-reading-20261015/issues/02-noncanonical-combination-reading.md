Status: needs-triage
Category: enhancement
Type: task

# 02：实施非典型组合解读

**What to build:** 三核心形成非典型组合（如本次债牛·股熊·商牛）时，AI 报告按 GLOSSARY"非典型组合解读"的定义生成一段解读：与哪些典型阶段只差一项资产、哪项资产偏离及其 30 日候选是否在转向、接下来应观察什么；不构成阶段判断，不写入正式阶段或阶段史。运行时默认 Codex CLI，失败改 Claude Code CLI，经报告解释校验后保存；首页以"AI 解读"区块单列（界面重规划决定第 7、8 条，`.scratch/ui-replan-20261003/decisions.md`）。

**Blocked by:** None（建议先 `/grill-with-docs` 定下面的问题再 ready-for-agent）

**Status:** needs-triage

## 现状

- GLOSSARY 已有术语定义；宏观语义批次（`.scratch/macro-semantics-20261006/spec.md` 第 30 行、Story 20）只做了输入准备：非典型组合时确认度不适用，但各关键指标读法照常输出。
- 报告提示词 `report-prompt-v0005`（`src/pring_cycle/reports.py:1065-1080`）是通用的"只解释已验证结果"，没有任何非典型组合的指引；输出 schema 的 section 只有 `title`／`explanation`。
- 事后检查（`_validate_ai_document`）中 `_stated_stages` 会把"当前/目前/现在阶段为 X"判为篡改阶段；解读里"与阶段 III 只差商品一项"这类措辞是否会被误拒，要在实施时用测试钉住。
- 确定性报告在非典型组合下没有任何解读文字（首页显示"本次报告无 AI 解读"）。

## 待决定（访谈）

1. 解读是报告里的一个固定 section（标题固定、便于页面单列），还是独立的制品／字段？
2. 输入给 AI 的"差一项资产"对照由 Worker 确定性算好（六阶段典型组合表 × 当前三状态）再交给 AI 写，还是让 AI 自己对照？倾向前者：页面不计算、AI 不判断。
3. 校验口径：解读中允许提及"最接近的典型阶段"的措辞边界；禁词表是否要加"最接近阶段／推测阶段／AI 阶段"（GLOSSARY _Avoid_ 项）以外的内容。
4. AI 两次都被拒时的确定性兜底：是否由 Worker 用模板写出"差一项资产"的事实句（不含观察建议）。
5. 是否要求对历史上的非典型组合日回填解读（倾向不回填，只对新运行生效）。

## Comments
