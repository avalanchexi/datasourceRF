独立只读code-review，不再委派，不改代码/文件/票状态、不跑测试或联网、不读凭据。中文400 words以内，给明确规则或规格依据与代码位置，静态推断标明。固定基线bb737200024369f2938d26d1cc49f5f77f18a1b1，工作树/home/tywin/worktrees/datasourceRF-window-20260922/ticket-06，无新commit；本次审WIP和两个新测试文件，不用空HEAD diff。先核 /mnt/d/cursor/datasourceRF/.scratch/pring-window-publication-20260922/execution/review-06-input.json和review-06.diff 的文件/差异哈希。重建差异命令：git -C /home/tywin/worktrees/datasourceRF-window-20260922/ticket-06 diff bb737200024369f2938d26d1cc49f5f77f18a1b1 -- src/pring_cycle/tushare_context.py src/pring_cycle/source_contract_review.py src/pring_cycle/search_evidence.py src/pring_cycle/worker.py src/pring_cycle/targeted_context.py tests/models/test_margin_scope_migration.py，以及两个新文件的git diff --no-index /dev/null <path>。只审这8个归属文件；复制的文档WIP不是本票变化。

先读AGENTS/CONTEXT/相关ADR与完整父spec：/mnt/d/cursor/datasourceRF/.scratch/pring-window-publication-20260922/spec.md；本票 issues/06-margin-two-exchange-delivery.md。交付报告为本树.task-runtime/implementation-report-r2.md和heavy-request.md。主代理核验当前安装103文件逐内容相同与36项选择测试终态；完整Worker、PUBLIC正向和回放未完成，不用该数目替代。
仅审Standards。文档硬要求与启发式smell分开；跳过工具已覆盖的格式/类型。
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

