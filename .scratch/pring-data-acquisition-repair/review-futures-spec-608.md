# Spec 复审：票11 / 608

固定 HEAD：`5e186f740be3d275cba5664a13ef0290e6a57916`；commits：`[]`。比较命令：`cat .scratch/pring-data-acquisition-repair/futures-review-608/changes.patch`。三快照及补丁 SHA256 全部匹配 [manifest](futures-review-608/manifest.json)；补丁为 `1deed9cb240a7f78b1e64f0d0cebb40da9277d0effa5e5524196de3af7a2be9f`。范围仍为538后本票输入模块、测试及适配器方法/返回类型导入。沿用既读 AGENTS、CONTEXT、规格、业务决定和 ADR0006/0012/0013；独立Spec只读复核，未测试、安装、修改冻结输入或读取Standards报告。

(a) 软件要求遗漏/部分实现：未发现新的具体问题。(b) 越界：未发现。(c) 看似实现却错误：未发现新的具体问题。

**604的PUBLIC P2已在608代码中解决。** [规格:104](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/spec.md:104)要求“数值修订前后的公开点时和系统点时各自选中正确版本”；[票11:19](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/issues/11-futures-contract-evidence.md:19)要求“覆盖到期及交易所调整事件”。冻结[代码:283](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/futures-review-608/futures_inputs.py:283)继续保留全部父项最大PUBLIC时间，[290–300](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/futures-review-608/futures_inputs.py:290)另外从事实自身接口的已审原件绑定中取得source_public_available_at；[664–668](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/futures-review-608/futures_inputs.py:664)先过全部父项可见门，再按自身来源公开时间排序。因此晚公布的到期调整不会把旧结算抬成新价格修订，未知或截止之后的必要父项仍阻止提前可见。

时间来自既有API/参数/raw_hash逐项绑定及原件重建，没有从SYSTEM或抓取时间推PUBLIC；时段直接使用其自身证明时间。[冲突比较:584](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/futures-review-608/futures_inputs.py:584)排除证据时间，但保留数值、单位和事实身份差异。原SYSTEM修复保持不变。

已读[606实际RED](verification-futures-public-order-red-606.txt)。冻结[新增测试:1905](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/futures-review-608/test_futures_inputs.py:1905)构造28日旧价、29日更正、30日延期公告，并在公告前及精确公布时点独立断言价格仍600、到期日从8月31日变为9月1日。这些代码与静态审查不替代正在进行的607完整70项、类型及静态检查终态验收。

Spec剩余软件发现：0。589后审入口及596/601的SYSTEM问题继续保持解决；旧报告均不改写。真实PP发布方样本、历史PUBLIC及许可认证仍缺，票11保持blocked；本结论不授予来源认证、不关闭票12选约/派生或整体验收。
