# 04 r1 独立双轴审查

## Standards

Standards：未发现明确硬违规；两项启发式建议，均为静态推断：

1. **可能 Duplicated Code**：[material_preflight_context.py:178](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-04/src/pring_cycle/material_preflight_context.py:178) 重写了 [context_projection.py:1138](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-04/src/pring_cycle/context_projection.py:1138) 的“七自然日后顺延交易日”规则，后续容易使诊断与实际计算分歧。建议共享这一纯函数。规则来源：[SKILL.md:46](/home/tywin/.codex/skills/code-review/SKILL.md:46)。

2. **可能 Feature Envy**：[material_preflight_context.py:407](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-04/src/pring_cycle/material_preflight_context.py:407) 直接连接数据库并关联证据内部表，使诊断模块依赖存储结构。建议由证据仓库提供包含损坏原件身份的查询接口。规则来源：[SKILL.md:47](/home/tywin/.codex/skills/code-review/SKILL.md:47)；架构依据：[ADR0004:7](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-04/docs/adr/0004-deep-modules-over-stage-file-pipeline.md:7)。此处不判硬违规。

首尾核验均通过：固定基线后无新提交，5 文件哈希及有序 diff 与冻结输入完全一致，未使用叠加 05 的根树作为基线。

验证记录：原 heavy 为 1 failed/5 passed；r2 未启动 pytest；r3 实际 [2 passed，5.61s](/mnt/d/cursor/datasourceRF/.scratch/pring-window-publication-20260922/execution/heavy-04-policy-parent-r3/pytest.log:8)，[退出码 0](/mnt/d/cursor/datasourceRF/.scratch/pring-window-publication-20260922/execution/heavy-04-policy-parent-r3/terminal.json:2)，绑定本次版本且前后身份一致。仅该修订专项已 GREEN；全套、真实认证仍未完成。

本次未委派、修改文件、运行测试、联网或读取凭据。

## Spec

Spec：发现两项问题，均为静态推断，未运行测试。

1. **P1：OMO 必需预热可能被漏检。** [material_preflight_context.py:166](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-04/src/pring_cycle/material_preflight_context.py:166) 仅从 PUBLIC 可见投放生成到期父项。若 08-21 的950亿元投放只有未知/未来发布时间，而08-28投放及日历有效，该父项直接消失；投影与预检同步遗漏，可能将200亿元错误标为公式通过。规则：[spec.md:107](/mnt/d/cursor/datasourceRF/.scratch/pring-window-publication-20260922/spec.md:107) 要求必要预热未知或晚于 cutoff 时拒收；ADR0019同样要求。

2. **P2：缺有效政策事件时可能给出错误父项诊断。** [material_preflight_context.py:339](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-04/src/pring_cycle/material_preflight_context.py:339) 将空期次替换为目标日前最新记录。若DR007最新为08-28、仅有08-31政策事件且 cutoff 为08-31，会把后者标成有效父项，虽然公式整体仍失败。应保留“DR007日期之前缺有效事件”。规则：[04票:28](/mnt/d/cursor/datasourceRF/.scratch/pring-window-publication-20260922/issues/04-context-formula-parents.md:28) 要求准确定位缺失父项。新增测试未覆盖上述两分支。

父代理[测试修订:167](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-04/tests/models/test_material_preflight.py:167)符合实际公式：保留两起点、缺政策失败、真实导入后0bp及两父项；10自然日不要求边缘值，符合规格实施决定5。

首尾核验均通过：固定HEAD、五文件哈希、有序diff完全匹配。r3日志实际为[2 passed](/mnt/d/cursor/datasourceRF/.scratch/pring-window-publication-20260922/execution/heavy-04-policy-parent-r3/pytest.log:8)；完整预检文件另为33 passed，身份一致。全套、真实认证及后续票仍未完成；合法synthetic软件验证不因真实源缺件而无效。

两轴结论：Standards硬违规0、启发式2；Spec缺陷2（P1 OMO未知/未来预热漏检，P2政策父期次诊断），均需实际公开反例核实。

## 主代理核验与处置

查实OMO projection和diagnostics均仅从PUBLIC可见series构建maturity候选，未知发布时间的到期父项可能消失；_parent在无合格rate_period时退到目标日而非DR007日，确有误报有效父项路径。派发r2先RED后修，不按通过33项关闭票。必要源码归属允许context_projection/material_preflight_context及适用公开evidence查询，但不改变公式或制造可见时间。测试修订2passed5.61秒，完整受影响文件33passed84.24秒，父包装84.94秒，三类身份一致；这些结果不覆盖新发现分支。04尚未集成。
