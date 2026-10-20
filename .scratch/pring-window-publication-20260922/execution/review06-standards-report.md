**Standards：未发现可确认的文档硬违规；有两项低优先级 smell 建议，均为静态判断。**

核验通过：八个文件 SHA-256 均与清单一致；按指定命令重建的差异与 review-06.diff 逐字节一致，哈希为 `0af375fd11da2a0861cabb3fc3471cdd50ca583e96ad92cc0d90325200a46d3d`。HEAD 等于指定基线，无新提交。

1. **可能的 Repeated Switches**： [source_contract_review.py:533](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-06/src/pring_cycle/source_contract_review.py:533) 在同一融资合同分支中，反复依据 `family == "margin_sse_szse"` 决定发布时间限制、scope、来源字段、解析器及规范化检查（534、539–540、569–575 行）。依据：本次 Fowler 基线的“相同类型判断反复出现”。建议集中两种合同的配置或校验策略，减少新增规则时漏改某处分支的风险；保留历史合同语义。

2. **可能的 Duplicated Code**： [适配器测试:174](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-06/tests/adapters/test_margin_two_exchange.py:174) 与 [Worker 测试:34](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-06/tests/integration/test_worker_margin_two_exchange.py:34) 重复“迁移请求→设置点时规则→读取审核包→重新绑定→公开提交→读取模型”的准备流程。依据：Fowler 基线的“变更中重复相同逻辑形状”。建议提取共享的合成候选夹具，避免两组测试准备条件漂移。

已读 AGENTS、CONTEXT、相关 ADR、完整父规格、本票及两份交付报告。103 文件安装一致性和36项通过属于已有核验记录，本次未重验；依据项目测试规则，它们不能替代尚未完成的完整 Worker、PUBLIC 正向及回放验收。

本次仅审指定八文件，未委派、修改、运行测试、联网或读取凭据；未报告工具已覆盖的格式、类型问题。