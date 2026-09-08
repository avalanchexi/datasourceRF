# 上下文回放明细的续作边界

2026-09-09，基于`0c33710`之后的候选字段工作树只读定位。以下是静态缺口及待验证假设，尚未运行其RED；本批候选字段测试不证明这些上下文行为。

## 要求与当前实现

票21要求逐日核验全部必要P1及派生维度，并绑定逐cutoff采用的证据版本；[规格](spec.md)验收38要求后续补入历史可见声明时检查旧制品是否失配。[ADR0012](../../docs/adr/0012-atomic-model-versions-and-parallel-replay.md)要求旧结果保持可读且不覆盖。

- `src/pring_cycle/model_evaluation.py`中的`evaluate_context_replay`会计算两侧每天的macro/inventory，校验公式输出和血缘；结束时`ContextReplayEvaluation`只返回差异数量、cutoff数量、耗时及缺口，未返回或保存逐日文档与完整采用证据指纹。
- `_normalized_context`有意排除版本身份等非语义噪声，用于判断两模型结果是否不同。这是合法比较规则，但不能代替保存与输入版本绑定。
- 本批`core_output_document`覆盖三核心及候选字段。`ModelRepository.replay_matches_current_evidence`核对该完整hash，同时仍只比较上下文的`context_output_differences`数量；它没有获得上下文逐日快照可供核对。

**待复现：**只补入在原PUBLIC cutoff可见的P1新vintage，两侧计算仍相同、差异数量不变、三核心完全不变时，已有回放是否仍被误判与当前证据一致。不能把这条静态推断写成已执行的失败结论。

## 下一纵向验证

复用真实EvidenceRepository及已支持的LPR/RRR公开组件，不patch内部投影/认证/评价器：先获得满足各自定义的两侧上下文回放，再经记录/读取边界核逐日值和采用身份。追加可靠历史PUBLIC的新声明后，旧存档不变，新评价保留当日字段及血缘，旧完整验收应失配；若只变版本ID而经济内容相同，两模型的语义差异计数仍可以为0。

缺日/维度不足、派生父项缺失、上下文原件损坏应保留明确失败状态，不能为追求保存成功而补0、跳过必要P1或把旧v3作为合格基线。新结构化明细应沿用本批同事务、可核hash、不可变和旧记录`not_recorded`边界。

这项续作不替代normalized消费核验、新目录active Worker完整纵向、业务规则冻结、真实来源认证与120日实际验收。后续先从公开反例确认缺口，再按影响范围实现和复审。
