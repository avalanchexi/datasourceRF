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
| [01](issues/01-holiday-due-period-calendar-coverage.md) | 节假日被当成应有期：运行内日历只覆盖到目标日（同 20260928 票 03，当时 wontfix） | 否，既有 | ready-for-agent |
| [02](issues/02-catalog-switch-hides-unchanged-claims.md) | 目录版本切换使语义未变的声明全部不可见 | 是，由票 25 触发 | ready-for-agent |
| [03](issues/03-czce-warrant-ssl-failures.md) | 郑商所仓单 14 天 SSL 失败 | 未见证据 | needs-triage |
| [04](issues/04-czce-acquisition-time-invalid.md) | 郑商所 5/18 `acquisition_time_invalid`（同 20260928 票 01） | 否，既有 | needs-triage |
| [05](issues/05-rejected-candidate-overrides-held-target.md) | 已取得目标期被旧候选改判"检索未通过" | 否，既有 | needs-triage |
| [06](issues/06-tushare-price-delivery-january-ppi.md) | TuShare CPI/PPI 含一月累计值整次被拒 | 否，既有（票 30 核对项） | needs-triage |

**分流（2026-10-02）**：01 节假日沿用上一期、国内国外分开（ready-for-agent）；02 按 [ADR-0036](../../docs/adr/0036-observation-identity-by-same-definition.md) 实施（ready-for-agent）。顺序 02 → 01，两张完成后跑一次真实完整运行一起验收。03–06 待分流。
