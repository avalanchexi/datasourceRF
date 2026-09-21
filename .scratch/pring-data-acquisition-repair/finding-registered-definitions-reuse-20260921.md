Status: ready-for-agent
Type: read-only-investigation
Date: 2026-09-21

# 发现：`registered_definitions` 可在 `shared_read_scope` 内安全复用

只读调查。未修改任何源码、测试或配置；未运行 pytest 或 `tools/check.py`。所有素材运行库均以
`mode=ro&immutable=1` 打开。

## 结论先说

**能安全复用。** 三问的答案：

1. **输入确实只有 `(已解析的 database_path, version)`。** 函数体（`catalog_registry.py:74-96`）不读时钟、
   不读环境变量、不读 `RuntimePaths`、不读 contextvar——该模块的全部 import 就是 `hashlib` / `json` /
   `sqlite3` / `Mapping` / `Path` / `Any`（`:5-10`）。它读的两张表在一个 Worker 作用域内都不会被写：
   唯一的写入点 `_register_admitted_catalog`（`:52`）经三跳只由 CLI 的 `model-source-certify` 到达，
   那条路不进任何 `shared_read_scope`。
2. **不会让任何校验失去意义。** 三道校验的两边分别是「同一行的两列」「另一张表的列 vs 函数参数」，
   没有一道是 `parse(A) != parse(B)` 那种会塌陷成自比的形状——这正是 `_commodity_document` 被否决的
   结构，此处不成立。`:95` 的 `json.loads(document)` 是一次**不参与任何比较**的独立解析。
3. **缓存值实测约 121 KB，一个作用域里只会有 1 份。** 不重蹈「要常驻 110 份快照（约 1.4 GB）」的覆辙：
   那一处的缓存值随日期变化且访问序是 `g00…g109 g00…g109`，这一处的缓存值既不随日期也不随 metric 变化。

需要点名的风险只有两条，都不是「不能做」，而是「做的时候不能顺手做另一件事」：**失败不入缓存**，
以及**不要把 `:95` 的独立解析省掉**（第二节第 3 小节）。

---

## 零、先纠一条行号

[JSON 解析调查](finding-json-decode-cost-20260921.md) 把这两次解析记作 `catalog_registry.py:106` + `:111`。
**这两行不存在。** 两次 `json.loads` 在当前 `src/` 是 **`:89`**（`manifest_json`）与 **`:95`**
（`definitions_json`）。核了三处：

- `catalog_registry.py` 在 git 里只有三个版本（`656eaa0` / `bda795f` / `26a0b84`，此后未再改），
  两次解析分别落在 86/92、87/93、89/95；
- 装机副本 `~/.local/share/pring-cycle/dev-venv/lib/python3.12/site-packages/pring_cycle/catalog_registry.py`
  与当前 `src/` `diff` 无差异；
- 全盘 716 份 `pring_cycle/catalog_registry.py`（含 `uv` 的 archive-v0 缓存），`json.loads` 出现过的
  行号集合是 {84, 86, 87, 89, 90, 92, 93, 95}，**没有 106，也没有 111**。

调用点的**归属**本身是对的——42,220 次约等于 2 × 两万余次 `registered_definitions`，两次解析确实都在
这一个函数里。只有行号要改。（`:111` 恰好是 `require_registered_manifest` 的 `def` 行，而 pstats 用
**函数定义行**标识调用方；`:106` 对不上任何 `def` 行，所以这只是一个可能的来源，不作断言。）

下文行号一律以当前 `src/` 为准。

---

## 一、输入面：只有 `(已解析的 database_path, version)`

### 1.1 逐句追踪 `catalog_registry.py:74-96`

| 行 | 读了什么 | 来源 |
|---|---|---|
| `:76` | `database_path.resolve().as_uri()` + `?mode=ro` | 文件系统（符号链接解析）+ 参数 |
| `:77-83` | 一条 SELECT，`registered_metric_catalog c JOIN model_version m`，参数只有 `(version,)` | 库 + 参数 |
| `:84-85` | `row is None` → `KeyError("unknown_metric_definition_version")` | — |
| `:86` | 拆出 `definitions_hash` / `definitions_json` / `manifest_json` | 上一步的行 |
| `:87-88` | `sha256(document.encode()).hexdigest() != digest` | 同一行的两列 |
| `:89` | `json.loads(admitted_manifest_json)` | `model_version.manifest_json` |
| `:90-94` | 两道比较（见第二节） | 两张表 + 参数 |
| `:95` | `json.loads(document)` | `registered_metric_catalog.definitions_json` |

没有第二个路径来源（对照 claims_valid 切片被审查指出的「键里没点名 `paths`」——此处确实只有
`database_path` 一个），没有 `as_of` / `mode` / metric，没有时钟。

### 1.2 它读的列在作用域内会不会变

- **`registered_metric_catalog`**：`src/` 里针对该表的唯一写语句是 `catalog_registry.py:68-71` 的
  `INSERT`；`:64-67` 在版本已存在且内容不一致时抛 `metric_catalog_version_is_immutable`。
  注意**这张表没有 SQL 触发器**（建表语句 `:32-39` 不含 `CREATE TRIGGER`，全仓也搜不到），
  它的不可变性是代码级的。但 `registered_definitions` 自己以 `mode=ro` 打开（`:76`），不可能写。
- **`model_version.manifest_json`**：有库级保护——`model_manifest_no_update`
  （`models.py:1280-1283`，`BEFORE UPDATE OF manifest_hash, manifest_json, certified_replay_start`）
  与 `model_version_no_delete`（`models.py:1284-1285`）。确实存在的 `UPDATE model_version` 只改
  `status`（`models.py:583`/`587` 在 `activate`，`models.py:980`/`984` 在 `rollback`），
  而 `status` **不在** `:78-81` 的 SELECT 列里。

### 1.3 作用域内会不会有人注册新版本

这是任务问的那一条：Worker run 确实会**采集证据**，那它会不会顺手注册或改写目录版本？

**不会。** 注册路径只有一条，三跳全是唯一调用方：

```
cli.py:436  model-source-certify --candidate-request-hash
  → candidate_admission.py:141  ModelRepository(...)._create_admitted_candidate(manifest)
    → models.py:294-303  _create_admitted_candidate（函数内 import，:297）
      → catalog_registry.py:52  _register_admitted_catalog
```

`src/` 里进入作用域的地方只有两处：`worker.py:189` 的 `with shared_read_scope()`（套在
`process_pending_run` 的一次 run 上，`:187-188` 的注释写明了理由），以及显式的包装
`futures_input_reads.py:116-121 shared_futures_input_reads()`。CLI 的准入命令不经过其中任何一处。

测试里开作用域的六处也都核过，没有一处在作用域内做准入：
`tests/adapters/test_futures_inputs.py:2074`、`tests/models/test_isolated_lifecycle.py:840`、
`tests/models/test_registered_commodity.py:77`/`:123`/`:126`/`:703`/`:764`——它们在作用域内做的是
`persist_commodity_basket` 与 `select_retrieval_input`，写的是 acquisition / claim，不是这两张表。

**但这是一条可达性论证，不是机制保证**（那张表没有触发器，见 1.2）。所以第四节把「失败不入缓存」
列为硬约束：缓存一个 `KeyError` 会把某个版本在整个作用域内永久钉成未知，而这恰恰是唯一能被
「作用域内注册」推翻的结论。

### 1.4 连接不是池化的

`storage.py:19-26` 的 `database_connection` 每次 `sqlite3.connect`（`:21`）、每次 `close`（`:26`）。
`worker.py:175` 的 `keep_database_open` 只是为了推迟 WAL 清理（`storage.py:30-39` 的 docstring
写明「callers keep using their own short-lived connections」），不复用连接。所以
「每次调用重开一次只读连接」属实，复用能省掉的不止是解析。

---

## 二、缓存会不会让某道校验失去意义

### 2.1 三道校验各自在比什么

| 校验 | 左边 | 右边 | 会不会塌陷成自比 |
|---|---|---|---|
| `:87-88` sha256 | `c.definitions_json` 现算的摘要 | `c.definitions_hash` 列 | 否（同一行的两**列**） |
| `:91` 版本一致 | `m.manifest_json` 的解析（`:89`） | 函数参数 `version` | 否（一边是参数） |
| `:92` 准入一致 | `m.manifest_json` 里的 `metric_definitions` 重新序列化 | `c.definitions_json` 原串 | 否（两张表的两列） |

**与 `_commodity_document` 的结构差异就在这里。** 那一处被否决，是因为校验写成
`json.loads(snapshot.raw) != json.loads(snapshot.normalized)`，两个操作数同源、今天只靠一个
`ensure_ascii` 的差别才没有变成同一串字节；一旦数据变成纯 ASCII，内容哈希缓存会把同一个对象还回来
两次，`document != document` 恒假（见 JSON 调查第 3.1 节）。这里没有任何一道比较的两边会收敛成
同一个对象：一边是函数参数，或是另一张表的另一列。

而 `:95` 的 `json.loads(document)` 是**第三次独立解析**，其产物**不参与上面任何一次比较**。
缓存它，等于缓存一个不被任何校验消费的值。

### 2.2 sha256 到底在守什么

它守的是 `registered_metric_catalog` 同一行内 `definitions_hash` 与 `definitions_json` 的一致性，
也就是「库文件被损坏或被手改」。它不守任何语义性质——`definitions_hash` 就是注册时对
`definitions_json` 算出来的（`:57-58`），两者由同一次写入产生。

实测（素材 `5d75499a…`）：`sha256(definitions_json) == definitions_hash` 为 True。

缓存之后，它在一个作用域内跑 1 次而不是两万余次。**这不是让它失效**，而是把「在同一次一致读里
重复校验同一行」省掉——`read_scope.py:3-7` 的 docstring 定义的正是这件事：作用域内可复用
「只依赖于 scope 内不会被采集或改写的输入」的结果。作用域之外每个调用方照旧重读重验（`:6-7`）。

### 2.3 唯一需要点名的下游，以及必须禁止的那一步「优化」

`require_registered_manifest:117-119`：

```python
definitions = registered_definitions(database_path, version)
if _definition_document(manifest["metric_definitions"]) != _definition_document(definitions):
    raise ValueError("model_metric_catalog_binding_mismatch")
```

这是全仓里唯一一处「把 `registered_definitions` 的返回值拿去做相等比较」的地方，所以逐条核过：

- 左边的 `manifest` 全部来自 `ModelRepository.manifest()`（`models.py:1040-1051`），每次都对
  `model_version.manifest_json` 现解析一次，**没有任何缓存**。四个调用点
  （`evidence.py:412`、`material_preflight.py:59`、`retrieval_ledger.py:69`、`search_evidence.py:89`）
  的 manifest 都是这么来的。
- 右边来自 `registered_metric_catalog.definitions_json`。
- 实测：`admitted["metric_definitions"] is json.loads(definitions_json)` 为 **False**——两张表的两列，
  不可能是同一个对象。

**因此缓存不会让它变成自比。** 但有一步将来很可能被当成顺手优化的重构必须禁止：

> **不要把 `:95` 的 `json.loads(document)` 换成直接返回 `:89` 已经解析好的
> `admitted["metric_definitions"]`。**

表面上「省一次 33 KB 的解析」，实际上返回值从此与 `model_version.manifest_json` 的解析同源。
那时只要有人再给 `ModelRepository.manifest` 加一层作用域缓存（是一个同样诱人的落点），而调用方
恰好就是当初的准入模型，上面 `:118` 的两边就会是同一个对象，`model_metric_catalog_binding_mismatch`
从此**不可达**。这就是 `_commodity_document` 那一型，只是需要两步才走到——记在这里，免得下一轮
分两次把它走完。

> **2026-09-21 两轴审查订正**：上面这段的因果写得太满。**仅给 `ModelRepository.manifest`
> 加缓存并不足以造成自比**——本函数 `:89` 自己解析一次 `admitted_manifest_json`，
> `ModelRepository.manifest`（`models.py:1048`）另行解析一次，两份独立解析不会因为其中一份被
> 缓存就共享身份。要让 `:118` 两边变成同一个对象，还需要两条路径共享同一个解析缓存（或同一个
> 对象）。**禁令本身保留**——它防的是一条只需再走一步的路——但理由不能写成必然事实。
> 实现里那条注释已按此改正。

还有一条同型的：实测 `_definition_document(json.loads(document)) == document` 成立（素材
`5d75499a…`），因为定义里的值类型集合实测为 `{str, list}`、list 里也只有 `str`。但这是**素材的性质，
不是结构保证**——`definitions_json` 是从 manifest 里原样搬来的 JSON（`:57`），没有任何地方拿
`MetricDefinition` 的字段表去约束它，混进一个浮点数就不再幂等。所以**不要**用存库的 `document`
字符串替代 `:118` 右边的 `_definition_document(definitions)`；要换必须先有测试钉住幂等。

> **2026-09-21 两轴审查订正**：「混进一个浮点数就不再幂等」这个具体反例**不成立**——审查方用内存
> 探针实测，含 `0.1` 的定义经序列化→解析→再序列化仍得到同一字符串。禁令保留（幂等确实没有任何
> 结构保证，只是素材的性质），但不要再引用这个反例。

### 2.4 可变性：一条需要新写下来的不变量

返回的 `list[dict]` 可变且直接暴露。三个调用方逐个核过，今天全都只读：

- `registered_metric_definition:102-107`：`values = dict(definition)` 是浅拷贝，`:105-106` 把四个容器
  字段**在副本上**重赋成 `tuple`，原 dict 不被改动。`MetricDefinition` 是
  `@dataclass(frozen=True)`（`catalog.py:19-35`），15 个字段里容器恰好只有 `dimensions` /
  `source_codes` / `source_candidates` / `allowed_units` 这四个——**就是 `:105` 列举的那四个**。
  所以构造出来的 `MetricDefinition` 不持有缓存结构里的任何可变对象。
  （实测素材里每条定义的键集合正是这 15 个，与 dataclass 字段一一对应。）
- `require_registered_manifest:118`：`_definition_document` 里 `sorted()` 返新表（`:44`），
  `json.dumps` 只读。
- `worker.py:1451`：只遍历读 `definition["metric_id"]`。

共享之后，「调用方不得改动返回值」会变成一条**没有任何机制保证的新不变量**——与已实施切片把
`members` 收成 `tuple`、并在 frozen dataclass 的 docstring 里写明只读，是同一型问题
（[claims_valid 调查](finding-claims-valid-cost-20260921.md) 两轴审查一节）。第四节给了一个能让这条
不变量消失的选项。

---

## 三、缓存值有多大、一个作用域能攒多少份

### 3.1 实测

逐个只读打开 `~/.cache/pring-cycle/test-materials/*/runtime/data/pring-cycle.sqlite3`（9 份，
`mode=ro&immutable=1`）：

| 素材 profile | `registered_metric_catalog` 行数 | `definitions_json` | 定义条数 | `manifest_json` | 解析结果深度 sizeof |
|---|---:|---:|---:|---:|---:|
| `…-isolated-lifecycle`（6 份） | **1** | 33,831 B | 61 | 40,458 B | **124,343 B** |
| `…-integrated-acquisition`（3 份） | **1** | 33,303 B | 59 | 40,199 B | **121,074 B** |

（深度 sizeof 按 `id()` 去重，所以共享/驻留的短字符串只计一次。`model_version` 每份素材 4 行。）

**一份缓存值约 121 KB。**

### 3.2 一个作用域里能有几份

一份对应一个 `(已解析 database_path, version)`：

- **一个 `database_path`**：`worker.py:189` 的作用域套在 `process_pending_run` 的一次 run 上，
  只有一个 `paths.database`。
- **能走到这个函数的 version 只有非内建的**：`catalog.py:397-413` 先查四个内建目录的字典，命中就
  完全不碰库；`catalog is None` 且给了 `database_path` 才转 `registered_metric_definition`
  （`:411-413`）。`require_registered_manifest:113-116` 同样对内建版本直接返回。
- **一次 run 的目录版本是钉住的**：`retrieval_ledger.py:67-68` 在 manifest 的
  `metric_catalog_version` 与 run 的 `definition_version` 不符时抛 `retrieval_catalog_model_mismatch`。
- 实测素材里 `source_claim` 的 `definition_version` 只有两个值，其中 `metric-catalog-v0001` 是内建
  （不进库）。

**所以实际就是 1 份。** 上界是库里注册过的目录版本行数（素材里是 1），**不随日期或 metric 增长**。

### 3.3 与 A 组那道坎的对比

被否掉的不是「缓存太大」，而是「**访问序**决定了必须常驻多少份」：`_commodity_document` 的调用序是
`g00 g01 … g109 g00 g01 …`，同一组两次解析的间隔恒定为 110，定长缓存留 1/2/4/8/16 份命中全是 0，
要吃掉重复必须留住全部 110 份、约 1.4 GB（[claims_valid 调查](finding-claims-valid-cost-20260921.md)
第三节）。

这里没有这个形状：缓存值既不随日期也不随 metric 变化，**一份就把全部调用吃掉**。121 KB 与 1.4 GB
差四个量级。

### 3.4 谁在反复调用（决定缓存放在哪一层）

按调用图分两类：

- **run 级 / selector 级，次数很少**：`require_registered_manifest` 的四个调用点
  （`evidence.py:412`、`material_preflight.py:59`、`retrieval_ledger.py:69`、`search_evidence.py:89`）
  都在一次 run 或一次 `ModelInputSelector` 构造里；`worker.py:1451` 在
  `refresh_context_sources` 里，一次 run 一次。
- **按 metric、按 claim 反复走**：`metric_definition(..., database_path=...)` →
  `catalog.py:413` → `registered_metric_definition` → `registered_definitions`。热的是
  `evidence.py:1374` 的 `_validate_claim`（每条 claim 一次）、`search_evidence.py:322`
  （`ModelInputSelector.select` 里每个 metric 一次）、`commodity_basket.py:553`（每个 member 一次）。

JSON 调查的计数与之相符：`registered_definitions` 约 21,118 次、`_definition_document` 约 21,140 次，
差 22——而 `require_registered_manifest` 每次要调 `_definition_document` **两**次（`:118`）。
也就是说 `require_registered_manifest` 在那一轮里只跑了十来次，两万余次几乎全部来自
`registered_metric_definition`。（这两个数与 42,220 之间有十几次的零头对不齐，来自不同轮次的计数，
所以只作旁证，不据此下结论。）

---

## 四、落点

**能否安全复用：能。**

### 4.1 缓存键

```
(str(database_path.resolve()), version)
```

把这个函数读到的每一样东西都点名了：

- `str(database_path.resolve())`——`:76` 自己就是用 `resolve().as_uri()` 打开的，键必须用同一份解析
  结果，否则两个指向同一文件的不同写法会各占一份（安全但白费）；用 `str` 而非 `Path` 是为了让
  「相对路径 + 进程内 chdir」不至于把两个不同文件映到同一个键。
- `version`——`:82` 的唯一查询参数。
- **没有第三样**。该模块 import 只有 `hashlib` / `json` / `sqlite3` / `Mapping` / `Path` / `Any`
  （`:5-10`）：没有时钟、没有环境变量、没有 `RuntimePaths`、没有 contextvar。这一条是
  claims_valid 那次审查「键里没点名 `paths`」的对照项，此处逐句核过，确认没有第二个路径来源。

### 4.2 缓存什么

**推荐两层，共用同一个键前缀：**

1. **外层**：`registered_definitions` 的返回值，即 `:95` 的解析结果（约 121 KB / 份）。覆盖全部
   调用方。代价是 2.4 节那条「返回值只读」的新不变量。
2. **内层（可选，覆盖热路径）**：在 `registered_metric_definition` 一层缓存
   `dict[metric_id, MetricDefinition]`，由外层条目派生。`MetricDefinition` 是 frozen dataclass、
   字段全是 `str` 与 `tuple[str, ...]`（`catalog.py:19-35`），**天然只读，不需要新增任何不变量**；
   顺带还省掉 `:102` 每次对 61 条定义的线性扫描。

若只做一层，**做外层**——内层覆盖不到 `require_registered_manifest:117` 与 `worker.py:1451`。

机制用 `read_scope.scope_cache`（`read_scope.py:32-35`），返回 `None` 时不缓存、退回现行行为，
先例见 `futures_input_reads.py:125-127`。**不要**用进程级全局缓存。

### 4.3 什么绝对不能缓存

1. **任何失败。** `KeyError("unknown_metric_definition_version")`（`:85`）、
   `ValueError("registered_metric_catalog_hash_mismatch")`（`:88`）、
   `ValueError("registered_metric_catalog_admission_mismatch")`（`:94`），一律不入缓存。两条理由都要记：
   - 注册是一次库内写入（`:68-71`）。今天它不可能发生在作用域内（1.3 节），但那是**可达性论证而非
     机制保证**——那张表连触发器都没有。缓存一个 `KeyError` 会把某个后来变成已知的版本在整个
     作用域内永久钉成未知。
   - 与已实施切片同理：记住失败会改变后续调用**看见错误的时机**
     （[claims_valid 调查](finding-claims-valid-cost-20260921.md) 第五节）。
2. **不要用存库的 `document` 字符串替代 `_definition_document(definitions)`**（2.3 节）。
3. **不要把 `:95` 的独立解析换成返回 `:89` 的 `admitted["metric_definitions"]`**（2.3 节）。

---

## 五、下一切片必须在测试里钉住什么

按已实施切片的做法，红测试先行（每条都应能在不跑重型套件的前提下验证）：

1. **一个作用域内只查一次库。** 在一个 `shared_read_scope()` 内，对同一个 `(paths.database, version)`
   取两个不同 metric 的定义，断言 `registered_metric_catalog` 只被查询 **1** 次（包
   `catalog_registry.database_connection` 或数 `sqlite3.connect` 皆可），且两次得到的
   `MetricDefinition` 相等。改前 2、改后 1。
2. **作用域外不复用。** 同样两次调用，不开作用域，断言查询 **2** 次。这钉住 `scope_cache` 返回
   `None` 时退回现行行为（`read_scope.py:34-35`，先例 `futures_input_reads.py:126-127`）。
3. **失败不入缓存。** 在一个作用域内先用一个未注册的 version 调一次、断言抛
   `KeyError("unknown_metric_definition_version")`；**同一作用域内**再调一次，断言仍然抛同一个
   `KeyError` **且库被再查了一次**——失败没有被记住。这条把
   `tests/integration/test_database_lifetime.py:150` 已经钉住的「未注册目录必须始终不可用」搬进作用域内。
4. **跨作用域不复用，校验不是一次性通行证。** 在第一个作用域里正常读一次；改坏
   `registered_metric_catalog` 的 `definitions_json`（或 `definitions_hash`）后**新开**一个作用域，
   断言 `registered_metric_catalog_hash_mismatch` 照常抛出。这条证明 `:87-88` 没有被缓存变成
   「验过一次就永远算验过」。
5. **返回值只读。** 若采用外层列表缓存，断言同一作用域内两次调用返回同一个对象，并在 docstring 里
   写明它必须保持只读（对照已实施切片给 `members` 加的那条说明）；若只做内层 `MetricDefinition`
   投影，frozen dataclass 已经保证，断言两次取到的对象相等即可。

另外：`tests/integration/test_database_lifetime.py:90-155` 那段子进程只读巡检**不在任何作用域内**，
因此行为不应改变；它同时是「读取不得建库、不得留连接」的守卫（`storage.py:19-26` 每次
connect/close），改完应确认它仍然通过。

---

## 六、不预测收益

JSON 调查实测的 **6.33 秒**是**已经发生的**解析耗时，不是改完能省下的秒数。每次调用还有
`sqlite3.connect` + 查询 + `close`（`storage.py:21`/`:26`）与一次 sha256，这两项均未单独实测。
本文件不给预测数字——实际收益须改完在同一口径下重测。

完整套件按 [ADR-0014](../../docs/adr/0014-full-suite-only-at-freeze-points.md) 留待显式冻结节点，
本文件不宣称全套结论。
