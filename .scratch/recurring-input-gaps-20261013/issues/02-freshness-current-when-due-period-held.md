Status: done
Type: task
Category: bug

# 02：证据时效按词表判定

**What to build:** 持有期不早于应有期即判 current，下一期已公开但未持有不再把它降为 awaiting_release；未过宽限为 awaiting_release，已过宽限为 stale。T+1 冻结时 DR007、DR007 政策利差、公开市场操作量价、SHIBOR、人民币中间价这类当天已持有的项显示 current，报告、页面与缺口清单一致。见 [规格](../spec.md) 与 CONTEXT.md“证据时效”。

**Blocked by:** None (can start immediately)

**主要模块：** 证据时效判定及其消费者（批次时效、成员读数状态、缺口清单）。

- [x] 持有期等于应有期、下一期已公开未持有：current
- [x] 持有期早于应有期、未过宽限：awaiting_release；已过宽限：stale（按主调度裁定改为“早于应有期 → stale”；前半句对已持有项不可达，见实施记录）
- [x] 消费时效标签的报告、页面与缺口清单行为一致，无连带回归
- [x] 受影响测试与切片收尾冒烟通过

## Comments
- 2026-10-13 红→绿第一切片：`assess` 改为持有不早于应有期（代码 due_period，含宽限）即 current；契约测试 28 passed。下一步：排查消费者与受影响测试。
- 2026-10-13 受影响测试 31 个文件 516 例：512 passed、4 failed（均为 awaiting_release→current 的预期变化：holiday_freshness 2 例、release_preannouncement 2 例），已改期望并复跑 14 passed。CONTEXT.md“证据时效”已改。下一步：冒烟、重型、ruff/mypy、审查。
- 2026-10-13 冒烟 2 passed（33 秒）；重型两文件（flock）4 passed（6:00）；Codex 两轴审查完成，标准轴一轮阻断已处置，定向复审通过。

### 2026-10-13 实施

**口径（主调度裁定，经用户授权）**：应有期取代码的 `due_period`（推算发布时点加宽限已过的最新期）。持有期不早于它即为 current，落后于它即为 stale；`released_period` 只标注“下一期已公开”，不再参与判定。

- **为什么 awaiting_release 对已持有项不可达**：`due_period` 按定义是宽限已过的最新期。持有期早于它，就说明至少这一期已经过了宽限，只能判 stale。规格测试决定的第二例“持有期早于应有期且未过宽限 → awaiting_release”因此构造不出来，改测“早于应有期 → stale”（契约测试 CSI1000 落后 1 期）。`awaiting_release` 现在只出现在发布判定里：计划的补缺发布门禁（`worker.py` `release_gate`）和 LPR 发布日历（`release_calendar.py`）。
- **改动**：
  - `src/pring_cycle/freshness.py` `assess` 的已持有分支改为 `due is None or held >= due` 判 current，否则 stale。提前退出时 `due` 为 None，表示持有期已不早于一个尚未到期的期次，判 current。模块文档串同步改写；`_ORDER` 删去已不可达的 `awaiting_release`，`worst()` 只作用于即时 `assess` 的结果。
  - `CONTEXT.md`“证据时效”改为：持有期不早于应有期为 current，落后为 stale；下一期已公开只作标注；`awaiting_release` 只用于发布判定（计划的补缺发布门禁、LPR 发布日历）。
- **消费者核对（读码，并由 Codex 规格轴复核）**：
  - 缺口清单原先跳过 awaiting_release，现在同样跳过 current，所以清单内容不变。
  - 报告与页面读取同一份投影缺口和同一判定时点。
  - 成员读数 `period_status` 只看 `periods_behind`，本票未改。
  - 派生项通过 `assess_catalog` 取各输入的 worst，DR007 政策利差在 T+1 下为 current。
  - Worker 的 P0 unconfigured 检查不变。
  - 体检直接读取批次表：新批次中这 5 项不再列为非 current，旧批次保留原标签。
- **预期变化（awaiting_release → current）**：
  - 契约测试：CSI500（持有 09-22、应有 09-22、已公开 09-23）、EIA WTI、LPR。
  - 假日时效：DR007 国庆（持有 9/29，9/30 已公开）、10-09 运行的国内日频持有 9/30。
  - 发布预告：8 月 CPI 两例（持有 7 月，8 月已公开但未到期）。
- **新增断言**：
  - CSI500 的 `status/held/due/released` 为 current、09-22、09-22、09-23（下一期已公开作为标注）。
  - 人民币中间价持有 09-22、09:15 已公开 09-23 → current（T+1 形态）。
  - 按 Codex 推演，在目标日 10-12、冻结 10-13 12:31 的条件下：DR007、SHIBOR、公开市场操作量与价、中间价均为 `held=due=10-12、released=10-13` → current；政策利差为 current。
- **测试**（venv `dev-venv-rig02`）：
  - 首轮受影响测试 31 个文件 516 例：512 passed、4 failed（即上列假日与发布预告的预期变化），用时 25:25。这一轮范围偏大，且与票 01 并行争用机器。
  - 改期望后复跑 `test_freshness_contract`、`test_holiday_freshness`、`test_release_preannouncement`、`test_derived_context_freshness`：72 passed（1:02）。
  - 冒烟 2 passed（33 秒）；重型 `test_worker_registered_catalog.py` 与 `test_core_carry_forward.py`（flock）4 passed（6:00）。
  - ruff check / format 通过；mypy 对 `freshness.py`、契约与假日测试无问题。`test_release_preannouncement.py:115` 有 1 条既有错误，不是本票引入。
- **审查**（Codex 两轴）：
  - 规格轴无阻断。确认 5 项与派生利差在 T+1 下为 current，提前退出不会误判任何频率，CONTEXT 改写未越界。
  - 标准轴首轮判阻断，共三条：
    - (1) 应有期词条与 `due_period` 含不含宽限有出入：不采纳，按裁定留给用户，见遗留。
    - (2) LPR 发布日历仍会把 awaiting_release 写入投影行：不改代码。它是独立的发布判定机制，早于本票存在，`context_projection` 又由票 01 在改。CONTEXT 与文档串改为把 LPR 发布日历列为保留 awaiting_release 的发布判定。
    - (3) `_ORDER` 有不可达成员：已删除。
  - 定向复审：阻断无。
- **遗留**：
  - CONTEXT“应有期”词条写的是“推算发布时点已过的最新统计期”（不含宽限），代码 `due_period` 含宽限。两者的出入交用户决定。
  - LPR 投影行在当月 LPR 未发布或仍在宽限内时仍显示“等待发布”。这是发布日历的判定，与批次时效 current 并存。若用户希望页面不再出现，另行开票。
  - 成员读数（落后一期仍 current）与批次时效（落后一期 stale）口径不同，是既有差异，本票未改。
