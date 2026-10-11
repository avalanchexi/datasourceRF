Status: ready-for-agent
Category: enhancement
Type: task

# 04：体检对 USDCNY 16:30 收盘价、SOX 改为“最新值＋比较上下文”口径（同人民币中间价）

## 来源

2026-10-11 残余分流的用户决定项（取证见 [README](../README.md)“P2 口径取证”）。用户选择：两项 P2 的第一层改为与人民币中间价相同的“最新值＋比较上下文”口径，历史缺口另列为信息；第二层仍核最终计划期次；SOX 的授权缺口照旧明示。

## 现状

- `tools/quality/acquisition.py:55` 的 `LATEST_ONLY` 只含人民币中间价，规则见 `:691`、`:728`；USDCNY 16:30（120 格，持有 4、缺 116）与 SOX（126 格，持有 0、缺 126）仍按整窗核对；`docs/development/data-quality-audit.md:120` 明文保留这一差别。
- 生产：两项不参与正式阶段与确认度；国际背景取每个成员最新值与前一个值（`src/pring_cycle/context_projection.py:2759`、`:3168`）。ADR-0029：USDCNY 按公开 P2 获取、接受滞后一个交易日；SOX 保持授权缺口、不检索。

## 验收

- [ ] 体检口径文档改写：USDCNY 16:30、SOX 第一层按“最新值＋比较上下文”核对，历史缺格另列为信息（不计入“未取到”），第二层仍核最终计划期次；注明出处为 2026-10-11 用户决定
- [ ] SOX 的授权缺口（ADR-0029，无取数路径）在报告中照旧明示，不因缩窗而消失
- [ ] 对 `run-8186b774087648d921e3` 实跑对账：目录日频计数约 7589／7331／250 → 7347／7329／10（以实跑为准，差异解释）；“仅模型用到”的计数与低频统计不变；其余各节逐字相同（耗时除外）
- [ ] 只用标准库，不导入生产代码，运行库只读；ruff 通过；Codex 两轴审查无阻断

## 主要模块

`tools/quality/acquisition.py`、`docs/development/data-quality-audit.md`。

## Comments
