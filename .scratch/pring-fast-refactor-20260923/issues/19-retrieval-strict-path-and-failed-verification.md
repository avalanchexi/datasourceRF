# 19: 检索补缺：白名单、P0/P1 严格路径与“检索未通过”

**What to build:** 对 missing 与 stale 项（awaiting_release 不触发）自动检索补缺，结果同过门③后重评①②。候选主机须在按解析器家族登记的白名单内；P0/P1 只由登记解析器从重抓原文解析取值，与搜索渠道值在数量级/小数位或时效上差别很大时不采纳；页面须解析出发布日期且统计期不早于应有期。不通过则在缺口清单单列“检索未通过”（指标、应有期、≤3 候选网址、逐网址原因）。检索记录去掉回放/认证列，挂批次 id。见票 05。

**Blocked by:** 14, 18

**Status:** done

Spec: [spec.md](../spec.md)

- [x] 经公开入口（搜索与页面替身）断言：白名单主机 + 解析器成功时补入数值且缺口消失
- [x] 不在白名单 / 解析失败 / 统计期不符 / 无发布日期 / 日期晚于截止时点 各自产生正确原因
- [x] 搜索值与解析值数量级不一致时不采纳
- [x] 检索记录含渠道、查询、返回网址、抓取网址、原文哈希、解析器版本、结果与原因，挂批次 id；不在页面/报告展示
- [x] 保留手动深搜；无人工采用入口
- [x] 受影响测试经 `check.py quick` 通过；切片收尾两例快速冒烟通过（按 ADR-0025）
- [ ] 另加跑完整目录正例与三核心反例（涉及 Worker 编排/目录/来源），记录退出码与耗时

## Comments

- 2026-09-23 完成。`verify_search_candidates` 经登记解析器重抓候选网址，并通过新增的 `admit` 钩子在入库前拒收：无发布日期、发布时点晚于运行截止、P0/P1 搜索摘要中的小数/百分数与解析值恰差 10 的整数次幂（且无一吻合）即“与搜索结果不一致”。解析器报错映射为原因：不在白名单（含无解析器家族、重定向换主机）/ 统计期不符 / 无发布日期 / 解析失败 / 抓取失败。被拒候选不存任何数值，原文与哈希保留在取数记录上。迁移 0027 去掉 `retrieval_candidate_validation` 的 `run_attempt`、`public_complete`、`public_selected_claim_ids_json`，新增 `fetched_url`、`raw_hash`、`parser_version`；记录以 `run_id`（即批次 id）挂批次，不在页面或报告展示。去重改为同一运行内已完结（非抓取失败）的同网址同缺口。
- 缺口清单新增 `retrieval_failed`（页面“检索未通过”）：仍缺失/落后的指标附 ≤3 个候选网址与逐网址原因；未配置时效的指标保留原类别，只附候选；同一指标不再重复列为拒收。缺失指标现在也推算应有期。
- 手动深搜保留（`manual_deep_search`）；没有人工采用入口。新增 `test_retrieval_strict_path.py` 9 例。
- 触发条件：发布闸门原先只认 LPR 的发布日历，其余指标一律 `unknown_release_configuration` 不检索。现改为按时效登记表推算：本期登记发布时点已过即 released（缺失/落后项进入检索），未到即 awaiting_release（不触发）；未登记或事件型仍为 unknown。完整运行只对各指标最新一个已发布期打开检索（缺口清单的对象），120 日窗口里更早的历史日保持 unknown、不逐日检索（否则每次运行上百次级联）；定向运行按其指定期判断。
- 因此删去两例以“发布未知、后得发布记录才打开检索”为前提的完整运行用例（`test_newly_acquired_historical_publication_fact_can_open_full_run_search`、`test_resume_rechecks_unknown_release_without_mutating_initial_plan`）；其余完整运行用例改为只对 LPR 查询给结果或报错，P2 联合发布一例放宽单次上限。
