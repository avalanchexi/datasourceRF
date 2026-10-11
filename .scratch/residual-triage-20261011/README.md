# 残余问题分流（2026-10-11）

| 票 | 内容 | 状态 |
|---|---|---|
| [01](issues/01-recurring-context-observation-failures.md) | 每次运行固定 12 条失败回执（订正：篮子“无需新增”时把 12 张输入回执误标为 failed） | ready-for-agent（线 E） |
| [02](issues/02-calendar-parser-missing-day-read-as-closed.md) | 日历解析器把漏列的日子当作休市 | ready-for-agent（线 B，排在票 03 之后） |
| [03](issues/03-core-pre-window-inputs-untraceable.md) | 核心窗口前输入追溯断链 | ready-for-agent（用户选 B：体检精确恢复；线 F） |
| [体检 17](../data-quality-audit-20261010/issues/17-audit-multi-source-note-lists-excluded-claims.md) | 体检备注误列已排除的错期值 | ready-for-agent（线 C，排在 05 之后） |
| [04](issues/04-audit-p2-quotes-latest-plus-comparison.md) | 体检对 USDCNY 16:30、SOX 改为“最新值＋比较上下文”口径（用户决定项） | ready-for-agent（用户选同中间价；线 C，排在体检 17 之后） |

## P2 口径取证（2026-10-11 分流，codex g4 第 B 部分）

- 现行：`tools/quality/acquisition.py:55` 的 `LATEST_ONLY` 只含人民币中间价，规则为“窗口内最后一个不确知休市日＋此前最近已持有日”（`:691`、`:728`）；USDCNY 16:30（120 格，持有 4、缺 116）与 SOX（126 格，持有 0、缺 126）仍按整窗核对，文档 `docs/development/data-quality-audit.md:120` 明文保留这一差别。
- 生产需求：两项不参与正式阶段与确认度，但国际背景取每个成员最新值和前一个值算方向（`context_projection.py:2759`、`:3168`）；`run-8186b774…` 的宏观冻结输入里 USDCNY 实有 2 条（09-28、09-30），SOX 0 条。最终计划各要求 10-08 一期。ADR-0029：USDCNY 按公开 P2 获取、接受滞后一个交易日；SOX 保持授权缺口、不检索。
- 改为“同中间价：最新＋比较”后，第一层目录日频计数 7589／7331／250 → 7347／7329／10（减少的 242 格中 240 个是缺格，不是补回了数据）；第二层仍核最终计划期次，“仅模型用到”的计数不变。只改 `tools/quality/acquisition.py` 与体检口径文档，外部调用 0，生产不变。

