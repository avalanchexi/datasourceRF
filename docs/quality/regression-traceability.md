# V1 回归追踪矩阵

本矩阵是 `pring-cycle acceptance` 的审计索引。35 个行为回归来自已冻结的历史故障清单；旧报告、旧阶段结果和旧 golden 不作为正确性 oracle。统一验收使用重新命名的合成证据、临时 SQLite、固定日历/模型/截止点及当前领域规则。

| 回归 | 规格约束 | ADR | 负责票 | 自动化测试 |
| --- | --- | --- | --- | --- |
| `REG-BOND-001` | 三核心价格状态 | ADR-0001 | 05 | `tests/domain/test_trend_state.py`, `tests/acceptance/test_v1_acceptance.py` |
| `REG-BOND-002` | 债券收益率仅确认 | ADR-0001 | 05 | `tests/domain/test_bond_direction.py`, `tests/acceptance/test_v1_acceptance.py` |
| `REG-BOND-003` | 确认冲突不替代核心票 | ADR-0001 | 05 | `tests/domain/test_bond_direction.py`, `tests/acceptance/test_v1_acceptance.py` |
| `REG-BOND-004` | metric identity 与单位绑定 | ADR-0002 | 05 | `tests/adapters/test_metric_identity.py`, `tests/acceptance/test_v1_acceptance.py` |
| `REG-CORE-001` | P0 优先门禁 | ADR-0002, ADR-0008 | 04 | `tests/integration/test_p0_gate.py`, `tests/acceptance/test_v1_acceptance.py` |
| `REG-CORE-002` | 核心身份不可互换 | ADR-0002 | 05, 06 | `tests/adapters/test_metric_identity.py`, `tests/acceptance/test_v1_acceptance.py` |
| `REG-CORE-003` | 任务身份与结果身份分离 | ADR-0002 | 05, 06 | `tests/adapters/test_metric_identity.py`, `tests/acceptance/test_v1_acceptance.py` |
| `REG-FUT-001` | 换月经济收益连续 | ADR-0002 | 06, 15 | `tests/domain/test_futures_rolls.py`, `tests/acceptance/test_v1_acceptance.py` |
| `REG-FUT-002` | 无换月元数据则不可认证 | ADR-0002 | 06, 15 | `tests/domain/test_futures_rolls.py`, `tests/acceptance/test_v1_acceptance.py` |
| `REG-FUT-003` | 保存实际合约链 | ADR-0002, ADR-0006 | 15 | `tests/domain/test_futures_rolls.py`, `tests/acceptance/test_v1_acceptance.py` |
| `REG-FUT-004` | NHII 不受外盘前月污染 | ADR-0002 | 06, 15 | `tests/adapters/test_metric_identity.py`, `tests/acceptance/test_v1_acceptance.py` |
| `REG-PIT-001` | 发布前不可见 | ADR-0006 | 02, 08 | `tests/evidence/test_point_in_time.py`, `tests/acceptance/test_v1_acceptance.py` |
| `REG-PIT-002` | public/system as-of 分离 | ADR-0006 | 02 | `tests/evidence/test_point_in_time.py`, `tests/acceptance/test_v1_acceptance.py` |
| `REG-PIT-003` | 季度数据遵守真实发布时点 | ADR-0006 | 02, 08 | `tests/evidence/test_point_in_time.py`, `tests/acceptance/test_v1_acceptance.py` |
| `REG-PIT-004` | 修订不改写旧视角 | ADR-0006 | 02 | `tests/evidence/test_point_in_time.py`, `tests/acceptance/test_v1_acceptance.py` |
| `REG-PIT-005` | 同期多 vintage 追加保存 | ADR-0006 | 02 | `tests/evidence/test_point_in_time.py`, `tests/acceptance/test_v1_acceptance.py` |
| `REG-PIT-006` | 120 个中国交易日窗口频率语义 | ADR-0006 | 02, 03 | `tests/evidence/test_point_in_time.py`, `tests/acceptance/test_v1_acceptance.py` |
| `REG-PIT-007` | 未发布时沿用上一期且不改期别 | ADR-0005, ADR-0006 | 08, 09 | `tests/catalog/test_release_calendar.py`, `tests/adapters/test_chinamoney_lpr.py`, `tests/acceptance/test_v1_acceptance.py` |
| `REG-RUN-001` | 事务中断不暴露半批结果 | ADR-0007, ADR-0008 | 16, 18 | `tests/integration/test_atomic_projection.py`, `tests/acceptance/test_v1_acceptance.py` |
| `REG-RUN-002` | 重复命令幂等 | ADR-0010 | 17 | `tests/integration/test_run_orchestration.py`, `tests/acceptance/test_v1_acceptance.py` |
| `REG-RUN-003` | 陈旧租约仅显式恢复 | ADR-0010 | 18 | `tests/integration/test_run_orchestration.py`, `tests/acceptance/test_v1_acceptance.py` |
| `REG-RUN-004` | 固定输入离线确定性重放 | ADR-0004, ADR-0008 | 03, 22, 24 | `tests/e2e/test_core_fixture_cli.py`, `tests/models/test_model_replay_rollback.py`, `tests/acceptance/test_v1_acceptance.py` |
| `REG-RUN-005` | CLI 不可用不破坏结构化驾驶舱 | ADR-0003, ADR-0009 | 19, 20 | `tests/reports/test_report_boundary.py`, `tests/acceptance/test_v1_acceptance.py` |
| `REG-RUN-006` | 截止时缺 P0 不发布 | ADR-0002, ADR-0010 | 04, 17 | `tests/integration/test_p0_gate.py`, `tests/integration/test_worker_execution.py` |
| `REG-STAGE-001` | 六个规范组合一一映射 | ADR-0001 | 03 | `tests/domain/test_pring_stage.py`, `tests/acceptance/test_v1_acceptance.py` |
| `REG-STAGE-002` | 单一不确定时正式阶段为空 | ADR-0001 | 03, 04 | `tests/domain/test_pring_stage.py`, `tests/acceptance/test_v1_acceptance.py` |
| `REG-STAGE-003` | 全不确定不得输出 Stage VI | ADR-0001 | 03, 04 | `tests/domain/test_pring_stage.py`, `tests/acceptance/test_v1_acceptance.py` |
| `REG-STAGE-004` | 非典型组合不近似匹配 | ADR-0001 | 03 | `tests/domain/test_pring_stage.py`, `tests/integration/test_p0_gate.py` |
| `REG-STAGE-005` | 宏观不可改写正式阶段 | ADR-0001, ADR-0003 | 10–16 | `tests/domain/test_pring_stage.py`, `tests/acceptance/test_v1_acceptance.py` |
| `REG-STAGE-006` | AI/报告不可改写正式阶段 | ADR-0003, ADR-0009 | 19 | `tests/reports/test_report_boundary.py`, `tests/acceptance/test_v1_acceptance.py` |
| `REG-STAGE-007` | 机械映射允许非相邻转换 | ADR-0001 | 03 | `tests/domain/test_pring_stage.py`, `tests/acceptance/test_v1_acceptance.py` |
| `REG-TREND-001` | 商品稳定牛市可达 | ADR-0001, ADR-0002 | 03, 06 | `tests/domain/test_trend_state.py`, `tests/acceptance/test_v1_acceptance.py` |
| `REG-TREND-002` | 商品稳定熊市可达 | ADR-0001, ADR-0002 | 03, 06 | `tests/domain/test_trend_state.py`, `tests/acceptance/test_v1_acceptance.py` |
| `REG-TREND-003` | 缺失不是中性分 | ADR-0001, ADR-0006 | 02, 03 | `tests/domain/test_trend_state.py`, `tests/evidence/test_point_in_time.py` |
| `REG-TREND-004` | 初始化不足不继承伪方向 | ADR-0001 | 03 | `tests/domain/test_trend_state.py`, `tests/acceptance/test_v1_acceptance.py` |

机器执行入口：

```bash
pring-cycle acceptance --json
```

任何回归、故障注入或性能硬门失败时，结果 `status=blocked`。套件耗时不属于硬门：它以 `suite_timing` 记录目标 600 秒、实测值、是否达标及计时范围，仅超时不改变 `status`。命令没有 `force`、忽略失败或改写结果的参数；产物保存于仓库外 `artifacts/sha256`，并返回内容哈希。
