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
