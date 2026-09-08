# 三核心消费时的原件核验

2026-09-09，基点 `dd744ff`。票 19/21 的软件切片；不构成实际来源认证、完整新候选、真实 120 日回放或切换。

## 已复现及修复

- [选值 RED](verification-core-original-red-01.txt)：真实隔离采集与入库后，改写或删除股票原始响应，`ModelInputSelector.select` 仍称输入完整。现在每次 select 都重新核验关联 raw；同一 selector 再评价也不能复用上次成功。恢复原件后重新通过；TuShare 的未知 PUBLIC 仍保持未知。
- [PUBLIC RED](verification-core-original-replay-red-02.txt)：已合法入库的原件损坏或丢失后，公开 `evaluate_history` 仍成功。现在新目录在每天采用声明前检查精确 provider/API/code/日期/单位、raw 哈希、回执解析及原行 close，失败报 `calibration_core_original_invalid`；后续修订尚不可见时，损坏的修订原件不妨碍较早窗口，到了其可见日则拒收，不回退旧版本。
- [读取次数 RED](verification-core-original-reads-red-01.txt)：最初正确性修复会将同一覆盖 149 日的原件读取 149 次。证据仓库增加批量 exact claim→receipt 读取，每份物理 acquisition 在本批核哈希一次；核心校验按 metric/acquisition 缓存原行索引，逐选中声明核日期和值。缓存不跨独立评价。
- Worker 已接同一核心校验器，核完整计算历史而非仅显示的最后 120 条；原件失败给 `source_original_invalid`，不形成核心状态或模型输入 ID。

新要求仅适用于新登记目录，保留内置旧目录各自的既有行为与 v3 否定守卫。多份原件关联时必须全部有效，不能以一份好原件掩盖坏关联。批量预读可遇到未选中的后续版本，其坏原件只在该版本实际 selected 时拒收。批量读取只持有本次评价的快照，不承诺评价过程中磁盘任意时刻的变化都即时生效。

本批核验 raw 并重新解析出原行；没有新增 normalized 制品的消费时完整性核验，不能据此声称 raw→normalized 全链全部重验。旧声明、认证、PUBLIC/SYSTEM 时间与保存结果均不修改。

## 验证与边界

目前 [8 项公开入口用例通过](verification-core-original-green-04.txt)。最终 PUBLIC fixture 为 168 个合成工作日、504 条基础声明（跨 500 个 SQL 参数批界），加后续修订或第二份原件。真实 parser、仓库与评价器运行，外部 transport/时钟及文件损坏为隔离 fixture。透明文件读取计数证明各物理 raw 一次，全部关联有效性、旧修订可见性、同对象重评和恢复均覆盖。

首次 PUBLIC fixture 仅 147 日，倒数第二天尚差一个持续日而无稳定状态；该设置错误保留在 `verification-core-original-replay-red-01.txt`，修正为 149 日后才取得真正未拒收 RED。扩充双原件用例时首次 fetched_at 未取最新回执，入库守卫正确拒绝；保留 `verification-core-original-green-03.txt`，修正 fixture 后 8 项通过。首次 Ruff 一处长行和 mypy 两处 lambda 类型问题也保留原日志，继续最终检查。

[最终关联回归](verification-core-original-associated-02.txt) **328 项通过，530.37 秒**，覆盖全部 models、evidence、趋势、Worker、核心采集和检索输入，包含上述 8 项在类型注解修正后的最终代码。mypy 87 文件、Ruff/格式 6 文件、86 安装 Python 源文件匹配；[双轴审查](verification-core-original/review.md)各 0 项。第一次关联启动在 WSL 初始化阶段以 `0x8007274c` 失败，未进入 pytest，原日志保留；新编号运行完整通过。最终来源/结果绑定见[检查点](verification-core-original/checkpoint.json)。本批未执行项目全部测试，整体最终门仍开放。

新目录 active Worker 完整纵向尚未单独验证，现有 Worker 回归只能证明已覆盖的兼容路径；不绕过 active 或认证门制造正例。

## 仍未完成

逐日候选字段与持续天数的历史输出验收仍缺；[下一切片研究](core-candidate-replay-boundary.md)已根核 14 输入/38 链接（票21本批追加评论前），仅为静态方案，未执行反例。固定 2026-03-09 至 2026-08-28 的真实 120 中国交易日、完整新候选、来源正式认证、合格 AI 报告及真实切换仍未完成。北交所、CNY030、估值、股票池/复权/完整金额、商品和其他 P1/P2 原依赖不变。相关任务继续开放。
