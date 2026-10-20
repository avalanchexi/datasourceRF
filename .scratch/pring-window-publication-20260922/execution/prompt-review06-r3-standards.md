独立只读code-review，不再委派、不修改文件/票/源码、不测试/联网/读凭据。中文400words内（必要可到600），给具体规则/规格+代码位置，推断注明。先读code-review/SKILL.md、AGENTS/CONTEXT、相关ADR0013/0018/0019、测试规范。主目录/mnt/d/cursor/datasourceRF/.scratch/pring-window-publication-20260922/execution，工作树/home/tywin/worktrees/datasourceRF-window-20260922/ticket-06。固定基线bb737200024369f2938d26d1cc49f5f77f18a1b1，无新增commit，审本次11归属文件WIP；继承文档WIP不属于票代码差异。
核review-06-r3-input.json所有文件hash及review-06-r3.diff：git diff <base> -- <tracked数组顺序>，再按new数组顺序拼git diff --no-index -- /dev/null <newfile>（退出1表示有差异）；不得用空HEAD差异。末尾复核输入未变。
读完整父spec、issues/06-margin-two-exchange-delivery.md，本树.task-runtime/implementation-report-r3.md、heavy-request-r3.md、r3-margin-publication-api.md，以及主目录review06-r3-focus.md与前轮review-06-combined.md。主代理重验104包文件相同、58 passed/29.76秒及软件安装材料前后相同；无重型/完整Worker/回放通过，不能补写完成。

仅Standards：仓库规范优先、工具已管不重复，启发式不当硬违反。关注新模块边界、重复/策略集中收益，不重排Spec。基线全文：
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
