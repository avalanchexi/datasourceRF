# v5 完整验证准备审查（2026-09-18）

相对已审 v4 驱动，v5 只允许候选天数测试夹具的已审增量。旧 v2 冻结 project/site 保留；新 project 从旧快照复制并仅替换该测试。当前整合树的 src/tests/tools 与配置、冻结快照、安装源码分别精确核对。环境、两种生命周期材料的完整 identity/key 及实际 runtime 内容哈希在启动前核对；消费者仍使用独立可变副本，默认发现和原始顺序完整保留。

初次 Spec 增量审查新增问题 0。Standards 发现 1 项前置阻断：正在运行的相关回归驱动把 `supervised_verification_command.run()` 返回的 Popen 当作结果字典序列化。该驱动的错误不等于 pytest 失败，也不能忽略真实测试终态。

运行中原驱动与绑定输入未修改。新增 `recover-calendar-related-receipt-20260918.py` 等待真实监督终态、同一 PID/start_ticks、已跟踪进程退出、实际 TypeError 日志、原驱动哈希及运行中捕获至恢复时的输入一致，再独占创建明确命名的 recovered 收据，不重复执行测试。原驱动启动前后比较在内存中计算、尚未成功落盘，恢复收据明确 `original_driver_input_comparison_recorded=false`，不冒充已有启动前快照。v5 必须重新独立保存并核对自身完整前后输入。

Standards 对恢复方案增量复核：未解决 0。Spec 恢复方案复核状态以随后追加记录为准。上述是准备审查，不证明恢复器已经执行，也不证明完整验证成功。

Spec 对恢复方案及实际恢复收据复核：新增阻断 0；独立核验测试监督 exit 0、187 passed、无残留与哈希一致。Standards/Spec 本轮未解决各 0。完整 v5 验证仍须实际执行并取得自身终态。
