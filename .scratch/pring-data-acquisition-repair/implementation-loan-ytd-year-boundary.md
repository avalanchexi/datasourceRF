Execution: completed-code-batch

# 13续：贷款一月累计值不跨年相减

基点 `375950b03a0a3ac73c21135a28e283c10afe1030`，范围与先失败再修复记录见
[贷款跨年边界](loan-ytd-year-boundary.md)，规格与票13保持原范围。

`loan-ytd-monthly-change-v0002`的一月累计增量等于一月流量，父项只有一月本身，
不需要前一年的全年累计；其余月份必须存在相邻前月。余额版本仍按余额差分，允许跨年。
真实零值与负增量保留；缺失前月不构造零来源。派生PUBLIC有未知父项时继续未知。

先前2失败分别是一月独立输入不产生输出、10减上年100错误得到-90。
[2项GREEN](verification-loan-ytd-year-boundary-green.txt)通过1.40秒；
[59项关联](verification-loan-ytd-focused.txt)通过6.87秒，其中新增14项覆盖上述边界。
应用仅修改context_projection.py，重新安装规定WSL包后测试；未运行生产、授予认证或切换模型。

Ruff、mypy84与2文件format check通过；81安装Python文件与工作区一致；
[两轴静态审查](verification-loan-ytd/review.md)均0。本批一次全套 **716通过、0失败、782.66秒**，
退出码0，见[完整日志](verification-loan-ytd-pytest-20260908-a.txt)与[最终收据](verification-loan-ytd/final.json)。

同期[PPI逐格审查](p1-ppi-full-value-audit.md)完成8期69格，相符69、冲突0、无法独立核验0。
根代理使用独立标准库表格读取，逐格检查源码行号、原文字面数字、报告和旧准备值、
实际category/source_field/单位/期次；8原件2028054字节、13本地链接复核通过，
见[根复核结果](verification-loan-ytd/ppi-verification.json)。没有运行应用解析器或改写旧包。
PPI本次69格与旧锚点重合1格，连同CPI和其他旧锚点共130个不同标量完成独立核对，
原1858标量中另1728仍待逐值审计。数值正确不代替历史PUBLIC、获取时间、修订链和正式认证。

随后[PMI三个指标逐格审查](p1-pmi-full-value-audit.md)完成7期56格，活动28、库存14、价格14。
根代理复核7原件2894481字节、12链接及56格原表/源码行/实际合并表头列/年月/字段/单位均通过，
见[根复核](verification-loan-ytd/pmi-verification.json)。本次与旧锚点重合3格，
累计独立核对为183个不同标量、另1675未审；没有改写旧1858标量准备快照。

并行完成[OMO缺失流量边界研究](omo-missing-flow-boundary.md)，
[根复核](verification-loan-ytd/omo-boundary-verification.json)确认28引用、11输入指纹。
日志编码标准化与研究读取交叉造成首次字节核验失败，报告保留旧指纹并注明UTF8/LF最终指纹，
再复核通过；并非诊断文本变化。
主代理[2项RED](verification-omo-invalid-flow-red.txt)证实已有未披露/冲突投放被净额派生当0，
该缺陷在独立草案目录，未列入本批默认全套、尚未修复。
下一批从此窄缺陷继续，完全无行与到期账本完整性仍单独待证。
