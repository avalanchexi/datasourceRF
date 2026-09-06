# 02 核心采集原件与双点时

实施基线：`f5c88befe1a8ea4056ebc8aba54b735c2ccd6e59`。范围：[02](issues/02-core-acquisition-receipts.md)。实施、最终检查和两路代码审查均已完成。

## 行为与证据边界

核心历史刷新和手动完整运行的核心日刷新共用 `refresh_core_history`。每次日历/价格 HTTP 请求先登记脱敏身份，保留实际响应 bytes、标准化 CAS、解析器版本、请求开始/接收/校验时间，并把成功声明关联到请求收据。日历拒绝越界或重复日期；价格沿用真实代码、单位、期次及质量校验。

接收完成时先持久记录时间，再保存原件；磁盘失败保留已知接收事实。解析或制品失败不产生声明，批量声明与收据链接在一个事务内写入。`available_at` 在响应、解析和声明校验后记录，请求中的 SYSTEM cutoff 看不到新声明。HTTP 错误正文可保留，普通失败记录异常类别，进程中断可能留下 started/received，不能当作验证成功。

不再为核心历史和日刷新生成固定 15:30。真实 TuShare 核心响应没有可靠发布时间字段，新的 `release_at/public_available_at` 均保持未知：PUBLIC 不可选，SYSTEM 仍按既有模型认证和质量规则选择。`publication_times` 只执行已可靠解析时间的保守转换：精确时刻保持原时刻，仅日期从来源本地次日零点开始，未知为空；它不认证来源。本票合成领域测试验证转换及查询边界，[04](issues/04-core-public-time-certification.md) 才接入真实官方解析与历史时间证据。

证据查询可返回 `linked/partially_linked/untraced/not_visible` 和关联收据。`GET /api/v1/acquisitions` 包括未产生声明的失败请求；`GET /api/v1/acquisitions/{id}/artifacts/{raw|normalized}` 核对哈希后返回原件。旧 0013 库在升级前仍能只读证据/空收据索引；0014 只增加请求与声明关联表，不倒填历史原件、改写旧声明或修改旧快照。

本票未访问真实外部渠道、迁移生产库、创建生产候选、完成来源认证、正式回放、模型激活或系统切换。旧 v3 隔离继续生效。迁移和 Worker 测试仅使用 WSL 原生专属隔离目录。

## 验证过程

- PUBLIC unknown 反例先失败：旧路径按固定 15:30 选到新声明；修复后 PUBLIC 空、SYSTEM 有值。
- 手动任务 → Worker → 仓库真实入口反例先失败：请求期间 SYSTEM cutoff 曾选到 160 条新声明；修复后为零，完成后为 160。仅替换外部 HTTP transport。
- 原件/API、失败请求、旧 0013 只读与升级兼容、untraced 状态均经过先失败再修复。保留原始 bytes 中的空白，不以重序列化 JSON 冒充 HTTP 原件。
- 原件写入及批次标准化写入失败均不留无依据声明；旧 cutoff 的规范 JSON 前后相同。
- 审查补充负例先得到 3 failed / 1 passed：越界日历被错误接受、重复日历未在请求边界拒绝、原件写入失败丢失 received_at。修复后最终该文件 **13 passed in 6.71s**。
- 精确时刻和仅日期正例使用明确 synthetic 来源声明走 EvidenceRepository 双点时入口；不是官方样本，不可计入来源认证。
- 验证环境曾安装旧包，首次恢复检查因缺少 acquisition 模块收集失败；重新离线安装后再验证，该环境错误不计为业务 RED。

[验证脚本](verification-02/verify.py) 与 [检查收据](verification-02/checks.json) 记录安装包、Ruff、mypy、完整 pytest 和最终应用/测试文件 SHA256。最终完整 pytest **430 passed in 117.51s**；Ruff 通过；mypy **70 个源文件通过**。全套后应用源码未再修改，收据中 9 个文件指纹均已复核。

## Standards

初审 1 项明确问题：手工时间元数据加任意已登记 CAS 可使声明 PUBLIC 可见，不符合可靠公开时间要求。已删除整条手工注入入口和关联证明字段；官方 parser 由 04 承接。只读增量复审：**0 项明确违规，0 项 smell**。

## Spec

初审 3 项：请求日历区间校验、CAS 失败时接收时间留存、手工发布时间证明过宽。全部已修复并独立复审：**0 项剩余问题**。两轴均使用 `git diff --cached f5c88be --` 审查暂存实现，未把测试模型运行当作生产认证。

审查汇总：Standards 0 项；Spec 0 项。测试结果与完成状态以最终收据和票据为准。

## 后续

02 完成后前沿为 03、04、15、18；继续 03 上下文采集，覆盖抓取时间回填公开时间、官方/TuShare 原件关联和追加版本。来源缺证、业务规则、检索实际效果及真实模型切换仍在所属票中未完成。
