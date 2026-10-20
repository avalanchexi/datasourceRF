**结论：新增一项 P2 覆盖缺口；既有 PUBLIC 完整性与合法 active Worker 验证仍未闭环，票06不能关闭。未发现范围扩张或生产守卫放宽。**

- **P2／部分实现（静态推断）：旧模型发布历史未覆盖。**[r4_window_lifecycle.py:522](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-06/tests/fixtures/r4_window_lifecycle.py:522)在新候选激活后，用该候选生成09-21历史；[test_r4_margin_lifecycle.py:243](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-06/tests/integration/test_r4_margin_lifecycle.py:243)此后才取历史快照。因此只能证明次日运行不改写新模型历史，不能证明迁移保留旧模型已发布结果。对应父规格实施13、测试7/10及票02验收5。

- **既有 P1 保留，尚无业务终态。**[test_r4_margin_lifecycle.py:203](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-06/tests/integration/test_r4_margin_lifecycle.py:203)正确要求先无gap、两measure实际采用，再损坏发布原件；但r5监督及子运行均无terminal。r3指出的[model_evaluation.py:1251](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-06/src/pring_cycle/model_evaluation.py:1251)仅检查旧融资身份仍未变。依父规格测试9/10，不能将准备失败算融资RED。

- **既有 P2／未验证边界。**[r4_window_lifecycle.py:505](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-06/tests/fixtures/r4_window_lifecycle.py:505)保留真实120日比较门；旧v1可能要求已移除legacy融资及待认证CNY，合法active尚未证明（静态推断）。单次Worker、报告/CNY排除断言已编写，尚未执行通过，不能满足票06测试边界、票07验收26–30行。

首尾七文件哈希及顺序diff逐字节一致；margin基线由r3新增补丁还原匹配，其余匹配r4-before，零新增commit。44件材料、245软件/104安装及最终三批日志核验一致，**32 passed／35.76秒**成立。OMO四列修复保持冻结v2父项规则；轻量通过不证明三核心、广度、期货篮子完整构建及公式消费成功。本次未委派、修改、执行测试或联网。