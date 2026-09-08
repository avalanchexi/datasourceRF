# RRR 新目录来源入库切片

基点7a7e384，沿用票13/19已接受的公开入库与证据查询测试入口。真实搜索新取得的PBC原通知作为不可变原件输入；本切片只修复来源结构入库，尚未实现动态事件完整成员选择器或正式来源认证。

新目录使用v3的RRR结构字段作比较基线，不继承其认证标签；来源必须为央行，维度须精确为scope/measure且scope非空。rrr_change使用percentage_points、post_change_rrr使用percent、released_funds使用hundred_million_cny；event必须为规范、合法、起止相等的生效日期。旧目录保持原行为。

真实原通知导入回归保留两范围-0.5/-5百分点、2025-05-15生效日与2025-05-07 10:00:00页头；测试中的SYSTEM取新的合成导入时钟，不冒充真实预实验取得时间。错误provider/scope/measure/unit/期次/日期整批拒绝，合法首条不会部分落库。

- 首次真实RED：1失败、118 deselected、32.15秒，registered_source_contract_not_implemented:CN_RRR_EVENT。
- 修复后正例：1通过、118 deselected、3.65秒。
- 针对回归：8通过、118 deselected、11.01秒。
- Spec静态复审0；Standards指出的原件跟踪问题已由c062d76证据检查点解决，原件属性-text/-diff且hash一致，复审剩余0。
- 关联回归未启动：WSL发行版挂载报0x80070070，C盘可用0字节。日志[保留](verification-rrr-source-related-01.txt)。未执行本切片Ruff/mypy及最终全量门；不能称完整验收。

源代码此前通过的搜索/macro门不替代本切片验证。RRR动态公告成员、修订时点、完整窗口及阶段期限仍待独立推进；未创建实际候选、激活模型或切换。

[本切片未完成检查点](verification-rrr-source/checkpoint.json)绑定8项针对回归、失败环境日志及两文件指纹。源码及测试保留工作区待恢复验证，未作为已验收代码提交。
