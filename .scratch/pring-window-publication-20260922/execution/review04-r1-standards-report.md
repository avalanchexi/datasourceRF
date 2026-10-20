Standards：未发现明确硬违规；两项启发式建议，均为静态推断：

1. **可能 Duplicated Code**：[material_preflight_context.py:178](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-04/src/pring_cycle/material_preflight_context.py:178) 重写了 [context_projection.py:1138](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-04/src/pring_cycle/context_projection.py:1138) 的“七自然日后顺延交易日”规则，后续容易使诊断与实际计算分歧。建议共享这一纯函数。规则来源：[SKILL.md:46](/home/tywin/.codex/skills/code-review/SKILL.md:46)。

2. **可能 Feature Envy**：[material_preflight_context.py:407](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-04/src/pring_cycle/material_preflight_context.py:407) 直接连接数据库并关联证据内部表，使诊断模块依赖存储结构。建议由证据仓库提供包含损坏原件身份的查询接口。规则来源：[SKILL.md:47](/home/tywin/.codex/skills/code-review/SKILL.md:47)；架构依据：[ADR0004:7](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-04/docs/adr/0004-deep-modules-over-stage-file-pipeline.md:7)。此处不判硬违规。

首尾核验均通过：固定基线后无新提交，5 文件哈希及有序 diff 与冻结输入完全一致，未使用叠加 05 的根树作为基线。

验证记录：原 heavy 为 1 failed/5 passed；r2 未启动 pytest；r3 实际 [2 passed，5.61s](/mnt/d/cursor/datasourceRF/.scratch/pring-window-publication-20260922/execution/heavy-04-policy-parent-r3/pytest.log:8)，[退出码 0](/mnt/d/cursor/datasourceRF/.scratch/pring-window-publication-20260922/execution/heavy-04-policy-parent-r3/terminal.json:2)，绑定本次版本且前后身份一致。仅该修订专项已 GREEN；全套、真实认证仍未完成。

本次未委派、修改文件、运行测试、联网或读取凭据。