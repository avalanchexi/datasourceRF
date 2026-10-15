当前源码静态审查发现以下 8 项：

1. **P1：报告绑定存在竞态。** `submit()` 提交排队记录后才绑定投影；Worker 若在间隙领取，会改取当前投影，使历史投影请求生成另一版本的报告。依据：[规格:158](D:/cursor/datasourceRF/.scratch/ui-rebuild-20261015/spec.md:158)、[web.py:876](D:/cursor/datasourceRF/src/pring_cycle/web.py:876)、[worker.py:619](D:/cursor/datasourceRF/src/pring_cycle/worker.py:619)。

2. **P1：冻结选值可能配上修订版回执。** 补算日采用旧声明，而同源修订已在运行截止前入库时，追溯先查询最新声明，再仅覆盖选值字段；声明列表及原件仍可能属于修订版。依据：[规格:127](D:/cursor/datasourceRF/.scratch/ui-rebuild-20261015/spec.md:127)、[evidence.py:1761](D:/cursor/datasourceRF/src/pring_cycle/evidence.py:1761)、[evidence.py:1993](D:/cursor/datasourceRF/src/pring_cycle/evidence.py:1993)。

3. **P1：未发送的请求会进入桑基图。** 非 TuShare 获取先创建回执，再执行预算/缓存门禁；门禁阻止发送后，健康摘要仍无条件计入该回执，增加请求及失败数。依据：[规格:181](D:/cursor/datasourceRF/.scratch/ui-rebuild-20261015/spec.md:181)、[acquisition.py:361](D:/cursor/datasourceRF/src/pring_cycle/acquisition.py:361)、[run_health.py:201](D:/cursor/datasourceRF/src/pring_cycle/run_health.py:201)。

4. **P2：一个缺日抹掉整条价格曲线。** 窗口内缺一个交易日即保留空 `closes`，展示层因此把其余真实价格及最新值全部清空。依据：[规格:135](D:/cursor/datasourceRF/.scratch/ui-rebuild-20261015/spec.md:135)、[day_summary.py:670](D:/cursor/datasourceRF/src/pring_cycle/day_summary.py:670)、[display_projection.py:103](D:/cursor/datasourceRF/src/pring_cycle/display_projection.py:103)。

5. **P2：历史投影默认关联最新运行。** 打开 `?projection=旧投影` 且未指定运行时，直接选 `candidates[0]`，并未寻找该投影的产出运行。依据：[规格:180](D:/cursor/datasourceRF/.scratch/ui-rebuild-20261015/spec.md:180)、[web.py:630](D:/cursor/datasourceRF/src/pring_cycle/web.py:630)。

6. **P2：筛选后图表与明细不一致。** 指标、环节、结果筛选会改变请求图，但降级链只筛来源，候选校验完全不筛，仍展示范围外记录。依据：[规格:185](D:/cursor/datasourceRF/.scratch/ui-rebuild-20261015/spec.md:185)、[cockpit_operations.py:345](D:/cursor/datasourceRF/src/pring_cycle/cockpit_operations.py:345)。

7. **P2：幂等缓存阻止后续合法重跑。** 成功命令永久留在页面内的 `commands`；任务结束后，再次提交同日运行或同投影新报告，只返回旧受理信息。依据：[规格:200](D:/cursor/datasourceRF/.scratch/ui-rebuild-20261015/spec.md:200)、[dashboard.js:111](D:/cursor/datasourceRF/src/pring_cycle/assets/dashboard.js:111)。

8. **P2：解析拒收被误报为请求失败。** 直连响应结构校验失败记录为 `state=failed、structure_check=rejected`，摘要忽略后者，将缺期归为请求失败。依据：[规格:173](D:/cursor/datasourceRF/.scratch/ui-rebuild-20261015/spec.md:173)、[run_health.py:218](D:/cursor/datasourceRF/src/pring_cycle/run_health.py:218)、[run_health.py:272](D:/cursor/datasourceRF/src/pring_cycle/run_health.py:272)。

限制：Git 命令持续报进程启动错误，未完成 `9a9c30c` 基线差异及新增测试清单核验，因此不宣称上述问题均为此次新增。全程未修改文件、运行测试或访问运行库、外部接口。
