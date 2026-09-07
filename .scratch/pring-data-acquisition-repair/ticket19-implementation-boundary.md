# 票 19：新候选消费认证包的最窄实施边界

研究日期：2026-09-08。固定源码基点 `a569fd757c7d19a4ae95b980bd2b1c0c51cba973`；下列行号和指纹均取 `git show <基点>:<路径>`，不包含正在并行修复的 `source_history.py` 工作树。本研究只读源码、已接受规格和测试；未运行应用、网络、账户、数据库、认证或模型命令，仅新建本文。测试入口建议尚未执行，不是 RED/GREEN 回执。

**有一项可独立推进的必要缺失能力：在新候选的公开提交边界，消费并校验显式的不可变认证包及其定义绑定，缺件时在写入候选之前给出具体机器拒绝。** 这属于票 19 已要求的拒绝能力，不需要预先选择 PE、广度或商品业务规则。但当前不存在可直接使用的新目录/正式包入口；不能把给旧 v3 路径换名或删除 guard 当作实现，也不能把完整新候选、来源认证或整票 19 标为完成。

## 已确定的规范与代码事实

| 检查点 | 固定基点事实与含义 |
| --- | --- |
| 规格已经要求机器校验 | [票 19 L19—21](issues/19-immutable-candidate-catalog.md#L19) 要求绑定来源包及全部版本身份，并对“认证缺件、陈旧哈希和不一致定义版本”给机器拒绝，“不能只填 certified 字符串通过”。这不取决于某个待选业务参数的最终值。 |
| 当前公开命令只进入冻结 v3 | [CLI L382—389](../../src/pring_cycle/cli.py#L382) 将目标日、smoke 哈希及使用边界传给旧创建服务；[服务 L105—123](../../src/pring_cycle/source_certification.py#L105) 在读取 smoke 前无条件调用 `require_source_contract("metric-catalog-v0003")`。因此当前不能用 A18 准备材料创建新候选。 |
| guard 是否定性审查，不是新版本认证器 | [source_contract_review L73—107](../../src/pring_cycle/source_contract_review.py#L73) 明写“absence is not a certification grant”；非 v3 未命中此审查，不等于正式认证通过。[目录查找 L396—412](../../src/pring_cycle/catalog.py#L396) 目前只登记 v1/v2/v3 及融资独立 v2，传不存在的新版本仍会拒绝。 |
| 旧包构建不是正式包验证 | [source_certification L349—375](../../src/pring_cycle/source_certification.py#L349) 对 metrics、smoke、review 文档描述和 terms 算包 ID；[L124—133](../../src/pring_cycle/source_certification.py#L124) 用冻结 v3 集合检查 P1 覆盖。它没有接收新定义及相应正式包并逐项验证的入口。旧 `_package` 本身的存在不构成可绕过 guard 的公开漏洞。 |
| 持久化与重放不能代替包认证 | [模型构造 L154—179](../../src/pring_cycle/models.py#L154) 对调用者给的包只要求集合非空、每项 package_id 非空；[create_candidate L271—302](../../src/pring_cycle/models.py#L271) 保证清单 ID/内容不可变并存库，未核验包内容。 [model_evaluation L677—693](../../src/pring_cycle/model_evaluation.py#L677) 将包用于版本差异和全 P1 回放范围判断，未核验证据包。清单自身哈希不能证明它引用的认证成立。 |
| 有可复用校验，不能误称全无 | [verify_source_smoke_artifacts L285—357](../../src/pring_cycle/rehearsals.py#L285) 已校验 smoke CAS、登记、执行指纹、目标、形状与集合；它的输入是旧 smoke 协议，不是新正式家族认证包。保留这类真实验证，不以另一层 certified 标签替代。 |

这里的结论是**票 19 所需新能力尚缺**，不是发现“当前生产 v3 已能被公开命令重新认证”。[已有隔离测试](../../tests/models/test_source_certification.py#L16) 明确验证旧 smoke 成功仍不能重新认证 v3；[历史候选回归](../../tests/integration/test_source_contract_quarantine.py#L32) 刻意保留旧候选可读并拒绝激活。不可通过收紧所有历史 `ModelRepository.create_candidate` 调用、重写旧包或删除旧查询能力来达成新入口要求。

## 一个最窄的公开行为 TDD 切片

沿现有 `model-source-certify` 的创建/查询流程增加**显式新契约分支**，接收不可变候选描述及正式包引用；具体参数名是实现选择，本文不新增业务规则或冻结一个未经实施的 schema。首先交付“包引用失配必须拒绝”的行为，再在同一入口接通已要求的必填与定义绑定检查。不要另建仅可调用私有 validator 的基础层票。[规格 L91—93、L132—134](spec.md#L91) 要求保持架构、公开边界和真实持久证据。

公开反例可使用隔离 runtime 的真实 CAS/仓库和明确 synthetic 的完整请求：先保存一份正式包格式的测试材料，再改动被引用文档一个字节而保留原哈希，经命令提交，必须返回包及引用定位明确的失配原因；查询证明候选未新增、active 指针和正式投影/发布历史未变。不能只断言旧 v3 guard 抛错或未知 CLI 参数报错，那只能证明新入口尚未接通，不能证明新包验证有效。

同一切片的必要边界：

- 缺失原件/审查引用、包自身内容与 ID 不符、包绑定定义与候选定义不符，均在存候选前拒绝；没有正式认证依据、只有准备包/候选值/`certified` 字符串，也必须拒绝。哈希检查仅证明身份，不能自行赋予来源资格。[票 19 L21](issues/19-immutable-candidate-catalog.md#L21)、[领域定义 L255—260](../../CONTEXT.md#L255)。
- 新契约必须显式绑定全部定义、来源包、趋势输出、选择/时间规则、公式及执行身份；候选计数规则为 `candidate-duration-v0002`。这里只校验“存在且一致”，不替用户决定尚未冻结参数值。[票 19 L19、L40](issues/19-immutable-candidate-catalog.md#L40)。
- 合格 synthetic 正例必须经过真实内容读取和新契约检查，再经公开查询读回相同身份；不可 patch 掉 guard、用空包替身或把仅有 package_id 的旧 fixture 当正式包。坏包拒绝与独立合格正例一起才能证明可用分支；实际来源正例仍须等真实材料齐备。[规格 L133](spec.md#L133)。
- P1 来源认证缺件是新完整候选阻断；目标日/维度不足、PUBLIC 未知、P2 受限各自表达，不把 P2 缺许可误加为强制采购或创建条件，也不把 SYSTEM 可见改称 PUBLIC 合格。[票 19 L16—18](issues/19-immutable-candidate-catalog.md#L16)、[规格 L96—100](spec.md#L96)。

最小验收仅是该入口已能区分并拒绝不合格包、接受自身契约合格的隔离测试材料；不会产生生产认证、真实完整候选、120 日重放或激活结论。完整票 19 的成功仍须实际形成完整新候选。[票 19 L29—31](issues/19-immutable-candidate-catalog.md#L29)。

## 不能由上述代码补齐的事实

| 尚需什么 | 可以先做什么 / 不得替代为什么 |
| --- | --- |
| 已接受的新定义及五家族业务决议 | 可按请求中已有定义检查包版本/范围一致；不能自行冻结静态/滚动 PE、停牌/新股窗口、金额范围、商品换月和基值。[规格 L102—105](spec.md#L102)。 |
| 家族正式语义、字段、历史、时间与使用范围认证 | 现有逐值审计和复算材料可以成为可读引用；准备包不是认证包，零差异和正确哈希不是资格授予。官方抽样继续按既有 ADR，不新增逐历史观测双来源核验。[CONTEXT L259](../../CONTEXT.md#L259)、[ADR0013 L7—9](../../docs/adr/0013-tushare-delivery-with-official-sampling.md#L7)。 |
| 某历史版本的 PUBLIC 合格事实及真实认证交集 | 原件取得、公开页标示和版本/修订证据分别承接；不能将当前取得或复算时钟回填历史，也不能把旧 v3 认证标签复制到新版本。精确 120 日范围和真正重放留在其既有验收边界。[规格 L96—98、L124—127](spec.md#L124)。 |

因此可先实施的是**正式包进入新候选前的可观察验证边界**；不是先制造新目录全员 certified，再以未来研究补证。当前 guard 保持生效，A18 等准备工作保持其原有有限证明范围。

## 固定输入指纹

下表由 Git 对象原始字节计算 SHA-256；不将 PowerShell 显示换行转换后的文本当输入。复核命令等价于 `git show a569fd757c7d19a4ae95b980bd2b1c0c51cba973:<路径>` 后直接计算 bytes/SHA-256。所有源码引用均指此基点，不断言并行工作树保持这些行号/哈希。

| Git 路径 | bytes | SHA-256 |
| --- | ---: | --- |
| `.scratch/pring-data-acquisition-repair/spec.md` | 27762 | `f5c32c407f216841b2afed0aaab3863868bdc394d9057207d25dbc9e9a561cc4` |
| `.scratch/pring-data-acquisition-repair/issues/19-immutable-candidate-catalog.md` | 3443 | `5a873d6493b2b7d716944ca641cc2eb75f9093f249ef1db1f9b996c5a1cb4b57` |
| `CONTEXT.md` | 20103 | `f0cdf13436e1dd178b86ac6181de916757c3ef59edb7024ec6e980f151e5a102` |
| `docs/adr/0013-tushare-delivery-with-official-sampling.md` | 1089 | `8580553c46299947b55e1dfef8718e43c121019a60e54b4f9b91f466ef4cac4b` |
| `src/pring_cycle/cli.py` | 37479 | `bcedbfaf97d2710f22c231919e22f57e443787823e7a17c7a153d11f5a1573c3` |
| `src/pring_cycle/source_certification.py` | 15659 | `e585ce624de989ec6f9def5ff4f44130ebad22c449d6c8a1a2f0c9d64e44a963` |
| `src/pring_cycle/source_contract_review.py` | 4706 | `ad377fafc71cbd26d8a3d06eaf71131c9111aecc436f84618032f11d70786e64` |
| `src/pring_cycle/catalog.py` | 25699 | `59fcac0c8279c4b1acfe7bac4eab1688088571745ef539fc41728c3acd0eb83a` |
| `src/pring_cycle/models.py` | 42485 | `42db5dfc7c2ca42b9916b21ddbc2b04165f0bc082d5c78be354cf15020ba39b8` |
| `src/pring_cycle/model_evaluation.py` | 37660 | `d5c15ce03b0dd97385678d4df32a6623c8c06a1953f912cec688d14c1020c732` |
| `src/pring_cycle/rehearsals.py` | 33995 | `492aac51500c810256366baa5e205998e66f9aec42b2866e3a2618bcfa690a1e` |
| `tests/models/test_source_certification.py` | 3064 | `6f8ee530760cfe86708ced90030d6204c2e3039fb930e17ed6ae7c41ce86f92e` |
| `tests/integration/test_source_contract_quarantine.py` | 11178 | `9adf244fb220ecc50564796b11e726a9df794c81753b99eb919e518bb9b5e9fb` |
