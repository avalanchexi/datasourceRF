Status: ready-for-agent
Type: read-only-fact-alignment
Date: 2026-09-21

# 发现：#28 的票面根因已经过时，四项验收里三项其实已被覆盖

只读核对，未改动 `src/`、`tests/`、`tools/`，未运行任何重型验证。本文件只对齐事实，不勾选验收
——勾选要由实施那一刀连同它自己的证据一起做。

## 结论先说

[#28 票](issues/28-trade-calendar-never-acquired.md)写于 2026-09-18，其后 `4be17e2`
「Block new Worker publication without an independent calendar (#28)」落地，但**票面从未更新**
（票文件自 `6c5f5f1` 创建后再没被改过）。今天回读代码，票面的根因段落有三条已不成立，
核心现象描述也已被推翻。

**照票面原文去实施会做错东西。** 下面逐条给出现状与依据。

## 一、票面根因的三条过时之处

| 票面说法 | 现状 | 依据 |
| --- | --- | --- |
| 「`trade_cal` 的采集请求数为 **0**——不是失败，是从未发起」 | 完整运行**会**采集日历 | `worker.py:323` 的 `_refresh_core_sources` → `core_history.py:85` → `adapter.acquire_calendar`，位置在 `full_retrieval.retrieve(run)` **之前** |
| 「留有一条回退……说明设计上预期有人取它，但**没有适配器负责**」 | 适配器一直都在 | `source_adapters.py:164` `TushareCoreAdapter.acquire_calendar` |
| 「运行库 7 次投影**无一例外**……**系统从未产出过一个正式阶段**」 | 已被反证 | `4be17e2` 的[实施记录](implementation-28-calendar-gate-20260918.md)写明「旧报告的『7次投影均无核心资产、无正式阶段』已由只读运行库核验反证」 |

`4be17e2` 实际做的是**发布闸门**：最终计划算出后，`daily_window` 不 available 即
`mark_action_required("p0_required_calendar_unavailable")` 并停止发布（`worker.py:341-343`）。
它把「缺日历却照样发布投影、再用非典型组合解释空阶段」这个真问题堵上了，**但它不是采集能力**。

## 二、四项验收的逐条现状

### 验收 1 「日历齐备的完整运行产出 `core_assets` 非空，且当前阶段按 `stage.py` 得出」——**已被覆盖**

`tests/integration/test_core_history_refresh.py::test_manual_run_cannot_backdate_daily_core_availability`
（该文件最后一次改动正是 `4be17e2`）已经走完整公开路径并断言：

```
window["status"] == "available"
window["basis"] == "validated_independent_calendar_response"
len(window["dates"]) == 120
any(item["api_name"] == "trade_cal" and item["state"] == "validated" for item in plan["acquisitions"])
len(projection.datasets["core_assets"]["assets"]) == 3
projection.datasets["cycle_overview"]["current_stage"] == "stage_iii"
```

倒数第二条正是「`core_assets` 非空」，最后一条**直接推翻了「从未产出过一个正式阶段」**——
这次运行产出的是 `stage_iii`。中间那条 `plan["acquisitions"]` 里有 `trade_cal` 且 `validated`，
是「日历确实被采集了」的直接证据。

**但有一处脆弱值得记下**：这些断言依附在一个主旨完全不同的测试上（它要证的是
「手工运行不得回填当日核心可用性」）。#28 的这项覆盖是顺带得来的，将来那个测试若因别的理由
被改写，覆盖可能无声消失。实施那一刀应当考虑给 #28 一条**以它自己为主旨**的用例。

### 验收 2 「日历缺失的失败分类与非典型组合可区分」——**已被覆盖**

`tests/integration/test_worker_calendar_gate.py::test_missing_independent_calendar_blocks_publication_and_preserves_previous_result`
断言缺日历时 `status == "action_required"`、`error_classification == "p0_required_calendar_unavailable"`、
`projection_set_id is None`、且既有报告历史不变。非典型组合则是运行**正常完成**但阶段为空。
两者在查询结果中形态不同，可区分。

两类分类也确实分开使用：`worker.py:342` 的 `p0_required_calendar_unavailable`（日历本身不可用）
与 `worker.py:348` 的 `p0_required_calendar_period_missing`（有日历但核心价格缺期）。

> **2026-09-22 实施时订正**：下面这节把 token 分支称作「唯一确定的实质剩余工作」，**判过头了**。
> 票面允许的归属是「要么进入某个通道的例行刷新，要么进入缺口计划」，日历走的正是前者，验收 3
> 因此已满足。无 token 等于不做真实采集，是本仓库广泛依赖的合法状态——`test_full_run_retrieval.py`
> 的 `prepare()` 从不写 secrets，四处用例正是在这个状态下断言 `p0_required_calendar_unavailable`；
> 若让缺 token 改变失败分类，这些用例全会被破坏，而它们的语义本就是「材料不足」而非「配置缺失」。
> token 那条是独立的**可用性**观察（生产用户没配 token 时，分类指向日历而非配置），不属于本票。

### 验收 3 「两处规则对齐，不再出现『不采集但又必需』」——**部分满足，剩一个分支**

票面允许两种对齐方式之一：「交易日历有明确的采集归属：**要么进入某个通道的例行刷新**，
要么进入缺口计划」。现状走的是前者——`_refresh_core_sources` 这条例行刷新。所以在**正常路径上**
归属是明确的，矛盾已消解。

`full_retrieval.py:213` 至今仍把 `CN_TRADE_CALENDAR` 连同 `CN_RELEASE_SCHEDULE`、
`SOURCE_OBSERVED_AVAILABILITY` 一起标为 `operational_evidence`（不生成缺口），这本身不再是缺陷
——它只是说「不由缺口计划负责」，而另有通道负责。

**但有一个分支仍然落空**：`_refresh_core_sources`（`worker.py:1700-1710`）在
`TUSHARE_TOKEN` 缺失时**静默 `return`**：

```python
    token = secrets.get("TUSHARE_TOKEN")
    if token is None:
        return
```

此时没有任何通道去取日历，而 `required_calendar` 仍然必需它——「不采集但又必需」在这个分支下
原样成立。运行随后以 `p0_required_calendar_unavailable` 停下，**分类指向「日历不可用」，
真实原因却是「没有配置 token」**。这恰好是验收 2 想要区分的那类混淆，只是混淆的另一侧不是
非典型组合，而是配置缺失。

这是 #28 目前**唯一确定的实质剩余工作**。

### 验收 4 「不放宽 `trend-v0001`，不为产出阶段而降低门槛」——**未被违反**

`4be17e2` 的做法是缺日历就**拒绝发布**，方向与放宽相反。实施记录亦写明「不改变趋势稳定性、
阶段映射或既有历史」。

## 三、因此，#28 的实施切片应当做什么

1. **补上 token 缺失这一分支**：让「没有 token」与「日历确实取不到」在失败分类上可分，
   使运行停下来时指向可操作的补救。这是验收 3 的剩余部分，也顺带完善验收 2。
2. **给验收 1 一条以 #28 为主旨的用例**，把目前寄居在别人测试里的覆盖固定下来。
3. **勾选验收并更新票面**，每一项附上它的证据（用例名与断言）。

不应当做的：不要按票面原文去「新建日历采集器」——适配器和采集路径都已存在，
`4be17e2` 的实施记录明确写过「原适配器、trade_cal 直接刷新路径已存在，不新增重复采集器」。

## 四、一处必须订正的转述

`plan-19-preflight-remaining-checks-20260920.md` 写道：「票面已在 2026-09-19 推进覆盖：
`Execution: completed`，四项验收全部勾选，修复提交 `4be17e2`、收尾提交 `c5f0796`。
**#28 不是下一张票**」。

前半句**不属实**：`git log --all -- <#28 票文件>` 只有一次提交 `6c5f5f1`（创建），
票面至今是 `Execution: not-started`、0/4 勾选。`4be17e2` 确实存在，但它没有更新票面。

讽刺的是那段话自己的结论是「引用提效文档的票况时必须回票面核对」——而它引用票况时正是没有核对。
该处已按本文件订正。
