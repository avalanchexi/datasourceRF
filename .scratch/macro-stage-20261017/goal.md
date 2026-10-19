# 目标：宏观判断阶段为主结论，永不为空（2026-10-17 起，2026-10-19 修订）

**范围**：[spec.md](spec.md)（2026-10-19 修订）与 [issues/](issues/) 01–10；决定见 [decisions.md](decisions.md)（36 条）；调查见 [investigation.md](investigation.md)；ADR-0043（含修订）。初版票存档 `issues-20261017/`，初版 01 规程见下方"初版 01 规程（存档）"。
**执行方式**：`/implement-spec`（2026-10-19 用户启动）：主 agent 调度，每票一个命名子代理（`ticket-msNN`），只读调查与审查走 `codex exec`。

## 依赖图

01（回测重跑＋对照表，需用户确认）→ 02 贯通 → {03 兜底、04 信号清单、06 价格验证、07 ④} → 05 滞回（03、04）→ 08 ⑥与阶段史（03、05）；09 报告（03、04、06）→ 10 集成与激活（需用户同意）。

## 集成分支

- 01 定稿（用户已于 10-19 确认，决定 37–48）、且 golive-20261019 的全套测试通过并把修复提交到 main 后（不等你验收新前端），从 main 建 `macro-stage`（worktree `/home/tywin/worktrees/datasourceRF-ms`），并把 `prototype/macro-stage` 上的文档（`GLOSSARY.md`、`docs/adr/0043*`、`.scratch/macro-stage-20261017/`）检出进来提交一次；原型脚本不并入。
- 代码地图（Codex 只读探查）：`/home/tywin/worktrees/macro-stage-notes/code-map.md`，各实施子代理先读。

## 代码地图带来的约束（Codex 探查，2026-10-19）

- **v0016 不分次登记**：模型版本登记后内容不可变。02–05 各自在清单构建处增加特征表、兜底、信号对照表、滞回参数，测试一律在每例独立运行库里登记；任何票都不得向共享库或正式库登记 `model-v0016`，正式登记只在 10 经用户同意后做一次。
- **02 先做预备重构**：先定发布用的宏观判断结构（原始判断、主结论、五维依据、并列信息、滞回状态、信号清单、价格验证），并把目标日与补算日共用的"发布前完成宏观判断"抽成一步；① 新结论板与 ④ 新维度卡放进小型渲染模块，保留旧投影分支；不改 v0015 确认度的分化封顶、贷款计数与预期表。后续票只扩展该结构。
- **并行度**：02 合入后，03、04、06、07 可并行，但同时在跑的实施子代理不超过 2 个（`cockpit.py`、单日汇总、`wording` 共改）；合并子代理按完成顺序合入，冲突逐处按两票意图解决并复跑两票受影响测试。
- **09 报告**：现行非典型报告契约（固定章节、禁止"倾向"字样、按 `noncanonical_basis` 进入旧限制）须按"有无宏观判断块"分流，旧输入保持原行为；阶段陈述校验要区分宏观主结论、价格阶段、并列候选与信号转换。

## 票 02 留下的接口（80e8932）

- `cycle_overview.macro_judgement`：`rules_version`；`raw{stage, confidence, matched, known, basis(unique_top/tied/insufficient), tied[]}`；`conclusion{stage, confidence, matched, known, reference_stage, steps, direction(forward/back/same/None)}`；`hysteresis`（None，05 填）；`dimensions[]`；`scores{stage_i..vi}`；`signals`（[]，04 填）；`price_verification`（None，06 填）。
- `dimensions[]` 每项：`dimension`、`group`(monetary/economic/inventory)、`value`、`position`、`basis`、`matches`、`indicators[]`；投票维另有 `position_from`、`tally`、`tie_breaker`；`indicators[]` 含 `key`、`name`、`voting`、`vote`、`divergent`、`period`、`evidence_status`（贷款列出但 `voting=False`）；政策维含 `action`、`actions[]`，库存维含 `quadrant`。
- 扩展点：03 改 `macro_judgement.judge` 选取分支（上一确认阶段经 `reference` 传入）；05 在 `DaySummaries._judge_macro`（目标日与补算日共用）接前一日状态，用 `macro_judgement.conclusion(raw, reference)` 生成主结论；规则追加到 `macro_judgement.rules_v0001()`，由 `MacroJudgementRules.from_manifest` 解析，`validate` 同步放宽；页面加在 `macro_board.py`（title、dimensions、conclusion_left），词汇在 `wording.py` 的 `MACRO_*`。
- 02 的偏离（票面 Comments 有详述）：政策维成员历史不全时不计动作，三项都读不到才"不明"；指标投票只要主要成员当期方向已知（与确认度"回看缺月判未确认"口径不同，票 10 对照时留意）；并列与不足暂发布 stage=None，由 03 替换；标题含"前进 N 步"；① 五维下暂留价格阶段旧行，由 06 收进价格验证行。

## 票 04 留下的接口（3f0d1c1）

- 信号清单在 `macro_judgement.signals`，未列入的萌芽在 `macro_judgement.sprouts`；每条：`id`、`kind`（price／observation／divergence）、`source`、`same_source`、`transition{from,to}`、`group`、`steps`、`maturity`、`sessions` 或 `periods`，另带事实块 `momentum`、`breadth`、`peers`、`candidates`、`asset_turn`、`combination`、`indicator`、`minority`、`rejudged`。模块 `macro_signals.py`。
- 文案：`macro_board.describe(item)`（整句）、`macro_board.pointer(item)`（短称），不依赖 dash，报告可直接用。
- `_judge_macro` 顺序：`judge` →（05 在此换成滞回后的主结论）→ `signal_list`；信号按 `conclusion.stage` 归组，滞回必须在 `signal_list` 之前。05 的进度条目追加到 `signals`：`id:"H"`、`kind:"hysteresis"`、`transition{from,to}`、`group`、`steps`（用 `_grouped`），渲染在 `macro_board._reading` 加分支；前一交易日状态用 `ProjectionSetRepository.macro_judgement_on(day)`。
- `p0.relink` 已接 `macro_signals.regrouped`（纠正上一确认阶段后按新主结论重新归组）。
- 04 的偏离：成熟度接续前一交易日已发布块计数（v0016 生效后前 4 个交易日价格信号只在两格同指或已确认时列入）；分化信号只分萌芽／成形；政策、库存维分化归"转换未定"；新板删去"转折观察"行（已并入清单）；B、K 组与分化跨两期成形只实现未单测（测试目录缺数据）。

## 票 03 留下的接口（736169d，合并 4fb29cf）

- `judge(rules, confirmation, reference=…, cores=…)` 的原始判断永不为空（决定 49 例外：三核心不可用且无上一确认阶段 → stage/confidence 为 None，标题"无可取阶段"）；把握程度 明确／倾向／弱。
- `raw` 新增 `fallback`（来源、三核心组合、差异资产数、候选阶段）与 `threshold`；决定 44 可直接比较 `raw.confidence` 与前一日 `conclusion.confidence`。
- 校验只约束原始判断自洽；主结论只校验步数与吻合数，05 的主结论可不同于原始判断。`with_reference` 在滞回状态非空时只重述步数——05 若需滞回随更正重算，要在此分支补。
- 08：每日记 `conclusion.stage` 与 `conclusion.confidence`，两者可同为 None，色带要能显示"无可取阶段"空格；`raw.basis`、`raw.fallback.source` 可标注来源，但阶段史只记主结论。
- `_judge_macro` 新增 `readiness`、`decided` 参数；三核心组合 `combination` 同时传给主判断与 04 的分化重判。

## 票 06 留下的接口（78254fc，合并 9917b08）

- `cycle_overview.macro_judgement.price_verification`：`price_stage`、`reason`、`combination{bond,stock,commodity}`（bull／bear／None）、`expected_stage`（即主结论阶段）、`expected{...}`、`deviations[]`（债、股、商顺序）、`verdict`（consistent／deviates／unavailable）、`comparisons[]`（非典型时即 `noncanonical_basis.comparisons`）。
- 写入点 `P0ProjectionService.publish`，**排在 05 滞回与 04 信号之后**，读最终主结论；纯函数与校验在 `macro_verification.py`；整句 `macro_board.verification_line(block)`。
- 06 的偏离：抽屉另收 02 暂留的原因、上次确认、核心沿用、判法；新投影右栏去掉确认度，标题暂定"旁注"（待用户验收）；relink 用 `restated` 重算价格验证（未单测）。

## 单票规程（02–09）

1. **worktree**：从 `macro-stage` 建 `ms-NN` 分支与 worktree `/home/tywin/worktrees/datasourceRF-ms-NN`；开工前确认基于 `macro-stage` 最新头，不是就 rebase 上去。
2. **读**：本票、spec、decisions、code-map.md 对应节、GLOSSARY、ADR-0043/0034/0037/0003；`docs/agents/testing.md`。
3. **环境**：独立 venv `~/.local/share/pring-cycle/dev-venv-msNN`（`UV_PROJECT_ENVIRONMENT=... uv sync --extra dev --no-editable`，在本票 worktree 执行），`PYTEST_ADDOPTS=--basetemp=/tmp/pytest-msNN`，`PYTHONDONTWRITEBYTECODE=1`；不碰正式 `dev-venv`、正式库与调度。
4. **实施**：调用 Skill `mattpocock-skills:tdd`，按票面勾选框红绿推进；只跑受影响测试（`python tools/check.py quick <文件>`），重型文件在 `flock /tmp/pring-heavy.lock` 下；收尾跑两例冒烟。
5. **收尾**：把 `macro-stage` 最新头合并进本分支并复跑受影响测试；票面勾选、`## Comments` 记测试命令、通过数与耗时；`Status: done`；英文提交信息带署名两行。回报主 agent：分支、提交号、测试结果、偏离票面之处。
6. **合并**：主 agent 派合并子代理把 `ms-NN` 合入 `macro-stage`（能快进则快进），复跑冒烟。
7. **清理**：合并后删 worktree、`/tmp/pytest-msNN`；venv 保留到 10 完成。

## 收尾（10）

全部 02–09 合入后：Codex 两轴审查（Standards＋Spec，`codex exec -s read-only`）→ 一个子代理修复全部审查项 → 全套测试（clock_check、flock、disk_guard 12G）→ 正式库只读副本跑 10-14～10-19 单日汇总并与 01 回测对照 → Codex 浏览器验收 → 用户验收清单；v0016 激活与并入 main 须用户明确同意。

## 初版 01 规程（存档）


1. **worktree**：`git -C /home/tywin/worktrees/datasourceRF-cl worktree add -b prototype/macro-stage /home/tywin/worktrees/datasourceRF-ms-proto cockpit-layout`。脚本与输出放 `prototype/macro-stage/`（仓库根下目录），用完即弃写法，不写测试、不改 `src/`。
2. **读**：票 01、spec、decisions（重点决定 4、7、8、9、13）、investigation、ADR-0043、GLOSSARY（宏观判断阶段、宏观周期特征表、维度方向、价格验证、价格阶段）。只读调查用 `codex exec -s read-only`。
3. **数据**：只读隔离副本。先把 `/tmp/pring-cb-real-20261016` 复制为 `/tmp/pring-ms-proto`（不在原副本上做任何写操作），脚本只读这份拷贝；不访问外网、不调 TuShare、不启动 Worker。
4. **运行**：用 `~/.local/share/pring-cycle/dev-venv-cl10` 的解释器加 `PYTHONPATH=src` 与 `PYTHONDONTWRITEBYTECODE=1` 导入当前代码（不重装、不改该 venv）；重计算放 `flock /tmp/pring-heavy.lock` 下。
5. **时点纪律**：逐月取时点，每个时点只用 `available_at` 不晚于该时点的观测；关键指标读法复用现有代码，不重写；五维方向按决定 7、特征表按决定 8、选取按决定 9。
6. **产出**：每月表格（五维方向与主要指标、六阶段得分、宏观判断/介于/证据不足、当时价格阶段或非典型）＋小结（覆盖月数与数据缺口、判断跳变次数、并列与证据不足月数、与价格阶段一致/偏离分布、I 与 VI 混淆、3 分门槛是否合适、是否需要滞回）；10-15 时点与手算（第五阶段 4/5）对照。小结写进 `prototype/macro-stage/README.md`，并摘要写回 spec "Further Notes"（只在本分支）。
7. **提交**：在 `prototype/macro-stage` 分支提交，英文提交信息带两行署名（同 A、B 批次）。票面 Comments 记"### 2026-10-17 回测"，`Status: needs-info`（等用户定稿），不勾"用户已看过"一框。
8. **回报**（中文）：分支与提交号、小结要点、建议的特征表或门槛调整（如有）。

## 进度

| 票 | 状态 | 执行者／分支 |
|---|---|---|
| 01 回测重跑＋对照表 | done（对照表定稿 24 格，da9ba92） | ticket-ms01／prototype/macro-stage |
| 02 宏观判断贯通 | done（80e8932，快进合入；冒烟＋新测 17 过） | ticket-ms02／ms-02 |
| 03 兜底 | done（736169d，合并 4fb29cf；55 过） | ticket-ms03／ms-03 |
| 04 信号清单 | done（3f0d1c1，快进合入；36 过） | ticket-ms04／ms-04 |
| 06 价格验证 | done（78254fc，合并 9917b08） | ticket-ms06／ms-06 |
| 07 ④ | done（cf8f46c，快进合入） | ticket-ms07／ms-07 |
| 05 滞回 | 进行中（21:0x 派出） | ticket-ms05／ms-05 |
| 09 报告 | 进行中（21:2x 派出） | ticket-ms09／ms-09 |
| 08 | 等 05 | — |
| 10 | ready-for-human | — |
