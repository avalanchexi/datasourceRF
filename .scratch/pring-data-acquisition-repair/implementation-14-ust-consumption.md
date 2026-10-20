# Treasury 新目录来源合同与模型消费

2026-09-10；implement + research；继续第90阶段 CLI 修复。主目标及票14/19仍未完成，本批未提交。

**最新实际终态98：**[合并回归](verification-ust-consumer-terminal-98.json)主会话90491已退出0，**113通过、0失败、369.84秒**。8个指定入口/文件包含15项新增合同/消费用例；前后228输入及4受保护文件未变，91安装源码与53依赖一致，两轴剩余各0、Ruff/格式和当前mypy93通过。旧未改Treasury测试的额外mypy23项错误单列保留。默认全套未复验，不以此批替代全项目和真实模型验收。90491已终态，不再轮询。

## 已确认范围

沿用规格 Testing 2–6/11 的公开入口：完整候选公开准入、Treasury 公开采集、来源声明追加、SYSTEM/PUBLIC 读取、上下文和利差、定向选值及组件回放。使用既有年度官方 CSV 原件与隔离 HTTP transport；认证审查是明确的合成 fixture，不授予实际数据来源认证。

新定义保持现有两个无维度标量和 percent 单位，显式绑定 `treasury_nominal_yields_csv.2 Yr` / `.10 Yr`、`treasury_nominal_yields_csv` 发布家族、`America/New_York` 时区和既有 `source_schedule_required`。不将旧 `us_tycr.y2/.y10` 静默解释为 Treasury CSV，不修改旧内置目录。

## 实际执行记录

- [合同RED91](verification-ust-contract-red-91.txt)：主会话21220退出1，1失败、10.18秒；`registered_source_contract_not_implemented:UST2Y_NOMINAL_YIELD`。
- 合同补入后 [第一次复验91](verification-ust-contract-green-91.txt)：主会话86344退出1，1失败、19.92秒。原因是测试把认证声明的 SYSTEM 时间设到先前 validation，晚于它的待认证声明仍被正确选中。测试改用公开追加完成时钟，并修正报告字段断言为 `period`；未修改选值规则来迎合测试。
- [合同GREEN92](verification-ust-contract-green-92.txt)：主会话33054退出0，1通过、17.01秒。真实字面值 4.37% 和 4.78% 形成 41bp 的 SYSTEM 上下文，PUBLIC 未知及历史目标选值缺口保留。
- [消费RED93](verification-ust-consumer-red-93.txt)：主会话32885退出1，1通过、2失败、36.81秒。原件或 normalized 损坏后，两个父项仍被标 current。
- [消费GREEN93](verification-ust-consumer-green-93.txt)：主会话42711退出0，3通过、29.92秒。共同核验已使坏制品退出原值和派生采用，诊断引用保留。
- [哈希自洽收据94](verification-ust-receipts-94.txt)：主会话76581退出0，10通过、59.56秒。覆盖正确批次及数值、单位、窗口、年、响应身份、parser、目录版本和无证据 PUBLIC。
- [最新坏父项95](verification-ust-latest-95.txt)：主会话71223退出0，5通过、44.20秒；覆盖前3例及最新质量invalid/normalized损坏且旧日原件仍有效时，不复活旧39bp利差。与前批范围重叠，不累加。
- [格式96](verification-ust-consumer-format-96.txt)、[Ruff96](verification-ust-consumer-ruff-96.txt)通过；[mypy97](verification-ust-consumer-mypy-97.txt)主会话20949退出0，应用及当前两个受检测试共93文件通过。
- 额外扩大至未改动的旧Treasury集成测试时，[mypy96](verification-ust-consumer-mypy-96.txt)主会话42767退出1，报告该旧测试文件23项类型错误。已用 `git diff --exit-code HEAD -- tests/integration/test_treasury_csv_acquisition.py` 确认文件与HEAD一致；保留原失败，不称扩大类型检查通过。本批没有为此修改旧测试或放宽mypy。
- [两轴审查96](verification-ust-consumer-review-96.md)剩余各0；[启动记录98](verification-ust-consumer-running-98.json)固定8个指定入口/文件和主会话90491。[运行前核验](verification-ust-consumer-runtime-before-98.json)及[运行后核验](verification-ust-consumer-runtime-after-98.json)确认228输入及4受保护文件未变、91安装源码与53依赖一致；该运行已取得本页顶部113通过的实际终态。

## 时间与消费边界

年度 CSV 只有来源日期和数值，没有逐行首次发布或修订公开时间。当前协议只支持 PUBLIC 未知的 Treasury 值；给声明直接填写一个时间不能代替发布证据。无目标日的显式 SYSTEM 上下文可按认证和制品资格展示实际取得值；已有历史目标日约束继续拒绝缺可靠 PUBLIC 的输入。本批不新建合成历史发布时间以制造检索或回放正例。

共享消费核验重读真实 claim–acquisition 关联，核原件与规范化制品、请求身份、完整批次重解析、字段/日期/数值和目录版本；重解析缓存仅限单次批量核验。现有年表全量与请求窗口裁剪分别保留，原表 latest_reported_periods 不当作该窗口外的新输入。

## 未完成

本批合并回归实际终态及运行后输入核验已完成，尚未提交。正式发布证据、真实来源审查包、Worker/定向刷新官方路由、实际候选认证、120日重放、真实合格AI及切换均未完成。最近默认全套结果和SQLite未定位锁故障保持原记录，不由本批专项覆盖。
