Status: ready-for-agent
Type: read-only-investigation
Date: 2026-09-21

# 发现：`_commodity_claims_valid` 的 440 次里，110 个快照各被检查了四遍

只读调查。未修改任何源码、测试或配置；探针只在运行时包装模块属性，不落盘到仓库，材料身份（安装包树的哈希）不变，素材缓存命中、未触发重建。

## 结论先说

[#22 票](issues/22-live-acceptance-cutover.md) 2026-09-21 记下的线索是「去重机制 `claims_checked_once` 的 `context` 可能从不命中，或 `scope_cache` 返回 `None` 时完全不去重」。**两条都不成立**：

- 探针记录的 720 次 `claims_checked_once` 调用，`in_scope` **全部**为 `True`——`shared_read_scope` 覆盖到位，没有一次退化成不去重。
- 其中 **280 次（39%）全部命中缓存**，一次实际检查都没触发。去重机制按设计在工作。

真正的成本来自别处：440 次实际检查覆盖的只有 **110 个不同的日快照**，每一个被检查了 **4 遍**。4 = 2 个 metric × 2 次 `process_pending_run`。

**跨 run 的那一倍不可省**（两次 run 各有自己的读作用域，这正是 `shared_read_scope` 的边界）。**同一 run 内 metric 之间的那一倍是纯重复**：`CN_COMMODITY_EX_HOG_BASKET` 与 `CN_COMMODITY_SLEEVE_CONTRIBUTION` 是两次独立调用，各自解析同一天的同一份快照、各自重算同一天的篮子，得到逐字节相同的结果。

因此票面「在查清之前不得据此改动缓存键」的约束可以解除——**不需要改任何缓存键**。缓存键是对的；缺的是 `require_commodity_results` 里已有、而这条路径上没有的那层按 `acquisition_ids` 的复用。

## 一、测量方式

热用例 `tests/integration/test_worker_registered_catalog.py::test_full_worker_falls_back_to_official_ppi_and_exposes_delivery_in_report`，无 cProfile，用运行时包装记录每次调用的参数摘要与自身耗时。

- 解释器：`~/.local/share/pring-cycle/dev-venv`（CPython 3.12.12），安装副本与 `src/` 逐字节一致（`diff -rq` 仅 `__pycache__` 差异，不计入 `_tree_hash`）。
- 素材：`isolated_lifecycle_material`，profile `legacy`，`code_hash` `94bf35ad…`，命中已存的 `5d75499a…`，未重建。
- 本轮耗时 **248.00 秒**（`call` 阶段）。作为对照，票面记录的同用例无探针基线为 261.54 秒，带 cProfile 为 471 秒。**探针开销不显著；profile 的 471 秒不可与这些数字混用。**

被包装的是 `commodity_basket` 的模块属性 `commodity_claims_matching_acquisitions`、`claims_checked_once`、`_commodity_claims_valid`、`_commodity_document`、`calculate_commodity_basket`。四处调用点都通过模块全局名或函数内 import 解析，包装全部生效（事件计数自洽：`entry` 720 = `checked_once` 720，`valid` = `document` = `calculate` = 440）。

## 二、实测

| 项 | 次数 | 合计秒 | 中位秒 | 不同输入 |
|---|---:|---:|---:|---|
| `commodity_claims_matching_acquisitions`（入口） | 720 | 147.34 | 0.1709 | — |
| └ 其中全部命中缓存、未触发检查 | 280 | ≈0 | — | — |
| `_commodity_claims_valid` | 440 | **147.26** | 0.3339 | 110 天 × 2 metric × 2 run |
| `_commodity_document` | 440 | 72.30 | 0.1676 | **110 个 acquisition 组** |
| `calculate_commodity_basket` | 440 | 31.88 | 0.0609 | **110 天 × 2 个 as_of** |

`_commodity_claims_valid` 占用例 `call` 阶段的 **59.4%**（147.26 / 248.00）。票面记的 68% 取自 cProfile 的 `cumtime` 比值，两者口径不同，不冲突也不可互换。

`entry` 的 147.34 秒与 `valid` 的 147.26 秒几乎相等，说明入口本身（含 `claims_checked_once`、`selected` 字典构造）开销可忽略，成本全在实际检查里。

### 每次调用的形状完全规整

- `valid` 每次只覆盖 **1 个** `period_end`（440/440）。
- 每次带的 claim 数：`CN_COMMODITY_EX_HOG_BASKET` 恒为 1，`CN_COMMODITY_SLEEVE_CONTRIBUTION` 恒为 7（七个 sleeve）。
- 两次 run 各 220 次 `valid`，各覆盖同样的 110 个 `period_end`，每个 metric 各 110 次。
- 每个 acquisition 组被 `_commodity_document` 解析 **恰好 4 次**（110 组 × 4 = 440，无例外）。
- 每个 `(business_date, as_of)` 被 `calculate_commodity_basket` 重算 **恰好 2 次**（220 组 × 2 = 440，无例外）。

那个「2」就是两个 metric；`as_of` 在一次 run 内恒定，两个不同的 `as_of` 对应两次 `process_pending_run`。

### 同一 run 内的重复，按已发生的耗时计

保留每组首次、把该 run 内的后续重复计为可省：

| run | `document` 重复 | `calculate` 重复 |
|---|---|---|
| 第一次 `process_pending_run` | 110 次 / 18.71 秒 | 110 次 / 6.15 秒 |
| 第二次 `process_pending_run` | 110 次 / 17.83 秒 | 110 次 / 6.14 秒 |
| 合计 | **220 次 / 36.54 秒** | **220 次 / 12.29 秒** |

合计 **440 次 / 48.83 秒**，占本轮 248.00 秒的 **19.7%**。这是**已经发生的**耗时，不是预测；去掉这些调用后实际能省多少，必须改完重测。

（`calculate` 第一次 run 19.70 秒、第二次 12.17 秒，差额主要来自单次最大 3.08 秒的冷启动，不影响重复部分的对称性。）

## 三、为什么跨 metric 复用是安全的

`_commodity_document(inputs, artifacts)` 的输入只有 `inputs`（由 `acquisition_ids` 唯一确定）与 `artifacts` 根，**不含 `as_of`、`mode` 或 metric**。同一组 `acquisition_ids` 在同一个读作用域内必然产出同一份 document——作用域的前提就是其内部既不捕获也不改动这些原件（`read_scope.py` 的模块 docstring）。

`calculate_commodity_basket(paths, business_date=…, mode=…, as_of=…)` 同样不含 metric。同一 run 内 `mode` 与 `as_of` 恒定，因此 `(business_date)` 已足以定键。

这与 [JSON 解析调查](finding-json-decode-cost-20260921.md) 判定为**不安全**的那种缓存不是一回事：那里被否决的是**按内容哈希**缓存解析结果，它会让 `document != json.loads(snapshot.normalized)` 在数据变成纯 ASCII 的那天静默失效。按 `acquisition_ids` 复用不触碰这道校验——**校验仍在首次解析时照常执行**，复用的是「这组原件已验过、结果是这份 document」这一结论，而不是绕过验证。

先例就在同一文件里：`require_commodity_results:728` 的 `checked[ids]` 正是这层复用，只是它的作用域是单次函数调用，而 `commodity_claims_matching_acquisitions` 这条路径上没有。

### 但「照搬 `checked[ids]`」在这里会撑爆内存

`require_commodity_results` 能直接把 `document` 存进 `checked[ids]`，是因为它一次只处理一批 claim。这条路径不行，原因是访问顺序：

**同一个 acquisition 组的两次解析，间隔恒定为 110 次**（330 个间隔全部等于 110，无一例外）。调用序是 `g00 g01 … g109 g00 g01 …`——`full_retrieval` 的计划把 metric 排在外层、日期排在内层，所以一个 metric 的 110 天全部走完，才轮到第二个 metric 从第一天重来。

按这个序列模拟定长缓存：

| 保留最近 N 份 | 命中 |
|---:|---:|
| 1 / 2 / 3 / 4 / 8 / 16 | **0** |
| 110 | 330 |

也就是说，要吃掉这些重复，必须把 **110 份 document 全部留住**。快照中位 12.6 MB、最大 24 MB，那是约 **1.4 GB** 常驻——而 `_commodity_claims_valid` 现有注释写明的正是相反的约束：*at most one snapshot and one day's recalculation are held*。在这台 9.7 GB 的机器上，这个代价不能换那 36 秒。

`expected`（重算结果）同理，不能按天缓存。

### 可行的是缓存「结论」而不是「材料」

`_commodity_claims_valid` 从一份 document 里真正用到的只有五样东西，全都很小：

- `document["definition_version"]`、`document["business_date"]`——两个字符串；
- `_commodity_members(result)`——**新建**的 8 个字典，字段全是标量，不持有 `result` 的任何子结构；
- `_commodity_publication(result)`——一个 `datetime` 或 `None`；
- `agreement`——一个 `bool`。

把这五样留下、把 document 与 `expected` 丢掉，每天约 1 KB，110 天约 110 KB。内存约束依然成立：**作用域里从不驻留快照，也从不驻留重算结果**。

## 四、调用点：全部来自 `ModelInputSelector.select`，一个 scope 一个 metric

第二轮运行加记调用栈，结果与第一轮逐项一致（440 / 440 / 440 / 720 / 720，本轮 252.05 秒）。**720 次入口调用的栈完全相同，无第二个来源**：

```
search_evidence.py:312:select  →  :315:<genexpr>  →  :286:<lambda>（commodity family）
    →  commodity_basket.py:608:commodity_claims_matching_acquisitions
        →  :612:<lambda>  →  _commodity_claims_valid  →  :671:calculate_commodity_basket
```

这否掉了另一个看似合理的嫌疑：`model_evaluation.py:846` 那个 `for cutoff in cutoffs:` 的逐日复核循环**根本不在 Worker 路径上**——它只属于 `evaluate_context_replay`，而后者在 `src/` 里没有任何调用方，只有测试调用。Worker 这条路上的 440 次与它无关。

关键结构：`_claim_families` 的 commodity family 本可以批量处理（`series_by_metric(metric_ids)` 接受多个 metric），但 `select` 拿到的 `scope.metric_ids` 实际上**每个 scope 只有一个 metric**（`full_retrieval.py:251` 是 `(definition.metric_id,)`，`:403` 是 `(metric,)`）。所以两个 commodity metric 永远落在两个不同的 scope、两次不同的 `select`、两次不同的入口调用里——**它们之间不可能靠「合并一次调用」来共享**，只能靠作用域级的复用。

### 每次 run 的入口请求与缓存吸收

| | 第一次 `process_pending_run` | 第二次 |
|---|---:|---:|
| 入口调用 | 240 | 480 |
| 不同 `(metric, claim 集)` 组合 | 222 | 222 |
| 每组合被请求 | 220 组各 1 次；2 个空集组各 10 次 | 220 组各 2 次；2 个空集组各 20 次 |
| 触发实际检查 | 220 | 220 |
| 被 `claims_checked_once` 吸收 | 20（全是空集） | 260 |

两次 run 的 `as_of` 不同，缓存不跨 run——这是设计。**第二次 run 内部的 220 次重复请求被缓存完整吸收**，一次检查都没多做。440 次实际检查按 `asked` 分布为 220 次 ×1 个 claim（`CN_COMMODITY_EX_HOG_BASKET`）与 220 次 ×7 个 claim（`CN_COMMODITY_SLEEVE_CONTRIBUTION` 的七个 sleeve），与 110 个交易日 × 2 metric × 2 run 精确吻合。

## 五、给下一切片的落点

**不要改 `claims_checked_once` 的 context。** 它是对的，而且实测证明它在吸收该吸收的那部分。按 claim 去重无法消除这里的重复，因为两个 metric 的 claim **本来就是不同的 claim**，各自都必须被检查一次；重复的不是「检查哪个 claim」，而是检查过程中各自重做的那两件与 metric 无关的工作。

落点是在 `_commodity_claims_valid` 内把「这一天的快照说了什么」提到作用域级，用 `read_scope.scope_cache`（返回 `None` 时不缓存、退回现行行为，先例见 `futures_input_reads.py:125`），缓存上一节那五个小字段而非 document 与 `expected` 本身。

必须保留的语义：

- **首次仍走完整的 `_commodity_document`**：`document != json.loads(snapshot.normalized)`、`schema_version`、`provider`、`parser_version`、`result_hash` 五道校验一个不少。缓存的是**已经验过**这一结论，不是跳过验证。这与 [JSON 解析调查](finding-json-decode-cost-20260921.md) 否决的那种按内容哈希的缓存不同——那一种会让 `!=` 校验在数据变成纯 ASCII 时静默失效，这一种不触碰校验的表达方式。
- **失败不入缓存**：`_commodity_document` 抛错时现行行为是 `continue`（跳过该组），把失败记进缓存会改变后续调用的错误时机。只缓存成功的 verdict；失败路径仍会重复解析，代价由少数派承担。
- **重算保持惰性**：一份 definition 或 period 都对不上的快照，现在不会走到 `calculate_commodity_basket`，改后也不能走到。因此判定「是否需要重算」的 `definition_version` 与该组的 `period_end` 集合都必须进缓存键。
- **`expected` 仍只持有一天**：`expected_day` / `expected` 的「释放上一天再重算」保留为一次调用内的局部复用，不提升到作用域。

### 已实施（2026-09-21）

`commodity_basket.py` 新增 `_commodity_group_verdict`，`_commodity_claims_valid` 改为按
`(artifacts, acquisition_ids, definition_version, mode, as_of, periods)` 取用作用域内的 verdict。
`expected_for` 闭包承接原有的单日持有逻辑。

红测试：`test_one_read_shares_a_day_s_original_and_recalculation_across_commodity_metrics`
（`tests/models/test_registered_commodity.py`）——在一个 `shared_read_scope` 内按 Worker 的方式
逐 metric 各做一次 `select_retrieval_input`，断言同一天只解析一次原件、只重算一次。
改前 `2 == 1` 失败，改后通过。

已完成的验证：

| 范围 | 结果 |
| --- | --- |
| `test_registered_commodity.py` + `adapters/test_commodity_basket.py` | 34 passed / 36.92 秒 |
| `integration/test_full_run_retrieval.py` + `models/test_candidate_replay.py`（`select` 与回放两条调用路径） | 110 passed / 581.73 秒 |
| mypy（`uv run --no-editable`） | 102 source files，无问题 |
| ruff check `src tests tools` | 通过 |
| ruff format --check（本轮两个改动文件） | 已格式化 |

受影响的重型验收 `integration/test_worker_registered_catalog.py`（`tools/check.py` 的 `HEAVY_FILES` 之一）
跑过两轮，都是 10 passed：两轴审查前 2075.62 秒，审查调整定稿后 **1963.61 秒**。两轮都含素材重建
（每次重装都改变 `code_hash`；[JSON 解析调查](finding-json-decode-cost-20260921.md) 记录过的那次
「构建存进 A、调用方期待 B」的 `FileNotFoundError` 两轮均未出现）。最终收据对应的是本文件描述的定稿代码。

完整套件按 [ADR-0014](../../docs/adr/0014-full-suite-only-at-freeze-points.md) 留待显式冻结节点，
本文件不宣称全套结论。

### 改后复测：重复确实消失了，按次数而不只是按秒数

同一探针、同一用例再跑一次：

| | 改前 | 改后 |
| --- | ---: | ---: |
| `_commodity_document` | 440（110 组 × **4**） | **220**（110 组 × **2**） |
| `calculate_commodity_basket` | 440 | **220** |
| `_commodity_claims_valid` | 440 | 440（不变） |
| 入口 / `claims_checked_once` | 720 / 720 | 720 / 720（不变） |
| `_commodity_claims_valid` 合计耗时 | 156.53 秒 | **80.95 秒** |
| 其中 `document` | 77.42 秒 | 35.37 秒 |
| 其中 `calculate` | 34.70 秒 | 18.79 秒 |

剩下的「×2」正是两次 `process_pending_run`——跨作用域不复用，与设计一致。入口与去重调用次数一个没变，
说明省掉的全部是同一作用域内的重复，选择逻辑本身未被改动。

### 用例耗时

| 口径 | 改前 | 改后 |
| --- | ---: | ---: |
| 单独运行，带探针 | 248.00 / 252.05 秒 | **174.38 秒** |
| 单独运行，无探针 | 261.54 秒（票面记录，更早的一次测量） | **166.36 秒** |
| 整个重型文件内运行 | — | 188.30 秒（审查前）/ 170.24 秒（定稿） |

同口径（单独运行、带探针）为 252.05 → 174.38 秒。**不同口径之间不可相减**：探针有开销，文件内运行的
缓存状态也与单独运行不同，上表三行各自成对比较。这些数字来自这台机器的这几次运行，不保证其他环境。

**执行路径变化、返回值不变**，共三处，都因为 group 层的工作移进了 group 层的 `try`：

1. `agreement` 原先在 per-claim 的 `try` 内计算（异常只跳过该 claim），现在在 group 层（异常跳过整组）。
2. `published` 同上。
3. `calculate_commodity_basket` 的失败原先由同组下一个 claim 重试，现在整组跳过。

逐条核对下来 `valid` 集合都不变：三者都是组内不变量，同组任一 claim 会抛，其余也都会抛，结果都是
无一进入 `valid`；而在 `definition_version` / `business_date` 处就提前 `continue` 的 claim 本来
也不会进入。第 3 条还有一层——重试用的是同一天、同一 `mode`/`as_of`，重试必然同样失败，所以省掉的
是一次注定失败的重算。原注释「a failed recalculation is retried」因此不再属实，已改为
「Release the previous day before rebuilding another one.」。这与
[facts 遍历调查](finding-commodity-facts-cost-20260921.md) 约束 6 分析过的是同一型。

### 两轴审查后的调整（2026-09-21）

规格轴与标准轴各查出一条真问题，都已修：

- **「失败不入缓存」当时只有实现、没有测试**。补 `test_a_damaged_original_is_read_again_by_the_next_metric_in_one_read`：
  破坏当天原件后，在一个作用域内两个 metric 各取一次，断言原件被读了 **2 次**（失败没被记住）
  且两次都不采纳该天的 claim。为确认这条测试真能挡住回归，临时把失败也写进缓存跑了一次，
  测试如期变红（`1 == 2`），随后还原。
- **`calculate_commodity_basket` 不再组内重试，而注释仍说会重试**——见上面第 3 条。
- **缓存键没有点名 `paths`**。`expected_for` 闭包读 `paths`，而键里只有 `str(artifacts)`；
  两者今天必然一致（`commodity_claims_matching_acquisitions` 以 `database_path.parent` 构造
  `paths`，并用 `commodity_artifact_root_mismatch` 守住），但那是一条没写在键上的不变量。
  键已补上 `str(paths.database)`。
- **`dict[str, Any]` 换成 `_CommodityGroupVerdict`（frozen dataclass）**，`members` 收为 `tuple`。
  顺带说明一件事：缓存后 `members` 是**跨调用共享**的对象，不再是每个调用方各建一份，
  dataclass 的 docstring 写明它必须保持只读。

审查提出但未采纳的几条，理由记在此处以免下轮重查：`periods` 留在缓存键里是保持重算惰性的代价，
不同 period 集合导致的未命中是安全的（重算一次，结果不变）；per-claim 循环里对
`definition_version` 的再次比较是原有的防御性检查，删掉会让这段代码改为依赖「`agreement` 为真
蕴含 definition 匹配」的间接推理；与 `require_commodity_results` 的 `checked[ids]` 合并成一处
属于另一切片（已列在「仍开放」）。

### 明确不做

- 不改 `claims_checked_once` 的 context 或 `shared_read_scope` 的边界。
- 不缓存 document 或 `expected` 本身——上一节的间隔实测说明那需要 110 份常驻。
- 不合并两个 metric 的 scope：scope 的粒度由 `full_retrieval` 的计划决定，为省时间去改它会改变检索计划的语义。
- 不把跨 run 的那一倍也缓存掉：两次 `process_pending_run` 是两次独立的一致读，跨越它去复用正是 `read_scope` 的 docstring 禁止的。
- 不预测改完之后的秒数。上面的秒数都是**这两轮里已经发生的**重复调用自身的耗时；实际收益须改完重测。
