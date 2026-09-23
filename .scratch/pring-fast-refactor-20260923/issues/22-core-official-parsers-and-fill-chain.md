# 22: 三核心官方页面解析器与补全链

**What to build:** 新写中证指数官网（000985、000012）与南华官网（NHII）解析器并登记白名单主机；三核心缺失时按 TuShare 重试一次 → Tavily（达限改 Exa）→ AI WebSearch → 按网址重抓原文由解析器解析的顺序补全，仍失败交 21 号处置。

**Blocked by:** 19, 21

**Status:** done (NHII official parser blocked)

Spec: [spec.md](../spec.md)

- [x] 解析器对保存的官网页面样本解析出数值、统计期与发布日期
- [x] 经公开入口断言：TuShare 缺三核心一项时经检索补全，正式阶段正常产出
- [x] 补全链顺序与次数正确；解析失败时落入核心沿用或阻断
- [x] 受影响测试经 `check.py quick` 通过；切片收尾两例快速冒烟通过（按 ADR-0025）
- [x] 另加跑完整目录正例与三核心反例（涉及 Worker 编排/目录/来源），记录退出码与耗时

## Comments

- 2026-09-24 完成中证部分。`official_core.py`：中证官网 `https://www.csindex.com.cn/csindex-home/perf/index-perf?indexCode=…&startDate=…&endDate=…` 返回按交易日的 JSON（close/change/changePct）。解析器校验指数代码、日期在请求区间内、数值齐全，得出收盘、前收（close−change）、官方涨跌幅；页面无发布时间字段，公开时间按时效登记表（交易日 17:00）推算。样本 `tests/fixtures/csindex/`（2026-08-20~31 两指数真实响应）。登记主机 www.csindex.com.cn；核心选择校验与原文重核（`selected_core_claim_is_valid`、`parse_core_acquisition`）接受 `csindex:index_perf:<代码>:<日期>` 来源。
- 补全链：直连核心刷新时 TuShare 失败的核心只重试一次（`refresh_core_history(metric_ids=…)`，单核心传输错误不再连累其他核心），仍缺的中证核心取官网区间一次；之后的缺口进入运行检索（Tavily→Exa 备用→AI），中证核心的搜索候选须是官网上该指数的页面，并以登记接口按该交易日重抓、由解析器解析（期不符/晚于截止/与搜索值错位即拒收）；最终仍缺交 21 号沿用或阻断。
- **NHII 阻塞**：南华官网旧数据接口 `/ianalysis/varietyindex/{index|price}/NHII.json` 已 404；新“指数走势”入口跳到 webhq.nanhua.net 前端应用，数据经第三方行情网关（zealink）取得，没有可稳定解析的官方页面。NHII 只有 TuShare（含一次重试），失败即沿用/阻断。待南华提供可解析页面后再补解析器。
- 测试：`tests/conftest.py` 会话级默认让中证官网离线（模块级夹具也不会真实联网）。新增 `test_core_official_fill.py` 6 例（样本解析 2、拒收 1、公开入口补全 1、页面不可解析阻断 1、NHII 阻断 1）。

- 2026-09-24 回填：完整目录正例与三核心反例已包含在终点全套（票 28）中一并运行。`check.py full` 退出码 0，1211 例通过，用时 4051.5 秒；其中完整目录正例 `test_worker_registered_catalog.py::test_full_worker_falls_back_to_official_ppi_and_exposes_delivery_in_report` 用时 125.6 秒，三核心反例（`test_core_carry_forward.py`、`test_core_official_fill.py`、`test_structural_rejection.py`）均通过。
