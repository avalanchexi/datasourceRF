Status: ready-for-agent
Type: task
Category: acceptance

# 05：收尾验收

**What to build:** 证明一次正常的 T+1 运行输入完整：体检“真正缺失”为 0，若不为 0 即为真实数据异常并写明。

**Blocked by:** 01、02、03、04；以及 [残余票 01](../../model-rules-residuals-20261013/issues/01-clock-two-time-syncs-fight.md) 的时钟持久处置（真实运行前用 65 秒时钟检查确认无回拨）。

**主要模块：** 无新代码；全套测试、真实运行与体检。

- [ ] 全套测试一次通过（ADR-0025），记录耗时与 C 盘最低余量
- [ ] 备份运行库，记录迁移状态与 doctor
- [ ] 一次真实 T+1 运行（优先 09:30 的计划运行；外部调用串行）完成
- [ ] 目标日两融值进入冻结输入；DR007 等 5 项时效为 current
- [ ] 体检：“真正缺失”为 0；上游未发布、已知历史缺口各自单列
- [ ] 与 `run-0a8dabc2e820321b84e1` 的差异逐项有原因，写入验收记录
- [ ] 规格轴审查用 `codex exec -s read-only`

## Comments

### 2026-10-13 用户决定（主 agent 转达）

真实运行用 10-14 09:30 的计划运行（目标日 10-13）：10-13 晚 06 合入后跑全套（`tools/clock_check.py` 退出码 0 才开跑，带 `tools/disk_guard.sh`）；通过后备份运行库、集成分支代码装入真实 dev-venv、`pring-cycle init`（迁移 0038 → 计划 09:30）、常驻 Worker；跑完停 Worker，体检与验收。验收通过后再问用户是否并入 main。
