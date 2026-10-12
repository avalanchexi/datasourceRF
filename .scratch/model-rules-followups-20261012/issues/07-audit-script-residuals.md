Status: done
Category: task
Type: task

# 07：体检脚本的零散残余（时间比较、原话复核、空串网址）

## 现象

(a) 残余 03：`core_recompute._raw_rows` 与 `common.Run.reached_source`／`validated_by_cutoff` 仍按文本比较时间（当前库都存 `+00:00`，不影响结果）；整批声明全被清理的旧投影无法恢复编号（`run-dc0bb2d9…` 56 个）。(b) 体检 17：未独立实现“原话按现行规则是否仍给出该值”一类排除（本样本漏判 2 条工业增加值）；空串网址体检按正文哈希区分页面、生产视为同一页面。

## 来源

[残余 03](../residual-triage-20261011/issues/03-core-pre-window-inputs-untraceable.md)、[体检 17](../data-quality-audit-20261010/issues/17-audit-multi-source-note-lists-excluded-claims.md) 遗留（模型规则补全批次，2026-10-12 收尾汇总）。

## 做法（分流决定）

- **(a) 做**：体检公共读取链改为解析时刻后再比较和排序。位置是 `tools/quality/common.py:306`（`Run.receipts` 的发起时间过滤与排序）、`:313`、`:317`（应答与校验截止判断）、`:342`（日历回执排序），复用 `common.py:33` 的解析函数；缺时区或解析失败记为不可用，不猜时区。`core_recompute._raw_rows`（`:134` 比的是 ISO 业务日期）不用改。
- **(a) 旧运行 56 个编号无法恢复**：已写在文档已知局限（`data-quality-audit.md:372`、`:388`），不另作处理。
- **(b) wontfix**：“原话按现行规则是否仍给出该值”的排除，需要各族抽取契约（族规则、期次定位、正负号与单位、地方主语、同成员多值冲突），这些没有书面规则，只能复制生产解析器，违反独立性约束。在体检文档“已知局限”写明，并列出本样本漏判的 2 条工业增加值。空串网址：体检按 `NULLIF(url,'')` 处理，与文档 `:295` 一致；生产 `news_rules.py:1262`、`:1374` 用 `COALESCE(url, body_hash)`，与书面规则不一致（本样本 0 条）。体检不迁就生产，差异记入已知局限，生产侧偏差转入下一批积压。

## 主要模块

`tools/quality/common.py`、`docs/development/data-quality-audit.md`（已知局限）。

## 验收

- [x] (a) 时间过滤、排序、截止判断都按解析后的时刻进行；混合时区写法有最小自测（标准库，脚本内或一次性片段，记入票面）
- [x] `run-b7d59b63…` 上报告数字不变（本样本时间格式统一）
- [x] (b) 已知局限写明“原话复核未独立实现”与 2 条漏判，以及空串网址的体检与生产差异
- [x] 对 `run-b7d59b63bedca39d9d2e` 改动前后各实跑一次体检：除改动节与耗时外逐字相同，差异逐项解释，记入票面
- [x] 改动文件通过 `ruff check`、`ruff format --check`；只用标准库、不导入生产代码；Codex 两轴审查无阻断

## Comments

### 2026-10-12 分流

Codex 只读取证全文：[triage-codex-03-04-05-07.md](../triage-codex-03-04-05-07.md) 第 07.1–07.8 条。

- (a) 订正：文本比较的位置在公共读取链 `common.py:306-342`，不在 `_raw_rows` 本身。快照中 9476／9219／8165 个时间戳都是统一 UTC 格式，文本与时刻比较差异为 0；混用时区或写法时会误判。
- 旧运行 `run-dc0bb2d9…` 断链 191 条，恢复 135 条，剩 56 条，已写在文档局限。
- (b) 体检文档 `:267`、`:297` 明确不做原话重抽取；漏判的 2 条是 `CN_INDUSTRIAL_VA` 的 `ytd_real_yoy`：2026-07 的 −1.0%（“全市…”）和 2026-08 的 6.1%（“全省…”）。空串网址本样本 0 条。
- 决定：(a) `ready-for-agent`；(b) wontfix，写进已知局限（标准库能实现，但缺书面规则，不能独立实现）。体检线 C 第四票。

### 2026-10-12 进展

- 领取（fub-07，worktree 分支 `worktree-agent-a42a448a95ce0c6ae`，基于 8f993b6）。基线已跑：`/home/tywin/.claude/jobs/cd7879cd/tmp/fub/07/before.md`，与票 05 的 `05/after.md` 相比只差耗时一行（17.7 → 41.6 秒）。
- 文档已改（先文档后脚本）：`docs/development/data-quality-audit.md` 的“用法”加时刻比较规则与 SQL 文本比较的范围说明；多源备注一节改为“已知局限”（原话复核未独立实现、2 条漏判、空串网址差异）；三核心编号恢复的局限补 `run-dc0bb2d9…` 56 个的实测（该旧运行缺 `confirmation_rules`，`audit.py` 不能直接体检，数字沿用分流取证）。
- 脚本已改：`tools/quality/common.py` 新增 `moment`（复用 `parse_time`，缺时区或解析失败返回 None）、`Run.cutoff_moment`、`Run.by_cutoff`；`receipts` 去掉 SQL 文本过滤，改为按时刻过滤并稳定排序（新者在前）；`reached_source`、`validated_by_cutoff` 与日历合并排序按时刻；`core_trace.py` 只改一处过时的 docstring。ruff check / format --check 通过。对账：`07/after.md` 与 `07/before.md` 只差耗时一行。自测片段 `07/selftest.py` 18/18 通过（输出 `07/selftest.txt`）。下一步 Codex 两轴审查。
- Codex 两轴审查第 1 轮：标准轴、规格轴均“阻断：无”（`07/review-standards-1.txt`、`07/review-spec-1.txt`）。采纳两条建议：文档写明解析范围以本机 Python `fromisoformat` 为准（3.10 只认 3／6 位小数秒），并补列 `acquisition.py` `_load_announced` 中 Python 层的一处文本比较；自测补小数秒两项，20/20 通过。代码未再改动，不做复审。

### 2026-10-12 实施

- **改了什么**
  - (a) `tools/quality/common.py`：新增 `moment(value)`，复用 `parse_time`，空值、缺时区、解析失败一律返回 `None`（不可用），不猜时区；`Run.cutoff_moment`（截止本身不可用时报错退出）、`Run.by_cutoff`。`Run.receipts` 去掉 SQL 中 `a.started_at <= ?` 的文本过滤，改为按时刻过滤，并按时刻做新者在前的稳定排序（SQL 仍 `ORDER BY a.started_at DESC`，只用来决定同一时刻的先后）；截止后的回执在解析请求参数前就被排除。`reached_source`、`validated_by_cutoff` 改为时刻比较；日历合并的回执排序键改为应答时刻。`core_recompute._raw_rows` 按票面未改；`core_trace.py` 只改一处过时的 docstring。
  - (b) `docs/development/data-quality-audit.md`：“用法”新增时刻比较规则（含解析范围、不可用的含义），并写明各层 SQL 中的截止比较与 `acquisition.py` `_load_announced` 的一处 Python 比较仍按文本、不在本票范围；多源备注一节的“不独立判定的一类”改写为“已知局限”：原话复核未独立实现及原因、本样本漏判的 2 条 `CN_INDUSTRIAL_VA` `ytd_real_yoy`（声明编号、期次、值、原话关键内容；只读查库核对过两条的 `subject` 都为 `NULL`）、空串网址上体检（`NULLIF`，按文档）与生产（`news_rules.py` 的 `COALESCE(url, body_hash)`）的差异，本样本空串网址 0 条（只读查库核对）。
  - 旧运行 56 个编号：文档原已在三核心编号恢复的局限中写明“整批声明全被清理时只能记未命中”，本次在该条补上 `run-dc0bb2d9…` 的实测数字（536／191／135／56，取自分流取证 07.4）。该旧运行的冻结清单没有 `confirmation_rules`，`audit.py` 直接对它体检会在 `Run.model_used` 报 `KeyError`，因此只对 `run-b7d59b63…` 对账。
- **对账**：`run-b7d59b63bedca39d9d2e` 改动前后各实跑一次（`/home/tywin/.claude/jobs/cd7879cd/tmp/fub/07/before.md`、`after.md`），`diff` 只差末行耗时（41.6 → 18.6 秒），其余逐字相同，报告数字不变，符合“本样本时间格式统一”的预期。基线与票 05 的 `05/after.md` 也只差耗时一行。
- **自测**：一次性标准库片段 `/home/tywin/.claude/jobs/cd7879cd/tmp/fub/07/selftest.py`（内存 SQLite，不碰真实库；输出 `selftest.txt`），20/20 通过。覆盖：`Z` 与 `+00:00` 混用、空格与 `T` 两种分隔、`+08:00`／`-08:00`／`-06:00` 混合时区；截止前回执的过滤（东八区实际已发起而文本会排除、西八区实际未发起而文本会纳入、`Z` 恰等于截止）与新者在前的排序（`10:00Z` → `09:59:59` 空格写法 → `09:30:00.500000` → `17:00+08:00`），同一时刻两种写法都保留且相邻；缺时区、解析失败的回执不纳入，截止后的坏参数回执不解析；应答与校验的截止判断；日历合并时按应答时刻取最新的一份覆盖（`09:45Z` 覆盖 `17:30+08:00`，文本排序会反过来）；小数秒 3／6 位等价，Python 3.10 下 1 位小数秒记为不可用。另有对照项：旧的文本比较对同一批样例会纳入缺时区和截止后的回执、漏掉截止前的两份。
- **审查**：Codex 两轴各一轮（`07/review-standards-1.txt`、`07/review-spec-1.txt`），均“阻断：无”。采纳的两条建议（写明解析范围、补列 Python 层的文本比较）只改文档与自测，代码未再改动。规格轴在只读沙箱中无法建临时目录，日历一项为静态核验；本地完整运行 20/20。
- **遗留**
  - 各层 SQL 中的截止比较（`available_at`、`started_at`、`received_at`、`validated_at`、`computed_at`、`attempted_at`、`occurred_at`）与 `_load_announced` 的 `validated_at` 比较仍按文本，已写入文档；库中时间格式统一时无影响，混用时区写法时才需另开票。
  - 生产侧空串网址偏差（`news_rules.py` 的 `COALESCE(url, body_hash)` 与书面规则不一致）按分流决定转入下一批积压，本票未开票。
