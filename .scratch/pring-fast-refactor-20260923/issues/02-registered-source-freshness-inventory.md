Type: research
Status: resolved
Blocked by: none

# 盘点注册来源及其频率与发布滞后

## Question

对当前生效目录的每个指标（含三核心，CNY030 为 P2），当前由哪个注册来源提供（TuShare 接口名或官方直连 URL/适配器）、更新频率、统计期粒度、上游通常的发布滞后（日频的更新时点；月/季频距统计期末的天数）？代码里已有哪些可直接复用的频率/发布窗口/宽限登记（如 release_calendar、source_families、metric_contracts）？哪些指标目前只能靠 Tavily/Exa/AI WebSearch 取得？

TuShare 的更新时点与字段须以 TuShare 官方文档为一手来源；给出每项结论的依据。不改代码。

## Answer

详见 [研究：注册来源、频率与发布滞后](../research/02-registered-source-freshness.md)。
- 生效目录由代码组装：`catalog.py` 的 metric-catalog-v0002 加上迁移 `cny030-optional-ecb-margin-v0001`（`candidate_admission.py:52`），共 59 项，其中 P0 6、**P1 41**（不是 42）、P2 12，数量由测试 `test_cny030_optional_migration.py:110-112` 断言。
- 来源分布：TuShare 31 项、官方直连 17 项、派生 5 项、运维证据 2 项。没有注册路径的 4 项是 USDCNY 16:30、VIX、SOX（均为 P2，搜索和解析也兜不住）和 `CN_MARGIN_BALANCE_SSE_SZSE`（P1，TuShare `margin` 接口可取，但新 ID 未接线）。
- 代码里没有逐来源的滞后或宽限登记。能复用的只有 `ReleaseExpectation`/`assess_release_state`（目前仅 LPR 实现了窗口）和 `evidence_max_age_days`（日 10 / 月 95 / 季 190 / 事件 370）。
- TuShare 文档只给出 daily、index_daily、margin、shibor 等接口的更新时点；宏观接口没有写，时效需按 NBS 和 PBoC 的官方日程推定，再加一个待定的宽限。另有风险：`index_dailybasic` 的文档覆盖范围不含 000300 和 000852。

