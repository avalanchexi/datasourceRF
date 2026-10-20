你是独立只读code-review子任务，不再委派，不改文件/代码/票状态，不跑测试/联网/读取凭据。报告中文，400 words以内，文件行号+明确规则/规格依据，未实测明确标注。先核哈希与固定点。

固定基线 bb737200024369f2938d26d1cc49f5f77f18a1b1；工作树 /home/tywin/worktrees/datasourceRF-window-20260922/ticket-01。审查WIP：git -C /home/tywin/worktrees/datasourceRF-window-20260922/ticket-01 diff bb737200024369f2938d26d1cc49f5f77f18a1b1 -- src/pring_cycle/material_preflight.py src/pring_cycle/cli.py src/pring_cycle/source_adapters.py；两个新文件分别用git diff --no-index /dev/null <path>（差异返回1正常）。尚无新commit，git log <base>..HEAD为空，所以不要用空HEAD三点diff冒充修改。主代理固定输入：/mnt/d/cursor/datasourceRF/.scratch/pring-window-publication-20260922/execution/review-01-input.json和review-01.diff。只审这5个归属文件，复制的既有文档不是本票修改。

完整规格 /mnt/d/cursor/datasourceRF/.scratch/pring-window-publication-20260922/spec.md；票 issues/01-fixed-window-calendar.md；本工作树 .task-runtime/implementation-report-r2.md、heavy-request.md。软件23项轻量定向通过，尚未重型/全套/真实源验收。先读AGENTS.md/CONTEXT.md及有关ADR。
仅审Standards轴。寻找项目明确标准违反、以及代码smell判断；规则优先于smell，跳过工具已经检查的格式/类型，不作泛化架构建议。每项注明硬违反或启发式判断。
On top of whatever the repo documents, the Standards axis always carries the **smell baseline** below: a fixed set of Fowler code smells (_Refactoring_, ch.3) that applies even when a repo documents nothing. Two rules bind it:

- **The repo overrides.** A documented repo standard always wins; where it endorses something the baseline would flag, suppress the smell.
- **Always a judgement call.** Each smell is a labelled heuristic ("possible Feature Envy"), never a hard violation. Like any standard here, skip anything tooling already enforces.

Each smell reads *what it is* → *how to fix*; match it against the diff:

- **Mysterious Name**: a function, variable, or type whose name doesn't reveal what it does or holds. → rename it; if no honest name comes, the design's murky.
- **Duplicated Code**: the same logic shape appears in more than one hunk or file in the change. → extract the shared shape, call it from both.
- **Feature Envy**: a method that reaches into another object's data more than its own. → move the method onto the data it envies.
- **Data Clumps**: the same few fields or params keep travelling together (a type wanting to be born). → bundle them into one type, pass that.
- **Primitive Obsession**: a primitive or string standing in for a domain concept that deserves its own type. → give the concept its own small type.
- **Repeated Switches**: the same `switch`/`if`-cascade on the same type recurs across the change. → replace with polymorphism, or one map both sites share.
- **Shotgun Surgery**: one logical change forces scattered edits across many files in the diff. → gather what changes together into one module.
- **Divergent Change**: one file or module is edited for several unrelated reasons. → split so each module changes for one reason.
- **Speculative Generality**: abstraction, parameters, or hooks added for needs the spec doesn't have. → delete it; inline back until a real need shows.
- **Message Chains**: long `a.b().c().d()` navigation the caller shouldn't depend on. → hide the walk behind one method on the first object.
- **Middle Man**: a class or function that mostly just delegates onward. → cut it, call the real target direct.
- **Refused Bequest**: a subclass or implementer that ignores or overrides most of what it inherits. → drop the inheritance, use composition.

