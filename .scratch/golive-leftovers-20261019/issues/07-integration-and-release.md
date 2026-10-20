# 07: 集成验收与上线（与前端缺陷批次共用）

**What to build:** 01–05 与前端缺陷 01–03 合入 main 后：一次全套（clock_check、flock、disk_guard 12G）；经用户同意重装正式 dev-venv（先备份正式库）；补生成 10-19 AI 报告（01 给出的命令）并确认 codex_cli 成功；下一次真实运行后体检，确认贷款 2025-09、债券指数、GDP 三产业、信用脉冲恢复。

**Blocked by:** 01、02、03、04、05

**Status:** done

- [x] 全套通过（integration-20261020，2756 passed，exit 0）
- [x] 用户同意后重装正式环境（10-20 06:47）
- [x] 10-19 AI 报告补生成成功（report-10416a30，codex_cli succeeded）
- [x] 下一次运行体检：上述四项恢复

## 收尾核对（2026-10-20）

run-3ebbe323（v0016 首个运行）体检：贷款 2025-09 9/9、GDP Q3 三产业、信用脉冲（22.60%）、两只债券指数全部恢复并进入模型输入。见 `.scratch/wrapup-20261020/phase1-run-check.md`。
