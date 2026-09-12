# 票09独立提交预览 Standards 498

固定HEAD `7272057fcbc5e1bd31c0673ead9f8dc25485e566`。仅核对 [准备清单496](window-preview-preparation-496.json) 指定的独立tree八文件及98007字节 [预览补丁](window-index-preview-496.patch)，补丁SHA256为 `7982e2e00ba69074b1319d6ae17ccf42818b9084449424ebe3c44e247fea0782`。八文件实际哈希均与准备表一致；从固定HEAD重新计算的完整八文件差异与该补丁逐字节一致。

**明确规范问题：未发现新增项。**

- 每个文件的实际增删行与495工作区本票补丁完全相同；差异仅来自基线行号/上下文。search_evidence.py:14及model_evaluation.py:32的广度导入保留完整窗口符号，邻接的旧interbank WIP依HEAD排除，未混入无关增量。
- market_breadth.py与495冻结版本完整字节一致，日期、PUBLIC及必要原件核验没有移植回退。tushare_context.py:238的合同调用与source_contract_review.py:105签名匹配，数据库、值和获取ID参数均已具备；不依赖旧WIP时间参数。新测试使用的公开准入、审查材料与transport构造函数在预览中存在，新增测试尾部未变。未见违反CONTEXT、ADR0006/0012/0013或spec Testing21的接口遗漏。

**判断性smell：没有新增重要项。**

27场景的Repeated Switches/Mysterious Name继续沿用 [495报告](review-window-standards-495.md)，不重复展开，也不将判断性建议升级为提交硬门。

本次只读核对并写报告，未运行应用测试或修改预览。主线程已记录预览Ruff/format及91文件mypy通过；175项相关回归仍运行中，不预报其终态，也不代替根495/497结果。488/494属于旧483受限测量，不构成当前预览容量验收或新增业务SLA/OOM判断。
