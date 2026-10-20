你继续票06 r3。r2已真实exit0，103安装文件一致，36相关通过；主代理已完成两轴审查（根目录execution/review06-standards-report.md与review06-spec-report.md），需要继续实际交付，不把部分软件当票完成。先读这两份、当前本树implementation-report-r2.md和heavy-request.md，再读完整父spec/本票及ADR0013/0018/0019。原日志/报告全部保留。

本轮顺序：
1. 完成可信的逐值/逐版本发布证据正向输入合同。现有TuShare日值没有发布字段，手填release_at仍必须拒绝；必须新增或复用正式审核/导入通道，将SSE与SZSE各自的日期、两个原始元级字段、精确数值版本、证据原件hash与实际取得收据绑定，再以两边最晚可靠时间形成合计可见性。有可靠日期用publication_times按Asia/Shanghai下一自然日，不延到交易日；任何一侧未知仍None，不能套更新日程/HTTP模板/下载时间。先实际公开证据入口RED，再最小实现。可复用futures_inputs/market_breadth的不可变证据包+内容审核通道，但必须核真实合同语义，不生造官方已有的字段/JSON结构。合成证明材料要明确synthetic并走同一审核门，不能把修改dataclass时间作为发布原件。
2. 当前新身份在search_evidence会复验原件，但model_evaluation只核旧CN_MARGIN_BALANCE。PUBLIC正向通后，用已批准领域公开边界或实际预检/回放入口复现“同一新身份损坏原件选值拒收而回放漏检”，统一消费者核验。新增授权可修改model_evaluation.py中融资分支及最小新模块/对应测试；其他家族与窗口代码不动。
3. 只要完整Worker仍要新合法active材料，写成真实可执行测试节点与准确前置/命令，让主代理重型排队；不要仅再写一份未实现伪代码后重复说完整链未测。公开任务持久→process_pending_run→投影/报告读取、两个measure/sse_szse/血缘/历史不变。主代理之后按07准备通用生命周期，不能伪造active或覆盖旧manifest。你可以准备此测试，但执行需要主代理重型排队，不写依赖未出现业务RED的生产补丁。
4. 现在是review修复阶段，两项Standards建议可按收益处理：margin family repeated switches配置合并、共享合法候选测试fixture；不为风格扩大重构。

代理源码归属扩展：原8文件之外可新增明确融资发布证明模块及必要测试、model_evaluation融资分支。candidate_admission.py归02，material_preflight/core公式归01/03，不修改。必要共享cli入口可先提供公共Python API，经主代理统一整合CLI，勿与他树竞争写入。新功能必须从批准公开边界验证；禁止私有helper测试。正确进程CLI入口是python -m pring_cycle（-m pring_cycle.cli没有入口，会空退出）。

仍只准必要轻量测试，完整生命周期/prepare_isolated_candidate_inputs/重型文件不自行运行。若正例唯一合法链要重型，先落可执行最小反例及重型请求，不绕认证守卫；主代理负责运行，再根据真实RED修复。重装并逐文件比对私有安装，类型/格式/相关测试如实留证，材料与软件身份分开。本轮终报告.task-runtime/implementation-report-r3.md与heavy-request-r3.md，日志r3前缀，不覆盖旧报告。禁止新委派/提交/改票/写其他树或生产。请自主完成可执行工作，不问已授权普通实现选择。

以下旧提示仅提供原隔离和范围历史；与本轮相冲突处以上为准：
继续同一票的未完成实施。主代理已核验前一进程的终态后才启动本续接；不要重做已完成部分。先读 .task-runtime/implementation-report.md（若存在）、progress.md 和 parent-instructions.md。

本次明确修正之前 TMPDIR 设置：允许读写本票独占树外运行目录 /tmp/datasourceRF-window-20260922/ticket-06；TMPDIR 与材料缓存已设置到该目录。通过 RuntimePaths.discover 实际核验后继续。已有最小 CLI 反例属于轻量合成合同，主代理查实 prepared_request 没有长历史构建；允许恢复该用例并执行真实 red，然后最小实现、重装私有副本、验证 green，继续本票全部软件要求。其余重型仍排队。不能因先前未收到普通目录授权而再等待用户。

你是本Goal中票06的独立实施子代理。只在工作树 /home/tywin/worktrees/datasourceRF-window-20260922/ticket-06 工作。当前工作树基线 bb737200024369f2938d26d1cc49f5f77f18a1b1，主代理复制了当前必要未提交文档、ADR和材料。不要再创建worktree、切分支、提交、merge或改票状态，主代理负责集成、两轴code-review、验收与提交。

用户已显式采用 .scratch/pring-window-publication-20260922/goal-prompt.md 的并行实施授权，覆盖旧委派文档的只读限制。你允许写自己的源码和测试；禁止写 /mnt/d/cursor/datasourceRF 原工作区、其他工作树、全局venv、生产runtime或正式模型指针。不要外派更多代理。

先读 AGENTS.md/CONTEXT.md、docs/agents/testing.md、相关ADR（尤其0014/0016/0019/0020）、完整 .scratch/pring-window-publication-20260922/spec.md 和 .scratch/pring-window-publication-20260922/issues/06-margin-two-exchange-delivery.md；按需读取其中历史交付。读取 /home/tywin/.codex/skills/implement/SKILL.md、tdd/SKILL.md及tests.md/mocking.md，严格公开接缝TDD，一个失败行为→最小修复→相关验证，不实现其他票。

任务边界：拥有 CN_MARGIN_BALANCE_SSE_SZSE 真实采集/交付/消费合同及专用测试。可改 tushare_context、source_certification、evidence、metric_contracts、必要消费者。不要改 candidate_admission 的迁移白名单（02独立处理CNY030）；如确需交叉改动，说明具体接口并留给主代理顺序整合。沿已批准融资两所语义，不能沿旧三所合同只改ID。

隔离已由主代理验证：独立 .venv、.task-runtime/tmp、materials、logs和uv-cache。使用 .venv/bin/python；修源码后必须重装本副本并逐文件比对安装与src，不能只比文件名。重装用当前环境的 uv pip install --python .venv/bin/python --no-build-isolation --no-deps --reinstall . ，UV_CACHE_DIR 已设为本工作树私有目录；hatchling已装。禁止 uv sync（会改其他环境假设）或安装新依赖、访问真实网络服务。

测试权限：可运行类型/格式检查及必要的轻量定向红绿验证，经 tools/check.py quick 选择明确文件/node。当前不授予任何重型测试、完整生命周期材料构建、校准、回放或全套权限（包括 tools/check.py HEAVY_FILES 与调用 prepare_isolated_candidate_inputs 的测试）。若唯一能验证本票的合法公开边界需要重型执行：先写最小反例，把准确命令、成本预期和需要的材料写入 .task-runtime/heavy-request.md，停止依赖其结果的生产修改，交回主代理排队执行；不要绕重型名单/内部mock/伪造认证以求快速绿。现有可复用的 prepared_request/admit_complete_candidate 与完整长历史材料构建要区分，按实际成本判定，疑问报告。

定期写简短 .task-runtime/progress.md；最终必须写 .task-runtime/implementation-report.md，包含：改动文件，红/绿各实际命令、退出码、结果及日志，实际安装包与材料身份，尚需重型检查和未满足的票面条件。仅读码推断要标注。报告中文精炼，不能把部分实现说成整票完成。请直接开始本票，返回真实成果；不要重复产品访谈或等待已授予的普通实施许可。


以上原提示中仅限工作树写入和 TMPDIR 位于工作树的部分由本次树外专属目录授权覆盖。报告用 .task-runtime/implementation-report-r2.md，原报告/日志保留；日志加 r2 前缀。重构在 code-review 阶段，实施使用逐例红—绿。