# 票 11 Standards 复审（608）

固定 HEAD：`5e186f740be3d275cba5664a13ef0290e6a57916`；commit list：空。授权 WIP 比较：`cat .scratch/pring-data-acquisition-repair/futures-review-608/changes.patch`。已核 [manifest](futures-review-608/manifest.json)、三快照 SHA-256 及补丁 SHA-256 `1deed9cb240a7f78b1e64f0d0cebb40da9277d0effa5e5524196de3af7a2be9f`。范围为538后本票增量；沿用604已审内容，逐项核604→608全部变动，TuShare快照未变。

硬规范违规：**未发现**。规范源沿用 AGENTS.md、docs/agents/domain.md、CONTEXT.md、ADR 0004/0006/0012/0013、docs/development/local-runtime.md 与 spec.md Testing Decisions。

`futures_inputs.py:290–300` 从已经过审包检查且匹配原件身份的来源发布项生成 `source_public_available_at`；未知时保持空，时段使用自身证明的公开时间（420行）。查询在665–668行先用全部父项的整体公开时间控制可见，再以自身公开时间排序。时间元数据在592行排除出经济值比较，且选中结果仍须由原件及审包重建核验。该边界符合CONTEXT.md公开可用时间定义与ADR 0006双点时规则，没有借辅助到期公告提升旧结算值的版本顺序。

新增 `test_futures_inputs.py:1905–2008` 从公开采集、真实raw/CAS及公开绑定取得两版价格和后续到期公告，通过公开查询独立断言延期前后价格仍为600、到期日从8月31日变为9月1日。它保留规则对照和持久证据路径，符合已授权边界及Testing Decisions 1/2/4；没有替换内部排序或模拟仓库。

判断性 smell：**保留2项，均P3、非阻断；无新增独立问题**。

- **Possible Duplicated Code（测试准备）**：`test_futures_inputs.py:148–155、177–184、222–229、395–402、461–468、508–515、641–648、832–839、1086–1093、1759–1766、1832–1839、1861–1868`，以及新增1940–1947，重复 `json.loads(raw)` → `fields.index(field)` → `items[0][column] = value` → `json.dumps(document).encode()`。后续可局部提取响应变更辅助函数，保留独立业务期望值；本阶段不要求大范围重构。
- **Possible Duplicated Code（审包捕获）**：`futures_inputs.py:469–479` 与 `545–555` 重复 `repository.capture(provider="reviewed_evidence", api_name="futures_input_evidence", … parse=lambda raw: _load_evidence(raw, paths.artifacts, verify_originals=True), … defer_validation=True)`。后续可统一私有捕获配置、保留各自终态处理，避免约束漂移。

publication/session共用校验仍在；ADR 0004允许TuShare适配接缝，不报Middle Man。其余基线无新增发现，工具覆盖项跳过。

仅静态复审；未读Spec轴，未测试、安装、联网或修改源码、测试、冻结输入；604及此前报告未覆盖。不宣称正在运行的70项验证结果。

结论：Standards硬违规0，判断性smell2；最严重项为非阻断P3重复逻辑。
