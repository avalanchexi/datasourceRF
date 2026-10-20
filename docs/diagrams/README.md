# Archify 图表归档

[打开图表导航页](index.html)

每张图使用独立文件夹，HTML、规格、图片、说明及校验材料归入同一目录。图中时间和状态保持原快照。

| 图表 | 快照 | 入口 |
|---|---|---|
| 最近12小时推进与后续执行 | 2026-09-09 21:18—2026-09-10 09:18 | [打开图表](pring-progress-12h-20260910-0918/pring-progress-12h-20260910-0918.html) · [目录说明](pring-progress-12h-20260910-0918/README.md) |
| 近期执行与修复甘特图 | 截至2026-09-09 10:02 | [打开图表](pring-execution-gantt/pring-execution-gantt.html) · [目录说明](pring-execution-gantt/README.md) |
| Pring Cycle 系统架构 | 原架构快照 | [打开图表](pring-architecture/pring-architecture.html) · [目录说明](pring-architecture/README.md) |
| 手动完整运行的执行链路 | 原流程快照 | [打开图表](pring-run-pipeline/pring-run-pipeline.html) · [目录说明](pring-run-pipeline/README.md) |

## 后续归档约定

1. 新图直接写入 `docs/diagrams/<图表标识>/`；历史快照使用带日期和时间的标识。
2. 同一图的HTML、JSON、PNG/SVG、说明和验证材料均放在该目录；不同视图属于同一图时仍归同一目录。
3. 历史校验结果保持原字节；路径调整后的检查另存，清楚绑定调整后的文件哈希。
4. 来源快照与构建材料归入图目录的 `support/`；项目任务记录仍在 `.scratch/` 中跟踪。
5. 新增图表后更新本索引，避免把文件再次散放到 `docs/diagrams/` 根目录。
