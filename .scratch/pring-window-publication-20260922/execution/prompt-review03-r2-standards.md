独立只读code-review，不再委派，不修改任何文件/票/源码，不跑测试/联网/读凭据。中文400words内，具体规则/规格及代码位置，静态推断注明。先读code-review/SKILL.md、AGENTS/CONTEXT、相关ADR0006/0018/0019、docs/agents/testing.md。
主目录/mnt/d/cursor/datasourceRF/.scratch/pring-window-publication-20260922/execution，工作树/home/tywin/worktrees/datasourceRF-window-20260922/ticket-03。固定Git基线bb737200024369f2938d26d1cc49f5f77f18a1b1，无新增提交；本票继承01七文件，冻结5归属文件WIP在review-03-r2-input.json，diff_commands有序git diff --no-index拼接必须等于review-03-r2.diff，退出1只是有差异。baseline副本按该票真实继承01冻结，不可拿已叠加05的根文件作比较。首尾重验hash与diff。
读完整父spec、issues/03-core-formula-warmup.md、前置01实际交付；本树.task-runtime/implementation-report-r2.md、heavy-request-r2.md、r2-final-identity.json；根review-03-combined.md、parent-verify-03-r2.json、heavy-03-preflight-r2/terminal.json及pytest.log。主代理已独立核104安装文件同源、最终7/33/15三个批次同版本同材料身份；实际heavy34passed85.80秒exit0前后身份相同，旧heavy5fail保留。这不代表全套/实际回放/真实认证完成。
本轮新增calendar_coverage：以实际未过滤trade_cal原件及绑定自然日范围证明预热日历完整，不能只数开市行；保留history_dates为01旧新窗口对账，不能漏行凑140或抹掉原件。03核心仍逐正式结果PUBLIC cutoff取140输入、默认259/139；认证、质量、逐版本原件绑定；诊断候选可以不可见但要区别正式consumer.inputs/versions血缘。未知/未来新修订不破坏合法旧版本，后来在真实cutoff可见时可以采用。初始化及持续性规则保持独立。
保留义务存在已披露缺口：旧r1临时CAS被pytest轮换清理，按hash找回318个，仍54路径缺失；本次r2用唯一basetemp且保存当前生成材料。不要伪称旧原件完全恢复，也不要据旧临时材料缺失否定当前同版本真实新验证。

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
