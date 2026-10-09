# 2026-10-02 架构评审终点真实运行发现

来源：[架构评审](../architecture-review-20260929/README.md)终点。全套 `check.py full`（`b490b90`）1433 例全过；真实完整运行 `run-b7ccf5dbbe8e21b2a6fc`（代码 `da340d2`，模型 v0014／目录 v0006，不指定目标日，系统定为 2026-09-30；国庆休市期间 10-02 21:29 提交），`completed`／`changed`，57 分钟，取数约 840 次，Tavily 14、AI 联网搜索 3、Exa 0，完成后 SIGTERM 停止 Worker。基线 `run-ad6793255ccb423e2bd1`（v0013，目标日 9/28，缺口清单只有 SOX）。

> *本段与各票的根因由 AI 汇总（Codex 只读调查，SQL 只读打开运行库）。*

**结果**：信用脉冲在 v0014 下 `current`，过热卡 `cooling`；正式阶段同基线（`noncanonical_combination`），无核心沿用。架构评审票 03（广度血缘）、04（外盘日历）核对通过。缺口清单由 1 项变为 28 项，无一由本轮票面改动直接引起：

| 类别 | 项数 | 去向 |
|---|---|---|
| 节假日应有期 10/01（运行内日历只覆盖到目标日） | 21 + 融资余额 | 票 01 |
| 目录切换使旧声明不可见：OMO 利率基准丢失、DR007 政策利差缺失；广度／篮子／仓单整窗重取 | 2 | 票 02 |
| 郑商所 SSL 失败 14 日、5/18 时钟错误 | 1（仓单） | 票 03、04 |
| 已取得目标期仍被旧候选改判"检索未通过"（OMO 操作量、USDCNY 中间价） | 2 | 票 05 |
| DR007 9/30 TuShare `repo_daily` 返回空 | 1 | 上游事实，随票 01 修正后为等待发布 |
| SOX 授权缺失 | 1 | 既定，同基线 |

另：票 30 列的核对项"TuShare CPI/PPI 交付含一月累计值整次被拒"本次证实（票 06）。

| 票 | 问题 | 是否重构回归 | 状态 |
|---|---|---|---|
| [01](issues/01-holiday-due-period-calendar-coverage.md) | 节假日被当成应有期：运行内日历只覆盖到目标日（同 20260928 票 03，当时 wontfix） | 否，既有 | done |
| [02](issues/02-catalog-switch-hides-unchanged-claims.md) | 目录版本切换使语义未变的声明全部不可见 | 是，由票 25 触发 | done（07、08、09） |
| [03](issues/03-czce-warrant-ssl-failures.md) | 郑商所仓单 14 天 SSL 失败 | 未见证据 | wontfix（2026-10-09 分流：10-03 后零复现） |
| [04](issues/04-czce-acquisition-time-invalid.md) | 郑商所 5/18 `acquisition_time_invalid`（同 20260928 票 01） | 否，既有 | done（(a) dd2058c：CF 时钟回跳只拒该品种该日；(b) 用户决定 wontfix） |
| [05](issues/05-rejected-candidate-overrides-held-target.md) | 已取得目标期被旧候选改判"检索未通过" | 否，既有 | ready-for-agent（2026-10-09 分流：现象未复现、根因仍在） |
| [06](issues/06-tushare-price-delivery-january-ppi.md) | TuShare CPI/PPI 含一月累计值整次被拒 | 否，既有（票 30 核对项） | done（lookback 批次，693db3f） |
| [07](issues/07-same-definition-read-and-selection.md) | 02a：相同定义——读取与选值跨版本归并 | 票 02 拆分 | done |
| [08](issues/08-same-definition-held-days-and-ingest.md) | 02b：相同定义——已持有日与入库查重（依赖 07） | 票 02 拆分 | done |
| [09](issues/09-same-definition-original-checks-and-cache-keys.md) | 02c：相同定义——原件复核与缓存键（依赖 07） | 票 02 拆分 | done |
| [10](issues/10-omo-rate-dropped-when-notice-ingested-for-amount.md) | OMO 公告原件写了利率，入库只存了操作量（验收运行发现） | 否，既有 | duplicate（并入 lookback 02） |
| [11](issues/11-first-retrieval-plan-before-run-calendar.md) | 完整补缺首次规划在装入运行日历之前（票 01 审查发现） | 否，既有 | ready-for-agent |
| [12](issues/12-scheduler-skips-only-weekends.md) | 盘后自动调度只排除周末（票 01 审查发现） | 否，既有 | ready-for-agent（运行库调度已开启） |

**分流（2026-10-02）**：01 节假日沿用上一期、国内国外分开（ready-for-agent）；02 按 [ADR-0036](../../docs/adr/0036-observation-identity-by-same-definition.md) 实施（ready-for-agent）。顺序 02 → 01，两张完成后跑一次真实完整运行一起验收。03–06 待分流。

## 验收运行（2026-10-03）

> *本段由 AI 在验收时生成。*

代码 `e439ae4`（票 07 `6fa8941`、09 `317f531`、08 `905ede0`、01 `e439ae4`）。

**全套** `check.py full`：1465 例中 1464 过、1 败，45.8 分钟（基线 `b490b90` 1433 例 48.3 分钟）。失败为 `test_tushare_call_quota.py::test_a_call_over_the_minute_waits_for_the_oldest_to_age_out`，`acquisition_time_invalid`：该测试时间线取系统墙钟加偏移，WSL 时钟回跳即触发；单独重跑 3 次、整个文件 16 例均通过。与本轮改动无关，属已知时钟抖动（同 [20260928 票 01](../run-findings-20260928/issues/01-wsl-clock-acquisition-time.md)、本目录票 04）。

**真实完整运行** `run-cfb8d12142289f56af73`：不指定目标日，系统定为 2026-09-30；2026-10-03 02:01 提交（国庆休市期间，节假日场景得以覆盖），`completed`／`changed`。从受理到投影生成 9 分 10 秒（基线 54 分钟）；之后机器休眠，监视器墙钟不计。完成后已用 SIGTERM 停止 Worker。

| 项 | 基线 `run-b7ccf5dbbe8e21b2a6fc` | 本次 |
|---|---|---|
| 缺口清单 | 28 项 | **3 项** |
| 取数请求 | 843 次 | **219 次** |
| 广度 `daily`／`stk_factor_pro` | 120／120 | **0／0** |
| 篮子 `fut_daily` | 60 | **0** |
| 郑商所仓单 | 241 | **0** |
| `fut_wsr`（既有按范围分段） | 50 | 50 |
| Tavily／AI 联网搜索 | 14／3 | 6／1 |
| P1 证据完整 | 38/43 | 42/43 |
| 核心、广度、SHIBOR 等国内日频（国庆） | 应有 10/01、落后一期 | **current** |
| DR007 | 落后两期 | **awaiting_release，落后 0 期** |
| VIX、美债 10Y | awaiting_release | 不变 |
| OMO 利率 | `not_held` | 持有 9/28（v0005 声明可见） |
| DR007 政策利差（投影） | 算不出 | **−1.38bp（9/29，current）** |
| 信用脉冲／过热卡 | current／cooling | current／cooling |

- **票 02（07／08／09）通过**：换目录后旧声明可见、原件复核通过；广度、篮子、仓单不再整窗重取（只取新日），运行时长与请求数大幅下降。基线运行中 14 个郑商所 SSL 缺日现由 v0005 已持有的声明补上，`CN_FUTURES_WARRANTS` 不再在清单中。
- **票 01 通过**：国庆期间国内指标沿用 9/30 不判落后；外盘按美国日历判断，结果与改动前相同。
- **剩余 3 项**：SOX `license_missing`（既定）；`CN_OMO_7D_RATE` 持有 9/28、应有 9/29 落后一期，及随之的 `CN_DR007_POLICY_SPREAD`——9/29 公告原件写明 1.40%，但入库只存了操作量（开 [票 10](issues/10-omo-rate-dropped-when-notice-ingested-for-amount.md)，既有问题，回执早于本轮改动）。投影仍以 9/28 基准算出 9/29 利差。
- **其他观察**：库存卡生产方向由"无"变为"冲突"、库存方向由"下"变为"上"——输入更全后的信号分歧（P1 42/43），两次投影均无来源冲突。

结论：run-findings 01、02 实施并验收完成；新开票 10、11、12（`needs-triage`）；03（SSL 缺日已由旧声明补上，可考虑关闭）、04（时钟，全套再现一次）、05、06 待分流。

