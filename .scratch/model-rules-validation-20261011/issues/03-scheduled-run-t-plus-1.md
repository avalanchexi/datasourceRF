Status: ready-for-agent
Type: task
Blocked by: —

# 03：自动盘后运行改为次一交易日上午 9:00 识别上一交易日

依据：spec 第 2 节，ADR-0041。在票 14（`worker.py` 的调度判断）基础上改。

## 验收
- [ ] 测试先红后绿：交易日 9:00 提交上一交易日的运行；非交易日不提交；上一交易日日历缺覆盖时先补取；补取失败时暂缓并重试；节后第一个交易日识别节前最后一个交易日。
- [ ] `docs/development/local-runtime.md` 中盘后计划一段更新。
- [ ] 受影响测试、冒烟、ruff、mypy 通过；Codex 两轴审查无阻断。

## Comments
