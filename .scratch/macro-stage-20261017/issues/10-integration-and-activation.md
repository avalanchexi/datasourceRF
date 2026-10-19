# 10: 集成验收与激活

**What to build:** 集成分支整体验证：全套测试；在正式库只读副本上用新代码跑 10-14 至 10-19 单日汇总，宏观判断、把握程度、滞回与 01 重跑回测一致或说明差异；Codex 浏览器验收 ①（标题、五维、信号清单、价格验证）、④、⑥（明暗 × 1440/908/390）；写用户验收清单。用户明确同意后激活 v0016，再并入 main。规格 [../spec.md](../spec.md)（2026-10-19 修订），决定 [../decisions.md](../decisions.md)，ADR-0043（含修订）。

**Blocked by:** 01–09

**Status:** ready-for-human

- [ ] 全套测试通过（或失败逐条说明并处理）
- [ ] 副本单日汇总与回测对照表
- [ ] 浏览器验收截图与数值经主 agent 核验
- [ ] 用户验收清单勾选；用户明确同意激活 v0016

## Comments

### 2026-10-20 自动化部分（ticket-ms10）

- **1 合并 main**：main 头 b0c3054（含 ddbba45、gl-02 3bbf8f6、fd-01..03、gl-03..05）无冲突合入，提交 f6b6b9e。宏观报告输入同走 `ReportInput.create`，gl-02 的溯源 ID 剔除对它同样生效。受影响测试（`dev-venv-ms10`，`flock`，`tools/check.py quick` 30 个文件＋两例冒烟）：454 passed，1830.7 s（期间副本备份与重放争用 IO，耗时偏高），日志 `integration/affected-merge-20261020.log`。
- **2 全套**：`clock_check` 退出 0 后，`flock /tmp/pring-heavy.lock` 下 `dev-venv-ms10`（非 editable，check.py 漂移检查通过）跑 `tools/check.py full`：**2920 passed，0 failed，8505.7 s（2:21:45，02:45–05:07）**；`disk_guard` 12G，C 盘 42G 起、最低 24G。日志与前 30 用例／前 15 文件计时摘要见 `integration/full-20261020.log`，C 盘记录 `integration/disk-guard-full-20261020.log`。期间副本重放以 `nice 19／ionice idle` 并行，耗时偏高。
- **3 副本对照**：正式库 sqlite backup（单步，Worker 写入时分步备份会反复重来）到 `/tmp/pring-ms10-replay`，artifacts `cp -al`；新代码 `init`、登记并激活 v0016（仅副本）。直接重算单日汇总不可行（副本留存已在 10-19 窗口，核心预热收盘被清理 → `insufficient_history`），改为原件应答的离线完整重放（同 wg07 做法，脚本 `integration/replay/replay_run.py`）：依次重放 10-14、10-15、10-16、10-19 原运行，截止＝原截止＋1 ms，时钟从原受理时刻起，只用原截止前抓到的原件，无原件按离线（四日各 1–5 个），不调 AI、不起 Worker、不清留存。重放前从 10-14 23:29 备份补回 04-14～04-20 被清理的 32,702 条原件（`restore_pruned.py`）。结果（`integration/replay/replay-*.json`）：10-14 第五阶段（明确 4/5，生效首日 initial，信用打平取社融）；10-15 第五阶段（明确 4/5，agrees）；10-16 原始判断第三阶段（倾向，III/IV/V 各 3 维）→ 主结论保持第五阶段，候选第三阶段 1/10；10-19 同并列，候选 2/10；四日价格验证债牛·股熊·商牛、债券偏离；⑥ 色带 10-14 起 4 格第五阶段（明确）。与 01 回测按运行截止的预期一致；信号清单差异（R11 生效后前几日不列、M1/M2 截止口径）逐条见 `acceptance.md` 第二节。重放中排掉的三处重放假象（留存清理、取到后续运行的原件、同截止汇总按 assessment_id 随机取新）也记在那里。10-19 v0016 报告完整提示词 71,055 字节（v0015 65,430），溯源 ID 0。
- **4 浏览器验收**：副本上用新代码起 8072（PID 585906，10-19 v0016 投影），Codex（`codex exec -s workspace-write -C` scratchpad 独立目录，Playwright 无头）核对 ①、④、⑥ 与 ⑦ 文案，明暗 × 1440／908／390：主结论标题、滞回保持句与当日原始判断依据、三组五维、信号清单归组、价格验证行与抽屉、④ 五卡、⑥ 宏观行（10-14 起 4 格第五阶段明确、生效前留空）与区间切换均符合；六组视口无横向溢出，console error 0。发现缺陷 D1（⑦ 与 ⑥ 抽屉残留"正式阶段"）、D2（⑥ 宏观区间抽屉逐日行仍是价格阶段描述，且与价格区间同日重复），疑点 3 项。我亲自看了 7 张关键截图，与 Codex 报告一致。截图 54 张（JPG）`integration/screenshots/`，报告 `integration/browser-report-codex.txt`。之后按 PID 停站、删副本 `/tmp/pring-ms10-replay` 与全套 basetemp（26G）；正式 Worker（224854）与 8069 未动。
- **5 验收清单**：`acceptance.md`——自动化结果、重放与 01 对照（含信号逐条差异与报告体积）、页面与报告核对点、需用户裁定 12 项（含本次发现的"滞回期间不改判的分化也归支持后退"）、激活与并入 main 的步骤（注意：正式激活时生效首日直接取当日原始判断，按 10-19 读数为第三阶段（倾向），不是重放里滞回保持的第五阶段）。
- Status 保持 ready-for-human：全套、副本对照、浏览器验收三框的证据已备，待主 agent 核验后勾选；第四框待用户。

### 2026-10-20 07:19 激活（用户"全部确认"，决定 61）

激活前小修 6116f3c、6321459（D1、决定 51/59/60、三处旧文案、方向悬停提示）合入 macro-stage 后 440 过。停常驻 Worker 与 8069 → 备份 `backups/pring-cycle-before-v0016-20261020.sqlite3`（quick_check ok，0039）→ macro-stage 并入 main（426ea1d，无冲突）→ 重装正式 dev-venv（与 HEAD 0 差异，init ok，冒烟＋宏观 22 过）→ 导出 `.scratch/macro-stage-20261017/model-v0016-manifest.json` → `model-register`（hash f58cd825…）→ `model-activate --confirm`，active 为 model-v0016 → 重启常驻 Worker（PID 618991）与 8069。待办：首个成功发布宏观块的运行即生效首日，核对 ① 标题（预期第三阶段（倾向），滞回 initial）、⑥ 首格、报告新校验与提示词完整发送；之后勾验收清单、本票改 done。
