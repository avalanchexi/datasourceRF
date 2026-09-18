# 发现：空的交易日历卡住了整条链（2026-09-18）

在为前端改版查"核心资产数据集为何全空"时发现。只读查询运行库（`immutable=1`，未创建旁文件），未修改任何数据。

## 现象

运行库里 7 次投影，**无一例外**：

| 项 | 7 次的值 |
|---|---|
| `current_stage` | 全部 `None` |
| `completeness` | 全部 `degraded` |
| `core_assets` 数据集 | 全部 **0 条** |
| `cycle_overview` / `inventory` / `macro` | 全部 0 条 |

即：**这套系统从未产出过一个正式阶段，也从未产出过一条核心资产状态。**

## 不是因为核心数据缺失

三个核心资产的证据非常完整：

| 指标 | 声明数 | 期次范围 | 已认证 |
|---|---|---|---|
| `CN_EQUITY_CORE_000985` | 43,300 | 2017-01-03 → 2026-08-28 | 43,300 |
| `CN_BOND_CORE_000012` | 43,300 | 2017-01-03 → 2026-08-28 | 43,300 |
| `CN_COMMODITY_CORE_NHII` | 43,300 | 2017-01-03 → 2026-08-28 | 43,300 |
| **`CN_TRADE_CALENDAR`** | **0** | — | — |

## 因果链

```
CN_TRADE_CALENDAR 零条声明
  → required_calendar() 取不到 120 个交易日
  → status: "unavailable"（full_run_requirements.py:86）
  → Worker 标记 p0_required_calendar_period_missing（worker.py:343）
  → 运行降级
  → core_assets 数据集为空
  → 无正式阶段
```

`CN_TRADE_CALENDAR` 是 **P0、已认证**的指标，趋势评估用它定观察轨道。它空着，三个核心资产的 43,300 条数据就用不上。

## 根因：它从未被请求过

```
trade_cal 采集请求总数: 0
```

不是请求失败，不是解析失败——**从未发起过**。全库 44 / 61 个指标有声明，交易日历不在其中。

## 为什么这值得单独记一笔

之前我把关键路径判断为"票13 的 18 项 A 类认证"。那个判断**方向没错但不完整**：18 项 A 类解决的是宏观证据的认证，而**即使它们全部认证完成，只要交易日历还是空的，运行照样降级、阶段照样为空**。

这一项的代价与收益极不对称：

- 代价：一次 `trade_cal` 采集，指标已认证、通道已存在（TuShare `trade_cal`，与三个核心指数同一通道）。
- 收益：核心资产状态、正式阶段、三资产动向——整个前端结果页的主角。

## 根因已查实：两处规则互相矛盾

**一处把它排除在采集之外。** `full_retrieval.py:164-171` 把 `CN_TRADE_CALENDAR` 连同 `CN_RELEASE_SCHEDULE`、`SOURCE_OBSERVED_AVAILABILITY` 一并归为 `operational_evidence` 并 `continue`——**不生成缺口**。不生成缺口就不会进检索，不进检索就永远不会被请求。这解释了 `trade_cal` 采集请求为 0。

**另一处硬性要求它存在。** `full_run_requirements.py:20` 读 `CN_TRADE_CALENDAR` 的序列，要求恰好 120 个交易日，否则 `status: "unavailable"`；`worker.py:343` 据此标记 `p0_required_calendar_period_missing`，运行降级。

两处规则的口径相反：

| 位置 | 口径 |
|---|---|
| `full_retrieval.py:164` | 这是运营性证据，**不需要采集** |
| `full_run_requirements.py:20` + `worker.py:343` | 没有它，**运行不能正常完成** |

`full_run_requirements.py:44` 还留了一条回退，去找 `api_name='trade_cal'` 且 `state='validated'` 的采集回执——**说明设计上预期有人去取它**，但没有任何适配器负责这件事。TuShare 有 `trade_cal` 接口，与三个核心指数同一通道、同一令牌。

这不是"少配了一个 URL"，是**两处规则没有对齐**。修法应当先定哪一处是对的：要么交易日历由某个通道正式采集（那就不能归为 `operational_evidence`），要么 `required_calendar` 不该把它当 P0 硬门槛。

## 待确认
- 补上之后是否真能产出阶段：取决于三资产各自能否形成稳定状态（`trend-v0001` 要求 120 日窗口、8 日持续）。数据覆盖 2017 年至今，窗口是够的，但**能否落入六个典型组合之一，要跑过才知道**——可能仍是非典型组合，那时当前阶段依然为空，且那是正确行为。
