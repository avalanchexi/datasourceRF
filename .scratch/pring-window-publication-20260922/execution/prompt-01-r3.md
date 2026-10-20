你继续票01审查修复阶段（r3），前一实施进程已经真实exit0；主代理的33项完整material_preflight重型回归也已exit0且身份未变。原报告/日志全部保留，不重跑无关已通过验证。

两轴审查已通过直接read-only CLI并行完成。先读主工作区 execution/review01-standards-report.md 和 review01-spec-report.md（路径完整前缀 /mnt/d/cursor/datasourceRF/.scratch/pring-window-publication-20260922/）；主代理已读代码确认两项Spec问题值得实际反例核验。

修复顺序：
1. CLI只传既有start/end、不加新增expected参数，在04-01至09-22窗口删06-10并用03-31补总数的真实反例，必须拒收119日。正式预检的默认应可靠绑定120日；短窗口诊断可以显式声明期望数量，收据应区别其范围，不能靠调用者记得附加守卫才满足本轮固定窗口。不要把2026日期硬编码进通用引擎；既有短窗口测试按原诊断目的显式传数量，保留旧日期/URL/历史用途。若更好的最小方案满足同一语义，可自行选择并说明，不增加业务访谈。先RED再最小实现。
2. 多份日历获取记录并存且被选中原件损坏，失败收据/公开重读必须指出实际失败acquisition/hash，不能用全历史acquisition_receipts清单代替关联。先走公开CLI反例证明，再最小修复；不要复制选择逻辑或开放内部mock。
3. Standards只有测试中read命令重复的P3建议。现在是review阶段，可在确有维护收益时提取同文件read_preflight_receipt helper，保持行为断言。

你仍仅获必要轻量定向验证权限；33项重型在源码变化后由主代理选取受影响范围重跑，不能把旧版本收据继续标当前。读取测试规则、准确保留红绿及安装身份。不要调用用户问题工具询问普通实现、目录配置或审查意见；需要产品新决定才报告主代理。最终 .task-runtime/implementation-report-r3.md，测试/安装日志用r3前缀。

继续同一票的未完成实施。主代理已核验前一进程的终态后才启动本续接；不要重做已完成部分。先读 .task-runtime/implementation-report.md（若存在）、progress.md 和 parent-instructions.md。

本次明确修正之前 TMPDIR 设置：允许读写本票独占树外运行目录 /tmp/datasourceRF-window-20260922/ticket-01；TMPDIR 与材料缓存已设置到该目录。通过 RuntimePaths.discover 实际核验后继续。已有最小 CLI 反例属于轻量合成合同，主代理查实 prepared_request 没有长历史构建；允许恢复该用例并执行真实 red，然后最小实现、重装私有副本、验证 green，继续本票全部软件要求。其余重型仍排队。不能因先前未收到普通目录授权而再等待用户。

你是本Goal中票01的独立实施子代理。只在工作树 /home/tywin/worktrees/datasourceRF-window-20260922/ticket-01 工作。当前工作树基线 bb737200024369f2938d26d1cc49f5f77f18a1b1，主代理复制了当前必要未提交文档、ADR和材料。不要再创建worktree、切分支、提交、merge或改票状态，主代理负责集成、两轴code-review、验收与提交。

用户已显式采用 .scratch/pring-window-publication-20260922/goal-prompt.md 的并行实施授权，覆盖旧委派文档的只读限制。你允许写自己的源码和测试；禁止写 /mnt/d/cursor/datasourceRF 原工作区、其他工作树、全局venv、生产runtime或正式模型指针。不要外派更多代理。

先读 AGENTS.md/CONTEXT.md、docs/agents/testing.md、相关ADR（尤其0014/0016/0019/0020）、完整 .scratch/pring-window-publication-20260922/spec.md 和 .scratch/pring-window-publication-20260922/issues/01-fixed-window-calendar.md；按需读取其中历史交付。读取 /home/tywin/.codex/skills/implement/SKILL.md、tdd/SKILL.md及tests.md/mocking.md，严格公开接缝TDD，一个失败行为→最小修复→相关验证，不实现其他票。

任务边界：拥有新窗口/日历预检相关最小改动及专用测试。优先 material_preflight、日历公共入口；不要改 CNY030 或融资合同。测试接缝是用户已批准的公开 CLI/API，不需再次问用户。不要造仅测试私有helper或只检验新常量的用例。

隔离已由主代理验证：独立 .venv、.task-runtime/tmp、materials、logs和uv-cache。使用 .venv/bin/python；修源码后必须重装本副本并逐文件比对安装与src，不能只比文件名。重装用当前环境的 uv pip install --python .venv/bin/python --no-build-isolation --no-deps --reinstall . ，UV_CACHE_DIR 已设为本工作树私有目录；hatchling已装。禁止 uv sync（会改其他环境假设）或安装新依赖、访问真实网络服务。

测试权限：可运行类型/格式检查及必要的轻量定向红绿验证，经 tools/check.py quick 选择明确文件/node。当前不授予任何重型测试、完整生命周期材料构建、校准、回放或全套权限（包括 tools/check.py HEAVY_FILES 与调用 prepare_isolated_candidate_inputs 的测试）。若唯一能验证本票的合法公开边界需要重型执行：先写最小反例，把准确命令、成本预期和需要的材料写入 .task-runtime/heavy-request.md，停止依赖其结果的生产修改，交回主代理排队执行；不要绕重型名单/内部mock/伪造认证以求快速绿。现有可复用的 prepared_request/admit_complete_candidate 与完整长历史材料构建要区分，按实际成本判定，疑问报告。

定期写简短 .task-runtime/progress.md；最终必须写 .task-runtime/implementation-report.md，包含：改动文件，红/绿各实际命令、退出码、结果及日志，实际安装包与材料身份，尚需重型检查和未满足的票面条件。仅读码推断要标注。报告中文精炼，不能把部分实现说成整票完成。请直接开始本票，返回真实成果；不要重复产品访谈或等待已授予的普通实施许可。


以上原提示中仅限工作树写入和 TMPDIR 位于工作树的部分由本次树外专属目录授权覆盖。报告用 .task-runtime/implementation-report-r2.md，原报告/日志保留；日志加 r2 前缀。重构在 code-review 阶段，实施使用逐例红—绿。
本轮最终报告明确用r3，原提示里的r2报告路径不覆盖。