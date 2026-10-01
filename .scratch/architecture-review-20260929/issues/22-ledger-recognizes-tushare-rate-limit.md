# 22: 检索账本认出 TuShare 限频

**What to build:** 适配器抛出带分类的来源异常，检索账本读取该分类；TuShare 限频（40203）按限频退避，不再按语义失败退避。

**Blocked by:** 18

**勿并行：** 无

**Status:** done

来源：[架构评审](../README.md) 候选 4 失败分类归属（用户决定，2026-09-29）。 规格：[spec.md](../spec.md)「五、获取结果模块」。

## 现状

- `TushareSourceError` 继承 `ValueError`，40203 在适配器内已单列为 `tushare_rate_limited`（`tushare_context.py:893`），但检索账本 `trace_acquisition` 只按异常类型分类，归为 `semantic_validation_failed`（`retrieval_ledger.py:452`），退避 6／24 小时，而限频应为 60 分钟或按 Retry-After（`retrieval_ledger.py:793`、`:819`）。
- TuShare 核心／日历 helper 对所有非零业务码抛普通 `ValueError("tushare_source_failed")`（`source_adapters.py:394`），业务码丢失；资讯按 `msg` 子串判断限频（`tushare_news.py:133`）。

## 验收

- [x] 账本按适配器给出的分类退避；TuShare 限频走限频退避。
- [x] 核心／日历与资讯路径的 TuShare 业务码与上下文路径同样保留。
- [x] 按 TDD：补缺路径遇 40203 → 账本分类为限频、退避按限频规则；其他业务码不误判为限频。
- [x] 受影响测试经 `check.py quick` 通过。
- [x] 代码审查无阻断。

## Comments

- **实现**：
  - `SourceFailed` 增加 `classification`，由适配器给出：`rate_limited` 或 `forbidden`。
  - `source_adapters.tushare_refusal(code, message)` 是三条路径共用的判断：40203 默认为限频；消息提到"权限"而没提"频率"或"最多访问"时，判为无权限；其他业务码不分类。
  - 核心／日历的 `TushareRefused`、上下文的 `TushareSourceError`、Worker 广度日历的翻译、资讯拉取（改抛 `TushareRefused`，不再按 `msg` 子串抛 ValueError）都带上业务码与分类。
  - 资讯拒绝因此记为源失败，回执不再落成结构拒收；拉取结果仍为 `tushare_rate_limited`／`tushare_source_failed`。
  - `capture_failure` 把分类写进获取尝试。
- **检索账本**：
  - `SourceFailed` 优先按适配器分类：`rate_limited` 无 Retry-After 时退避 60 分钟；`forbidden` 记为 `forbidden_unknown`，等到上海时间次日 00:05，与 HTTP 401/403 同规则。
  - 没有分类时，带 HTTP 码的按状态码，其余维持 `semantic_validation_failed`。
  - 原来 TuShare 40203 被归为语义失败，要退避 6 或 24 小时。
- **票面没写的差异（用户在 2026-10-01 访谈中确认处理方式）**：40203 在记录中同时被用于限频与无权限（测试夹具与审查记录有，真实原始响应只核实到限频那一种），所以按消息区分；这是关键词启发式，消息若写"限流""访问次数"之类其他措辞可能误判。
- **留给票 31**：
  - 拒绝消息原文的长期留存：资讯原件 3 天后清理，异常不保存原文。
  - 缺口原因显示"无权限"。
  - 每日额度被拒后本轮停用该接口。
- **测试**（先红后绿）：
  - `test_warrant_symbol_isolation.py::test_a_gap_day_refetch_backs_off_as_tushare_s_code_says` 走缺口日补取的真实路径，覆盖三种答复：40203 频率 → 限频、退避 1 小时；40203 权限 → 无权限、次日 00:05；2002 → 语义失败、P2 退避 24 小时。改动前，40203 频率那一例失败。
  - `test_tushare_context.py::test_a_refused_call_says_which_code_refused_it` 参数化业务码、消息与分类。
- **验证**（`PYTHONPATH=src`）：引用 TuShare 适配器、定向补取、检索账本、资讯或完整运行的测试文件，共 727 例全过（42.6 分钟），其中包括两例冒烟。审查后的补强（分类写入尝试、精确退避断言）单独重跑相关 4 个文件，68 例全过。ruff、mypy 通过。
- **审查**（Codex 只读）：无阻断。按意见把退避断言改成精确期限，把分类写进获取尝试，并改正注释。
