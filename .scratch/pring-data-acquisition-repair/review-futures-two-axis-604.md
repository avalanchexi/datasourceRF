# 票11两轴复审604

根线程已全文读取两报告并核SHA；固定604快照，不代表后续代码验收。

## Standards

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

## Spec

# Spec 复审：票11 / 604

固定 HEAD：`5e186f740be3d275cba5664a13ef0290e6a57916`；commits：`[]`。比较命令：`cat .scratch/pring-data-acquisition-repair/futures-review-604/changes.patch`。三快照及补丁 SHA256 全部匹配 [manifest](futures-review-604/manifest.json)；补丁为 `60ce3c4b68bba5134ffe88aaaca1693ec5685bbd8f5132179e33c9b13e7b1564`。范围为538后票11输入模块、测试及适配器方法/返回类型导入。沿用既读 AGENTS、CONTEXT、规格、业务决定及 ADR0006/0012/0013；独立Spec只读审查，未测试、安装或修改冻结输入，未读取Standards报告。

(a) 遗漏/部分实现：未发现新的入口缺口。(b) 越界：未发现。

**601的SYSTEM残留已修复。** 冻结[来源映射:32](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/futures-review-604/futures_inputs.py:32)与[排序:634](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/futures-review-604/futures_inputs.py:634)使settlement仅按fut_daily原件版本排序；身份、日历、时段各用自身来源，全部父项继续约束SYSTEM可见性。合法跨批组合仍可用。已读602中跨批失败、原同批通过的记录；冻结[参数化测试:1816](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/futures-review-604/test_futures_inputs.py:1816)同时核两种组合下SYSTEM保持600、旧截止不变、原PUBLIC584.2可读。本报告不代替603完整运行终态及静态门验收。

(c) **P2 — PUBLIC仍将较新的支持元数据误当价格修订。** [规格:104](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/spec.md:104)要求“数值修订前后的公开点时和系统点时各自选中正确版本”；[票11:19](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/issues/11-futures-contract-evidence.md:19)要求“覆盖到期及交易所调整事件”。若旧结算584.2于8月28日公开、新修订600于29日公开，30日又公布不改变报价含义的到期日延期；将30日元数据与28日旧价格原件后审组合，[283–289](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/futures-review-604/futures_inputs.py:283)取全部父项最大PUBLIC时间30日，[650–661](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/futures-review-604/futures_inputs.py:650)又把它作为价格版本顺序。31日PUBLIC查询因此选择584.2，压过29日已公开的600。

需要保留全部父项的PUBLIC可见门，同时按事实自身来源的公开版本时间排序；元数据晚公开不能制造价格修订。现跨批测试的元数据发布时间仍沿用第一批，尚未覆盖这个公开时序。此项为静态发现，尚待公开RED；不重报已经修复的SYSTEM问题。

共1项剩余P2。真实PP发布方样本、历史PUBLIC及许可认证仍缺，票11保持blocked；票12选约/派生不计为本票软件缺陷。589、596及601报告保持不变。

Standards：硬违规0、P3建议2；Spec：剩余P2错误1（PUBLIC元数据公告抬高旧价格），SYSTEM场景已解决。
