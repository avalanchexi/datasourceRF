Status: needs-triage
Category: bug
Type: task

# 04 — VIX 检索范围用例只在全套里失败

## 原始发现

- 全套（`18899cf`）中，`tests/integration/test_full_run_retrieval.py::test_full_run_plans_the_latest_released_period_of_a_metric_not_held` 在最后一条断言失败：检索范围里出现了 `full:cboe_vix_index:2026-09-22`（ADR-0029 规定 VIX 从 Cboe 文件读取，不检索）。
- 单独运行这个用例能通过。9/26 的全套（`9d230f9`）里它也是通过的。
- 真实运行 `run-dc0bb2d9db7068bf552d` 的检索计划里没有 VIX 范围，所以生产行为正常。

## 待决定

- 找出全套中是哪个先跑的用例留下了状态（模块级缓存、没有还原的补丁、共用的运行库等）。可能与今天新增的 `czce_warrants` 补丁或按品种取数的改动有关。
