# 全目录数据获取与可用性只读盘点

观察时刻：2026-09-06T10:38:07.833555+00:00。Git HEAD：`6edf0cbea95c3c26efa9c24fbb4e8f88f57c0302`。

完整机器可核验统计：[metric-inventory.json](metric-inventory.json)，SHA256 `6bcae5fcf3631d626f9f94efb01cd05fea69c3901e8fd61243b5abef0b87a2e7`。统计范围是生产 SQLite 的全部历史定义版本、来源和保留修订，不是仅活动模型或仅 120 日。

数据库以 `file:/home/tywin/.local/share/pring-cycle/pring-cycle.sqlite3?mode=ro` 打开，在同一只读事务内统计；本次网络请求 0，未读取密钥值、运行迁移、启动 Worker 或修改 DB/代码。另只读校验 CAS 原件。

## 可直接引用的结论

- 目录 61 项：P0 6、P1 42、P2 13。44 项有来源声明，其中 42 项 source-only、2 项 source + derived；另 5 项 derived-only、12 项两者都无。故这四类互斥并合计 61。12 项无标量中有 3 项 P0 运维证据、9 项未认证 P2，不能一律叫 12 项下载失败。
- 数据库有 272,949 条 source_claim；92 条 derived_observation，其中目录内 7 项合计 87 条，另 5 条为目录外辅助指标 CN_REAL_FINISHED_GOODS_INVENTORY_PROXY。派生记录全为 system_as_of；这只描述持久化记录，不能推断从未运行过临时 public_as_of 查询。
- 冻结 v3 标签：P0 certified 4 / awaiting 2；P1 certified 38 / derived_from_certified_inputs 4；P2 certified 3 / derived 1 / awaiting 9。上述为历史静态标签。当前活动 v3 模型整体被 source_certification_contract_unresolved 阻止正式新运行/写入/激活/切换，61 行均明确标 blocked；不是只有直接审出的 15 项受模型级隔离。
- 当前保留投影目标交易日 2026-08-03、系统截止点 2026-08-31T20:51:41.285300+00:00，completeness=degraded。worker.py:882–928 的分子是 available：P1 34/42 = 可用 34、未可用 8；P2 2/13 = 可用 2、未可用 11。它是历史目标日的规则结果，不是当前认证通过数。
- 生产 run_retrieval_attempt 和 run_retrieval_scope 均 0；模型可用的唯一证据缺口补齐率为 N/A。研究/候选 retrieval_attempt 的 5,745 次尝试、原始网络请求数、网页相关数都不能替代这个分母。

## 全库结构检查与时间边界

逐条检查 272,949 条 claim：reported_value 必需数值、非有限数、单位缺失/不在对应定义允许集合、维度 JSON/键集合/空白值、时期 ISO 日期/起止倒置、必需时间/时区等均未发现异常。每条使用其自身 definition_version；不能拿 v3 维度定义追溯判旧 v1 行为坏数据。单位集合符合冻结定义也不证明该定义本身符合官方语义（商品结算口径就是反例）。

全部 quality_status=validated，全部 value_state=reported_value，public_available_at 为空 0；这些只是已有标签和字段内容，不是逐值官方核对证明。release_at 为空 22,411 条；public_available_at == fetched_at 为 53,352 条；public_available_at == release_at 为 218,739 条；public 早于 fetched 为 219,597 条。相等关系不是完整来源分类，也不等于可信发布时间证明。tushare_context.py:1064–1066、1173–1177 保留了把取得时间用于缺失公开时间界的旧路径；需与 CONTEXT 的“无可靠日期保持空”要求分开评估。融资新候选则明确保持未知公开时间为空。

同 observation_id 多条 claim 是可能的来源/修订保留；定义版本本身也参与观察身份。JSON 分列 claim 数、唯一 observation_id 数、统计期结束日数、维度组合数和带 supersedes 的数，未把“多行”一概判重复坏数据。未执行 27 万条逐值官方网站重新对账。

可复核 SQL（其余分组与结构检查定义在 JSON/query_definitions）：

```sql
SELECT count(*) AS n,sum(public_available_at IS NULL) AS public_null,sum(release_at IS NULL) AS release_null,sum(public_available_at=fetched_at) AS public_equals_fetched,sum(public_available_at=release_at) AS public_equals_release FROM source_claim;
SELECT count(*) AS n,sum(value_state='reported_value' AND value IS NULL) AS numeric_missing,sum(unit IS NULL OR trim(unit)='') AS unit_missing,sum(NOT json_valid(dimensions_json)) AS invalid_dimensions_json,sum(period_start>period_end) AS reversed_period FROM source_claim;
SELECT metric_id,count(*) AS n,count(DISTINCT observation_id) AS identities,count(DISTINCT period_end) AS periods,min(period_start),max(period_end) FROM source_claim GROUP BY metric_id;
SELECT count(*) FROM run_retrieval_attempt;
SELECT metric_id, formula_version, as_of_mode, count(*)
FROM derived_observation GROUP BY metric_id, formula_version, as_of_mode;
```

## 原件链与实际复核覆盖

- 691 个登记 artifact 共 47,629,036 字节，全部实际读取并通过 SHA256 和 byte_count 核验，缺失/哈希不符/字节数不符均 0。该计数只涵盖 SQLite 登记原件，不能代表 CAS 全部研究文件总量。
- 1,970 条官方 claim 的 source_reference 含 HTTPS URL#sha256，涉及 272 个不同原件，均存在且哈希匹配。source_history 清单 69f291…eec 有 270 条官方历史记录，所引 raw hash 全部核验；覆盖、日期和每项关联原件均保存在 JSON。原件存在及字节匹配证明可追溯，不等于逐值解析正确或时间已逐条认证。
- 270,979 条 TuShare claim 的 source_reference 为 tushare:API:字段:日期等文本；source_claim 无逐行 raw_response_hash 外键。完整 source_reference 与 artifact_reference 精确连接为 0，原因包含官方 hash 片段和 smoke 注册键使用不同形状，不能据此宣称所有原件丢失。TuShare smoke 有批次 normalized_hash、normalized_result_hash 和获取范围；它们不能单独证明逐行原始响应或实际首发时间。
- 活动模型保留 6 个历史认证包。P1 直接值覆盖为官方直连 20 项 + 仅 TuShare context 的 3 项（DR007、Shibor、仓单）+ 受审市场 15 项，另 4 项派生。受审市场包 official_direct_smoke_hashes 为空，review 文件仅核心权益代理和 NHII 历史方法，不能证明全部 15 项市场语义已经核对。
- ADR0013:7 要求按对应官方样本复核语义、字段、单位、统计期、发布时间和许可；不要求每条正式观测都拥有第二来源。本盘点没有把它加严成逐历史值双源一致。

后续隔离研究已有实际成果，但都没有解除冻结 v3：

- 融资候选 margin-financing-v0002：120 交易日 × 3 所 = 360 原始行、240 标量，沪深 2026-08-28 融资余额/买入额共 4 个数与官方原件一致；北交所官方数值样本和实际发布时间仍缺。240 条公开时间未知、public_as_of_points=0、active_database_modified=false。清单 c0bbdf18fa19fcf0a2025b602c7a57f7317e60822b54ac90ff3fc11fd3d5dc6f 及所引两官方原件和两请求原件已实读 hash 核验。
- 广度新输入复核清单 dfa264f956d2c07def24190b0fda8dc8da6160b6c37000fe165c9cde9b834110：120/120 日期输入结构通过，660,811 条报价、1,463 个全天停牌成员、453,571 条盘后属性未知记录。仅按两份官方 PDF 裁决两个具体股票/日期全天停牌冲突。来源认证记录 0、公开时间声明 0、活跃 DB 修改 false；它仍 awaiting_source_certification，不能据此断言 120 日 PIT 广度已就绪。
- 指数/估值官方补证、商品月份合约/结算与换月证据的已审范围和缺口，应结合 docs/research/*official-resolution-2026-09-05.md；本盘点没有发起新的官方获取。CNY030 数值样本、CSI1000 估值覆盖、DCE PP 真实月份结算样本以及可证实的换月时点仍不能由旧库标签填补。

## 61 项紧凑矩阵

S=source_claim 条数（全部定义/修订）；D=持久化 derived 条数；末期=source_claim 最大 period_end，不是下载/发布日期；维度=实际出现的不同组合数（空字典也计 1 组），详细键值及各组覆盖见 JSON。快照状态只汇总嵌入 metric_id 的显式节点，空表示未以该形状呈现，不代表 worker 不可用；无状态节点也不据此推定 current。逐项 available 布尔未保存于该诊断快照，本次未启动 Worker 重算。**本表全部行的当前正式模型状态均为 blocked**。

| # | 级别 | 指标 | 频率 | v3旧标签 | S / D | 末期 | 实现维度组合 | 保留快照显式状态 | 关键缺口/边界 |
|---|---|---|---|---|---:|---|---|---|---|
| 1 | P0 | CN_TRADE_CALENDAR | daily | cert | 0 / 0 | — | — | 未显式呈现 | 运维证据另表/CAS；S=0不等于获取失败 |
| 2 | P0 | CN_RELEASE_SCHEDULE | event | await | 0 / 0 | — | — | 未显式呈现 | 运维证据另表/CAS；S=0不等于获取失败 |
| 3 | P0 | SOURCE_OBSERVED_AVAILABILITY | daily | await | 0 / 0 | — | — | 未显式呈现 | 运维证据另表/CAS；S=0不等于获取失败 |
| 4 | P0 | CN_EQUITY_CORE_000985 | daily | cert | 43300 / 0 | 2026-08-28 | 1 (无键) | 仅无status节点 | 历史数据/标签；本次未重新授予认证 |
| 5 | P0 | CN_BOND_CORE_000012 | daily | cert | 43300 / 0 | 2026-08-28 | 1 (无键) | 仅无status节点 | 历史数据/标签；本次未重新授予认证 |
| 6 | P0 | CN_COMMODITY_CORE_NHII | daily | cert | 43300 / 0 | 2026-08-28 | 1 (无键) | 仅无status节点 | 历史数据/标签；本次未重新授予认证 |
| 7 | P1 | CN_EQ_CSI300 | daily | cert | 311 / 0 | 2026-08-28 | 1 (source_code) | 未显式呈现 | 官方渠道/数值与时间抽样未闭合 |
| 8 | P1 | CN_EQ_CSI500 | daily | cert | 311 / 0 | 2026-08-28 | 1 (source_code) | 未显式呈现 | 官方渠道/数值与时间抽样未闭合 |
| 9 | P1 | CN_EQ_CSI1000 | daily | cert | 311 / 0 | 2026-08-28 | 1 (source_code) | 未显式呈现 | 官方渠道/数值与时间抽样未闭合 |
| 10 | P1 | CN_EQ_ADV_DEC | daily | cert | 556 / 0 | 2026-08-28 | 4 (measure,universe) | 未显式呈现 | 结构120日通过≠PIT；历史池/公开时点/预热未闭合 |
| 11 | P1 | CN_EQ_AD_RATIO | daily | cert | 139 / 0 | 2026-08-28 | 1 (measure,universe) | 未显式呈现 | 结构120日通过≠PIT；历史池/公开时点/预热未闭合 |
| 12 | P1 | CN_EQ_NEW_HIGH_LOW_120 | daily | cert | 406 / 0 | 2026-08-28 | 2 (measure,universe) | 未显式呈现 | 结构120日通过≠PIT；历史池/公开时点/预热未闭合 |
| 13 | P1 | CN_EQ_ABOVE_MA120 | daily | cert | 295 / 0 | 2026-08-28 | 1 (measure,universe) | 未显式呈现 | 结构120日通过≠PIT；历史池/公开时点/预热未闭合 |
| 14 | P1 | CN_EQ_ADV_AMOUNT_SHARE | daily | cert | 139 / 0 | 2026-08-28 | 1 (measure,universe) | 未显式呈现 | 结构120日通过≠PIT；历史池/公开时点/预热未闭合 |
| 15 | P1 | CN_MARGIN_BALANCE | daily | cert | 622 / 0 | 2026-08-28 | 2 (measure,scope) | 未显式呈现 | 新候选240条；BSE官方样本与实际公开时间缺 |
| 16 | P1 | CN_INDEX_VALUATION | daily | cert | 1866 / 0 | 2026-08-28 | 6 (index,measure) | 未显式呈现 | 仅300/500×3项，缺1000；提供方算法/时间未证 |
| 17 | P1 | CN_BOND_FULL_PRICE_CNY030 | daily | cert | 311 / 0 | 2026-08-28 | 1 (source_code) | stale | 官方渠道/数值与时间抽样未闭合 |
| 18 | P1 | CN_BOND_10Y_930916 | daily | cert | 311 / 0 | 2026-08-28 | 1 (source_code) | stale | 官方渠道/数值与时间抽样未闭合 |
| 19 | P1 | CN_DR007 | daily | cert | 318 / 0 | 2026-08-28 | 1 (无键) | stale | 历史数据/标签；本次未重新授予认证 |
| 20 | P1 | CN_OMO_7D_RATE | daily | cert | 121 / 0 | 2026-08-28 | 1 (无键) | stale | 历史数据/标签；本次未重新授予认证 |
| 21 | P1 | CN_OMO_7D_AMOUNT | daily | cert | 131 / 6 | 2026-08-28 | 1 (measure) | current,stale | 历史数据/标签；本次未重新授予认证 |
| 22 | P1 | CN_DR007_POLICY_SPREAD | daily | derived | 0 / 6 | — | — | current | 依赖上游；此处D为system_as_of记录 |
| 23 | P1 | CN_SHIBOR_ON_1W_3M | daily | cert | 501 / 0 | 2026-08-28 | 3 (tenor) | stale | 历史数据/标签；本次未重新授予认证 |
| 24 | P1 | CN_LPR_1Y_5Y | monthly | cert | 20 / 0 | 2026-08-31 | 2 (tenor) | awaiting_release,current | 历史数据/标签；本次未重新授予认证 |
| 25 | P1 | CN_RRR_EVENT | event | cert | 1 / 0 | 2025-05-15 | 1 (measure,scope) | no_event_in_visible_window | 可见窗无事件有效；不是缺失日值 |
| 26 | P1 | CN_TOOL_LIQUIDITY_MONTHLY | monthly | cert | 192 / 0 | 2026-07-31 | 24 (measure,tool) | current | 历史数据/标签；本次未重新授予认证 |
| 27 | P1 | CN_COMMODITY_BROAD_NHCI | daily | cert | 311 / 0 | 2026-08-28 | 1 (source_code) | 仅无status节点 | 官方渠道/数值与时间抽样未闭合 |
| 28 | P1 | CN_COMMODITY_EX_HOG_BASKET | daily | cert | 543 / 0 | 2026-08-28 | 1 (formula_version) | 未显式呈现 | 旧close收益不符结算规则；真实合约/换月/基点未闭合 |
| 29 | P1 | CN_COMMODITY_SLEEVE_CONTRIBUTION | daily | cert | 973 / 0 | 2026-08-28 | 7 (formula_version,sleeve) | 未显式呈现 | 旧close收益不符结算规则；真实合约/换月/基点未闭合 |
| 30 | P1 | CN_FUTURES_WARRANTS | daily | cert | 130587 / 0 | 2026-08-28 | 474 (exchange,measure,symbol,warehouse) | stale | 历史数据/标签；本次未重新授予认证 |
| 31 | P1 | CN_PMI_ACTIVITY | monthly | cert | 220 / 0 | 2026-07-31 | 4 (measure,series) | 仅无status节点 | 历史数据/标签；本次未重新授予认证 |
| 32 | P1 | CN_PMI_INVENTORY | monthly | cert | 110 / 0 | 2026-07-31 | 2 (measure,series) | current | 历史数据/标签；本次未重新授予认证 |
| 33 | P1 | CN_PMI_PRICES | monthly | cert | 110 / 0 | 2026-07-31 | 2 (measure,series) | 仅无status节点 | 历史数据/标签；本次未重新授予认证 |
| 34 | P1 | CN_ORDER_INVENTORY_SPREAD | daily | derived | 0 / 5 | — | — | current | 依赖上游；此处D为system_as_of记录 |
| 35 | P1 | CN_PRODUCTION_ORDER_SPREAD | daily | derived | 0 / 5 | — | — | current | 依赖上游；此处D为system_as_of记录 |
| 36 | P1 | CN_CPI_HEADLINE | monthly | cert | 167 / 0 | 2026-07-31 | 3 (category,measure) | 仅无status节点 | 历史数据/标签；本次未重新授予认证 |
| 37 | P1 | CN_CORE_CPI | monthly | cert | 26 / 0 | 2026-07-31 | 3 (category,measure) | 仅无status节点 | 历史数据/标签；本次未重新授予认证 |
| 38 | P1 | CN_PPI | monthly | cert | 501 / 0 | 2026-07-31 | 9 (category,measure) | current | 历史数据/标签；本次未重新授予认证 |
| 39 | P1 | CN_INDUSTRIAL_VA | monthly | cert | 20 / 0 | 2026-07-31 | 3 (measure) | 仅无status节点 | 历史数据/标签；本次未重新授予认证 |
| 40 | P1 | CN_INDUSTRIAL_FINANCE | monthly | cert | 42 / 0 | 2026-07-31 | 6 (item,measure) | current | 历史数据/标签；本次未重新授予认证 |
| 41 | P1 | CN_FINISHED_GOODS_INVENTORY | monthly | cert | 14 / 0 | 2026-07-31 | 2 (measure) | current | 历史数据/标签；本次未重新授予认证 |
| 42 | P1 | CN_INVENTORY_TURNOVER | monthly | cert | 14 / 0 | 2026-07-31 | 2 (measure) | current | 历史数据/标签；本次未重新授予认证 |
| 43 | P1 | CN_CAPACITY_UTILIZATION | quarterly | cert | 9 / 0 | 2026-06-30 | 3 (industry,measure) | current | 历史数据/标签；本次未重新授予认证 |
| 44 | P1 | CN_M1_M2 | monthly | cert | 316 / 0 | 2026-07-31 | 6 (aggregate,measure) | current | 历史数据/标签；本次未重新授予认证 |
| 45 | P1 | CN_SF_TOTAL | monthly | cert | 237 / 0 | 2026-07-31 | 4 (measure) | current | 历史数据/标签；本次未重新授予认证 |
| 46 | P1 | CN_SF_COMPONENTS | monthly | cert | 744 / 0 | 2026-07-31 | 24 (component,measure) | current | 历史数据/标签；本次未重新授予认证 |
| 47 | P1 | CN_LOAN_STRUCTURE | monthly | cert | 279 / 54 | 2026-07-31 | 9 (borrower,measure,tenor) | current | 历史数据/标签；本次未重新授予认证 |
| 48 | P1 | CN_CREDIT_IMPULSE | monthly | derived | 0 / 5 | — | — | available,current | 依赖上游；此处D为system_as_of记录 |
| 49 | P2 | CN_GDP | quarterly | cert | 216 / 0 | 2026-06-30 | 8 (aggregate,measure) | current | 历史数据/标签；本次未重新授予认证 |
| 50 | P2 | CN_USDCNY_CENTRAL_PARITY | daily | await | 0 / 0 | — | — | awaiting_source_certification | 生产库无值；来源待认证 |
| 51 | P2 | CN_USDCNH_FXCM | daily | await | 0 / 0 | — | — | awaiting_source_certification | 生产库无值；来源待认证 |
| 52 | P2 | CN_USDCNY_CLOSE_1630 | daily | await | 0 / 0 | — | — | awaiting_source_certification | 生产库无值；来源待认证 |
| 53 | P2 | COMEX_GC_ACTIVE_MONTH_SETTLEMENT_USD_OZT | daily | await | 0 / 0 | — | — | awaiting_source_certification | 生产库无值；来源待认证 |
| 54 | P2 | LBMA_GOLD_PRICE_PM_USD_OZT | daily | await | 0 / 0 | — | — | awaiting_source_certification | 生产库无值；来源待认证 |
| 55 | P2 | EIA_BRENT_RBRTE | daily | await | 0 / 0 | — | — | awaiting_source_certification | 生产库无值；来源待认证；既有doctor记录EIA disabled |
| 56 | P2 | EIA_WTI_RWTC | daily | await | 0 / 0 | — | — | awaiting_source_certification | 生产库无值；来源待认证；既有doctor记录EIA disabled |
| 57 | P2 | UST10Y_NOMINAL_YIELD | daily | cert | 374 / 0 | 2026-08-28 | 1 (无键) | stale | 历史数据/标签；本次未重新授予认证 |
| 58 | P2 | UST2Y_NOMINAL_YIELD | daily | cert | 374 / 0 | 2026-08-28 | 1 (无键) | stale | 历史数据/标签；本次未重新授予认证 |
| 59 | P2 | UST_2S10S_SPREAD | daily | derived | 0 / 6 | — | — | current | 依赖上游；此处D为system_as_of记录 |
| 60 | P2 | CBOE_VIX_INDEX | daily | await | 0 / 0 | — | — | awaiting_source_certification | 生产库无值；来源待认证 |
| 61 | P2 | NASDAQ_SOX_INDEX | daily | await | 0 / 0 | — | — | awaiting_source_certification | 生产库无值；来源待认证 |

## 文件与代码定位

- catalog.py:37–103 列出 6/42/13 目录；catalog.py:340–394 为冻结 v3 标签生成；evidence.py:998–1028 定义单位、维度、数值及时区结构要求。
- source_contract_review.py:14–15 固定审查文件及其哈希；16–68 为 15 项/5 family 原因；73–107 将 v3 模型整体阻断并保留历史读取。
- worker.py:882–928 生成 available/total warning；当前投影绑定关系由 JSON/current_projection 直接保存，未用今天日期重述旧时效状态。
- tushare_context.py:1087 来源文本引用、1145–1147 新融资候选时间为空、1173–1177 旧 fallback 时间、1197–1198 库标签、1259–1296 normalized_hash 的实际计算。
- source_history.py:116–134 清单的 coverage、raw records 和 validated_candidate 标签；历史清单/认证包/新候选清单在 JSON 中区分保存。
- CONTEXT.md 的 Source Claim / Observation Identity / Public Available At / Source Certification Package / Model-usable Gap Resolution Rate 定义，及 ADR0013:7–9 是解释边界。

本盘点确认“哪些数据和证据真的存在、结构统计如何、当前模型为何受阻”。它没有把下载成功、哈希正确、历史 certified 标签、结构120日通过或旧 replay passed 自动提升为当前正式模型可用。
