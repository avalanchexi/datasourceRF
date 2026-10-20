你是独立只读code-review子任务，不再委派，不改文件/代码/票状态，不跑测试/联网/读取凭据。报告中文，400 words以内，文件行号+明确规则/规格依据，未实测明确标注。先核哈希与固定点。

固定基线 bb737200024369f2938d26d1cc49f5f77f18a1b1；工作树 /home/tywin/worktrees/datasourceRF-window-20260922/ticket-01。审查WIP：git -C /home/tywin/worktrees/datasourceRF-window-20260922/ticket-01 diff bb737200024369f2938d26d1cc49f5f77f18a1b1 -- src/pring_cycle/material_preflight.py src/pring_cycle/cli.py src/pring_cycle/source_adapters.py；两个新文件分别用git diff --no-index /dev/null <path>（差异返回1正常）。尚无新commit，git log <base>..HEAD为空，所以不要用空HEAD三点diff冒充修改。主代理固定输入：/mnt/d/cursor/datasourceRF/.scratch/pring-window-publication-20260922/execution/review-01-r3-input.json和review-01-r3.diff。只审这7个归属文件，复制的既有文档不是本票修改。

完整规格 /mnt/d/cursor/datasourceRF/.scratch/pring-window-publication-20260922/spec.md；票 issues/01-fixed-window-calendar.md；本工作树 .task-runtime/implementation-report-r3.md、heavy-request.md。软件23项轻量定向通过，尚未重型/全套/真实源验收。先读AGENTS.md/CONTEXT.md及有关ADR。
仅审Spec轴，完整读取规格和票面。报告缺失/部分、超范围、实现错误，逐项引用对应条目。特别核对固定120日是否确实绑定：新参数--expected-trading-days是可选，保留旧短窗口诊断可以合理，但本轮范围须真正拒收119日，不只靠测试调用额外参数才达标。核对持久收据是否完整绑定实际检查的模型/日历原件、失败路径和重读，PUBLIC历史截止与SYSTEM当前检查是否混淆。未完成重型与真实范围边界要分清，不把23项当整票完成。独立判断，不只是附和既有报告。

这是审查修复后的r3完整WIP复审。已知前轮问题和处理见review-01-combined.md（同execution目录）。核验7文件新哈希；完整tracked diff现在还含src/pring_cycle/full_run_requirements.py、tests/models/test_material_preflight.py。重点确认默认120与精确失败原件身份已经解决，检查新增选择错误携带是否影响已有消费者，不仅重复旧问题；测试helper提取是审查阶段允许的重构。当前14项新定向通过，主代理正在重跑受影响33项重型，不能预写通过。请报告当前仍存在的真实问题。
