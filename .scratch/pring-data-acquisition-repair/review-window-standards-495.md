# 票09 Standards 收尾复审495

固定HEAD `7272057fcbc5e1bd31c0673ead9f8dc25485e566`，本票提交为空。仅审 [inputs495](window-review-inputs-495.json) 指定的422基线（evidence.py为476基线）至495冻结快照；八份快照及98054字节补丁SHA均核对一致，补丁为 `b96a926c34f0fec6ed663ba31df5141a9d0626b71b5fab3ad2a93ea9b9822c6f`。相对484仅market_breadth.py和测试追加发生变化，未用活动工作区差异扩大范围。

**明确规范违反：未发现新增项。**

- `market_breadth.py:885–903`：coverage起止日和事件有效日均要求规范ISO编码，覆盖起止顺序也被核验；484发现的“解析接受但字符串排序漏用事件”已收口。公开反例位于 `test_candidate_admission.py:14070、14108`，保留failed收据及无SYSTEM值断言。符合CONTEXT「已验证证据」和spec Testing7/21；489、492公开RED与490、493对应GREEN在实施记录中有据，不把此静态复核冒充另一次测试。
- `market_breadth.py:332–363、868–906、1176–1251`：共同元数据与原件内容核验各有明确职责。采集仍验证全部输入；逐期采用验证共享审查和元数据，再验证实际coverage/事件原件。新公开例 `test_candidate_admission.py:14006` 独立断言第二日新低增加、损坏未来事件只撤销第二日采用、恢复后复原。未见违反ADR0006、CONTEXT不可变证据或spec Testing21必要父项约束的新增问题。

**判断性smell：保留1项。**

- **Repeated Switches / Mysterious Name**：`test_candidate_admission.py:12995–13519` 仍以一个“完整窗口”名称串联27种输入、拒收、PUBLIC及回放行为，尚未重构。建议按窗口资格/停牌、调整与PUBLIC、输入拒收、原件采用/回放四组拆分，仅共享合法输入构造并保留独立期望。code-review明确这些是判断性启发；仓库及implement/tdd没有要求每项smell必须在软件切片提交前清零。可明确登记为可维护性欠项，不能把“适合在review阶段重构”解释成新增硬门。

本次未运行产品测试。493四项、491日广度60项是已记录的限定范围结果；family495尚未取得终态，不称家族通过。488/494均为旧483的5000成员受限实验：494定位首次窗口计算，未证明OOM或业务SLA失败，更未验收495容量。真实来源认证、最终性能及同版本全套仍按各自票与spec Testing12/15/22处理，本报告不据此关闭M2/M6或整票业务验收。
