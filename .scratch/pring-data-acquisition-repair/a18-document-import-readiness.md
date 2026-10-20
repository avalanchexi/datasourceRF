# A18 原件本次 document_import 可执行性与证据边界

研究日期：2026-09-09，Asia/Shanghai。类型：只读源码与已存材料研究；本次 capture 未执行。
读取基点：HEAD `99c495a217b66d4bca9d6ceae4688ee69d4382bb` 加当前工作树；关键输入的实际字节指纹见文末。
本研究仅新增本文；应用调用、测试、安装、数据库/SQL、网络、认证及模型操作均为 0。取证开始时主线有独立测试会话，本研究没有启动第二个应用进程。

**现有材料足以在主线应用进程结束并核对安装源码后，实施 A18 本次真实 `document_import` 获取准备。公开 `AcquisitionRepository.capture` 不要求来源声明、来源认证、新指标目录或候选模型。应按 268 个“原件 SHA + 家族 + 期次”分别取得收据，保留 250 份不同原件。Q1 产能的源字段映射待定应原样保留；它不是阻止保存本次原件及解析结果的条件。** 这是一项尚未执行的可达性结论，不能报作已有 268 张成功收据或模型可用输入。依据：[capture 入口](../../src/pring_cycle/acquisition.py#L125)、[公开官方解析器](../../src/pring_cycle/official_context.py#L200)、[A18 准备包](evidence-13-preparation-v2/preparation.json#L1888)。

有一处不能直接照搬 LPR 脚本：它调用的 `initialize_runtime` 会预置三个历史内置候选模型。若本批明确要求“模型记录新增 0”，应在新隔离运行目录仅通过公开 `storage.migrate_database` 建立表结构，再调用 capture，不调用运行时 bootstrap。新模型既不是 capture 的参数，也不是它的前置条件。[LPR 初始化](verification-catalog/import_lpr_originals.py#L34)、[运行时 bootstrap](../../src/pring_cycle/runtime.py#L251)、[公开迁移入口](../../src/pring_cycle/storage.py#L31)。

## 已有材料的本次只读核对

本次以 Windows 标准库读取 JSON、源码 AST 和精确文件字节，没有导入 `pring_cycle`、执行准备脚本或连接数据库。

- 准备包仍为 **3,189,072 字节**，SHA256 `92f44dbb435ea56fd1b08813373f4abf4749d76db33f364547098e290fb58034`。
- 实际读取准备包登记的 **250/250** 个 WSL CAS 文件，逐件 SHA 和字节数与清单相符，合计 **20,069,217 字节**；11 份绑定审计报告也全部重哈希相符。原件路径来自包内 `data.raw_artifacts[].cas_path`，读取时仅将 `/home/tywin/` 映射为 Windows 可读的 `//wsl.localhost/Ubuntu-22.04/home/tywin/`。
- 268 个结果均能按 `artifact_sha256` 关联唯一原件；原件/结果的 `source_url` 与期次、解析对象的家族/期次/URL、`official:{family}:{period}:{raw_sha}` 发布身份全部一致。268 个三元身份无重复。239 份原件对应一个家族、4 份对应两个、7 份对应三个；因此不能把 250 当作解析收据数量，或合并同一月份的不同社融原件。
- 准备包的 250 个历史 `acquisition_time` 和 268 个 `system_acquisition_time` 仍全为 `null`；本研究没有修改这些字段。1858 个值中 **1857 个严格字面匹配、1 个 Q1 源映射待定** 的原审计分类保持不变。
- LPR `receipts.json` 仍有 9 个 `validated` 收据；独立重哈希其导出的 18 个原件/规范化制品，9 份原件共 92,717 字节。本次未重新读 LPR 数据库；“数据库行与回执匹配、source_claim 和 registered_catalog 均为 0”属于已有独立验证记录的结论。

数据来源：[A18 说明](p1-official-preparation-v2.md)、[原件目录](evidence-13-preparation-v2/preparation.json#L2453)、[家族汇总](evidence-13-preparation-v2/preparation.json#L10545)、[已有根验证](evidence-13-preparation-v2/delivery-verification.json)、[LPR 收据](evidence-lpr-import-20260908/receipts.json)、[LPR 已存独立验证](verification-catalog/lpr-import-verification.json)。上述本次复核只证明已存材料完整，不重复授予字段、来源或历史时间认证。

| 家族 | 本批调用/预期收据数 | 期次范围 | 标量数 |
|---|---:|---|---:|
| `nbs_capacity_utilization` | 3 | 2025-Q4—2026-Q2 | 9 |
| `nbs_core_cpi` | 8 | 2025-12—2026-07 | 46 |
| `nbs_industrial_finance` | 7 | 2025-12—2026-07 | 70 |
| `nbs_industrial_value_added` | 7 | 2025-12—2026-07 | 20 |
| `nbs_pmi` | 7 | 2026-01—2026-07 | 56 |
| `nbs_ppi` | 8 | 2025-12—2026-07 | 69 |
| `pbc_loan_structure` | 31 | 2024-01—2026-07 | 279 |
| `pbc_money` | 7 | 2026-01—2026-07 | 28 |
| `pbc_omo_notice` | 131 | 2026-02-24—2026-08-28 | 252 |
| `pbc_social_financing` | 51，覆盖 31 个月 | 2024-01—2026-07 | 837 |
| `pbc_tool_liquidity_monthly` | 8 | 2025-12—2026-07 | 192 |
| 合计 | **268** | 各家族按真实频率 | **1858** |

表中为准备包实际范围，不表示 120 个中国交易日输入完整。社融同月不同发布原件各自保存；OMO 的 131 个金额和 121 个利率意味着部分零操作公告没有利率成员，不能补出 10 个 0% 值。[家族汇总及特殊情况](evidence-13-preparation-v2/preparation.json#L10545)、[原准备特殊值核对逻辑](evidence-13-preparation/prepare.py#L246)。

## 必须具备的依赖与不需要的前置

| 项目 | 本次 document_import 所需条件 | 一手依据 |
|---|---|---|
| 运行版本 | Ubuntu 原生 Python 3.12；使用已锁定依赖及当前安装包，执行前核对工作树/安装源码。研究不启动安装或重解析 | [Python 约束](../../pyproject.toml#L10)、[旧准备执行身份检查](evidence-13-preparation/prepare.py#L132) |
| 原件身份 | 固定新旧准备包 SHA，逐次读原 CAS 的完整 bytes，再核对本次 receipt.raw_hash；导入中不能以新下载页面、摘要、清洗后的文本替代原件 | [原件清单](evidence-13-preparation-v2/preparation.json#L2453)、[capture 接收与原件保存](../../src/pring_cycle/acquisition.py#L188) |
| 路径与表结构 | 全新、明确隔离的 WSL 原生运行根；拒绝已存在的本批路径。数据库及 CAS 不放 `/mnt` 或源码树，交付 JSON/原件副本仍放仓库 `.scratch/`。通过公开迁移建立表 | [RuntimePaths](../../src/pring_cycle/runtime.py#L23)、[迁移](../../src/pring_cycle/storage.py#L31)、[原件表](../../src/pring_cycle/migrations/versions/0001_runtime.py#L16)、[获取表](../../src/pring_cycle/migrations/versions/0014_acquisition_receipts.py#L19) |
| 官方身份 | `family`、`source_url`、`expected_period` 来自同一结果记录；provider 来自相应公开家族描述，解析器再次检查官方 HTTPS 域、路径、期次及字段 | [家族描述](../../src/pring_cycle/source_families.py#L14)、[公开解析](../../src/pring_cycle/official_context.py#L200)、[URL 校验](../../src/pring_cycle/official_context.py#L2064) |
| 规范结果 | 调用当前公开 parser 后 `normalize=asdict`；标准化保存完整 `ParsedOfficialContextRelease`，不用准备报告里的带注解 JSON | [解析对象](../../src/pring_cycle/official_context.py#L113)、[规范化写入](../../src/pring_cycle/acquisition.py#L226)、[完整回执重建校验](../../src/pring_cycle/official_context.py#L259) |
| 实际时钟 | capture 使用真实 UTC clock；逐请求记录 started、received、validated，单调非降；解析 fetched_at 取该次实际 received_at，或单列实际解析调用时刻，绝不采用旧准备的研究 clock | [clock 默认及顺序](../../src/pring_cycle/acquisition.py#L125)、[时间检查](../../src/pring_cycle/acquisition.py#L328) |
| 结果保存 | 保存实际 history 中成功/失败收据、导出原件和规范化字节、三元身份、当前执行指纹、准备包与审计状态的引用。失败保留，不把重试覆盖为一次成功 | [history/read_content](../../src/pring_cycle/acquisition.py#L296)、[失败状态](../../src/pring_cycle/acquisition.py#L251)、[终态不可变触发器](../../src/pring_cycle/acquisition.py#L392) |

**不需要的前置**包括新 registered catalog、模型 manifest/激活、来源声明、来源认证 grant、生产数据库、Tavily/Exa/API key、外网 smoke 或新 HTTP GET。capture 在没有 `own_acquisitions` 上下文时不查询 parent_run 或模型，只操作获取与制品记录；官方纯 parser 也不查目录数据库。[capture 的 owner 条件](../../src/pring_cycle/acquisition.py#L146)、[纯解析函数](../../src/pring_cycle/official_context.py#L200)。

为严格维持模型记录新增为 0，应使用公开 `migrate_database` 而不调用 `initialize_runtime`。当前迁移创建包括空模型表在内的 schema；`0002` 读取的六段 schema 经本次 AST 静态核对均没有 INSERT，迁移目录未发现 `create_candidate`/`ModelRepository`/INSERT 调用。真正预置三个候选的动作在 `runtime._bootstrap_v1_repositories`。该差异只影响初始化选择，不要求修改应用或直接执行手写 SQL。[0002 迁移](../../src/pring_cycle/migrations/versions/0002_v1_domain.py#L34)、[运行时预置](../../src/pring_cycle/runtime.py#L267)、[模型创建实际写入](../../src/pring_cycle/models.py#L288)。实际执行后仍应独立核对 source_claim、registered_metric_catalog、model_version、model_activation 等表记录为 0，不能仅凭本研究静态结论填写计数。

`execution_fingerprint(paths)` 不传 model_version_id 时只记录代码、依赖、配置版本标签和数据库 revision，不需要模型实例；新运行应绑定当前指纹，不能借用旧 LPR 或旧准备的指纹。[实现](../../src/pring_cycle/runtime_fingerprint.py#L13)。

## 268 次公开调用的完整关联方法

这是执行契约，不是已运行脚本，也没有在研究中调用这些接口：

1. 排他创建新的本批运行目录和交付目录；验证准备包、250 原件及 11 审计指纹。以 `data.results` 的 268 项为迭代单位，关联 `data.raw_artifacts` 获取真实 CAS 路径；不能按月份或 provider 去重。
2. 每项使用 `AcquisitionRepository.capture(provider=该家族 provider, api_name="document_import", parameters={family, source_url, period, imported_from, preparation_sha256}, fields="", parser_version="official-context-parser-v0004", fetch=原件文件读取, parse=当前公开官方 parser, normalize=asdict)`。额外 lineage 参数不改变当前 replay 的 family/source_url/period 合同。不要使用 LPR 的 `fields="1y,5y_plus"` 或 LPR parser 版本。[当前官方回执合同](../../src/pring_cycle/official_context.py#L259)、[官方 capture 既有组合](../../src/pring_cycle/official_context.py#L371)。
3. 若要精确使用本次 received_at，利用公开 `on_started` 保存本次 acquisition_id，在 parse 回调通过公开 `get(id)` 读取已接收回执，再把它的 received_at 传给 `parse_official_context_document`。回调先核对实际传入 raw 的 SHA/字节数与固定输入一致，避免仅预检查文件后又读到不同内容。capture 是先 `_receive` 再 parse，此处没有模拟时钟，也不依赖源页面历史时间。[capture 调用顺序](../../src/pring_cycle/acquisition.py#L177)、[get](../../src/pring_cycle/acquisition.py#L285)。
4. 成功后从仓库重新读取回执与 raw/normalized，核对三个 clock、两个 SHA、完整规范对象，并用公开 `parse_official_acquisition(receipt, raw)` 重建。它会验证官方 provider/家族/期次、parser v0004、fields 为空以及规范化 SHA。导出的制品保持原始字节；同一 raw hash 可由多张收据引用，不能因此丢失家族或期次关联。[read_content](../../src/pring_cycle/acquisition.py#L303)、[重建验证](../../src/pring_cycle/official_context.py#L259)。
5. 将准备包中的逐值审计注解作为旁路审计记录绑定，保留对应 scalar 身份与 Q1 pending，和当前 parser 的规范结果分别保存。终态记录本次导入成功/失败数、250 原件覆盖、268 调用身份覆盖、实际标量数与原准备的比较；只有真实计数全部符合时才称 completed_acquisition_preparation。

`ingest_official_context_document` 会在 capture 后继续调用 `ingest_acquired_official_release`，后者创建来源声明并涉及定义版本，因此本批“只要获取收据、不创建声明”的执行应停在 capture 及只读重建校验。无需为使用该便捷 ingest 函数而先制造一个目录。[入口后半段](../../src/pring_cycle/official_context.py#L382)、[声明入口](../../src/pring_cycle/official_context.py#L387)。

## 规范化兼容问题必须在新脚本中明确处理

旧准备的 JSON 不是 capture 可直接采用的 normalized 文档。

- 当前 `ContextScalar` 有 13 个公开字段，完整 release 有 8 个字段。准备包为每个 scalar 额外增加 **5 个研究字段**：`independent_period_binding_status`、`field_unit_dimension_shape_status`、`independent_review_status`、`independent_review_report`、`review_scope`。这些注解不是 parser dataclass 的一部分；把它们混入规范制品会使后续 `parse_official_acquisition` 的规范化 SHA 不匹配。[ContextScalar](../../src/pring_cycle/tushare_context.py#L78)、[旧准备注解](evidence-13-preparation/prepare.py#L213)、[v2 审计注解](evidence-13-preparation-v2/prepare.py#L72)。
- 准备 helper 把 datetime 变成带 `T` 的 ISO 字符串；capture 用 `json.dumps(default=str, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)`，datetime 通常成为空格分隔的字符串。新规范制品须沿用 capture 与重建器的一致序列化；和研究准备的逐字段比较可仅对时间表达做无损规范化，不能要求两个不同职责 JSON 字节相等。[准备的 normalized](evidence-13-preparation/prepare.py#L40)、[capture 序列化](../../src/pring_cycle/acquisition.py#L229)。
- `prepare.py` 默认重算比较整个 `data`，其中有旧 `code_identity.files`。本次只读重哈希发现旧包登记的 81 个源码中 32 个当前原始字节指纹已经不同；这是精确指纹差异统计，不等于 32 项语义回归。直接运行旧 v2 默认全对象比较不能作为当前 capture 前置通行证，更不能覆盖旧包或还原修复来满足它。新脚本应绑定当前源码，再把实际解析的 13 字段/8 字段对象按完整身份与旧准备比较，明确记录任何数据差异。[旧代码身份](evidence-13-preparation/prepare.py#L102)、[v2 默认比较](evidence-13-preparation-v2/prepare.py#L119)。

本次没有运行 268 次当前 parser，因而不声称其当前重解析已全部通过。完整再解析将自然发生在各次 capture；当前解析失败或值/成员/期次变化时，应留下本次失败证据或差异结果，不能把历史成功状态当成本次结果。

## Q1 源映射、PUBLIC 与 SYSTEM 的不同结论

Q1 待定项精确身份为：原件 `0c66284a8d0420a6168c432e87e7e4ee31bf4002896634e5253780d928cdb02a`，`nbs_capacity_utilization / CN_CAPACITY_UTILIZATION`，`industrial_capacity_utilization_ytd_pct`，`year_to_quarter`，2026-01-01—2026-03-31，`industry=all_industry, measure=ytd_rate`，73.6%。原表只给一季度率；当前实现把同区间当季值复用于累计值，原审计没有把它计为独立累计源格。[准备中的待定项](evidence-13-preparation-v2/preparation.json#L64045)、[原字段审计](p1-capacity-utilization-full-value-audit.md#L55)、[既有复用实现](../../src/pring_cycle/official_context.py#L1274)。

capture 可以保存这份原件和当前 parser 的完整输出，其 `validated` 只说明该次获取经过传入 parser 和规范化函数成功完成。它不会检查外部审计注解，也不会自动生成 `source_field_certification_mapping_pending`；新交付必须明确旁挂这项状态。不得因 acquisition validated 把 1857+1 改为“1858 独立官方字段认证通过”，也不应为让导入全绿而删掉 Q1 标量或修改原件。[capture 验证范围](../../src/pring_cycle/acquisition.py#L197)、[v2 保留待定](evidence-13-preparation-v2/prepare.py#L68)。

| 时间/认证事实 | 本次导入能够形成 | 仍然不能声称 |
|---|---|---|
| 本次 started/received/validated | 本次真实从旧原件文件读取、解析、规范化完成的获取收据 | 原件在 2024—2026 年相应历史日期已被本系统取得；文件 mtime、旧研究 clock 也不能补造 |
| 历史 SYSTEM | 保留旧 `acquisition_time=null` 与新导入 clock 的两条事实 | 没有来源声明时，不存在新增 SYSTEM 查询观测；即便以后纳入声明，也不能倒填成历史 SYSTEM |
| 页面 release/public 候选 | 原件中的页头时间及当前 parser 解释，可与该 raw hash 一起审查 | `validated` 不证明首发版本、修订链或页头适用于当前内容的历史 PUBLIC 资格 |
| 来源与使用资格 | 更完整的获取及规范化证据，供后续正式认证使用 | 新 grant、来源认证包、指标目录认证、模型可用缺口补齐或候选通过 |

领域依据：[CONTEXT 的证据/时间/来源认证定义](../../CONTEXT.md#L155)、[双点时 ADR](../../docs/adr/0006-dual-as-of-and-immutable-evidence-vintages.md)、[模型回放 ADR](../../docs/adr/0012-atomic-model-versions-and-parallel-replay.md)。因此本次工作可以独立推进，完成后应报告“268 次本次 document_import 获取准备（以实际结果为准）”，继续保留 Q1 映射、历史 PUBLIC/SYSTEM、来源正式认证和完整模型验收的开放状态。

## 只读输入指纹

以下为本研究实际读取时的原始字节 SHA256，供主线检查研究所依据的版本；不是新导入运行指纹。长 JSON 的完整字节已按上文重核，不通过重写或清洗获得。

| 文件 | 字节 | SHA256 |
|---|---:|---|
| [A18 说明](p1-official-preparation-v2.md) | 2841 | `6623bd19acee525d3a2a18eec7749e908bf28e17b52e6f6012c92f4a7291b688` |
| [v2 准备包](evidence-13-preparation-v2/preparation.json) | 3189072 | `92f44dbb435ea56fd1b08813373f4abf4749d76db33f364547098e290fb58034` |
| [v2 helper](evidence-13-preparation-v2/prepare.py) | 6911 | `b89cce9dd8435851af48414ecdd6704702ba2914212582436675f49deef80f16` |
| [原 helper](evidence-13-preparation/prepare.py) | 18456 | `e9295dcd722d9ff1f67e9fb0e57db6154c297510f80df344258b69971f638b27` |
| [LPR 回执](evidence-lpr-import-20260908/receipts.json) | 15463 | `31e1572983801245e76e1b4c33f57616029ba14bc304d2a276b9c1d1977d2d22` |
| [LPR 导入脚本](verification-catalog/import_lpr_originals.py) | 4716 | `a95c9e467df4dc54f0be38c7762357b39fc37a91c0ef8791b0e84953c6385db1` |
| [LPR 独立验证脚本](verification-catalog/verify_lpr_import.py) | 3232 | `aa4341c56cd9254eba57cc3bf2dbdbea71f7bb7f6637ea5eee597fdbc57bd6f2` |
| [LPR 已存验证结果](verification-catalog/lpr-import-verification.json) | 335 | `332e608b74e749f1b39b102eba69821571ae277c76d9eb2d3d31cd0a8966f729` |
| [产能源值审计](p1-capacity-utilization-full-value-audit.md) | 13203 | `5cce581124ccb722782eb94e6aef5a48bd36faa78d4396ec41568f49feeeb9ed` |
| [获取仓库](../../src/pring_cycle/acquisition.py) | 14584 | `ed81eef2b153417009c0beb356be64bbe8fd164a9f3ea0d6eafe9cdc66ad69f8` |
| [官方解析及入库](../../src/pring_cycle/official_context.py) | 84300 | `fb0a54664e8582a2c00ee00b790a7d4d9cb6cda162c69e6dfc3f077bf9f56b11` |
| [运行路径和初始化](../../src/pring_cycle/runtime.py) | 9257 | `30ffd317f672cd948f519771b04e7fd5814d354e02eef72d6ae3a5895c4874ca` |
| [迁移公开入口](../../src/pring_cycle/storage.py) | 7191 | `ef947dab6fc589e8efb4f121f77f4237566f23492cee6351ade035ea66874401` |
| [CAS 制品](../../src/pring_cycle/artifacts.py) | 3022 | `114427470f2c3f8140eb22d214465620e99a1b2a7baa8c3c1717b8ba4e750ea4` |
| [标量结构](../../src/pring_cycle/tushare_context.py) | 76846 | `5a642d4a7275c8991d76f6e5ec24f271ff1fc8693e213fc7abeca26d0602c443` |
| [官方家族](../../src/pring_cycle/source_families.py) | 2487 | `420a241b90fc0ff63cafe5e9119f15a375e90617834cae2698e403ccbcaa5f6e` |
| [执行指纹](../../src/pring_cycle/runtime_fingerprint.py) | 2775 | `d5976a3fe7530a27262dedbab4f763c259e296faa478cf82e72bb69f689ce46e` |

交付仅为本 Markdown；没有创建 import 脚本、新运行目录或导入结果文件。实际执行与终态数据库检查由主线在现有应用会话结束后进行。
