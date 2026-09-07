# 新候选正式包准入契约

本入口交付票 19 的软件校验能力；尚无实际来源材料通过本协议。本批合成正例不产生生产认证，也不代表新目录的真实采集、目标日可用性、重放、报告或切换已通过。

## 入口和信任边界

`model-source-certify --candidate-request-hash <sha256> --target-date <日期> --confirm-personal-noncommercial` 消费指定隔离或正式 runtime 的 CAS。请求哈希与旧 `--source-smoke-hash` 互斥。旧路径仍执行 v3 否定性审查；新路径也检查清单及定义不得引用被隔离版本。命令本身不联网、不生成审查、不抓取 URL、不激活模型。

正式审查记录由本地受信维护流程提供，必须来自实际完成的语义、字段、历史、时间、权限和使用许可审查。机器验证记录是否完整、引用内容是否存在、身份与定义是否一致；不会阅读一个 `accepted` 字符串就推断官方真实性、许可合法性或历史 PUBLIC 时点。此接口不是签名认证系统，不能防御有权篡改本地运行库的维护者。真实家族审查仍须按 ADR0013 的官方样本流程完成。

## 请求和内容身份

请求 JSON 使用 `source-certified-candidate-request-v0001`，包含 `target_business_date`、`manifest` 和非空 `package_hashes`。哈希均为完整小写 SHA-256，按 CAS 原始字节读取核验。被审查的清单不包含系统生成的 `model_version_id`、`source_certification_packages`、`certification_request_hash`，也不接受旧 `source_certifications` 标签。

清单含全部 61 个指标定义、原有优先级/角色、三核心映射、趋势和六阶段映射、选择/点时/窗口/重放版本、全部八个派生公式、执行指纹及日期范围。每个定义的版本必须与新目录一致。三核心与 42 个 P1 均需正式包覆盖；P2 可保持 `awaiting_source_certification`，只有声明认证的 P2 才要求包覆盖。三个 P0 运维目录项不被计入 45 个标量来源的覆盖检查；此命令不制造任何运维或标量观测。

规范化 JSON 哈希使用 UTF-8、`ensure_ascii=False`、`sort_keys=True`、`separators=(",", ":")`，拒绝非有限数值。原件自身哈希始终针对存储的原始字节，不能以规范化 JSON 的哈希冒充。

正式包 `source-certification-package-v0002` 恰含以下字段：

| 字段 | 含义 |
| --- | --- |
| `schema_version` | 上述正式包版本；准备包和旧 smoke 包不能代替 |
| `definition_bindings` | 指标 ID → 完整定义的规范化 JSON 哈希 |
| `manifest_hash` | 请求中完整清单的规范化 JSON 哈希 |
| `certified_from` | 已审查的来源认证起日；不能晚于候选正式回放起日 |
| `review_hash` | 正式审查记录的 CAS 原始字节哈希 |

包 ID 由实际包哈希生成，不接受调用者覆盖。其审查对象是 `definition_bindings`、`manifest_hash`、`certified_from` 三字段组成的对象。

审查 JSON 使用 `source-certification-review-v0001`，包含该对象的规范化 `subject_hash`、非空 `reviewer`、带时区的 `reviewed_at`、`decision=accepted`，以及六项 `assessments`：`semantics`、`fields`、`history`、`time`、`permissions`、`usage`。每项须有非空 `finding` 和非空 `evidence` 列表。每个引用含 `artifact_hash` 和 `source_reference`，内容须非空、哈希正确，且该来源引用须已在真实制品登记中关联同一哈希。单一原件可支持多项审查；不要求每个历史观测重复双源采样。

## 运行约束与结果

新入口只接受当前实现支持的强化规则：`selection-v0001`、`public-cutoff-v0002`、`exact-core-calendar-120-v0001`、`active-baseline-exact-120-v0001`。趋势明确绑定 `candidate-duration-v0002`，120 日窗口及合法参数；阶段映射保持既有六阶段。公式版本由上下文规则的支持集合核验，八个必需公式均须存在。频率仅接受当前运行时支持的日、月、季和事件型值。

执行指纹必须与提交时安装代码、依赖、配置和数据库版本一致。正式回放不得早于 2026-03-09 或晚于目标日，长期核心校准从 2018-06-01 开始。来源包认证范围还需覆盖回放起日；这些检查不能证明实际历史输入已齐备，也不会重建未知 PUBLIC 时间。

全部验证结束后才写入一个内容寻址的 `model-reviewed-…` 候选，并保存原请求身份和包内容。相同请求幂等；定义、规则、执行身份或证据变更需重新审查并形成新身份。通过 `models` 命令及 `ModelRepository.manifest` 可读取候选。已有生效指针和已发布投影保持原样。

新定义在实际采集、选值与重放中的接入仍需后续票 19 实施与真实验证。本批没有登记新的生产目录，没有补写正式来源声明，没有将所有未知时间或缺口变为可用。
