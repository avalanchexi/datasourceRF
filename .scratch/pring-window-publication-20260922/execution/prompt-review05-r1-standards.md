独立只读 code-review，不再委派、不修改文件/票/源码、不测试/联网/读凭据。中文400words以内，给具体规范/规格+代码位置，推断注明。先读 /home/tywin/.codex/skills/code-review/SKILL.md、根AGENTS/CONTEXT、相关ADR0006/0018/0019/0020及docs/agents/testing.md。
主目录 /mnt/d/cursor/datasourceRF/.scratch/pring-window-publication-20260922/execution，工作树 /home/tywin/worktrees/datasourceRF-window-20260922/ticket-05。Git固定基线bb737200024369f2938d26d1cc49f5f77f18a1b1，无新增commit；本票继承01与02已审软件，勿冒认为本票改动。review-05-r1-input.json载明3文件hash和有序diff_commands：逐条git diff --no-index拼接应等于review-05-r1.diff，退出1表示差异；已有文件的继承版本已冻结在review-05-r1-baseline，不能用空HEADdiff或将继承WIP算入。首尾核验输入不变。
读完整父spec、issues/05-catalog-material-preflight.md、本树.task-runtime/implementation-report.md、family-coverage.md、heavy-request.md和owned.patch。主代理已独立核验103包文件同源、final-quick-bound前后软件/安装/材料同身份，实际31passed/27.09s，未运行重型与全目录合法材料正例，不能把pending写成完成。
本轮公开预检catalog_checks与ModelInputSelection.material_checks增加可见执行诊断；核实际完整目录优先级、可选/运维保留、合同不可用、原件/normalized和缺维度守卫、未来坏修订隔离、跨调用损坏与持久旧收据。新selection.complete仅说明已到达选择，不等于指标材料齐全。03核心/04公式/06融资各自归属，整体checks_complete不可提前成功。不要以无实际新融资材料否定合法synthetic局部正例，但完整家族验收缺件须保留。

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
