# 集成分支代码审查（2026-10-16）

基线 conclusion-board 638d125，HEAD c7afb8a；两轴各一次 codex exec -s read-only。

## Standards

(a) 硬违反：[test_conclusion_board_noncanonical.py:125](/home/tywin/worktrees/datasourceRF-cl/tests/web/test_conclusion_board_noncanonical.py:125)通过 `html.Strong` 断言加粗，违反 [spec.md:182](/home/tywin/worktrees/datasourceRF-cl/.scratch/cockpit-layout-20261016/spec.md:182)“不断言样式”；应保留文本断言。

(b) 坏味（判断题，均属 Duplicated Code）：

- [cockpit.py:1500](/home/tywin/worktrees/datasourceRF-cl/src/pring_cycle/cockpit.py:1500)、[cockpit.py:2499](/home/tywin/worktrees/datasourceRF-cl/src/pring_cycle/cockpit.py:2499)重复拼后缀去重，未再次查重。只读复现：输入 `X,X-3,X` 产生两个 `overseas-X-3`，可能打开错误抽屉；应统一分配唯一键。
- [cockpit.py:989](/home/tywin/worktrees/datasourceRF-cl/src/pring_cycle/cockpit.py:989)、[cockpit.py:1833](/home/tywin/worktrees/datasourceRF-cl/src/pring_cycle/cockpit.py:1833)分别渲染同源完整缺口清单，建议两个触发器共用一个抽屉。
- [cockpit_operations.py:102](/home/tywin/worktrees/datasourceRF-cl/src/pring_cycle/cockpit_operations.py:102)、[report.css:222](/home/tywin/worktrees/datasourceRF-cl/src/pring_cycle/assets/report.css:222)重复维护七项浅色调色值，改色容易漂移，应集中维护。

阻断：有

## Spec

(a) cockpit.py:619、2241：①/⑥未限量，违反“限高滚动或前 N 条”（spec.md:152）。

(b) cockpit.py:480：删②观察接口列表且丢“目录未收录”状态，未保全“同类观察每行全部字段”（spec.md:157）。

(b) cockpit_operations.py:84、120：新增received映射、单个小来源不合并，偏离“未映射值显示原值、灰色”“请求数 <2 的来源合并”（spec.md:176）。

(c) wording.py:243、cockpit.py:87：成员表压过目录、组名回退免标注，偏离“否则查对照表”“未提供中文名”（spec.md:165）。

(c) cockpit.py:1471、1491：核心待处理也标“非典型组合不判定命题与成熟度”，把非典型限定扩大到所有无正式阶段（spec.md:170）。

阻断：有

## 主 agent 处置

| # | 发现 | 处置 |
|---|---|---|
| S1 | 测试以 `html.Strong` 断言加粗 | 修：改为只断言文本；加粗由票 10 截图证明 |
| S2 | ③/② 抽屉键后缀去重不查重（X、X-3、X 撞键） | 修：统一唯一键分配，加反例 |
| S3 | ① 与 ⑦ 两个同源缺口抽屉 | 修：共用一个抽屉，两个触发器 |
| S4 | 桑基浅色调色在 Python 与 CSS 各一份 | 修：颜色只在 CSS 变量维护，Python 只留单一中性兜底 |
| P1 | ①、⑥ 明细未限量 | 不改：① 明细为数行短句；⑥ 已按 120 交易日窗口限量（规格"默认最近 120 个交易日"） |
| P2 | ② 删"观察接口"列表丢"目录未收录"状态 | 修：行抽屉补该状态；保留删除列表（与卡内同类观察重复） |
| P3 | 新增 received 映射；单个小来源不合并 | 接受：避免英文原码；"其他（1）"不如原名，记入票 09 |
| P4 | 组名回退未标注 | 修：回退到组名时抽屉标"未提供成员中文名"；成员项优先于目录名保留（避免融资两行重名） |
| P5 | 核心待处理也写"非典型组合不判定…" | 修：仅非典型写该句；其他无阶段原因写"无正式阶段，不判定命题与成熟度" |
| 遗留 | tests/integration 确认相关旧首页文案断言 4 例失败（自结论板批次起）；家数"978.00 家"；仓单吨数"2175351.0" | 修 |

## 修复结果（分支 cl-rf，提交 1eb0d17，基于 cockpit-layout 3a86b37）

| # | 结果 |
|---|---|
| S1 | 已修：`test_the_reason_reads_with_the_key_values_beside_it` 只断言 ① 段文本含原因与关键值，删去 `_bold`／`html.Strong` 断言；加粗留给票 10 截图 |
| S2 | 已修：`drawer.unique_key(key, taken)` 取第一个未被占用的 `key-<n>`，④ `confirmation_cards` 与 ②③ `_row_keys` 共用；反例 `test_a_repeated_row_never_takes_the_key_of_another_row`（X、X-3、X 三行三个抽屉各开各值） |
| S3 | 已修：缺口抽屉只渲染一份（键 `drawer-gaps`，标题"全部缺口（N）"，按类别分组），① 数据边界与 ⑦"查看全部"两个触发器指向它；新用例 `test_the_data_boundary_and_section_07_open_the_same_gap_drawer` |
| S4 | 已修：删 `FLOW_COLOURS`，图形初始只带单一中性灰 `FLOW_FALLBACK`，各色族只在 `report.css` 的 `--flow-*` 维护；颜色测试改读 trace meta 的色族；新增"图形只一色"与"每个色族在明暗两套主题都有变量"两例。浏览器 8110 复核明暗两套都由 JS 重绘成功 |
| P1 | 不改，已记入票 07 Comments |
| P2 | 已修：② 行抽屉对 `in_catalog: false` 的成员补"目录状态 当前目录未收录"；新用例 `test_a_member_the_catalog_does_not_list_says_so_in_its_drawer` |
| P3 | 接受，已记入票 09 Comments |
| P4 | 已修：`DisplayName.group` 标记回退到组名；抽屉写"未提供成员中文名"（`wording.NO_MEMBER_NAME`）；成员项优先于目录名不变；新用例 `test_a_row_named_after_its_group_says_the_member_has_no_chinese_name` |
| P5 | 已修：`is_noncanonical(projection)` 判定；非典型写"非典型组合不判定命题与成熟度"，其他无正式阶段写"无正式阶段，不判定命题与成熟度"；新用例 `test_a_drawer_without_a_formal_stage_for_another_reason_does_not_say_noncanonical`；结论板右栏改用同一判定 |
| 遗留·集成断言 | 已修：flock 下确切失败清单为 3 例（另 3 例 `unable to open database file` 系与 web 用例共用 basetemp 被清所致，单独重跑通过）：`test_confirmation_policy.py::test_the_policy_dimension_reaches_the_pages_and_the_report`、`test_confirmation_publish.py::test_the_pages_list_the_dimension_summary_and_the_pmi_reading`、`::test_the_price_and_credit_counts_reach_the_pages_and_the_report`。按新首页结构改写为"维度卡计数＋行读法"（如"物价 支持 1 · 反证 0 · 仅观察 0 · 未确认 2 PPI 支持"），库存页改为"数据 不可用（缺失）""确认关系：未确认（象限仅计一项）"；报告侧断言不动。仓单行原文断言（`test_confirmation_inventory.py`）在当前分支已通过，未改 |
| 遗留·家数 | 已修：`number()` 遇单位 `count` 按整数千分位（"978 家""-222 家"）；既有用例期望随之更新 |
| 遗留·仓单吨数 | 已修：七品种折算吨数合计写"2,175,351 吨 → 2,090,014 吨"；新用例 `test_the_seven_symbol_tonnes_read_as_whole_tonnes_with_thousands_separators` |

**验证**：`tests/web/` 全目录 152 passed（16 s）；`test_confirmation_policy/publish/inventory.py`、`test_czce_warrant_refresh.py` 205 passed（2 m 37 s，flock）；两项必跑冒烟 2 passed（48 s，flock）；改动文件 `ruff check`、`ruff format --check` 通过，源文件 `mypy` 通过（测试文件不在 mypy 配置范围，改动行无新报错）；`node --check dashboard.js` 通过。浏览器自检 8110（`/tmp/pring-ui-real-20261015`，已停）：截图 `/tmp/claude-1000/-mnt-d-cursor-datasourceRF/98152580-dc82-4790-be5a-d146e59f2771/scratchpad/clrf/shots/`。

**观察（未改）**：真实副本 ② 同类观察"近 5 日"列对家数显示百分比变化（如"上涨家数 978 家 -61.89 %"），口径来自投影 `change_5.unit`，不在本次处置范围。
