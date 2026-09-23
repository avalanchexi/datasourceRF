Type: task
Status: resolved
Blocked by: 04, 05, 06, 07, 08

# 写取代性 ADR 并更新领域词汇

## Question

把已锁定的决策写成新 ADR，显式取代 0006、0012、0014、0016、0017、0018、0019 中的冲突部分；更新 CONTEXT.md 中被改变含义或废止的术语（来源认证包、数据源认证状态、公开可用时间、计算预热、P1 认证完成等），并更新 AGENTS.md / testing.md 的相关指引。AFK 执行，完成后记录改动文件清单。

## Answer

2026-09-23 AFK 完成。

**新 ADR**
- [ADR-0021 注册来源按频率推定时效，取代来源认证与逐值发布证据](../../../docs/adr/0021-registered-sources-freshness-replaces-certification.md)：取代 0016–0019；部分取代 0013、0020。
- [ADR-0022 明细、汇总与加工批次统一只留 120 个交易日](../../../docs/adr/0022-uniform-120-day-retention-and-processing-batches.md)：取代 0006、0012。
- [ADR-0023 检索结果只从注册白名单来源取值](../../../docs/adr/0023-retrieval-verification-by-registered-parsers.md)：取代 0005。
- [ADR-0024 中断的运行作为新批次从头重跑](../../../docs/adr/0024-interrupted-runs-restart-as-new-batches.md)：部分取代 0010。
- [ADR-0025 日常只跑受影响测试，全套只在真实运行前跑一次](../../../docs/adr/0025-affected-tests-daily-full-suite-once.md)：取代 0014。

**旧 ADR**：0005、0006、0012、0014、0016、0017、0018、0019 状态改为 `superseded by ADR-00xx`；0010、0013、0020 改为 `accepted; partially superseded by ADR-00xx`；均在标题下加取代说明，正文不动。

**CONTEXT.md**：删除“候选模型版本”“可认证回放区间”“版本回放”“系统切换”“公开点时查询”“系统点时查询”“数据源认证状态”“来源认证包”“P1 认证完成”；“计算预热”改为“公式回看”，“初始化预热”改为“首次初始化”；改写“模型版本”“分析投影集”（去 `system_as_of`）、“发布历史”“核心价格指标”“来源冲突”“数据版本”“可公开接入 P2”“报告快照”“120 日证据窗口”；2026-09-05 认证审查补充标为历史记录。（票 04–07 已改的术语不重复。）

**指引**：`docs/agents/testing.md` 按 ADR-0025 重写（日常 quick、切片冒烟、终点前全套一次、门禁测试随模块删改；删除收据绑定一节，保留磁盘与解释器诊断）；`AGENTS.md` 测试执行一行指向 ADR-0025。

**未做（属实施切片）**：`tools/check.py` 的 `--freeze`/`HEAVY_FILES`、`tools/inputs.py` 收据、代码中的认证/回放逻辑均未改；`docs/agents/testing.md` 已注明落地前 `check.py full` 仍需 `--freeze`。

