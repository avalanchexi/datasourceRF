只读复核确认 **3 项 P2 正确性问题**，均非可选重构建议：

1. **成员单位被错误统一** — [context_projection.py:876](/D:/cursor/datasourceRF/src/pring_cycle/context_projection.py:876)
   GDP 的实际同比与名义累计值分别使用 `%` 和亿元，但新增元数据一律取 `definition.unit`，使宏观表“模型读取值”错标或丢失量纲。应保留成员实际输入的单位。规则：[规格第 134 条所在行](/D:/cursor/datasourceRF/.scratch/ui-rebuild-20261015/spec.md:134)。

2. **旧运行请求被漏计** — [web.py:662](/D:/cursor/datasourceRF/src/pring_cycle/web.py:662)、[run_health.py:234](/D:/cursor/datasourceRF/src/pring_cycle/run_health.py:234)
   升级后打开没有健康摘要的旧运行，Web 会临时计算摘要；旧请求没有迁移 0039 新增的 `acquisition_dispatch` 标记，因此被过滤，页面可能显示“0 次真实请求”。应显示口径不可用，不能把缺少记录当作未发送。规则：[规格 §8–9](/D:/cursor/datasourceRF/.scratch/ui-rebuild-20261015/spec.md:175)。

3. **再次恢复仍被幂等缓存拦截** — [dashboard.js:142](/D:/cursor/datasourceRF/src/pring_cycle/assets/dashboard.js:142)
   恢复后再次进入 `action_required` 或 `interrupted`，缓存只在 completed/cancelled/failed 时释放；同页再次点击恢复会直接返回旧受理信息，不发送新命令。上一轮修复未覆盖这两个可恢复状态。规则：[ADR-0031](/D:/cursor/datasourceRF/docs/adr/0031-keep-run-resume.md:9)、[规格 §11](/D:/cursor/datasourceRF/.scratch/ui-rebuild-20261015/spec.md:200)。

已核对预计算基线差异、当前源码及新增测试；未修改文件、运行测试、联网、访问运行库或再委派。
