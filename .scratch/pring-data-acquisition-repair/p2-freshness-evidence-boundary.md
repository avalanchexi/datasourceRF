# P2 鲜度：当前来源观察与目标时点资格分开

2026-09-08，只读研究，源码 HEAD `68c87eaef1fa21ef62f74400f6c9b8e772fbf0ec`。复用 [研究 14](research-14.md)、[Treasury 增量](treasury-followup.md)、[EIA HTML 契约](eia-html-contract.md) 和已有原件；无联网、数据库、认证、模型或应用改动。

**已有证据足以实施“所选旧值落后于当前已观察官方期次”的独立提示，以及 EIA 下一计划日的前/当日/已过提示。它们不足以将历史目标日的 `current` 自动改成 `stale`，也不足以认定 EIA 已发布、尚未发布或官方延迟。** 不新增采购、许可或用户审批门槛；受限 P2 暂缺仍可完成状态透明交付，不改变正式阶段。

## Treasury：能说明当前观察落后，不能倒灌历史鲜度

已存 [官方 CSV 精确原件](evidence-14-treasury-followup/a14a321adffded36dfd9ab1aec72cc81423aeca271110f76569d37dd02ca4ee5) 13,961 字节，SHA256 与文件名一致。本轮标准库重读确认：08-28 的 2Y/10Y 为 4.34%/4.73%，09-04 为 4.37%/4.78%；对应同日利差分别为 39/41 bp。[官方 CSV 地址](https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/2026/all?type=daily_treasury_yield_curve&field_tdr_date_value=2026&page&_format=csv)

[研究取得回执](evidence-14-treasury-followup/receipts.json) 在 2026-09-07T06:37:53.830242Z 收到该快照。这证明研究当时观察到 09-04 行，不证明 09-04 任何历史钟点已公开。这里“旧值仍为 08-28”是旧研究快照和验收场景，本轮没有查询当前生产库。原始逐日 PUBLIC 仍未知。

可以直接实施：**同一指标/单位/来源身份的有效官方行已被当前观察取得，且其源统计日比所选值新时，保留所选值、期次、原件与认证状态，另显示“当前已观察官方数据至 09-04；所选值为 08-28”**。不需要先定义多少自然日算旧，也不能自动采用未认证的 09-04 值。若所选值因认证门禁不可展示，仍遵守原门禁，只展示可追溯的来源观察说明。

必须明确这个提示的范围，例如包含 `scope=current_source_observation`、`observed_at`、`selected_period`、`observed_source_period` 和证据引用；这是建议的最小数据契约，不是已实现状态。正式应用使用自己的取得/校验记录，不把研究回执倒填为生产 SYSTEM。缺少范围/观察截止时，先不要让这项比较改变原 `status`。

两个现有代码边界必须保留：

- [Treasury 解析器](../../src/pring_cycle/treasury_context.py) 的 `latest_reported_periods` 来自全年 CSV，更新发生在请求窗口过滤之前。请求截止 08-28 仍可能获得 `latest_source_period=09-04`；它只表明当前快照全年最新有效行，不能代表目标窗口最新可用值。比较时需明确全源观察范围；目标日判断必须另取符合目标范围且有时点资格的证据。
- [TargetBoundEvidenceRepository](../../src/pring_cycle/context_projection.py) 给所有 `metric_series` 查询增加目标日 **Asia/Shanghai 日末 PUBLIC 上界，SYSTEM 也适用**。所以 `source_period<=target_date` 加“现在已取得”仍不够。即使目标为中国 09-04，09-07 才观察到的美国 09-04 行、且历史 PUBLIC 未知，也不能证明目标日已有新值。

官方方法的约 15:30 Eastern 是报价采样，通常 18:00 前可用且允许延迟；9 月按 `America/New_York` 夏令时换算，前者已是中国次日约 03:30，后者为次日约 06:00，均不是可回填的实际发布记录。[方法原件](evidence-14-treasury-followup/f0043d5ea80ea54730c5b5ed5a8c8f105341afff6ed5edcc29f45a4ad039b23e)、[官方方法页](https://home.treasury.gov/policy-issues/financing-the-government/interest-rate-statistics/treasury-yield-curve-methodology)

要修改“目标时点鲜度”，仍需对应值/版本的可靠 PUBLIC 和适用源日历；跨境假期、允许延迟多久、缺多少期判陈旧等阈值本次没有冻结。**不能仅凭当前全年最大源日或通常日程绕过现有目标 PUBLIC 上界。**

## EIA：日期计划只用于计划描述

已存 [Brent 日页](evidence-14/b078a362332a3d6b34ae2a5dc5a91b98ddfacc7979410b32081f07e9dadc243e) 和 [WTI 日页](evidence-14/7da3e5b6632942bfedf02642fde22867d24bb0cf6477eff5ac9e5f9be4d92497) 均标 `Release Date=9/2/2026`、`Next Release Date=9/10/2026`，最新数值至 09-01。两页本轮 hash 复核分别为 457,442 / 472,300 字节；原件名称即精确 SHA。[官方 Brent](https://www.eia.gov/dnav/pet/hist/RBRTED.htm)、[官方 WTI](https://www.eia.gov/dnav/pet/hist/RWTCD.htm)

[发布总表原件](evidence-14-eia-followup/966a610f36397c815edc2ed6fcd3b857ea5725eb6ef6723dbea9a48990f02ae9) 54,803 字节、hash 相符，明确发布日历采用 Eastern Time；`America/New_York` 是沿用的工程映射。它没有给 RBRTE/RWTC 具体钟点，不能移植其他石油周报的 10:30 或 13:00。[官方发布总表](https://www.eia.gov/reports/upcoming.php)

只有该快照已在所讨论的**观察截止**可见，才能用其计划作如下描述；比较日期在来源时区进行，不能用中国零点抢先进入美国的计划日：

| 观察时刻（America/New_York） | 可诚实显示 | 不能推断 |
|---|---|---|
| 09-10 之前 | “已观察批次 09-02，数值至 09-01；该快照列示下一计划日 09-10，尚未到此计划日期” | 09-02—09-04 的日值必然尚未发布、必为休市或获取失败；不存在提前发布/更正 |
| 09-10 当天 | “已到快照列示的计划日期；尚无本次观察可证明的新批次” | 零点已发布、某个固定钟点已逾期，或必定能取到目标日值 |
| 09-10 之后且仍只有旧快照 | “已过快照列示的计划日期；新批次是否已发布尚未验证” | 官方延迟、官网没有更新、下载失败；旧页面上的计划仍是当前最新计划 |
| 实际读取的新有效批次/新数值已取得 | 保留新原件/真实取得与校验时间，按真实日期和字段更新“当前观察” | 新批次计划日期自动成为实际发布时间；新值自动获认证或历史 PUBLIC |
| 最近请求失败但仍有旧有效值 | 保留旧期次/批次/计划及最近失败原因，同时说明未验证新批次 | 把失败写成 0，或宣称官方取消/推迟发布 |

09-02 是所存页面声明的**批次发布日期**，不是全历史每行的首次公开时间。既有日期精度规则可在批次字段与版本关系正式核清后解释为该批次的保守可见边界；不能把计划 09-10 套同一规则来生成未来 PUBLIC。当前 [EIA HTML 入口](../../src/pring_cycle/eia_html.py) 正确保留 release/public 为 null，仅把批次日期和下一计划日写入取得元数据，本轮不改变它。

若“当天”没有具体发布时刻，就不应新增小时级逾期规则；若之后没有再取页面，就只能说计划日已过、更新未验证。需要自动判“官方应已发布/已延迟”的额外源日历或容忍阈值尚缺，但不妨碍先实施上表的事实描述。

## 最小实现反例与现状

当前 [投影](../../src/pring_cycle/context_projection.py) 已传出 `latest_source_period`、`release_date`、`next_release_date` 和来源时区；`_evidence_status` 仍按日频 10 个自然日等旧阈值判断，`_release_status` 仅处理 LPR。元数据存在不代表本报告建议已实现。[取得尝试查询](../../src/pring_cycle/evidence.py) 按 `fetched_at<=as_of`、目标日和定义过滤，但它并不凭自己建立目标日 PUBLIC 资格。

最低验收反例：

1. 当前观察已证 UST 09-04，所选 08-28：显示带观察范围的“落后于当前源”提示，保留值和认证状态；不自动派生/采用 41 bp。
2. 目标 08-28，全年元数据最大 09-04：不能判目标落后；目标中国 09-04、美国 09-04 行 PUBLIC 未知：同样不能判目标落后。
3. 新源只有 10Y 有效、2Y 缺值：各指标分别比较，不能把全表日期当两项都更新；不同日父项不能派生利差。
4. 快照取得/校验或源观察证据晚于所用观察截止：不能使用该新来源提示。最近一次请求失败，不应抹掉此前已有的有效来源观察，但需要保留其原观察时间，不能冒称刚刚验证。
5. EIA 中国 09-10 00:00 仍是美东 09-09：不能显示“已到美东计划日”；美东 09-10 00:00 无具体发布时间，不能判逾期。
6. EIA 美东 09-11 仍持旧快照：可说计划日已过、更新未验证，不能写“官方未发布/延期”或把新批次写成既成 PUBLIC。

下一步可直接实施独立的当前观察诊断与上述计划描述；若要改变目标时点 `status`，先补对应的时间资格和明确规则，不从本报告自动获得它们。P2 保持 context-only，不参与正式阶段、不增加受限来源采购硬门。

本轮精确新增文件只有 `.scratch/pring-data-acquisition-repair/p2-freshness-evidence-boundary.md`。原件仅只读复用；交付时提供报告字节/SHA与本地链接检查结果。这里的建议反例未运行应用测试，不冒充 HEAD 68c87ea 的 682 项既有全套覆盖。
