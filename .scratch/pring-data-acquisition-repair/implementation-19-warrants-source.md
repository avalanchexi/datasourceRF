# 仓单来源契约与物理请求关联切片

基点 `d68fe6e`。本批接通新目录 `CN_FUTURES_WARRANTS` 的原始来源入库与追溯，仍未完成多仓库模型选择、定向获取或正式来源认证。

新目录契约比较既有v3结构，不继承旧认证；要求TuShare、合法同日、完整四维身份和允许单位，保留8品种范围。源字段精确绑定 `fut_wsr` 的 `pre_vol/vol/vol_chg` 与前值/当值/变化；错接口或错字段整批拒绝。前值、当值不得为负；真实0和合法负变化保留。

取得链从每份原始响应的实际行建立回执关联，按品种、日期、仓库、交易所、字段、单位和值匹配。铜声明不再关联原油请求；达到1000行上限的父请求保留原件，但不承担当作完整输入的血缘，拆分后的完整子请求才关联声明。单次取得中重复的同日同品种同仓库同交易所身份，无论同值或冲突值均整批拒绝，原件保留在失败回执中，不把同次响应冲突当成历史修订。

软件正例使用明确标识的合成TuShare响应，数值锚定既有独立官方样本：铜225吨、原油1027000桶。SC保留真实交付标签SHFE；前值缺披露不构造数值，PUBLIC未知时基础SYSTEM可读而历史目标输入不通过。本批没有网络请求、真实来源认证、模型激活或切换。

## 验证

- 首个新目录取得RED为来源契约未实现；修复后1通过。
- 错API/字段RED为2个未抛错，修复后3通过；铜声明混绑两份回执的RED为2份而非1份，按原行修复后3通过。
- 负前值/当值RED2，修复后6项仓单解析通过；重复225/225和冲突225/226的RED2，修复后11项针对通过。
- [190项关联回归](verification-warrants-source-associated-01.txt)全部通过，316.56秒，范围为候选准入、TuShare上下文适配、取得回执及旧来源隔离。
- 加入完整子请求血缘正例后的[最后12项回归](verification-warrants-source-final-01.txt)全部通过，10.88秒，150 deselected。
- [mypy](verification-warrants-source-mypy-final.txt)87文件通过；[Ruff](verification-warrants-source-ruff.txt)与[格式检查](verification-warrants-source-format.txt)4文件通过；[85个源码与非editable安装核对](verification-warrants-source-fingerprint.json)一致。mypy第一轮发现既有饱和响应测试的字典推断过窄，仅补 `dict[str, object]` 注解；最终格式整理只统一该处换行，不改变行为。
- Spec与Standards最终静态审查各0项。原始RED、mypy失败及后续通过日志均保留。

## 研究纠正与下一切片

[下一切片研究](warrants-consumption-next-slice.md)关于“尚未校验请求日期范围”的判断过宽，现撤回：`_call.parse → _validate_response_periods` 已在带回执和不带回执两条公共路径逐行检查日期，仓单又明确要求trade_date列；未发现实际绕过。原研究文件保持原样，本段作为后续纠正。

仍需修复二键最低要求与四维多仓库观测的选择冲突，依据原返回行保留所有应有仓库和缺当值分母，接通定向8品种取得，并使投影及重放采用相同完整性规则。仅选择任意一个仓库或只检查已有非空标量都不能宣告齐全。总计、分区与明细暂不加总；PP/CF/TA官方原表、单位和PUBLIC仍缺证。票13、19及项目全量最终门均保持开放。

精确代码与日志绑定见[检查点](verification-warrants-source/checkpoint.json)。
