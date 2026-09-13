# Spec 复审：票11 / 604

固定 HEAD：`5e186f740be3d275cba5664a13ef0290e6a57916`；commits：`[]`。比较命令：`cat .scratch/pring-data-acquisition-repair/futures-review-604/changes.patch`。三快照及补丁 SHA256 全部匹配 [manifest](futures-review-604/manifest.json)；补丁为 `60ce3c4b68bba5134ffe88aaaca1693ec5685bbd8f5132179e33c9b13e7b1564`。范围为538后票11输入模块、测试及适配器方法/返回类型导入。沿用既读 AGENTS、CONTEXT、规格、业务决定及 ADR0006/0012/0013；独立Spec只读审查，未测试、安装或修改冻结输入，未读取Standards报告。

(a) 遗漏/部分实现：未发现新的入口缺口。(b) 越界：未发现。

**601的SYSTEM残留已修复。** 冻结[来源映射:32](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/futures-review-604/futures_inputs.py:32)与[排序:634](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/futures-review-604/futures_inputs.py:634)使settlement仅按fut_daily原件版本排序；身份、日历、时段各用自身来源，全部父项继续约束SYSTEM可见性。合法跨批组合仍可用。已读602中跨批失败、原同批通过的记录；冻结[参数化测试:1816](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/futures-review-604/test_futures_inputs.py:1816)同时核两种组合下SYSTEM保持600、旧截止不变、原PUBLIC584.2可读。本报告不代替603完整运行终态及静态门验收。

(c) **P2 — PUBLIC仍将较新的支持元数据误当价格修订。** [规格:104](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/spec.md:104)要求“数值修订前后的公开点时和系统点时各自选中正确版本”；[票11:19](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/issues/11-futures-contract-evidence.md:19)要求“覆盖到期及交易所调整事件”。若旧结算584.2于8月28日公开、新修订600于29日公开，30日又公布不改变报价含义的到期日延期；将30日元数据与28日旧价格原件后审组合，[283–289](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/futures-review-604/futures_inputs.py:283)取全部父项最大PUBLIC时间30日，[650–661](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/futures-review-604/futures_inputs.py:650)又把它作为价格版本顺序。31日PUBLIC查询因此选择584.2，压过29日已公开的600。

需要保留全部父项的PUBLIC可见门，同时按事实自身来源的公开版本时间排序；元数据晚公开不能制造价格修订。现跨批测试的元数据发布时间仍沿用第一批，尚未覆盖这个公开时序。此项为静态发现，尚待公开RED；不重报已经修复的SYSTEM问题。

共1项剩余P2。真实PP发布方样本、历史PUBLIC及许可认证仍缺，票11保持blocked；票12选约/派生不计为本票软件缺陷。589、596及601报告保持不变。
