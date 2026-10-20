你是独立只读 code-review 子任务，只通过本次直接 codex exec 调用，不再委派。不要写文件、改源码/票状态、运行测试/联网/读取凭据。报告由主代理从CLI输出保存。中文精炼，400 words以内。找真实问题，不只是附和已知意见；未实测明确标注。

审查固定点 bb737200024369f2938d26d1cc49f5f77f18a1b1，工作树 /home/tywin/worktrees/datasourceRF-window-20260922/ticket-02。尚未提交新commit，所以本次审查WIP，不用空的HEAD三点diff冒充改动。主代理已固定差异和文件哈希：/mnt/d/cursor/datasourceRF/.scratch/pring-window-publication-20260922/execution/review-02-input.json、review-02.diff。重验哈希后阅读差异及必要上下文。可复现命令：git -C <工作树> diff bb737200024369f2938d26d1cc49f5f77f18a1b1 -- src/pring_cycle/candidate_admission.py；新增测试用 git -C <工作树> diff --no-index -- /dev/null tests/models/test_cny030_optional_migration.py（有差异exit1正常）。git log <base>..HEAD为空，本轮只审查明确两个改动文件，不纳入复制的既有文档WIP。

已交付公开候选准入与轻量PUBLIC/SYSTEM选值/投影；完整Worker/报告仍未验证。父规格：/mnt/d/cursor/datasourceRF/.scratch/pring-window-publication-20260922/spec.md，票issues/02-cny030-optional-migration.md；交接工作树 .task-runtime/implementation-report.md、heavy-request.md。主代理独立核验安装103文件与源码内容一致及88项选择测试终态；这些不等于整票通过。
本次只审 Standards 轴。先读 AGENTS.md、CONTEXT.md、docs/agents/testing.md、domain.md及有关ADR；代码相关标准若无专门文档，说明这一点。只对文档明确要求判定硬违反，命名/重复等仅作启发式判断；忽略工具已检查的格式/类型。逐项给文件行号、具体规则位置和可复核影响。

必须采用的smell baseline（repo标准优先，所有smell均判断而非硬违反）：
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

