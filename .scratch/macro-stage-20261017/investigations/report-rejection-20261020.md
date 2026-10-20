结论：**两次 `sections[0]` 拒收都是校验误判，直接原因是得分正则漏掉了“各得”**。两份输出均正确陈述了“第三阶段、倾向，第三／第四／第五阶段各得 3 维”；校验却把第四阶段归为主结论，拿它与 `{stage_iii}` 比较后拒收。

另外发现一层被遮蔽的问题：补上“各得”后，校验又把“不能解释为明确结论／不是明确的结论”当成肯定“明确”，继续误拒。以下调查未修改文件或数据库；数据库连接使用 `mode=ro` 和 `PRAGMA query_only=ON`，源码导入均设置了指定的两个环境变量。

**1. 留存位置及两份原文**

关联链为：

`report_attempt.output_hash` → `artifact.content_hash`／`artifact_reference` → artifacts JSON 文件。

两份文件的 SHA-256 均与 `output_hash` 一致；共同的 `source_reference` 为 `report-output:bundle-612f01b4b419587fd525`。冻结输入位于 `evidence_bundle.document_json`，`bundle_id=bundle-612f01b4b419587fd525`。

代码在校验前保存输出，见 [reports.py:1308](/mnt/d/cursor/datasourceRF/src/pring_cycle/reports.py:1308)；保存位置见 [reports.py:1033](/mnt/d/cursor/datasourceRF/src/pring_cycle/reports.py:1033) 和 [artifacts.py:34](/mnt/d/cursor/datasourceRF/src/pring_cycle/artifacts.py:34)。`report_snapshot.body_json` 保存的是降级报告，不能用它代替拒收原文。

Attempt 42，`codex_cli`：

```text
/home/tywin/.local/share/pring-cycle/artifacts/sha256/ce/cefc2e6844c70871b415bb555cc27e75bd0832675a7180908ee303157f0df80d
```

`sections[0].title`：宏观判断与五维依据

`sections[0].explanation` 全文：

> 宏观判断为第三阶段，把握程度为倾向。报告输入的确定性规则结果显示，五维均有判断：政策中性、增长上行、主动补库存与第三阶段吻合，信用下行、物价上行与其不吻合；第三阶段、第四阶段、第五阶段各得 3 维，规则选择距离上次确认的第三阶段最近者，因此不能解释为明确结论。本次没有滞回保持，主结论与当日原始判断均为第三阶段、倾向，也没有因维度缺失退回价格组合推断。上述得分及选择依据均来自报告输入的宏观判断规则结果。

Attempt 43，`claude_code_cli`：

```text
/home/tywin/.local/share/pring-cycle/artifacts/sha256/2e/2e134d3abb2d6ea6cb520ddf87c3aa3a1515126dff5754d609c9dc72b11e4d8b
```

`sections[0].title`：宏观判断与五维依据

`sections[0].explanation` 全文：

> 宏观判断为第三阶段，把握程度为倾向，不是明确的结论：五个维度都有读数，其中 3 维与第三阶段吻合，但第三阶段、第四阶段、第五阶段各得 3 维、三者并列（第六阶段 2 维，第一阶段 1 维，第二阶段 0 维）。按规则在并列阶段中取离上次确认的第三阶段最近的一个，所以落在第三阶段，相对上次确认没有变化。滞回状态为初始，没有触发滞回保持，当日原始判断同样是第三阶段（倾向），与主结论一致。分维度看：政策维度为中性，吻合，依据是 120 日内没有降息、LPR 下调、降准或上调，七天逆回购利率 1.4%（TuShare 资讯，2026-10-19），1 年期和 5 年期以上 LPR 分别为 3.0% 和 3.5%（中国货币网，2026-09-20），最近一次降准在 2025-05-15（中国人民银行），已在窗口之外。信用维度为下行、处于低位，不吻合，社融存量同比 7.1%，呈下行且内部分化（TuShare、中国人民银行，2026-09-30），M1 同比 3.2%、M2 同比 7.2%，两者都在下行（TuShare，2026-09-30）。增长维度为上行、处于中位，吻合，制造业 PMI 50.1，上行但内部分化（TuShare，2026-09-30），工业增加值当月实际同比 5.5%（TuShare 资讯，2026-09-30），GDP 实际季度同比 4.5%（2026-09-30，输入中未标注来源），这三项上行；产能利用率 73.1%，下行（TuShare 资讯、国家统计局，2026-09-30），工业企业利润累计同比 15.7%，下行且内部分化（TuShare 资讯、国家统计局，统计期为 2026-08-31，比其他指标晚一个月）。物价维度为上行、处于高位，不吻合，PPI 同比 5.0%、CPI 同比 0.9%、PMI 出厂价格 54.0，都在上行（TuShare，2026-09-30）。库存维度为主动补库存，吻合，统计期 2026-08-31，辅助成员中 PMI 产成品库存方向相反。

**2. 当前 main 的离线复现**

源码版本：`main@2f876b2e3f48125c63471d40a48ab1573a664346`，`reports.py` 无工作区差异。用 `.venv/bin/python` 从指定 `src` 导入，重建冻结 `ReportInput`，直接调用 `_validate_ai_document`；通过内存跟踪读取 `_macro_statements` 的实际局部变量。

两次完整复现均得到：

```text
stage_mutation_rejected
{"check":"macro_stated_stage",
 "path":"sections[0]",
 "section_index":0,
 "section_title":"宏观判断与五维依据"}
```

从该 bundle 实际构造的允许集合如下；不是用重放投影或现算结果代替。构造代码见 [reports.py:1732](/mnt/d/cursor/datasourceRF/src/pring_cycle/reports.py:1732)。

| subject | 实际 `allowed[subject]` |
|---|---|
| conclusion | `{stage_iii}` |
| raw | `{stage_iii}` |
| price | `{None}` |
| reference | `{stage_iii}` |
| expected | `{stage_iii}` |
| tied | `{stage_iii, stage_iv, stage_v}` |
| signal | `{None, stage_iii, stage_iv, stage_v}` |
| candidate | `{None, stage_i, stage_iii, stage_v}` |

`score` 不走 `allowed`；它比较 `macro.scores`，实际为：

```text
stage_i=1, stage_ii=0, stage_iii=3,
stage_iv=3, stage_v=3, stage_vi=2
```

按代码的 `[。；;！!？?]` 切句，逐句结果如下。**生产校验遇到首个错误立即返回；表中后续提及是离线继续枚举的结果。**

| 输出／句子 | 阶段提及 → 实际 subject | 结果 |
|---|---|---|
| 42①“宏观判断为第三阶段，把握程度为倾向” | III → conclusion，允许 `{III}` | 通过 |
| 42②“报告输入……与第三阶段吻合……不吻合” | III → conclusion，允许 `{III}` | 通过 |
| 42③“第三阶段、第四阶段、第五阶段各得 3 维，规则选择距离上次确认的第三阶段最近者，因此不能解释为明确结论” | III、IV、V → conclusion，允许 `{III}`；末尾 III → reference，允许 `{III}` | **IV 是实际首个拒绝点；V 继续枚举也不通过** |
| 42④“本次没有滞回保持……原始判断均为第三阶段、倾向……” | III → raw，允许 `{III}` | 通过 |
| 42⑤“上述得分及选择依据……” | 无阶段提及 | 无阶段错误 |
| 43①从“宏观判断为第三阶段”至“第二阶段 0 维）”的完整首句 | 前两次 III 及列表中的 III、IV、V → conclusion，允许 `{III}`；VI、I、II → score，分别为 2、1、0 | **IV 是实际首个拒绝点；V 继续枚举也不通过；后三个得分正确** |
| 43②“按规则在并列阶段中取离上次确认的第三阶段最近的一个，所以落在第三阶段，相对上次确认没有变化” | 两次 III 均 → reference，允许 `{III}` | 通过；第二次实际在说选择结果，但同值掩盖了归属不精确 |
| 43③“滞回状态为初始……当日原始判断同样是第三阶段（倾向）……” | III → raw，允许 `{III}` | 通过 |
| 43④政策；⑤信用；⑥增长前三项；⑦产能／利润；⑧物价；⑨库存 | 均无阶段提及 | 无阶段错误 |

表中 III 等是 `stage_iii` 等的缩写。

**3. 根因与判定**

阶段识别本身正确：`_MENTION` 找到了第三、第四、第五阶段，`_mention_stage` 也正确转换了代码。问题发生在归属：

1. `_chain_end` 正确跨过“第三阶段、第四阶段、第五阶段”，将后缀定位为“**各得 3 维……**”。见 [reports.py:1822](/mnt/d/cursor/datasourceRF/src/pring_cycle/reports.py:1822)。
2. `_FOLLOWING` 的得分正则只允许一个前缀选项：

   ```regex
   (?:同为|均为|都是|各|得分为|得分|得|为|[:：])?
   ```

   “各”之后要求数字，遇到“得”就失败；没有“各得”这一项。见 [reports.py:1697](/mnt/d/cursor/datasourceRF/src/pring_cycle/reports.py:1697)。
3. `_following` 因此返回 `None`。42 的列表前没有 subject 标记，默认 `conclusion`；43 最近的有效标记是“把握程度”，也属于 `conclusion`。见 [reports.py:1685](/mnt/d/cursor/datasourceRF/src/pring_cycle/reports.py:1685)、[reports.py:1772](/mnt/d/cursor/datasourceRF/src/pring_cycle/reports.py:1772)。
4. IV 不属于 `{stage_iii}`，于是返回 `macro_stated_stage`。见 [reports.py:1785](/mnt/d/cursor/datasourceRF/src/pring_cycle/reports.py:1785)。

**两段没有把第四／第五阶段说成当前宏观主结论；它们是在报告真实得分。** “上次确认”“原始判断”在本次相关提及中均通过；两段也没有陈述一个非空价格阶段。用户列举的“第五阶段预期债熊”等不是这次首节拒收的触发文本。

进一步，仅在内存中补上“各得”后：

| 输出 | 新暴露的拒收 |
|---|---|
| 42 | “因此**不能解释为明确结论**”中的“明确”被绑定到前面的参考阶段 III，要求 `(III, explicit)`；实际相关判断是 tendency |
| 43 | “**不是明确的结论**”中的“明确”被绑定到 conclusion，与 tendency 冲突 |

`_CONFIDENCE` 没处理这些否定表达，见 [reports.py:1703](/mnt/d/cursor/datasourceRF/src/pring_cycle/reports.py:1703)；绑定及比较见 [reports.py:1789](/mnt/d/cursor/datasourceRF/src/pring_cycle/reports.py:1789)、[reports.py:1841](/mnt/d/cursor/datasourceRF/src/pring_cycle/reports.py:1841)。

这是对**阶段与把握程度拒收原因**的判定，不代表已审核两篇报告的所有数值和其他文字。

**4. 最小修复建议与回归用例**

针对这两段，需要两处修复：

- **得分识别**：在 `_FOLLOWING` 的 score 前缀中增加 `各得`，保留逐阶段与 `macro.scores` 的比较。不要通过扩大 `allowed["conclusion"]` 放行，否则会漏掉真正改写主结论的输出。
- **把握程度的否定处理**：在 `_CONFIDENCE`／其消费循环中识别“不是明确”“不能解释为明确”的否定作用域，不能将其当作肯定的 `explicit`，也不能让否定词替代必需的肯定把握程度陈述。避免“句中有不就跳过整句”这种宽泛规则。

内存探针结果：

```text
原代码：
  42、43：sections[0] / macro_stated_stage

仅增加“各得”：
  42、43：sections[0] / macro_stated_confidence

增加“各得”并排除上述两种否定的肯定匹配：
  42、43：sections[0] 均通过，confidence_told=True
  42 整份文档：succeeded
```

建议把**两份完整首节＋该冻结宏观块**固化为离线回归样本，再覆盖这些真实片段：

| 回归输入 | 预期 |
|---|---|
| “第三阶段、第四阶段、第五阶段各得 3 维” | 三项均识别为 score，全部通过 |
| 42 上述完整触发句，包含“不能解释为明确结论” | 通过 |
| 43 完整首句，包含“不是明确的结论”、并列和六阶段得分 | 通过 |
| 两份完整 `sections[0]` | 无失败且 `confidence_told=True` |
| 把“各得 3 维”改为“各得 4 维” | `macro_stated_score` |
| “宏观判断为第四阶段，把握程度为倾向” | `macro_stated_stage` |
| “宏观判断为第三阶段，把握程度为明确” | `macro_stated_confidence` |

后三项反例在内存探针中仍正确拒收。

**整份 Claude 输出还存在另一处校验误判，不能声称这两处修改足以让它全部通过。** 首节通过后，`sections[1]` 的真实句子：

> 如果 PMI 改按少数方向计票，增长维度转为下行，判断会变为第五阶段，把握程度为明确（5 维中 4 维吻合），对应第三阶段向第五阶段转换，目前只是萌芽。

首个 V 被归为 conclusion，允许集合仍是 `{III}`；但 bundle 的 PMI `rejudged` 确为 `stage_v/explicit`。`_SUBJECTS` 支持“少数方向”，却随后把“把握程度”等重新归入 conclusion，条件推演的作用域没有完整保留。修复应同时约束该条件分句内的阶段、把握程度和转换端点，见 [reports.py:1681](/mnt/d/cursor/datasourceRF/src/pring_cycle/reports.py:1681)。此句应另加整句回归，不能仅补一个关键词后宣布完成。

本次无需归咎于提示词：它已经要求写明并列阶段与得分、不得将倾向写成明确，见 [reports.py:1415](/mnt/d/cursor/datasourceRF/src/pring_cycle/reports.py:1415)。模型使用“各得”和否定“明确”是在履行这个要求。

**5. 为什么重放和测试没有暴露**

- **重放没有进入 AI 正文校验路径。** `replay_run.py` 显式阻止 codex／claude 子进程，并调用 `process_pending_run(paths, report_adapters=())`。见 [replay_run.py:64](/mnt/d/cursor/datasourceRF/.scratch/macro-stage-20261017/integration/replay/replay_run.py:64)、[replay_run.py:213](/mnt/d/cursor/datasourceRF/.scratch/macro-stage-20261017/integration/replay/replay_run.py:213)。它验证了计算、投影和确定性报告链路，没有生成自然语言输出供 `_macro_statements` 检查。
- **验收记录明确承认这个覆盖空白。** [acceptance.md:51](/mnt/d/cursor/datasourceRF/.scratch/macro-stage-20261017/acceptance.md:51) 写明“v0011 提示词下的真实 AI 报告尚未实测”，将新校验留待首个正式运行检查。
- **测试覆盖了相近概念，缺少这两个表达变体。** 已有正例使用“并列，各 3 维”和“同为 3 分”，没有“各得 3 维”；把握程度测试覆盖肯定改写，却没有此次两种否定句。见 [test_macro_report.py:146](/mnt/d/cursor/datasourceRF/tests/reports/test_macro_report.py:146)、[test_macro_report.py:171](/mnt/d/cursor/datasourceRF/tests/reports/test_macro_report.py:171)、[test_macro_report.py:197](/mnt/d/cursor/datasourceRF/tests/reports/test_macro_report.py:197)。
- **CLI 测试不是自由生成的真实模型输出。** `install_cli` 的模拟程序直接用宏观块标题构造解释，见 [test_cli_protocol.py:101](/mnt/d/cursor/datasourceRF/tests/reports/test_cli_protocol.py:101)。模板回写测试也只证明固定模板能通过，见 [test_macro_report.py:305](/mnt/d/cursor/datasourceRF/tests/reports/test_macro_report.py:305)。
- **重放的阶段状态也不同。** 重放 10-19 是第五阶段明确、滞回保持，原始判断第三阶段倾向；本次正式 bundle 是生效初始状态，主结论直接为第三阶段倾向。这个差异已有记录，见 [10-integration-and-activation.md:22](/mnt/d/cursor/datasourceRF/.scratch/macro-stage-20261017/issues/10-integration-and-activation.md:22)。不过决定性的漏检原因仍是重放禁用 AI、测试缺少真实自然语言样本。
