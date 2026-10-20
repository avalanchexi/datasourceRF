**结论：部分满足，不能认定两票已完整按规格验收。** D2 的主要问题已修复，B2／B4／K2／K4 也已有单日汇总测试；但票 12 明确要求的 v0006 宏观数据夹具未实现，票 11 新增的 `initial` 文案存在边界错误，旧数据补齐与更正路径仍缺针对性断言。

审查范围为 `main...macro-followups`（`2f876b2` → `ba845dc`），未修改文件。本次未执行 pytest：集成测试需要写临时运行库，与只读约束冲突；当前系统解释器也缺少 Dash、SQLAlchemy。以下“测试覆盖”均指已审阅断言，票面运行结果另行注明。

1. **票 11：逐日显示主结论、把握程度、滞回状态——部分满足。**  
   [cockpit.py:2556](/home/tywin/worktrees/datasourceRF-mf/src/pring_cycle/cockpit.py:2556) 使用独立宏观行；[页面测试:233](/home/tywin/worktrees/datasourceRF-mf/tests/web/test_macro_stage_history_board.py:233) 覆盖明确／倾向及 initial、held、agrees、replaced 四种状态，排除了价格阶段、上一确认和原因文案。满足决定 58、验收第四节第 9 项及 D2 的主要要求。  
   **遗漏：**[cockpit.py:2537](/home/tywin/worktrees/datasourceRF-mf/src/pring_cycle/cockpit.py:2537) 将 `initial` 固定解释为“生效首日”，而 [macro_judgement.py:424](/home/tywin/worktrees/datasourceRF-mf/src/pring_cycle/macro_judgement.py:424) 在此前结论无阶段时也产生 `initial`。例如生效日按决定 49 发布“无可取阶段”，下一交易日首次取得阶段，页面仍会误称“生效首日”。建议改成“无既往主结论，取当日原始判断”，并补这个边界用例。

2. **价格区间抽屉不变——满足。**  
   [cockpit.py:2802](/home/tywin/worktrees/datasourceRF-mf/src/pring_cycle/cockpit.py:2802) 保留价格列表路径，仅宏观列表指定新行渲染器；[页面测试:277](/home/tywin/worktrees/datasourceRF-mf/tests/web/test_macro_stage_history_board.py:277) 锁定非典型组合、上一确认及原因文本。既有 `test_an_interval_drawer_lists_each_day_with_its_correction_version_and_projection` 还覆盖缺口、更正版本和链接。建议保留这些回归断言。

3. **票 11 偏离：新增发布层记录、仓储读取——满足，可接受。**  
   [projections.py:389](/home/tywin/worktrees/datasourceRF-mf/src/pring_cycle/projections.py:389) 按各日投影 ID 读取已发布原始判断及滞回状态；[p0.py:366](/home/tywin/worktrees/datasourceRF-mf/src/pring_cycle/p0.py:366) 对正在发布的当天使用当前宏观块。它是完成逐日展示所需的数据贯通，没有增加判定规则或前端补算。  
   [发布测试:90](/home/tywin/worktrees/datasourceRF-mf/tests/integration/test_macro_stage_history.py:90) 精确断言生效前两日、initial、agrees、held×9、replaced，能证明历史行使用各日状态。建议接受此偏离，无需为维持“只改页面”而削减实现。

4. **决定 33：阶段史只记主结论，不记候选 k/10——满足。**  
   [display_projection.py:90](/home/tywin/worktrees/datasourceRF-mf/src/pring_cycle/display_projection.py:90) 只投影状态摘要，held 附原始阶段／把握程度，replaced 附完成门槛，没有候选阶段计数。上述发布测试同时锁定主结论九日保持、第十日替换。  
   结合后续决定 58，补充“如何保持或替换”的说明合理；没有把候选当作阶段史主结论。建议维持这一边界。

5. **旧投影兼容及“滞回状态未记录”——满足；自动补齐承诺的测试证据部分。**  
   [页面测试:159](/home/tywin/worktrees/datasourceRF-mf/tests/web/test_macro_stage_history_board.py:159) 覆盖有宏观阶段但缺新字段的提示；`test_a_set_from_before_the_macro_row_shows_its_four_rows_and_says_why` 覆盖完全没有宏观行的旧投影。符合规格第 51 项及禁止前端补算的约束。  
   需要澄清：下一次发布补齐的是**新投影中的历史展示行**，固定访问旧投影仍会显示“未记录”，旧投影本身不被修改。建议补一例“旧投影缺字段但保有宏观块 → 新发布补齐 → 旧投影保持原样”的集成测试，并修正票面措辞。

6. **更正说明、投影链接与 relink——部分满足。**  
   [cockpit.py:2568](/home/tywin/worktrees/datasourceRF-mf/src/pring_cycle/cockpit.py:2568) 明确保留更正说明和链接；[p0.py:492](/home/tywin/worktrees/datasourceRF-mf/src/pring_cycle/p0.py:492) 用 relink 后宏观块重建展示。实现路径合理。  
   但 `test_a_correction_under_the_macro_judgement_names_the_price_stage` 在[第 215 行](/home/tywin/worktrees/datasourceRF-mf/tests/web/test_macro_stage_history_board.py:215)检查整段页面文本，即使宏观抽屉漏掉说明，价格抽屉仍能使断言通过；现有 relink 测试也未断言新字段 `macro_hysteresis`。建议定位宏观抽屉检查说明、旧／新投影链接，并验证更正后的状态而非更正前状态。更正说明中出现“价格阶段”是在解释更正范围，不应作为 D2 的重复价格描述删除。

7. **票 12：B／K 四格单日汇总映射——满足。**  
   新测试经 [publish:75](/home/tywin/worktrees/datasourceRF-mf/tests/integration/test_confirmation_publish.py:75) 调用 `DaySummaries.summarize_target`，不是只测映射纯函数。与 `signal-table.md` 第 42、43、51、52 行相符：

   | 格 | 测试断言 | 判定及证据 | 建议 |
   |---|---|---|---|
   | B2 | IV→V；相对 III 前进 2；萌芽，不入清单 | 满足，[第 780 行](/home/tywin/worktrees/datasourceRF-mf/tests/integration/test_macro_signals.py:780) | 保留 |
   | B4 | I→II；前进 1；与 R5 同转换而成形，入清单 | 满足，[第 814 行](/home/tywin/worktrees/datasourceRF-mf/tests/integration/test_macro_signals.py:814) | 保留 |
   | K2 | V→VI；相对 I 后退 1；萌芽，不入清单 | 满足，[第 822 行](/home/tywin/worktrees/datasourceRF-mf/tests/integration/test_macro_signals.py:822) | 保留 |
   | K4 | II→III；维持；目标等于价格阶段而确认，入清单 | 满足，[第 785 行](/home/tywin/worktrees/datasourceRF-mf/tests/integration/test_macro_signals.py:785) | 保留 |

8. **票 12：“核心与宏观数据都放在 v0006”——不满足。**  
   核心通过假 TuShare 原件进入 v0006；广度和带 `formula_version／sleeve` 的分项贡献也已准备。但 [夹具:685](/home/tywin/worktrees/datasourceRF-mf/tests/integration/test_macro_signals.py:685) 明确没有宏观 claim，违反[票 12 第 3 行](/home/tywin/worktrees/datasourceRF-mf/.scratch/macro-stage-20261017/issues/12-breadth-basket-signal-cases.md:3)。Comments 的工作量解释并不等于规格已获变更批准；决定 57 只允许延后、不阻塞激活。  
   建议补最小宏观原件集合，无需覆盖全部官方数据族。仓库已有 [macro_rows:218](/home/tywin/worktrees/datasourceRF-mf/tests/integration/test_worker_registered_catalog.py:218) 等假宏观交付构造，可调查复用。若决定缩减要求，应明确修订票面，不能直接视为全部完成。

9. **票 12 偏离：用弱判断兜底作为主结论——行为合法，验收证据部分。**  
   弱判断取典型价格阶段符合决定 35，本身不是生产逻辑违规；但两例中宏观主结论均等于价格阶段，无法区分“归组相对宏观主结论”和“归组误用价格阶段”，也无法区分“确认看价格阶段”和“确认误看宏观阶段”。证据为[第 773 行](/home/tywin/worktrees/datasourceRF-mf/tests/integration/test_macro_signals.py:773)、[第 807 行](/home/tywin/worktrees/datasourceRF-mf/tests/integration/test_macro_signals.py:807)。  
   既有 R2 用例在第 312 行覆盖宏观、价格阶段不同的归组，降低了公共逻辑风险，但不替代本票的明确夹具要求。建议至少新增一例两阶段不同的 B／K 场景，同时锁定归组基准和确认基准。

10. **票 12 偏离：只测首日成熟度——满足，可接受。**  
    决定 43 的萌芽、两格同转换成形、价格阶段确认均已覆盖；连续五日成形由既有 `test_relative_momentum_maps_to_its_cell_s_transition_once_formed` 覆盖，四日仍萌芽也有反例。生产代码在 [macro_signals.py:297](/home/tywin/worktrees/datasourceRF-mf/src/pring_cycle/macro_signals.py:297) 对这些价格信号共用成熟度循环。票面没有要求四格各跑五日，建议接受这项取舍。

11. **对照表其他边界——部分覆盖，属于补强建议。**  
    K2 新例只覆盖单一分项上涨，K4 只覆盖少数分项下跌；其余读法由[清单测试:105](/home/tywin/worktrees/datasourceRF-mf/tests/integration/test_macro_signals.py:105)锁定。对照表要求普涨、普跌、持平、不一致等“不落格”，新增两例的集合断言只能证明该场景没有另外两格，不能证明这些负例。120 日数据也采用每天同号，难以发现窗口误缩短。建议按风险补参数化负例及一个 20 日／120 日方向不同的案例；这些缺口不应被描述成已经发现生产错误。

12. **两票“两例冒烟通过”——满足票面记录，本次未独立复跑。**  
    [票 11 第 25 行](/home/tywin/worktrees/datasourceRF-mf/.scratch/macro-stage-20261017/issues/11-macro-interval-drawer.md:25)记录两例 2 passed、66 秒；[票 12 第 21 行](/home/tywin/worktrees/datasourceRF-mf/.scratch/macro-stage-20261017/issues/12-breadth-basket-signal-cases.md:21)记录两例与信号测试合计 25 passed、135 秒。测试名符合仓库要求。建议将其标为实施者执行证据，与本次静态审查区分。
