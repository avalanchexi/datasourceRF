# Spec 独立审查：票10／515

范围：HEAD `7828c99799bf958092403a825c2303814c48763a`＋502工作区基线→515冻结快照。8文件哈希及指定patch `19cba342…da46`均相符；未审入旧WIP，未运行测试或修改应用。

1. **P2，重复金额事实可被不同标签重复计入。** [票10:25](issues/10-breadth-amount-share.md#L25)要求“重复覆盖”边界及“不靠缩小金额范围获得完整状态”；[已确认规则§10](business-decisions-draft.md#L38)明确“无法排除渠道重复覆盖，结果不可用且不可认证”。冻结[market_amount:110](amount-review-515-market_amount.py.txt#L110)只排重`methods`标签，[150–190](amount-review-515-market_amount.py.txt#L150)逐分量取数累加，没有排重同原件、同证券日、同字段事实。最小公开反例：完整正例仅把A盘后分量的`field=ah_amount`改成`amount`，保持两种不同methods标签并重新绑定合成审查；同一竞价金额会计算两次，静态推得N=220000、D=490000，仍输出可用。应拒绝重复覆盖。[现有测试:14515](amount-review-515-test_candidate_admission.py.txt#L14515)只覆盖标签重复／空标签，未覆盖此错误。需公开RED确认实际采用结果。

2. **P2，未采用独立原件仍阻断单日消费。** [Testing21](spec.md#L198)要求“派生家族还核对父项集合及公式结果”，[票10:24](issues/10-breadth-amount-share.md#L24)要求金额关联到“分子、分母与原件”。据此推导采用边界，不引用信用脉冲专属规则。[market_amount:39](amount-review-515-market_amount.py.txt#L39)校验包内全部外部proof，候选按`period`重建时仍先调用此加载器；但[101、168、221](amount-review-515-market_amount.py.txt#L101)记录的实际采用证据只含coverage及当日分量。最小公开反例：共享审查包含两日、两日金额原件独立，成功采集后仅损坏第二日原件；首日候选也会被拒。应保留首日采用，第二日拒绝。共享审查JSON／coverage原件仍须整体校验；不扩展修改08身份证据。该路径尚需双日公开RED。

未发现额外范围扩张；全池分母、未知保留、适用性时间与注册消费已有接线。以上两处使软件要求仍部分满足。真实盘后补证、官方差额及认证仍按票10:17–20开放。根线程报告515家族15项通过；这些既有场景未证明上述两个反例。
