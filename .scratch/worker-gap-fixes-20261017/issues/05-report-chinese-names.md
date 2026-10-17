# 05: AI 报告用中文名

**What to build:** AI 解读正文出现 `tushare:index_daily`、`stage_iii`（决定 5）。报告输入保留机器字段并附中文展示名（指标、来源、阶段）；提示词要求正文用中文名；报告解释校验发现原始代号时照常保存、报告详情标"含未翻译代号"，不判失败。规格 [../spec.md](../spec.md)，根因 [../investigation.md](../investigation.md)，决定 [../decisions.md](../decisions.md)。

**Blocked by:** None (can start immediately)

**Status:** done

- [x] 报告输入含中文展示名，机器字段不变
- [x] 正文含原始代号的报告照常保存并带标注；不含时无标注
- [x] 报告详情抽屉显示该标注
- [x] 两项必跑冒烟通过

## Comments

### 2026-10-17 实施

**改了什么**（分支 `wg-05`）

- `wording`：新增 `stage_name`（取 `STAGE_TITLES` 中文部分，如“第三阶段”）；`SOURCE_NAMES` 补登记来源前缀（`pbc` 中国人民银行、`chinamoney` 中国货币网、`eia`、`ecb`、`cboe`、`nasdaq`、`derived` 派生计算），`source_name` 精确匹配不到时按冒号前的提供方取名（`tushare:index_daily` → TuShare）。复用现有显示名逻辑，没有另起一套。
- `reports.ReportInput` 新增 `display_names`（`stages`／`metrics`／`sources` 三组“代号 → 中文名”），由 `create` 从当前阶段、结论与已验证结果里出现的代号推出（异常码 `gap:CN_X` 取冒号后的指标）；计入 bundle 身份与存档文档，送给 AI；机器字段原样不动，确定性骨架不复述。
- 提示词：要求正文提及阶段、指标、数据来源时用 `report_input.display_names` 的中文名，不写原始代号。提示词契约随之升版：普通 v0004→**v0008**、确认度 v0005→**v0009**、非典型组合 v0007→**v0010**（沿 569ffab 先例：提示文本变了就升契约）。不涉及模型版本。
- 报告解释校验：AI 解读通过校验后，扫描各节标题与正文，出现 `display_names` 中的代号或任一 `stage_*` 时在报告正文写入 `untranslated_codes`（排序列表），报告照常保存为 completed，不判失败；没有则不写该字段。
- 报告详情（驾驶舱 ⑦ 报告详情抽屉与报告页共用 `_report_head`）：有 `untranslated_codes` 时多一行“正文代号 含未翻译代号：stage_iii、tushare:index_daily”；没有则不显示。
- 阶段改写校验补中文：既然要求正文写“第三阶段”，`_STATED_STAGE` 同时识别“当前处于第X阶段”“目前阶段为第X阶段”，与罗马数字同样拦截改写（ADR-0003）。

**测试（先红后绿）**

- 报告入口 `tests/reports/test_report_boundary.py`：`test_report_input_names_its_stages_metrics_and_sources_in_chinese`、`test_cli_prompt_asks_for_the_chinese_names_of_the_codes_it_carries`、`test_report_with_untranslated_codes_is_kept_and_marked`、`test_a_stage_stated_by_its_chinese_name_is_checked_like_its_numeral`（3 例）。
- 首页渲染 `tests/web/test_reading_section.py::test_report_details_mark_a_reading_that_kept_raw_codes`。
- 契约升版连带改了 `test_cli_protocol.py`、`test_noncanonical_reading.py` 的版本字面量。
- 受影响：reports 三文件＋web 六文件 144 passed（合入 worker-gaps 74001ce 后复跑，27.5 秒）；确认度七文件、留存、模型版本切换、cockpit_http、ai_websearch、媒体页、来源契约隔离、TuShare 资讯共 443 passed（979 秒，另含排 heavy 锁约 5.5 分钟）。
- 两项必跑冒烟 2 passed（70 秒；排 heavy 锁约 22.5 分钟）。
- `ruff check`、`ruff format --check`、`mypy`（改动文件）通过。

**遗留／待主 agent 知悉的领域选择**

- 来源中文名取提供方粒度（`tushare:*` 一律“TuShare”），未细到接口（如“指数日线”）；需要接口级名称时在 `SOURCE_NAMES` 加精确条目即可。
- “未翻译代号”只认输入里出现过的指标／来源代号与六个阶段代号，大小写敏感；`carried_forward`、`gap:` 这类异常类型码不在本票范围（规格只要求指标、来源、阶段）。
- 已存旧报告不回填标注；旧投影重新生成报告时自然走新提示词与标注。

### 2026-10-18 审查修复（wg-07）

审查 Spec 3：非典型固定句仍写"阶段 III"，按提示词写"第三阶段"的解读会被拒收。固定句改用 `wording.stage_name`，"倾向/当前……阶段"拦截也认"第X阶段"（a18e1cf）。`report-prompt-v0010` 未发布过，不再升版。详见 [../acceptance.md](../acceptance.md)。
