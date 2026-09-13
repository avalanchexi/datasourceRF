# 票 11 Standards 复审（604）

固定 HEAD：`5e186f740be3d275cba5664a13ef0290e6a57916`；commit list：空。授权 WIP 比较：`cat .scratch/pring-data-acquisition-repair/futures-review-604/changes.patch`。已核 [manifest](futures-review-604/manifest.json)、三快照 SHA-256 与补丁 SHA-256 `60ce3c4b68bba5134ffe88aaaca1693ec5685bbd8f5132179e33c9b13e7b1564`。只审538后本票增量；沿用601已读内容，检查601→604全部变动；TuShare快照未变。

硬规范违规：**未发现**。规范源沿用 AGENTS.md、docs/agents/domain.md、CONTEXT.md、ADR 0004/0006/0012/0013、docs/development/local-runtime.md、spec.md Testing Decisions。

`futures_inputs.py:32–37、634–651` 明确将 contract/calendar/settlement/session 分别映射至 fut_basic/fut_trade_cal/fut_daily/futures_input_evidence。SYSTEM仍须全部父项在cutoff前validated，排序仅采用提供该事实的来源原件时间；缺少自身来源时间时拒绝该交付，不再用其他父项时间代替。该分离与CONTEXT.md的系统可用时间、ADR 0006双点时及追加保存规则相容；PUBLIC分支不变。

`test_futures_inputs.py:1816–1901` 通过公开采集生成新旧价格和跨批元数据，公开绑定后读取SYSTEM当前值、旧SYSTEM结果、PUBLIC值及采用身份。期望值600与584.2明确给出，未调用私有选值实现，也未模拟仓库；符合已授权边界及Testing Decisions 1/2/4。该代码审查不替代本轮实际回归结果。

判断性 smell：**保留2项，均P3、非阻断；无新增独立问题**。

- **Possible Duplicated Code（测试准备）**：`test_futures_inputs.py:148–155、177–184、222–229、395–402、461–468、508–515、641–648、832–839、1086–1093、1759–1766、1832–1839、1861–1868` 重复 `json.loads(raw)` → `fields.index(field)` → `items[0][column] = value` → `json.dumps(document).encode()`。后续可局部提取响应变更辅助函数，保留业务输入与独立期望值；本阶段不要求大范围重构。
- **Possible Duplicated Code（审包捕获）**：`futures_inputs.py:456–466` 与 `532–542` 重复 `repository.capture(provider="reviewed_evidence", api_name="futures_input_evidence", … parse=lambda raw: _load_evidence(raw, paths.artifacts, verify_originals=True), … defer_validation=True)`。可后续统一私有捕获配置，保留各入口终态处理，避免规则漂移。

publication/session共用校验仍在；ADR 0004允许TuShare适配接缝，不报Middle Man。新增单一映射没有引入Repeated Switches；其余基线无新增发现。工具覆盖项跳过。

仅只读静态复审，未读Spec轴，未测试、安装、联网或改动源码、测试、冻结输入；旧报告未覆盖。

结论：Standards硬违规0，判断性smell2；最严重项为非阻断P3重复逻辑。
