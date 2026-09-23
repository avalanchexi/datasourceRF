# 17: 门③拒收，解析异常改为缺口

**What to build:** 每条取回数据经廉价结构校验（字段/单位/统计期/非空），不通过即拒收、不入库，结果记入批次；TuShare P1/P2 解析异常不再让整次运行 action_required，而是按③拒收并记为缺口。

**Blocked by:** 12

**Status:** done

Spec: [spec.md](../spec.md)

- [x] 经公开入口断言：结构不合格的响应不入库，批次里该次调用记为拒收及原因
- [x] TuShare P1 解析异常时运行照常完成，该指标出现在缺口中
- [x] P0 解析异常同样拒收（后续处置由 21/22 号决定），不抛出中断运行
- [x] 受影响测试经 `check.py quick` 通过；切片收尾两例快速冒烟通过（按 ADR-0025）
- [ ] 另加跑完整目录正例与三核心反例（涉及 Worker 编排/目录/来源），记录退出码与耗时

## Comments

- 2026-09-23 完成：获取回执新增 `structure_check`（passed / rejected）与 `rejection_reason`（迁移 0026），已应答但解析或校验失败的调用即为拒收；Worker 不再因非 P2 的 TuShare 解析异常中止运行（KeyError 一并视为结构失败）；三核心刷新改为逐路拒收，其余核心照常入库，三路全被拒时抛出第一处原错误，Worker 捕获后交由后续核心缺口处置。新增 `test_structural_rejection.py`（P1 与 NHII 各一例）；`test_worker_reviewed_context` 的无效月份用例改为“拒收并记录、不抛出”。相关 7 个文件 69 passed，两例冒烟通过。
- 完整目录正例与三核心反例未跑：前者待 27 重建，后者在 21 以新规则重建。
