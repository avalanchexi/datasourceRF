独立只读code-review，不委派、不改文件/票、不跑测试/网络/读凭据。中文400words以内，给代码位置和具体规则/规格依据，推断注明。先读 /home/tywin/.codex/skills/code-review/SKILL.md及AGENTS/CONTEXT/相关ADR0006/0018/0019、docs/agents/testing.md。
固定Git基线bb737200024369f2938d26d1cc49f5f77f18a1b1，两树无新commit；03继承01已审软件，不能把继承变化混入本票。主目录/mnt/d/cursor/datasourceRF/.scratch/pring-window-publication-20260922/execution，核review-03-input.json与review-03.diff哈希；仅3归属文件。准确差异：git diff --no-index -- /dev/null /home/tywin/worktrees/datasourceRF-window-20260922/ticket-03/src/pring_cycle/core_input_requirements.py；git diff --no-index -- /home/tywin/worktrees/datasourceRF-window-20260922/ticket-01/src/pring_cycle/material_preflight.py /home/tywin/worktrees/datasourceRF-window-20260922/ticket-03/src/pring_cycle/material_preflight.py；git diff --no-index -- /dev/null /home/tywin/worktrees/datasourceRF-window-20260922/ticket-03/tests/models/test_core_formula_warmup.py。顺序拼接必须匹配固定diff，退出1仅表示有差异。
读完整父spec和issues/03-core-formula-warmup.md、01前置交付；本树.task-runtime/implementation-report.md与heavy-request.md。主代理将独立核安装104文件、36+15各自同版本日志；重型正在排队，不能预记通过。检查核心按真正正式消费者cutoff选择140输入×120结果、259/139、认证包有效期、质量/实际原件、每版血缘、状态初始化分离/不改公式。未知/未来修订不污染当时合法版本，坏最新实际采用原件不能静默退旧。

只审Standards，repo规则优先，启发式不当硬违规，工具已覆盖问题不重复。Fowler基线全文：
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
