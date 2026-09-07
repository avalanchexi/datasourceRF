Execution: research-complete / implementation-not-started

# OMO 缺失投放、到期与零现金流边界

2026-09-08（Asia/Shanghai）。只读静态研究；没有执行应用、访问网络、查询生产库或修改代码。唯一交付为本文。读取时 HEAD 为 `375950b03a0a3ac73c21135a28e283c10afe1030`，工作区包含正在验收的贷款一月修复；下列源码行号及指纹绑定该工作区，不代表纯 HEAD 内容。

## 结论

不能仅因 `injection=None` 或到期集合为空就一概删除零现金流语义。既有 v2 公式和公开测试明确保留了“仅有到期，输出净回笼”的实现契约；但当前代码没有区分**已证明当天没有操作**、**没有取得操作**和**已经取得但不合格的操作**。前者可以具有零投放的经济含义，后两者不能凭空获得这个含义。

已确认的窄缺陷是：目标日已有不合格投放证据时，预先过滤使它与“没有这一条”完全相同，随后有效到期量仍产生 `current` 净回笼。更广的“完全没有记录能否视为无操作”、空到期集合能否证明零到期，需要台账覆盖和适用日历证据；不能靠旧 fixture 名称或 `certified` 标签证明。本文不新增这种业务规则，也不判定任何生产目标日的真实净额。

## 本地规范与既有契约

- [CONTEXT.md:157–179](../../CONTEXT.md#L157)：派生观测必须由冻结公式和明确输入生成；“尚未发布或获取失败不是合法报告值，也不能用0替代”，并区分已发布未披露。
- [修复规格:47、96–100](spec.md#L47)：获取失败不能成为零值；来源/定义认证、数值有效及点时可见是分别成立的条件。
- [票13:18–21](issues/13-remaining-p1-evidence.md#L18)：检查必要历史基线、最小预热、同期输入和派生血缘，区分已取得、认证、可用、被采用。
- [旧政策票:9–15](../pring-cycle-dashboard/issues/10-policy-action-transmission.md#L9)允许操作量/到期量/净投放，同时要求点时、时效和冲突规则；未授权把未取得或冲突输入当成零。
- [原来源研究:73–77](../../docs/research/official-gap-source-audit.md#L73)要求按操作日/期限及交易日规则复核到期，且“逆回购净投放”只能从已认证的操作及到期账本派生。
- [P1准备清单:32](p1-certification-readiness.md#L32)明确先认证7天投放；日净投放另需到期台账或已认证日历/顺延规则。该准备材料不是已完成认证。
- [业务决议草案](business-decisions-draft.md)当前为 `needs-info`，范围是估值、广度和商品，没有 OMO“无记录等于无操作”的决议。不能从这份草案推出额外 OMO 授权。

已经版本化的实现边界：[models.py:238–249](../../src/pring_cycle/models.py#L238)将 `repo-net-injection-trading-calendar-v0002` 绑定新模型；[测试:201–251](../../tests/integration/test_context_projection.py#L201)保留 v1 同日投放/到期成对输入的语义。因此不得把 v2 直接改回 v1、修改历史公式身份或原地重写发布结果。[ADR0006](../../docs/adr/0006-dual-as-of-and-immutable-evidence-vintages.md)、[ADR0012](../../docs/adr/0012-atomic-model-versions-and-parallel-replay.md)仍适用。

## 当前源码与公开测试证明什么

1. [context_projection.py:666–684](../../src/pring_cycle/context_projection.py#L666)只保留 `_certified_point` 成立的金额行；[2003–2011](../../src/pring_cycle/context_projection.py#L2003)要求无选值冲突、`reported_value`、非空值、来源已认证且质量已验证。被排除行的存在与原因不再传入净投放计算。
2. [708–750](../../src/pring_cycle/context_projection.py#L708)使用模型核心股票的已认证行情日期推到期；先取操作日加7个自然日，再取**已读到日期集合**中首个不早于该日的日期（[987–992](../../src/pring_cycle/context_projection.py#L987)）。显式同日到期量优先，可以不经过股票日历分支。
3. [1032–1040](../../src/pring_cycle/context_projection.py#L1032)把空到期集合求和为0，把不存在投放点变成0，然后求差。它没有创建伪零来源声明，但会将这个未经证明的零参与派生事实。
4. [1053–1089](../../src/pring_cycle/context_projection.py#L1053)仅以实际保留下来的父项传播 PUBLIC/SYSTEM 时间，并写 `derived_from_certified_inputs`、`validated`。随后现有鲜度检查只检查终止期年龄；新鲜结果进入当前模型采纳集合（[356–381、497–510](../../src/pring_cycle/context_projection.py#L356)）。缺失父项不会通过“任一父项 PUBLIC 未知”检查被发现，因为它已经不在父项集合内。
5. [测试:130–198](../../tests/integration/test_context_projection.py#L130)用8月21日投放2500、8月28日投放3000及股票日期，验证28日净投放500。它是隔离输入和派生血缘回归，不是完整真实操作台账证明。
6. [测试:254–317](../../tests/integration/test_context_projection.py#L254)只有21日投放2500和21/28日股票记录，**没有28日零投放声明或覆盖证明**，仍明确断言28日 `-2500`。这是已存在的兼容契约，不是官方证明“28日无新增投放”。

## 窄缺陷与仍须补证的情况

| 情况 | 当前结果与判断 | 后续边界 |
|---|---|---|
| 官方明确报告投放0，且到期2500已验证 | `0−2500=−2500`有实际输入支持，零必须保留 | 不因防止缺失填零而拒绝真实零 |
| 目标日投放 `not_disclosed`/冲突/未认证，同时有合格显式到期2500 | 不合格投放先被过滤，`injection=None`，随后输出`−2500`；**确认的实现缺陷** | 不应把被否定/未知投放解释为已证明的0；保留原因及证据，不能采纳有效净额 |
| 只有合格显式到期2500，完全没有目标日投放记录 | 当前输出`−2500`；单凭这个输入集不能证明错误净额，也不能证明当天无操作 | 保留“仅到期可净回笼”的已存在公式能力；需证明目标日无新增操作，或有能判定不存在操作的完整性契约 |
| 只有当日投放200和当日股票记录，没有到期字段/前置操作 | 空到期集合变0并输出200；**缺台账覆盖证明** | 不能用“数据库未读到到期操作”证明零到期；需有效预热范围及缺日/缺操作检测 |
| 名义到期日的股票行情缺一行，但后一天有行情 | 算法将后一天当首个交易日；无法区分缺报价与市场休市 | 需要适用操作结算日历及完整性；本文不擅定PBC/银行间/股票日历等价，也不指定新顺延算法 |
| 当日确实无新增操作、当日确实无到期，且双方均有完整证明 | 当前两侧都无点时不产生行；显式零声明则可计算0 | 是否需要每日显示“无事件/0”、采用哪种证明对象，需要另行冻结，不能从稀疏空集合自动补日报 |

第二行不依赖新外部规则：`EvidenceRepository.append_source_claim` 允许 `not_disclosed/value=None`（[evidence.py:48–51、1151–1156](../../src/pring_cycle/evidence.py#L48)）；同目标日添加合法到期值，绑定已认证金额定义和 v2 公式，调用 `build_context_projection`，不合格投放会被过滤。

主代理随后在规定 WSL 隔离环境实际执行了[公开入口草案](draft-tests/test_omo_invalid_flow.py)：到期500，投放分别为 `not_disclosed` 和两个来源100/200冲突；原始投放行正确保持坏状态，派生净额却仍为 `current`。[主代理 RED 日志](verification-omo-invalid-flow-red.txt)为 **2 failed / 3.78s**；按上述源码计算净额为−500。本人只读取草案和日志，没有执行应用。该结果证明上述窄缺陷，不证明生产运行状态，也不证明完全无行时的业务含义。

## 官方操作解析没有授权缺列补零

[official_context.py:1226–1274](../../src/pring_cycle/official_context.py#L1226)处理当前官方7天操作表：从明确的“中标量”解析 `injection`，有利率列才生成利率，没有到期列就**不生成到期声明**。旧六列表路径则分别解析投放量和到期量（[1275–1322](../../src/pring_cycle/official_context.py#L1275)）。因此“当前官方表不提供到期量”不能解释为官方报告到期0。

已保存来源准备材料还说明，8月11日原件明确报告7天中标量0而没有利率列（[P1清单:66](p1-certification-readiness.md#L66)）；这是“金额真实0、利率未报告”的样本，不是“缺公告也等于0”的证据。本次仅核对既有材料与解析代码，未重新读取该CAS原件或声称新增官方独立验证。

## 可执行下一步，不扩大为新规则

“已存在但不合格的目标投放 + 合格显式到期”已有主代理公开入口 RED。下一步修复并取得 GREEN，验证不产生可采纳净额，保留原因、原有证据及旧公式/历史结果；配套保留真实零投放、完整成对流量的正例。未知PUBLIC应同时覆盖实际两父项及显式零父项，不能只验证省略后的剩余集合。

另开完整性补证：确定当前日投放不存在的证明、全部可能到期操作的必要前置区间、适用日历/顺延和例外，以及相应 PUBLIC cutoff。股票行情单点认证不等于完整到期日历认证；[full_run_requirements.py:102](../../src/pring_cycle/full_run_requirements.py#L102)的OMO期数1与[model_evaluation.py:1007](../../src/pring_cycle/model_evaluation.py#L1007)的10日预热配置也不是覆盖证书。只有这些前提明确后，才能决定稀疏账本的零值行为及新增回归；不能为了让现有测试变绿而补造零来源。生产 v3 隔离、来源认证和新模型切换门禁保持原边界。

## 读取指纹

以下 SHA-256 与 bytes 为本次直接读取的工作区文件字节；未转换换行。记录时刻 `2026-09-08T00:55:21+08:00` 附近。本文自身最终SHA/bytes由交付消息提供，避免自引用哈希。

| 文件 | bytes | SHA-256 |
|---|---:|---|
| `CONTEXT.md` | 20103 | `f0cdf13436e1dd178b86ac6181de916757c3ef59edb7024ec6e980f151e5a102` |
| `.scratch/pring-data-acquisition-repair/spec.md` | 27762 | `f5c32c407f216841b2afed0aaab3863868bdc394d9057207d25dbc9e9a561cc4` |
| `.scratch/pring-data-acquisition-repair/business-decisions-draft.md` | 5314 | `7d17453b12975869eed360d3047d862c562e1e4f697fbe8a97321af6f0919064` |
| `.scratch/pring-data-acquisition-repair/p1-certification-readiness.md` | 34721 | `0f3cb130613ee6cddbd535fff58ea11929dca2d0526ba1d2c484dbc25591f368` |
| `src/pring_cycle/context_projection.py` | 78142 | `1c63a6523a11cf151df06949c0cc0cfdfe58728aca4468f5ed96add3120a4372` |
| `src/pring_cycle/official_context.py` | 80005 | `fae1b0310e6534b2d6ebd6a439614460f1ce4ecfdd4dcbd70361319736ad9d73` |
| `src/pring_cycle/models.py` | 42485 | `42db5dfc7c2ca42b9916b21ddbc2b04165f0bc082d5c78be354cf15020ba39b8` |
| `tests/integration/test_context_projection.py` | 58226 | `183001359f933b212b69e33705895dabc3054a459b93b8828ecf8934cfe8d2d2` |
| `docs/research/official-gap-source-audit.md` | 26565 | `17e7f9c5bf94bbaf14c33a481064b868a7b51be22b90eef556fcb3d7bfe95a24` |
| `.scratch/pring-data-acquisition-repair/draft-tests/test_omo_invalid_flow.py`（主代理新增） | 2963 | `38560a01f97d120be5ba568df64ac1f6b7700f7055d49ff2f4d0b1e86232e920` |
| `.scratch/pring-data-acquisition-repair/verification-omo-invalid-flow-red.txt`（主代理实测，编码标准化后） | 7045 | `58635939bf967d433367c4a52a556e85e8a4e4ba0ed3a5be2af715bc3630182a` |

日志指纹更新说明：主代理在完成 Tee 日志后将 UTF-16 转为 UTF-8 无 BOM、LF 换行，诊断文本未改；本次复核确认无 UTF-8 BOM、无 CR、114 个 LF。该处理与首次读取交叉，因此旧读取记录为 14320 bytes、SHA-256 `938f3443bd06f70999c29c496b39b9d73ecdf1ddd39482db5e0f25843a28c634`；当前交付采用上表的标准化后指纹。
