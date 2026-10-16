# 02: 中文名为主（显示名对照表）

**What to build:** 全站资产与指标第一行写中文名、第二行小号灰色写代号；紧凑位置只写中文名、悬停看代号；抽屉标题两者全写。同一指标的不同成员各有可区分的中文名，"融资买入额"不再被标成"融资余额"。见 [规格](../spec.md) 用户故事 12–17、57，实现决定"显示名模块"，[访谈决定](../decisions.md) 第三轮 16–17。

**Blocked by:** 01

**Status:** done

- [x] 在现有用词映射模块新增显示名解析：输入 metric_id 与成员维度（measure、index、sleeve、aggregate、symbol 等），输出中文名与代号；优先目录 `name_cn`（不等于代号时），其次对照表，最后回退代号并在抽屉标"未提供中文名"
- [x] 对照表按访谈第三轮 17 项全部写入：02 债券 / 股票 / 商品各成员、估值"指数 + 指标"9 行、融资余额与融资买入额、商品分项 7 项（含"纺织（棉花与 PTA 合计）"）、03 全部、GDP 四口径 × 两量、仓单 8 品种、桑基来源名
- [x] 生效位置：③ 卡片与抽屉、② 现有同类观察行、⑤ 仓单、数据链路请求表指标列；④ 的 17 个关键指标与 58 个成员沿用确认规则中文名不变
- [x] 首页与数据链路页渲染入口测试：目录有名 / 对照表命中 / 都无三例；同一指标多成员不同名；融资买入额；回退代号时抽屉标注
- [x] 两项必跑冒烟通过

## Comments

### 2026-10-16 实施

分支 `cl-02`（worktree `/home/tywin/worktrees/datasourceRF-cl-02`），已并入 cockpit-layout 最新（ad2cd3e，含票 08）。

**改了什么**

- `wording.py` 新增显示名模块：`METRIC_NAMES`（登记目录 61 个指标的指标级中文名）、`MEMBER_NAMES`（按成员维度：涨跌家数 5 项、90/250 日新高新低、估值"指数＋指标"9 项、融资余额 / 融资买入额、商品分项 7 项含"纺织（棉花与 PTA 合计）"、GDP 四口径 × 两量 8 项、仓单 8 品种）、`SOURCE_NAMES`（桑基与请求表来源名：official→官方发布、tushare→TuShare、EIA→美国能源信息署、ECB→欧洲央行等）；`display_name(metric_id, dimensions, catalog_name)` 返回中文名、代号、是否有中文名；`source_name(channel)` 供票 09 桑基复用。
- 代号 = metric_id ＋ 命中成员项的维度值（如 `CN_EQ_ADV_DEC · advances`）；未命中成员项时带全部维度值（如 `CN_EQ_CSI300 · 000300.SH`）。
- `cockpit.py`：`row_name / name_cell / name_note` 三个渲染助手。③ 卡片两行（中文名＋小号代号），抽屉标题中文名、副标代号，回退代号时抽屉正文首行"未提供中文名"；② 同类观察名称列、⑤ 仓单表品种列为紧凑单元（只写中文名，悬停 title 看代号）；`dashboard._warrant_line` 写"棉花（CF）"。
- `cockpit_operations.py`：数据链路请求表"来源"写中文来源名（悬停原值），"指标"列逐个写中文名（悬停代号）。
- 顺带：③ `CN_USDCNY_CLOSE_1630` 单位 `scalar` 属前端缺项，`cockpit.METRIC_UNITS` 按（指标, scalar）读作 `cny_per_usd`，卡片、抽屉、走势表均显示"元/美元"，已加断言。

**按推荐实现的选择（规格未细到此，回报主 agent）**

1. 优先级细化为：成员对照项 → 目录 `name_cn`（≠代号）→ 指标级对照项 → 代号。原因：目录无成员层，`CN_MARGIN_BALANCE_SSE_SZSE` 的目录名"沪深两所融资余额与买入额"若压过成员项，两行会重名、买入额仍不可区分。日后目录补齐指标级 `name_cn` 仍自动优先于指标级对照项。
2. ② 同类观察行若对照表与目录都无名，先用投影已有的观察接口中文组名（如"北向资金"），再回退代号；保证新指标不比改前更差。
3. 指标级对照表覆盖登记目录全部 61 个指标（④ 关键指标沿用确认规则已有名，如 七天逆回购利率、制造业 PMI），使数据链路请求表不再满屏代号；④ 段本身不改。
4. 拟定中文名：沪深 300（000300.SH，原标签"中证 300"有误）、美元兑人民币中间价、美元兑人民币 16:30 收盘价、美国 10 / 2 年期国债收益率、美债 10 年减 2 年利差、VIX 波动率指数、费城半导体指数；GDP 成员为"GDP 总量实际季度同比""第一产业名义累计值"等。

**测试与耗时**

- 新增 `tests/web/test_display_names.py` 9 例（首页与数据链路页渲染入口）：对照表命中、目录有名优先、都无时回退代号并抽屉标注、估值与涨跌家数多成员不同名、融资买入额、未映射观察沿用组名、16:30 收盘价单位、仓单中文名、请求表来源与指标中文名。`test_overseas_cards.py` 两例改断言为中文名在前（保护的仍是名单顺序与"其他背景指标"分组）。
- 合并后：`tests/web/*.py` 111 passed（23.8 秒）；两项必跑冒烟 2 passed（63.6 秒，flock）；改动文件 ruff check / format --check / mypy 通过。
- 浏览器自检（8102，隔离副本 `/tmp/pring-ui-real-20261015`，1440 浅色，已停）：③ 10 张卡全为中文名＋代号，16:30 收盘价"6.69 元/美元"；② 40 行同类观察 40 个互不相同的中文名；⑤ 仓单 8 品种中文名、列表"棉花（CF）"；数据链路请求表来源"TuShare / 官方发布"、指标"GDP / 工业企业盈利"等，悬停为代号；`scrollWidth` 1440。截图：`/tmp/claude-1000/-mnt-d-cursor-datasourceRF/98152580-dc82-4790-be5a-d146e59f2771/scratchpad/cl02/`（overseas-1440、assets-1440、drawer-1630-1440、warrants-1440、data-chain-1440），实测值 `shot.json`。

**遗留**

- Worker 侧：16:30 收盘价解析器 `quote_sources.CHINAMONEY_USDCNY_1630` 写 `unit="scalar"`，应为 `cny_per_usd`；本票只在前端映射，Worker 未改。
- GDP 8 项成员名已入表，但 ③ 不显示 GDP；待票 05 在 ④ GDP 抽屉"分产业"小表使用。桑基节点中文来源名 `source_name` 待票 09 使用。
- 代号中带 `universe` 等非区分维度（如 `CN_EQ_AD_RATIO · advance_decline_ratio × point_in_time_traded_a_shares`），只在悬停与小号代号中出现，未裁剪。
- `count`、`multiple`、`ratio` 单位在 ② 仍显示原码（UNITS 缺项，非本票范围），票 04 改 ② 卡片时可一并处理。
