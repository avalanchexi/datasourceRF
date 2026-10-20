独立只读code-review；不再委派、不修改文件、不跑测试/构建/校准/回放、不联网/读取凭据。中文400words以内，先结论，具体file:line及规则；静态推断标注，不把单纯文件长当缺陷。读/home/tywin/.codex/skills/code-review/SKILL.md。
主仓库/mnt/d/cursor/datasourceRF，execution目录.scratch/pring-window-publication-20260922/execution，工作树/home/tywin/worktrees/datasourceRF-window-20260922/ticket-06。Git基线bb737200024369f2938d26d1cc49f5f77f18a1b1，零新增commit。精确WIP为review-06-fixtures-r5-input.json的7文件，baseline是已审06r3+01/02overlay后的r4-before哈希，不是当前根树。diff_commands按序输出必须等于review-06-fixtures-r5.diff，首尾核哈希。margin.py原为r3新文件，baseline从已审r3完整新增patch还原并核hash，其他baselines同r4-before。
阅读AGENTS/CONTEXT/testing及ADR0018/0019/0020、父spec、票02/06/07；.task-runtime/implementation-report-r4.md、implementation-report-r5.md、heavy-request-r5.md；主目录parent-verify-06-r4.json/parent-verify-06-r5.json，已有r3独立review结论可复用但此次重点7个fixture/tools测试变更。r5实际材料合同RED原因是OMO合成六列表包含注册合同不接受maturity，改四列injection，冻结v2历史投放/日历推到期不变；不是放宽生产守卫。27文档真实公开准入/导入和单日context transport，最终32passed35.76秒，245软件/104包同源，父代理复核44artifact/最终3批日志及旧失败保留。没有src生产改动。
真正完整PUBLIC节点父队列正在heavy-06-replay-r5执行，可引用实际terminal/log，未终态则不推断成功。r4实际1failed55.78秒发生prepare阶段registered_official_source_identity_mismatch，绝非融资业务RED。独立input profile完整注册candidate不需active；Worker profile必须走真实合法准入/校准/120日比较/激活及旧历史发布，已知与旧v1比较可能要求已移除legacy margin及待认证CNY的门，仍未证明可构建合法active。只静态观察这一未验证边界，不用伪active降低测试范围。
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
