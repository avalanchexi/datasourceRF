# 票11两轴复审608

根线程已全文读取两报告并核SHA；只评价608快照，实际测试/独立提交验证另验。

## Standards

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

## Spec

# Spec 复审：票11 / 608

固定 HEAD：`5e186f740be3d275cba5664a13ef0290e6a57916`；commits：`[]`。比较命令：`cat .scratch/pring-data-acquisition-repair/futures-review-608/changes.patch`。三快照及补丁 SHA256 全部匹配 [manifest](futures-review-608/manifest.json)；补丁为 `1deed9cb240a7f78b1e64f0d0cebb40da9277d0effa5e5524196de3af7a2be9f`。范围仍为538后本票输入模块、测试及适配器方法/返回类型导入。沿用既读 AGENTS、CONTEXT、规格、业务决定和 ADR0006/0012/0013；独立Spec只读复核，未测试、安装、修改冻结输入或读取Standards报告。

(a) 软件要求遗漏/部分实现：未发现新的具体问题。(b) 越界：未发现。(c) 看似实现却错误：未发现新的具体问题。

**604的PUBLIC P2已在608代码中解决。** [规格:104](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/spec.md:104)要求“数值修订前后的公开点时和系统点时各自选中正确版本”；[票11:19](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/issues/11-futures-contract-evidence.md:19)要求“覆盖到期及交易所调整事件”。冻结[代码:283](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/futures-review-608/futures_inputs.py:283)继续保留全部父项最大PUBLIC时间，[290–300](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/futures-review-608/futures_inputs.py:290)另外从事实自身接口的已审原件绑定中取得source_public_available_at；[664–668](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/futures-review-608/futures_inputs.py:664)先过全部父项可见门，再按自身来源公开时间排序。因此晚公布的到期调整不会把旧结算抬成新价格修订，未知或截止之后的必要父项仍阻止提前可见。

时间来自既有API/参数/raw_hash逐项绑定及原件重建，没有从SYSTEM或抓取时间推PUBLIC；时段直接使用其自身证明时间。[冲突比较:584](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/futures-review-608/futures_inputs.py:584)排除证据时间，但保留数值、单位和事实身份差异。原SYSTEM修复保持不变。

已读[606实际RED](verification-futures-public-order-red-606.txt)。冻结[新增测试:1905](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/futures-review-608/test_futures_inputs.py:1905)构造28日旧价、29日更正、30日延期公告，并在公告前及精确公布时点独立断言价格仍600、到期日从8月31日变为9月1日。这些代码与静态审查不替代正在进行的607完整70项、类型及静态检查终态验收。

Spec剩余软件发现：0。589后审入口及596/601的SYSTEM问题继续保持解决；旧报告均不改写。真实PP发布方样本、历史PUBLIC及许可认证仍缺，票11保持blocked；本结论不授予来源认证、不关闭票12选约/派生或整体验收。

Standards：硬违规0、非阻断P3建议2（测试准备与审包捕获重复，保留后续局部整理建议）；Spec：剩余软件发现0。真实认证、12和整体验收仍开放。
