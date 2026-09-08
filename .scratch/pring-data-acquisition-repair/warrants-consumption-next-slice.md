# 仓单新目录消费：下一最小切片

2026-09-08。只读指定的 4 份源码与 `remaining-p1-source-consumers.md`；没有联网、数据库读取、应用/测试执行或认证操作。以下绑定本文件末尾的实际工作树字节，旧研究仅复用来源事实，不把旧代码拒绝点当作当前状态。

**下一批应一起接通仓单来源守卫、准确字段绑定、多仓库集合选择与定向取得。** 最低范围仍是 8 品种；CU/RB/RU/SP/SC 的已有官方样本可以支撑软件正例，不能把 PP/CF/TA 缺证抹掉或缩成 5 品种完成。

## 当前已具备与确定缺口

| 边界 | 当前事实与最窄动作 |
|---|---|
| 新目录解析 | [ingest_context_scalars](../../src/pring_cycle/tushare_context.py#L1204) 已传 `database_path=paths.database`。旧研究 L13 的目录解析首拒绝已经过时，不再修一次。 |
| 来源守卫 | [require_registered_source_contract](../../src/pring_cycle/source_contract_review.py#L175) 的 contracts 尚无仓单；`official_source_members` 也无仓单实现，最终返回 None。新目录 certified 声明仍落入 L184 `registered_source_contract_not_implemented:CN_FUTURES_WARRANTS`。增加独立 TuShare 仓单分支，不塞进 NBS/PBC 官方 family map，也不改旧 v3 guard。 |
| 接口/字段绑定 | [新目录交付校验](../../src/pring_cycle/tushare_context.py#L1209) 目前仅给 DR007/Shibor 校验 `(api_name, source_field)`。仓单需同样绑定 `fut_wsr` 及下表三组字段，不能只认维度和单位而接受别的 source_field。 |
| 模型最低成员 | [required_dimension_members 的仓单定义](../../src/pring_cycle/metric_contracts.py#L40) 已有 8 个 `{symbol, measure=registered_receipts}`。保留它作为最低品种覆盖；它不是“一品种只有一个仓库”的声明。 |
| 多仓库消费 | [旧源码审查 L18](remaining-p1-source-consumers.md#L18) 已定位二键要求与四键观测精确比较、以及“恰好一条”的冲突。本轮按授权未重读 selector/worker/evaluation，因此这是下一实现需复核的公开行为，**不是本轮重新执行或复现的缺陷**。最窄策略是按品种收集完整四维身份集合、保留各 claim，再统一供选择器与完成门使用。 |
| 定向取得 | [retrieve_tushare_context](../../src/pring_cycle/targeted_context.py#L59) 日频分支没有仓单，L82–85 返回 `targeted_tushare_family_unavailable`。新增仅仓单的分支，按已声明范围调用 `futures_warrants`；当前函数使用 metric_ids/period，没有现成 symbol 分流。全家族请求须取全部 8 品种；如接已有单品种 scope，要显式传其筛选，不能无声默认 CU。沿 L127 的 `acquire_scalars`、ledger 和 L142 的最终选择判断，不把下载成功直接返回 verified。 |

## 源契约：结构允许不等于来源认证

[既有目录审查 L25–34](remaining-p1-source-consumers.md#L25) 已记明：`metric_id=CN_FUTURES_WARRANTS`；`provider=tushare`；`source_codes=(CN_FUTURES_WARRANTS,)`；主 unit 为 `tonne`，allowed_units 为 `tonne, kilogram, sheet, lot, barrel`；frequency=`daily`，release_event_family=`cn_futures_warrants`，release_rule=`source_schedule_required`，release_timezone=`Asia/Shanghai`。新目录可比较这些结构字段，不能继承旧 certified 标签，也不能用 v2 的 scalar 主单位代替该基线。

[实际 parser](../../src/pring_cycle/tushare_context.py#L387) 的准确身份如下：

| 字段 | 必须保留的绑定 |
|---|---|
| API / 请求品种 | `fut_wsr`；规范品种 `CF,CU,PP,RB,RU,SC,SP,TA`。TA 请求实际 `symbol=PTA`，返回也必须是 PTA，随后输出规范 TA；不能把任何返回 symbol 都改成请求品种。 |
| 完整维度 | 恰为 `symbol, warehouse, exchange, measure`；仓库、交易所必须非空；同名仓库跨品种或 exchange 不合并。 |
| 三组字段 | `pre_vol → previous_registered_receipts`；`vol → registered_receipts`；`vol_chg → registered_receipts_change`。只要求最低当值成员；前值/变化按实际披露保存，不能用当值减变化冒充源 pre_vol。 |
| 日期 | `_daily_scalar` 的 `business_day`，start=end=真实 `trade_date`。守卫应要求严格合法同日；取得层还应核该日属于请求区间，避免供应商错期行冒充目标日。当前 futures_warrants 循环只显式核 symbol/仓库/exchange/unit，没有日期区间校验。 |
| 单位 | [原单位映射](../../src/pring_cycle/tushare_context.py#L66)：吨→tonne，千克/公斤→kilogram，张→sheet，手→lot，桶→barrel。未知或缺单位拒绝，不以主 unit 回填，也不跨单位求和。 |
| 空值/数量 | [L448–450](../../src/pring_cycle/tushare_context.py#L448) 对 `None` 省略 scalar；`_number` 对非法文本、布尔、非有限值拒绝。明示 0 保留，变化可为负。当前 `_number` 对所有字段只查有限性；新增数量契约如区分非负前值/当值与可负变化，应以明确语义测试绑定，不能将合法负变化一起拒绝。 |

**SC 的真实 TuShare exchange 是 SHFE。** [旧研究 L47](remaining-p1-source-consumers.md#L47) 的真实快照已对照弘润油储 `SC / SHFE / 1027000桶`；合成测试里的 SC/INE/1200 不证明生产标签必为 INE。仓单消费者须接受并保留这条 SHFE 身份，不借商品合约代码 `SC.INE` 重写仓单 exchange。若另支持 INE 标签，须说明其独立来源依据；不能仅凭合成测试扩大真实来源断言。其他已有快照标签为 CU/RB/RU/SP→SHFE、PP→DCE、CF/TA→CZCE。

PP/CF/TA 仍缺官方原表、单位及明细身份依据；允许单位集合只是结构范围，**不授予三个品种的逐品种单位认证**。现有 5 品种、134 次同名官方对照也不是全行覆盖。[原件定位与边界](remaining-p1-source-consumers.md#L61) 已给 CU 国储天威当值 225 吨、变化 0，以及 SC 弘润油储当值 1027000 桶、变化 0；本轮不重抓或重新认证这些原件。

## 多仓库完整性的最小实现边界

1. **两个层次分别检查。** 第一层是固定 8 品种均具有合格 `registered_receipts`；第二层是本次已返回、应有当值的各仓库身份是否完整。对同一品种允许多仓库，结果保留逐条 claim；只用 subset 匹配后选一个仓库，或每个品种随便保留一条，都不能证明第二层完整。尚未取得全量官方仓库全集时，准确表述只能是“当前取得批次内完整＋8 品种最低覆盖”，不能宣称全国所有仓库无遗漏。
2. **从原返回行保留分母。** 某仓库行有 `vol=None`，即使同品种另一仓库有值，也不应静默 complete。因为当前 parser 直接省略该 scalar，只扫描 accepted scalars 会失去这条缺件。最窄可从已保存 raw 行推得本请求的仓库身份，并记录缺当值；或为仓单保留具体 rejected/missing field 记录。无需建立永久“全历史仓库 registry”。没有行不等于明示零；总计与明细/分区只分别保留，不在这批擅自冻结加总规则。
3. **先准确绑定请求，再复用回执。** [acquire_scalars L172–177](../../src/pring_cycle/tushare_context.py#L172) 按 api_name 关联所有同 API 回执。8 品种都是 fut_wsr，所以 CU scalar 当前也可关联其他品种/日期的 fut_wsr 回执；L192–206 的每份 normalized 可能包含全批 scalars。这证明已有完整性材料，但不能单凭“某回执 normalized 列齐”声称该 raw 精确包含所有成员。最窄收紧 fut_wsr 的请求 symbol/date 与行匹配，或在批次消费者中读取各原始请求及响应交叉核对，避免全局改造其他 family。每个成员保留可追溯原件和真实取得/校验时钟。
4. **分页与时间约束沿用。** [L469–503](../../src/pring_cycle/tushare_context.py#L469) 已实现满 1000 行拆日期、单日满限拒绝，不能重写旧研究的截断风险为未修复；仍须将拒绝传到完成结果。PUBLIC 不能由统计日/固定收盘点生成；[L1313–1342](../../src/pring_cycle/tushare_context.py#L1313) 已保留未知发布修订与取得回执时钟。目标日选择还需保持既有 PUBLIC/SYSTEM cutoff，基础 SYSTEM 可读不等于历史目标输入可用。

## 最小公开行为验收建议

- 在新登记目录，经 `TushareContextAdapter.acquire_scalars(... futures_warrants(...))` 走真实公共导入链；仅 transport 为明确标注的合成 TuShare 形状，以 CU 225 吨、SC/SHFE 1027000 桶作独立期待。先验证守卫首拒绝，再验证回执、字段/维度/日期与多单位原值保留；两个品种成功时全家族仍缺 6 个，不把软件正例称认证。
- 同一品种增加第二仓库，目标选择须返回两份正确 claim；删去其中已返回仓库的 vol 或使其质量不合格，保持未完成。两个同名仓库跨品种不碰撞；总计与明细不重复累计。
- 错 provider、错 source_field、TA 返回非 PTA、空 warehouse/exchange/unit、错期行均不能借新守卫入库或形成完成结果；0 当值、负变化和空前值分别验证，不能混同。
- 八品种合成行为集只验证最低范围与定向请求的流水：缺一品种、单日满 1000 行、未知 PUBLIC 时不 complete。PP/CF/TA 合成单位仍明确非官方补证。真实回执分母按实际物理调用计数，不把 8 品种请求记作一次取得。

## 只读输入指纹与交付

| 文件 | bytes | SHA256 |
|---|---:|---|
| [source_contract_review.py](../../src/pring_cycle/source_contract_review.py) | 11799 | `1b1a95adacd7bdba95f3a91d22b68f4a6aec948a93c7b2a6aa3e3a394b3655ac` |
| [metric_contracts.py](../../src/pring_cycle/metric_contracts.py) | 9849 | `b94d7b0e1da8ca282c53a12779b5bf738d8bf380950189f6569453d8ce598f66` |
| [tushare_context.py](../../src/pring_cycle/tushare_context.py) | 69165 | `5fefbe8ff0f17ac0947be75621d8365e6d8616170368afee6394663c8b6aeece` |
| [targeted_context.py](../../src/pring_cycle/targeted_context.py) | 5936 | `065a5342fc01694cd832c237122f706914a95a9a5a41febaea054a16fbdee25a` |
| [remaining-p1-source-consumers.md](remaining-p1-source-consumers.md) | 25757 | `b29d4daf67fe06d1ddce2d21c38339152bdfff89f4e27f90bd09bb22d1fdf251` |

唯一交付：`.scratch/pring-data-acquisition-repair/warrants-consumption-next-slice.md`。以上是下一实现边界，没有本轮新测试通过数，也没有授予仓单认证或宣布票 13 完成。
