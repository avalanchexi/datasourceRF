# 02: 降准：资讯监测与现行基准

**What to build:**
1. 登记降准资讯规则（`news_rules.py`，家族 `pbc_rrr_notice`）：句中须写明生效日期；按适用范围取调整幅度（下调记负、上调记正），按生效日记期（`event`，起止同日）；口径与 `official_context._parse_rrr_notice` 的原文句式分支一致（含“不含已执行5%存款准备金率的金融机构”与汽车金融、金融租赁公司定向调整）。句中出现时顺带取调整后加权平均准备金率与释放资金。
2. 每轮完整运行在本轮资讯里监测降准：不依赖缺口期，按句中生效日取期；命中即记新事件并留命中原话。
3. 未命中：已持有时记“本轮资讯未见降准公告”，沿用现行基准，不算缺失，不走官网、Tavily、AI。
4. 降准入模关口（`published_events.select_published_rrr_events`）同时认资讯规则命中原话的事件（ADR-0026 口径），现行基准生效至变更。

**Blocked by:** —

**Status:** claimed

Spec: [spec.md](../spec.md)

- [x] 资讯规则单测：央行原句的调整幅度、范围、生效日均取到；未写生效日期的句子不取
- [x] 经公开入口断言：本轮资讯含降准公告时，新事件被采用、留原话，并进入政策动作卡片
- [x] 已持有降准、本轮资讯无公告时，降准不在缺口清单，后续渠道未被调用
- [ ] 持有很早以前的降准仍作为现行基准被模型使用（待 Q11：120 天留存与投影可见窗口会清掉/隐去它）
- [x] 受影响测试经 `check.py quick` 通过；切片收尾两例快速冒烟通过（按 ADR-0025）

## Comments

- 2026-09-24 由原票 02 拆出（原票含追溯发现，拆为 03）。
- 2026-09-24 阻塞：资讯规则须有真实样本（`test_every_rule_is_exercised_by_a_real_sample`）。已存资讯原件（9/20–9/23）无降准句；TuShare `major_news` 当日 40 次额度已耗尽（`40203`）。9/25 额度恢复后取 2025-05-07 08:30–12:00 的 `major_news`（央行宣布 5/15 降准 0.5 个百分点，1–2 次调用）存为 `tests/fixtures/news/pbc_20250507_rrr.json`，再按 TDD 实施。
- 2026-09-24 前置已修：分析层（`context_projection`）此前不认资讯规则命中原话，资讯/媒体/AI 取得的官方完整性类指标在卡片里一律 `source_failed`；已改为与检索层同口径。降准入模关口 `select_published_rrr_events` 仍只认官方公告，属本票第 4 项。
- 2026-09-24 22:10 实施（待真实样本后提交）：`news_rules` 登记降准两条规则（不含 5% 机构的通用范围；汽车金融与金融租赁定向），`stated_event_days` 按句中生效日取期，`member_period` 对事件记 `event`；`tushare_news.fill_events_from_news` 在每轮拉取后监测（`NEWS_EVENT_METRICS`），事件以稿件发布时间为公开时间（`store_news_values(published_is_public=True)`，否则次日运行按目标日看不到）；`select_published_rrr_events` 同时认资讯命中原话的事件。偏差待用户确认：① 未登记“全体金融机构”（无“不含5%”）规则——近年降准均写明不含 5% 机构，找不到真实样本；② 调整后加权平均准备金率、释放资金暂不取——官方原文句式分支未定义其适用范围维度，硬写即臆造口径。
- 2026-09-25 00:04 取样本仍 `40203`：额度并非零点重置，疑为滚动 24 小时（9/24 约 15:26 用满）。今天下午再试一次，不反复试探。
- 2026-09-25 提交（除第 4 验收项）：规则真实样本暂用央行史表原句（`tests/fixtures/news/pbc_rrr_chronicle_20250515.json`，来源已注明非 major_news），额度恢复后补资讯稿样本。Codex 审查（Standards+Spec）属实项已修：生效日须在同句（`day_in_sentence`）、年份取离发稿日最近者、资讯事件 ID 含正文哈希（同页多稿不再冲突，也修了按缺口取值的同类隐患）、计划新增 `event_monitoring` 阶段（new_event / none_stated / news_unavailable）、命名 `published_is_public`。受影响 488 例 + 完整目录正例通过（仅缺样本一例，现已补）。官方与资讯混选移交票 03。
