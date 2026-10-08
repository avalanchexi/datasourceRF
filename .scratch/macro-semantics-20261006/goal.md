# 目标：自动完成宏观语义票 02–11（2026-10-07 起）

**终点**：票 01–11 全部 `Status: done` 并各自提交；票 11 的全套测试与真实完整运行验收记录写入本目录。

## 用户决定（2026-10-07）

- 机制：主会话只调度与核验；每张票交给一个**全新上下文的子代理**完成（等同每票 `/clear`）。
- 顺序：严格串行 02 → 03 → 04 → 05 → 06 → 07 → 08 → 09 → 10 → 11（满足全部阻塞关系；共用 dev-venv，重型测试同时只跑一个，不并行）。
- 票 11 全自动：先按记忆规则清理 C 盘可再生成的临时/缓存，确认余量足够（全套峰值实测约 60.5 GiB，2026-10-07 C 盘余 56G，**不够，必须先清**），再跑 `check.py full` 与真实完整运行。
- 遇到规格、ADR、`key-indicators.md`、`expectation-table.md` 都没有覆盖的领域决定：**该票暂停**，不自行拍板，报主会话由用户决定。
- 进度：主会话每 15 分钟汇报当前票、后台进程进度与下一步。

## 单票执行规程（子代理照做）

1. **读**：票文件、`spec.md`、票里链接的文档、`docs/agents/testing.md`、`docs/agents/codex-delegation.md`、`CONTEXT.md` 相关术语、相关 ADR（尤其 ADR-0037、ADR-0025、ADR-0034）。只读调查量大时用 `codex exec -s read-only`（见 codex-delegation.md），不要开 Claude 子代理。
2. **领取**：票面 `Status: ready-for-agent` 改为 `Status: claimed`。
3. **TDD 实施**：先写会失败的测试，再实现，一次一个红→绿切片。代码风格贴合周边（命名、注释密度、英文注释与标识符）。
4. **环境**：改 `src/` 后先重装再测：
   `UV_PROJECT_ENVIRONMENT=$HOME/.local/share/pring-cycle/dev-venv uv sync --extra dev --no-editable --reinstall-package pring-cycle`
   测试一律用 `$HOME/.local/share/pring-cycle/dev-venv/bin/python tools/check.py quick <具体文件或 node>`；从 `src/` 直接导入调试须加 `PYTHONDONTWRITEBYTECODE=1`。
5. **验证**（按 testing.md 与票面验收）：受影响测试 → 两例冒烟 → 涉及 Worker 编排、指标目录或来源时加跑 `tests/integration/test_worker_registered_catalog.py` 与 `tests/integration/test_core_carry_forward.py`（重型，用 `python -m pytest` 显式跑）→ `ruff check`、`ruff format --check`、`mypy` 覆盖改动文件。失败如实记录；不删必要测试凑时限。
6. **Codex 两轴审查**：标准轴与规格轴各一次 `codex exec -s read-only ...`（提示词要求中文、结论先行、`file:line`、末行"阻断：有/无"）。有阻断就修，修后复审；两轮仍阻断则停下上报。非阻断意见：采纳或在票面写明不采纳理由。
7. **收尾**：勾选验收框（只勾有证据的）；在 `## Comments` 下追加"### 日期 实施"记录（改了什么、测试与耗时、审查结论）；`Status: done`；更新 `README.md` 票表状态与"下一步"。
8. **提交**：只 `git add` 本票相关文件（工作区有大量与本票无关的未跟踪文件，不要 `git add -A`）；英文提交信息沿用仓库风格（一句话标题＋简短正文），末尾附：

   ```
   Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
   Claude-Session: https://claude.ai/code/session_013FhCGqT7LMbB6gqUQutg7H
   ```

9. **回报**（中文，精炼）：完成/暂停；提交号；改动要点；测试结果与耗时；审查结论；遗留问题；若暂停，写清需要用户决定的问题与可选方案（同时写进票面 Comments，`Status: needs-info`）。

## 票 03 起沿用的审查口径（主会话决定，2026-10-07）

- 报告正文（AI 自由文本）的确认关系／计数改写校验：结构化结论严格不可改；正文只要求拦住规范写法与常见明确写法（动词式、冒号式、否定式、跨句延续、标题与正文分写），与正式阶段的 `_stated_stages`（ADR-0027）同一标准。审查新找出的自由文本绕过写法记入票面"已知残余风险"，**不算阻断**；审查提示词须写明这一口径。
- 两轮审查后剩下的阻断如果只是对上一轮修复的定向确认，做一次定向复审（只验修复本身，不再找新问题），通过即提交。

## 票 11 前置：用户手动压缩 WSL 虚拟盘（2026-10-08 用户选定）

C 盘约 51G，全套峰值约 60G；Windows 侧可清缓存不到 3G。`ext4.vhdx` 约 228G 而盘内只用约 97G，`.wslconfig` 虽有 `sparseVhd=true`，但这块旧盘未设稀疏（`fsutil sparse queryflag` 实测）。票 10 提交后、票 11 开始前，由用户执行：

1. 管理员 PowerShell：`wsl --shutdown`（会结束当前 Claude 会话与定时汇报）
2. `wsl --manage Ubuntu-22.04 --set-sparse true`
3. 重新打开 Ubuntu，执行 `sudo fstrim -av`（稀疏盘上 fstrim 会把空闲块还给 C 盘）
4. `df -h /mnt/c` 确认余量（预期回升一百多 G；至少要 ≥ 75G 才开跑全套）
5. 在仓库重新打开 Claude，说"继续自动实施宏观语义票"：新会话读本文件与 README，从票 11 继续，重设每 15 分钟进度汇报。

若第 3 步后余量未明显回升，再用 diskpart：`select vdisk file="<ext4.vhdx 路径>"` → `attach vdisk readonly` → `compact vdisk` → `detach vdisk`（需先 `wsl --shutdown`）。

**2026-10-08 用户改为"不要重启直接继续"**：不压缩虚拟盘。全套测试由 `disk_guard.sh` 每 30 秒记录 C 盘余量，低于 12G 立即终止测试进程树；虚拟盘内约 130G 已分配未使用的块可被复用，峰值未必全部落到 C 盘。若被保护终止，如实记录，改为分批跑（每批后删 basetemp）并在验收记录写明偏离 ADR-0025 的原因。

## 约束

- 外部真实调用（TuShare 等）一律串行，普通回归保持离线。
- 不 push，不改 git 配置，不做破坏性 git 操作。
- 交互与文档一律中文；代码标识符、命令、路径保持原样。

## 进度

| 票 | 状态 | 提交 |
|---|---|---|
| 01 | done | 2724046 |
| 02 | done（两项范围决定：日频长回看与仓单/降准成员均维持拒绝；日频扩展由 06/09 承接） | e512e87 |
| 03 | done（⑤ 斜率带方向：用户确认；报告正文校验口径同 `_stated_stages`，残余风险列于票面） | b99d539 |
| 04 | done（Q1 2 月取累计同比、Q2 社融 7 个非政府分项逐个列入：用户确认；F3 要求 7 分项均已知且无一回升） | 061d3f9 |
| 05 | done（月度起点：新模型取已持有最新期与按日历已到期最新期的较晚者，旧模型不变；宽限/成熟度规则入清单） | 3f8aabb |
| 06 | done（日频 5 交易日一期；已传导＝下调后 DR007 均值下降；D1 六阶段适用；OMO 按 SSE 日历：用户确认；日频长回看取数已扩展） | 8ec4f36 |
| 07 | done（季度高低位近 4 季、回看到 t−4；贷款守 13 个月；Ⅵ 信用脉冲附注；盈利 2 月比照工增：用户确认；GDP 名义累计只展示：主会话决定） | 12315b3 |
| 08 | done（数据不足的未分类记未确认、方向齐但凑不成象限记仅观察：主会话接受；仓单只作附注） | 3c1d6a0 |
| 09 | done（广度站上 90 日均线占比、篮子按同向分项个数、"明显回升"＝收益差转正：用户确认） | 039d7ce |
| 10 | done（政策轴＝动作＋DR007 四者一致；增长通胀轴＝5 项同步指标至少 3 项同向：用户确认） | 19fb530 |
| 11 | done（全套 2012 例通过 59 分 58 秒，C 盘最低 51G；真实运行 v0015 约 20.5 分钟，目标日非典型组合，17 项不适用；回看取数缺陷待另开票） | 本提交（"Activate model v0015 …"） |
