# 183 全套期间的后续实施边界复核

2026-09-11。183 默认全套尚在执行，本轮没有修改其冻结的生产源码、测试或原件，也没有另启测试。以下是只读复核及输入准备，不是 Worker、信用脉冲或真实模型验收。

## Worker 注册目录

当前 `worker.py:838` 官方刷新后认证查询与 `worker.py:1506` TuShare 异常优先级查询仍缺少 `database_path`。注册目录只能从数据库解析，这两条路径的问题仍存在。

旧研究的部分前置已经过时：GDP 的 8 字段合同、官方原件消费已实现；Treasury 合同也已实现。当前 `ContextReplayScope` 区分必需与可选公式，`test_registered_candidate_allows_uncertified_optional_p2_at_replay_preflight` 明确保持 61 指标、42 P1、8 公式，并允许无认证的可选 UST。因此不能再用“UST 必须全部先认证”阻挡 P1 验收。

[实际分派核对](worker-current-contract-boundary-184.json)仍发现 15 项 P1 没有注册来源分派：3 个股票确认指数、5 个广度指标、融资、估值、CNY030、930916、NHCI、商品篮子及袖套。它们恰属原规格的五个市场家族。存在分派只代表软件支持，尚不代表取得真实来源认证。

## 原校准价格已找回

[恢复收据](worker-calibration-input-recovery-184/receipt.json)核实旧数据库中原 `model-v0001` 验收 hash 与历史记录一致；找到两份原规范化价格制品并核对完整 SHA-256。三核心各 2,345 个共同日期，2017-01-03—2026-08-28；截至 2026-08-19 的输入 2,338 日，其中 2018-06-01 起评估 1,995 日。7,035 个日价格与旧声明逐项一致，没有发现同日不同价格。

[价格输入](worker-calibration-input-recovery-184/price-history.json)只提取日期、价格、代码及单位。没有把旧 PUBLIC 和 certified 标记转换为新认证。旧 v1 核心声明没有 acquisition 关联，这两份制品也是规范化历史，不是接口原始收据；共同日期不替代独立交易日历。旧运行库注册目录数为 0，现存 active 仍是旧模型。

这解除了“长期校准价格找不到”的前置问题。后续隔离 Worker 正例仍必须通过真实公开导入、机器校准、固定 120 日回放和激活，测试发布时间证据明确标为 synthetic；不得复制旧 active 状态或使用历史通过数字替代重新计算。

## 信用脉冲

`_credit_impulse_proxy` 仍先过滤认证点再取末尾窗口，所选全窗父项没有走官方原件核验；GDP YTD 转季度仍只检同年相邻与正差分。修复必须同时处理坏父项、不回退较旧窗口及修订基线，不能只修最新卡片。

[完整原件清单](credit-window-inputs-186/manifest.json)已准备 25 个社融 YTD 与 9 个 GDP YTD 父项，并重新逐件核哈希。独立读取 GDP HTML 单元格再次验证：2024 Q4 跨发布差分比本公告季度值多 25,612 亿元；2025 Q4 少 1,068 亿元。完整原件并不保证跨发布差分可比。

[首个公开反例补丁](credit-window-first-public-test-186.patch)已准备，尚未应用或运行。它经完整 synthetic 审查目录与 34 份真实原件导入，分别检查 PUBLIC/SYSTEM 不应产生合格信用脉冲结论。先等待 183 实际终态，再应用、取得真实 RED，最后做生产修复。当前不能称这个反例已复现或修复。
