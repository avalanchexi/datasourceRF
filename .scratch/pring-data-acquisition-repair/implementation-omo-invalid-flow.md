Execution: completed-code-batch

# 13续：OMO 已知无效流量不得成为净额中的零

基点 `d3c83e51839c0afa72d8147e2768350ab8617fe2`。沿用
[规格](spec.md)、[票13](issues/13-remaining-p1-evidence.md)及
[OMO原始研究边界](omo-missing-flow-boundary.md)，后者保留原批代码和日志指纹。
本批公开测试接缝仍是 EvidenceRepository 写入/查询/派生追溯与 build_context_projection。

`repo-net-injection-trading-calendar-v0002` 保留截至时可见的无效投放、到期记录参与
目标日期与可用性判定。目标日已知无效投放/到期阻断净額派生；依日历推算到期时，
应在目标日到期的已知无效历史投放也阻断。较新坏记录不会被过滤后回退旧净额。
有效显式到期量不依赖无关的无效历史投放；真实零值保留为实际输入，血缘只含实际父项，
任一实际父项 PUBLIC 未知则派生 PUBLIC 仍未知。

本批先在未改代码基点重现2项失败，首段修复后2通过；再重现无效到期、无效预热、
较新坏记录3项失败，修复后13项关联通过。新增正向控制后
[74项关联测试](verification-omo-controls.txt)通过，20.40秒。
双轴初审指出无效历史投放的推算到期日仍未参与目标选择；
[公开反例](verification-omo-review-red.txt)1失败后，加入该日期集合与阻断判断。
[最终75项关联](verification-omo-review-green.txt)通过29.46秒，新增默认回归9项。

这不认定“完全没有记录”等于官方确认不操作，也不解决历史到期账本完整性。
旧 v0001 显式成对公式不在本批变更范围。没有给予真实来源认证、生产写入或模型激活。
后续仍需原始公告覆盖证据和正式时间/版本认证，再验收真实模型与重放。

Ruff与2文件格式检查通过；mypy本批src及新增测试82文件通过；81安装Python文件一致。
类型初查还包含未修改的test_context_projection.py，报告本批列表可空类型1项和既有20项；
本批类型已修复，旧测试文件保持原状，初查日志保留。不能将其称为全仓测试类型无错。
[两轴复审](verification-omo-flow/review.md)均0剩余问题。
本批一次全套 **725通过、0失败、1014.22秒**，退出码0，
见[完整日志](verification-omo-flow-pytest-20260908-a.txt)与
[最终收据](verification-omo-flow/final.json)。全套之后81安装Python文件再次与工作区一致。

[工业财务逐格审计](p1-industrial-finance-full-value-audit.md)7期70格通过；
[根复核](verification-omo-flow/industrial-finance-verification.json)校验7原件3401593字节、
12本地链接、49原表格定位、14段落片段及7金额单位转换；没有运行应用解析器。
本次与旧锚点重合3格，累计250/1858个不同准备标量独立核对、1608待审。
数值核对通过不代表历史PUBLIC、修订版本或来源正式认证通过。

[工业增加值](p1-industrial-va-full-value-audit.md)20格/7原件2664666字节与7页面时间标注
根复核通过；[月度工具](p1-tool-liquidity-full-value-audit.md)192格/8原件357909字节通过，
19个负数、28个真零保留，RRR行24个非数字短横线没有当零。
[产能审计](p1-capacity-utilization-full-value-audit.md)9标量中8个直接原文字面通过，
Q1累计复用另1个源映射待确认。根复核结果见verification-omo-flow目录。
扣除各家族与旧锚点重合，累计467/1858个不同标量字面核对通过；1391个未通过，
其中产能Q1复用1项已检查但源映射待确认，不能归为完全未检查。

后续[产能缺累计列边界](capacity-missing-ytd-boundary.md)已公开复现1RED：
非Q1不完整数据行仍把当季率复制为累计率。反例在独立草案目录，不在本批默认全套；
本批没有改official_context.py，因此此缺陷仍待下一批修复。

最后[M1/M2审计](p1-money-full-value-audit.md)28格完成根复核：27精确相符，
2026-02 M2原文349.22万亿元应归一化3492200亿元，旧准备值3492200.0000000005，
差5E-10亿元保留未通过。7原件312999字节、12链接、5输入指纹和全部身份/单位/期次通过。
未执行当前应用，不能将旧快照差异称为当前公开解析器已经复现的代码缺陷。
本次27相符格与旧锚点重合1，最终累计 **493/1858** 不同标量直接字面核对通过；
另1365未通过，其中1项金额表示差异、1项Q1复用源映射待确认，其余1363尚未逐值核对。
全部旧快照和真实时间未知状态保留，未自行设容差放行。
