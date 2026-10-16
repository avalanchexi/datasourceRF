# 09: 桑基图与请求表

**What to build:** 读者在数据链路页看到清晰的桑基图：来源 → 环节 → 结果三列分色，连线按结果四色（成功绿、候选琥珀、未找到 / 未完成灰、失败红）、明暗主题都清晰；节点标签中文并带请求数，小来源合并为"其他（N）"，悬停看数与占比；请求表限高滚动、指标列写中文名。见 [规格](../spec.md) 用户故事 69–75，实现决定"桑基图""数据链路请求表"。

**Blocked by:** 02

**Status:** done

- [x] 节点标签 = 中文名 · 请求数，去掉"来源:"等前缀；来源名用票 02 显示名
- [x] 结果中文与四色归类集中一处：绿 accepted / verified / validated；琥珀 candidate_source；灰 not_found / started / reserved / unknown_completion / completed；红 failed / interrupted / timeout / error / rejected；未映射值显示原值、归灰
- [x] 节点按列分色；连线半透明、颜色取主题变量；高约 420px；请求数 <2 的来源合并"其他（N）"；悬停显示请求数与占比
- [x] 请求表限高约 480px 内滚；指标列显示名
- [x] 数据链路页渲染入口测试：中文标签与计数、"其他（N）"合并、四色归类、未映射值；既有数据链路 HTTP 轮询用例通过；两项必跑冒烟通过

## Comments

### 2026-10-16 实施

**改了什么**（分支 `cl-09`）：
- `cockpit_operations.py`：新增 `FLOW_RESULTS` / `flow_result()`——结果中文与四色归类的唯一映射（成功 / 候选 / 中性 / 失败），未映射值返回原值、归灰；请求表"结果"列改用同一映射。新增 `flow_sankey()`：由请求直接构图（不改 `run_health.filtered_flow`，其 JSON 仍供 API 使用），节点 = 显示名 · 请求数，列内按请求数降序、"其他"殿后；连线按（端点, 结果）拆分，各自取结果色；节点与连线悬停写"N 次请求 · 占比 x.x%"，"其他"节点悬停列出被并入的来源名。高 420px，边距收紧。原 `flow_node_label` 删除（无其他调用方）。请求表外包 `request-table` 容器。
- `assets/report.css`：`--flow-*` 七个主题变量（明 / 暗各一套）；请求表 `max-height: 480px` 内滚、表头吸顶；桑基节点文字改用 `--ink-body`、去白色描边。
- `assets/dashboard.js`：`paintFlowSankeys()` 依主题读 `--flow-*`，按 trace `meta` 记录的列与色族 `Plotly.restyle` 重绘；页面变化与切换主题时触发，颜色一致即跳过（不循环）。图本身带明色兜底色。
- 新测试 `tests/web/test_data_chain_sankey.py`（6 例，测试缝 `data_chain`）：中文标签与计数、"其他（N）"合并及其连线、单个小来源保留原名、14 个已知结果＋未映射值四色归类（按色相判定，不比对色值）、悬停数与占比、请求表结果中文与指标显示名。

**按推荐实现的领域选择**（规格未写明）：
1. "其他（N）"的 N = 被并入的来源个数，标签后仍带" · 请求数"（如"其他（5） · 5"）；只有 1 个小来源时不合并、保留原名（并成"其他（1）"反而丢信息）。
2. `received`（直连取数已接收、未校验）不在决定 22 的列表里，补为"已接收"、归灰（未完成类），避免原有中文退回原值。
3. 占比分母 = 当前筛选下的真实请求总数；源→环节连线也按结果拆色，故同一对节点间可能有多条不同色的连线。

**测试与耗时**（合入 cockpit-layout 509d4b6 后）：
- 受影响 Web：`test_data_chain_sankey`、`test_display_names`、`test_dashboard_contract`、`test_projection_api`、`test_cockpit_http::test_live_chain_refreshes_requests_without_a_run_step_change` 共 42 passed（10.9s）；`test_cockpit_http.py` 全文件 12 passed（18.7s）。
- 两项必跑冒烟（flock）：2 passed，55.8s（另等锁约 5 分钟）。
- `ruff check`、`ruff format --check` 通过；`mypy src/pring_cycle/cockpit_operations.py` 通过（新测试文件经 import `test_dashboard_contract` 带出的 5 个旧类型错误为既有，未改）；`node --check dashboard.js` 通过。

**浏览器自检**（8109，隔离副本 `/tmp/pring-ui-real-20261015`，1440 宽，已停）：138 次请求，节点"TuShare · 81 / 官方发布 · 50 / 美国能源信息署 · 2 / 其他（5） · 5 / 背景指标取数 · 73 / 补缺 · 54 / … / 已接纳 · 76 / 候选来源 · 47 / 校验通过 · 8 / 已验证 · 7"；图高 420px；请求表可视高 480px（内容 6107px、138 行）；明色连线 rgba(22,131,77,.4) / rgba(209,138,22,.45)，暗色重绘为 rgba(75,212,155,.45) / rgba(242,173,70,.5)，页内切换主题同样生效；悬停示例"美国能源信息署 · 2 → 背景指标取数 · 73 / 已接纳 · 2 次请求 · 占比 1.4%"。截图：`/tmp/claude-1000/-mnt-d-cursor-datasourceRF/98152580-dc82-4790-be5a-d146e59f2771/scratchpad/cl09/`（`sankey-light.png`、`sankey-dark.png`、`sankey-hover-*.png`、`page-*.png`）。

**遗留**：此投影无失败、未找到类请求，红灰两色只经测试覆盖、未在真实数据上目视；Python 侧 `FLOW_COLOURS` 兜底色与 CSS 明色变量重复一份（无 JS 时仍可读）。

### 2026-10-16 审查处置（P3 接受；S4 已修）

- P3（新增 `received` 映射、单个小来源不合并）：主 agent 接受，不改。`received` 映射为"已接收"，避免页面出现英文原码；只有一个小来源时"其他（1）"不如直接写来源名，故仅两个及以上小来源才合并。
- S4（浅色调色在 Python 与 CSS 各一份）：已在审查修复分支 cl-rf 修掉。`FLOW_COLOURS` 删除，图形初始只带单一中性灰 `FLOW_FALLBACK`，各色族颜色只在 `report.css` 的 `--flow-*` 变量维护，由 `dashboard.js` 按 trace meta 重绘；本票遗留"Python 兜底色与 CSS 明色重复"随之消除。浏览器复核（8110，`/tmp/pring-ui-real-20261015`）：明色连线 rgba(22,131,77,.4)/rgba(209,138,22,.45)、节点 #3d6d9b/#7b5ea7/#176a66；暗色 rgba(75,212,155,.45)/rgba(242,173,70,.5)、节点 #4b97ff/#b78af5/#5ce1ed。
