# Spec 复审：票11 / 596

固定 HEAD：`5e186f740be3d275cba5664a13ef0290e6a57916`；commits：`[]`。比较命令：`cat .scratch/pring-data-acquisition-repair/futures-review-596/changes.patch`。三快照及补丁 SHA256 均与 [manifest](futures-review-596/manifest.json) 匹配；补丁为 `63bb6e023f2dd7b7f3e4eef5aa6be62bccd0376e756fc8d624b11b355b21919b`。范围仍为538后票11输入模块、测试及适配器方法/返回类型导入。沿用 AGENTS、CONTEXT、规格、业务决定及 ADR0006/0012/0013；只读审查，未测试、安装或修改冻结输入，未读取 Standards 报告。

(a) 遗漏/部分实现：**589 的 P1 已解决。** [票11:25](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/issues/11-futures-contract-evidence.md:25)要求“经公开采集和输入查询……事件发布时间和原件关联”。新增 [bind_futures_input_evidence:518](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/futures-review-596/futures_inputs.py:518)从既存已验证TuShare收据读取原件，只新建已审材料收据及标准化版本。已读592能力缺失RED、593单例GREEN及594两项控制记录；冻结[测试:1635](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/futures-review-596/test_futures_inputs.py:1635)核对请求标识变化、无额外网络请求、旧收据/raw/normalized及早期SYSTEM结果不变。没有继续要求旧证明错误匹配新响应。

(b) 越界：未发现。

(c) **P2 — 给旧原件后补审查会把当前SYSTEM值退回旧修订。** [规格:104](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/spec.md:104)要求“数值修订前后的公开点时和系统点时各自选中正确版本”；[CONTEXT:146](/mnt/d/cursor/datasourceRF/CONTEXT.md:146)将Vintage限定为“随上游修订或回填形成的不可变版本”。设先取得并验证同合约旧结算100，再取得上游新修订110，最后仅为旧100原件后补发布时间审查：冻结[代码:290](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/futures-review-596/futures_inputs.py:290)把新审查收据加入旧价父项，[628–644](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/futures-review-596/futures_inputs.py:628)同时用父项最大validated_at判断可见性和SYSTEM修订顺序，因此旧100压过已验证110。后审没有产生新的上游数值修订。应区分原件版本的新旧与审查版本的可见时间；较新SYSTEM截止仍应选110，旧PUBLIC历史可以获得其合法时间依据。[现测试:1735](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/futures-review-596/test_futures_inputs.py:1735)只核最早SYSTEM截止，且两次行情数值相同，未覆盖此场景。此项为静态发现，尚待公开RED，不宣称已复现。

共1项剩余软件发现，589原P1已关闭。595完整67项和静态检查的运行结果由根线程另行验收；真实PP、历史PUBLIC及许可认证仍缺，票11保持blocked，票12选约/派生不计本票软件缺陷。
