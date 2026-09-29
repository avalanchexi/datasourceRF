# 06: 投影也复核融资余额、指数行情、估值的原件

**What to build:** 上下文投影对 `CN_MARGIN_BALANCE`、指数行情（CSI300、CSI500、CSI1000、CNY030、930916、NHCI）、`CN_INDEX_VALUATION` 走可采用声明模块的同一家族复核；原件损坏的声明在投影中不可采用，与检索侧一致。

**Blocked by:** 05

**勿并行：** 07、08、09、16、23、26、28、30（同改：上下文投影；逐区明细见 [README](../README.md)「串行约束」）

**Status:** ready-for-agent

来源：[架构评审](../README.md) 候选 2 差异 1（用户判定为遗漏，2026-09-29）。 规格：[spec.md](../spec.md)「三、可采用声明模块」。

## 现状

检索侧 `search_evidence.py:263–290` 用 `tushare_claims_matching_acquisitions` 按各自解析器重解析原件，损坏即拒用；投影 `_metric_rows` 无对应分支，只凭声明质量与时效显示并参与分析（`context_projection.py:1587`）。未见有意豁免的说明。05 完成后，这一差异只是投影调用处"跳过这三类"的一行。

注意：`CN_MARGIN_BALANCE_SSE_SZSE` 不属于融资余额复核分支（`search_evidence.py:264`），不因名称相似纳入。

## 验收

- [ ] 投影删除对这三类的跳过；原件损坏时投影行不可采用（状态与其他家族复核失败一致）。
- [ ] 按 TDD 补投影侧用例：融资、指数、估值各一例原件损坏即不可采用；原件完好时投影输出不变。
- [ ] 受影响测试经 `check.py quick` 通过；切片收尾两例快速冒烟通过。
- [ ] 代码审查无阻断。
