# 上下文逐日快照与输入版本绑定

2026-09-09，基点 `6662bc2f5d7c8914fdedaab187a15aaea5f042c8`。票19/21的软件续作已通过**432项关联回归，0失败，611.08秒**，包含19项新增用例。mypy92、Ruff/格式9文件和90安装Python源核对通过，双轴复审剩余0。正式来源认证、实际完整候选、120中国交易日重放、合格AI输出及真实切换仍未通过。

## 已实现的行为

- 每个PUBLIC截止日保存候选/比较模型的macro、inventory、采用声明ID、警告、仓单覆盖，以及必需来源指标的全部可见期次选值历史。最新卡片不变时，较早仓单覆盖依据的新版本也进入指纹。历史点用于存证；当前仓单资格仍按实际采用成员校验，退出仓库旧坏点不混入当前输入。
- 模型清单hash、范围、交易日集合与日历hash、必需来源和公式范围、经济差异数和完整上下文文档共同绑定。源范围从同一个 `ContextReplayScope` 计算，不能把必要上下文改成“不适用”或自行缩小指标集合。
- 经济差异仍排除声明身份等元数据；完整输出hash保留这些身份。LPR同值新vintage能使旧回放与当前证据失配，而差异计数仍为0。旧文档不随补证覆盖。
- 沿用SQLite追加式 `model_evaluation_output`，上下文明细与回放引用在同一事务保存。读取核hash及结构/身份/日期/成员/声明关联/取值/单位/公开时间；失败明细保留坏输入与原因。新hardened duration-v0002缺上下文明细不能通过，已有核心和真实来源准入门继续生效。
- `model-replay-show`及GET `/api/v1/model-replays/{replay_id}`返回保存的上下文文档与状态。旧记录明确`not_recorded`，不在读取时补算或授予资格。0021迁移给0020追加可空引用，0019/0020旧失败记录均保留。

这里的 `source_inputs` 是截止时点的可见选值历史，包含覆盖校验和派生可能需要的历史期次；实际经济采用身份另存于投影字段。它不是“这些历史点全部参加当前经济判断”的声明，也不是新取得的官方原件。

## 可复核反例与修复

- [最初LPR版本反例](verification-context-snapshot-red-01.txt)到[通过](verification-context-snapshot-green-01.txt)：核心hash及经济差异数不变，旧证据机验仍须失配。
- [来源取值缺失](verification-context-snapshot-inputs-red-01.txt)到[通过](verification-context-snapshot-inputs-green-01.txt)：保存两个期限的独立字面值及所选ID。
- [缺声明ID](verification-context-identity-red-01.txt)到[3项通过](verification-context-identity-green-01.txt)；[伪造不适用](verification-context-scope-red-01.txt)到[86项模型回归](verification-context-scope-green-01.txt)。
- 审查发现整点可删除：[缺期限/空列表/孤立ID三项RED](verification-context-members-red-02.txt)到[4项GREEN](verification-context-members-green-01.txt)。`members-red-01`是WSL启动0x8007274c失败，未执行pytest，不充当缺陷证明。
- [清空经济输出RED](verification-context-economic-red-01.txt)到[6项GREEN](verification-context-economic-green-01.txt)。数值、单位、版本、时间和所选声明一致性继续检查；[字符串数值RED](verification-context-value-red-01.txt)到[13项GREEN](verification-context-value-green-01.txt)。
- [较早仓单同值版本RED](verification-context-warrant-red-01.txt)到[3项GREEN](verification-context-warrant-green-01.txt)：5个合成日期，正式注册来源组件和真实原件收据通路，首日CU重取改变保存内容，不改变经济差异数。
- [失败输入不能保存RED](verification-context-failure-red-01.txt)到[5项GREEN](verification-context-failure-green-01.txt)：坏质量如实保存，保持失败；同时覆盖1月26日3.0、27/28日2.9的PUBLIC取值、晚取得、旧库迁移和旧核心明细边界。
- 复审发现退出仓库被误加质量门：[公开保存RED](verification-context-retired-red-01.txt)到[13项GREEN](verification-context-retired-green-01.txt)。独立组件fixture保存上下文为recorded，旧invalid可读；整条模型回放仍因核心明细等缺口failed，未绕过完整模型准入。

最初关联[83通过/1失败](verification-context-snapshot-models-01.txt)是非法布尔天数先被新增上下文校验拒绝，旧测试只匹配核心错误前缀；修正测试预期后通过。两次融资探索失败分别是旧fixture单位不符、新目录 `registered_source_contract_not_implemented:CN_MARGIN_BALANCE`；原日志保留，不能作为已修复融资的证据。最初mypy两项、后续四项类型诊断已处理，最终检查另存。

## 审查与最终门

[两轴审查](verification-context/review.md)分别保留发现及关闭结果，未把静态审查当真实运行。[432项关联回归](verification-context-associated-01.txt)覆盖全部models、趋势、候选、上下文投影/认证/收据、派生鲜度、仓单、Worker、原子投影、两组CLI及查询API，进程终态为0。这是本切片关联范围，不是全项目最终门。[检查点](verification-context/checkpoint.json)绑定最终源码与日志；安装和工作区90个Python文件逐一一致。

## 仍开放的整体条件

融资的新目录来源合同仍未接通；其他实际P1/P2来源认证、历史公开时间、北交所/CNY030/估值/股票池/商品原件与规则仍不足。新目录active Worker完整纵向、normalized消费完整性及全项目最终门继续开放。未新增网络请求、来源认证或生产写入；真实合格AI输出仍为0。真实窗口仍为2026-03-09至2026-08-28的120中国交易日及独立预热，不用本批合成组件测试替代。

下一公开反例入口已定位于[标准化消费边界](normalized-consumption-boundary.md)。这是源码定位，尚未执行其RED；不把本批432项通过用于证明该后续行为。
