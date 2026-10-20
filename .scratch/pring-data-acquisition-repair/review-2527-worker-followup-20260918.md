# 完整 Worker 后续反例和变异脚本复审

2026-09-18 11:27 上海时间。两轴复审范围为 `pending-test_integrated_worker_core_gap.py`、`verify-2527-worker-delivery-mutations-20260918.py`；生产源码和正在验收的测试保持冻结。

Spec 与 Standards 均指出旧变异脚本只匹配退出码、AssertionError、FAILED，可能把生命周期准备失败误算为检出。Standards 另指出未固定原材料身份和缓存目录，可能因scratch输入、依赖或环境变化意外重建。

修正后固定实际基线激活进程记录的 material key/store，检查当前完整身份、存储运行文件哈希及 material.json，显式传递同一缓存目录。检出要求唯一 call 阶段失败且文件、断言行准确，同时通过公开 RunRepository/AcquisitionRepository 核实改动后的外部交付及原始响应。两轴只读复审均确认上述问题闭合，无新增硬问题。

P0反例会在直接采集阶段停止，证明核心空交付不发布且原件/归属仍可查；它不证明之后的官方回退已执行。m1_yoy变异证明必需响应字段的敏感性，不证明移除投影或报告来源留痕的敏感性。

截至本记录，两项变异及新P0反例均未执行；脚本已通过语法编译。必须等基线句柄16639终态exit0后串行运行，实际结果另留日志和JSON，不把本次审查作为运行通过证据。
