Status: done
Type: task
Blocked by: 01, 02, 03, 04, 05, 06, 07, 10, 11, 12, 13, 14

# 09 — 终点：全套一次与真实完整运行

规格“验收”一节（用户故事 26）。跑一次 `python tools/check.py full`，登记并切换到 `model-v0013`，再做一次真实完整运行，缺口清单与规格预期逐项对照。预期：美债 3 项、仓单、VIX、USDCNY 16:30、广度 7 项、篮子 2 项都不在缺口清单；SOX 列为授权缺失。

## Comments

- 2026-09-26 全套（`check.py full`，代码至 9d230f9）：1191 例，1190 过、1 败，用时 74 分 18 秒，C 盘始终 67G（开跑前清掉 4.4G 旧 pytest 临时目录）。失败例 `test_worker_fails_closed_and_classifies_context_validation_failures` 是假设过时：它以 TuShare 返回码 −1 模拟校验失败，而审查修复把非零返回码改记为取数失败；夹具改为返回码 0、缺字段的应答（3f43593），该例单独重跑通过。
- 2026-09-26 登记并切换 `model-v0013`（`model-register`/`model-activate --confirm`，之前迁移到 0031，运行库备份在 `~/.cache/pring-cycle/backups/pring-cycle-20260926-before-v0013.sqlite3`）。
- 第一次真实完整运行（run-15542949d737d6b62707，目标 2026-09-24，16 分钟，completed）：缺口 18 → 15。暴露两处实现缺陷：① Cboe 把 `cdn.cboe.com` 307 跳到 `cdn-api.cboe.com`（不跟随重定向，VIX 取数失败）；② 名册退市状态有历史代码 `T600018.SH`，整批广度被 `tushare_breadth_security_scope_unknown` 拒收。已修（825bb05）。
- 第二次真实完整运行（run-64209ab01ac75439cc8c，目标 2026-09-24，28 分钟，completed，614 条回执）：缺口 18 → **4**。
  - 已消除（与规格预期对照）：美债 2Y/10Y 与 2s10s（current）；USDCNY 16:30（9/24，current）；VIX（9/24 = 15.67，与 Cboe 文件一致）；广度 7 项（各 120 天 4/3–9/24，9/24 参与 5556、上涨 1120、站上 MA250 26.4%、90 日新高 51）；篮子与袖套（120 天，9/24 = 1108.80）；仓单（目标日 9/24 持有）；社融分项。
  - 余下：SOX `license_missing`（预期）；工具流动性 `retrieval_failed`（本规格外，已有遗留）；仓单 `rejected` 提示与 OMO 操作量 `rejected` 提示（两者均已持有，只是某次原件被结构校验拒收）。
- 遗留（待分流）：
  1. **PTA 仓单历史**：TuShare 在 2026-03 至 2026-09 若干时段的 PTA 应答里，同一仓库一天有重复的整行（如长江国际 5/19 两行 1176/−144）外加一行把变动放进数量栏的负数行（−144/空）。按现规则负数即拒收，而仓单家族是一次取八个品种，一条 PTA 负数行会让整个 220 天历史都被拒；目标日靠补缺时的单日重取持有。可选：按品种各自取数隔离，或 CZCE 品种改用郑商所官网日报（ADR-0029 修订段已记为更权威口径）。
  2. OMO 操作量官网页 `official_context_table_schema_mismatch`、工具流动性检索未通过，均为本规格前已有问题。
