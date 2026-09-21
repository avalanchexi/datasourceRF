Status: ready-for-agent
Type: task-batch
Date: 2026-09-21

# 可并行任务组 B（#28 开工前的铺路与记录对齐）

承接 [任务组 A](parallel-tasks-20260921.md)。A 组四项与其串行项已于 `fb8937b` 收口
（见 [claims_valid 成本调查](finding-claims-valid-cost-20260921.md)）。

## 调度约束（先读这一条）

**重型计算仍然串行，一次只跑一个。** 9.7 GB 内存 / 12 核，一轮完整套件的 `--basetemp`
会涨到 20 GB 以上；2026-09-20 就发生过一轮在跑、另一轮启动，双双被系统杀掉。

本组 B1–B5 可以并行，因为它们**都不运行重型验证，也都不改 `src/`**。这两条是并行的前提，
不是巧合：

- **不改 `src/`**：本机装的是 `--no-editable` 副本，任何一项改了源码就得 `uv sync` 重装，
  而那个副本是全组共用的。一边重装一边有人在跑测试，跑的是哪一版都说不准。
- **不跑重型**：见上。

**输出文件互不重叠**（下表每项都写不同的文件），所以并行写入不会互相覆盖。特别注意
**B1 独占 `28-trade-calendar-never-acquired.md`，B2 不得碰它**。

完整套件按 [ADR-0014](../../docs/adr/0014-full-suite-only-at-freeze-points.md) 需要显式
`tools/check.py full --freeze`，本组任何一项都不触发它。

## B1 · #28 事实对齐并落盘（主线程执行，结论已在手）

2026-09-21 的只读核对发现 #28 票面的根因描述有三条已经过时：

1. 「`trade_cal` 的采集请求数为 0，从未发起」——`worker.py:323` 的 `_refresh_core_sources`
   → `core_history.py:85` → `acquire_calendar`，在 `full_retrieval.retrieve` **之前**就会采集。
2. 「没有适配器负责」——`source_adapters.py:164` 的 `acquire_calendar` 一直都在。
3. 「7 次投影无一例外空阶段」——`4be17e2` 的实施记录写明这条「已由只读运行库核验反证」。

四项验收的读码判断（**待实测确认**）：1 未证；2 大概率已满足
（`test_worker_calendar_gate.py` 已钉住）；3 **未满足**——`full_retrieval.py:213` 至今把
`CN_TRADE_CALENDAR` 标为 `operational_evidence`，而 `required_calendar` 仍必需它，
规则层面「不采集但又必需」依然成立；4 未违反。

另有一处没人记过的口子：`_refresh_core_sources` 在 `TUSHARE_TOKEN` 缺失时**静默 return**，
之后以 `p0_required_calendar_unavailable` 停下——分类指向「日历不可用」，真实原因是没配 token。
这正是验收 2 想区分的那类混淆。

产出：写入 `finding-28-calendar-facts-20260921.md`；把 #28 的 `Execution:` 改为实况；
订正 `plan-19-preflight-remaining-checks-20260920.md` 里「#28 票面已在 09-19 更新为
`completed`、四项全勾」那句——票文件自 `6c5f5f1` 创建后从未被改过，那句不属实。

## B2 · 票面 Execution 标签与实况对齐（只读核对 + 改票面）

`Execution:` 字段普遍陈旧，会让下一轮取错票。

> **2026-09-21 订正（B2 执行后回填）**：本段原先断言「#04–#08、#11 写着 `blocked`，
> 但依赖 02/03 已 `completed`，所以标签陈旧」——**这个前提不成立，是写任务书时的误判**。
> 提交时间戳显示 `3231539`（#03 → completed）为 `2026-09-06 22:19:13`，而 `aac107f`
> （给 #04/#05 写入 `Execution: blocked`）为 `22:21:10`：`blocked` 是在依赖完成**两分钟后**
> 写上去的，写的人清楚依赖已满足。真实阻塞原因写在各票票尾，与 `**Blocked by:**` 那行无关
> ——#05 是「北交所 4 次公开请求均 403」，#04 是「全部日线仍缺绑定数值版本的实际公开时间」，
> #06–#08、#11 同理（`e0d06cc`）。**这六张票缺的是外部原件，写代码解除不了，不得改成
> `in-progress`**。详见 [Execution 字段审计](audit-ticket-execution-20260921.md)。

逐票核对 28 张票的 `Status:` / `Execution:` / `Blocked by:` / 勾选数与 git 历史是否自洽，
把不自洽的列出来并改正 `Execution:` 一项。**不改 `Status:`，不勾选任何验收条件**——
那两者要有实证才能动。**不得碰 #28**（B1 独占）。

产出：`audit-ticket-execution-20260921.md` 列出每处不一致与依据（哪个提交、哪条证据）。

## B3 · #19 维度反例：逐家族可达性分类（只读）

`plan-19` 已确定维度反例应建在 `CN_INDEX_VALUATION` 上（`tushare_context.py:968` 起逐指数
`_call`，某指数返回空行是合法交付形态），也已确定 `CN_MARGIN_BALANCE` 不可达（全部必需成员
来自同一次交付，缺列在传输边界即被拒）。判据是**交付粒度**：同次交付 vs 分次交付。

`REQUIRED_DIMENSION_MEMBERS`（`metric_contracts.py:52`）其余家族按同一判据逐个分类：
`CN_LPR_1Y_5Y`、`CN_M1_M2`、`CN_OMO_7D_AMOUNT`、`CN_FUTURES_WARRANTS`、`CN_EQ_ADV_DEC`、
`CN_EQ_NEW_HIGH_LOW_120`、`CN_COMMODITY_SLEEVE_CONTRIBUTION`。

对每个家族回答：必需成员是否来自同一次 `_call`？若是，「应有而未交付」的状态能否经合法公开
入口到达，还是必然在响应字段校验或原件一致性校验处被拦？**不要绕合同造夹具去试**——
plan-19 记过一次那样的尝试，两条路都被守卫拦住，测试已撤除。

产出：`finding-19-dimension-reachability-20260921.md`，逐家族给出「可达 / 不可达 + 拦截点」。
若逐家族核对后确认除 `CN_INDEX_VALUATION` 外都不可达，明确写出来——那会让
`pending_checks` 里的 `dimensions` 该记为「合同上不可达」而非留一个永远验不了的待办。

## B4 · #27 迁移影响面盘点（只读）

#27 要重命名 `CN_USDCNH_FXCM`、删除两项、新接三项官方通道。票面写明「指标 id 是身份的一部分：
**重命名与删除必须作为迁移设计**，波及目录版本、历史声明与投影」。

盘点这五项指标 id 在 `src/`、`tests/`、`.scratch/` 的目录/清单里各出现在哪些位置，按
「目录定义 / 历史声明 / 投影与报告 / 测试夹具 / 文档」分类，并指出哪些位置一旦改名就需要
迁移而不能原地替换。**不提出方案，只给影响面**——方案归 `/implement` 那一刀。

产出：`survey-27-identity-migration-20260921.md`。

> **2026-09-21 执行后回填**：盘点结论是 #27 **不是一张小票**。六项指标在生产库里一条历史声明都没有
> （`source_claim` 全库 272,949 行中各 0 行），所以要迁移的不是观测值而是**目录定义本身**——
> 它已冻结进 18 个 `model_version` 清单。`_P2` 元组（`catalog.py:90`）是 v0001/v0002/v0003 三个
> 目录版本的共同输入，改一个字符串同时改写三份「不可变」历史目录，`catalog.py:14` 的
> `_METRIC_CATALOG_V0003_SHA256` 会在 import 阶段就抛；而 `runtime.py:267` 每次
> `initialize_runtime` 无条件重跑 `create_candidate`，`_P2` 一改运行库下次就起不来
> （`model_version_is_immutable`）。另外 `metric_id` 是 `observation_id` 的哈希输入
> （`evidence.py:1441`），`release_event_family` 就是 `metric_id.lower()`——**改名即改 event_key**。
> 票面与 09-17 的 ECB 决定不一致，已订正。

## B5 · `registered_definitions` 去重的落点核对（只读）

[JSON 解析调查](finding-json-decode-cost-20260921.md) 把它排在落点第一：实测 6.33 秒、
重复率 99.995%、无自比风险，且「`shared_read_scope` 已经给出了适用条件」。

核实：`catalog_registry.py:74` 的 `registered_definitions` 每次调用都重开只读连接、重算 sha256、
解析 74 KB、再 `json.dumps` 一遍（`_definition_document` 被调 21,140 次）。回答三问：
(1) 它的输入是否真的只有 `(database_path, version)`；(2) 在一个 `shared_read_scope` 内缓存它
是否会让任何一处校验失去意义（对照 `_commodity_document` 那道 `!=` 校验被否决的理由）；
(3) 缓存值有多大、会不会重蹈 A 组「要常驻 110 份快照」的覆辙。

产出：`finding-registered-definitions-reuse-20260921.md`，含「能否安全复用」的结论与理由。
**不改任何源码。**

## 串行队列（B 组执行后重排，一次一个）

B 组把四项的前期调查全部做完，落点都已确定，因此顺序按「落点清晰度 × 量级」重排：

1. **S1 · `registered_definitions` 复用**：B5 判定可安全复用，键为 `(str(database_path.resolve()), version)`，
   作用域内仅 **1 条**缓存（生产库该表只有 1 行，解析值约 124 KB），并已给出 5 条待钉断言。
   改动面最小、落点最清晰，适合作为热身。
2. **S2 · #19 维度反例**：B3 判定可达，Codex 独立复核 11 道守卫后确认「采集与入库途中没有一行拦得住」。
   反例建在 `CN_INDEX_VALUATION`，断言三条精确到 `index + measure`。注意两处：期望集需先定目录版本；
   `CN_FUTURES_WARRANTS` 虽可达却走专用诊断，不可用作反例。
3. **S3 · #28 收尾**：B1 查明四项验收已覆盖三项，只剩三件小事——补 `TUSHARE_TOKEN` 缺失分支的
   可分失败分类、给验收 1 一条以本票为主旨的用例、逐项勾选附证据。**不要新建日历采集器。**
4. **S4 · #27 身份迁移**：量级最大，且**不宜直接 `/implement`**。B4 查明它触及
   「已冻结进 18 个 `model_version` 清单的不可变目录如何演进」这一架构问题：`_P2` 是三个目录版本的
   共同输入、`_METRIC_CATALOG_V0003_SHA256` 在 import 阶段设闸、`metric_id` 是 `observation_id`
   的哈希输入、`release_event_family` 即 `metric_id.lower()` 故改名即改 `event_key`。
   这类不可逆决定应当先有 ADR，再进实施。另有三项官方通道**全部需要新适配器**。
5. **S5 · 完整套件**：需显式 `--freeze`，由人判定。

每项各自一个 context（`/implement` 的惯例），中间 `/clear`。

## B 组执行小结（2026-09-21）

五项全部完成。值得记下的是：**其中四项纠正了前一轮的记录**——B2 用提交时间戳推翻了本任务书
自己写下的前提（#04–#08/#11 的 `blocked` 是外部原件缺失，不是依赖未满足）；B3 修正了 plan-19
的可达性判据（不只看交付粒度，还看 builder 遇缺值是 `raise` 还是 `continue`）；B5 改正了
JSON 调查的行号（`catalog_registry.py` 只有 126 行，`:106`/`:111` 不存在）；B4 发现 #27 票面
与 09-17 的 ECB 决定不一致。

这不是偶然：本目录的笔记密度已经高到**转述开始失真**。凡引用他处结论，回原文核对，
不要引用转述——这也是 [Codex 分派](../../docs/agents/codex-delegation.md) 里要求
「让执行方自己去读背景文件」的由来。
