# GDP 新目录八字段与原件消费修复

2026-09-09。承接修复规格实施3、6–8及测试2、4、6，来源边界见 [GDP研究](gdp-registered-source-contract-boundary.md)。工作区基点为 `99c495a217b66d4bca9d6ceae4688ee69d4382bb`；本页只记录本次GDP增量，不将已有宏观/银行间批次或报告批次的测试数量累加。

前一目标轮只更新进展首页，按目标规则记为 no progress。本轮已有实际源码修复和行为验证，可记 progress。

## 实际缺陷与修复

- [导入RED75](verification-gdp-contract-red-75.txt)：完整登记候选经合成审查后导入NBS Q2原件，报 `registered_source_contract_not_implemented:CN_GDP`，1失败、29.85秒。`official_source_members` 增加GDP四产业/总量类别各两成员，复用通用官方合同校验；[GREEN76](verification-gdp-contract-green-76.txt)1通过、12.90秒。
- [消费RED77](verification-gdp-consumer-red-77.txt)：分别损坏隔离库raw或normalized文件后，检索仍返回complete=true，2失败、1正常通过。将 `nbs_gdp` 加入已有官方原件完整性集合，沿用声明、原件和规范化内容核验；[GREEN77](verification-gdp-consumer-green-77.txt)3通过、32.89秒，包含正常选择及PUBLIC/SYSTEM下坏原件拒收和模型采纳集合排除。

GDP保持P2及已有八字段：`nominal_ytd_level`使用亿元和年初至季末，`real_quarter_yoy`使用百分比和当季首尾。没有修改parser表示、信用脉冲公式、冻结v3、真实来源认证、生效模型或旧声明。

## 扩展验证

- [Q1复制收据78](verification-gdp-q1-copy-78.json)：从既有CAS只读取得238636字节Q1原件，原/副本SHA256均为 `61f8de5fbdb2ca88130504d13a0af85ebb92004b04b85772ae3c619003767a18`，固化到仓库fixture；不是新网络获取，也不沿用旧SYSTEM时间。
- 扩展78的3失败来自测试误读投影字段 `period_kind`；它由公开trace提供，未据此修改产品接口。另按实际trace类型使用获取收据和公开原件读取。旧失败日志保留。
- [扩展79](verification-gdp-quarter-expanded-79.txt)：3通过、14.98秒。Q1/Q2共16独立官方字面值、Q1同起日的两类期次、Q2季度同比与累计同比区别、PUBLIC与本次SYSTEM、投影中GDP角色/值/单位、原件故障状态均验证。合成更改数值但保留旧页头的修订PUBLIC保持未知，旧PUBLIC仍取原值，SYSTEM选择新取得版本。
- [身份80](verification-gdp-identity-80.txt)：1测试通过、18.99秒，覆盖6种错误来源/成员/单位/period_kind和4种错误季度边界，均被公开声明接口拒绝。
- [成员81](verification-gdp-members-81.txt)：5通过、32.41秒。完整Q2选8项；缺一个成员、缺获取关联、质量无效、累计同比错作季度同比各只选7项并保持不完整，不从已存Q1补成员。

以上各批范围有重叠，不相加作为最终计数。应用安装及验证使用仓库独立 `.tmp/venvs/pring-repair-20260909` 和原ext4验证卷，不向既有服务环境追加安装。

## 表头问题的追加修复与实际终态

Standards审查发现v4解析仅按列位取值，尚未核单位/季度列和价格口径。RED83中单位及价格基础两例实际未拒收，季度标题变体误改全文标题而被旧期次门拒绝；保留该日志，随后把变体收窄为实际表格单元格。完整[RED84](verification-gdp-headers-red-84.txt)在新目录入库与消费分别复现错误单位、互换季度/累计列、增长按现价，共6失败。

新增 `_validate_registered_gdp_table` 共享守卫，只接新目录入库与原件消费；核支持表头、成员行列数及同表价格说明，保持旧v4解析和规范化输出。准入测试准备提取为 `admitted_gdp_manifest`。[GREEN84](verification-gdp-headers-green-84.txt)15通过、93.03秒。另把既有Q3/Q4原件按hash只读复制到仓库fixture，并从原HTML独立读取16个字面值，见[复制记录85](verification-gdp-q3-q4-copy-85.json)。全部四类季度布局由真实样本覆盖，不是新网络样本或历史SYSTEM恢复。

**2026-09-10最终合并87：95通过、0失败，337.12秒，主会话70085实际退出0。** 包含17项GDP测试和相关官方家族、新旧来源隔离、CLI、旧GDP语义及目录检查，精确范围见[运行记录](verification-gdp-running-87.json)，[终态收据](verification-gdp-terminal-87.json)。前后228冻结输入与4受保护文件不变、91安装源码和53固定依赖一致；mypy85检查93文件通过，Ruff及格式85通过。两轴最终剩余0，初次发现与处理分别保留于[审查记录](verification-gdp-review-85.md)。默认全套尚未复验，本批未提交。

## 保留的未完成项

本次合成审查仅验证软件准入，未授予真实GDP来源认证。GDP跨公告YTD修订基线、信用脉冲全部父项原件消费、完整候选/120交易日重放、真实合格AI报告及切换仍未完成。SQLite锁故障根因仍开放，最近默认全套1146通过/2失败的记录不改写。本批未提交。
