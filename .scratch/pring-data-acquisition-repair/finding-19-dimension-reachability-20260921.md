Status: assessment-only
Type: read-only-survey
Date: 2026-09-21

# #19 维度反例：`REQUIRED_DIMENSION_MEMBERS` 逐家族可达性分类

本文件只读码，不改 `src/`、`tests/`、`tools/`，不跑任何验证。承接
[plan-19](plan-19-preflight-remaining-checks-20260920.md) 末两节确立的判据，把它套到
`metric_contracts.py:52` `REQUIRED_DIMENSION_MEMBERS` 的其余家族上。

按 [任务组 B](parallel-tasks-b-20260921.md) B3 的要求，**没有**为试探可达性去造任何绕合同的夹具；
plan-19 第 53–62 行记过那次尝试及其撤除，此处只从适配器与守卫的代码推。

## 结论（先给判决）

**不能**把 `dimensions` 记为「合同上不可达」并从 `material_preflight.py:312`
的 `pending_checks` 移出。至少 `CN_INDEX_VALUATION` 可达且成本低，`CN_FUTURES_WARRANTS`
在交付粒度上同样可达（只是走另一条诊断），`CN_M1_M2` 经 tushare 通道在原理上也可达。
该项应保留在 pending，并按下面第 6 节的草图落一条反例。

## 1. 判据需要补一条：不是一条通道，是两条

plan-19 的判据「同次交付 vs 分次交付」是对的，但只覆盖了一半。逐家族核对后，
「某必需成员应有而未交付」这一状态实际有**两条**互相独立的合法通道：

- **通道 A · 分次 `_call`，某次返回空行。** 一次交付对应一个成员子集，那次为空即天然缺该子集。
  `_response_rows`（`tushare_context.py:2696`）只要求 `data.fields` 里**有**必需字段名
  （`:2713-2714` 的 `tushare_response_required_field_missing`），对 `data.items` 为空列表
  不作限制（`:2715-2719` 直接遍历空列表返回空元组）。所以「字段齐全、零行」是完全合法的响应。
- **通道 B · 同次交付内的空值被跳过。** 构造标量的 builder 遇到空值时若是 `continue`
  而不是 `raise`，那么一行里某列为 null 就少产出一个成员。关键在于：**再解析同一份原件
  会得到同样短的标量集**，所以原件一致性校验对比的是「短集 vs 短集」，恒相等，拦不住。

margin 之所以不可达，是因为两条通道都被堵死：它只有一次 `_call`（`tushare_context.py:854-861`），
而 builder 在缺值时 `raise ValueError("tushare_margin_value_missing")`（`tushare_context.py:875`）
而不是跳过。这比 plan-19 原来的表述更精确——**决定可达性的是 builder 对缺值的处置方式，
以及交付粒度，两者任一成立即可达**。

各 builder 对缺值的处置（均经代码核实）：

| builder | 缺值处置 | 位置 |
| --- | --- | --- |
| `_valuation_scalars` | `continue`（跳过该 measure） | `tushare_context.py:2044-2045` |
| `_monthly_scalars` | `continue`（跳过该 field） | `tushare_context.py:1959-1961` |
| `_warrant_scalars` | `continue`（跳过该 measure） | `tushare_context.py:2660-2662` |
| `margin_financing` | `raise tushare_margin_value_missing` | `tushare_context.py:873-875` |
| `daily_breadth_scalars` | `raise breadth_available_value_missing` | `market_breadth.py:695-696` |
| `_extract_rate`（LPR） | `raise lpr_{1y,5y_plus}_value_missing` | `official_lpr.py:509-514` |
| `_parse_pbc_money` | `raise official_context_money_values_missing` | `official_context.py:2131-2132` |

## 2. 逐家族分类表

判定口径是**预检能看到的部分成员集**：同一 `metric_id`、同一 period 下，一部分必需成员有值、
另一部分没有。整指标全缺不算——那在 `material_preflight.py:135-139` 就以
`source_material_missing` 结束，根本走不到 `historical_selector.select`，
和维度检查无关。

| 家族 | 交付粒度 | 部分成员集是否可达 | 若不可达，最先拦截处 |
| --- | --- | --- | --- |
| `CN_INDEX_VALUATION` | **逐指数分次**（`tushare_context.py:968-978`，对 `VALUATION_INDEX_CODES` 的 3 个代码各一次 `_call`） | **可达**（通道 A、B 均可） | 不适用 |
| `CN_FUTURES_WARRANTS` | **逐品种分次**（`worker.py:1601-1610` 对 `WARRANT_SYMBOLS` 逐个调 `adapter.futures_warrants`；`tushare_context.py:713-721` 每品种一次 `fut_wsr`） | **可达**，但走专用诊断，见第 3 节 | 不适用 |
| `CN_M1_M2` | 同次 `cn_m`（`tushare_context.py:606-610`）**或**同次 PBC 公告 | **tushare 路可达（通道 B）；PBC 路不可达** | PBC 路：`official_context.py:2132` `official_context_money_values_missing`（m1/m2 任一正则不中即抛，4 个标量在 `:2143-2160` 以定长笛卡尔积生成） |
| `CN_LPR_1Y_5Y` | 同一份 HTML 公告，两个 tenor 同次抽取（`official_lpr.py:160-165`） | **不可达** | `official_lpr.py:509-514` `_extract_rate` 抛 `lpr_1y_value_missing` / `lpr_5y_plus_value_missing`；且 `official_lpr.py:347-360` 的标量由 `parsed.observations` 这个定长二元组生成，公开入口无法只投一个 tenor |
| `CN_OMO_7D_AMOUNT` | 同一份 PBC 公开市场公告；且**必需成员只有一个**（`metric_contracts.py:247-248` / `:62`） | **不可达（按构造不存在部分集）** | 单成员家族没有「部分」可言：要么整指标缺（`source_material_missing`），要么该成员在。解析失败处 `official_context.py:1633-1635` `official_context_row_identity_mismatch` |
| `CN_EQ_ADV_DEC` | 同次计算，成员为定长元组 | **不可达** | `market_breadth.py:686-696`：5 个 measure 定长生成，任一为 None 即 `breadth_available_value_missing`；另有整批相等校验 `market_breadth.py:870-894` `breadth_scalar_values_mismatch`；旧路 `tushare_context.py:1288-1302` 同样定长，缺观测在 `:1287` 以 `tushare_breadth_observations_incomplete` 先抛 |
| `CN_EQ_NEW_HIGH_LOW_120` | 同次计算，成员为定长元组（`tushare_context.py:1294-1295`） | **不可达** | 同上；窗口路另有 `tushare_context.py:1487-1500` `_require_breadth_scalar_match`（`:1500` 抛 `breadth_{family}_scalar_values_mismatch`） 的整批相等校验 |
| `CN_COMMODITY_SLEEVE_CONTRIBUTION` | 同次计算，7 个 sleeve 由 `COMMODITY_SLEEVES`（`commodity_basket.py:35-43`）定长笛卡尔积生成 | **不可达** | `commodity_basket.py:291-293`：任一 product 当日缺数即 `break`，整日不产出；`_commodity_members`（`:331-352`）从 `day["contributions"]` 全量展开。旧路 `tushare_context.py:1371-1377` 取各代码日期交集，缺一个代码是少一整天而非少一个 sleeve |
| `CN_MARGIN_BALANCE`（plan-19 已定） | 同次 `margin` | **不可达** | `tushare_context.py:875` `tushare_margin_value_missing`（去列则在 `:2714` `tushare_response_required_field_missing`）；事后过滤在 `tushare_context.py:317-343` `registered_margin_acquisition_values_mismatch` |

补一条守卫范围的事实：`tushare_context.py:302-343` 的整批相等校验（
`registered_{family}_acquisition_values_mismatch`）**只覆盖 margin、market_index、valuation
三族**。`cn_m`、`sf_month`、`cn_cpi` 等月度族不在其中，所以它们没有「持久化标量必须等于
重解析全集」这道闸；但也正因为重解析走同一个 `_monthly_scalars`，短集恒等于短集，
这道闸即便加上也拦不住空值那条通道。

## 3. `CN_FUTURES_WARRANTS`：可达，但不经通用维度循环

这是本次核对里最容易记错的一处。在注册目录下（`definition_version not in
BUILTIN_CATALOG_VERSIONS`），`search_evidence.py:326-339` 对 `CN_FUTURES_WARRANTS`
**提前 `continue`**，改用 `select_warrant_inputs`；`required_dimension_members`
那段通用成员循环（`search_evidence.py:355-411`）根本不执行。

于是缺品种时给出的是 `warrant_inputs.py:144` 的
`CN_FUTURES_WARRANTS:symbol_missing:{symbol}`，而不是通用的
`{metric_id}:{json.dumps(member, sort_keys=True)}`（`search_evidence.py:411`）。
两者都会进 `material_preflight.py:254` 的 `missing_members`，但它们检验的是不同代码路径。

推论（属推断，未实测）：拿 warrants 做「维度」反例，钉住的是 `select_warrant_inputs` 的
逐品种完整性，不是 `required_dimension_members` 这条通用契约。只有在内建目录下
（走通用循环、用 `REQUIRED_DIMENSION_MEMBERS` 的 8 个 symbol 成员）它才落在通用路径上，
而预检实际跑的是注册目录。**所以它不该被选作 `dimensions` 的反例。**

## 4. 必须与「缺件」区分开的三类合法变化

1. **报告月导致的合法变化**：`metric_contracts.py:259-265`，CPI/核心 CPI 的 measure 集
   按月变化——1 月官方表没有 cumulative 列，`required_dimension_members` 相应少返回一个成员。
   这是**期望集本身在变**，不是交付缺件。任何反例都不能把这种情况读成缺口。
2. **同一 metric_id 在不同目录版本下期望集不同**：`CN_EQ_ADV_DEC` 在注册目录下走
   `DAILY_BREADTH_MEASURES`（`market_breadth.py:288-291`），**5 个**成员且带
   `universe` 维；而 `REQUIRED_DIMENSION_MEMBERS`（`metric_contracts.py:67-69`）里是
   **4 个**、不含 `participants`、不带 `universe`。旧适配路径
   `tushare_context.py:1288-1291` 也只产 4 个。断言时必须先确定目录版本，
   否则会把「另一套合法期望集」误记成缺件。
3. **整日/整指标缺失**：breadth 的 `market_breadth.py:684`（`participants` 为空跳过整日）、
   commodity 的 `commodity_basket.py:291-293`（`break`）、valuation 的整族无材料，
   都会让该 period 全部成员一起缺。那在诊断里与 `source_material_missing` 无法区分，
   **不构成维度检查的反例**。这正是为什么现有的
   `tests/integration/test_valuation_completeness.py:29-31`（断言 9 个成员全缺）
   虽然涉及 `missing_members`，却没有覆盖维度这一项。

## 5. `CN_M1_M2` 为何「原理可达但不该选它」

tushare `cn_m` 路确实可达：`money`（`tushare_context.py:593-611`）一次取回
m1/m2 × balance/yoy(/mom)，但 `_monthly_scalars` 对空值 `continue`
（`tushare_context.py:1959-1961`），所以某月 `m1_yoy` 为 null 就会少一个必需成员，
而 `parse_money_acquisition`（`tushare_context.py:2188-2199`）重解析同一份原件
得到同样短的集合，原件一致性校验恒过。注册目录下该族的必需成员由
`official_source_members`（`metric_contracts.py:179-184`）给出的 4 个，
与 `REQUIRED_DIMENSION_MEMBERS` 一致，没有 CPI 那种按月变化。

但现有隔离材料里 `CN_M1_M2` 的声明来自**归档的 PBC 公告**
（`tests/models/test_isolated_lifecycle.py:261-280` 的 `import_official_archive`，
family `pbc_money`）；`tushare:cn_m:official-sampled-v0001`
只是在 `:132` 被加进 `source_codes`，并没有对应的 tushare 采集导入。
要在这条路上造反例，得先给夹具新增一整条 tushare money 采集通道——
成本远高于 valuation，且触碰的是双来源审查（`source_contract_review.py:214-216`）那一摊。
**不建议选它**；但它的存在足以否掉「所有家族都不可达」这个结论。

## 6. `CN_INDEX_VALUATION` 反例草图（给下一切片，可直接实施）

**改动点**：`tests/models/test_isolated_lifecycle.py:376-410` 的 `import_market_daily`，
其 `transport` 在 `api == "index_dailybasic"` 分支（`:395-397`）按 `code` 分流——
对 `"000852.SH"` 返回 `items: []`，`fields` 保持
`["ts_code", "trade_date", "pe", "pb", "turnover_rate"]` 不变；另两个指数照旧。

**为什么这不绕合同**（逐道守卫核对）：

- `_response_rows`（`tushare_context.py:2696-2719`）：`fields` 齐全，`items` 为空
  → 返回空元组，不触发 `tushare_response_required_field_missing`（`:2714`）。
- `_valuation_scalars`（`:2033-2058`）：零行 → 零标量，不抛。
- `index_valuation`（`:968-978`）：另两个指数的 6 个 measure 照常返回。
- 整批相等校验（`:317-343`）：持久化侧与重解析侧**都**没有 000852 的标量，两侧相等，
  不触发 `registered_valuation_acquisition_values_mismatch`（`:343`）。
- 逐标量溯源（`:408-421`）：只对**已产出**的标量找对应 `ts_code` 的收据；
  没有 000852 标量可遍历，`registered_valuation_acquisition_missing`（`:420`）不触发。
- 选值期的原件比对（`search_evidence.py:266-274` 的 `parse_valuation_acquisition` 族）：
  逐条声明校验，000852 没有声明可校验，全部通过。

**断言什么**：`CN_INDEX_VALUATION` 是 P1（`catalog.py:56`，在 `_P1` 元组内），
所以进 `gaps` 而非 `optional_gaps`（`material_preflight.py:222-227`）。
预检结果里应能取到一条

```
{"metric_id": "CN_INDEX_VALUATION", "reason": "input_selection_missing",
 "business_date": <当日>, "period": <当日>, "missing_members": "<以 ';' 连接>"}
```

（构造处 `material_preflight.py:247-256`，`period` 取自 `:229` 的
`max(point.period_end ...)`，该族为日频故等于当日。）

`missing_members` 必须**恰好**是这三条，且不多不少（即另外 6 个成员不得出现）：

```
CN_INDEX_VALUATION:{"index": "000852.SH", "measure": "price_book"}
CN_INDEX_VALUATION:{"index": "000852.SH", "measure": "price_earnings"}
CN_INDEX_VALUATION:{"index": "000852.SH", "measure": "turnover_rate"}
```

字符串形态来自 `search_evidence.py:411`
`f"{metric_id}:{json.dumps(member, sort_keys=True)}"`——`sort_keys=True`、默认分隔符
（`", "` 与 `": "`），成员字典来自 `metric_contracts.py:75-80`（`index` × `measure`
笛卡尔积，`measure` 取自 `VALUATION_FIELDS`，`tushare_context.py:60-64`）。

「不多不少」是这条反例的全部价值所在：它把维度检查与
`tests/integration/test_valuation_completeness.py:29-31` 那条「9 个全缺」区分开——
后者与整族无材料不可分辨，前者只有逐成员比对才能产生。

**更锐的变体（可选，二选一或都做）**：不让 000852 空行，而是让它的 `pb` 列返回
`null`（`items` 为 `[[code, d, 12.5, None, 0.8] for d in compact]`）。
`_valuation_scalars:2044-2045` 跳过该 measure，结果**只缺一个成员**：
`CN_INDEX_VALUATION:{"index": "000852.SH", "measure": "price_book"}`。
这条同时钉住了通道 B，并证明检查粒度到 measure 而非到 index。

**不要做的事**：不要去改已持久化的标量、不要从原件里删列、不要绕过
`acquire_scalars`。以上两个变体都只改**投喂给适配器的响应内容**，
适配器、守卫、持久化路径一行不碰——这正是它与 margin 那次失败尝试的区别。

## 7. 已核实 vs 推断

**已核实（读码，逐条有 file:line）**：第 1 节的 builder 缺值处置表；第 2 节每一格的交付粒度
与拦截点；`_response_rows` 允许空 `items`；三族整批相等校验的覆盖范围；
warrants 在注册目录下绕过通用成员循环；`missing_members` 的字符串形态与构造位置；
`CN_INDEX_VALUATION` 的 P1 归属；夹具中 `CN_M1_M2` 走 PBC 归档而非 tushare。

**属推断，未实测**：第 6 节「六道守卫都不触发」是按代码推的，没有跑过；
下一切片实施时若某一道意外触发，应当按 plan-19 的规矩**撤除测试并记录拦截点**，
而不是改夹具去绕它。第 3 节关于「warrants 反例钉住的是另一条路径」同为推断。
另外，本文件只核对了 `REQUIRED_DIMENSION_MEMBERS` 中 B3 点名的 7 族加上 margin、
valuation；`CN_PMI_*`、`CN_SHIBOR_ON_1W_3M`、`CN_SF_TOTAL` 未纳入本次核对范围。

## 独立复核（2026-09-21，Codex CLI，只读）

本文件写成后由另一引擎独立重追一遍，用于补上「六道守卫都不触发」这一读码推断的第二意见。
复核逐条核对了 **11 道**检查点，结论：**反例可行，采集与入库途中没有一行拦得住它。**

### 确认的部分

- `tushare_context.py:968` 的循环确实对 `VALUATION_INDEX_CODES`（`:59`）逐个 `_call`，
  请求参数含当前 `ts_code`；`_response_rows`（`:2696`）只要求 `fields` 完整、`items` 是列表，
  **不要求非空**；`_valuation_scalars`（`:2033`）只遍历实际返回行，零行产出零标量。
- 空响应仍会追加收据（`:1469`），其规范化内容为 `[]`；`complete_validation`
  （`acquisition.py:235`）检查状态、可序列化与时间顺序，无非空要求。
- 整批标量非空检查（`:1512`）仍有另两个指数的标量，不触发 `ContextObservationsMissingError`。
- 声明字段与注册契约检查（`evidence.py:498`/`:1374`、`source_contract_review.py:424`/`:489`）
  逐声明校验，**不要求这一批包含全部九个成员**。

### 修正一处理由

本文件原先说 `registered_valuation_acquisition_values_mismatch`（`tushare_context.py:317`）
不触发是因为「两侧同为空故相等」。**这个说法不准确**：正常单日数据下两侧并非空集，而是
**六个标量对六个标量**——两侧都同样缺少 000852 的贡献，所以相等。结论不变，理由要改成
「两侧都缺同一块，因而仍然相等」。

`registered_valuation_acquisition_missing`（`:355`/`:410`）不触发的理由成立：外层只遍历
已产出的标量并按其 `dimensions["index"]` 找收据，没有 000852 标量需要检查。

### 补充的定位

- 首次明确记录该成员缺失的是 **`search_evidence.py:411`**；`ModelInputSelector` 在 `:367`/`:408`
  对每个成员做 **`p.dimensions == member` 完整字典比较**，不是只比 `index`。
- `metric_contracts.py:75` 列出三指数 × 三 measure 的笛卡尔积共九个成员，
  `required_dimension_members` 对 valuation 最终返回这个固定集合（`:303`）。
- 预检把缺失项以分号连接保留在 `reason="input_selection_missing"` 的诊断里
  （`material_preflight.py:247`），**不会折叠成一个 index**。

因此断言的三条应为：

```text
CN_INDEX_VALUATION:{"index": "000852.SH", "measure": "price_earnings"}
CN_INDEX_VALUATION:{"index": "000852.SH", "measure": "price_book"}
CN_INDEX_VALUATION:{"index": "000852.SH", "measure": "turnover_rate"}
```

### 复核自己声明的边界

解析部分由纯内存探针实测（三次独立请求、六个标量、按指数重解析 `3、3、0`、经济字段比较相等）；
**入库到预检那一段仍是读码复核，未跑完整生命周期**。另外，「当前接入契约接受这种交付形态」
不等于「真实 TuShare 曾返回过该形态」——这两件事不可混谈。
