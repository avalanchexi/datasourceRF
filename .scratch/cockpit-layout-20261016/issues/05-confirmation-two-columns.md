# 05: ④ 两列维度卡与非典型读法

**What to build:** 读者在 ④ 段宽屏看到五张维度卡每行两张；每卡头写维度名与计数，卡内每个关键指标一行。非典型组合时每行改写该指标主成员自身读法（最新值与单位、读取期、方向）并标"不计数"；详情在抽屉，GDP 抽屉含原本混在 ③ 的分产业细项。见 [规格](../spec.md) 用户故事 44–51，实现决定"非典型组合读法"。

**Blocked by:** 01, 02

**Status:** done

- [x] 五维度卡宽屏每行两张、窄屏单列；卡头维度名与支持 / 反证 / 仅观察 / 未确认计数（全称）
- [x] 有正式阶段：每行指标名、确认关系、读取期
- [x] 非典型：每行主成员 `value / period / direction`（缺失读 `latest_source`）加"不计数"标签，不显示确认关系；抽屉写"非典型组合不判定命题与成熟度"
- [x] 点指标行抽屉：主辅成员、派生说明、依据与缺口、命题与成熟度
- [x] GDP 抽屉"分产业"小表：总量、第一、第二、第三产业 × 实际季度同比、名义累计值（数据取自投影现有行，中文名用票 02 显示名）
- [x] 首页渲染入口测试：典型与非典型两种行内容；抽屉内容；GDP 分产业 8 格；两项必跑冒烟通过

## Comments

### 2026-10-16 实施

分支 `cl-05`（worktree `/home/tywin/worktrees/datasourceRF-cl-05`）。

**改了什么**
- `cockpit.py`：④ 段原"每维一张表＋原地展开"换成 `confirmation_cards`：五张维度卡（`dimension-grid` 宽屏两列、≤1100px 单列），卡头维度名＋"支持 / 反证 / 仅观察 / 未确认"全称计数（`dimension_counts`），未接入写"尚未接入"；卡内每个关键指标一行抽屉触发器。有正式阶段：指标名、确认关系、"读取期 …"。非典型（`confirmation.applicable` 非 true）：指标名、主成员名（与指标名相同时省略）、主成员 `value＋unit / period / direction`，任一字段缺失时逐字段读 `latest_source`，再加"不计数"标签，不显示确认关系。抽屉 `_indicator_drawer`：非典型时首行"非典型组合不判定命题与成熟度"；"主辅成员"（沿用 `member_readings`，含证据版本链接）；"派生、依据与缺口、命题与成熟度"（沿用 `dashboard._indicator_card`）；GDP 另有"分产业"小表 `gdp_sectors`（GDP 总量 / 第一 / 第二 / 第三产业 × 实际季度同比 / 名义累计值，取投影 `international_context` 中 `CN_GDP` 的 8 行，名称用 `wording` 的 GDP 口径表，单元格带期与证据链接，缺行写"未提供"）。面板统一放在卡片网格之外。
- `assets/report.css`：维度卡、指标行、"不计数"标签样式（插在 ③ 卡片样式之后）。
- 新测试 `tests/web/test_confirmation_cards.py`（6 例，首页渲染入口）：卡头全称计数与未接入、典型行内容、非典型行读法＋不计数（含贷款无来源值、产能利用率单位回退来源、库存象限读象限）、非典型抽屉说明且典型抽屉无此句、抽屉主辅成员 / 派生 / 缺口 / 命题 / 成熟度 / 证据链接、GDP 分产业 8 格与缺格。

**按推荐实现的领域选择（规格未覆盖）**
- 非典型卡头仍列四项全称计数（均为 0），尾部加"不计数 N"，不再写"不适用 N"。
- 库存象限主成员无 `direction`，方向位写象限名（如"主动补库存"）；无 `value` 时按规则读 `latest_source`（产成品存货 73,600.00 亿元）。
- 抽屉内沿用的 `_indicator_card` 在非典型时仍写一行"不适用"作为确认关系，上方已有"非典型组合不判定命题与成熟度"说明。

**测试与耗时**
- 受影响 Web 用例：`tests/web/*.py` 130 passed（合入 cockpit-layout 后复跑 21.8 秒）。
- 两项必跑冒烟（flock）：2 passed（首次 56.6 秒；合入后复跑 84.9 秒，另等锁约 5.5 分钟）。
- 渲染首页的确认集成用例 `test_confirmation_publish / policy / bond_attribution / inventory / cumulative_quarterly`：279 passed、4 failed（7 分 41 秒）；4 例在未改动的 cockpit-layout 代码上同样失败（断言旧首页文案"PPI：支持""政策利率：支持""库存象限：未确认"与仓单行原文），非本票引入，留给集成验收（票 10）处理。
- `ruff check`、`ruff format --check` 通过；`mypy src/pring_cycle/cockpit.py` 无报错（测试文件导入的 `test_dashboard_contract` 有既有报错，与本票无关）。

**浏览器自检**（8105，隔离副本 `/tmp/pring-ui-real-20261015`，10-14 投影，非典型组合）
- ④ 段高度：1440 宽 746px（改前截图约 1459px）；908 宽 1118px（单列）；390 宽 1515px（单列）；三档 `scrollWidth` 等于视口，无横向溢出；明暗两套一致。
- 卡宽：1440 两列各 584px；908 与 390 单列 648 / 366px。
- 17 行均为主成员读法＋"不计数"，如"GDP 实际季度同比 4.30 % 2026-06-30 ↓ 下降 不计数"。
- 点 GDP 行：抽屉宽 520px、地址栏 `#drawer-confirmation-CN_GDP-gdp`、含非典型说明 / 主辅成员 / 分产业表（4.30 %、695,704.00 亿元等 8 格）；Esc 关闭；390 宽抽屉全屏 390px。
- 截图：`/tmp/claude-1000/-mnt-d-cursor-datasourceRF/98152580-dc82-4790-be5a-d146e59f2771/scratchpad/cl05/`（`confirmation-{light,dark}-{1440,908,390}.png`、`drawer-gdp-{light,dark}-1440.png`、`drawer-gdp-sectors-{1440,390}.png`，实测值 `measure.json`）。本票 Web 已停。

**遗留**
- 有正式阶段的典型组合真实投影未在浏览器核对（隔离副本均为非典型），典型行内容由首页渲染入口测试覆盖。
