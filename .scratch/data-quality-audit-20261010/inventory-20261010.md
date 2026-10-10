# 数据质量现状盘点（2026-10-10，Codex 只读）

> 来源：`codex exec -s read-only`；对象为最新完成运行 `run-a8675946cf7fa1b060b4`（目标日 09-30，受 lookback/30 影响）。标"读码推断"者未实测。

**结论：取数和模型输入已有多道检查，但尚未形成完整性闭环；输出侧主要验证规则执行与内部一致性，缺少独立的正确性基准。最新运行也不能沿用验收记录的“58 个成员全部 current”结论。**

本次仅查文件及 SQLite `mode=ro`，未修改文件、运行测试或业务命令、访问外网。以下 SQL 结果统一取最新完成运行：`run-a8675946cf7fa1b060b4`，模型 **v0015**，目标日 **2026-09-30**，北京时间 **2026-10-10 15:23:56** 完成；投影为 `projection-8885a639914a804b7ebb`。最新按 `parent_run.status='completed'` 联接 `run_step_event` 的完成时间确定。

**一、数据获取是否完整**

1. **“应取什么”由模型清单、指标目录、日历和回看声明共同定义。** 模型冻结指标定义、公式与确认度规则；交易日历确定目标日和 120 日窗口，发布注册表及预告确定应有期，`lookback` 再展开成员和公式所需历史期，并非每项都要求 120 条。证据：[models.py:483](../../src/pring_cycle/models.py:483)、[freshness.py:417](../../src/pring_cycle/freshness.py:417)、[full_run_requirements.py:81](../../src/pring_cycle/full_run_requirements.py:81)、[lookback.py:210](../../src/pring_cycle/lookback.py:210)。

2. **现有机制分别检查请求、期次、时效和核心可用性，不能互相替代。**

   | 机制 | 检查口径与产出 |
   |---|---|
   | 取数回执 | `acquisition_request` 记录请求状态、结构校验、入库结果及来源记录数／标量数／入库数；`validated` 不等于已入库，更不等于期次齐全。[acquisition.py:419](../../src/pring_cycle/acquisition.py:419)、[acquisition.py:467](../../src/pring_cycle/acquisition.py:467) |
   | 最终取数计划 | 对声明的“指标×期次×成员”重新选值，记录 `local_complete`／`model_input_missing`，存于 `full_run_gap_plan` 的 `final`。[full_retrieval.py:619](../../src/pring_cycle/full_retrieval.py:619)、[full_retrieval.py:829](../../src/pring_cycle/full_retrieval.py:829) |
   | 批次时效 | `batch_freshness` 比较最新持有期与运行截止时点的发布期、应有期；主要检查尾部落后，不扫描全部历史空洞。[freshness.py:320](../../src/pring_cycle/freshness.py:320)、[freshness.py:499](../../src/pring_cycle/freshness.py:499) |
   | 发布缺口清单 | `cycle_overview.gap_list` 每指标一行，合并时效、取数失败、拒收、授权、来源冲突、公式失败、未请求及列表未覆盖等原因。[freshness.py:832](../../src/pring_cycle/freshness.py:832)、[freshness.py:934](../../src/pring_cycle/freshness.py:934) |
   | 核心就绪／缺口说明 | 三核心检查窗口缺日、冲突、身份、原件及目标日落后；只差一期可沿用，更多则阻断正式阶段，结果存 `p0_assessment`。`data_gap_notice` 是另行显式请求生成的核心缺口说明，本库目前 **0 条**。[day_summary.py:369](../../src/pring_cycle/day_summary.py:369)、[projections.py:236](../../src/pring_cycle/projections.py:236) |

3. **最新运行：目录 61 项，发布缺口 36 项，失败回执 18 条。** SQL 按冻结模型 `metric_definitions`、目标投影 `gap_list`，以及 `full_run_acquisition JOIN acquisition_request` 分组得到：

   | 指标／类别 | 数量 |
   |---|---:|
   | 目录指标 | **61**：P0 6、P1 43、P2 12；P0 不全是核心价格 |
   | `missing / two_or_more_periods_behind` | 33 |
   | `missing / period_not_requested` | 2 |
   | `license_missing / restricted_license` | 1 |
   | 其他发布缺口类别 | 0 |
   | 回执合计 | **153**：validated 135、failed 18 |

   | 失败来源／接口 | 数量 | 原因 |
   |---|---:|---|
   | TuShare `fut_basic` | 8 | `tushare_context_observations_missing` |
   | TuShare `fut_trade_cal` | 4 | 同上 |
   | TuShare `fut_wsr` | 6 | `negative_cache_active`，被负缓存拦截，不能算六次外部请求失败 |

4. **存在“应取却没进入检查范围”及“计划有缺口、发布清单未充分表达”的可能，属读码推断。** 未登记指标／成员不会自动发现；P2 日频、普通低频主要按声明的回看期检查，日历未覆盖的回看期还可能被截短，而发布清单并未无条件收录每一个历史缺期。[lookback.py:192](../../src/pring_cycle/lookback.py:192)、[lookback.py:433](../../src/pring_cycle/lookback.py:433)、[lookback.py:505](../../src/pring_cycle/lookback.py:505)、[freshness.py:1009](../../src/pring_cycle/freshness.py:1009)。留存另有明确例外：核心窗口前输入即使被投影引用也可删除，最新核心输入 **480 个编号中 120 个已无法联接原始声明**；这是追溯缺口，不等于当时没取到。[retention.py:169](../../src/pring_cycle/retention.py:169)

**二、输入 Pring 模型是否完整**

5. **模型输入检查已细到成员和期次，但“17 项完整”必须说明口径。** `ModelInputSelector` 按冻结目录、指定成员及原件复核判断可用性；确认度再检查主要成员回看缺期、时效、读法是否可计算，派生项不独立计票。[search_evidence.py:182](../../src/pring_cycle/search_evidence.py:182)、[confirmation.py:1202](../../src/pring_cycle/confirmation.py:1202)。**非典型组合会在这些指标级缺失判断前返回**，令指标级 `missing=[]`；必须查看 `members[].missing/evidence_status`，不能据空列表认定完整。[confirmation.py:1186](../../src/pring_cycle/confirmation.py:1186)

6. **最新最终计划缺 7 个“指标期”，涉及 6 个指标；实际冻结输入编号合计 2189 个。** SQL 结果如下，计划行数、输入编号数与确认度项数是三个不同分母：

   | 口径 | 最新结果 |
   |---|---|
   | `final.requirements` | 3067 行：完整 3057、缺失 7、运行证据 3；另有 8 条公式需求 |
   | 投影模型输入编号 | 核心 480、宏观 1709，合并去重 **2189**；宏观全部可追溯 |
   | 核心沿用 | **0**；三核心均 `validated`，目标日均为 09-30 |
   | 批次时效 | **58 项**：current 23、awaiting_release 1、missing 1、stale 33；落后一期 **0 项** |
   | 17 项确认度 | 主要成员缺期 **0 项**；58 个成员为 **current 55、stale 3**，全部关系为“不适用” |
   | stale 成员 | 流动性投放 `net_injection`、DR007 主成员、SHIBOR 1W 辅成员 |

   | 缺失指标 | 期次／成员 |
   |---|---|
   | 期货仓单 | 2026-07-21：CU、RB、RU、SC、SP |
   | 期货仓单 | 2026-09-09：PP |
   | USDCNY 16:30 | 2026-09-29 |
   | EIA Brent、WTI | 各缺 2026-09-30 |
   | SOX | 2026-09-29 |
   | 两融 | 2026-09-30：融资余额、融资买入额 |

   指定验收运行的宏观输入为 **2775**、成员 **58 current**，最新已经变化；且三核心批次标签记录 `held=09-30、due=10-08、periods_behind=6`，应核对日历覆盖与回退，不能直接解释为真实缺六个交易日，具体成因本次未证实。日历未覆盖时回退工作日的代码见 [trading_calendar.py:406](../../src/pring_cycle/trading_calendar.py:406)。

7. **值可疑并非完全没人管，但检查偏重契约和来源一致性。** 已检查单位、维度、有限数、注册来源契约与原件；跨注册来源差异超过 0.5% 或接近十进制单位倍数会标冲突，但资讯／检索值不全部参加该冲突比较。[evidence.py:1921](../../src/pring_cycle/evidence.py:1921)、[evidence.py:1860](../../src/pring_cycle/evidence.py:1860)。未发现统一的异常跳变、合理区间或独立选源正确性检查，**读码推断**：单一来源数值错但格式合法、多个来源一致地错、语义规则漏识别，仍可能通过。

**三、Pring 模型输出是否正确**

8. **输出是结构化分析结果加报告快照，不只是一个阶段号。** 正式阶段由三核心机械映射，当前阶段可能为空；核心状态／候选、上一确认阶段、确认度、库存象限及阶段史等存于 `analytical_dataset` 六个数据集，投影身份存 `projection_set`，报告正文存 `report_snapshot.body_json`。[p0.py:180](../../src/pring_cycle/p0.py:180)、[reports.py:750](../../src/pring_cycle/reports.py:750)。最新 SQL 显示 **债牛、股熊、商品牛，非典型组合，current_stage=NULL**；报告 `report-ac55500c5f7543e9555f` 已完成，由 `codex_cli` 生成。

9. **已有较强的规则用例与发布一致性校验，但不足以证明经济判断正确。**

   | 已有手段 | 覆盖与边界 |
   |---|---|
   | 规则测试 | 六种典型组合、两种非典型组合、核心不可用；趋势噪声／持续确认／中断反转；确认度六阶段条件、缺期、时序宽限与成熟度。[test_pring_stage.py:10](../../tests/domain/test_pring_stage.py:10)、[test_trend_state.py:56](../../tests/domain/test_trend_state.py:56)、[test_confirmation_monthly_indicators.py:377](../../tests/integration/test_confirmation_monthly_indicators.py:377)、[test_confirmation_timing.py:103](../../tests/integration/test_confirmation_timing.py:103) |
   | 发布前校验 | 重验核心状态到阶段映射、数据集引用一致、确认度计数、库存关系、宽限及输出结构；事务保证整套发布。[projections.py:414](../../src/pring_cycle/projections.py:414)、[projections.py:488](../../src/pring_cycle/projections.py:488) |
   | 正文一致性 | 结构化阶段／核心／结论必须相等，`_stated_stages` 等检查正文里的阶段、计数和归因；依赖限定词句匹配，**读码推断**仍可漏掉其他措辞的矛盾。[reports.py:1213](../../src/pring_cycle/reports.py:1213)、[reports.py:1453](../../src/pring_cycle/reports.py:1453) |
   | 确定性及历史对比 | 有趋势逐前缀重算一致性测试，以及验收时比较选值、成员读法与输入差异；前者仍用同一实现，后者证明不退化，不是独立正确性证明。[test_trend_state.py:104](../../tests/domain/test_trend_state.py:104)、[acceptance-20261010.md:113](../../.scratch/backlog-triage-20261009/acceptance-20261010.md:113) |
   | 公开 Pring 12 月代理 | v0014 起已关闭，最新模型不计算，不能作为当前输出对照。[models.py:507](../../src/pring_cycle/models.py:507) |

10. **未发现现成的“冻结输入→独立引擎重算→逐项比对”闭环，也未发现完整真实案例的人工签核 golden 集或输出跨日稳定性报警，属读码推断。** 有明确期望值的合成规则案例，但旧回放／模型评估记录已退役，确定性报告只是复制已有结论，核心输入还存在上述留存断链。[0025_drop_model_lifecycle.py:12](../../src/pring_cycle/migrations/versions/0025_drop_model_lifecycle.py:12)、[reports.py:123](../../src/pring_cycle/reports.py:123)。`parent_run.outcome='changed'` 也不能当输出变化监控：代码在进入 completed 时直接赋该值。[runs.py:625](../../src/pring_cycle/runs.py:625)

**建议的检查清单雏形**

| 层次 | 优先检查 | 实现方式 |
|---|---|---|
| 获取 | 最终计划每个缺失指标期都能对应到发布缺口及具体原因 | **现有表 SQL**：展开 `final.gaps` 与 `gap_list` |
| 获取 | 按来源／接口统计失败、拒收、空响应、负缓存，分开计算 | **现有表 SQL**：回执及运行关联表 |
| 获取 | 从目标日到时效截止点，日历每日是否都有明确开休市依据 | **需要新代码**：现有材料在回执原件，需解析核对 |
| 获取 | 独立生成全窗口应有期，发现登记遗漏和历史空洞 | **需要新代码**，避免复用同一规划逻辑自证 |
| 输入 | 分开统计计划完整、主要成员缺期、成员 stale、核心沿用 | **现有表 SQL** |
| 输入 | 冻结输入编号全部能追到声明／派生血缘，单列核心留存例外 | **现有表 SQL** |
| 输入 | 同目标日运行比较指标、期次、成员、值及退出输入的原因 | **现有表 SQL**；原因自动归纳需新代码 |
| 输入 | 异常跳变、单位倍数、成员勾稽及来源冲突选值复核 | **需要新代码**，按指标定义阈值和关系 |
| 输出 | 阶段映射、确认度计数、报告与投影结构化结论一致 | **现有表 SQL**可批量复查 |
| 输出 | 冻结完整输入，独立实现趋势／确认度计算并对照 | **需要新代码**及可重算输入保留方案 |
| 输出 | 建立人工核对的典型、非典型、缺失、冲突、沿用 golden 案例 | **人工标注＋新代码** |
| 输出 | 同输入结果不变、跨日变化可解释；正文换措辞矛盾回归 | **SQL 可取差异；监控和语义校验需新代码** |
