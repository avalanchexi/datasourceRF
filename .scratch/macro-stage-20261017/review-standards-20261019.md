审查范围为 `2502ae4..e2ad06d`。全程只读，未运行 pytest 或全套测试；下述标注“探针确认”的问题均以当前源码在内存中复现。

1. **P1：滞回后的五维依据仍解释原始阶段。**  
   位置：[macro_judgement.py:397](/home/tywin/worktrees/datasourceRF-ms/src/pring_cycle/macro_judgement.py:397)。`hold()` 修改主结论，却保留 `judge()` 按原始阶段生成的 `dimensions[].matches`。  
   **失败情形：**昨日主结论 V；今日五维为中性、上行、上行、低位上行、主动补库，原始判断 III。滞回后标题为“V，1/5 吻合”，五维明细却全部显示“吻合”，报告亦读取这些错误依据。探针确认。  
   **修法：**最终主结论确定后，统一按其阶段重算五维吻合标记；relink 同样经过这一步。补真实单日汇总到页面、报告的回归。

2. **P1：报告正文可以改写宏观阶段并通过校验。**  
   位置：[reports.py:1607](/home/tywin/worktrees/datasourceRF-ms/src/pring_cycle/reports.py:1607)、[reports.py:1652](/home/tywin/worktrees/datasourceRF-ms/src/pring_cycle/reports.py:1652)。校验只识别有限句式，未匹配的阶段陈述直接放行，不满足 ADR-0003 和规格第 39 条。  
   **失败情形：**结构化结论为“III／倾向”，正文写“宏观判断为第5阶段（倾向）”“宏观判断为阶段Ⅴ（倾向）”，或者“主结论已经进入第五阶段”，均返回 `succeeded`。探针确认。  
   **修法：**阶段、把握程度等事实句由确定性模板生成，AI 只补解释；至少先统一数字表示并补齐上述拒收用例，不能把正则未匹配当作事实一致。

3. **P1：生效前漏跑日会被倒推宏观判断。**  
   位置：[day_summary.py:442](/home/tywin/worktrees/datasourceRF-ms/src/pring_cycle/day_summary.py:442)。`held is None` 无条件允许宏观判断，实际边界是“有没有旧汇总”，不是模型生效业务日。  
   **失败情形：**v0016 在 D0 生效，D−1 漏跑；首次补算 D−1 时发布宏观阶段，并成为 D0 滞回的前态。已有旧模型汇总的 D−1 却保持空白，同一生效边界因历史完整度而异。违反 ADR-0043“生效前不倒推”。  
   **修法：**明确并传递宏观规则生效业务日，目标日、补算和更正统一检查。票 08 已记录这一偏离，但尚无用户确认取代原约定。

4. **P2：同类价格候选跳过缺口，把不完整窗口当成连续 30 日。**  
   位置：[macro_signals.py:527](/home/tywin/worktrees/datasourceRF-ms/src/pring_cycle/macro_signals.py:527)。读取展示点时删除所有非数值点，也不检查行的时效状态。  
   **失败情形：**40 个交易日持续下跌，其中倒数第二日价格为 `None`；代码压成 39 个点，仍生成 P1“债券同类转熊”。连续多日沿用这份残缺序列还会累计成熟度。探针确认。  
   **修法：**按所属市场日历验证所需 31 个连续收盘点及最新应有期，再调用已有候选算法；缺口、冲突或过期时不生成候选。展示序列不能直接替代经过完整性检查的计算输入。

5. **P2：relink 没有重选分化信号的并列判断。**  
   位置：[macro_signals.py:698](/home/tywin/worktrees/datasourceRF-ms/src/pring_cycle/macro_signals.py:698)、[p0.py:427](/home/tywin/worktrees/datasourceRF-ms/src/pring_cycle/p0.py:427)。`regrouped()` 只改 `transition.from` 和分组，保留旧 `rejudged.stage`、`transition.to`。  
   **失败情形：**主结论 V，PMI 少数方向重判为 III／IV／V 并列；参照 III 时取 III。参照更正为 VI 后应取 V、归“支持维持”，实际仍指向 III、归“支持后退”。探针确认。  
   **修法：**用更正后的参照重新选择分化重判结果，再生成转换和分组；补含分化信号、滞回进行中的 relink 用例。

6. **P2：不同转换仅因终点相同，就被提前判为“成形”。**  
   位置：[macro_signals.py:297](/home/tywin/worktrees/datasourceRF-ms/src/pring_cycle/macro_signals.py:297)、[macro_signals.py:335](/home/tywin/worktrees/datasourceRF-ms/src/pring_cycle/macro_signals.py:335)。`_move()` 只使用目标阶段，丢弃转换起点。  
   **失败情形：**首日同时出现 B2“IV→V”和 C6“VI→V”，两条均立即成为 `forming`；它们是不同方向的转换，不满足对照表“当日两格指向同一转换”。探针确认。  
   **修法：**已映射信号以完整 `(from, to)` 标识转换；未映射信号另按资产及方向处理。增加 B/K 与 P/C 混合场景。

7. **P2：宏观投影校验允许得分与五维事实脱离。**  
   位置：[macro_judgement.py:719](/home/tywin/worktrees/datasourceRF-ms/src/pring_cycle/macro_judgement.py:719)。校验只检查得分范围及结论与得分自洽，没有验证得分确实来自冻结特征表。  
   **失败情形：**保留应判 III 的五维读数，把得分改成“V=5、其他=0”，同步修改 `raw` 和主结论后，`validate()` 通过；`matches` 也未被核对。探针确认。  
   **修法：**根据该模型冻结规则校验六阶段得分、最终阶段的吻合标记，并核对参照与本集上一确认阶段；补“内部自洽但违背输入”的拒收测试。

8. **P2：清单工厂泄漏共享可变特征表。**  
   位置：[macro_judgement.py:168](/home/tywin/worktrees/datasourceRF-ms/src/pring_cycle/macro_judgement.py:168)。`dict(cells)` 只浅拷贝，格内字典与列表仍引用 `_SIGNATURE`。  
   **失败情形：**对一次 `model_v0016_manifest()` 返回值的 I 阶段政策列表追加 `neutral`，下一次全新调用也返回这个修改，污染同进程后续候选模型和测试。探针确认。  
   **修法：**深拷贝特征表，或使用不可变内部结构并逐层生成清单；通过公开模型工厂验证两次返回值互不影响。

9. **P2：删除当日阶段史事件可以绕过宏观记录校验。**  
   位置：[projections.py:687](/home/tywin/worktrees/datasourceRF-ms/src/pring_cycle/projections.py:687)。找不到当日事件时直接返回。  
   **失败情形：**总览保留“V／明确”，但阶段史删除当日事件，新增校验仍通过，无法保证“每日记录主结论”。探针确认。  
   **修法：**有宏观判断块时，要求恰有一个当日事件且结论一致；同时核对提供的展示日记录。现有测试只覆盖修改、删除事件内字段，没有覆盖删除整个事件。

10. **P3：新宏观页面仍使用已禁用的“正式阶段”术语。**  
    位置：[cockpit.py:2611](/home/tywin/worktrees/datasourceRF-ms/src/pring_cycle/cockpit.py:2611)。新页面说明、色带及区间切换仍沿用旧称，与 `GLOSSARY.md` 和 `docs/agents/domain.md` 的术语要求不一致。  
    **失败情形：**同一 v0016 页面在①称“价格阶段”，⑥却称“正式阶段”，容易让用户误以为另有优先级更高的正式结论。  
    **修法：**统一新页面可见文字为“价格阶段”，保留 `formal_stage` 代码标识符；更新页面断言。

测试主要经单日汇总、页面和报告入口检查外部行为，但 [test_macro_report.py:295](/home/tywin/worktrees/datasourceRF-ms/tests/reports/test_macro_report.py:295) 手工改写投影构造滞回，绕过了真实发布一致性。B/K 行为、分化跨两期、滞回中 relink、核心不可用页面文案仍缺专门覆盖。

性能方面，新增 [projections.py:357](/home/tywin/worktrees/datasourceRF-ms/src/pring_cycle/projections.py:357) 每日重复执行历史排名与 JSON 查询，分化重判则逐项深拷贝完整确认度块。120 日补算存在重复扫描和复制成本，但本次未测端到端耗时，**尚不能认定性能回归**；应先分段计时，再决定是否批量读取前态、缩小重判复制范围。
