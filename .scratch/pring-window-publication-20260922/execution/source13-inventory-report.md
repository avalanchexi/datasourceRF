**结论：软件接缝已存在，真实材料仍不能证明新窗齐备；另发现旧采集原件在本工作区缺失。** 本轮仅静态读码、读取原件及重算哈希，未联网、运行旧脚本、测试或改变状态。

下文 `R=.scratch/pring-data-acquisition-repair/`，`W=.scratch/pring-window-publication-20260922/`，`S=src/pring_cycle/`，`E=R/evidence-11/`。

1. **冻结规则与必需输入**

七袖套为 CU、RB、PP、纺织（CF/TA各半）、RU、SP、SC；SC权重1/5，其余各2/15，每日恢复权重。真实已上市合约按最近到期选择，剩余交易所开市日按 `(T, 到期日]` 计数，须严格大于10；同到期不能唯一选择即拒绝。选择在T所属时段开始前冻结，含夜盘；T日公告不能改变T选择。收益为所选同一合约 `settle/pre_settle−1`，不使用连续主力代理。批准依据 `R/issues/12-commodity-basket.md:62`；实现 `S/commodity_basket.py:31、99、149、211、300`。

父项包括完整交割年月、来源短码映射、上市/最后交易日、单位及乘数、逐所日历、逐品种所属交易日与时段、结算对、调整及发布版本。CF/TA不能凭短码猜年份；SC按元/桶，其余按元/吨。字段及校验见 `S/futures_inputs.py:38、70、361`。

**预热不能统一259日。** 本篮子固定2026-03-06收盘1000，须保留基日输入及03-09起全部累乘链；03-09—03-31虽移出展示，仍参与04-01结果。见 `S/commodity_basket.py:246、272`；新范围见 `W/spec.md:82`。发布证据须绑定值自己的版本；仅日期则下一本地日可见，未知保持空，规则日程不能补时间（`docs/adr/0018-tiered-evidence-for-historical-publication-dates.md:7`）。证据包按API、参数、raw_hash及可选合约/日期绑定，并要求accepted审查：`S/futures_inputs.py:209、249、298`。

2. **本轮实核材料及缺件**

| 项目 | 本轮可证范围／缺件 |
|---|---|
| 第一方研究原件 | E内28份内容寻址文件全部哈希匹配；18份请求响应及10份导入文件的长度、哈希均匹配登记。不是28份有效业务材料，含错误/验证页。 |
| 行情覆盖 | 实读SHFE DAT、CZCE TXT各08-27/28/31三日，最晚08-31；合约表仅02-02、03-09、08-28。不能称连续覆盖至08-31。 |
| 旧渠道材料 | `futures-metadata-204/`、`futures-daily-206/`及收据不存在；205核验、206请求计划、208核验亦不在原路径。535清单166项中14项存在且匹配，**152项缺失：12元数据/日历、140行情**。旧“11,712行”只能保留为历史记录。 |
| 新17日 | `W/calendar-plan.json:185`给出08-31—09-22。需要17×8＝136个品种日的实际选择及结算对，另加其全部父项；08-31已有部分第一方价格样本，不代表该日篮子齐备。已查最新抢救收据仅含南华、融资，无本票新增合约交付。 |
| 旧实质缺件 | PP发布方价格、字段/单位锚点；PP及CF/TA适用规则链；历史身份、日历、时段、到期调整与逐值发布时间；固定基日及累乘链完整性。 |
| synthetic边界 | 合成合约/工作日日历在 `tests/adapters/test_futures_inputs.py:27、53`；商品认证包调用`bind_synthetic_review`在 `tests/models/test_registered_commodity.py:56`。不能作为真实认证。 |

可复核样本：`E/09820b4f…dat`中的SC2609前结算640.1、结算584.2；`E/81686cd4…dat`的08-31同合约为584.2、605.6，均明确`sc_f/PRODUCTCLASS=1`，不能混TAS。

本轮实算完整SHA：

- 08-31 DAT：`81686cd4f0a5724726e31795acafeb720297a244126736af0e995a81f2a32a89`
- E请求收据：`16b488376897305af98e46e5b051fa5145d5790f9188a8674d41c2ae79951274`
- `R/verification-futures-research-root-535.json`：`a1b861cf388f330091442e4989607ffe93aa431fbc26e7b09e26e01d26219bda`

**准确缺件列表可从535文件`:9`的`originals`逐项检查存在性及哈希生成。** 恢复材料后，再按冻结选择器为每个日期生成候选身份、时段、所需日历区间、选中结算及发布版本需求，与原件逐项做差；当前不能可靠列出新17日已认证持有合约。

3. **可接入入口，均未实测**

调用链为：

`TushareContextAdapter.acquire_futures_inputs`（`S/tushare_context.py:1321`）→原响应采集/解析（`S/futures_inputs.py:463`）→`bind_futures_input_evidence`（`:573`）→`select_futures_inputs`（`S/futures_input_reads.py:134`）→`persist_commodity_basket`（`S/commodity_basket.py:475`）→8个不可变声明及父项（`:523`）→`EvidenceRepository.source_claim_originals`（`S/evidence.py:304`）。

研究文件不会自动成为应用收据。特别注意：`S/tushare_context.py:1341`仍有连续码、`close/pre_close`旧篮子入口，不能用于本票。`R/verify-futures-research-root-535.py:9`会写输出，不应作为只读命令执行。

4. **下一步一次最小取证行动**

建议主代理在其已有采集授权内，先做**目标日SHFE两件原件批次，共2次匿名GET、失败不自动重试**：

- `https://www.shfe.com.cn/data/busiparamdata/future/ContractBaseInfo20260921.dat`
- `https://www.shfe.com.cn/data/tradedata/future/dailydata/kx20260922.dat`

路线由已核哈希的第一方`E/888923e3…js:70、218`明确生成。保存完整响应、请求/接收时刻、状态、哈希、字节数；核业务日期、普通合约类别、月份、结算列及对应身份。09-21合约快照仅作为09-22时段前输入候选，必须另证其实际公开时间；正文更新时间未经语义核验不能自动当首次发布。两件不足以关闭PP、日历、时段或整窗缺口。

TuShare属于项目已接受的个人非商业交付渠道，但当前账户权限未查；其批量入口参数为八品种`fut_basic(fut_type=1)`、四所`fut_trade_cal`、逐真实合约`fut_daily`，调用数为`8+4+N`（`S/futures_inputs.py:517`）。DCE旧POST只有超时收据、缺第一方字段绑定（`E/receipts.json:18`），客户端/席位及付费权限未知，不列为本批可用渠道。