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
