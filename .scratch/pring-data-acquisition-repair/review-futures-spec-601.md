# Spec 复审：票11 / 601

固定 HEAD：`5e186f740be3d275cba5664a13ef0290e6a57916`；commits：`[]`。比较命令：`cat .scratch/pring-data-acquisition-repair/futures-review-601/changes.patch`。三快照和补丁 SHA256 均匹配 [manifest](futures-review-601/manifest.json)；补丁为 `1c3c1d98d881ac4b7b2ee416175909ce33f879039a182970b5260f600a366069`。仅审538后本票输入模块、测试及适配器方法/返回类型导入。沿用既读 AGENTS、CONTEXT、规格、业务决定及 ADR0006/0012/0013；只读Spec审查，未测试、安装或修改冻结输入，不读取Standards报告。

(a) 遗漏/部分实现：589后审入口缺口继续保持解决。(b) 越界：未发现。

596的原复现场景已修复：[代码:633](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/futures-review-601/futures_inputs.py:633)先用全部父项校验时间执行SYSTEM可见门，再排除审查包时间进行来源版本排序；时段无TuShare父项时使用证明版本时间，PUBLIC分支不变。已读598中584.2错误替换600的实际失败记录，冻结[测试:1817](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/futures-review-601/test_futures_inputs.py:1817)检查当前SYSTEM保持600、旧截止不变及PUBLIC仍读已审584.2。完整同版本测试和静态门由根线程另验。

(c) **P2残留 — 跨批绑定仍可由新元数据把旧结算抬成最新SYSTEM版本。** [规格:104](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/spec.md:104)要求“数值修订前后的公开点时和系统点时各自选中正确版本”；[票11:26](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/issues/11-futures-contract-evidence.md:26)要求验证“事后修订”。[绑定校验:538](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/futures-review-601/futures_inputs.py:538)接受来自不同批次的validated TuShare收据；[355–371](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/futures-review-601/futures_inputs.py:355)再将所给fut_basic身份与fut_daily价格组合。先取得8月28日584.2，再取得当日修订600，随后正常采集另一交易日的新元数据；后审时若给出第三批fut_basic及第一批8月28日fut_daily，[638–644](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/futures-review-601/futures_inputs.py:638)仍取包含身份收据的最大时间，使旧584.2压过600。全部原件和收据可以合法且完好，无须伪造数据。

应让各类事实按自身来源接口的版本排序：settlement使用fut_daily，contract使用fut_basic，calendar使用fut_trade_cal，session使用证明包；其他父项继续约束可见性，不能由身份刷新制造价格修订。现新增测试只后审原批次全组收据，未覆盖重配。此项是静态残留，尚待公开RED；不把596已经复现并修复的同批场景重复计为新发现。

共1项剩余P2。真实PP、历史PUBLIC及许可认证缺件仍保持blocked；12负责选约及派生，均不计本票软件缺陷。旧589/596报告不变。
