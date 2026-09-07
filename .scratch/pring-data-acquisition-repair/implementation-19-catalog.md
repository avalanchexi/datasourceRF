# 票 19：不可变目录登记与实际消费

状态：本批代码与获取准备已验收，完整票19仍in-progress。固定基点 `0679a4758316bbeb520da9d79aafeb7572f5c6ce`。

沿用已确认的公开准入 CLI、真实 CAS/模型/证据仓库及 PUBLIC/SYSTEM/投影入口。先用两个各自有效且重新审查的请求，复现同一目录版本被不同定义占用；目录登记必须与候选创建共用事务，同版本同内容幂等、异内容拒绝，失败不留新候选或可解析的半成品目录。

随后用现有 LPR fixture，经新候选的登记目录进入公开导入、真实来源声明、双点时查询、模型选值和上下文投影。所有数据库和原件使用 WSL 原生隔离 runtime；只替换既定外部 transport/时钟/CLI 子进程，不 patch 目录或内部验证器。

默认静态目录和历史 v3 隔离保留；通用 ModelRepository.create_candidate 不自动登记或认证目录，生产 Worker 仍只执行 active 模型。实际来源认证、市场规则、历史 PUBLIC、检索配对和真实重放/切换仍按原票验收。

## 已实现的合同

- 0019 迁移新增登记表。正式准入的模型写入与目录登记共用 BEGIN IMMEDIATE 事务；同版本同内容可供不同模型使用，顺序不影响目录身份，同版本异内容拒绝并回滚候选。
- 动态目录仅从指定运行库读取，校验定义 hash 和登记时不可变模型清单；普通模型创建不登记。模型选值及上下文在读取前核对绑定，拒绝未登记或异定义借用。
- 新目录实际接通 **LPR 一个家族**：原文获取收据、声明、PUBLIC/SYSTEM、选值、上下文。现有解析器必须匹配已登记的来源、维度、主单位/允许单位、频率和发布规则，声明 provider/月/tenor 也须一致。只支持 percent；不做 basis_points 转换。其他新目录家族的 certified 输入明确报 source contract not implemented，须逐家族另接通，不因目录登记自动认证现有解析器。
- 新增 13 个公开行为用例；采用真实准入 CLI/仓库，不新增内部 patch。旧 4 个测试文件仅同步既有替身签名并转发 database_path；另1个升级测试构造旧库时移除新目录表，数据保留断言不变。

## 验证过程与已纠正的执行问题

同版本异定义实际 RED：1 failed；首轮准入 GREEN：51 passed / 45.29s。新目录 LPR 原先在官方导入报 unknown_metric_definition_version，后续完成纵向取值。上下文未登记/错绑定及未知定义字段 RED：3 failed / 2 passed。来源/规则/provider RED：3 failed；允许单位 RED：1 failed。以上均已修复，最后来源针对性 5 passed / 6.35s。

第一次 LPR GREEN 的最后断言误以为无 active 返回 None，真实接口抛 active_model_unavailable；更正测试断言，没有修改生产接口。第一轮关联 21 failed / 70 passed 是旧替身签名未兼容新增参数。一次 PowerShell→python -c 字符串替换未匹配含引号内容，还误撤掉目录 fallback，第二轮关联 23 failed / 100 passed；随后改为可核对独立脚本/apply_patch，恢复 fallback 并确认实际差异。第三轮关联 **126 passed / 91.31s**；此后新增的单位反例单独红绿验证。

应用及新增测试 mypy **85 文件通过**。扩展到旧测试出现29条类型诊断，已用固定基点旧文件逐条比较，诊断集合完全相同，见 [比较收据](verification-catalog/legacy-typing.json)；不把这次扩大检查说成全库类型清洁，也不为通过而删断言或屏蔽诊断。

Spec 初审1项来源绑定、复审1项允许单位，均已关闭；Standards 的目录 fallback 回退与单位遗漏也已关闭，最终两轴均0。第二轮全套 **819 passed / 0 failed / 852.83s**；应用源码及安装包84个Python文件在最终测试前后核对一致。见[最终收据](verification-catalog/final.json)。

第一轮全套已结束：**817 passed / 2 failed / 851.10s**。失败为旧库模拟未移除0019新表，以及另一个v1目录替身未接database_path；仅修测试构造/签名，应用源码不变。迁移及模型生命周期复测 **34 passed / 36.70s**。两处失败现场复制到项目 `.tmp/catalog-failed-full-01`，确认原pytest已终止后只清理本批指定basetemp的401,319,457字节，见 [清理收据](verification-catalog/failed-suite-cleanup.json)。第二轮在新basetemp结束且819全过；第一轮失败日志保留，不覆盖为成功。

## 真实 LPR 材料的独立进展

[认证矩阵](lpr-certification-gap-matrix.md)根复核13输入、9原件、39本地引用、18字面值。研究实际2次官方GET均200，其中新基准页响应尚未登记CAS，只作研究记录，不冒充正式包原件。已有9期原件共92,717字节。

通过已安装应用的公开 AcquisitionRepository.capture，对9份真实原件在全新 WSL 隔离库执行 document_import，生成9份本次真实取得/校验收据和18个 raw/normalized 导出文件。独立标准库只读对照库记录、旧原件、导出hash、时钟和18个值通过；source_claim与registered_metric_catalog均为0。见 [收据](evidence-lpr-import-20260908/receipts.json)和[核验](verification-catalog/lpr-import-verification.json)。未调用网络、未生成已认证声明或候选，不恢复历史SYSTEM，不替代PUBLIC版本审查。执行指纹单独保留，后续源码变化不得改写此准备包。

下一步继续正式 LPR semantics/fields/history/time 与实际用途依据收口，并按原依赖推进其余家族；完整票19、真实检索、报告、固定120日重放及切换均未完成。

第二轮全套期间，另进行2次北交所官方域检索，未发现2026-08-28市场融资余额的新官方入口；新增正文读取0、有效目标样本0，未重复旧失败URL，未新增泛化报告。该结果不证明数据不存在，也不计Tavily/Exa配对分母。
