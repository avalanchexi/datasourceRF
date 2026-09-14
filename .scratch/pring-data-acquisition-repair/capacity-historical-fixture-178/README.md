# Q1 历史目录兼容测试快照

该快照来自此前152阶段保留的合成测试库
`official-capacity-related-152/test_registered_capacity_q1_co0/runtime/data`。
178只读检查确认：SQLite integrity_check为ok、没有未落盘WAL，目录原入场模型的
清单没有`source_mapping_reference_contract`，10个注册制品字节与其SHA-256一致。
数据库与制品按原字节复制，没有删掉新清单标记、改写模型、绕过当前准入或伪造激活状态。
来源路径、原模型/目录身份、指纹与每个文件hash保存在provenance.json。

后续测试只将此快照复制到各自临时runtime，再通过公开查询、检索选择和上下文采用入口
检查旧解释兼容性；坏制品反例只损坏临时副本。它是合成审查/合成模型测试状态，
不构成正式来源认证、真实候选、PUBLIC历史认证、模型激活或120日回放验收。
