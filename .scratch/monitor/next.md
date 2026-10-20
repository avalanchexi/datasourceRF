## 下一步任务（手工维护，按优先级）

0. **10-16 已补跑**（run-151cdf85，10-19 16:29 完成，Worker 已停）；体检 `.scratch/makeup-run-20261019/audit-run-151cdf85.md` 真正缺失 0、输出 60/60 一致。新发现：信用脉冲 CN_CREDIT_IMPULSE 目标日 10-16 派生缺失（10-15 有值 22.94），疑与当天 Q3 GDP 部分入库有关，待用户决定是否调查／开票。
0a. **上线完成**（10-19）：正式环境新代码、10-19 投影；常驻 Worker 已起（不包重型锁）；8069 正式驾驶舱。待办：Codex 调查前端两疑点与上线遗留 → 开"前端缺陷 20261019"（含 Q6 加高 240px）与"上线遗留 20261019"两小批次；补生成 10-19 AI 报告。
0b. **C 批次**：规格已修订、重拆 10 票（ms-proto `.scratch/macro-stage-20261017/issues/`）；票 01 回测重跑由子代理 ticket-ms01 进行，完成后请用户看回测并逐格确认价格信号对照表；02 起等 golive 验收后从 main 建 macro-stage。
1. ~~常驻 Worker~~ 已于 10-19 起常驻。
2. **布局精简批次验收**：实施完（cockpit-layout），8067（10-14）/8068（10-15）已换新代码；按 `/home/tywin/worktrees/datasourceRF-cl/.scratch/cockpit-layout-20261016/acceptance.md` 清单逐段确认；通过后与 conclusion-board 一起并入 main。
2a. **结论板验收**：用 8068（10-15 AI 报告）与 Claude 方案 ① 逐项核对；决定四处视觉差异与"30 日候选方向无"是否列入转折观察；确认度标题与五小格不一致待定。
3. **关口 C**：前端重建 13 票 ready-for-human，等逐段验收。
4. **并入 main 与切换**：conclusion-board 验收后并入 → 跑一次全套（上次 2552 过 / 7 败，修复后只跑切片）→ 经你同意重装正式 dev-venv（现为 10-14 旧代码、旧 8 页站）→ 新代码跑一次真实运行，投影才有走势、确认汇总、运行摘要；之后可删 dev-venv-cb07 与 8067/8068 预览。
4a. **②～⑦ 段对齐 Claude 方案**：结论板规格明确另开批次，尚未开票；先看你逐段验收时哪些段不满意再定。
5. **dot 托管**：票 02 已领取，等你贴回 dot 报告；票 03（谁触发每日运行）未定。
6. **积压**：model-rules-residuals-20261013 的 8 张 needs-triage；recurring-input-gaps-residuals 01–07 已由 08–13 取代、待标记。
