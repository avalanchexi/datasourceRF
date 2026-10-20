你是04独立实施代理。用户已确认Goal严格开发流程与并行实施授权，只通过本次direct codex exec，不再委派。主代理已交付01软件切片，02准入亦已审并集成；本树继承01+02，已核独立安装与运行库。你只实施04上下文公式父输入诊断，不改票面/他树/生产指针/旧原件。

先读AGENTS/CONTEXT、docs/agents/testing.md及相关ADR0006/0018/0019；完整.scratch/pring-window-publication-20260922/spec.md、本票issues/04-context-formula-parents.md、01票及根目录execution/integration-01.json。访谈、规格、19票、公开测试边界已获授权，不重复审批或重新拆票。再读 /home/tywin/.codex/skills/implement/SKILL.md、tdd/SKILL.md/tests.md/mocking.md。主代理负责两轴code-review、串行heavy、验收与commit。

固定窗口04-01至09-22含120日，跨日不右移。公式预热须真实逐版本PUBLIC可见/认证/质量/原件/维度，各自需要自然日/月季期/事件比较，不套259日。基线bb737200024369f2938d26d1cc49f5f77f18a1b1 + 01七文件+02准入两文件；initial-identity.json载明实际软件/安装。继承内容不能冒认为你的交付。

关键先读主代理已接收的独立只读盘点：根 /mnt/d/cursor/datasourceRF/.scratch/pring-window-publication-20260922/execution/source04-formula-inventory-report.md。里面是读码线索，自己核验，不照抄当实测。各公式已有大量合法导入/选择/投影反例，不重写已冻结派生计算，不批量补机械镜像测试。

本票实际全部5项AC：
1. 冻结manifest实际启用8公式的父指标/维度/期次/比较基线/回看单位/消费cutoff可读；父表要表达stock core日期对OMO到期顺延的实际依赖，库存目录owner与派生output不同要分清。信用累计差分通常25月+9季原始输入而非只计24+8，贷款一月无需十二月，其他月份9组父维度不能漏；利率是有效事件而非10条日值；库存v1/v2分别按冻结语义。
2. 沿公开选择、派生/预检入口，合法完整材料独立数值期望以及全部实际父版本/原件血缘可追溯；失败具体指出缺期、缺维度、未知/未来、坏原件、修订不兼容及影响的结果。不能只最早日期/每指标有记录/父ID非空便算完成。
3. 不让旧派生/初始化历史掩盖最新必需父项坏/期次缺口；但未来或未知新修订不污染已可见旧合法版本。沿实际已采用版本做校验，不能因库里存在未来声明就阻断。
4. 必需/可选从实际ContextReplayScope分类：GDP虽P2但信用必需，UST可选；没有合法Treasury PUBLIC合同就保留未认证/未知及更早拒收证明，不能伪造时间。货币M1/M2四成员不新增剪刀差/12月同比需求，方向比较无上一公开观测即unknown。广度、成交額、商品篮子、ECB来源合同计算已有自己的父守卫，复用且说明覆盖，不重写为上下文公式。
5. 每个已执行检查保留执行状态，整体checks_complete不能提前true；其他03核心/05目录/06融资归属保持。

模块归属：material_preflight.py上下文派生/父需求诊断分支；必要新material_preflight_context.py或等价深模块；full_run_requirements.py的上下文需求、context_replay_scope.py的上下文依赖；必要context_projection.py的公开派生诊断结果及专用测试。接口形状依实际TDD最小确定，避免无证据先大改。禁止改03核心历史/日历source_adapters分支、05一般原件/维度search_evidence分支、06融资/source_contract_review、candidate_admission.py。确需越界时给主代理具体最小修改理由，普通技术选择无需问用户。并行不同工作树不会共享文件，主代理顺序集成这些预检hook；不要新增产品依赖边。

测试只在已批准公开CLI/API→真实仓库→公开查询/选择/投影，外部HTTP/时钟/CLI可替身，实际解析/选择/认证/持久层不mock。逐例RED→最小实现→GREEN，重构留review。新bounded公式材料测试可轻量，先实际缺口的一个反例，再逐个扩展。已有信用/利差/PMI/贷款/OMO用例复用，不把未跑的旧测试说本轮通过。任何tools/check.py heavy文件（尤其test_material_preflight/test_isolated_lifecycle/test_worker_registered_catalog）、完整模型准备/校准/回放/全套只能主代理执行，即使换文件名亦然。若遇必须heavy先写真实可执行节点和heavy-request.md给主代理跑RED，不预修未经复现的生产漏洞；静态诊断/工具检查可继续。

环境 /home/tywin/worktrees/datasourceRF-window-20260922/ticket-04/.venv，私有UV_PROJECT_ENVIRONMENT/UV_CACHE_DIR，UV_LINK_MODE=copy；TMPDIR=/tmp/datasourceRF-window-20260922/ticket-04/tmp，材料root同票/materials，不能在工作树内建RuntimePaths。使用.venv/bin/python；正确进程CLI是python -m pring_cycle。源码每变更后uv pip install --python .venv/bin/python --no-build-isolation --no-deps --reinstall .并核实际安装文件内容；不得uv sync或安装新依赖。禁止真实网络/凭据、跨树写入、变分支/创建worktree/commit/merge。

可运行受影响轻量tools/check.py quick具体文件或node及必要ruff/mypy；记录真实命令/退出码/成本、前后software inventory+实际imported_package+所有读取材料身份（包括calendar-plan等）。若批次超过3分钟如实记录并停止扩大，重型报请求。更新.task-runtime/progress.md；最终implementation-report.md附归属差异、基准、RED/GREEN与尚未执行边界、heavy-request.md。不要只交计划，请开始实际实施。
