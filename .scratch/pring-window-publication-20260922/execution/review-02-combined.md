# 票02两轴审查

两轴经独立只读CLI并行执行，均exit0；范围为对应review-02-input.json固定的WIP。下面保持两个轴分开。

## Standards

Standards 结论：未发现可确认的硬违反，也未发现值得单列的 smell 问题。

- 已核验两个文件及固定差异的 SHA-256；按指定命令重建的 WIP 差异与 `review-02.diff` 字节一致。基点后无新提交，仅审查指定两文件。
- 已读 AGENTS、CONTEXT、testing、domain 及相关 ADR；未找到独立编码标准文档。已逐项应用 12 项 smell baseline，未将命名偏好或既有结构判为硬违反。
- `candidate_admission.py:68–85、253–258` 使用精确迁移声明、冻结定义及专项比对；没有复用 v3 历史认证状态。静态检查符合 `ADR-0020:7–9` 的单项降级、保留待认证及核心门槛要求。
- 新测试经公开 CLI、登记目录、PUBLIC/SYSTEM 选择与投影检查行为；未发现新增内部 mock 或测试后门。

本轮未运行测试。完整 Worker、报告证据排除及发布历史不变仍未验证；依据 `docs/agents/testing.md:19`，88 项选择测试不能替代受影响重型验收。本结论仅针对当前 WIP 的 Standards 轴，不代表整票通过。

## Spec

结论：**Spec 部分满足，整票不能关闭。** 固定 diff 和两文件哈希均匹配，base..HEAD 无提交。已完整阅读父规格、票02及 ADR0020；以下为静态审查，未运行测试。

1. **核心源身份拒收不完整。** 票02 AC4、规格实施§12要求拒绝更换核心身份。新增完整定义比较仅覆盖 CNY030；[candidate_admission.py:253](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-02/src/pring_cycle/candidate_admission.py:253) 后续检查只固定核心 ID 映射、角色和认证状态。若保持这些字段、修改债券核心 `source_codes` 并重新绑定审核包，静态路径未见准入拒绝；入库合同才另行拦截。属于新迁移未补齐的拒收要求，**未实测**。

2. **报告引用白名单缺少认证过滤。** 票02 AC3、规格实施§12要求待认证 CNY030 不进入报告证据。[context_projection.py:1655](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-02/src/pring_cycle/context_projection.py:1655) 保留其观测 ID，[reports.py:237](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-02/src/pring_cycle/reports.py:237) 无条件递归收集，随后成为 `allowed_evidence_ids`。静态推断该 ID 可被引用；数值已隐藏，**不能据此声称报告实际采用过未认证数值**。

3. **Worker 完成链仍缺交付。** 票02 AC3、规格测试§7要求其余材料合法时完整运行可完成。新增测试止于直接选值和构建上下文；且[来源合同:359](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-02/src/pring_cycle/source_contract_review.py:359) 仅支持旧融资 ID，新沪深 ID 会落入未实现分支。须整合融资合同并验证完整链，88项不能替代。

4. **历史不可变验证仅覆盖部分对象。** 票02 AC5、规格实施§13还要求旧声明、已发布投影和报告不变；[新增测试:261](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-02/tests/models/test_cny030_optional_migration.py:261) 只比较旧目录、模型和请求原件，缺其余对象的前后核验。

未见超范围实现；CNY030 完整定义、P2待认证、ECB/黄金/融资组合及其他核心/P1认证门的准入切片符合方向。

Standards：0项，无发现。Spec：4项，核心源身份拒收及报告/Worker边界须继续证明并补齐。
