# 26：无可靠发布日期时保留 PUBLIC 缺口

2026-09-17 用户在确认排队问题内容后明确答复「确认」。确认的问题为：DR007、Shibor 等历史数据没有可靠官方发布日期时，是否保持 PUBLIC 时间为空，只从系统真实取得并校验成功后进入 SYSTEM 查询。

## 已确认规则

- 有可靠实际发布时间：按该时刻进入 PUBLIC。
- 只有可靠发布日期：按来源本地时区的次日零点进入 PUBLIC。
- 无可靠发布日期：`release_at` 与 `public_available_at` 保持为空，不进入历史 PUBLIC 查询，不推测或倒填日期。
- SYSTEM 从真实取得并完成字段、单位、统计期与质量校验的 `available_at` 起可见，不将取得时间倒填为历史系统时间。
- SYSTEM 可见不自动等于模型可采用；来源认证、质量及模型输入条件继续独立生效。本决定不豁免真实 PUBLIC 回放条件。

这与 `CONTEXT.md` 和 ADR-0006 一致，无需改术语、增加 ADR、字段、计算函数或数据库迁移。#26 的领域决定收口；先前重复实现保持撤回。

## 对来源任务的影响

DR007/Shibor 无可靠日期的历史部分继续保留 PUBLIC 缺口，符合其他条件的真实新获取可以供 SYSTEM 使用。LPR 所选公告已有发布时间，逐原件核验；许可问题按既有用户决定处理。RRR 的生效/调整日期不能冒充公告日期，事件覆盖与公告时间仍归 #13 核验。

已有公开边界测试 `test_supported_publication_precision_controls_public_queries` 覆盖实际时刻、仅日期以及 SYSTEM 校验前后；`test_candidate_context_keeps_public_time_unknown_after_valid_fetch` 和重复导入用例覆盖未知 PUBLIC 保留及未认证值不被投影采用。任务 D 已取得最终通过，详见 `verification-taskD-codex-closeout-20260917.md`；其输入限制保留，本决定未改业务代码。

### 2026-09-17 22:47 用户明确选项确认

用户引用DR007/Shibor无可靠历史发布日期的问题，并选择：“保留历史缺口，按实际 SYSTEM 时间使用（推荐）”。这再次明确先前“确认”的含义：历史PUBLIC保持为空；SYSTEM按真实取得并校验成功的时间使用，仍须满足其他认证条件。无需变更既有领域规则或补造公开时间。该答复只针对#26，不作为TMA授权问题的回答。
