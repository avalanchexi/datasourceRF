Spec：发现两项问题，均为静态推断，未运行测试。

1. **P1：OMO 必需预热可能被漏检。** [material_preflight_context.py:166](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-04/src/pring_cycle/material_preflight_context.py:166) 仅从 PUBLIC 可见投放生成到期父项。若 08-21 的950亿元投放只有未知/未来发布时间，而08-28投放及日历有效，该父项直接消失；投影与预检同步遗漏，可能将200亿元错误标为公式通过。规则：[spec.md:107](/mnt/d/cursor/datasourceRF/.scratch/pring-window-publication-20260922/spec.md:107) 要求必要预热未知或晚于 cutoff 时拒收；ADR0019同样要求。

2. **P2：缺有效政策事件时可能给出错误父项诊断。** [material_preflight_context.py:339](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-04/src/pring_cycle/material_preflight_context.py:339) 将空期次替换为目标日前最新记录。若DR007最新为08-28、仅有08-31政策事件且 cutoff 为08-31，会把后者标成有效父项，虽然公式整体仍失败。应保留“DR007日期之前缺有效事件”。规则：[04票:28](/mnt/d/cursor/datasourceRF/.scratch/pring-window-publication-20260922/issues/04-context-formula-parents.md:28) 要求准确定位缺失父项。新增测试未覆盖上述两分支。

父代理[测试修订:167](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-04/tests/models/test_material_preflight.py:167)符合实际公式：保留两起点、缺政策失败、真实导入后0bp及两父项；10自然日不要求边缘值，符合规格实施决定5。

首尾核验均通过：固定HEAD、五文件哈希、有序diff完全匹配。r3日志实际为[2 passed](/mnt/d/cursor/datasourceRF/.scratch/pring-window-publication-20260922/execution/heavy-04-policy-parent-r3/pytest.log:8)；完整预检文件另为33 passed，身份一致。全套、真实认证及后续票仍未完成；合法synthetic软件验证不因真实源缺件而无效。