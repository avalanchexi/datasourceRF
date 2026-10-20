结论：**标准轴不通过：2 项阻断、1 项建议。** 两项阻断均已用冻结夹具复现：相同报告在 `74cdb38` 被拒，在 `06b7503` 返回 `succeeded`。全程只读，未改文件或落盘报告。

1. **阻断｜[reports.py:1848](/home/tywin/worktrees/datasourceRF-mf/src/pring_cycle/reports.py:1848)、[reports.py:1777](/home/tywin/worktrees/datasourceRF-mf/src/pring_cycle/reports.py:1777)：条件作用域过宽，真实主结论改写可以借用信号重判结果通过。**

   冻结夹具的主结论是“第三阶段／倾向”，PMI 重判是“第五阶段／明确”。以下完整正文却通过校验：

   > 宏观判断为第三阶段，把握程度为倾向。如果读者需要一句话概括，宏观判断为第五阶段，把握程度为明确。

   另一反例也通过：

   > 宏观判断为第三阶段，把握程度为倾向。如果 PMI 转弱则需要关注，但本次宏观判断为第五阶段，把握程度为明确。

   `_conditions` 不区分经济条件与表达条件，也不识别“但本次”已恢复现实陈述；区间内所有 conclusion 标记都被改成 signal。违反 ADR-0027 的“不改写结论”及 ADR-0043 对主结论、把握程度的要求。

   **建议改法：**仅对明确描述指标变化及其重判结果的分句启用重判校验，绑定对应信号；独立断言、转折后的现实陈述恢复主结论校验。补充上述整段反例，不能只继续扩充 `_ACTUAL` 关键词。

2. **阻断｜[reports.py:1710](/home/tywin/worktrees/datasourceRF-mf/src/pring_cycle/reports.py:1710)、[reports.py:1827](/home/tywin/worktrees/datasourceRF-mf/src/pring_cycle/reports.py:1827)：否定正则只匹配末端，双重否定被误判为否定“明确”。**

   以下完整正文通过校验：

   > 宏观判断为第三阶段，把握程度为倾向。宏观判断为第三阶段，把握程度并非不是明确。

   `search` 只捕获紧邻“明确”的“不是”，忽略外层“并非”，于是允许把倾向升级为明确。“宏观判断为第三阶段，不能说不是明确的结论”也同样放过。依据同上，尤其违反 ADR-0043“倾向、弱不得显示为明确”。

   **建议改法：**识别完整否定结构；只有确定为单层否定时才能走当前放行分支。对双重否定及无法消歧的嵌套结构保守拒收，并通过现有 `ReportService.generate` 接缝补反例。

3. **建议｜[day_summary.py:214](/home/tywin/worktrees/datasourceRF-mf/src/pring_cycle/day_summary.py:214)、[worker.py:800](/home/tywin/worktrees/datasourceRF-mf/src/pring_cycle/worker.py:800)：同一份时效记录拆成两张平行映射，增加调用方保持一致的负担。**

   **传入已记录的时效状态本身合理**：Worker 仍只读取一次 `batch_freshness`，汇总模块不必重算时效，符合运行材料边界。这不是 ADR 硬违例，但 `held_periods` 与 `freshness_status` 是同键、同来源、共同消费的数据，存在数据成组却分散传递的问题。

   **建议改法：**将两者收束为一份有类型的逐指标时效摘要，由 Worker 传入、汇总模块消费，符合 ADR-0004 的小接口原则。不建议从“没有缺口”反推 current，也不建议直接替用上下文行的 `status`——后者还包含可采用性、冲突等不同语义。

夹具方面，[rejected-readings-20261019.json:1](/home/tywin/worktrees/datasourceRF-mf/tests/fixtures/report_input/rejected-readings-20261019.json:1) 为 **83,688 字节，约 81.7 KiB**；冻结输入加两份真实完整报告的体积合理，确认关系等内容也参与校验，测试只读取仓库内样本，不依赖正式目录，建议保留完整回归价值。

其余方面未发现需报告的问题：ms-14 保留旧模型分支并比较投影原值；页面不重算旧投影；ms-rf 的“无既往主结论”措辞与行为相符；新增测试主要断言发布结果、报告采用结果及可见文字，命名和注释方式与周边一致。

验证范围：在内存中重放现有 **20 个报告校验案例，全部通过**；直接执行 **3 个使用内存 SQLite 的体检测试，全部通过**。未运行会创建临时文件的 pytest 集成流程，因此不将这些探针表述为完整测试套件通过。
