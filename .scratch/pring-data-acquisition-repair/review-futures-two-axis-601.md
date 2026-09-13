# 票11两轴复审601

根线程已全文读取两报告并核SHA；固定601快照，不代表后续代码验收。

## Standards

# 票 11 Standards 复审（601）

固定 HEAD：`5e186f740be3d275cba5664a13ef0290e6a57916`；commit list：空。授权 WIP 比较：`cat .scratch/pring-data-acquisition-repair/futures-review-601/changes.patch`。已核 [manifest](futures-review-601/manifest.json)、三快照 SHA-256 及补丁 SHA-256 `1c3c1d98d881ac4b7b2ee416175909ce33f879039a182970b5260f600a366069`。范围为 538 后本票增量；沿用596已审内容，逐项检查596→601新增查询逻辑与公开反例，TuShare快照未变。

硬规范违规：**未发现**。沿用 AGENTS.md、docs/agents/domain.md、CONTEXT.md、ADR 0004/0006/0012/0013、docs/development/local-runtime.md 与 spec.md Testing Decisions。

`futures_inputs.py:628–647` 先由全部父项 validated 时间决定 SYSTEM 可见性，再以排除审包后的 TuShare 父项时间排序数值版本；只含审包的时段仍按证明版本排序。`available_at` 保持全部必要证据首次完成校验的时间，PUBLIC仍按公开时间选择，符合 CONTEXT.md“系统可用时间”“公开点时查询”及 ADR 0006 的双点时语义。新增 `test_futures_inputs.py:1817–1873` 经公开采集→真实仓库→公开绑定→双点时查询，独立断言新值600、旧PUBLIC值584.2、旧SYSTEM读回和采用身份；符合已授权边界与 Testing Decisions 1/2/4，未替换内部选值实现。

判断性 smell：**保留2项，均P3、非阻断；无新增类别**。

- **Possible Duplicated Code（测试准备）**：`test_futures_inputs.py:148–155、177–184、222–229、395–402、461–468、508–515、641–648、832–839、1086–1093、1759–1766`，本轮新增 `1830–1837`，重复 `json.loads(raw)` → `fields.index(field)` → `items[0][column] = value` → `json.dumps(document).encode()`。可后续局部提取响应变更辅助函数，保持独立业务期望值；不要求本阶段大范围重构。
- **Possible Duplicated Code（审包捕获）**：`futures_inputs.py:450–460` 与 `526–536` 重复 `repository.capture(provider="reviewed_evidence", api_name="futures_input_evidence", … parse=lambda raw: _load_evidence(raw, paths.artifacts, verify_originals=True), … defer_validation=True)`。可后续用私有辅助函数统一配置，避免两个入口约束漂移；保留各自终态处理。

publication/session共用校验仍在；TuShare委托符合ADR 0004的适配接缝，不报Middle Man。其余基线smell无新增发现；工具覆盖项不列人工发现。

仅静态复审，未读取Spec轴，未运行测试、安装、联网或修改源码、测试、冻结输入；596报告未覆盖。本报告不宣称600运行结果。

结论：Standards硬违规0，判断性smell2；最严重项为非阻断P3重复逻辑。

## Spec

# Spec 复审：票11 / 601

固定 HEAD：`5e186f740be3d275cba5664a13ef0290e6a57916`；commits：`[]`。比较命令：`cat .scratch/pring-data-acquisition-repair/futures-review-601/changes.patch`。三快照和补丁 SHA256 均匹配 [manifest](futures-review-601/manifest.json)；补丁为 `1c3c1d98d881ac4b7b2ee416175909ce33f879039a182970b5260f600a366069`。仅审538后本票输入模块、测试及适配器方法/返回类型导入。沿用既读 AGENTS、CONTEXT、规格、业务决定及 ADR0006/0012/0013；只读Spec审查，未测试、安装或修改冻结输入，不读取Standards报告。

(a) 遗漏/部分实现：589后审入口缺口继续保持解决。(b) 越界：未发现。

596的原复现场景已修复：[代码:633](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/futures-review-601/futures_inputs.py:633)先用全部父项校验时间执行SYSTEM可见门，再排除审查包时间进行来源版本排序；时段无TuShare父项时使用证明版本时间，PUBLIC分支不变。已读598中584.2错误替换600的实际失败记录，冻结[测试:1817](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/futures-review-601/test_futures_inputs.py:1817)检查当前SYSTEM保持600、旧截止不变及PUBLIC仍读已审584.2。完整同版本测试和静态门由根线程另验。

(c) **P2残留 — 跨批绑定仍可由新元数据把旧结算抬成最新SYSTEM版本。** [规格:104](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/spec.md:104)要求“数值修订前后的公开点时和系统点时各自选中正确版本”；[票11:26](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/issues/11-futures-contract-evidence.md:26)要求验证“事后修订”。[绑定校验:538](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/futures-review-601/futures_inputs.py:538)接受来自不同批次的validated TuShare收据；[355–371](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/futures-review-601/futures_inputs.py:355)再将所给fut_basic身份与fut_daily价格组合。先取得8月28日584.2，再取得当日修订600，随后正常采集另一交易日的新元数据；后审时若给出第三批fut_basic及第一批8月28日fut_daily，[638–644](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/futures-review-601/futures_inputs.py:638)仍取包含身份收据的最大时间，使旧584.2压过600。全部原件和收据可以合法且完好，无须伪造数据。

应让各类事实按自身来源接口的版本排序：settlement使用fut_daily，contract使用fut_basic，calendar使用fut_trade_cal，session使用证明包；其他父项继续约束可见性，不能由身份刷新制造价格修订。现新增测试只后审原批次全组收据，未覆盖重配。此项是静态残留，尚待公开RED；不把596已经复现并修复的同批场景重复计为新发现。

共1项剩余P2。真实PP、历史PUBLIC及许可认证缺件仍保持blocked；12负责选约及派生，均不计本票软件缺陷。旧589/596报告不变。

Standards：硬违规0、P3建议2；Spec：剩余P2错误1（跨批新元数据抬高旧价格顺序），同批场景已解决。
