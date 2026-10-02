Status: ready-for-agent（父票，拆为 07、08、09）
Category: bug
Type: task

# 02 — 目录版本切换使语义未变的声明全部不可见

## 原始发现

- 模型 v0014（目录 `metric-catalog-v0006`，[架构评审票 25](../../architecture-review-20260929/issues/25-model-v0014-twelve-month-horizon.md)）激活后第一次真实运行：
  - **OMO 7 天期利率 `not_held`**：v0005 下持有 9/24、9/28（9/28 值 1.4%），v0006 下 0 条。9/30 央行公告"7天期逆回购操作量为零"，表格无利率；"未写利率时沿用已持有值"找不到可沿用的基准。连带 **DR007 政策利差算不出**（`missing`，缺 `CN_OMO_7D_RATE`）。
  - **整窗重取**：广度 `daily`／`stk_factor_pro` 各 120 次、商品篮子 `fut_daily` 60 次（从 3/09 补链）、郑商所仓单 CF/TA 约 120 个交易日文件——旧目录各持有约 118 日，新目录 0。运行 57 分钟（基线约 10 分钟），取数约 840 次。
- 对比两版注册清单，忽略 `definition_version` 后只有 `CN_CREDIT_IMPULSE` 的定义变了。

## 根因（Codex 只读调查）

- `models.py:493` 把全部指标的定义版本换成 v0006；`evidence.py:972` 按版本严格过滤。郑商所按当前版本算已持有日（`czce_warrants.py:300`、`:385`），广度与篮子按当前版本读已有值（`worker.py:1855`、`basket.py:200`）。
- 旧声明没有被删，只是新目录读不到；120 日后随留存清理。

## 待决定

- 修复方向（建议）：定义未变的指标在新目录下可复用旧声明（显式兼容或按定义比较继承），至少事件类现行基准（OMO 利率）要能跨目录沿用。
- 是否需要补一条 ADR（目录版本与声明可见性的关系）。
- 下次切换目录前是否先修；本次的整窗重取已经发生，后续运行不会再重取。

## 分流（2026-10-02）

> *本段由 AI 按用户决定记录。*

用户决定：需要优化，按建议方案（见下）；边界经 `/grill-with-docs` 访谈定下，记为 [ADR-0036](../../../docs/adr/0036-observation-identity-by-same-definition.md)，`CONTEXT.md`「观测身份」「相同定义」已改。

- **现状**：`model_v0014_manifest()` 因信用脉冲单位变化把目录升为 v0006，并把**所有**指标的 `definition_version` 一并改成 v0006（`models.py` 注释："the catalog is v0006, every definition with it"）。读取按 `definition_version` 严格相等过滤（`evidence.py` `metric_series`），观测身份也含定义版本（`CONTEXT.md`「观测身份」）。所以 v0005 下取得的声明对 v0006 全部不可见。v0012→v0013 切换时同样整窗重取过广度（9/25）。
- **建议方案**：按定义内容判断可见性——当前定义与旧版本定义除版本号外完全相同的指标，读取时同时接受旧版本的声明（同一统计期与维度视为同一观测参与选值）；定义真正变化的指标（本次只有 `CN_CREDIT_IMPULSE`）仍只读新版本。不改已注册模型与清单哈希，切回 v0014 当下即可恢复 OMO 利率基准、免去下次整窗重取。
- **备选**：只给变化的指标升版本（按指标定版本，目录版本只作集合标签）——更干净，但要新模型版本、改观测身份规则，影响面大。

## 访谈结论（2026-10-02）

> *本段由 AI 按用户逐题确认记录。*

1. **相同定义**：自动比较，不靠清单声明；比较单位（含允许单位）、频率、维度、来源代码，派生指标再加公式版本（清单顶层 `derived_formula_versions`）。不比较 `name_cn`、`priority`、`role`、`source_candidates`、`certification_status`、`release_*`。
2. **新旧版本值不一致**：同一来源按修订取最新（ADR-0022）；跨来源按 ADR-0033。
3. **可见范围**：不限版本、双向，只受留存期约束。
4. **已发布历史**：不重算。
5. **实现**：读取时归并，不改写已存观测编号。Codex 勘察列出的按版本卡住处都要改成认"相同定义版本组"：`evidence.py` 的 `metric_series`、`preload_metric_series`、`delivered_values`（GDP 同次交付）、`source_claims_matching_registered_contract`、`latest_source_claim`、`source_claim_vintages`、`claims_for_release_source`、`release_events_for_definition`；原件复核（TuShare 一般／银行间／仓单 normalized 版本、ECB、美债原件参数）；仓单解析缓存键；`acquisition_outcome` 的版本条件；Worker 已持有日（广度、篮子、核心补缺、目标交易日）、`czce_warrants._held_totals`、信用脉冲输入、发布日历、上下文投影各序列入口。同一统计期跨版本的多条声明须在归并后只形成一个观测（`search_evidence.py:245` 现在要求每成员恰好一条）。旧定义从库中 `registered_metric_catalog`／`model_version.manifest_json` 读取比较。
6. **顺序与验收**：先做本票，再做票 01；两张完成后跑一次真实完整运行一起验收——OMO 利率沿用 1.4% 基准、DR007 政策利差算出；广度／篮子／仓单不再整窗重取；国庆期间国内指标不判落后、外盘照常推进。

勘察全文（Codex 只读）：观测编号含定义版本（`evidence.py:1555`）；v0013→v0014 61 个指标中 60 个定义相同，仅信用脉冲 `unit`／`allowed_units` 变化；v0012→v0013 广度与篮子 5 个同名指标的来源代码变化，另删 2 增 4。

**2026-10-02 拆票**：按 goal 拆为三片竖切——[07（02a）读取与选值归并](07-same-definition-read-and-selection.md)、[08（02b）已持有日与入库查重](08-same-definition-held-days-and-ingest.md)、[09（02c）原件复核与缓存键](09-same-definition-original-checks-and-cache-keys.md)；08、09 依赖 07。三片 done 后本票 done。

