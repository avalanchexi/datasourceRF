Status: ready-for-agent
Type: read-only-audit + header-field-correction
Date: 2026-09-21

# 票面 `Execution:` 与实况的逐票核对（28 张）

只读核对 `issues/` 下 28 张票的 `Status:` / `Execution:` / `**Blocked by:**` / 验收勾选数，
并与 git 历史交叉验证。**只改 `Execution:` 一个字段，共改 5 张票**；未改任何 `Status:`，
未勾选或取消勾选任何验收条件，未触碰 `src/`、`tests/`、`tools/`。#28 由 B1 独占，本次未碰。

## 一条必须先说的更正：#04–#08、#11 的 `blocked` 不是陈旧标签

任务书的前提是「它们的 `Blocked by:` 指向 02/03，两张都已 `completed`，所以依赖早已满足、
标签陈旧」。**这条前提与提交记录不符，因此这六张票一张都没改。** 证据：

| 事实 | 出处 |
|---|---|
| `3231539`（#03 → `completed`）时间戳 2026-09-06 22:19:13 | `git log --date=iso` |
| `aac107f`（给 #04、#05 写入 `Execution: blocked`）时间戳 2026-09-06 **22:21:10** | 同上 |

`blocked` 是在 #03 完成**两分钟后**写上去的，写它的人当时清楚依赖已满足。同一提交在票尾
写下了真正的阻塞原因，与 `**Blocked by:**` 那一行无关：

- **#04**（`aac107f`）：「全部日线仍缺绑定数值版本的实际公开时间；NHII 仅 15 个正确日报，
  6 日缺目录、08-17 错链、98 个原件传输失败……保持认证未完成」。
- **#05**（`aac107f`）：「北交所 4 次公开请求均 403，缺可对账官方数值原件，三所历史实际
  公开时间未建立。保持本票受阻」。
- **#06**（`e0d06cc`）：「历史首次公开与修订证据不足，六系列 TuShare 原响应未找到……未完成
  候选认证，继续阻塞 19」。
- **#07**（`e0d06cc`，后续 `02a5cce`）：确定性缺陷已修，但「来源、定义及历史发布时间认证仍
  blocked」。
- **#08**（`e0d06cc`）：「BSE 实际换码通知/全映射正文未取得，历史起始池及 PUBLIC 可得性仍缺
  ……不解锁 09/10/19」。
- **#11**（`e0d06cc`，后续 `9a36df5`）：「PP 真实数值与规则原件、CF/TA 完整年月……仍缺」；
  2026-09-13 批 611/612 的票尾明写「真实来源认证仍 blocked」。

**结论**：这六张票的 `Execution: blocked` 指的是「外部来源认证受阻」，不是「上游票未完成」。
`2026-09-14` 之后再无提交提及这六张票，也就没有任何证据表明那些外部缺件已解除。
把它们改成 `in-progress` 会把「别去碰、缺的是外部原件」误传成「可以接着做」——正是任务书
要防止的取错票。**真正不自洽的是 `**Blocked by:**` 那一行本身**（它记的依赖确实已满足，
却被当成阻塞理由留着），但改那一行不在本次授权范围内，见「未修正」一节。

## 逐票核对表（28 张）

「Blocked by 是否满足」按 `docs/agents/issue-tracker.md` 的规则判定：所有依赖均已完成才算满足。

| 票 | Status | Execution（改前） | Execution（改后） | 勾选/总数 | Blocked by 是否满足 |
|---|---|---|---|---|---|
| 01 | ready-for-agent | completed | 不变 | 5/5 | 无依赖 |
| 02 | ready-for-agent | completed | 不变 | 6/6 | 无依赖 |
| 03 | ready-for-agent | completed | 不变 | 6/6 | 满足（02 completed） |
| 04 | ready-for-agent | blocked | 不变 | 0/5 | **满足**（02 completed），但真实阻塞在外部来源 |
| 05 | ready-for-agent | blocked | 不变 | 0/5 | **满足**（03 completed），真实阻塞：北交所 403 |
| 06 | ready-for-agent | blocked | 不变 | 0/5 | **满足**（03 completed），真实阻塞：历史公开时间缺证 |
| 07 | ready-for-agent | blocked | 不变 | 0/5 | **满足**（03 completed），真实阻塞：口径/发布时间认证 |
| 08 | ready-for-agent | blocked | 不变 | 0/5 | **满足**（03 completed），真实阻塞：BSE 换码正文缺失 |
| 09 | ready-for-agent | blocked | 不变 | 3/7 | 不满足（08 仍 blocked，0/5） |
| 10 | ready-for-agent | blocked | 不变 | 2/7 | 不满足（08 仍 blocked，0/5） |
| 11 | ready-for-agent | blocked | 不变 | 2/7 | **满足**（03 completed），真实阻塞：PP/CF/TA 原件缺失 |
| 12 | ready-for-agent | in-progress | 不变 | 8/13 | 不满足（11 仍 blocked） |
| 13 | ready-for-agent | in-progress | 不变 | 0/5 | 满足（03 completed） |
| 14 | ready-for-agent | in-progress | 不变 | 4/9 | 满足（03 completed） |
| 15 | ready-for-agent | completed | 不变 | 6/6 | 满足（02 completed） |
| 16 | ready-for-agent | completed | 不变 | 6/6 | 满足（03、15 均 completed） |
| 17 | done | **complete** | **completed** | 18/18 | 满足（16 completed） |
| 18 | ready-for-agent | in-progress | 不变 | 6/6 | 无依赖 |
| 19 | ready-for-agent | in-progress | 不变 | 9/19 | 不满足（04–07、09、10、12–14 均未完成） |
| 20 | ready-for-agent | **（无此字段）** | **blocked** | 0/6 | 不满足（17 completed，但 19 仍 in-progress） |
| 21 | ready-for-agent | **（无此字段）** | **blocked** | 0/11 | 不满足（19 仍 in-progress） |
| 22 | ready-for-agent | **（无此字段）** | **in-progress** | 9/21 | 不满足（18、20、21 均未完成） |
| 23 | needs-triage | deferred | 不变 | 0/0（无验收节） | 无依赖 |
| 24 | superseded | not-started | 不变 | 0/5 | 无依赖（票已被规格 24 取代） |
| 25 | ready-for-agent | **not-started** | **blocked** | 0/4 | 不满足（19 仍 in-progress） |
| 26 | needs-domain-decision | reverted | 不变 | 0/4 | 无依赖 |
| 27 | ready-for-agent | not-started | 不变 | 0/4 | 无依赖 |
| 28 | ready-for-agent | not-started → in-progress（**B1 所改，非本任务**） | 同左 | 0/4 | 无依赖 |

## 五处修正与各自的依据

### 1. #17 `complete` → `completed`（写法归一，语义不变）

全仓 `Execution:` 取值统计里 `completed` 出现 23 次，`complete` 只在 #17 出现 1 次，由
`4c79cac`「Close ticket 17 within its own scope」写入（该提交同时把 `Status:` 改为 `done`、
把 `Execution:` 从 `in-progress` 改过来）。`docs/diagrams/pring-execution-gantt/support/build_data.py:385`
的核验语句写的是「票 17 Execution: completed。」——改后这句话才成立。
**这不是状态变更**：票仍是 18/18 全勾、`Status: done`、按本票范围关闭。

### 2. #20 补 `Execution: blocked`（原本缺字段）

#20、#21、#22 三张票**根本没有 `Execution:` 行**，其余 25 张都有。缺字段比陈旧更糟：按字段
筛票时它们既不出现在「可做」里，也不出现在「受阻」里。
#20 依据：0/6 勾选；除 `aeb6b41`（建票）、`c062d76`、`d2545c3`（均为记录笔记，未动验收）外
无实施提交；`**Blocked by:** 17；19`，其中 19 仍 `in-progress`（9/19）。按 issue-tracker
「所有依赖均为 resolved 后任务才解除阻塞」判为 `blocked`。

### 3. #21 补 `Execution: blocked`（原本缺字段）

依据：0/11 勾选；无实施提交（`3e1b7d3`、`6662bc2` 等均是 19 的实施顺带引用本票）；
`**Blocked by:** 19`，19 未完成。
**须同时看票内那一行**：#21 自己写了「**Preparation blocked by:** None —— 现有原件、日历和
缺件的只读核查可先行」。所以 `blocked` 指的是**正式真实回放**，只读准备现在就能做。

### 4. #22 补 `Execution: in-progress`（原本缺字段）

依据最硬：9/21 已勾选，且有落地源码的提交明确挂本票号——
`b6caf3a`「Skip unrelated source-family checks during input selection (#22)」改 `src/pring_cycle/search_evidence.py`；
`dc65c98`「Stop rechecking claims a period can never adopt (#19, #22)」改 8 个 `src/` 文件、新增
`material_preflight.py`；`f80b8e5`（测试）；最近的 `fb8937b`、`5e79293`（2026-09-21）也仍在改本票。

### 5. #25 `not-started` → `blocked`

`not-started` + `Status: ready-for-agent` 会让人当成「现在就能开工」，而票内自己写明做不了：
「补候选 URL 不是改一行常量，而是新开目录版本 → 候选准入 → 120 交易日重放 → 显式激活，
即票 19 的机制」，并列有 `**Blocked by:** 票19`。19 现为 `in-progress`（9/19）。
另外本票的探测与用例其实**已经做完**（票内「已完成」表；`tests/catalog/test_official_fallback_candidates.py`
已在仓库中），所以 `not-started` 两头都不准；在既有取值里 `blocked` 是唯一同时正确的。

## 发现了但**没有**修正的不自洽

1. **#04–#08、#11 的 `**Blocked by:**` 行名不副实。** 它指的 02/03 确已 `completed`，真实阻塞
   写在票尾评论里。要修的是那一行（或补一行 `Certification blocked by:`），不是 `Execution:`；
   改依赖声明超出「只改 `Execution:`」的授权。
2. **#09、#10 的 `blocked` 与 3/7、2/7 勾选并存。** `7828c99`、`5e186f7` 在落地软件切片的**同一个
   提交里**写入 `Execution: blocked`，并在票尾注明「真实认证、5000 股容量及整票业务结果仍
   blocked」。这是作者的有意标注，不是遗忘。是否该换成 `software-completed / real-certification-blocked`
   （该写法在 `.scratch/` 其他文档中已被用过 4 次）属于口径决定，不是只读审计能定的。
3. **#18 全勾 6/6 却是 `in-progress`。** 同样是有意的：2026-09-18 的票尾写着「Execution 暂保持
   in-progress 至共同收尾……不得据此关闭完整包、9 月 11 日真实市场报告、来源认证或切换」。
   **不要因为看到 6/6 就把它改成 `completed`。**
4. **#24 `Status: superseded` 但 `Execution: not-started`。** `c5b0922` 已把它拆成 25/26/27。
   `not-started` 字面为真（确实从未实施），`Status` 已承载「已被取代」，改 `Execution` 只会
   造一个新取值。保留，但按 `Execution` 筛票的人需要知道这张是死票。
5. **#17 正文与票头互相矛盾。** `Latest runtime checkpoint` 那一段末尾仍留着上一版的
   「新目录 Worker 及本票其余原验收仍开放；**未提交或关闭本票**」，而票头已是 `Status: done`
   ＋ 18/18 全勾。属于正文残留，改正文需要核对「本票范围」到底包含什么，只读无法判定。
6. **#25 有一个挂本票号的提交未被票面记录。** `e98e8c8`「Assert nonempty certified delivery
   identity across official channels (#25)」（2026-09-18）改了 `tests/fixtures/delivery_assertions.py`
   及四个 `tests/integration/test_official_*_fallback.py`，**只有测试、没有提交说明正文**，
   票内也没有 `## Comments` 记它。它是否构成本票的实施起点无法只读判定，因此我按票内
   「已完成/待票 19 之后」的自述取 `blocked`，未据此声称任何验收达成。
7. **#28 的票面与 `4be17e2` 长期脱节。** `4be17e2`「Block new Worker publication without an
   independent calendar (#28)」（2026-09-18）落了 `src/pring_cycle/worker.py` 与
   `tests/integration/test_worker_calendar_gate.py` 等 4 个测试文件，票面却一直是
   `not-started` ＋ 0/4。本次核对期间 B1 已把它改为 `in-progress` 并附了事实对齐，
   本任务未做任何改动。
8. **`Execution:` 字段本身没有任何文档定义。** `docs/agents/issue-tracker.md` 只规定 `Status:`，
   `docs/agents/triage-labels.md` 只定义分流标签。全仓实际出现了 19 种不同取值（`completed` 23、
   `blocked` 21、`in-progress` 20、`completed-code-batch` 14，以及十余种一次性长句）。
   没有约定就无法判定「什么算不自洽」，本次一律按已出现过的取值取最保守的一个。

## 现在真正可以开工的票

**无依赖、无外部缺件、0 勾选：**

- **#27（修正五项 P2 国际行情的口径与身份）** —— `**Blocked by:** 无`，`Execution: not-started`，
  0/4，除建票提交 `c5b0922` 外无任何后续提交。**这是唯一一张干净可起的实施票**；影响面盘点
  由本组 B4 产出（`survey-27-identity-migration-20260921.md`）。

**能起但只能起一部分：**

- **#28** —— 无依赖，`4be17e2` 已落地一半。按 B1 的 `finding-28-calendar-facts-20260921.md`
  实施，**不要照票面原文做**。
- **#21 的只读准备部分** —— 票内 `Preparation blocked by: None` 明确允许；正式回放仍等 19。
- **#22** —— 已 `in-progress`、2026-09-21 仍在改，但 18/20/21 未完成，不能走到切换。
- **#18** —— 无依赖、6/6 全勾，剩下的是与 17/19/22 的共同收尾，不是新实施。

**不要碰（外部原件缺失，不是代码问题）：** #04、#05、#06、#07、#08、#11。它们缺的分别是
历史公开时间原件、北交所可对账数值（403）、TuShare 六系列原响应、静态 PE/PB 目标期数值、
BSE 换码通知正文、PP/CF/TA 仓单规则原件——都不是写代码能解除的。

**依赖未满足：** #09、#10（等 08）、#12（等 11）、#19（等九张）、#20、#25（等 19）。

**已关闭或搁置：** #01、#02、#03、#15、#16、#17（completed）；#23（deferred，用户 2026-09-11
明确选择延后）；#24（superseded）；#26（reverted，`5fe9cf8`，且已改为 `needs-domain-decision`）。

## 本次改动清单

```
issues/17-full-run-gap-retrieval.md      Execution: complete    → completed
issues/20-retrieval-paired-benchmark.md  Execution:（缺）       → blocked
issues/21-public-replay-120d.md          Execution:（缺）       → blocked
issues/22-live-acceptance-cutover.md     Execution:（缺）       → in-progress
issues/25-freshness-fallback.md          Execution: not-started → blocked
```

共 5 行。未改 `Status:`，未动任何 `- [ ]` / `- [x]`，未碰 `src/`、`tests/`、`tools/`，
未运行 pytest 或 `tools/check.py`，未触碰 `issues/28-trade-calendar-never-acquired.md`。
