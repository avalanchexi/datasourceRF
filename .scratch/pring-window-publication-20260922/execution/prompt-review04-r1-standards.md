独立只读code-review，不再委派、不修改文件、不运行测试、不联网、不读凭据。中文400words以内，给file:line和规则来源，静态推断注明。读取/home/tywin/.codex/skills/code-review/SKILL.md。主仓库/mnt/d/cursor/datasourceRF，execution目录.scratch/pring-window-publication-20260922/execution；工作树/home/tywin/worktrees/datasourceRF-window-20260922/ticket-04。
固定Git基线bb737200024369f2938d26d1cc49f5f77f18a1b1，无新提交，实际继承01+02。非空WIP的5文件哈希、精确diff_commands与baseline副本见review-04-r1-input.json；有序输出必须匹配review-04-r1.diff，首尾重验。不要用已叠加05的根树为基线。
读取AGENTS及相关docs/agents、CONTEXT、ADR0006/0018/0019，完整父spec及issues/04-context-formula-parents.md，本树根目录implementation-report.md/heavy-request.md，execution/parent-verify-04-r1.json、heavy-04-parents-r1/pytest.log及terminal.json、diagnosis-04-lookback-edge.md。
04原4文件补8个冻结上下文公式的父期次/维度/比较基线及血缘诊断。父代理另改旧边缘日期测试：原heavy1failed5passed，10自然日lookback不代表必须有边缘值，改成先缺政策父项失败再真实导入政策成功，保留DR007两个起点。此修订待GREEN：heavy-04-policy-parent-r2在C盘PowerShell监测失败，pytest未启动；独立审查可先行但交付须等待验证。重试运行heavy-04-policy-parent-r3若终态可引用实际结果，不得推测成功。全套/真实认证未完成。
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
