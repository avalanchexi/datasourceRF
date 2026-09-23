# 12: 加工批次骨架

**What to build:** 一次手动完整运行即一个加工批次：批次 id = 运行 id。运行后可查询批次登记的目标交易日、代码版本、模型版本号，以及每次接口调用的接口与参数、返回条数、原始响应哈希；汇总各表带文本型 `batch_id`（非外键）。批次不在页面或报告展示。见 spec“存储、批次与留存”与票 06。

**Blocked by:** None (can start immediately)

**Status:** done

Spec: [spec.md](../spec.md)

- [x] schema 迁移扩展 `parent_run` 与 `acquisition_request`，汇总表（派生观测、投影集、当前投影、阶段史、报告快照、缺口提示）增加 `batch_id` 文本列
- [x] 经 run-submit → Worker 的测试断言：批次记录目标交易日、代码版本、模型版本号；每次接口调用有参数、条数、原始响应哈希
- [x] 明细经获取回执可追到批次；汇总行的 `batch_id` 等于该运行 id
- [x] 页面与报告不出现批次信息
- [x] 受影响测试经 `check.py quick` 通过；切片收尾两例快速冒烟通过（按 ADR-0025）

## Comments

- 2026-09-23 完成：新增 `batches.py`（批次上下文、`add_batch_columns`、代码版本、返回条数）与迁移 0022；`parent_run.code_version`、`acquisition_request.row_count`、七张汇总表 `batch_id`。获取回执经既有 `full_run_acquisition` 挂运行。`tests/integration/test_processing_batch.py` 4 passed / 16.6 秒；相关 163 passed；两例冒烟 2 passed。
