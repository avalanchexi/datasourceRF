# 票11两轴复审596

根线程已全文读取两报告并核SHA；固定596快照，不代表后续代码验收。

## Standards

# 票 11 Standards 复审（596）

固定 HEAD：`5e186f740be3d275cba5664a13ef0290e6a57916`；commit list：空。授权 WIP 比较：`cat .scratch/pring-data-acquisition-repair/futures-review-596/changes.patch`。已核 [manifest](futures-review-596/manifest.json) 与三文件快照 SHA-256；补丁 SHA-256：`63bb6e023f2dd7b7f3e4eef5aa6be62bccd0376e756fc8d624b11b355b21919b`。仅审 538 后本票增量；589 已读部分沿用，逐项检查 589→596 新增绑定入口及测试，TuShare 快照未变。

硬规范违规：**未发现**。规范源沿用 AGENTS.md、docs/agents/domain.md、CONTEXT.md、ADR 0004/0006/0012/0013、docs/development/local-runtime.md、spec.md Testing Decisions。

新增 `futures_inputs.py:518–562` 使用真实仓库校验既存 TuShare 父获取的来源、接口、解析版本、validated 状态，重新核验 raw，仅追加审包获取及规范化批次；失败保留失败收据。原父获取和原件不覆盖，符合 ADR 0006 的“追加保存，不原地覆盖”。新增测试从公开采集、绑定和双点时查询读回身份、原件及旧 SYSTEM 结果，符合已授权边界及 Testing Decisions 1/2/4；不把测试成功当作来源认证。工具覆盖项不列人工发现。

判断性 smell：**2 项，均 P3、非阻断**。

- **Possible Duplicated Code（保留589建议）**：`test_futures_inputs.py:148–155、177–184、222–229、395–402、461–468、508–515、641–648、832–839、1086–1093`，新增 `1759–1766`，重复 `json.loads(raw)` → `fields.index(field)` → `items[0][column] = value` → `json.dumps(document).encode()`。可日后局部提取响应变更辅助函数，保持业务输入与期望值独立；不要求本阶段大范围重构。
- **Possible Duplicated Code（新增）**：`futures_inputs.py:450–460` 与 `526–536` 重复 `repository.capture(provider="reviewed_evidence", api_name="futures_input_evidence", … parse=lambda raw: _load_evidence(raw, paths.artifacts, verify_originals=True), … defer_validation=True)`。两个入口未来修改审包取得约束时可能漂移；可考虑一个私有审包捕获函数，仅统一相同配置，保留两者各自的终态处理。

publication/session 共用 `_validate_publication` 的修复仍在；ADR 0004 明确允许 TuShare 适配接缝，不报 Middle Man。其余基线 smell 未见值得报告的问题。

仅静态复审，未读取另一轴，未测试、安装、联网或修改源码、测试、冻结输入。589 报告保持不变。

结论：Standards 硬违规 0，判断性 smell 2；最严重项为非阻断 P3 重复逻辑。

## Spec

# Spec 复审：票11 / 596

固定 HEAD：`5e186f740be3d275cba5664a13ef0290e6a57916`；commits：`[]`。比较命令：`cat .scratch/pring-data-acquisition-repair/futures-review-596/changes.patch`。三快照及补丁 SHA256 均与 [manifest](futures-review-596/manifest.json) 匹配；补丁为 `63bb6e023f2dd7b7f3e4eef5aa6be62bccd0376e756fc8d624b11b355b21919b`。范围仍为538后票11输入模块、测试及适配器方法/返回类型导入。沿用 AGENTS、CONTEXT、规格、业务决定及 ADR0006/0012/0013；只读审查，未测试、安装或修改冻结输入，未读取 Standards 报告。

(a) 遗漏/部分实现：**589 的 P1 已解决。** [票11:25](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/issues/11-futures-contract-evidence.md:25)要求“经公开采集和输入查询……事件发布时间和原件关联”。新增 [bind_futures_input_evidence:518](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/futures-review-596/futures_inputs.py:518)从既存已验证TuShare收据读取原件，只新建已审材料收据及标准化版本。已读592能力缺失RED、593单例GREEN及594两项控制记录；冻结[测试:1635](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/futures-review-596/test_futures_inputs.py:1635)核对请求标识变化、无额外网络请求、旧收据/raw/normalized及早期SYSTEM结果不变。没有继续要求旧证明错误匹配新响应。

(b) 越界：未发现。

(c) **P2 — 给旧原件后补审查会把当前SYSTEM值退回旧修订。** [规格:104](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/spec.md:104)要求“数值修订前后的公开点时和系统点时各自选中正确版本”；[CONTEXT:146](/mnt/d/cursor/datasourceRF/CONTEXT.md:146)将Vintage限定为“随上游修订或回填形成的不可变版本”。设先取得并验证同合约旧结算100，再取得上游新修订110，最后仅为旧100原件后补发布时间审查：冻结[代码:290](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/futures-review-596/futures_inputs.py:290)把新审查收据加入旧价父项，[628–644](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/futures-review-596/futures_inputs.py:628)同时用父项最大validated_at判断可见性和SYSTEM修订顺序，因此旧100压过已验证110。后审没有产生新的上游数值修订。应区分原件版本的新旧与审查版本的可见时间；较新SYSTEM截止仍应选110，旧PUBLIC历史可以获得其合法时间依据。[现测试:1735](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/futures-review-596/test_futures_inputs.py:1735)只核最早SYSTEM截止，且两次行情数值相同，未覆盖此场景。此项为静态发现，尚待公开RED，不宣称已复现。

共1项剩余软件发现，589原P1已关闭。595完整67项和静态检查的运行结果由根线程另行验收；真实PP、历史PUBLIC及许可认证仍缺，票11保持blocked，票12选约/派生不计本票软件缺陷。

Standards：硬违规0、P3建议2；Spec：剩余P2错误1（后审旧值越过新修订），589P1能力缺口已解决。
