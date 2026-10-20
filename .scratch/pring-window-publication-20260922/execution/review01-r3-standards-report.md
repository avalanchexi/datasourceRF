Standards 复审：**未发现仍需报告的硬违反或明确启发式问题。**

固定点已核：HEAD＝`bb737200024369f2938d26d1cc49f5f77f18a1b1`，提交区间为空。七文件哈希全部匹配输入清单；五个 tracked 文件加两个新文件组成的 WIP diff 与固定文件逐字节一致，SHA256 为 `074c2b85e04d3605f6ac187ae72d9f968ac2254d1040f71e8e6eb58ce616d4f5`。

- 默认120已落实于 [material_preflight.py:49](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-01/src/pring_cycle/material_preflight.py:49)，且第172行仅统计请求范围内日期；对应票01验收第1、3项，旧119日反例已被代码覆盖。
- [full_run_requirements.py:68](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-01/src/pring_cycle/full_run_requirements.py:68) 在规范化原件读取失败时携带具体 acquisition/hash；[material_preflight.py:578](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-01/src/pring_cycle/material_preflight.py:578) 保留 raw 失败身份，符合票01验收第5项的材料绑定要求。
- 新异常仍继承 `ValueError`，现有 Worker 捕获分支仍会进入 `action_required`。其持久错误分类中的类型名会变为 `CalendarMaterialError`；静态追踪未发现现有消费者依赖日历错误的旧类型字符串，因此不列为违反。
- 前轮 Fowler **Duplicated Code** 启发式问题已通过 [test_fixed_window_preflight.py:73](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-01/tests/models/test_fixed_window_preflight.py:73) 的读取 helper 消除。

**以上仅静态审查，未实测。** 14项通过来自实施报告；当前33项重型正在重跑，不预判通过，全套及真实源验收亦未获证明。未修改文件、票状态，未运行测试、联网、读取凭据或委派。