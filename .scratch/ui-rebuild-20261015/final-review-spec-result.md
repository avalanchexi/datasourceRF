按最后读取的当前源码，仍有 **3 项 P2 规格偏差**：

1. **按指标筛选会隐藏未发请求的降级记录。** 仅设置 `metric` 后，降级表要求记录的 `physical_request_id` 属于筛选结果；发布门禁等 `not_attempted` 记录没有请求 ID，因此被排除，用户无法看到该指标未尝试的原因。违反[规格第185行](D:/cursor/datasourceRF/.scratch/ui-rebuild-20261015/spec.md:185)。位置：[cockpit_operations.py:442](D:/cursor/datasourceRF/src/pring_cycle/cockpit_operations.py:442)；实际记录来源：[full_retrieval.py:110](D:/cursor/datasourceRF/src/pring_cycle/full_retrieval.py:110)。

2. **历史投影日历被当前月份、当前目录的事件覆盖。** 打开带旧 `projection` 的日历页，只要实时事件非空，就优先展示按当前时间和当前模型查询的事件，隐藏投影内日历，也未标明两者身份及更新时间。违反[规格第128行](D:/cursor/datasourceRF/.scratch/ui-rebuild-20261015/spec.md:128)及[第167行](D:/cursor/datasourceRF/.scratch/ui-rebuild-20261015/spec.md:167)。位置：[web.py:763](D:/cursor/datasourceRF/src/pring_cycle/web.py:763)、[dashboard.py:801](D:/cursor/datasourceRF/src/pring_cycle/dashboard.py:801)。

3. **补算历史投影无法默认关联其产出运行。** 完整运行会发布补算日投影，但运行记录只关联最终目标日投影。打开 `/data-chain?projection=补算投影ID` 时，页面仅按该单一关联字段匹配，找不到实际存在的产出运行，显示无运行记录。违反[规格第180行](D:/cursor/datasourceRF/.scratch/ui-rebuild-20261015/spec.md:180)。位置：[web.py:641](D:/cursor/datasourceRF/src/pring_cycle/web.py:641)、[worker.py:849](D:/cursor/datasourceRF/src/pring_cycle/worker.py:849)。

本次仅静态只读审查，未修改文件、运行测试、访问运行库或外部接口。
