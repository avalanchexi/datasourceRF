Execution: completed-code-batch

# 13续：库存近似输入期次检查

本批已完成，见[实施与680项全套结果](implementation-13-inventory-period.md)；以下保留修复前反例与边界。

依据票13“同期多维输入”和用户要求数据正确进入模型，公开`build_context_projection`反例已复现：7月名义产成品库存与6月PPI均有有效/已认证来源时，旧实现直接组合为可用近似。隔离fixture使用名义105、PPI +5%，同期独立期望100；错期不能使用同一计算输出冒充有效输入。

[Draft公开反例](draft-tests/test_inventory_period_alignment.py)在规定WSL非editable环境结果[1失败、1通过，1.69秒](verification-13-inventory-period-red.txt)。只包含隔离来源声明及内存中的读取manifest，不创建候选模型或认证，不使用生产库。该反例在RRR全套运行期间保存，未修改当时受测源码；这个下一批缺陷不能因RRR批次全套通过而标为已修。

最小修复为计算前检查名义库存与PPI报告期，错期时保留两个输入的期次和来源、值为null、状态`period_mismatch`。不改变既有近似公式，不回溯选择更旧月份来掩盖最新输入不齐，不把此代理叫作官方实际库存。后续从默认测试入口完成TDD、检查缺件/认证状态及血缘，再审查和全套验证。

显示端`dashboard.py`的公式摘要已经会在value为空时省略数值，状态经`_state_label`转换。下一批应为新状态补“输入报告期不一致”的可读标签；不接管另一个任务正在修改的dashboard.css/dashboard.js。
