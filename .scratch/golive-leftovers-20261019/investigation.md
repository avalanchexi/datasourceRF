调查完成。**主要根因是 CLI 大输入发送缺陷、贷款回看计划未随新期更新、指数校验范围不一致，以及 GDP 官方表型不兼容。** GDP 可比性守卫确实阻止了信用脉冲，但已保存的官方原件提供了恢复核验所需的数据。

代码核对为 `main 2502ae4`。数据库及上线前备份均以 `file:...?mode=ro` 打开；未修改文件、未调用外部接口、未启动 Worker。以下时间统一为北京时间，长 claim ID 使用唯一前缀。

**1．AI 报告：输入增长触发了可复现的 stdin 发送缺陷**

`report_attempt` 的证据如下：

| 行 | 目标日／提示词 | 执行时间（2026-10-19） | 结果 |
|---|---|---|---|
| `attempt_id=38`，Codex | 10-16／v0005 | 16:28:03.948—16:29:00.508 | 成功，56.560 秒 |
| `attempt_id=39`，Codex | 10-19／v0010 | 19:14:59.918—19:20:00.051 | 超时，300.132 秒 |
| `attempt_id=40`，Claude Code | 10-19／v0010 | 19:20:00.059—19:25:00.611 | 超时，300.552 秒 |

两次 Codex 均为 `0.162.1`；Claude Code 为 `2.1.300`。失败的两行均为：

- `process_phase=generation`，版本探测成功。
- `stdout_bytes=0`、`stderr_bytes=0`、`cli_notices=[]`、`tool_events=0`。
- Codex 没有生成输出文件；终止后退出码为 0，Claude 为 143。**Codex 的退出码 0 不代表生成成功**：超时分类优先于退出码，见 [cli_process.py:228](/mnt/d/cursor/datasourceRF/src/pring_cycle/cli_process.py:228)。

提示词版本不是依次经历 v0008、v0009：

| 提交 | 改动 |
|---|---|
| `b99d539`，10-07 | 引入确认度报告契约 v0005 |
| `325a9f9`，10-15 | 新增非典型组合事实与观察句契约 v0006 |
| `569ffab`，10-16 | 统一资产状态术语，非典型契约 v0006→v0007 |
| `56e5f59`，10-17 | 加入中文名称映射：普通契约→v0008、确认度→v0009、非典型→v0010 |
| `a18e1cf`，10-18 | 固定事实句改用“第三阶段”等中文名称，继续使用尚未发布的 v0010 |

契约选择见 [reports.py:529](/mnt/d/cursor/datasourceRF/src/pring_cycle/reports.py:529)，新增约束见 [reports.py:1156](/mnt/d/cursor/datasourceRF/src/pring_cycle/reports.py:1156)。

从 `evidence_bundle.document_json` 和 `process_audit_json` 实测 UTF-8 字节数：

| 内容 | 10-16 报告 | 10-19 报告 |
|---|---:|---:|
| 存储 bundle | 62,145 | 92,830 |
| 实际 `report_input`，去掉 `gap_list` | 60,950 | 88,650 |
| 完整提示词 | 61,913 | 91,805 |
| 其中注册仓单内容 | 3,003 | 29,378 |

完整提示词增长 **29,892 字节，48.28%**。主要增量来自仓单，而非中文提示语：提交 `7d012bc` 新增仓单首末日 claim ID，新 bundle 带入 **389 个 ID**。生成代码见 [registered_warrants.py:211](/mnt/d/cursor/datasourceRF/src/pring_cycle/registered_warrants.py:211)；报告只删除顶层 `observation_version_ids`，没有删除嵌套 ID，见 [reports.py:458](/mnt/d/cursor/datasourceRF/src/pring_cycle/reports.py:458)。

**关键机制已用正式 Python 3.12.12、本地假子进程复现：**

[cli_process.py:274](/mnt/d/cursor/datasourceRF/src/pring_cycle/cli_process.py:274) 首次调用 `communicate(prompt, timeout=0.5)`；超时后改为 `communicate(None, …)`。该 Python 实现只有传入非空 `input` 时才注册 stdin 写事件。若首个 0.5 秒未送完，剩余输入不再续写，stdin 也无法正常结束。

让本地子进程启动后等待 0.75 秒再读 stdin，结果为：

| 输入大小 | 管道容量 | 实际发送 | 结果 |
|---|---:|---:|---|
| 61,913 字节 | 65,536 | 61,913 | 正常完成 |
| 91,805 字节 | 65,536 | 65,536 | 空 stdout/stderr，超时 |
| 91,805 字节，单次 `communicate` 对照 | 65,536 | 全部 | 正常完成 |

因此，**首要根因判断是输入膨胀跨过管道容量，触发应用层 I/O 缺陷**；不是仅凭提示词变复杂推断模型变慢。历史审计没有记录已发送字节数或进程栈，无法直接证明当时恰好停在 65,536 字节，但复现与两个 CLI 的共同症状高度吻合，目前没有认证、限流或服务端异常证据。

300 秒默认值定义于 [reports.py:1137](/mnt/d/cursor/datasourceRF/src/pring_cycle/reports.py:1137)，版本探测也占用该截止预算。建议修复持续写入和 EOF 管理，例如由单独 I/O 线程执行一次 `communicate`，主线程负责取消／截止；同时采用报告输入字段白名单，剔除嵌套溯源 ID。单纯延长超时无法解决此阻塞。

**补生成命令建议，仅建议、未执行：**

```bash
~/.local/share/pring-cycle/dev-venv/bin/pring-cycle report-generate \
  --request-id repair-report-20261019-stdin-01 \
  --json
```

应先修复并安装上述缺陷。命令读取**当前投影**，没有指定目标日或旧报告 ID 的参数；调查时 `current_projection` 正是 `projection-554b0640f5f9d167fb6a`，目标日 10-19。执行时仍须满足这个条件。新 request ID 会追加报告版本，重复 ID 返回已有结果；见 [cli.py:396](/mnt/d/cursor/datasourceRF/src/pring_cycle/cli.py:396)、[reports.py:1022](/mnt/d/cursor/datasourceRF/src/pring_cycle/reports.py:1022)。不要加 `--deterministic-only`，否则不会调用 AI。

**2．贷款 2025-09：新一期到货后，没有追加其同比回看需求**

公式明确读取 `t、t−1、t−12、t−13`，见 [confirmation.py:177](/mnt/d/cursor/datasourceRF/src/pring_cycle/confirmation.py:177)及 [lookback.py:338](/mnt/d/cursor/datasourceRF/src/pring_cycle/lookback.py:338)，符合 ADR-0035 的最长 13 个月回看。

`full_run_gap_plan` 保存了完整转折：

| 运行／计划 | 最新读数 t | 四期需求 |
|---|---|---|
| 10-16：initial、final | 2026-08 | 2026-08、2026-07、2025-08、2025-07；各有 9 个成员 |
| 10-19：initial，19:05:50.595 | 2026-08 | 同上，全部齐全 |
| 10-19：final，截止 19:11:32.136 | 2026-09 | 2026-09、2026-08、**2025-09**、2025-08；2025-09 缺 9 个成员 |

本次 `acquisition-27dfed7b742a480d9dd8cb7dc1662d85` 于 **19:10:47.578** 取得并入库 2026-09 的九个成员，来源是央行 10-14 金融统计报告。例如 `source_claim=23d4c86e0cb4…`，企业中长期累计增量 65,300 亿元。

代码只遍历初始 `scopes`，见 [full_retrieval.py:103](/mnt/d/cursor/datasourceRF/src/pring_cycle/full_retrieval.py:103)。取数结束、截止冻结后，`evaluate()` 才重新生成计划，见 [full_retrieval.py:835](/mnt/d/cursor/datasourceRF/src/pring_cycle/full_retrieval.py:835)；这时只记录新缺口，没有再取数。因此 2025-09 从未进入本次执行队列。

**是否被清理：未找到“曾入库后被删”的证据。**

- 正式库和 **18:55 上线前备份**中，该期 `source_claim` 均为 0。
- 保存的 `acquisition_request` 中，`family=pbc_loan_structure, period=2025-09` 为 0。
- 检查 43 份相关规范化制品，没有该期贷款标量。
- 更早的 2025-07、2025-08 各九条仍保留。投影引用的非核心声明受留存保护，见 [retention.py:190](/mnt/d/cursor/datasourceRF/src/pring_cycle/retention.py:190)。

这些证据支持“未补取”，不能将无限历史中是否删除过绝对证明为否；现有库也没有该期逐行删除审计。

10-16 没有这个缺口，是因为当时仍读 2026-08。`run_retrieval_attempt.id=14728` 在 **16:23:28.575** 把 2026-09 记为 `release_gate / not_attempted / awaiting_release`。新安装代码的 `bc969fa` 才允许在估计尚未发布时探测官方栏目，见 [full_retrieval.py:200](/mnt/d/cursor/datasourceRF/src/pring_cycle/full_retrieval.py:200)。所以旧运行的“无缺口”不代表它拥有 2025-09。

建议：发现最新期推进后，重新展开依赖并补取新增基期，直到无新增需求或预算耗尽；再冻结截止。修复后补齐 2025-09 九个成员，不应扩大长期留存范围。

**3．信用脉冲：Q3 新闻值与旧 GDP 累计序列缺少已认可的可比性证明**

两个投影的 `analytical_dataset(dataset_name='macro')`，`credit.formula` 均明确记录：

```text
status = incomparable_gdp_vintages
failures.periods = ["2026-Q3"]
member = total / nominal_ytd_level
```

判定链见 [credit_impulse.py:424](/mnt/d/cursor/datasourceRF/src/pring_cycle/credit_impulse.py:424)：

1. 累计值差分后，先找同一 TuShare 交付是否同时给出所选基期和本期数值。
2. 没有同批证明，再检查所选声明的官方原件是否明确给出相同的当季名义值。
3. 两条路径都不成立，记 `incomparable_gdp_vintages`。

同批判断按 `acquisition_id` 与数值相等执行，且当前限定 `provider="tushare"`，见 [credit_impulse.py:699](/mnt/d/cursor/datasourceRF/src/pring_cycle/credit_impulse.py:699)、[evidence.py:394](/mnt/d/cursor/datasourceRF/src/pring_cycle/evidence.py:394)。因此现行实现并非只有“必须同一次交付”一条路，还允许官方当季数值核验。

库中 Q3 总量来源：

| `source_claim` 前缀 | 入库时间 | 来源／值 |
|---|---|---|
| `d534672114acf4ff…` | 16:17:38.796 | TuShare `major_news`，1,071,071 亿元；10-16 运行选中 |
| `70068402087bc9e3…` | 19:06:22.957 | TuShare `major_news`，同值；10-19 运行选中 |
| `bddf8386803bea5e…` | 19:11:31.109 | 财联社页面，同值 |

对应新闻回执为 `acquisition-97927d7b…`、`acquisition-e83784ec…`；财联社为 `acquisition-4ac32cb7…`。

结构化 `cn_gdp` 回执 `acquisition-fce362b29680434ca9bae55738a7047a` 于 **19:03:49.779** 返回的最新期仍为 **2026Q2**，虽然请求覆盖 2025Q1—2026Q4。19:11:22 的 Q3 单期回执 `acquisition-998ed316…` 返回空集。因此 Q3 与此前三季并非同一交付；新闻源 `tushare_news` 也不等于结构化源 `tushare`。

目标日 10-16 的运行实际在 10-19 下午执行，冻结截止为 **16:23:57.216**，所以会读入当天取得的 Q3 信息；这是现有目标日截止规则的行为，见 [summary_cutoff.py:63](/mnt/d/cursor/datasourceRF/src/pring_cycle/summary_cutoff.py:63)。

**恢复条件和建议：**

- 不改代码时，等待 `cn_gdp` 的一次完整交付包含 Q3 及必要基期，且与所选值一致；不能承诺具体恢复日期。
- 修复第 5 项后，可以走现有“官方当季值核验”路径。已保存官方原件给出 **375,367**，恰好等于 `1,071,071 − 695,704`。当前数据没有表现出这个差分的数值冲突，阻塞点是可比性证明未被解析、采纳。
- 官方修订批次整体重取值得支持，但应保存并选择一致的修订批次；不能把分别重取的独立发布页仅因“同一次运行抓取”就当成同一版本。若扩展官方批次支持，应保留这条约束，而非取消守卫。

**4．两只债券：不是价格数值不同，而是“六只输入对一只输出”**

校验比较的是完整 `ContextScalar` 集合：原件重解析结果与待入库输出，剔除发布时刻、定义版本、回执 ID 后，排序比较 JSON。见 [tushare_context.py:279](/mnt/d/cursor/datasourceRF/src/pring_cycle/tushare_context.py:279)。

定向补取仍调用返回六只指数的 `market_indices()`，见 [tushare_context.py:851](/mnt/d/cursor/datasourceRF/src/pring_cycle/tushare_context.py:851)；但 `_scoped()` 在校验前把输出裁成目标指标，见 [targeted_context.py:224](/mnt/d/cursor/datasourceRF/src/pring_cycle/targeted_context.py:224)、[targeted_context.py:280](/mnt/d/cursor/datasourceRF/src/pring_cycle/targeted_context.py:280)。

保存的原件重建出的六只指数，10-19 值为：

| 指数 | 原件解析侧 | 补 930916 时输出侧 | 补 CNY030 时输出侧 |
|---|---:|---:|---:|
| 000300.SH | 4,174.5349 | 无 | 无 |
| 000905.SH | 6,800.6594 | 无 | 无 |
| 000852.SH | 6,698.3026 | 无 | 无 |
| 000012CNY030.CSI | **111.6248** | 无 | **111.6248** |
| 930916.CSI | **185.8319** | **185.8319** | 无 |
| NHCI.NH | 2,949.2 | 无 | 无 |

所以目标债券两侧数值相同。原件侧作为整批交付正确，输出侧作为定向范围也正确，错误在于要求这两个不同范围的集合相等。

`full_run_acquisition` 联接 `acquisition_request` 显示：

- 补 `CN_BOND_10Y_930916`：**19:07:18.325—19:07:29.752**，整组六张回执失败。
- 补 `CN_BOND_FULL_PRICE_CNY030`：**19:10:50.140—19:11:02.668**，整组六张回执失败。

**“各 6 次”是各自补取批次包含六只指数，不是各只债券重复发生六次价格冲突。**

明确保存目标值的回执包括 `acquisition-6a8662134c2648af9029b1055baa535d`（111.6248）和 `acquisition-28bd3a600cc546db85d2d0cd760e63c7`（185.8319）。

更早 18:59 的直接刷新成功，但原件最新只有 10-16：CNY030 为 111.6455，930916 为 185.9087；所以没有提供 10-19 声明。这两项仍沿用上期输入。

建议让请求、重解析校验和入库输出采用同一范围，最好直接按所需指数发请求；保留严格数值校验，不放宽容差。本次仅核验保存的来源应答，没有外部交叉认证价格。

**5．GDP 三产业同比：遇到的是另一种官方表型，不能简单称为专表改版**

失败回执：

```text
acquisition-b25d9d8b47a34905ac9b2a08c6406e98
发起：2026-10-19 19:11:26.578
收到：2026-10-19 19:11:30.819
rejection_reason：official_context_table_schema_mismatch
raw_hash：8818987a1874e4a9c31d95a3d6e604be6aba23c45a89b23e6ae89d7abdbbcffc
```

保存页面标题是《前三季度经济运行总体平稳　高质量发展取得新成效》，地址为国家统计局 `/sj/zxfbhjd/202610/t20261019_1965618.html`。它的附表是“2026年9月份及前三季度主要指标数据”，不是解析器预设的 GDP 初步核算专表。

| 项目 | 代码预设 | 实际综合发布表 |
|---|---|---|
| 总量行名 | `GDP` | `一、国内生产总值（亿元）` |
| 表头 | 绝对额／同比，再分当季与累计 | 9月／1—9月，各分绝对量与同比 |
| 数值列序 | 当季额、累计额、当季同比、累计同比 | 当季额、当季同比、累计额、累计同比 |
| 当季单元格 | 纯数字 | 数字后带 `（三季度）` |

实际四行：

| 成员 | 当季名义额 | 当季实际同比 | 累计名义额 | 累计实际同比 |
|---|---:|---:|---:|---:|
| GDP 总量 | 375,367 | 4.5% | 1,071,071 | 4.6% |
| 第一产业 | 27,472 | **3.6%** | 58,994 | 3.7% |
| 第二产业 | 133,349 | **3.4%** | 383,822 | 3.8% |
| 第三产业 | 214,546 | **5.2%** | 628,255 | 5.2% |

[official_context.py:1830](/mnt/d/cursor/datasourceRF/src/pring_cycle/official_context.py:1830) 要求表的首列同时包含 `GDP／第一产业／第二产业／第三产业`，实际没有精确的 `GDP` 行名，于 [official_context.py:3052](/mnt/d/cursor/datasourceRF/src/pring_cycle/official_context.py:3052) 抛出当前错误。

即使只修行名，固定列序仍会读错；表头校验也会失败，见 [official_context.py:1785](/mnt/d/cursor/datasourceRF/src/pring_cycle/official_context.py:1785)。例如总量行会把 4.5 当累计额、把 1,071,071 当当季同比。

建议增加综合发布表的独立契约，识别期次、列序和单元格季度标注，再统一输出规范化 GDP 行；让解析、来源校验和 [官方当季名义值核验](/mnt/d/cursor/datasourceRF/src/pring_cycle/official_context.py:477) 共用该结果。不能用正文里的累计产业增速替代当季同比。

**建议开票清单**

| 一句话标题 | 优先级 | 是否影响模型输入 |
|---|---|---|
| 修复 CLI 大提示词在首次轮询超时后停止续写 stdin，并记录已发送字节数。 | P1 | 否，影响 AI 报告生成 |
| 对报告输入实行字段白名单，剔除仓单嵌套溯源 ID。 | P2 | 否，影响 AI 输入体积 |
| 最新期发现后重新展开并执行公式回看，补齐贷款 2025-09 九个成员。 | P1 | 是，贷款同比读数 |
| 统一定向市场指数请求、原件校验与入库输出范围。 | P1 | 是，两项辅助债券指标 |
| 支持官方 GDP 综合发布表，并共用当季同比解析与名义差分核验。 | P1 | 是，GDP 三产业及信用脉冲 |
| 为 GDP 修订提供可追溯的整批重取和一致版本选择，明确信用脉冲恢复条件。 | P2 | 是，信用脉冲 |
