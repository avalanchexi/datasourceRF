# 票 06 验收取证：更正失败与体检差异（Codex 只读，2026-10-12）

提示词：`/home/tywin/.claude/jobs/cd7879cd/tmp/mr-06/codex-investigate.txt`；命令 `codex exec -s read-only`。以下为原样输出。

结论：Q1 是生产证据窗口缺陷；Q2、Q3 是体检规则误报；Q4 符合引用留存规则，但报告隐藏了成员差别；Q5 是早期更正失败的后续影响。

本次数据库连接全部使用 `file:...?mode=ro`。未修改文件、未运行 pytest、未联网、未启动 worker。以下区分只读实测与源码推断。

**Q1：回看原料被派生函数选成了窗口内展示证据。**

根因链如下：

1. 上下文构建分别建立了“截至该日公开可见”的 `repository` 和“再限制窗口下界”的 `visible_repository`。[context_projection.py:322](/mnt/d/cursor/datasourceRF/src/pring_cycle/context_projection.py:322)
2. 普通指标行使用 `visible_repository`，但 `_derived_market_context_rows()` 收到的是**没有窗口下界的 `repository`**。[context_projection.py:357](/mnt/d/cursor/datasourceRF/src/pring_cycle/context_projection.py:357)、[context_projection.py:447](/mnt/d/cursor/datasourceRF/src/pring_cycle/context_projection.py:447)
3. 贷款派生按成员排序，直接取 `current = ordered[-1]`；前一期连续便计算，没有检查产出期是否落在展示窗口内。**这是关键选期位置。**[context_projection.py:2323](/mnt/d/cursor/datasourceRF/src/pring_cycle/context_projection.py:2323)
4. 派生行直接并入 `rows_by_metric`，随后进入 `credit.evidence`，没有再次截取窗口。[context_projection.py:476](/mnt/d/cursor/datasourceRF/src/pring_cycle/context_projection.py:476)、[context_projection.py:663](/mnt/d/cursor/datasourceRF/src/pring_cycle/context_projection.py:663)
5. 投影校验发现其 `period=2025-08-31` 早于窗口下界，抛出指定异常。[projections.py:647](/mnt/d/cursor/datasourceRF/src/pring_cycle/projections.py:647)

实测当前库的贷款原料：

```sql
SELECT period_end, count(*),
       min(public_available_at), min(available_at)
FROM source_claim
WHERE metric_id='CN_LOAN_STRUCTURE'
GROUP BY period_end;
```

相关结果：

| 期次 | 声明数 | 公开时间 UTC | 入库时间 UTC |
|---|---:|---|---|
| 2025-07 | 9 | 2025-08-13 09:00:28 | 2026-10-08 22:37:13.704750 |
| 2025-08 | 9 | 2025-09-12 09:00:31 | 2026-10-08 22:37:14.719945 |
| 2026-07 | 9 | 2026-08-14 08:30:05 | 2026-10-08 22:37:16.215566 |

因此，在本次系统截止时间下回算 08-13，2025-08 是最新公开可见贷款期；08-14 才能看到 2026-07。这里“后来入库、但历史上已公开”的原料可以参与补算，**错误在展示期越界，而不是公开截止过滤失效**。

只读调用真实生产派生函数，设置 `persist_derived=False`，结果为：

| 补算日 | 贷款派生输出 | 窗口校验 |
|---|---|---|
| 08-13 | 9 条，期次 2025-08 | 指定越界异常 |
| 08-14 | 0 条 | 此项通过 |
| 09-14 | 9 条，期次 2026-08 | 此项通过 |

关于你复现的“9 个成员各 2 条”：我另实测了 `_metric_rows()`。窗口下界为 `None` 时，它会再选出 9 条 2025-08 原始累计值；设置有效下界时只留下缺口行。故“9 条原始＋9 条派生”可以出现；**即使正确设置下界，绕过下界的 9 条派生也足以触发失败**。原始行的选期位置是 [context_projection.py:2757](/mnt/d/cursor/datasourceRF/src/pring_cycle/context_projection.py:2757)。未将这个 18 条数量断言为原始 worker 当时的完整输出。

首次初始化没有触发这条数据链。查询：

```sql
SELECT count(*)
FROM source_claim
WHERE metric_id='CN_LOAN_STRUCTURE'
  AND julianday(available_at) <= (
    SELECT julianday(system_as_of)
    FROM parent_run
    WHERE run_id='run-a0418ed439ef25c9e00c'
  );
```

结果为 **0**。初始化截止为 `2026-09-23T19:58:56.425178Z`，上述原料尚未入库。

2025-07、2025-08 确属公式回看原料：

- `source_claim_acquisition → acquisition_request → full_run_acquisition` 显示，它们由 `run-8a3779cff80f6bd586a0` 的 `gap_retrieval` 获取，请求参数分别为 `family=pbc_loan_structure, period=2025-07/2025-08`。
- 贷款当月增量同比差需要 `t、t−1、t−12、t−13`；对 2026-08 就需要这两个去年期次。[confirmation.py:134](/mnt/d/cursor/datasourceRF/src/pring_cycle/confirmation.py:134)、[lookback.py:339](/mnt/d/cursor/datasourceRF/src/pring_cycle/lookback.py:339)
- 抽查两个期次各一条声明，均被 25 个留存投影引用，出现在确认度成员血缘、模型输入编号和冻结快照中。因此按引用例外留存，并非清理遗漏。[retention.py:181](/mnt/d/cursor/datasourceRF/src/pring_cycle/retention.py:181)

**普通补算缺失日同样受影响。** `_backfill()` 对缺失日和需要更正的旧日都调用 `_summarize_day()`；后者使用相同上下文构建。[day_summary.py:323](/mnt/d/cursor/datasourceRF/src/pring_cycle/day_summary.py:323)、[day_summary.py:374](/mnt/d/cursor/datasourceRF/src/pring_cycle/day_summary.py:374)

**下一次会重试仍在窗口里的失败日。** 当前按每日最新评估统计，仍有 **85 日，04-13～08-13，口径不是 `core-history-v0002`**。异常只进入失败列表，没有成功更正记录，也没有重试次数上限。[day_summary.py:316](/mnt/d/cursor/datasourceRF/src/pring_cycle/day_summary.py:316)

准确条件是：

- 同一目标日、核心历史齐备、原料与代码不变：85 日会再次尝试并再次失败。
- 窗口前移：只重试其中仍在窗口内的日子，并非永远固定 85 日。
- 成功更正后口径匹配，或日子移出窗口，才不再被选中；窗口首日推进至 08-14 后，这批日子全部退出，相当于当前窗口再推进 85 个交易日。
- 若下一次核心历史不足、`basis=None`，旧日更正会被跳过；这不代表问题解决。

`summary_corrections=34` 是**成功落库的更正日计数**，不是只计划尝试了 34 日。[worker.py:621](/mnt/d/cursor/datasourceRF/src/pring_cycle/worker.py:621)

是否实测：数据、日志 85 条、选期及校验异常均已只读实测；下一次运行行为为源码推断，未执行完整补算或 worker。

**Q2：两项不一致是体检未覆盖票 02，不是违反生产设计。**

生产明确区分评估值与展示值：

- `stage.last_confirmed_stage` 保留窗口阶段史所得值；`shown_stage` 才允许用成功回溯结果补充。[p0.py:101](/mnt/d/cursor/datasourceRF/src/pring_cycle/p0.py:101)
- 评估写入 `stage.last_confirmed_stage`。[p0.py:198](/mnt/d/cursor/datasourceRF/src/pring_cycle/p0.py:198)
- `cycle_overview.last_confirmed_stage` 写入 `shown_stage`。[p0.py:217](/mnt/d/cursor/datasourceRF/src/pring_cycle/p0.py:217)
- `last_confirmed_lookback` 同时写入 `cycle_overview` 和 `stage_history` 数据集。[p0.py:231](/mnt/d/cursor/datasourceRF/src/pring_cycle/p0.py:231)

当前库实查目标投影：

```text
p0_assessment.last_confirmed_stage = null
cycle_overview.last_confirmed_stage = stage_iii
last_confirmed_lookback:
  source=lookback, status=found, stage=stage_iii
  stage_date=2026-04-10
  searched_from=2025-04-14, searched_through=2026-04-10
```

体检第一条无条件要求评估与总览一致；第二条只查 `formal` 阶段史事件，没有读取回溯元数据。[output_consistency.py:159](/mnt/d/cursor/datasourceRF/tools/quality/output_consistency.py:159)、[output_consistency.py:168](/mnt/d/cursor/datasourceRF/tools/quality/output_consistency.py:168)

是否实测：已查询生产落库字段并核对规则源码；未重新执行整份体检。

**Q3：189 项“缺失”是假阳性，生产没有漏算该日最新期。**

体检的贷款公式没有设置 `newest_anchor_only=True`，默认允许向旧期寻找可计算值。[derived.py:794](/mnt/d/cursor/datasourceRF/tools/quality/derived.py:794)、[derived.py:837](/mnt/d/cursor/datasourceRF/tools/quality/derived.py:837)

`_newest_complete()` 从新到旧逐期尝试；2026-07 缺 2026-06 后，它继续回退到原料齐全的 2025-08。`_judge()` 只要找到这个旧期、投影却没有记录，就判“缺失”。[derived.py:990](/mnt/d/cursor/datasourceRF/tools/quality/derived.py:990)、[derived.py:1022](/mnt/d/cursor/datasourceRF/tools/quality/derived.py:1022)

生产则只取最新期，若前月不连续就直接跳过，**不会回退寻找旧的完整对**。[context_projection.py:2323](/mnt/d/cursor/datasourceRF/src/pring_cycle/context_projection.py:2323)

实际只读调用结果：

```text
08-14～09-11：21 日 × 9 成员
_judge → ('缺失', '2025-08-31')：189 次
```

原料包含 `2025-07、2025-08、2026-07`，没有 `2026-06`。生产该时段不输出贷款派生值；09-14 能看到 2026-08 后，已有投影包含 9 条 2026-08 派生值。

因此本例的直接原因是**生产锚定最新期、体检回退旧期**。生产这一分支本身没有正确限制展示窗口，恰好也是 Q1 的问题，不能把这里的零输出归因于窗口守卫。

是否实测：189 次体检判定、生产派生函数和实际投影记录均已只读实测。

**Q4：前两项由新更正投影引用而留存；第三项没有引用。工业财务还存在成员粒度差别。**

运行前备份中，三项的 2026-03 声明均不存在。当前库查询：

```sql
SELECT metric_id, dimensions_json, available_at
FROM source_claim
WHERE period_end='2026-03-31'
  AND metric_id IN (
    'CN_FINISHED_GOODS_INVENTORY',
    'CN_INDUSTRIAL_FINANCE',
    'CN_INVENTORY_TURNOVER'
  );
```

结果只有：

| 指标 | 留下的成员 | 入库时间 UTC |
|---|---|---|
| CN_FINISHED_GOODS_INVENTORY | `official_yoy` | 2026-10-11 18:30:01.306049 |
| CN_INDUSTRIAL_FINANCE | `profit / official_yoy` | 同上 |

这两项统计期早于留存下界 04-13，本应清理，但命中了引用保留条件。关系存放于：

- `analytical_dataset.document_json`，本例具体是 `macro.model_input_observation_version_ids`。
- `projection_set.envelope_json.evidence_snapshot_id → evidence_snapshot.observation_version_ids_json`。
- 另有 `derived_observation.input_observation_version_ids_json` 保留途径，但本例未命中。

依据为 [retention.py:181](/mnt/d/cursor/datasourceRF/src/pring_cycle/retention.py:181)。按声明 ID 精确扫描 JSON 引用的结果：

| 声明 | 引用投影数 | 对应快照引用数 | 引用投影日期 |
|---|---:|---:|---|
| 产成品存货同比，`c8cb21df…` | 8 | 8 | 08-17～08-26 |
| 工业利润同比，`d50f73bc…` | 30 | 30 | 08-14～09-24 |
| 存货周转，`b83ef12e…` | 0 | 0 | 无 |
| 工业营收同比，`f6c69c78…` | 0 | 0 | 无 |

上述保留投影均来自本次运行。存货周转声明在本次最终计划中被选中，但没有留存引用，因此被清理。

**需要修正“工业财务整期留下”的理解：**最终计划选中的是营收同比 `f6c69c78…`，它也已被清理；当前存在的是利润同比 `d50f73bc…`。体检按指标聚合 `stored[period]`，任一成员仍在就认为该期存在，因此不再列整期“已入库后被清理”。[acquisition.py:1072](/mnt/d/cursor/datasourceRF/tools/quality/acquisition.py:1072)、[acquisition.py:1096](/mnt/d/cursor/datasourceRF/tools/quality/acquisition.py:1096)

是否实测：两库存在性、具体成员、计划声明 ID 和引用数量均已实查；未执行清理函数。

**Q5：原因确认，但 35 日中目标日总览应单独看。**

更正日发布时，上一确认阶段来自 `_last_confirmed_stage(day)`；该函数读取前一自然日及以前的阶段史。[day_summary.py:383](/mnt/d/cursor/datasourceRF/src/pring_cycle/day_summary.py:383)、[day_summary.py:447](/mnt/d/cursor/datasourceRF/src/pring_cycle/day_summary.py:447)

底层查询先取**每个日期最新评估**，再找最近的 `event_kind='formal'`，不会从投影的回溯字段取值。[projections.py:251](/mnt/d/cursor/datasourceRF/src/pring_cycle/projections.py:251)

实查：

```sql
SELECT count(*) FROM p0_assessment WHERE event_kind='formal';
-- 0
```

本次 08-14～10-09 的 35 条新评估全部为：

```text
core_history_basis=core-history-v0002
current_stage=null
last_confirmed_stage=null
```

早期 85 日没有成功更正，仍保留旧口径无阶段评估；后续自然读不到正式阶段。这不是后续日子的三核心状态继续算错。

我用体检的冻结核心输入恢复与独立重算函数重新计算，得到：

```text
stage_iii：67 个交易日，2026-04-27～2026-08-03
08-13、08-14、10-09：(current_stage=null, last_confirmed_stage=stage_iii)
```

因此，**若早期日子按这些核心结果成功更正**，后续 `_last_confirmed_stage(day)` 就能读取最近的 stage_iii；目标日也不必再靠窗口外回溯补充展示值。[day_summary.py:255](/mnt/d/cursor/datasourceRF/src/pring_cycle/day_summary.py:255)

例外说明：35 日中的 **10-09 总览已经是 stage_iii**；该日仍不一致的是评估及阶段史事件。其余 34 个更正日没有传入 lookback。这与 Q2 的设计区别一致。

是否实测：已实际运行只读核心独立重算并查询阶段史；“85 日成功更正后”的发布结果为源码推断，未执行更正写入。

**摘要**

Q1：生产贷款派生绕过展示窗口下界；失败日仍会重试，直至成功更正、移出窗口，或暂因核心历史不足被跳过。  
Q2：两项不一致是体检未覆盖票 02；评估保留窗口值、总览使用回溯值符合设计。  
Q3：189 项是假阳性；体检回退到 2025-08，生产锚定缺少前月原料的 2026-07。  
Q4：新投影引用保住存货同比和工业利润同比；周转及工业营收同比仍被清理，报告按指标掩盖了成员区别。  
Q5：早期更正失败导致正式阶段史为空，后续读不到 stage_iii；独立重算已确认早期存在 67 个 stage_iii 日。
