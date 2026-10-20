你是本Goal中票02的独立实施子代理。只在工作树 /home/tywin/worktrees/datasourceRF-window-20260922/ticket-02 工作。当前工作树基线 bb737200024369f2938d26d1cc49f5f77f18a1b1，主代理复制了当前必要未提交文档、ADR和材料。不要再创建worktree、切分支、提交、merge或改票状态，主代理负责集成、两轴code-review、验收与提交。

用户已显式采用 .scratch/pring-window-publication-20260922/goal-prompt.md 的并行实施授权，覆盖旧委派文档的只读限制。你允许写自己的源码和测试；禁止写 /mnt/d/cursor/datasourceRF 原工作区、其他工作树、全局venv、生产runtime或正式模型指针。不要外派更多代理。

先读 AGENTS.md/CONTEXT.md、docs/agents/testing.md、相关ADR（尤其0014/0016/0019/0020）、完整 .scratch/pring-window-publication-20260922/spec.md 和 .scratch/pring-window-publication-20260922/issues/02-cny030-optional-migration.md；按需读取其中历史交付。读取 /home/tywin/.codex/skills/implement/SKILL.md、tdd/SKILL.md及tests.md/mocking.md，严格公开接缝TDD，一个失败行为→最小修复→相关验证，不实现其他票。

任务边界：拥有 CNY030 priority 专项迁移和相应准入/消费者测试。可改 candidate_admission、必要目录/选择代码。另一个06在实现融资适配/交付合同，请不要实施那项；可用其既有合法身份迁移夹具验证组合。先检查现有 metric_identity_migration 只允许单声明的限制，迁移须保留已经批准的黄金删除、外汇、沪深身份，不能通过弱化通用守卫实现。不要宽泛重构迁移框架。

隔离已由主代理验证：独立 .venv、.task-runtime/tmp、materials、logs和uv-cache。使用 .venv/bin/python；修源码后必须重装本副本并逐文件比对安装与src，不能只比文件名。重装用当前环境的 uv pip install --python .venv/bin/python --no-build-isolation --no-deps --reinstall . ，UV_CACHE_DIR 已设为本工作树私有目录；hatchling已装。禁止 uv sync（会改其他环境假设）或安装新依赖、访问真实网络服务。

测试权限：可运行类型/格式检查及必要的轻量定向红绿验证，经 tools/check.py quick 选择明确文件/node。当前不授予任何重型测试、完整生命周期材料构建、校准、回放或全套权限（包括 tools/check.py HEAVY_FILES 与调用 prepare_isolated_candidate_inputs 的测试）。若唯一能验证本票的合法公开边界需要重型执行：先写最小反例，把准确命令、成本预期和需要的材料写入 .task-runtime/heavy-request.md，停止依赖其结果的生产修改，交回主代理排队执行；不要绕重型名单/内部mock/伪造认证以求快速绿。现有可复用的 prepared_request/admit_complete_candidate 与完整长历史材料构建要区分，按实际成本判定，疑问报告。

定期写简短 .task-runtime/progress.md；最终必须写 .task-runtime/implementation-report.md，包含：改动文件，红/绿各实际命令、退出码、结果及日志，实际安装包与材料身份，尚需重型检查和未满足的票面条件。仅读码推断要标注。报告中文精炼，不能把部分实现说成整票完成。请直接开始本票，返回真实成果；不要重复产品访谈或等待已授予的普通实施许可。
