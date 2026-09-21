Status: ready-for-agent
Type: read-only-survey
Date: 2026-09-21


> **2026-09-22 订正**：本盘点是在「#27 尚未动手」的假设下做的，**该前提已不成立**——身份迁移
> 软件已由五个提交落地（`61de7e0`、`06bccc3`、`dc44076`、`26a0b84`、`fd330c2`）。下列各道闸的
> **真实性不受影响**，但「仍待迁移方案解决」的说法要换成「已由『保留旧输入、另建候选范围』的方案
> 处理」，逐条见[事实对齐](finding-27-migration-facts-20260922.md)。另外文中「18 个模型、7 个投影、
> 六项零声明」是当时的生产库快照，未重新查询，不可当作今日事实引用。
# 盘点：#27 五项 P2 身份变更的迁移影响面

为[票27](issues/27-metric-identity-corrections.md)与[规格24](spec-24-source-identity-20260917.md)第三、四节准备。
**只给影响面，不给方案**——重命名怎么做、按什么顺序做，归 `/implement` 那一刀。

只读调查。未修改 `src/`、`tests/`、`tools/` 任何一行；未跑 pytest 或 `tools/check.py`。
事实来源：仓库 grep、`.venv/bin/python` 对 `pring_cycle.catalog` 的只读求值、以及对生产运行库
`~/.local/share/pring-cycle/pring-cycle.sqlite3` 与 `.scratch` 两个夹具库的 `mode=ro` 查询。

票面列「五项」，逐项动作表实为 **6 个 id**（`CN_USDCNY_CLOSE_1630` 单列一行）。本文按 6 个 id 盘点，
另加两个迁移目标 id `CN_USDCNH_TMA_SPOT_RATE`、`CN_USDCNY_ECB_REFERENCE_CROSS`——后者是 09-17
之后追加的第二条迁移声明，票面没写，但它已经在 `src/` 里，盘点不能漏。

---

## 零 · 三条先于分类的事实

这三条决定了「哪些位置必须迁移」，先说，后面的表都挂在它们上面。

### 0.1 六项在生产库里一条历史声明都没有

```
source_claim        WHERE metric_id IN (六项)  →  0 行   （全库 272,949 行）
derived_observation WHERE metric_id IN (六项)  →  0 行
retrieval_attempt   WHERE metric_id IN (六项)  →  0 行
```

与 `docs/teach/metric-flow-sankey.html:203`「只在目录里有定义，没有适配器，也从未产生过声明」一致。

**这条把迁移的难点整个搬了家**：需要迁移的不是「某个 id 下的观测值」，而是**目录定义本身**
——定义已经冻结进 18 个 `model_version` 清单、7 个投影集和若干 `.scratch` 内容寻址件，
每一处都不可改写。

### 0.2 `_P2` 元组是三个目录版本的共同输入，改一个字就动三版

`catalog.py:90` 的 `_P2` 被 `metric_catalog()`（v0002，`:273`）、`metric_catalog_v0001()`（`:304`）、
`metric_catalog_v0003()`（经 `metric_catalog()`，`:341`）**共同**遍历。实测三版各 61 项，六个 id 在三版里
都存在且字段一致：

| id | unit | dimensions | source_codes | release_event_family | certification_status |
|---|---|---|---|---|---|
| `CN_USDCNH_FXCM` | `index_points` | `()` | `("CN_USDCNH_FXCM",)` | `cn_usdcnh_fxcm` | `awaiting_source_certification` |
| `CN_USDCNY_CLOSE_1630` | `scalar` | `()` | `("CN_USDCNY_CLOSE_1630",)` | `cn_usdcny_close_1630` | 同上 |
| `COMEX_GC_…_USD_OZT` | `usd_per_troy_ounce` | `("contract_month","measure","roll_chain_version")` | 同 id | `comex_gc_active_month_settlement_usd_ozt` | 同上 |
| `LBMA_GOLD_PRICE_PM_USD_OZT` | `usd_per_troy_ounce` | `("fixing","measure")` | 同 id | `lbma_gold_price_pm_usd_ozt` | 同上 |
| `CBOE_VIX_INDEX` | `index_points` | `()` | 同 id | `cboe_vix_index` | 同上 |
| `NASDAQ_SOX_INDEX` | `index_points` | `()` | 同 id | `nasdaq_sox_index` | 同上 |

注意三处**由 id 字符串派生**、改名即连带变化的字段：

- `catalog.py:661` `_release_event_family` 默认 `metric_id.lower()`——六项全部走默认；
- `catalog.py:275` `source_codes` 默认取 `(metric_id,)`，`source_candidates` 默认等于 `source_codes`——六项全部走默认；
- `catalog.py:424` `_role` 按前缀 `("COMEX","LBMA","EIA","UST","CBOE","NASDAQ")` 判 `international_context`
  ——删掉两项黄金后该分支的 `COMEX`/`LBMA` 成为死枝；`catalog.py:459`、`:490` 的 `{"CBOE_VIX_INDEX","NASDAQ_SOX_INDEX"}`
  单位表、`:444`、`:477` 的黄金单位表、`:614`/`:654` 的黄金维度表同理。

另有一处顺带发现：`CN_USDCNH_FXCM` 的 unit 实为 `index_points`，是 `catalog.py:461`
`"NH" in metric_id` 这条兜底命中的结果（汇率被判成指数点）。`CN_USDCNH_TMA_SPOT_RATE` 里同样含 `"NH"`，
所以 `candidate_admission.py:70` 才必须显式写死 `unit="cnh_per_usd"` 而不能靠派生。

### 0.3 改 `_P2` 会让三个内建模型清单的哈希与已落盘的行对不上

`models.py:128`、`:134`、`:166` 把 `metric_catalog_v0001() / metric_catalog()` 的 61 条定义
**整体内联**进 `model-v0001/v0002/v0003` 的清单；`models.py:316-322` 在 `model_version_id` 已存在时
比对重算哈希，不同即 `model_version_is_immutable`。而 `runtime.py:137` → `:267-269` 与
`runs.py:104-106` 在**每次** `initialize_runtime` / `RunRepository.create` 时无条件重跑这三次
`create_candidate`。

实测当前三者完全相等：

```
model-v0001 stored 87db11acfb184571… rebuilt 87db11acfb184571…  match
model-v0002 stored 91dde912ebc73f50… rebuilt 91dde912ebc73f50…  match
model-v0003 stored c3f4bf39dcb718d3… rebuilt c3f4bf39dcb718d3…  match
```

**这是整张票最硬的一道闸**：只要 `_P2` 里那几个字符串一改，下一次 `initialize_runtime` 就在
`models.py:322` 抛 `model_version_is_immutable`，运行库直接起不来。
`catalog.py:393` 的 `metric_catalog_v0003_canonical_hash_mismatch`（对照常量在 `catalog.py:14`）
更早一步——它在 `import pring_cycle.catalog` 时就由 `catalog.py:700` 的 `_BY_ID_V0003` 触发。

---

## 一 · 逐 id 位置表

分类：**目录定义** / **历史声明** / **投影与报告** / **测试夹具** / **文档**。

### 1.1 `CN_USDCNH_FXCM`（重命名）

| 位置 | 分类 | 说明 |
|---|---|---|
| `src/pring_cycle/catalog.py:93` | 目录定义 | `_P2` 成员；三个内建目录版本的共同来源 |
| `src/pring_cycle/candidate_admission.py:28` | 目录定义 | `_P2_IDENTITY_MIGRATION.replacements` 的**源** id |
| `src/pring_cycle/candidate_admission.py:38` | 目录定义 | `_P2_ECB_IDENTITY_MIGRATION.replacements` 的源 id |
| `src/pring_cycle/candidate_admission.py:51` | 目录定义 | `_admission_catalog()` 用 `expected.pop("CN_USDCNH_FXCM")` 取出旧定义作替换基底 |
| 生产库 `model_version` 18 行（v0001×1、v0002×2、v0003×15） | 历史声明 | 每行 `manifest_json.metric_definitions` 61 条内含该 id；表上有 `model_manifest_no_update` / `model_version_no_delete` 触发器 |
| 生产库 `analytical_dataset` `dataset_name='macro'` ×7 | 投影与报告 | `international_context` 行 `{"metric_id":"CN_USDCNH_FXCM","status":"awaiting_source_certification","value":null,"unit":"index_points"}`；`projections.py:493-503` 触发器禁改禁删 |
| `.scratch/…/capacity-historical-fixture-178/artifacts/sha256/98/98d5…93b7` | 历史声明 | `source-certified-candidate-request-v0001`，内嵌 61 条定义；**文件名即自身 sha256** |
| `.scratch/…/capacity-historical-multiple-fixture-181/artifacts/sha256/19/19d6…fe6b`、`…/d5/d5e0…0142d` | 历史声明 | 同上 |
| 两个夹具库 `registered_metric_catalog` | 历史声明 | `synthetic-metric-catalog-admission-v1`（178）与 `…-candidate` / `…-comparison`（181），`definitions_json` 含该 id |
| `tests/models/test_p2_identity_migration.py:33,53,58,122,135,180,281` | 测试夹具 | TMA 迁移正反例 |
| `tests/models/test_ecb_identity_migration.py:32,91,105,117` | 测试夹具 | ECB 迁移正反例；`:105` 用 `metric-catalog-v0001` 造旧声明 |
| `tests/models/test_isolated_lifecycle.py:139,156` | 测试夹具 | 隔离生命周期 |
| `docs/teach/metric-flow-sankey.html:202` | 文档 | 「六项国际行情无通道」卡片 |
| `docs/research/tushare-indicator-capability-audit.md:59,94,95` | 文档 | `USDCNH.FXCM` 上游代码溯源 |
| `.scratch` 内 37 个文件 | 文档 / 历史声明 | 见 §1.7 汇总 |

### 1.2 `COMEX_GC_ACTIVE_MONTH_SETTLEMENT_USD_OZT`（删除）

| 位置 | 分类 | 说明 |
|---|---|---|
| `src/pring_cycle/catalog.py:95` | 目录定义 | `_P2` 成员 |
| `src/pring_cycle/catalog.py:445`、`:478` | 目录定义 | `_unit` / `_unit_v0001` 的黄金单位表 |
| `src/pring_cycle/catalog.py:614`、`:654` | 目录定义 | `_dimensions` / `_dimensions_v0001` 的 `startswith("COMEX")` 三维 |
| `src/pring_cycle/catalog.py:424` | 目录定义 | `_role` 前缀表含 `"COMEX"` |
| `src/pring_cycle/candidate_admission.py:30` | 目录定义 | `removed_metric_ids` 成员 |
| `src/pring_cycle/dashboard.py:736` | 投影与报告 | `_international_boundary` 的 `startswith(("EIA_","COMEX_","LBMA_"))` 分支 |
| 生产库 `model_version` ×18 / `analytical_dataset` ×7 | 历史声明 / 投影与报告 | 同 1.1 |
| 三个 `.scratch` 内容寻址件 + 两个夹具库 `registered_metric_catalog` | 历史声明 | 同 1.1 |
| `tests/catalog/test_metric_catalog.py:74` | 测试夹具 | 钉住 `dimensions` 与 `unit` |
| `tests/models/test_isolated_lifecycle.py:136` | 测试夹具 | `removed` 列表 |
| `tests/models/test_p2_identity_migration.py:48,182` | 测试夹具 | 删除范围与旧声明保留反例 |
| `docs/research/new-york-london-gold-benchmarks.md:38,127` | 文档 | 该 id 的命名依据原文 |
| `docs/teach/metric-flow-sankey.html:202` | 文档 | 同 1.1 |

### 1.3 `LBMA_GOLD_PRICE_PM_USD_OZT`（删除）

| 位置 | 分类 | 说明 |
|---|---|---|
| `src/pring_cycle/catalog.py:96` | 目录定义 | `_P2` 成员 |
| `src/pring_cycle/catalog.py:446`、`:479` | 目录定义 | 黄金单位表 |
| `src/pring_cycle/catalog.py:616`、`:656` | 目录定义 | `startswith("LBMA")` 二维 |
| `src/pring_cycle/catalog.py:424` | 目录定义 | `_role` 前缀表含 `"LBMA"` |
| `src/pring_cycle/candidate_admission.py:31` | 目录定义 | `removed_metric_ids` 成员 |
| `src/pring_cycle/dashboard.py:736` | 投影与报告 | 同 1.2 |
| 生产库 `model_version` ×18 / `analytical_dataset` ×7 | 历史声明 / 投影与报告 | 同 1.1 |
| 三个 `.scratch` 内容寻址件 + 两个夹具库 | 历史声明 | 同 1.1 |
| `tests/models/test_isolated_lifecycle.py:136` | 测试夹具 | `removed` 列表 |
| `tests/models/test_p2_identity_migration.py:49,190` | 测试夹具 | 删除范围；`:190` 用 `{"fixing":"PM","measure":"price"}` 造旧声明 |
| `docs/research/new-york-london-gold-benchmarks.md:74,127` | 文档 | 命名依据原文 |
| `docs/teach/metric-flow-sankey.html:202` | 文档 | 同 1.1 |

### 1.4 `CBOE_VIX_INDEX`（保 id，接 Cboe 官方 CSV）

| 位置 | 分类 | 说明 |
|---|---|---|
| `src/pring_cycle/catalog.py:102` | 目录定义 | `_P2` 成员 |
| `src/pring_cycle/catalog.py:459`、`:490` | 目录定义 | `{"CBOE_VIX_INDEX","NASDAQ_SOX_INDEX"}` → `index_points` |
| `src/pring_cycle/catalog.py:424` | 目录定义 | `_role` 前缀表含 `"CBOE"` |
| 生产库 `model_version` ×18 / `analytical_dataset` ×7 | 历史声明 / 投影与报告 | 同 1.1 |
| 三个 `.scratch` 内容寻址件 + 两个夹具库 | 历史声明 | 同 1.1 |
| `tests/integration/test_worker_execution.py:1025,1036` | 测试夹具 | `manual_deep_search` 的 P2 单指标约束 |
| `tests/retrieval/test_cascade.py:46` | 测试夹具 | P2 级联止于 exa，不用 ai_websearch |
| `docs/teach/metric-flow-sankey.html:202` | 文档 | 同 1.1 |
| `.scratch/…/vix-followup.md:9`、`plan-2527-probe-20260917.md:29`、`survey-24-p2-publishers-20260917.md:13` | 文档 | 官方 CSV 入口核实记录 |

### 1.5 `NASDAQ_SOX_INDEX`（保 id，接 Nasdaq 官方指数站）

| 位置 | 分类 | 说明 |
|---|---|---|
| `src/pring_cycle/catalog.py:103` | 目录定义 | `_P2` 成员 |
| `src/pring_cycle/catalog.py:459`、`:490` | 目录定义 | 同 1.4 |
| `src/pring_cycle/catalog.py:424` | 目录定义 | `_role` 前缀表含 `"NASDAQ"` |
| 生产库 `model_version` ×18 / `analytical_dataset` ×7 | 历史声明 / 投影与报告 | 同 1.1 |
| 三个 `.scratch` 内容寻址件 + 两个夹具库 | 历史声明 | 同 1.1 |
| `tests/integration/test_worker_execution.py:1025` | 测试夹具 | 同 1.4 |
| `docs/teach/metric-flow-sankey.html:202` | 文档 | 同 1.1 |
| `.scratch/…/plan-2527-probe-20260917.md:30`、`survey-24-p2-publishers-20260917.md:14` | 文档 | 官方站核实记录（已取得 6 行真实历史，见 `implementation-27-identity-migration-20260917.md` 末节） |

### 1.6 `CN_USDCNY_CLOSE_1630`（保 id，接 CFETS / 中国货币网）

| 位置 | 分类 | 说明 |
|---|---|---|
| `src/pring_cycle/catalog.py:94` | 目录定义 | `_P2` 成员；**unit 实为 `scalar`**，接 CFETS 后必然要改成 `cny_per_usd`——即使 id 不变，定义也变 |
| 生产库 `model_version` ×18 / `analytical_dataset` ×7 | 历史声明 / 投影与报告 | 同 1.1 |
| 三个 `.scratch` 内容寻址件 + 两个夹具库 | 历史声明 | 同 1.1 |
| `docs/teach/metric-flow-sankey.html:202` | 文档 | 同 1.1 |
| `.scratch/…/research-27-cfets-close-followup-20260918.md:9`、`plan-2527-probe-20260917.md:31`、`survey-24-p2-publishers-20260917.md:15`、`review-26-standards-findings-20260917.md:87`、`implementation-19-material-preflight-20260919.md:161` | 文档 | 口径核实与预检缺口记录 |

`src/` 中**没有任何**按 id 引用它的分支——它是六项里唯一一个只在 `_P2` 出现一次的。

### 1.7 两个迁移目标 id（已在 `src/`，票面未写）

| 位置 | 分类 | 说明 |
|---|---|---|
| `src/pring_cycle/candidate_admission.py:28,70-81` | 目录定义 | `CN_USDCNH_TMA_SPOT_RATE`：名称/单位/维度/代码/入口/频率/发布族/时区逐项写死 |
| `src/pring_cycle/candidate_admission.py:178` | 目录定义 | `identity` 表 `{"CN_USDCNH_TMA_SPOT_RATE":"tma", "CN_USDCNY_ECB_REFERENCE_CROSS":"ecb"}`，十字段比对，不符即 `certification_{identity}_identity_mismatch`（`:196`） |
| `src/pring_cycle/evidence.py:1391-1394` | 历史声明 | 两个新身份**即使未认证**也强制走 `require_registered_source_contract`，禁止继承旧 broker 通路 |
| `src/pring_cycle/candidate_admission.py:38,53-68` | 目录定义 | `CN_USDCNY_ECB_REFERENCE_CROSS` 的第二条迁移声明 |
| `src/pring_cycle/ecb_reference.py`（整模块，`:34` `ECB_METRIC`） | 目录定义 / 历史声明 | ECB 侧**已有完整适配器**：ZIP/CSV 有界解析、采集回执、声明写入 |
| `src/pring_cycle/worker.py:1448-1462` | 投影与报告 | `refresh_context_sources` 的 ECB 分支，门控于「注册目录含该指标」 |
| `src/pring_cycle/context_projection.py:1498`、`search_evidence.py:204`、`source_contract_review.py:145` | 投影与报告 | ECB 声明的契约校验与检索族 |
| `docs/operations/ecb-reference-cross.md`（55 行，`:52` 明写「旧 FXCM/TMA 目录不会因此请求 ECB 或 TMA」） | 文档 | 运维说明 |
| `tests/models/test_p2_identity_migration.py`（14 处）、`test_ecb_identity_migration.py`（4 处） | 测试夹具 | 两条迁移的正反例 |

**TMA 侧只有准入约束，没有适配器**——`src/` 下不存在 `tma_*.py`，`source_contract_review.py:351-368`
的 `contracts` 表里也没有它，所以今天任何 TMA 声明都会在 `:372` 撞上
`registered_source_contract_not_implemented:CN_USDCNH_TMA_SPOT_RATE`。

### 1.8 `.scratch` 汇总（`grep -o | wc -l` 实测命中数，非估计）

按命中数排序，`.scratch` 下共 **56 个文件**含这些 id（`CN_USDCNH_FXCM` 37 个、`CBOE_VIX_INDEX` 39 个、`NASDAQ_SOX_INDEX` 32 个、`CN_USDCNY_CLOSE_1630` 32 个、`COMEX_GC_…` 27 个、`LBMA_…` 25 个）：

- **历史声明**（冻结记录，内嵌清单或读数矩阵）：`evidence-14/p2-read-matrix.json`(72)、
  `pring-data-acquisition-audit/metric-inventory.json`(54)、`evidence-14/availability-matrix.json`(30)、
  `evidence-search-preexperiment-20260908-n4-v1/frozen.json`(24)、`evidence-13/legacy-read-matrix.json`(24)、
  三个 `capacity-historical-*/artifacts/sha256/**`(各 24)、`verification-03/official-sample-result.json`(18)、
  `evidence-13/readonly-checks.json`(18)、`evidence-18/frozen-bundle.json`(6)、
  `evidence-14/sample-comparison.json`(6)、`evidence-14/code-evidence.json`(8)、`evidence-14/build_inventory.py`(6)、
  `evidence-14-vix-followup/{code-inspection,source-inspection}.json`(5/1)
- **投影与报告**（跑批采集/事件记录）：`verification-current-full-v7-events-20260919.jsonl`(8)、
  `verification-current-full{,-v3..v7}-collection-*.json`(各 4)、
  `verification-22{,-current}-full-collection-20260918.txt`(各 2)、
  `verification-current-full-v7-20260919.txt`(2)、
  `verification-19-preflight-complete-inputs-result-{20260919-v2,20260920-v4}.json`(各 3)、
  `verification-27-system-target-red-20260918.txt`(1)
- **文档**：`issues/24…`(18)、`issues/27…`(6)、`spec-24…`(8)、`survey-24-p2-publishers`(8)、
  `survey-24-coverage`(6)、`research-14.md`(6)、`metric-inventory-notes.md`(6)、
  `v1-metric-catalog.md`(6)、`v1-data-inventory-summary.md`(6)、
  `source-availability-triage-2026-08-31.md`(6)、`verification-2527-probe-*.{md,json}`(各 3)、
  `plan-2527-probe`(3)、`implementation-19-material-preflight`(3)、
  `implementation-27-{identity-migration,ecb-identity}`(2/1)、`vix-followup`(1)、
  `research-27-cfets-close-followup`(1)、`review-26-standards-findings`(1)、`parallel-tasks-b`(1)
- **测试夹具（原型）**：`pring-cycle-v1-wayfinding/prototypes/**` 5 个文件（`claude-probe-results.json` 2，其余各 1）

---

## 二 · 必须迁移 vs 可原地替换

### 2.1 必须迁移——被旧 id 键住的落盘物

| 位置 | 被旧 id 键住的是什么 | 原地改会怎样 |
|---|---|---|
| 生产库 `model_version` 18 行的 `manifest_json` | 整份 61 条定义**按内容**入库，`manifest_hash` = 该 JSON 的 sha256。`models.py:316-322` 在 id 已存在时比对重算值 | `runtime.py:267-269` / `runs.py:104-106` 下次重跑 `create_candidate` 即抛 `model_version_is_immutable`；`models.py:1285` 的删除触发器也不允许清掉重来 |
| `catalog.py:14` `_METRIC_CATALOG_V0003_SHA256` | v0003 全目录的规范 sha256 | `catalog.py:393` 在 `import pring_cycle.catalog` 阶段就抛 `metric_catalog_v0003_canonical_hash_mismatch`（`:700` 的 `_BY_ID_V0003` 触发），全仓库无法导入 |
| `registered_metric_catalog`（两个 `.scratch` 夹具库已有 3 个版本；生产库为空） | `catalog_version → (definitions_hash, definitions_json)`，且 `catalog_registry.py:59-67` 对同名版本做逐字节比对（不符即 `:66`） | `metric_catalog_version_is_immutable:<version>`；即使绕过，`registered_definitions` 在 `:87-94` 还会抛 `registered_metric_catalog_hash_mismatch` / `registered_metric_catalog_admission_mismatch` |
| `definition_bindings`（`candidate_admission.py:112-127`、`source_contract_review.py:748-750`） | `metric_id → sha256(asdict(definition))`。**id 本身是被哈希的字段之一** | 改 id 或任一字段 → `certification_definition_mismatch:<package>:<metric_id>`；来源审查包与其 `review.subject_hash` 也连带失效 |
| `.scratch/…/capacity-historical-*/artifacts/sha256/**` 三个件 | 文件名 = 自身内容的 sha256，内含 61 条定义 | 改内容即改文件名；`request_hash` / `package_hash` 引用链全断。这些是**内容寻址**，不存在「原地编辑」这种操作 |
| 生产库 `analytical_dataset` 7 个 `macro` 文档 | `international_context` 数组里按 `metric_id` 排的行 | `projections.py:493-503` 的 `analytical_dataset_no_update` / `_no_delete` 触发器直接 ABORT |
| `source_claim` / `derived_observation` / `retrieval_attempt` 的 `metric_id` 列 | `evidence.py:1583`、`:1611`、`:1622`；`observation_id = sha256(metric_id ∥ definition_version ∥ period_kind ∥ period_start ∥ period_end ∥ dimensions_json)`（`evidence.py:1441-1447`），`claim_id` 再由 `observation_id` 派生（`:1449`） | `evidence.py:1605-1608` 的 `source_claim_no_update` / `_no_delete` 触发器禁止任何改写。**今天这三张表对六项都是 0 行**（§0.1），所以这一项当前是「规则上必须迁移、事实上无行可迁」——但 `tests/models/test_p2_identity_migration.py:180-192` 会合成旧声明，夹具路径上它是实打实的 |
| `run_retrieval_scope.metric_ids_json`（`runs.py:1229`）、`retrieval_negative_cache.metric_ids_json`（`runs.py:1255`）、`full_run_acquisition.metric_ids_json`（`full_retrieval.py:668`） | 检索范围按 id 列表落盘；三张表均带不可变触发器 | 同上，不可改写 |
| 检索范围标识与缺口键 | `full_retrieval.py:250` 的 `f"full:{release_event_family}:{period}"`、`retrieval_ledger.py:75` 的 `event_key = json([release_event_family, period])` | 六项的 `release_event_family` 就是 `metric_id.lower()`（§0.2），**改名即改 event_key**，已落盘的 `retrieval_gap` / `retrieval_request_event` 行与新 key 对不上 |

一句话：**旧 id 没有值要搬，但有身份要交代**。「旧 id 的历史证据如何处置」这个票面要求，
落到这份库上等于「旧 id 的**定义**在已冻结的 18 份清单、7 个投影、3 个内容寻址件里怎么办」。

### 2.2 可原地替换——只在代码里按 id 分支

这些改完不影响任何落盘物的身份，前提是 §2.1 的目录版本问题已经用「铸新版本」而非「改旧版本」解决：

- `catalog.py:424` `_role` 前缀表、`:444-446`/`:477-479` 黄金单位、`:459`/`:490` VIX/SOX 单位、
  `:614`/`:616`/`:654`/`:656` 黄金维度——删除两项后这些分支成为死码
- `dashboard.py:736` `_international_boundary` 的 `COMEX_`/`LBMA_` 分支
- `candidate_admission.py:28-38` 两条迁移声明常量本身
- 各测试文件的字面量

### 2.3 **不**按 id 硬编码、因而无需改动的面

这一条是为了让 `/implement` 那一刀不去白改：P2 的处理在下列各处都是**按 priority 泛化**的，
删 / 改 id 不需要动它们——

`context_projection.py:179,304,1950`（`_international_context` 遍历 `rules.metric_definitions`
里所有 `priority=="P2"`）、`context_replay_scope.py:68,116`、`material_preflight.py:130,224`、
`model_evaluation.py:760,851`、`retrieval_ledger.py:338,780`、`retrieval.py:96`、
`source_certification.py:208`、`worker.py:1041,1664`、`candidate_admission.py:207`。

`metric_contracts.py` 里 **没有** 这六项的任何条目（`REQUIRED_DIMENSION_MEMBERS` 等），
`source_families.py` 的 `OFFICIAL_CONTEXT_FAMILIES` 也 **不含** 任何一项。

另外，「新旧不混算」在 observation 层面本来就成立：`observation_id` 同时含 `metric_id` 与
`definition_version`（`evidence.py:1441-1447`），`_validate_claim` 在 `evidence.py:1380-1381` 还要求
两者严格一致。票面验收第一条要的反例，代码里已有既成形状（`test_p2_identity_migration.py:172-200`）。

---

## 三 · 三项「接官方通道」：新适配器还是既有？（次要，从简）

| 指标 | 结论 | 依据 |
|---|---|---|
| `CBOE_VIX_INDEX` | **新适配器** | `source_contract_review.py:351-368` 的 `contracts` 表无此项；`source_families.py` 无对应族；`worker.py:1409` 的 `refresh_context_sources` 只接了 EIA 与 ECB 两条 |
| `NASDAQ_SOX_INDEX` | **新适配器** | 同上 |
| `CN_USDCNY_CLOSE_1630` | **新适配器**（不能复用 LPR 那条） | 同域不等于同通道：`CN_LPR_1Y_5Y` 走 `official_lpr.py` + 族 `chinamoney_lpr`（`catalog.py:664`、`release_calendar.py:220`），是按 LPR 页面结构写的解析器；16:30 收盘价是另一个页面与另一套字段 |
| （`CN_USDCNH_TMA_SPOT_RATE`） | **新适配器** | `src/` 无 `tma_*`；`evidence.py:1391` 已把它强制送进 `require_registered_source_contract`，而 `source_contract_review.py:372` 必然抛 `registered_source_contract_not_implemented` |
| （`CN_USDCNY_ECB_REFERENCE_CROSS`） | **已有** | `ecb_reference.py` 整模块 + `worker.py:1448` 接线 + `docs/operations/ecb-reference-cross.md` |

每新增一项都要在 `source_contract_review.py:351` 的 `contracts` 表加条目，
否则该项的任何声明都走不出 `:372`。

---

## 四 · 只读判不了的开放问题

1. **票面与已确认决定不一致：重命名目标已由 TMA 改为 ECB，但票面没改。**
   这一条不是开放问题，是本次盘点顺带查实的事实，列在这里因为它直接决定 `/implement` 该迁向哪个 id。
   `decision-27-ecb-reference-cross-20260917.md`（2026-09-17 23:42 确认）明写：
   「新不可变目录中用独立 ECB 身份替代**原计划 TMA 新项**」「TMA 暂无授权且保留缺口的决定保持」。
   而 `issues/27-metric-identity-corrections.md:4,18` 至今仍写 TMA 定盘。
   `candidate_admission.py:47` 两条声明都接受，二者只能二选一出现在一份清单里。
   **真正开放的是**：TMA 那条迁移声明（`candidate_admission.py:28`）在 ECB 决定之后是留是删，
   决定文件没说；`implementation-27-ecb-identity-20260917.md:7` 只说「旧 TMA migration 仍支持读取/创建其未认证候选」。

2. **`ecb_reference.py` 是什么时候、以什么范围合进主干的？**
   `implementation-27-ecb-identity-20260917.md` 明写「未合并、推送、正式认证或激活」，
   但 `src/pring_cycle/ecb_reference.py` 与 `docs/operations/ecb-reference-cross.md` 今天都在主干上。
   两者不自洽。查清需要翻 git 历史，超出本次只读 grep 的范围，留给 B2 的票面对齐或 `/implement`。

3. **删掉两项黄金后，`awaiting_source_certification` 的 P2 计数会从 13 变成 11——
   有没有别处把「13」或「61」写死？**
   `src/` 里 grep 不到 `61` 这个字面量（唯一命中是 `source_history.py:459` 的一段 URL 片段），
   `docs/teach/metric-flow-sankey.html` 里的「48 项」「6 项」是叙述文本。
   但 `tests/integration/test_context_projection.py:462` 断言
   `len(context.macro["international_context"]) == 13`——这是投影里 P2 的行数。
   它会不会因删除而变，取决于迁移后用哪个目录版本跑该用例；**不跑测试判不了**，
   只能指出这一处需要 `/implement` 亲自确认。

4. **生产库 `registered_metric_catalog` 为空（0 行），18 个模型全部挂在三个内建版本上。**
   这意味着迁移要落到真实运行库，必须先完整走一遍 ADR-0013 的准入铸版——
   而 `catalog_registry.py:55-56` 明确禁止把内建版本号拿去注册
   （`builtin_metric_catalog_cannot_be_registered`）。新版本号叫什么、由哪个模型准入，
   是设计问题，不在本次盘点范围。

5. **`.scratch` 下 56 个命中文件里，哪些是「必须随迁移更新的账本」、哪些是「当时如实的历史记录、不该改」？**
   三个 `capacity-historical-*` 内容寻址件与两个夹具库显然属后者（改了就毁掉哈希链）；
   `metric-inventory.json`、各 `verification-*-collection-*.json` 看形制也是冻结记录。
   但没有一份 `.scratch` 材料声明过自己的可变性约定，**只读判不了**哪些属于「账本」。
