# 票01 r3 两轴审查

## Standards

Standards 复审：**未发现仍需报告的硬违反或明确启发式问题。**

固定点已核：HEAD＝`bb737200024369f2938d26d1cc49f5f77f18a1b1`，提交区间为空。七文件哈希全部匹配输入清单；五个 tracked 文件加两个新文件组成的 WIP diff 与固定文件逐字节一致，SHA256 为 `074c2b85e04d3605f6ac187ae72d9f968ac2254d1040f71e8e6eb58ce616d4f5`。

- 默认120已落实于 [material_preflight.py:49](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-01/src/pring_cycle/material_preflight.py:49)，且第172行仅统计请求范围内日期；对应票01验收第1、3项，旧119日反例已被代码覆盖。
- [full_run_requirements.py:68](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-01/src/pring_cycle/full_run_requirements.py:68) 在规范化原件读取失败时携带具体 acquisition/hash；[material_preflight.py:578](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-01/src/pring_cycle/material_preflight.py:578) 保留 raw 失败身份，符合票01验收第5项的材料绑定要求。
- 新异常仍继承 `ValueError`，现有 Worker 捕获分支仍会进入 `action_required`。其持久错误分类中的类型名会变为 `CalendarMaterialError`；静态追踪未发现现有消费者依赖日历错误的旧类型字符串，因此不列为违反。
- 前轮 Fowler **Duplicated Code** 启发式问题已通过 [test_fixed_window_preflight.py:73](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-01/tests/models/test_fixed_window_preflight.py:73) 的读取 helper 消除。

**以上仅静态审查，未实测。** 14项通过来自实施报告；当前33项重型正在重跑，不预判通过，全套及真实源验收亦未获证明。未修改文件、票状态，未运行测试、联网、读取凭据或委派。

## Spec

**Spec 轴：未发现 r3 仍需修复的明确问题；不等于整票验收完成。仅静态审查，未实测。**

固定点核验：HEAD＝`bb737200024369f2938d26d1cc49f5f77f18a1b1`，提交差集为空。7 文件哈希全部匹配，结束时复核未变；指定 WIP diff 与两个新文件差异拼接后，与固定审查包逐字节一致，SHA-256：
`074c2b85e04d3605f6ac187ae72d9f968ac2254d1040f71e8e6eb58ce616d4f5`。

- **默认120日已修复。** CLI/API 均默认120，且[窗口计数](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-01/src/pring_cycle/material_preflight.py:171)仅统计请求范围；补入窗口外日期不能使119日通过。符合[票01验收第1、3项](/mnt/d/cursor/datasourceRF/.scratch/pring-window-publication-20260922/issues/01-fixed-window-calendar.md:26)。
- **原件身份与重读已修复。** [选择错误](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-01/src/pring_cycle/full_run_requirements.py:68)携带具体 acquisition/raw/normalized 身份；[raw失败路径](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-01/src/pring_cycle/material_preflight.py:578)也保留身份。[持久收据及读取](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-01/src/pring_cycle/material_preflight.py:63)绑定模型清单、请求与结果，并验证收据哈希。符合票01验收第5项、规格US25。
- **消费者及截止语义未发现回归。** 新异常仍属 `ValueError`，现有捕获有效；Worker错误分类中的类名会变化，但未发现依赖旧文字的生产分支。[日历SYSTEM时刻](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-01/src/pring_cycle/material_preflight.py:141)与[逐日PUBLIC截止](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-01/src/pring_cycle/material_preflight.py:292)分离，符合票01验收第4项及ADR-0006。

未发现明确超范围修改。14项通过仅引用实施报告；旧23项及旧版本33项不能代替当前验收。正在重跑的33项不预记通过；同版本全套、真实日历认证、真实回放及历史发布保护仍须各自证据。未修改文件或票状态，未跑测试、联网、读取凭据或委派。

Standards 0项；Spec 0项。其后重型时钟失败与一行测试时钟替身另审；不冒用r3审查覆盖新差异。
