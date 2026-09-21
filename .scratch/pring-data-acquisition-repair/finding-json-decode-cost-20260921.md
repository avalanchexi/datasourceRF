# 发现：54.8 万次 JSON 解析里，八成时间在 440 次调用上（2026-09-21）

只读调查。未修改任何源码、测试或配置；所有运行库均以 `mode=ro&immutable=1` 打开。

## 结论先说

**"次数多"和"时间贵"在这里不是同一批调用点。**

- 按**次数**：`evidence.py:917 metric_series` 一家占 58%（320,947 次），但它解析的是 28 字节的 `dimensions_json`，全部加起来只值 0.21 秒。
- 按**时间**：`_commodity_document` 只有 874 次解析，却吃掉 `raw_decode` 65.01 秒中的约 **53.6 秒**。因为它每次解析的是一份 **中位 12.6 MB、最大 24 MB** 的快照，而且一次调用解析两份（`raw` 与 `normalized`）。

也就是说：票据里"`_commodity_document` 只有 440 次调用，远不足以解释 54.8 万次"这个判断，**对次数是对的，对时间是反的**。54.8 万次这个数字本身是个误导性指标。

安全性结论：**按内容哈希缓存解析结果，在 `_commodity_document` 上不安全**。今天不会立刻出错，但它会让 `document != json.loads(snapshot.normalized)` 这道校验的有效性，取决于数据里碰巧有没有一个非 ASCII 字符。理由见第三节。

---

## 一、54.8 万次的调用点分布

数据来自 `hot-test.pstats`（`pstats` 的 `print_callers`，逐层回溯到 `pring_cycle` 自己的函数）。`json.loads` 的 `cc == nc == 548,960`，没有递归；58 个上游调用点，下表列出 ≥300 次的全部。

**注意行号口径**：profile 采于 10:55，跑的是 `~/.local/share/pring-cycle/dev-venv/.../site-packages/pring_cycle/`（安装副本，非 `src/` 的 editable 链接）。该副本与当前 `src/` 逐字节一致（`diff` 无差异），但 `src/pring_cycle/commodity_basket.py` 在 11:47 被改过并于 11:54 重装，**`_commodity_document` 已从第 383 行移到第 438 行**。其余热点文件未改动，行号仍然有效。

| 次数 | 调用点（当前 `src/` 行号） | 解析对象 | 单份大小 |
|---:|---|---|---|
| 320,947 | `evidence.py:998` / `evidence.py:1055`（均在 `metric_series`，`evidence.py:917`） | `row["dimensions_json"]` | 均值 28 B |
| 89,420 | `acquisition.py:387`（`receipt_from_row`，`acquisition.py:385`） | `row["parameters_json"]` | 均值 59 B |
| 54,010 | `market_breadth.py:627`（`parse_daily_breadth_acquisitions`，:586） | 采集原件 `raw` | 96–224 B |
| 42,220 | `catalog_registry.py:106` + `:111`（`registered_definitions`，:74） | `manifest_json` + `definitions_json` | 40,394 B + 33,767 B |
| 26,620 | `market_breadth.py:1258`（`parse_window_breadth_acquisitions`，:1180） | 采集原件 `raw` | 同上 |
| 3,295 | `tushare_context.py:2294` | — | — |
| 1,986 | `tushare_context.py:2007` | — | — |
| 1,760 | `tushare_context.py:2529` | — | — |
| 1,094 | `source_adapters.py:350` | — | — |
| 993 | `tushare_context.py:2060` | — | — |
| 880 | `market_breadth.py:322`（`_validate_breadth_review`） | 评审制品 | — |
| **874** | **`commodity_basket.py:445` + `:447`（`_commodity_document`，:438）** | **快照 `raw` + `normalized`** | **中位 12.6 MB** |
| 770 | `market_breadth.py:810`（`_breadth_claims_valid`） | `item.normalized` | 4,739 B |
| 677 | `tushare_context.py:1433` | — | — |
| 601 | `tushare_context.py:2083` | — | — |
| 550 | `market_breadth.py:375`（`load_breadth_universe`） | — | — |
| 469 | `full_retrieval.py:587` | — | — |

前 5 项占 533,217 次 / 548,960 次 = **97.1%** 的调用次数。

### 时间归属不能直接信 pstats

pstats 对 `loads` 的逐调用方 `cumtime` 加总只有 17.48 秒，而 `loads` 自身 `cumtime` 是 77.11 秒——上游里有递归帧（如 `_commodity_document` 显示为 `874/63`），逐调用方的累计时间不可用。

所以改为**直接重放实测**：从素材库（见第二节）取出各调用点真实的载荷，按 profile 里的次数在同一解释器（`dev-venv`，CPython 3.12.12）上重跑 `json.loads`，不开 profiler。

| 调用点 | 次数 | 解析字节总量 | 实测秒 |
|---|---:|---:|---:|
| `commodity_basket.py:445`+`:447` | 874 | ~10.6 GB | **53.6** |
| `catalog_registry.py:106`+`:111` | 42,220 | 1,566 MB | **6.33** |
| `evidence.py:998`+`:1055` | 320,947 | 8.9 MB | 0.21 |
| `market_breadth.py:627` | 54,010 | 8.6 MB | 0.13 |
| `acquisition.py:387` | 89,420 | 5.3 MB | 0.07 |
| `market_breadth.py:1258` | 26,620 | 4.3 MB | 0.06 |
| 合计 | 534,091 | — | **60.4** |

对照 profile 中 `raw_decode` 的 `tottime` = 65.01 秒，剩余约 4.6 秒落在未逐项重放的约 1.5 万次调用上。两边能对上，说明这个时间模型可用。

顺带核了一次 profiler 失真：同一批载荷在 `cProfile` 下的 `raw_decode` `tottime` 与裸跑耗时比值为 0.9，**65.01 秒不是被插桩放大出来的**，是真实解析开销。

---

## 二、有多少是同一份字节被反复解析

### 依据来源与其局限

热用例的运行库是一次性的 `tmp_path` 副本，跑完即弃，无法事后查询。改用 `isolated_lifecycle_material` 的**素材库**度量：`/home/tywin/.cache/pring-cycle/test-materials/5d75499a…/runtime`（其 `material.json` 为 `isolated-lifecycle-material-v0001`、`replay_trading_days: 120`、`metric_catalog_version: synthetic-metric-catalog-admission-v1-isolated-lifecycle`）。热用例正是从同一套 builders 产出的素材复制而来。

**这不是同一份素材**：热用例算出的 key 是 `648d5e2d…`，此处度量的是 `5d75499a…`。两者由同一 builders 构建，指纹（`code_hash`/`dependency_hash` 等）不同。因此下列"distinct"是**同构下的实测值**，不是该次 profile 运行的逐字节回放。

另：本次尝试过给 `json.loads` 加探针后重跑热用例（`-p jsonprobe -p no:cacheprovider`，不改仓库文件）。用例在重建素材上跑了 18 分 14 秒后失败——`isolated_lifecycle_material` 把构建结果存进了 `5d75499a…`，而调用方期待 `648d5e2d…`，于是 `material.json` 读不到（`FileNotFoundError`）。只跑到 4 次 `json.loads` 就中止，拿不到运行内的实测重复率。这条路本次没走通。

### 实测重复率

| 调用点 | 解析次数 | 素材中不同载荷数 | 重复率下界 |
|---|---:|---:|---:|
| `catalog_registry.py:106`+`:111` | 42,220 | **2**（`registered_metric_catalog` 仅 1 行；`definitions_json` 与其 `manifest_json` 各 1 份） | **99.995%** |
| `evidence.py:998`+`:1055` | 320,947 | **176**（`source_claim` 23,886 行，`dimensions_json` 176 个不同值） | **99.945%** |
| `acquisition.py:387` | 89,420 | **795**（`acquisition_request` 1,556 行，`parameters_json` 795 个不同值） | **99.11%** |
| `market_breadth.py:627`+`:1258` | 80,630 | **251**（`daily`/`suspend_d`/`trade_cal`/`breadth_universe` 共 999 行，251 个不同 `raw_hash`） | **99.69%** |
| `commodity_basket.py:445`+`:447` | 874 | **≤240** 个不同字节串（120 份 `raw` + 120 份 `normalized`）；**≤120** 个不同解析结果 | **≥72.5%**（按字节串）<br>**≥86.3%**（按解析结果） |

几点说明：

- **`registered_definitions` 是纯重复**。它的全部输入只有 `(database_path, version)`；21,118 次调用里，本用例可达的 `(path, version)` 组合最多一个，表里就 1 行。每次调用都重开一次只读连接、重算一次 sha256、解析 74 KB、再 `json.dumps` 一遍（`_definition_document` 被调 21,140 次）。这 6.33 秒解析的是同样的两个字符串。
- **`_commodity_document` 的 874 次里有一层"结构性重复"**：每次调用把同一份快照解析两遍（`raw` 一次、`normalized` 一次）。实测这两份字节串不同（见下节），但解析出来**完全相等**。所以 874 次解析最多产出 120 个不同的值。
- `commodity_basket.py:745` 附近已有 `checked[ids]` 缓存，把同一组 `acquisition_ids` 的 document 复用；`commodity_basket.py:649` 那条路径没有等价缓存，且该函数被反复调用（每次 as-of 切点一轮），874 次就是这么攒出来的。

---

## 三、能否安全复用解析结果

这一问按调用点分开回答，因为答案不一样。

### 3.1 `_commodity_document`（占八成时间的那一个）——**不可按内容哈希复用**

`commodity_basket.py:445-453`：

```python
document: dict[str, Any] = json.loads(snapshot.raw)
if (
    document != json.loads(snapshot.normalized)
    or ...
    or snapshot.receipt.parameters != {"result_hash": hashlib.sha256(snapshot.raw).hexdigest()}
):
    raise ValueError("commodity_result_original_mismatch")
```

**实测：今天 `raw` 与 `normalized` 不是同一串字节。** 素材库 120 条 `commodity_basket` 收据，`raw_hash = normalized_hash` 的有 **0 条**。取一对出来逐字节比对，第一个差异在第 28,387 字节：

```
raw : ..."contract_unit":"吨","delivery_month"...
norm: ..."contract_unit":"吨","delivery_month"...
```

两者解析后相等。差异只来自 `ensure_ascii`：

- `commodity_basket.py:531`：`raw = json.dumps(document, sort_keys=True, separators=(",", ":"))`（`ensure_ascii` 默认 True）
- `acquisition.py:245`（`complete_validation`）：`normalized = json.dumps(normalized_value, default=str, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)`，而 `capture` 传的是 `parse=json.loads, normalize=lambda value: value`

所以按内容哈希做缓存，两边落在不同的 key 上，仍是两次独立解析，`document != json.loads(snapshot.normalized)` **今天不会退化成自己跟自己比**。

**但这个"安全"是碰巧的。** 用同样两句 dumps 做最小复现：

| 文档 | `raw == normalized` |
|---|---|
| 纯 ASCII | **True** |
| 含 `"吨"` | False |

两次 dumps 的差别**只有** `ensure_ascii`（`default=str` 和 `allow_nan=False` 在一次 `loads` 往返之后不起作用）。也就是说：**只要哪天商品结果文档里不再出现非 ASCII 字符**（比如 `contract_unit` 改成 `"t"`，或该字段被去掉），`raw` 与 `normalized` 立刻变成同一串字节，内容哈希缓存会把同一个对象还回来两次，`document != document` 恒为 False——这道校验静默失效，不抛异常、不报错、没有测试会红。它是**向失效方向塌陷**的。

把一道校验的有效性，挂在"数据里碰巧有没有一个汉字"上，不是可以接受的代价。**结论：此处不可按内容哈希复用解析结果。**

补充两点，免得下一轮重新推一遍：

1. **这道校验本来就比看上去弱。** `capture` 用的是 `parse=json.loads` + `normalize=identity`，于是 `normalized ≡ dumps(loads(raw))`。对任何写入正确的收据，`loads(raw) == loads(normalized)` 是构造上必然成立的。它实际能发现的是**制品库里两份 blob 对不上**（损坏或错配），而不是任何语义性质。要在不解析两份 12 MB 文档的前提下保住这层意思，方向应当是比对/重算两个摘要，而不是"解析一次传对象"——后者恰恰是把这层意思删掉。
2. **`result_hash` 那一项不受解析缓存影响。** `snapshot.receipt.parameters != {"result_hash": sha256(snapshot.raw).hexdigest()}` 的右边是从 `raw` **字节**现算的，左边来自另一列（`parameters_json`）的解析结果，两边不可能是同一个对象，不存在自比。它唯一的新风险是**别名**：若 `receipt.parameters` 按 `parameters_json` 共享同一个 dict，任一处修改会串到所有同参收据上。已在 `src/` 全量检索：没有任何地方修改 `receipt.parameters`（`parameters[...] = ` 的两处写入在 `source_history.py:200-202`，改的是刚 new 出来的本地 dict）。所以现在共享是安全的，但这会变成一条**没有任何机制保证的新不变量**。

同样地，`_commodity_document` 返回的 `document` 被下游持有（`result = document["result"]`、`_commodity_facts(result)` 直接返回内部节点的引用）。已核：`_commodity_facts` / `_commodity_members` / `_commodity_publication` / `_commodity_meaning_equal` 全是只读遍历，不改 document。若改为共享对象，"下游只读"同样成为一条无保障的新不变量。

### 3.2 `registered_definitions`——可复用，但会少跑 21,117 次自校验

每次调用都重新验证：`sha256(document) == digest`、`admitted["metric_catalog_version"] == version`、`_definition_document(admitted["metric_definitions"]) == document`。缓存结果 = 这些验证只在第一次跑。

这里**不存在自比风险**：三项比较的另一边分别是存库的摘要列、传入的 `version`、以及从 `manifest_json` 现算的字符串，没有一项会和被缓存对象本身比较。

但要注意两件事：

- 该行在构造上不可变（`_register_admitted_catalog` 发现已存在且不一致就抛 `metric_catalog_version_is_immutable`），但注册动作确实发生在运行期（`models.py:302`）。跨注册点缓存会让"注册后"看见"注册前"的结果，尤其是缓存 `KeyError`（未知版本）会把一个后来变成已知的版本永久钉成未知。
- 返回的 `list[dict]` 是可变的且直接暴露。现有三个调用方都只读（`registered_metric_definition` 先 `dict(definition)` 再改副本；`require_registered_manifest` 只重新序列化；`worker.py:1451` 只遍历）。共享后同样多一条无保障的不变量。

仓库里已经有现成的、写明了适用条件的机制：`read_scope.py` 的 `shared_read_scope` / `scope_cache`，其模块 docstring 明确界定了"scope 内可复用只依赖于 scope 内不会被采集或改写的输入的结果"。这一处若要复用，应当落在那套约束里，而不是进程级全局缓存。

### 3.3 `metric_series` 的 `dimensions_json`——复用在语义上完全无害，但只值 0.21 秒

`evidence.py:998` / `:1055` 的解析结果当场被降解成 `{str(key): str(value)}`，不参与任何比较、不被回写。复用不会破坏任何东西。但 320,947 次总共 8.9 MB、0.21 秒——**占调用次数的 58%，占时间的 0.3%**。

### 3.4 一个具体的陷阱：`parse_float` 不是同一种解析

同一份 `raw` 在不同调用点用不同解码口径：

- `market_breadth.py:627`、`:1258`、`futures_inputs.py:60`：`json.loads(raw, parse_float=Decimal)`
- `market_breadth.py:375`、`:915`、`futures_inputs.py:190`：`json.loads(raw)`

产出的数值类型不同（`Decimal` vs `float`），而这些值下游会进精确性判定（`commodity_basket.py:_commodity_meaning_equal` 里的 `Fraction(child) != Fraction(other)`、`futures_input_reads.py:_meaning` 里的 `Decimal(...)`）。**任何只以字节/哈希为 key 的缓存都必须把解码口径并入 key**，否则会把 `Decimal` 的结果喂给期待 `float` 的路径（反之亦然）。

### 3.5 仓库里已经在做的、方向正确的先例

写下来，免得下一轮当成新想法：

- `futures_input_reads.py:FuturesInputReader._document`：按 `receipt.normalized_hash` 缓存已解析的批次文档，docstring 写明"只复用哈希校验成功的读取；失败每次都走 damaged 路径"，且明确"reader 生命周期内复用，要看到更新的投递必须新建 reader"。
- `evidence.py:source_claim_acquisitions_many`：批内以 `content_by_hash` 去重读取与哈希校验。
- `acquisition.py:read_receipt_content(..., verified=...)`：显式参数，"收据校验照跑，`verified` 只共享同一调用方已经哈希校验过的字节"。
- `market_breadth.py:806-809`：`checked_normalized` 按 `normalized_hash` 跳过重复的 `item.normalized` 解析。
- `commodity_basket.py:728, 755`：`checked[ids]` 缓存同一组 `acquisition_ids` 的 document。

共同点是：**缓存的 key 是已经哈希校验过的内容摘要，作用域是一次一致读取，失败路径不进缓存**。3.1 里 `raw`/`normalized` 的自比问题，恰恰是这套模式覆盖不到的情形——因为那道校验比较的是两份内容本身。

---

## 四、给下一轮的落点

按"时间 × 安全度"排，不给未实测的收益数字：

1. **`registered_definitions`（实测 6.33 秒，重复率 99.995%，无自比风险）**——最干净的一处。约束是注册时点与返回列表的可变性，`shared_read_scope` 已经给出了适用条件。
2. **`_commodity_document`（实测约 53.6 秒）**——钱都在这里，但**不能靠"解析一次传对象"拿**。真要动，必须先处理 `document != json.loads(snapshot.normalized)` 这道校验的表达方式；沿用内容哈希缓存会让它在数据变成纯 ASCII 的那天静默失效。另外 `commodity_basket.py:649` 那条路径缺 `:745` 已有的 `checked[ids]` 式复用，这是一个**不触碰校验语义**的方向。
3. **其余全部调用点加起来实测约 0.5 秒**——`metric_series` 的 320,947 次尽管醒目，不值得为它改动任何校验相关的代码。
