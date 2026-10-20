# Standards 279

基线269与当前278哈希吻合，已核规范。新增边界选值、独立数值、父项替换及旧trace保护值得保留，符合ADR0006/0012；无已证硬规范违反。

P3建议，文件均为`tests/models/test_candidate_admission.py`：

- 5996–6026：递增clock配合+1/+2断言锁定内部读钟次数。tdd/tests.md将“Asserting on call counts/order”列为反例；建议读取公开回执/vintage边界，另验接收、校验、可用时序，再测边界选值。
- 5981–6116：新增136行嵌套分支使通用窗口用例承担独立修订流程，属判断性Divergent Change。建议拆独立修订测试，共享准备，保留行为断言。

未运行测试；279结果待真实终态。合成修订不证明实际历史PUBLIC认证。
