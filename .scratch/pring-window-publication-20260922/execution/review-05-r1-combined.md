# 05 r1 两轴审查

## Standards

Standards：未发现可确认的新增硬性违规；有一项非阻断建议。

- **可能的 Duplicated Code（启发式判断）**：[search_evidence.py:348](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-05/src/pring_cycle/search_evidence.py:348) 与同文件375行重复使用“存在所选声明→原件检查 executed，否则 blocked”的判断。依据 [Fowler 基线](/home/tywin/.codex/skills/code-review/SKILL.md)，可提取共享判断，保留两家族各自的维度诊断。未来维护时可能发生语义漂移属于推断，不是已证实缺陷。

[票05](/mnt/d/cursor/datasourceRF/.scratch/pring-window-publication-20260922/issues/05-catalog-material-preflight.md)要求仅记录实际检查、保留未完成项：[material_preflight.py:192](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-05/src/pring_cycle/material_preflight.py:192)保留实际目录优先级及必需性；366行聚合选择诊断，468行仍固定 `checks_complete=False`。`selection.complete`不能据此解释为整窗材料齐全。

首尾清单、三文件哈希及有序 diff 均一致，无新增提交；未将继承01/02计入本票。未修改、测试、联网、读凭据或委派。31 passed／27.09s仅引用既有核验；按[测试规范](/mnt/d/cursor/datasourceRF/docs/agents/testing.md)，重型验证及完整目录合法材料正例仍未完成。

## Spec

本票增量中，未发现可静态确认的软件错误或超范围实现；**仍有一项验收缺交**。

- **验证未完成：完整目录各适用家族的合法材料正例及受影响 heavy。** [票05 AC3](/mnt/d/cursor/datasourceRF/.scratch/pring-window-publication-20260922/issues/05-catalog-material-preflight.md:28)要求“核对各适用家族原件与规范化材料资格，完整正例可读回”。新增[测试](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-05/tests/models/test_catalog_preflight.py:127)证明局部家族行为；[重型请求](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-05/.task-runtime/heavy-request.md:18)仍保留完整材料验收。31 passed／27.09s 不能关闭该项。这是验证缺口，不是已证明的软件错误；06材料尚缺也不否定合法 synthetic 局部正例。

独立追踪显示：[普通家族](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-05/src/pring_cycle/search_evidence.py:320)先调用原件复核，再形成执行诊断；RRR、仓单调用各自专用检查。目录项在分支跳过前已登记，可选及运维项保留。未发现本票新增“空缺口即成功”路径：[全局状态](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-05/src/pring_cycle/material_preflight.py:458)仍为 blocked/incomplete、checks_complete=false；selection.complete 不证明整项材料齐全。

静态核对未发现新增未来坏修订污染过去或跨调用复用损坏材料的路径。测试经过公开预检／选值入口，以明确成员、时间和旧收据内容作期望，未绕守卫写坏数据库。

首尾输入清单、三文件哈希、冻结差异均一致；有序 diff 拼接匹配，HEAD 未变。未委派、修改、测试、联网或读取凭据；01/02继承实现未计为本票改动。

Standards：1项非阻断重复判断建议，无硬违规；Spec：1项完整家族验证缺交，无确认的软件错误。

## 主代理核验与处理

审查启动后主代理串行重型已实际完成：33 passed/80.80秒、exit0、三类身份一致，见heavy-05-preflight-r1；因此报告中“受影响heavy尚缺”已解除。完整当前目录各家族合法材料正例仍未完成，AC3保留。重复的局部有值判断分别紧邻RRR与仓单的不同合同诊断，当前无语义分歧；提取仅包装该短谓词会增加间接层，本轮保留，不把启发式视为硬错误。

三个归属文件已在复制前核对根树等于该票继承基线，然后集成。此根软件组合与已经验证的05树软件清单相同；后续03/04/06组合需重新验证。尚无默认全套/提交/真实来源认证结论。
