票03 r2审查修复。r1已真实exit0，主代理重验104包文件、36+15各批前后身份相同；源码未集成根树。两轴审查已结束：先读根execution/review-03-combined.md、review03-spec-report.md、review03-standards-report.md。主代理重型实际exit1：5 failed/28 passed/73.68秒，软件/安装/材料身份不变，日志根execution/heavy-03-preflight-r1/pytest.log；旧报告与全部失败原件保留。

必须先按批准公开边界复现2项Spec（现为静态推断），再最小修复：
1. 日历预热中间日漏项却用更早日补足，不能变成140条/259条即available。反例保持正式120日期正确，删除2025-09-05并加入08-28，价格同样缺09-05且审核覆盖更早历史。应用必须根据合法日历原件/绑定范围发现缺项，不能由价格有值日推日历或硬编码2026日期/所有weekday即开市。可核验原trade_cal未过滤is_open请求的自然日范围完整性，或更好的等价原件完整性证据；区别完整日历与只有开市子集。如果必须最小扩展01日历原件的覆盖元数据/验证，主代理现在明确授权本票为该实际缺陷修改material_preflight相关日历证据传递及必要source_adapters日历守卫，不推翻01固定日期/持久收据语义；列清影响和既有fixture是否需合法闭市行。不在没有证明的情况下把一个漏行换成“闭市”掩盖。
2. core_history_input_missing保守拒收还不足以定位实际缺件。数值缺失、无可靠public时间、晚于消费cutoff、未认证、质量失败需可区分，并保留相关版本/获取对象定位；不可见候选的诊断ID必须与实际选中/采用血缘区别，不能让未来/未知版本进入正式inputs，也不能因未来修订存在而破坏旧合法版本。兼容通用reason并补具体cause字段也可，自行用最小清晰接口。
3. Standards覆盖认证包列表重复是P3建议。当前review阶段可计算一次实际覆盖包列表，复用判定与血缘，避免不必要更广重构。

收到新语义后修正5个实际旧heavy失败，不改生产守卫去迎合旧断言：
- test_preflight_checks_core_history_before_the_requested_window[missing]/[late_public]原夹具没有独立日历、只2条价格。必须补足合法适用日历并按正式消费日定位；注意原late_public是08-27值在08-28 08:00Z已发布，对08-28正式结果本应可用，不能仍按08-27自身截止拒收！保留真实“晚于正式消费cutoff不可用”的负例及到消费前已公开的正例，旧日期/URL原用途不批量改动。不要让正例因根本未执行核心检查而真空通过。
- calendar_artifacts[None]/[late_capture]及registered_calendar_claims[bound]目前把所有CN_TRADE_CALENDAR gap都当原件不合格；新的core_formula_calendar_history_missing是预热覆盖缺口，应明确区分日历原件资格与公式历史范围，或通过合法日历材料补足。不能清空/删除真实预热缺口以求旧断言绿。
如需要调整旧测试，保持原行为目标，复用新有效反例而非机械重复；不要删除关键回归或绕认证状态。

你只可运行获准轻量定向/静态检查；已经有主代理heavy真实RED，可据此改这些测试材料，修改后的heavy GREEN由主代理统一排队运行。交回可审差异、确切受影响节点和软件安装/材料身份，不自己启动heavy。本轮r2报告implementation-report-r2.md、日志r2前缀、heavy-request-r2.md，原r1不覆盖。除了上述明确日历覆盖范围扩展，沿原模块归属。请自主开始，不询问已授权普通选择。

原隔离/流程指令仍适用：
你是票03独立实施代理，只通过本次direct codex exec，不再委派。用户已采纳Goal并行授权，覆盖旧只读限制。工作树 /home/tywin/worktrees/datasourceRF-window-20260922/ticket-03，Git基线bb737200024369f2938d26d1cc49f5f77f18a1b1，并已叠加主代理通过审查的01软件交付（根effort execution/integration-01.json、isolation-03.json）。初始完整软件/包身份在本树.task-runtime/initial-identity.json，包含继承01的7文件，审查你的差异时不能冒认继承内容为你的改动。

先读AGENTS/CONTEXT、docs/agents/testing.md、相关ADR0006/0018/0019；完整.scratch/pring-window-publication-20260922/spec.md、本票issues/03-core-formula-warmup.md、直接前置issues/01-fixed-window-calendar.md及根execution/integration-01.json。01经真实CLI预检的120日/259日calendardates、36受影响验证与两轴0发现已交付软件，最终shared full suite等后续集成版本统一运行，不再重复询问是否能开始。本票不等待08/09真实来源整票完成。
读取 /home/tywin/.codex/skills/implement/SKILL.md、tdd/SKILL.md及tests.md/mocking.md。采用已批准公开任务/API或PUBLIC/SYSTEM选择、趋势/阶段领域边界TDD，逐例RED→最小实现→GREEN，重构留审查阶段。不要写私有helper镜像测试，不绕来源认证/直接改DB。先复用现有有效用例和合法合成获取/审核材料。

交付目标是本票全部5项AC：从冻结规则导出固定正式120日所需259日/139预窗口和各结果消费cutoff；每个真正公式输入认证、质量、发布证据、原件/版本逐点可追溯；窗口内全合法而唯一预热未知/未来/未认证/坏原件应明确阻断，同公开入口补入合格版本恢复；日期精度周末下一自然日、SYSTEM与PUBLIC区分；中间缺口不靠最早日期/行数掩盖；状态初始化与基础公式用途分开，不改变趋势公式或持续性规则。切勿把整个checks_complete提前改true（04/05等仍未完成）。

模块归属：本票可改 material_preflight.py核心输入需求/核心预检分支、必要新核心需求模块、core_history.py、source_adapters.py的核心逻辑、model_evaluation.py的核心输入/回放分支及专用测试。06同时拥有model_evaluation.py中的融资分支，禁止动它；也禁止修改candidate_admission.py/CNY030或source_contract_review.py/融资发布证明。不改CLI固定窗口语义/01日历分支。若必需改其他共享模块，先给主代理具体文件和最小范围，不向用户重复请求普通授权。主代理处理顺序集成冲突，不新增产品依赖边。

隔离已实测：103安装文件内容与源码同，236软件输入与集成根相同；本树venv由01副本独立复制（无共享包inode）并重装项目，入口脚本前缀已改成本树。运行 .venv/bin/python，正确CLI是python -m pring_cycle，不是无入口的pring_cycle.cli。独占TMPDIR=/tmp/datasourceRF-window-20260922/ticket-03/tmp，材料root同前缀/materials；RuntimePaths实测有效。禁止写根树、他树、全局venv、生产runtime/模型指针；不切分支/创建worktree/commit/merge/改票状态/安装新依赖/访问真实网络。

可运行必要类型/格式/轻量定向红绿，tools/check.py quick明确文件/node。新259日×3核心的有界合成获取/预检反例如不调用完整生命周期/prepare_isolated_candidate_inputs可按实际轻量执行，实际超过3分钟如实记录并停止扩大批次。已有heavy清单文件、完整材料构建/校准/回放/全套一律主代理调度，不靠新文件名隐藏重型。若唯一合法边界需heavy，先写实际可执行新测试节点并提交heavy-request.md含准确命令/材料/预期资源，主代理运行真实RED后继续；不要发明未发生的RED或通过绕门求绿。

源码改动后使用当前独占环境 uv pip install --python .venv/bin/python --no-build-isolation --no-deps --reinstall .，逐文件比对src与实际发行物；别用uv sync改其他假设。记录前后software与材料身份，不能只比文件名。定期写.task-runtime/progress.md，最终.task-runtime/implementation-report.md（命令/退出码/日志/成本/代码安装材料/缺口/重型请求）；主代理负责两轴review/验收/票面/提交。请开始实际实施，不重复已批准访谈或重建spec。
