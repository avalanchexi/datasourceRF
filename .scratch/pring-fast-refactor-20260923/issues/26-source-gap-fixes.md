# 26: 取数补洞：融资新 ID、PMI 频率、index_dailybasic 覆盖

**What to build:** 沪深融资余额新 ID 接入 TuShare `margin` 并登记时效；两项 PMI 差值频率改为 monthly；按 TuShare 官方文档核实 `index_dailybasic` 对 000300/000852 的覆盖，不覆盖时登记替代路径或明确记为缺口。

**Blocked by:** 13

**Status:** done

Spec: [spec.md](../spec.md)

- [x] 经公开入口断言：沪深融资新 ID 由 `margin` 取得并判定时效
- [x] PMI 差值按月频判定，不再每日 stale
- [x] `index_dailybasic` 覆盖结论附一手依据，并据此登记路径或缺口
- [x] 受影响测试经 `check.py quick` 通过；切片收尾两例快速冒烟通过（按 ADR-0025）

## Comments

- 2026-09-23 完成。`TushareContextAdapter.margin_financing_sse_szse` 取 TuShare `margin`，只合计 SSE 与 SZSE（BSE 行忽略，两所缺一即结构拒收），产出 `CN_MARGIN_BALANCE_SSE_SZSE`（scope `sse_szse`）；注册来源契约以“改名后的已审融资定义”为参照，原件复核按同一解析重建；Worker 仅抓取目录所含的那一个融资口径。时效登记表已有该 ID（T+1 09:05）。生效目录中两项 PMI 差值频率改为 monthly（时效按 PMI 父项月频判定）。新增 `models.effective_model_manifest()`（59 项、`model-v0012`、目录版本 metric-catalog-v0004），供登记与 27/28 使用。
- `index_dailybasic` 一手依据：TuShare 文档 https://tushare.pro/document/2?doc_id=128 写明“目前只提供上证综指，深证成指，上证50，中证500，中小板指，创业板指的每日指标数据”，不含 000300、000852。2026-09-22 真实请求三指数各返回 120/120 交易日（见 `.scratch/pring-window-publication-20260922/evidence-12-value-review.md`），故保留该注册路径并在时效登记表注明；若返回为空则按门①记缺失。
- 新增 `test_source_gap_fixes.py` 3 例；受影响 376 例全过。
