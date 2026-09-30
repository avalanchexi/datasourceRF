# 06: 投影也复核融资余额、指数行情、估值的原件

**What to build:** 上下文投影对 `CN_MARGIN_BALANCE`、指数行情（CSI300、CSI500、CSI1000、CNY030、930916、NHCI）、`CN_INDEX_VALUATION` 走可采用声明模块的同一家族复核；原件损坏的声明在投影中不可采用，与检索侧一致。

**Blocked by:** 05

**勿并行：** 07、08、09、16、23、26、28、30（同改：上下文投影；逐区明细见 [README](../README.md)「串行约束」）

**Status:** done

来源：[架构评审](../README.md) 候选 2 差异 1（用户判定为遗漏，2026-09-29）。 规格：[spec.md](../spec.md)「三、可采用声明模块」。

## 现状

检索侧 `search_evidence.py:263–290` 用 `tushare_claims_matching_acquisitions` 按各自解析器重解析原件，损坏即拒用；投影 `_metric_rows` 无对应分支，只凭声明质量与时效显示并参与分析（`context_projection.py:1587`）。未见有意豁免的说明。05 完成后，这一差异只是投影调用处"跳过这三类"的一行。

注意：`CN_MARGIN_BALANCE_SSE_SZSE` 不属于融资余额复核分支（`search_evidence.py:264`），不因名称相似纳入。

## 验收

- [x] 投影删除对这三类的跳过；原件损坏时投影行不可采用（状态与其他家族复核失败一致）。
- [x] 按 TDD 补投影侧用例：融资、指数、估值各一例原件损坏即不可采用；原件完好时投影输出不变。
- [x] 受影响测试经 `check.py quick` 通过；切片收尾两例快速冒烟通过。
- [x] 代码审查无阻断。

## Comments

**2026-09-30 实施记录**

- **改动**：投影的跳过集合 `_NOT_RECHECKED_IN_PROJECTION` 只保留三核心（由核心就绪复核）。融资 `CN_MARGIN_BALANCE`、六种指数行情、估值改走可采用声明模块复核；复核失败的行与其他家族一样为 `source_failed`。`CN_MARGIN_BALANCE_SSE_SZSE` 不属融资复核家族，照旧。内置目录照旧不复核。
- **实际影响范围**：当前模型里作为投影上下文行读取的只有 NHCI（价格链）、CNY030 与 930916（政策传导）。它们的原件损坏时，之后生成的投影行变为 `source_failed`，不再参与方向与宏观判断；已经发布的投影不会追溯改变。融资、估值和三个 CSI 指数目前不作为上下文行，只有模型将来读它们时才生效。
- **测试**（先红后绿）：`tests/models/test_registered_model_inputs.py` 在融资、指数、估值三个原件损坏用例里补了投影行断言。用投影的行构建函数 `_metric_rows` 直接取行（先例：`test_context_projection` 导入 `_role_direction`）：原件完好时不是 `source_failed`，损坏后是。NHCI 另经 `build_context_projection` 端到端确认；估值按维度确认恰好是被损坏指数的 3 行失败，其余 6 行不受影响。改动前这些断言失败（完好与损坏都显示 `stale`）。
- **验证**（`PYTHONPATH=src`）：涉及投影、NHCI、融资、估值、CSI 指数的测试文件，加 Worker 执行、收尾冒烟、完整目录正例，共 544 例全过（22.6 分钟）；审查后加强的用例 16 例全过。ruff、mypy 通过。
- **审查**（Codex 只读）：未发现阻断项。已按意见更正辅助函数注释（当前模型读取的是 NHCI、CNY030、930916，不只 NHCI），并加强估值断言。

