# GDP 双轴审查

审查固定基点：`99c495a217b66d4bca9d6ceae4688ee69d4382bb`，无新增提交。命令 `git diff 99c495a -- src/pring_cycle/metric_contracts.py src/pring_cycle/official_context.py tests/models/test_candidate_admission.py`；限定本次GDP合同、完整性集合、表头守卫及GDP公开测试，其余已有宏观/银行间变化只作调用上下文。审查者只读，没有运行应用、测试、WSL、SQL或网络。

## Standards

首次硬问题1：v4解析器仅按固定列位读取，没有核金额单位、当季/累计表头及价格口径，符合字节哈希仍可能语义错误。首次启发式建议1：三处重复GDP合成准入准备。

真实RED84复现前者的六种入库/消费失败；新目录专用共享表头守卫已加到入库与消费两处，保持v4 parser与规范化表示。准入准备提取为 `admitted_gdp_manifest`。最终只读复核：**剩余硬问题0，新增实质气味0**。

## Spec

首次及增量复核均为 **剩余0项**。表头校验覆盖新目录入库与原件消费，旧版本、GDP P2和信用脉冲公式保持。Q3/Q4测试仅验证真实原件布局与八个独立字面值，不代表真实来源认证、跨修订可相减或120日完成。

## 复核绑定

|文件|SHA256|
|---|---|
|src/pring_cycle/metric_contracts.py|db57e40351114456ef31ee1befbaee038f7d90a80e78678dc843248343e549a6|
|src/pring_cycle/official_context.py|32390379d5729d14c0b445ec2a895e3bd799d73ceb691942ed47810bf9cc2bde|
|tests/models/test_candidate_admission.py|b5f1254160cf1d7a1227390166a6ec445b15bafd3aa0a18d47353ab080baae42|

Standards与Spec分别报告，未将静态审查作为执行测试或整体完成依据。最终合并回归87尚待实际终态。
