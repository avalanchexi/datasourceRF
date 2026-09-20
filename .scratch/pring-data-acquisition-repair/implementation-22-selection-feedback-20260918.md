# #22 相关验证中的选择器成本修复（2026-09-18）

Status: implemented-awaiting-common-frozen-validation

必要日历回归的 profile 显示约101782次 SQLite 连接、90568次 source_claim_acquisitions_many；选择器为不属于本次指标的来源族也调用空集合校验。保留所有相关且已注册来源族（包括重叠归属）的原件校验，只跳过无对应指标的空调用；未引入跨运行缓存，也未放宽准入或来源身份检查。

同一组6个无外部网络等待的正向日历用例，230.88秒降至56.44秒。对应比较收据 `verification-22-selection-feedback-comparison-20260918.json` 在主工作树，包文件差异只有 search_evidence.py。该局部收益不能外推为全套或真实Worker耗时。

扩展来源反例首批63通过、16失败（175.96秒）；16项均因既有测试删除已准入 manifest 的认证包，触发当前身份绑定校验。用优化前包复跑同例也失败，确认不是本次优化引入。另10项直接来源测试使用准入前请求manifest，同样尚未触达原件校验。

修复仅涉及这三个 interbank 测试：读取完整已准入 manifest；16参数测试更名 PUBLIC 投影/选值组件验证，通过公开 build_context_projection 和 select_retrieval_input 保留损坏/缺失、晚修订、旧值不可复活、历史切点及比较侧隔离断言。完整回放编排、覆盖检查及特定聚合gap分类仍由合法完整材料验收，不冒充由此组件测试证明。

[修复后的28项](verification-22-interbank-bound-manifest-final-20260918.txt)全部通过85.30秒。其他已知类似旧夹具尚需逐例审查，不能批量删除认证字段或放宽产品身份校验。

## Standards

选择器优化：硬违规0、判断项0。夹具修复：硬违规0、判断项0。无跨run缓存、无注册族漏检或内部选择逻辑替身。

## Spec

无阻断项。未削弱公开时间、来源原件和已准入身份约束；组件验证范围已明示。最终同版本完整验证及受影响重型验收仍待执行。
