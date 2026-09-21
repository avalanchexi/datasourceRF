# 发现：`_commodity_facts` 的开销不在"三处各走一遍"，而在循环里的不变量（2026-09-21）

只读调查。未修改任何源码、测试或配置。

依据：`tests/integration/test_worker_registered_catalog.py::test_full_worker_falls_back_to_official_ppi_and_exposes_delivery_in_report` 的 cProfile（`hot-test.pstats`），加上通读 `src/pring_cycle/commodity_basket.py` 与 `src/pring_cycle/futures_inputs.py`。

> 行号说明：profile 采集于安装进 dev-venv 的 **HEAD 版本**，其行号比当前工作树少约 55 行（工作树新增了 `_commodity_meaning_equal` 及其常量）。下文一律用**当前工作树**的行号；profile 输出里的 `376`/`383`/`569` 分别对应工作树的 `431`/`438`/`627`。委派任务中给出的 `377/406/465` 来自 `.scratch/wip-batches-20260914-superseded/commodity_basket.py`，是同一套代码的旧副本。

## 一、profile 说了什么

```
   ncalls  tottime   cumtime  函数
      440    3.973   322.563  _commodity_claims_valid   (工作树 627)
      440   12.412    84.991  _commodity_document       (工作树 438)
     1760    2.897    39.037  _commodity_publication    (工作树 431)
53848240/2200  24.631  28.069  _commodity_facts         (工作树 319)
     1760    0.026     0.028  _commodity_members        (工作树 329)
```

2200 个顶层入口**恰好**拆成两份：

| 入口 | 次数 | 占比 |
|---|---|---|
| `_commodity_publication` → `_commodity_facts` | 1760 | 80% |
| `_commodity_document` → `_commodity_facts` | 440 | 20% |

两者的调用方**都只有** `_commodity_claims_valid`（440 次）。`440 × (1 + 4) = 2200`：每次 `_commodity_claims_valid` 遍历 1 次文档、4 次发布时间。

`_persist_commodity_basket`（写入路径）在这个测试里一次都没进。`require_commodity_results` 同样没有出现在 `_commodity_publication` 的调用方里。

**所以：主要成本不是"三个调用点各走一遍同一个 result"，而是同一个调用点 `_commodity_publication` 在一个它并不改变的循环里被重复调用 4 倍。**

## 二、三个调用点的调用链与各自所需字段

### 调用点 A — `_commodity_publication`（`commodity_basket.py:432`）

```python
publications = [fact["public_available_at"] for fact in _commodity_facts(result)]
if not publications or any(t is None for t in publications):
    return None
return max(datetime.fromisoformat(t) for t in publications)
```

只取 `fact["public_available_at"]`，**直接下标，不是 `.get`**。

三条进入链：

1. `_commodity_claims_valid:682` —— 在 `for claim_id in claim_ids:` **循环体内部**。`result` 在循环前的 `:653` 绑定（`result = document["result"]`），循环体内**没有任何地方重新绑定或修改 `result`**。即：该调用对本组的每个 claim 都返回同一个值，是彻底的循环不变量。这一条贡献了 1742/1760 次调用。
2. `require_commodity_results:750` —— 同样在 `for claim in commodity:` 循环体内部。文档本身有 `checked[ids]` 缓存（`:743`），但 `_commodity_publication` 在缓存命中时仍然重算一遍。
3. `_persist_commodity_basket:522` —— 每次持久化调用一次，紧挨着调用点 C。

### 调用点 B — `_commodity_document`（`commodity_basket.py:461`）

```python
facts = _commodity_facts(result)
parents = {identity for fact in facts for identity in fact["acquisition_ids"]}      # :462
...
for digest in {h for fact in facts
               for key in ("raw_hashes", "evidence_hashes")
               for h in fact.get(key, [])}:                                          # :465-467
```

取 `fact["acquisition_ids"]`（下标）与 `fact.get("raw_hashes"/"evidence_hashes", [])`（带默认值）。用途：一是核对父采集集合（不符抛 `commodity_result_parent_mismatch`），二是逐个校验落盘原件的摘要（不符抛 `commodity_result_parent_original_invalid`）。

调用方：`_commodity_claims_valid:649`、`require_commodity_results:737`。两处都包在捕获 `(ValueError, KeyError, TypeError, LookupError, OSError)` 的 `try` 里。

### 调用点 C — `_persist_commodity_basket`（`commodity_basket.py:520`）

```python
facts = _commodity_facts(result)
parents = tuple(sorted({identity for fact in facts for identity in fact["acquisition_ids"]}))
published = _commodity_publication(result)     # :522
```

只取 `fact["acquisition_ids"]`。

### 结论（问题 1）

**不存在"三处在同一次处理中各遍历一次同一个 result"的情形。** 实际是两两成对、分处两条互不相交的路径：

- **写入路径**：C（`:520`）与 A（经 `:522`）背靠背遍历同一个 `result` 对象，中间无任何改动 → 确实是 2 次可以合并成 1 次。但该路径在被 profile 的测试里未被触发。
- **复核路径**：B（在 `_commodity_document` 内，对 `document["result"]`）与 A（`_commodity_claims_valid:682`，对 `:653` 取出的同一个 `document["result"]`，**同一对象**）遍历同一个 `result`；但 A 在每个 claim 上重复一次，所以是 `1 + N` 次而不是 2 次。这条路径贡献了全部 2200 次。

B 与 C 永远不会出现在同一次处理中（一个是复核读路径，一个是持久化写路径）。

## 三、一次遍历能否同时产出三处所需（问题 2）

可行。三处需要的都是对 fact 列表的**可折叠聚合**，互不干扰：

| 产物 | 折叠方式 | 谁需要 |
|---|---|---|
| `parents` 集合 | `acquisition_ids` 并集 | B、C |
| 原件摘要集合 | `raw_hashes` ∪ `evidence_hashes`（缺键按空） | B |
| 发布时间 | `public_available_at` 的"全非空则取 max，否则 None" | A |

没有任何一处需要 fact 的**顺序**或**完整列表**（B、C 只构造集合，A 只取 max 与判空），所以一次遍历直接产出三个聚合值、不物化列表，是成立的。

不过按第一节的数据，真正值钱的不是"B 与 A 合并"（能省 440 次），而是**把 A 从循环里提出来**（能省约 1320 次，占 2200 的 60%）。两者叠加可把 2200 降到 440。此处只陈述遍历次数，不预测耗时——实际收益必须重新测量。

## 四、合并时必须保持的语义约束（问题 3）

以下每条都是"合并遍历最容易写错"的点，逐条核对过源码。

### 1. `public_available_at` 的"一个为空则全体为空"

`_commodity_publication:433` 是 `if not publications or any(t is None for t in publications): return None`。两个条件是**分开的**：

- **fact 列表为空** → `None`（不是报错，也不是某个兜底时间）
- **任意一个 `public_available_at` 是 `None`** → 整体 `None`，**而不是跳过该 fact 再对其余取 max**

合并遍历若用"滚动 max"，必须**另立一个 `saw_none` 标志和一个 `saw_any` 标志**，不能写成 `max(t for t in ... if t is not None)`。后者在"部分为空"时会返回一个非 None 的时间，直接改变 `claim.release_at == published` / `claim.public_available_at == published` 的比对结果，让本应被拒的 claim 通过。

这个规则在上游 `futures_inputs.py:317-325` 构造 fact 时是同一套写法（`max(...) if all(... is not None) else None`），属于这条链上一贯的约定，不是偶然。

### 2. `fact["public_available_at"]` 的下标必须保持下标，不能换成 `.get`

A 用下标，缺键会抛 `KeyError`；B 对 hash 字段用 `.get(key, [])`，缺键按空处理。两者**不是同一种宽容度**，合并时不能统一成一种。

缺键与值为 `None` 在下游是两种不同结果：`None` 会正常返回并参与比对（大概率比对失败但走的是"不相等"分支）；`KeyError` 则被 `_commodity_claims_valid:695` / `require_commodity_results:765` 的 `except` 接住，走的是"跳过/判定无效"分支。把下标改成 `.get` 会把后者悄悄变成前者。

（补充事实：`futures_inputs.py` 的 `_fact()`（`:347-359`）总是写入 `public_available_at` 键，`:455` 的 session fact 也经由 `_fact` 构造。所以 `KeyError` 是针对外来/重建数据的防御路径，而不是常规路径——但它确实是当前语义的一部分。）

### 3. 遍历必须穷尽，不得提前退出

诱惑在于：一旦看到某个 `public_available_at` 为 `None`，发布时间就已经定死为 `None`，可以立刻返回。**不行**——同一次遍历还要为 B/C 收集 `acquisition_ids` 与原件摘要，提前退出会漏掉后面的 fact，导致 `commodity_result_parent_mismatch` 误报、以及部分原件不被校验（后者是安全性放松）。

### 4. 剪枝规则必须一字不差地保留

`_commodity_facts:321-322`：字典同时含 `kind` 与 `acquisition_ids` 时，**返回该字典本身并停止向下递归**，其子节点一律不看。这意味着嵌套在 fact 内部的 fact 是不可见的。合并实现若改用"先收集所有节点再筛选"，会多捞出被当前实现剪掉的节点，同时改变 parents 集合与发布时间 max。必须保持"命中即剪枝"。

### 5. 重复 fact 对象被计两次是当前行为，且无害

同一个 dict 对象若在结构中出现两次，当前实现会收集两次。三处消费者分别是集合并、集合并、max 与判空，都对重复不敏感。合并实现可以去重也可以不去重，但**不能因为去重而改变"fact 列表是否为空"的判断**（`not publications`）——只要至少有一个 fact，判空结果就不变，这一点去重不影响。

### 6. 错误抛出的时机会前移（复核路径特有）

若把 A 的计算并入 `_commodity_document` 内的那次遍历，`public_available_at` 缺键引发的 `KeyError` 会从 `_commodity_claims_valid:682`（在**每个 claim 的 try** 内，`continue` 只跳过该 claim）前移到 `:649`（在**整组的 try** 内，`continue` 跳过整组）。

逐条核对下来，对返回的 `valid` 集合**没有影响**：因为 A 是组内不变量，只要有一个 claim 走到 `:682` 会抛，同组其余 claim 也都会抛，结果都是无一进入 `valid`。至于那些在 `:657-662`（`definition_version` / `business_date` 不匹配）就提前 `continue`、根本走不到 `:682` 的 claim——它们本来就不会进入 `valid`，前移后仍然不会。

但**做的工作量会变**：前移后，`:664` 的 `calculate_commodity_basket` 重算可能不再发生。`expected_day` / `expected` 是跨组携带的循环变量，但它按 `period_end` 作键、每组开头会判断是否需要重算，跳过一整组不会污染下一组。因此这是"执行路径变化、返回值不变"，不是语义变化——但必须明确写下来，而不是默认它无害。

`require_commodity_results` 一侧不存在这个问题：B（`:737`）与 A（`:750`）在同一个 `try` 内，两者抛出的异常都被 `:765` 转成同一个 `ValueError("commodity_result_original_or_value_invalid")`。

### 7. 缓存不能按 `id(result)` 做

若打算把"每个 result 的遍历结果"缓存起来供 A 复用，不能用 `id(result)` 作键：`_commodity_claims_valid:653` 每组都重新绑定 `result`，旧对象被回收后 id 会被复用，可能把上一组的发布时间错配给下一组。安全的做法是把聚合结果显式地随 result 一起传递（或存进组的局部变量），而不是全局记忆化。

### 8. 两次遍历之间 `result` 确实未被改动（已核对）

- `_persist_commodity_basket`：`:520` 与 `:522` 之间无任何写入；`result` 随后在 `:528` 被放进 `document` 并序列化，也不改动它。
- `_commodity_claims_valid`：`:649`（`_commodity_document` 内部遍历）与 `:682` 之间，`document` / `result` 均未被写入。
- `require_commodity_results`：`:737` 与 `:750` 之间只有读取与比较（`:741` 的 `result != expected`），无写入。

所以"一次遍历的结果可以给后面用"这个前提成立。

## 五、结论

**可以安全合并，但要分两步、且第一步不是合并。**

1. **先把 `_commodity_publication` 从循环里提出来**（`_commodity_claims_valid:682`、`require_commodity_results:750`）。这是纯粹的不变量外提，不跨函数边界、不改错误时机——若采用"组内惰性算一次、仍留在原 `try` 位置"的写法，约束 6 完全不会被触及。按 profile，遍历次数从 2200 降到约 440。
2. **再考虑把 A 并入 B 那次遍历**，把剩下的 440 次降到 0 次额外遍历。这一步跨函数边界、会前移错误时机（约束 6），收益只有第一步的四分之一，风险更高。

`_persist_commodity_basket` 里 `:520` + `:522` 的合并是纯局部的、安全的，但在被 profile 的测试里不贡献任何次数，收益未经测量。

无论走哪一步，上面第 1、2、3、4 条约束都必须逐条对照实现来验：**"一个为空则全体为空"、下标与 `.get` 的宽容度差异、不得提前退出、命中即剪枝。**

不预测合并后的秒数。上面的次数是从 profile 直接读出的，耗时改善必须在改完后重新测。
