# 票06 两轴审查

## Standards

**Standards：未发现可确认的文档硬违规；有两项低优先级 smell 建议，均为静态判断。**

核验通过：八个文件 SHA-256 均与清单一致；按指定命令重建的差异与 review-06.diff 逐字节一致，哈希为 `0af375fd11da2a0861cabb3fc3471cdd50ca583e96ad92cc0d90325200a46d3d`。HEAD 等于指定基线，无新提交。

1. **可能的 Repeated Switches**： [source_contract_review.py:533](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-06/src/pring_cycle/source_contract_review.py:533) 在同一融资合同分支中，反复依据 `family == "margin_sse_szse"` 决定发布时间限制、scope、来源字段、解析器及规范化检查（534、539–540、569–575 行）。依据：本次 Fowler 基线的“相同类型判断反复出现”。建议集中两种合同的配置或校验策略，减少新增规则时漏改某处分支的风险；保留历史合同语义。

2. **可能的 Duplicated Code**： [适配器测试:174](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-06/tests/adapters/test_margin_two_exchange.py:174) 与 [Worker 测试:34](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-06/tests/integration/test_worker_margin_two_exchange.py:34) 重复“迁移请求→设置点时规则→读取审核包→重新绑定→公开提交→读取模型”的准备流程。依据：Fowler 基线的“变更中重复相同逻辑形状”。建议提取共享的合成候选夹具，避免两组测试准备条件漂移。

已读 AGENTS、CONTEXT、相关 ADR、完整父规格、本票及两份交付报告。103 文件安装一致性和36项通过属于已有核验记录，本次未重验；依据项目测试规则，它们不能替代尚未完成的完整 Worker、PUBLIC 正向及回放验收。

本次仅审指定八文件，未委派、修改、运行测试、联网或读取凭据；未报告工具已覆盖的格式、类型问题。

## Spec

**Spec 结论：仍有 3 项交付缺口，不能关闭本票。**这些缺口已在 r2 报告中披露。

核验通过：HEAD 等于固定基线；8 文件哈希全部匹配；重建差异逐字节一致，SHA256 为 `0af375fd11da2a0861cabb3fc3471cdd50ca583e96ad92cc0d90325200a46d3d`。当前安装的 103 文件与源码相同；既有日志确认 36 passed、exit 0，不代表完整验收。本次未修改、委派、跑测试、联网或读取凭据。

1. **P1｜PUBLIC 正向合同缺失（静态推断）。**依据票06验收1/4/5、父spec测试9及ADR-0018：[合同:534](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-06/src/pring_cycle/source_contract_review.py:534)拒绝全部非空发布时间。尚需交付公开获取/导入入口，将两所各自的逐版本发布原件、数值、日期、收据与规范化声明绑定，再推导聚合可见时间；用合法隔离材料验证PUBLIC正向及修订拒收。不能靠手填时间或改认证标签补齐。

2. **P1｜选值与回放完整性检查未对齐（静态推断）。**依据父spec测试9/10：[选值:250](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-06/src/pring_cycle/search_evidence.py:250)已为新身份重解析原件；调用链对照发现[回放:1251](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-06/src/pring_cycle/model_evaluation.py:1251)仍仅检查旧ID。当前PUBLIC正向被阻断，不能据此声称已发生错误回放；开通前须让两条路径对损坏原件、规范化及缺成员一致拒收。

3. **P2｜完整Worker消费尚无证明。**依据票06测试边界、父spec测试1/11：[新测试:78](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-06/tests/integration/test_worker_margin_two_exchange.py:78)直接调用刷新函数。仍需合法生命周期材料经持久任务、`process_pending_run`，读回投影/报告的两个measure、范围、血缘及截止点，并核验旧历史不变。

静态检查未发现两所十进制求和、缺所/重复拒收、旧三所冒名防护的明确错误，亦未发现超范围变更。

Standards 2项启发式建议（无硬违规）；Spec 3项（PUBLIC正向、回放完整性、完整Worker）。主代理确认这些均仍待交付；继续实施，不关闭本票。
