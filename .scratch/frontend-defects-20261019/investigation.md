核对版本为 `2502ae4`；正式库当前指针确为 `projection-554b0640f5f9d167fb6a`，关联运行 `run-153de3060fa2b0ebc424`、模型 `model-v0015`。数据库均以 `file:...?mode=ro` 打开，未修改文件、未运行测试。当前沙箱连接 `127.0.0.1:8069` 失败，以下依据代码与正式库，不包含在线渲染验证。

**1. 同类观察：“方向”是较上一可用期，和“近 5 日”口径不同，应改标签。**

页面“方向”直接读取 `evidence.direction`，没有按五日变化重算或反转箭头：[cockpit.py:1899](/mnt/d/cursor/datasourceRF/src/pring_cycle/cockpit.py:1899)、[cockpit.py:2525](/mnt/d/cursor/datasourceRF/src/pring_cycle/cockpit.py:2525)。

后端取同指标、同维度的最新点 `points[-1]` 与上一点 `points[-2]` 比较；差值大于 `max(abs(previous)*1e-9, 1e-12)` 为 `up`，反向为 `down`，容差内为 `flat`。**不是五日趋势，也不保证上一可用期就是上一交易日。** 依据：[context_projection.py:2935](/mnt/d/cursor/datasourceRF/src/pring_cycle/context_projection.py:2935)、[context_projection.py:3173](/mnt/d/cursor/datasourceRF/src/pring_cycle/context_projection.py:3173)。

“近 5 日”以最新有效观测日为终点，回溯五个交易日，需要含端点的六个交易日观测。一般数值计算收益率；百分比、百分点计算差值并转为基点；家数在页面转换为端点家数之差。依据：[display_projection.py:239](/mnt/d/cursor/datasourceRF/src/pring_cycle/display_projection.py:239)、[cockpit.py:291](/mnt/d/cursor/datasourceRF/src/pring_cycle/cockpit.py:291)。

库中三个直接例子：

- 上涨家数：10-12 为 **1,166**，10-16 为 **3,301**，10-19 为 **2,274**。五日 `2274−1166=+1108`；方向比较 `2274−3301=−1027`，故下降。
- 下跌家数：依次 **4,325、2,127、3,129**。五日 `3129−4325=−1196`；方向比较 `3129−2127=+1002`，故上升。
- 铜贡献：依次 **0.14110635、−0.03644647、0.04872849 百分点**。五日 `(0.04872849−0.14110635)×100=−9.23778558 基点`；较上一期增加，故上升。这里比较的是每日贡献值，并非五日累计贡献。

逐一关联 `selected_claim_id`、`direction_input_observation_version_ids`、`display.change_5.input_claim_ids` 到 `source_claim` 复算，**40 行方向与后端五日数值全部符合代码**。不能据此证明外部源数据本身绝无错误，但这批“相反符号”由不同比较周期完整解释，不是箭头显示反了。建议列名改为 **“较上期方向”**，并展示比较日期。

全部相反行如下，**共 18 行：债券 0/2、股票 13/27、商品 5/11**。这些行五日窗口均为 **2026-10-12 → 2026-10-19**，方向比较均为 **10-16 → 10-19**。

库中定位：`analytical_dataset` 指定投影的 `dataset_name='macro'`，路径 `observation_interfaces.cores[].members[].evidence[]`。表中前三个数值为投影引用的 `source_claim.value`，末两列按上述页面代码口径列出。

| 行 | 10-12 | 10-16 | 10-19 | 近 5 日 | 方向 |
|---|---:|---:|---:|---:|---|
| 沪深300 | 4287.9798 | 4170.6131 | 4174.5349 | −2.65% | ↑ |
| 中证500 | 7093.0205 | 6772.7532 | 6800.6594 | −4.12% | ↑ |
| 中证1000 | 7021.4723 | 6681.9444 | 6698.3026 | −4.60% | ↑ |
| 上涨家数 | 1166 | 3301 | 2274 | +1108 家 | ↓ |
| 下跌家数 | 4325 | 2127 | 3129 | −1196 家 | ↑ |
| 净上涨家数 | −3159 | 1174 | −855 | +2304 家 | ↓ |
| 参与交易家数 | 5560 | 5566 | 5563 | +3 家 | ↓ |
| 涨跌家数比 | 0.269595 | 1.551951 | 0.726750 | +169.57% | ↓ |
| 上涨成交额占比（%） | 28.192237 | 49.349248 | 46.781231 | +1858.90 基点 | ↓ |
| 沪深300 市净率 | 1.3948 | 1.3779 | 1.3849 | −0.71% | ↑ |
| 沪深300 市盈率 | 14.2599 | 14.0714 | 14.1421 | −0.83% | ↑ |
| 中证500 市净率 | 2.2190 | 2.1261 | 2.1433 | −3.41% | ↑ |
| 中证500 市盈率 | 35.2908 | 33.8067 | 34.1384 | −3.27% | ↑ |
| 南华综合指数 | 2997.00 | 2940.03 | 2949.20 | −1.59% | ↑ |
| 铜贡献（百分点） | 0.141106 | −0.036446 | 0.048728 | −9.24 基点 | ↑ |
| 原油贡献（百分点） | −0.294078 | −0.060673 | −0.116183 | +17.79 基点 | ↓ |
| 聚丙烯贡献（百分点） | 0.204678 | −0.114494 | 0.056430 | −14.82 基点 | ↑ |
| 纸浆贡献（百分点） | −0.185497 | 0.040317 | −0.091875 | +9.36 基点 | ↓ |

定位这些成员的字段为：指数 `CN_EQ_CSI300/500/1000`；家数 `CN_EQ_ADV_DEC.measure=advances/declines/net/participants`；比值 `CN_EQ_AD_RATIO`；成交额占比 `CN_EQ_ADV_AMOUNT_SHARE`；估值 `CN_INDEX_VALUATION` 的 `index` 和 `measure=price_book/price_earnings`；南华 `CN_COMMODITY_BROAD_NHCI`；贡献 `CN_COMMODITY_SLEEVE_CONTRIBUTION.sleeve=copper/crude_oil/polypropylene/pulp`。

特别注意：**净上涨家数必须按页面差值判断**，直接扫描库中百分比收益率的符号会漏掉它，得到错误的 17 行。

**2. 海外三张卡：人民币卡确实缺窗口观测，美债利差缺的是展示投影。**

库中定位为同一 `macro` 文档的 `international_context[]`，按下表 `metric_id` 筛选。

| 卡片 / metric_id | `change_5.reason` | 五日窗口内有效点 | 展示点列有效数 |
|---|---|---|---|
| 中间价 `CN_USDCNY_CENTRAL_PARITY` | `window_session_missing` | **5/6**；缺 10-15 | 120 个日期槽中 **10 点** |
| 16:30 收盘价 `CN_USDCNY_CLOSE_1630` | `window_session_missing` | **2/6**；仅 10-14、10-19，缺 10-12、13、15、16 | 120 个日期槽中 **6 点** |
| 利差 `UST_2S10S_SPREAD` | **字段不存在**，整个 `display` 不存在 | 利差自身无点列；两条输入均 **6/6** | 利差无点列；两条输入各 **119/120 点** |

两张人民币卡的五日窗口均为 **10-12 至 10-19**：

- **中间价**：窗口值为 `6.7313、6.7298、6.7249、缺、6.7220、6.7208`。虽然首尾都有数，代码要求窗口每个交易日都有有效观测，因此留空符合现行规则：[display_projection.py:255](/mnt/d/cursor/datasourceRF/src/pring_cycle/display_projection.py:255)。
- **16:30 收盘价**：窗口仅 `10-14=6.6925、10-19=6.6817`。首点也缺，无法形成五日比较。其来源解析器只产出快照对应交易日的一条收盘价，不提供历史序列：[quote_sources.py:142](/mnt/d/cursor/datasourceRF/src/pring_cycle/quote_sources.py:142)、[quote_sources.py:166](/mnt/d/cursor/datasourceRF/src/pring_cycle/quote_sources.py:166)。

关于“**不在需求内／只取最近两期**”，应区分读取声明、需求计划和实际取得的数据：

- 通用自身读法声明读取最近两期、最低要求一期；仅 P0/P1 默认要求窗口逐日数据，两张人民币指标属于 P2。依据：[lookback.py:191](/mnt/d/cursor/datasourceRF/src/pring_cycle/lookback.py:191)、[lookback.py:216](/mnt/d/cursor/datasourceRF/src/pring_cycle/lookback.py:216)。
- 本次 `full_run_gap_plan(phase='final')` 中，中间价仅要求 **10-19**，状态 `local_complete`；16:30 收盘价仅要求 **10-16**，状态 `model_input_missing`。中间价缺失的 10-15 不在本次需求计划内；收盘价缺失的 10-16 **在需求内**，不能一概说“均不在需求内”。
- **没有证据支持“实际查询被截成最近两条”**。库中分别已有 10 个和 6 个不同日期；收盘价本次请求参数甚至含 `start_date=2026-04-07`，但该快照解析器仍只能给出一日值。
- 收盘价要求日为 10-16，与其时效规则 `lag=1` 一致：[freshness.py:157](/mnt/d/cursor/datasourceRF/src/pring_cycle/freshness.py:157)。

因此，两张人民币卡的“—”是**正确表达当前数据不足**；但若产品承诺持续提供“五日变化”，目前取数需求与展示需求没有闭合。应明确显示缺哪些日期，而不是只写“—”。现有代码实际上已把原因放进悬停 `title`，抽屉也显示原因，并非完全没有说明：[cockpit.py:317](/mnt/d/cursor/datasourceRF/src/pring_cycle/cockpit.py:317)、[cockpit.py:2548](/mnt/d/cursor/datasourceRF/src/pring_cycle/cockpit.py:2548)。

**美债利差属于展示投影缺项，可用现有输入补算。**

代码先给普通指标生成 `display`，随后只对美债两条输入的**最新共同日期**生成一条利差记录；这条派生记录没有 `display/change_5`：[context_projection.py:409](/mnt/d/cursor/datasourceRF/src/pring_cycle/context_projection.py:409)、[context_projection.py:2384](/mnt/d/cursor/datasourceRF/src/pring_cycle/context_projection.py:2384)、[context_projection.py:2728](/mnt/d/cursor/datasourceRF/src/pring_cycle/context_projection.py:2728)。

库中派生记录 `93a13efdf5466eb51f161f2a12ae41f090435385bc1af8a9320d556b2f514747` 的值为 **35 基点**，输入为 10-16 的 `5.09%−4.74%`。两条输入的五日窗口均为 **10-08 → 10-16**，六个市场交易日齐全：

- 10-08：`(5.22−4.75)×100=47 基点`
- 10-16：`(5.09−4.74)×100=35 基点`
- 应可生成五日变化：**−12 基点**

这不是历史数据不足。页面当前回退提示“旧投影未提供”，对本次新投影不够准确，建议补齐派生展示序列及变化字段。

另有一个相关语义问题：利差记录的 `direction='up'` 是因为 **35 基点大于零**，不是利差较前期上升；代码见 [context_projection.py:2734](/mnt/d/cursor/datasourceRF/src/pring_cycle/context_projection.py:2734)。这一卡的“↑上升”也应调整，不能套用同类观察的“较上期方向”解释。

**3. 资产线图改为约 240px、每月一个横轴刻度的位置与测试。**

高度需要同时改两处：

- [cockpit.py:223](/mnt/d/cursor/datasourceRF/src/pring_cycle/cockpit.py:223)：`figure.layout.height: 160 → 240`。
- [cockpit.py:241](/mnt/d/cursor/datasourceRF/src/pring_cycle/cockpit.py:241)：`dcc.Graph.style.height: "160px" → "240px"`，同步更新上方注释。显式容器高度用于避免响应式布局中图表塌缩。

横轴位于 [cockpit.py:229](/mnt/d/cursor/datasourceRF/src/pring_cycle/cockpit.py:229)，当前为 `type="category", nticks=4`。建议保留交易日分类轴，将其改为：

```python
tickmode="array"
tickvals=每个月在 points 中首次出现的交易日期
ticktext=对应的 YYYY-MM
```

每月首个已有日期可由 [cockpit.py:186](/mnt/d/cursor/datasourceRF/src/pring_cycle/cockpit.py:186) 的 `dates` 生成；仅增大 `nticks` 不能保证每月一刻度。

**库中证据**：该投影 `core_assets.display.bond/stock/commodity.points` 均为 **120 点，2026-04-21 至 2026-10-19**，覆盖 4—10 月，按上述方法各产生 **7 个刻度**。图高与刻度配置不存于库中，由页面代码决定。

**`tests/web` 当前没有直接断言 `160px`、图高或横轴刻度的测试。** 检索 `160|240|height|nticks|tickvals|ticktext|tickmode|dtick|xaxis` 为零命中，因此没有必须随数值修改的旧断言。

相关回归入口是：

- [test_asset_cards.py:121](/mnt/d/cursor/datasourceRF/tests/web/test_asset_cards.py:121)：资产卡内容与顺序。
- [test_asset_cards.py:182](/mnt/d/cursor/datasourceRF/tests/web/test_asset_cards.py:182)：无展示点列的兼容分支。
- [test_report_board.py:17](/mnt/d/cursor/datasourceRF/tests/web/test_report_board.py:17)：整页板块与冻结证据链接。

这些测试能覆盖渲染调用链，**不能验证实际图高或月刻度效果**；实施时需针对跨月点列核查图配置，并补一次浏览器尺寸与刻度检查。
