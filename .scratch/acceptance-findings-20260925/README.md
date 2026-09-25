# 2026-09-25 验收发现分流

来源：`.scratch/pring-retrieval-report-v2-20260924/issues/13-endpoint-suite-docs-real-run.md` 末尾“发现（待分流）”四条（真实完整运行 run-f26f88cbd9e0681f397a），外加旧 `pring-cycle-dashboard` 票逐票核对时发现的两处重构遗留（05、06）。

| 票 | 问题 | 状态 |
|---|---|---|
| [01](issues/01-check-tool-content-drift.md) | `check.py` 只比文件名，旧环境漏报 | done |
| [02](issues/02-search-candidate-fragment-cap.md) | 检索路径 1600 字片段上限使央行页面必然拒收（工具流动性、社融分项） | done |
| [03](issues/03-margin-partial-latest-day.md) | 最新一日部分交易所已发布时两融整批拒收 / 部分求和 | done |
| [04](issues/04-p2-quote-sources.md) | USDCNY 16:30、VIX、SOX 无结构化来源，候选全为 `period_mismatch` | done（ADR-0029，gap-sources 票 06/07/04） |
| [05](issues/05-run-resume-after-adr-0024.md) | ADR-0024 取消检查点恢复，`run-resume` 仍在 | done（保留，ADR-0031） |
| [06](issues/06-report-body-30-day-clear.md) | 报告正文 30 天清空与 ADR-0022 120 交易日保留并存 | done（删 30 天，gap-sources 票 14） |
