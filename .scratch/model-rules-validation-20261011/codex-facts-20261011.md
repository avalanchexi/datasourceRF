# 模型规则访谈取证（2026-10-11，Codex 只读，允许读 src/）

1. **A4：生产没有独立的“位置与斜率冲突”标记，现有字段是 `reason`。** 历史达到 140 点、但尚未确认任何稳定方向时，趋势函数返回 `transition_pending`；首次确认后改为 `stable`，投影通常显示 `validated`，已有稳定方向后的冲突只清空候选、保留稳定方向，不重新置位。历史不足或数据失效则由相应原因码替代，因此现行语义与校准票描述有差异。证据：[trend.py:110](../../src/pring_cycle/domain/trend.py:110)、[trend.py:136](../../src/pring_cycle/domain/trend.py:136)、[day_summary.py:453](../../src/pring_cycle/day_summary.py:453)。

2. **A5：沿用日插入临时前收盘点，正常参与全部计算，也可能推进候选或完成确认。** 该日收益为零，MA120、20 日均线斜率和 `1.5×σ20` 均包含这个新增点重新计算；生产实际读取选中的收盘价、按相邻点比值算收益，并未在这条路径重建文档所说的官方收益链。临时点不入库，恢复后用真实序列从头计算：缺日补齐就自然接回，缺日仍在窗口内部则报 `window_session_missing`，不会永久沿用。证据：[day_summary.py:432](../../src/pring_cycle/day_summary.py:432)、[trend.py:95](../../src/pring_cycle/domain/trend.py:95)、[day_summary.py:486](../../src/pring_cycle/day_summary.py:486)。

3. **A6：`candidate_30d` 是即时方向，没有持续确认。** 公式为“当日价格严格高于 MA30，且 MA30 严格高于昨日 MA30”则牛，两个条件反向则熊，否则为空；使用相邻两组 30 点均值，需要至少 31 点，没有噪声阈值、滞回或持续天数。外层函数却先要求完整的 140 点历史，因此生产并不会在第 31 点就输出该字段。证据：[trend.py:210](../../src/pring_cycle/domain/trend.py:210)、[trend.py:75](../../src/pring_cycle/domain/trend.py:75)。

4. **A7：历史不足时返回 `insufficient_history`，稳定方向、候选、30 日方向及测量值全部为空。** 首个可测量日是第 140 个输入点，最早第 147 点才能完成连续 8 日确认；若总共只取得 160 点、展示末尾 120 日，则分别落在窗口第 100、107 日。将此列为未决的是 [architecture-review spec:425](../../.scratch/architecture-review-20260929/spec.md:425)；生产门槛见 [trend.py:75](../../src/pring_cycle/domain/trend.py:75)。

5. **商品篮子广度：取目标日及此前 120 个交易日的 121 日跨度，累计后 120 日贡献。** 起始锚点当天的贡献排除，因此展示窗口首日的贡献仍计入；各分项贡献直接求和，篮子整体则按每日分项贡献合计复利计算。持平单列 `flat`：分项贡献和容差为 `1e-12` 个百分点，篮子以初值 1 比较的容差为 `1e-9`，持平不会归为上涨或下跌。证据：[price_consistency.py:344](../../src/pring_cycle/price_consistency.py:344)、[price_consistency.py:539](../../src/pring_cycle/price_consistency.py:539)、[price_consistency.py:660](../../src/pring_cycle/price_consistency.py:660)。

6. **典型组合真实样本：**

   **(a) 规范声明各有 120 个日期；把留存原件也算上，各可读出 166 个日期。** SQL 对 `source_claim` 按指标统计 `MIN/MAX(period_end)、COUNT(*)、COUNT(DISTINCT period_end)`，结果如下；留存 TuShare 回执关联原件合并去重后，三者均覆盖 **2026-01-28～2026-10-09，共 166 点**，不能将原件历史等同于仍在库的规范声明。

   | 核心 | 规范声明日期范围 | 日期数 | 声明行数（含多版本） |
   |---|---|---:|---:|
   | 债券 000012.SH | 2026-04-13～2026-10-09 | 120 | 3,267 |
   | 股票 000985.CSI | 同上 | 120 | 3,267 |
   | 商品 NHII.NH | 同上 | 120 | 3,037 |

   **(b) 实算没有典型组合日。** 按生效模型 v0015 参数，对上述 166 点按生产公式在内存粗算：债牛、股熊于 **09-04** 首次确认，商品牛于 **09-10** 首次确认，此后至 **10-09 共 16 个交易日**全部为非典型的“债牛、股熊、商品牛”；原件重叠价格无差异，`pre_close` 无断点。另查 `analytical_dataset`：全部 **141 个 `cycle_overview` 的 `current_stage` 均为 NULL**；这是实算与 SQL 结果，未运行测试或生产流程。

   **(c) 可以指定 2024 年目标日发起计算，但不支持严格的历史点时回放。** 入口接受目标日，核心接口按起止日期请求 `index_daily`／`fut_index_daily`，正常流程取末尾 160 点、补算 120 日窗口，仍受首部历史不足及上游历史覆盖、权限和完整性交付约束；本次未联网验证 2024 数据可得性。宏观公开时间依发布规则推算、修订取最新，选值受目标日限制而时效按本次运行截止点判断，明细与汇总又按 120 日留存，因此不能保证复现当年的信息集或页面。证据：[cli.py:313](../../src/pring_cycle/cli.py:313)、[source_adapters.py:194](../../src/pring_cycle/source_adapters.py:194)、[worker.py:2092](../../src/pring_cycle/worker.py:2092)、[ADR-0021:7](../../docs/adr/0021-registered-sources-freshness-replaces-certification.md:7)、[ADR-0022:7](../../docs/adr/0022-uniform-120-day-retention-and-processing-batches.md:7)、[CONTEXT.md:254](../../CONTEXT.md:254)。

   **(d) 有构造数据下的典型 Stage III 链路覆盖。** 测试从三核心价格经单日汇总确认 Stage III，检查 PMI 支持及计数，再检查页面、报告输入和报告落库／篡改拒绝；这是多个用例共同覆盖，不是六阶段真实行情的全链路验证，本次只读未执行。证据：[test_confirmation_publish.py:92](../../tests/integration/test_confirmation_publish.py:92)、[同文件:177](../../tests/integration/test_confirmation_publish.py:177)、[同文件:239](../../tests/integration/test_confirmation_publish.py:239)、[同文件:478](../../tests/integration/test_confirmation_publish.py:478)。

7. **库存三条线的主成员分别是 PMI 新订单、工业增加值当月实际同比、产成品存货名义同比，均按主成员动量确定方向。** 辅助成员分别为工业企业营收累计同比、PMI 生产，以及 PMI 产成品库存／产成品周转天数同比变化；三线联合得到象限，象限整体只计一项，按阶段预期及宽限确定关系，分化封顶为仅观察，无正式阶段则不适用。体检已核成员展开、主成员标注和计数，但尚未独立核验库存各线主辅方向比较与分化识别，只依据生产的 `opposes` 标注纳入封顶检查，而现有真实样本尚未触发适用时的封顶。证据：[confirmation.py:3123](../../src/pring_cycle/confirmation.py:3123)、[confirmation.py:3190](../../src/pring_cycle/confirmation.py:3190)、[confirmation.py:1154](../../src/pring_cycle/confirmation.py:1154)、[体检文档:288](../../docs/development/data-quality-audit.md:288)、[票12:84](../../.scratch/data-quality-audit-20261010/issues/12-layer3-rules-not-covered.md:84)。

取证完成
