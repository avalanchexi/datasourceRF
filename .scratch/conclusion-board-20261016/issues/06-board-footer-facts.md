# 06: 板底解读行与运行事实行

**What to build:** 结论板底部两行事实。第一行是 AI 解读，按报告状态四分：有 AI 解读写首段首句加"全文"链接；确定性模板写"本次报告为确定性模板，无 AI 解读"并附适配器失败原因；报告任务排队或运行中写"报告生成中"；无报告写"报告尚未生成"并链到 ⑦ 段生成按钮。第二行是目标交易日、模型版本、外部请求数与失败数、检索预算用量、耗时（秒），取产出本投影的运行的持久化健康摘要，缺失写"口径不可用"。

**Blocked by:** 02：顶栏七项身份字段与产出运行摘要接入；04：结论板右栏

**Status:** done

- [x] 解读行四种状态文案与链接正确；报告与当前展示的投影同身份，同投影取最新版本；身份不匹配的旧报告不显示。
- [x] 确定性模板时注明适配器失败原因（取报告记录的适配器尝试结果），不冒充 AI 输出。
- [x] 运行事实行五项来自票 02 传入的健康摘要；摘要缺失时相应项写"口径不可用"，不显示 0。
- [x] 反例：AI 解读、确定性模板、生成中、未生成四例；有摘要与无摘要两例；固定历史投影时解读与摘要都属于该投影。
- [x] 受影响的 Web 切片与两项必跑冒烟通过；修改范围 ruff、mypy 通过。
- [x] 规格：[spec.md](../spec.md) 实现决定"板底事实行"。

## Comments

### 2026-10-16 进展

- 读完：票、规格、run_health 摘要结构、报告适配器尝试记录、首页渲染入口与现有测试；worktree cb-06 基于 conclusion-board 492dd1d。
- 红→绿：解读行四态（AI 首句＋全文、确定性模板＋适配器失败原因、生成中、未生成＋生成按钮链接）6 例通过；ReportSnapshot 新增 adapter_outcomes（报告服务记录的适配器尝试）。
- 红→绿：运行事实行（有摘要、无摘要两种、缺耗时、空库）与固定历史投影 HTTP 用例通过；失败数口径取 run_health.REQUEST_FAILURES（与缺口诊断 request_failed 同一集合）。
- 验证：受影响 Web 全目录＋报告边界＋检索账本 140 例通过（23.9 秒）；ruff、mypy（src 三文件）通过。

### 2026-10-16 实施

**改了什么**

- `cockpit.reading_line`：板底解读行四态。同投影报告取最新版本（沿用前端重建批次按 `projection_set_id` 绑定、取最大 version 的做法），身份不符的报告不显示。AI 解读取首段首句（截至第一个 。！？）加"全文"链接到 `#reading`；`adapter == "deterministic"` 时写"本次报告为确定性模板，无 AI 解读（适配器失败原因：…）"，不显示模板句；报告任务排队/运行中写"报告生成中"（原写"无报告而"，已按审查推翻）；都没有写"报告尚未生成"并链到 `#generate-report-command`（⑦ 段生成按钮）。空库只写"报告尚未生成"，不给链接（按钮此时禁用）。
- `ReportSnapshot.adapter_outcomes`：报告仓库读取时随运行元数据附上已记录的适配器尝试（适配器名、结果），失败原因由此而来；`cockpit.ADAPTER_FAILURES` 把 `cli_process` 与报告校验的结果码译成中文，未知码原样显示；没有尝试记录时写"未记录适配器尝试"，不编造原因。
- `cockpit.run_facts_line`：运行事实行五项全部取票 02 传入的 `ProducerRun.summary`；摘要缺失（无产出运行或旧运行无摘要）时五项都写"口径不可用"；单项缺失只该项写"口径不可用"，从不显示 0。预算格式沿用运行列表"Tavily a/16、Exa b/8、AI c"；耗时与运行页同用 `number`（两位小数）。
- `run_health.REQUEST_FAILURES`：失败数口径与缺口诊断 `request_failed` 共用同一集合（failed、interrupted、timeout、error），缺口诊断改为引用它。
- `report.css` 新增 `.board-fact`，只用现有变量。

**测试与耗时**

- 新增 `tests/web/test_board_footer.py` 12 例：AI 首句（同投影取最新版本、他投影不混入）、确定性模板两例（有/无尝试记录）、报告服务真实记录的失败原因、生成中、未生成、运行事实有摘要/无摘要两种/缺耗时、空库。
- `tests/web/test_cockpit_http.py::test_pinned_projection_does_not_mix_with_a_new_current_pointer` 增补：固定历史投影时解读行与运行事实行都属于该投影（新当前投影的模板报告与未完成运行不混入）。
- 受影响 Web 全目录＋`tests/reports/test_report_boundary.py`＋`tests/integration/test_retrieval_ledger.py`：140 passed，23.9 秒。
- 两项必跑冒烟：2 passed，42.4 秒。
- ruff check / format --check 通过；mypy（src 三文件）通过；测试文件的 mypy 报错为既有（test_cockpit_http 5 处、test_dashboard_contract 5 处，基线同样存在），新文件无报错。

**按推荐实现的领域选择（规格未覆盖）**

- ~~已有同投影报告而又在重新生成时，板底继续显示已有报告，不改成"报告生成中"（⑦ 段同样保留旧报告并提示"完成后自动显示新版本"）。~~ **已按审查推翻**（2026-10-16 集成审查 Spec 3，见 review.md 修复记录）：按规格原句，报告任务排队或运行中板底一律写"报告生成中"，已有旧报告也不例外；⑦ 段仍保留旧报告并提示"完成后自动显示新版本"。
- 失败数只计请求本身失败（failed、interrupted、timeout、error），不计"已应答但无值或被拒收"的结果。
- 运行事实行的目标交易日与模型版本也严格取自摘要，摘要缺失时写"口径不可用"，不回退到投影（顶栏已显示投影的这两项）。

**遗留**

- 浏览器明暗主题与窄屏截图对照留给票 07。
- `/api/v1/reports` 与报告详情接口的快照 JSON 因此多出 `adapter_outcomes` 字段（只增不改）。
