| 票 | 通过 | 不通过 | 已被取代 | 无法核对 | 建议 |
|---|---:|---:|---:|---:|---|
| conclusion-board／07 | 4 | 0 | 2 | 1 | 需用户看 |
| cockpit-layout／10 | 10 | 0 | 6 | 1 | 需用户看 |
| cockpit-layout／15 | 11 | 0 | 4 | 0 | 可关 done（按后续决定收口） |
| worker-gap-fixes／07 | 5 | 1 | 2 | 3 | 需用户看 |
| 合计（50项） | 30 | 1 | 14 | 5 | 不修改票面或代勾用户确认 |

核对时间：2026-10-20（北京时间，以截图顶栏时间为准）。统计粒度：票面每个框计一项；cockpit 10追加第一轮acceptance的12框，cockpit 15追加第二轮11框，Worker追加8框，分别为7／17／15／11项。“通过”中的历史流程项只表示存档支持该历史事实，源码项会明确标“静态确认”；均不声称本次重新执行测试、重放或部署。组合项保留一个结论，证据栏说明仍有效的子要求和限制。

本次发现1项明确不通过：Worker清单6的目录缺期对账漏两只债券观察指数。其余待用户项主要是原来的视觉签收、修复方案接受与指定10-15重放证据。票15的技术项及后续替代依据齐备，建议可关；这个建议不等于替用户在仓库勾框。

**实际环境与取代口径**

只访问 `http://127.0.0.1:8069/` 同源页面及静态资源；Playwright系统python3、sync_api、无头Chromium；等待domcontentloaded后目标选择器，未用networkidle。主题写浏览器localStorage `pring-cycle-theme` 后reload。未点运行、报告生成、刷新、提交、重试、启停或筛选提交按钮；只做导航、抽屉、锚点和键盘操作。未启动／停止应用服务或Worker，未重装、未改仓库与正式配置。数据库仅以 `file:///home/tywin/.local/share/pring-cycle/pring-cycle.sqlite3?mode=ro` ＋ `PRAGMA query_only=ON` 打开；产物均在当前目录。页面自己的Dash读视图POST仅允许 `/_dash-update-component`，无命令提交。

正式库active_model确为model-v0016，激活时间2026-10-20 07:19:21北京；first_published_business_date为NULL。当前projection-554b0640f5f9d167fb6a，目标日2026-10-19，仍绑定model-v0015、run-153de3060fa2b0ebc424，截止19:11:32北京。cycle_overview无宏观判断块。**实际首页未以宏观判断领衔**：①仍“正式阶段／暂无正式阶段”，④仍“宏观事后确认”，①和⑥注明“该投影生成时尚无宏观判断”。这与任务背景中的新页面描述有差异，按实际记录。

这一兼容行为有明确依据：[宏观规格 Implementation Decisions／前端](/mnt/d/cursor/datasourceRF/.scratch/macro-stage-20261017/spec.md:120)要求“旧投影无宏观字段时①保持现状并提示……，不补算”；[src/pring_cycle/cockpit.py:680](/mnt/d/cursor/datasourceRF/src/pring_cycle/cockpit.py:680)、[src/pring_cycle/cockpit.py:698](/mnt/d/cursor/datasourceRF/src/pring_cycle/cockpit.py:698)按是否存在宏观块走术语和版式分支。因此没有把当前旧投影中的“正式阶段”直接判成新批次回归，也没有伪称测到了v0016标题、宏观区间切换或生效日色带。数据证据见 [db-evidence.json](db-evidence.json)、[datasets-current.json](datasets-current.json)。

**浏览器实测**

| 页面／主题 | 视口宽 | scrollWidth | 页高 | 日值抽屉宽 |
|---|---:|---:|---:|---:|
| home／light-1440 | 1440 | 1440 | 5344 | 520 |
| chain／light-1440 | 1440 | 1440 | 5485 | — |
| home／dark-1440 | 1440 | 1440 | 5344 | 520 |
| chain／dark-1440 | 1440 | 1440 | 5485 | — |
| home／light-908 | 908 | 908 | 8595 | 363.1875 |
| chain／light-908 | 908 | 908 | 6801 | — |
| home／dark-908 | 908 | 908 | 8595 | 363.1875 |
| chain／dark-908 | 908 | 908 | 6801 | — |
| home／light-390 | 390 | 390 | 10488 | 390 |
| chain／light-390 | 390 | 390 | 7143 | — |
| home／dark-390 | 390 | 390 | 10488 | 390 |
| chain／dark-390 | 390 | 390 | 7143 | — |

各段当前高度（px；同宽明暗一致）：

| 宽度 | ① | ② | ③ | ④ | ⑤ | ⑥ | ⑦ |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1440 | 614.09 | 1099.28 | 612.66 | 745.55 | 453.58 | 493.06 | 986.50 |
| 908 | 903.47 | 2889.45 | 953.06 | 1118.39 | 470.62 | 675.73 | 1162.03 |
| 390 | 1270.73 | 3030.67 | 1007.30 | 1515.53 | 814.52 | 781.70 | 1491.00 |

1440明暗：资产卡高840.17px，三卡顶／底差0；图高240px、月刻度2026-05至10、无可见工具栏；同类观察框外高320px，clientHeight318，内容高318／905／387。②下方两卡高140.11px，⑥两栏高376.38px、顶／底差0。908和390按<1000断点上下堆叠；390的③为两列五行。请求表和目录逐项表均外高480、内高478，滚动限制有效。

共检查83个不同抽屉，成功83个。键盘：{'focus_trapped': True, 'focus_return': True}；浏览器后退关闭：True；分享链接直达：True。console error/pageerror 0条；被同源守卫拦截请求0条（详见原始记录）。

| 导航／旧书签 | 目标段 | 段顶距视口（px） |
|---|---|---:|
| `/#conclusion` | conclusion | 135.59 |
| `/#assets` | assets | 137.69 |
| `/#overseas` | overseas | 137.97 |
| `/#confirmation` | confirmation | 137.62 |
| `/#inventory` | inventory | 138.17 |
| `/#history` | history | 137.75 |
| `/#reading` | reading | 137.81 |
| `/core-assets` | assets | 137.69 |
| `/macro` | confirmation | 137.62 |
| `/inventory` | inventory | 138.17 |
| `/stage-history` | history | 137.75 |

完整测量与抽屉文本：[browser-results.json](browser-results.json)；旧投影、悬停文案、各段对齐及表头吸顶补验：[supplement-results.json](supplement-results.json)；截图：[shots/](shots/)；执行脚本：[verify_browser.py](verify_browser.py)、[inspect_db.py](inspect_db.py)。截图为原页面截取，未改DOM/CSS伪造布局。历史改前高度使用存档，当前测量不与不同投影作严格等值比较。

**conclusion-board／07：逐项核对**

原票：[.scratch/conclusion-board-20261016/issues/07-integration-acceptance.md:1](/mnt/d/cursor/datasourceRF/.scratch/conclusion-board-20261016/issues/07-integration-acceptance.md:1)。清单N为该票引用acceptance的对应用户确认框；票N为票面按顺序编号。

| 项 | 原文验收项（简写） | 判定 | 证据／现象 |
|---|---|---|---|
| 票1 | 隔离重装，Web 完整切片＋两项冒烟，不跑全套 | **通过** | [.scratch/conclusion-board-20261016/acceptance.md:17](/mnt/d/cursor/datasourceRF/.scratch/conclusion-board-20261016/acceptance.md:17)记载修复后 Web 110 passed、冒烟 2 passed，未重跑全套。本次仅核对存档，未执行测试或重装。 |
| 票2 | 真实投影明暗／390 截图，与 Claude 方案①并排，记录偏离 | **已被取代** | 原截图与差异已存档于 [.scratch/conclusion-board-20261016/acceptance.md:29](/mnt/d/cursor/datasourceRF/.scratch/conclusion-board-20261016/acceptance.md:29)、该文“与 Claude 方案①段的差异”。当前布局已由 [布局决定3、19、23、24](/mnt/d/cursor/datasourceRF/.scratch/cockpit-layout-20261016/decisions.md:9)（三核心表移②、非典型五格改单行、转折观察只列反向候选）及 [宏观决定10、11](/mnt/d/cursor/datasourceRF/.scratch/macro-stage-20261017/decisions.md:35)取代；不能继续以原九列表／五小格判现页失败。现页证据 [conclusion-light-1440.png](shots/conclusion-light-1440.png)、[conclusion-dark-390.png](shots/conclusion-dark-390.png)。 |
| 票3 | 390 整页无横向溢出；旧书签、#conclusion 定位 | **通过** | 明暗 390 的 scrollWidth=390；四个旧书签与七个锚点均测试，详见下方实测表、browser-results.json。[home-dark-390.png](shots/home-dark-390.png) |
| 票4 | 原生 Codex 两轴审查，有效问题修复留档 | **通过** | [.scratch/conclusion-board-20261016/review.md:3](/mnt/d/cursor/datasourceRF/.scratch/conclusion-board-20261016/review.md:3)列出两轴审查；[.scratch/conclusion-board-20261016/review.md:36](/mnt/d/cursor/datasourceRF/.scratch/conclusion-board-20261016/review.md:36)逐条记录修复与测试；票07自身补审见 [.scratch/conclusion-board-20261016/acceptance.md:82](/mnt/d/cursor/datasourceRF/.scratch/conclusion-board-20261016/acceptance.md:82)附近“审查”节。属存档核对。 |
| 票5 | 前端重建记录追加重排说明；关口 C 不代填 | **通过** | [.scratch/ui-rebuild-20261015/acceptance.md:112](/mnt/d/cursor/datasourceRF/.scratch/ui-rebuild-20261015/acceptance.md:112)已有“01 段与顶栏已按结论板规格重排”，并明确关口 C 仍待用户、未代填。 |
| 票6 | 正式安装／库／调度未切换；未启动 Worker／真实 AI | **已被取代** | 这是旧批次实施边界；后续 [宏观决定15](/mnt/d/cursor/datasourceRF/.scratch/macro-stage-20261017/decisions.md:54)明确授权合并、正式重装及运行；[.scratch/macro-stage-20261017/issues/10-integration-and-activation.md:25](/mnt/d/cursor/datasourceRF/.scratch/macro-stage-20261017/issues/10-integration-and-activation.md:25)记录 10-20 激活。不能把后来正式上线倒判为旧票失败。本次未做任何此类操作。 |
| 票7 | 规格测试决定“浏览器验收”“执行规则” | **无法在浏览器核对** | [.scratch/conclusion-board-20261016/spec.md:107](/mnt/d/cursor/datasourceRF/.scratch/conclusion-board-20261016/spec.md:107)要求“由用户确认，自动检查不代填”。执行规则已有票1存档证据，页面技术项已复核；原 Claude 差异接受与关口 C 的逐项用户签收不能由本次自动验收补造，需用户确认记录。 |

**cockpit-layout／10：逐项核对**

原票：[.scratch/cockpit-layout-20261016/issues/10-integration-acceptance.md:1](/mnt/d/cursor/datasourceRF/.scratch/cockpit-layout-20261016/issues/10-integration-acceptance.md:1)。清单N为该票引用acceptance的对应用户确认框；票N为票面按顺序编号。

| 项 | 原文验收项（简写） | 判定 | 证据／现象 |
|---|---|---|---|
| 票1 | 8067／8068 两份隔离副本以集成代码起站，仅 Web | **已被取代** | 历史起站记录见 [.scratch/cockpit-layout-20261016/acceptance.md:5](/mnt/d/cursor/datasourceRF/.scratch/cockpit-layout-20261016/acceptance.md:5)；当前正式验收入口由 [宏观决定15](/mnt/d/cursor/datasourceRF/.scratch/macro-stage-20261017/decisions.md:54)、[.scratch/frontend-defects-20261019/issues/04-integration-and-release.md:3](/mnt/d/cursor/datasourceRF/.scratch/frontend-defects-20261019/issues/04-integration-and-release.md:3)改为 8069。遵守本次端口限制，未探测旧端口。 |
| 票2 | 明暗×1440／908／390，各段／链路截图，宽度、高度、抽屉和限高 | **通过** | 本次六组首页及链路截图、各段高度与抽屉宽度见实测表及 browser-results.json；历史改前→改后值见 [.scratch/cockpit-layout-20261016/acceptance.md:28](/mnt/d/cursor/datasourceRF/.scratch/cockpit-layout-20261016/acceptance.md:28)。当前数据日期不同，不伪造同投影改前对照。 |
| 票3 | 抽屉、Esc、后退、分享、键盘；旧书签、空库可读 | **通过** | 83 个抽屉逐个开合；另测 Enter、Tab/Shift+Tab 焦点约束、Esc 返回焦点、后退和直达抽屉链接。锚点见实测表。空库只能静态确认：[tests/web/test_report_board.py:159](/mnt/d/cursor/datasourceRF/tests/web/test_report_board.py:159)、[src/pring_cycle/cockpit.py:1879](/mnt/d/cursor/datasourceRF/src/pring_cycle/cockpit.py:1879)；未起空库站、未执行测试。 |
| 票4 | 完整 Web、冒烟、合入前全套，结果如实记录 | **通过** | [.scratch/cockpit-layout-20261016/acceptance.md:13](/mnt/d/cursor/datasourceRF/.scratch/cockpit-layout-20261016/acceptance.md:13)：Web 152、冒烟2；全套1 failed/2676 passed，过时断言已修并复跑69，未声称该轮全套全绿；后续票15全套2694 passed，见 [.scratch/cockpit-layout-20261016/acceptance.md:145](/mnt/d/cursor/datasourceRF/.scratch/cockpit-layout-20261016/acceptance.md:145)。历史记录核对。 |
| 票5 | acceptance.md、用户逐段清单、不代填、ready-for-human | **通过** | [.scratch/cockpit-layout-20261016/acceptance.md:104](/mnt/d/cursor/datasourceRF/.scratch/cockpit-layout-20261016/acceptance.md:104)有12项待用户清单；原票 Status 为 ready-for-human，本次未改票。 |
| 清单1 | ① 只差一项三行、五维一行、加粗、转折观察和②链接 | **已被取代** | [宏观决定10、11、21](/mnt/d/cursor/datasourceRF/.scratch/macro-stage-20261017/decisions.md:35)将①改为宏观主结论、五维、信号及价格验证抽屉。当前 v0015 兼容页仍具旧清单各项，见 [conclusion-light-1440.png](shots/conclusion-light-1440.png)；旧投影保持现状依据 [.scratch/macro-stage-20261017/spec.md:120](/mnt/d/cursor/datasourceRF/.scratch/macro-stage-20261017/spec.md:120)。 |
| 清单2 | ② 三列卡、160px 图无工具栏、四列同类观察、完整抽屉 | **已被取代** | [.scratch/frontend-defects-20261019/issues/01-asset-chart-height-ticks.md:3](/mnt/d/cursor/datasourceRF/.scratch/frontend-defects-20261019/issues/01-asset-chart-height-ticks.md:3)明确160→240px、月刻度；其余仍通过：图高240、可见工具栏0、观察框320、三卡字段完整，[assets-light-1440.png](shots/assets-light-1440.png)，83个抽屉中相关项全开合。 |
| 清单3 | ③ 十项卡，中债030不在此段，抽屉字段与来源 | **通过** | 3汇率＋3美债＋VIX＋SOX＋Brent＋WTI，共10卡；中债030仅在②；十个卡片抽屉均打开，含值／统计期／来源。[overseas-light-1440.png](shots/overseas-light-1440.png)、browser-results.json 的 drawer-overseas-*。 |
| 清单4 | ④ 两列维度卡，非典型自身读法／不计数，含GDP分产业抽屉 | **已被取代** | [宏观决定11](/mnt/d/cursor/datasourceRF/.scratch/macro-stage-20261017/decisions.md:36)将④改“宏观判断依据”五卡，确认度移价格验证抽屉。v0015 兼容页仍显示原五维17项与GDP分产业；[confirmation-light-1440.png](shots/confirmation-light-1440.png)、[drawer-66-light-1440.png](shots/drawer-66-light-1440.png)。 |
| 清单5 | ⑤ 象限卡＋三线小卡、仓单摘要与抽屉 | **通过** | 主动补库存；统计期2026-08-31；需求／生产／库存三卡，仓单摘要8品种、最新10-19，抽屉可开。[inventory-light-1440.png](shots/inventory-light-1440.png)及 browser-results.json 的 inventory 抽屉记录。 |
| 清单6 | ⑥ 色带＋区间、逐日／更正、等价表格抽屉 | **通过** | 当前四行色带、4/67/49日三区间；区间抽屉有逐日与更正，等价表格可开。[history-light-1440.png](shots/history-light-1440.png)、[drawer-78-light-1440.png](shots/drawer-78-light-1440.png)。宏观行尚无生效数据，未臆造；无区间切换触发器。 |
| 清单7 | ⑦ 完整度两行、缺口前5、摘要、报告／日历抽屉 | **通过** | 两口径表、总8条前5条、AI摘要、报告与发布日历抽屉均在；[reading-light-1440.png](shots/reading-light-1440.png)、[drawer-82-light-1440.png](shots/drawer-82-light-1440.png)。本项核布局；完整度与缺口对账另在WG清单6判不通过，不能据此行推断数据一致。 |
| 清单8 | 数据链路：桑基分色中文、旧投影空态、请求表限高 | **通过** | 当前桑基176次请求、中文标签及分色；请求表外高480px、内高478、内容9119（1440）。旧10-15无健康摘要的兼容分支由旧投影导航补验；[chain-light-1440.png](shots/chain-light-1440.png)、补验记录 supplement-results.json。 |
| 清单9 | 抽屉宽度、Esc、后退、分享、键盘 | **通过** | 1440／908／390 的日值抽屉宽520／约363／390；83个开合通过，焦点／后退／分享结果见 browser-results.json。[daily-drawer-dark-390.png](shots/daily-drawer-dark-390.png) |
| 清单10 | 家数近5日及发现1—5如何处理 | **已被取代** | [布局决定25—28](/mnt/d/cursor/datasourceRF/.scratch/cockpit-layout-20261016/decisions.md:53)已决定家数差、原因中文、空库新卡、桑基“其他N个来源”、逐项表480px、③窄屏两列；由票11—14实施，现页实测见票15。 |
| 清单11 | 关口C：前端重建／结论板用户逐段验收以本版为准 | **无法在浏览器核对** | [.scratch/cockpit-layout-20261016/acceptance.md:118](/mnt/d/cursor/datasourceRF/.scratch/cockpit-layout-20261016/acceptance.md:118)仍是用户确认框。后续上线授权可证明部署获准，不能等同这项逐段视觉签收；需用户确认是否以本报告取代旧逐段签收。 |
| 清单12 | 与conclusion-board一起并入main，由用户决定 | **已被取代** | [宏观决定15](/mnt/d/cursor/datasourceRF/.scratch/macro-stage-20261017/decisions.md:54)已明确依次合并 conclusion-board、cockpit-layout、worker-gaps 并上线；[.scratch/golive-20261019/progress.md:6](/mnt/d/cursor/datasourceRF/.scratch/golive-20261019/progress.md:6)记录正式重装。原“待决定”已失效。 |

**cockpit-layout／15：逐项核对**

原票：[.scratch/cockpit-layout-20261016/issues/15-adjust-integration-acceptance.md:1](/mnt/d/cursor/datasourceRF/.scratch/cockpit-layout-20261016/issues/15-adjust-integration-acceptance.md:1)。清单N为该票引用acceptance的对应用户确认框；票N为票面按顺序编号。

| 项 | 原文验收项（简写） | 判定 | 证据／现象 |
|---|---|---|---|
| 票1 | 全套通过或逐条处理失败；两项冒烟通过 | **通过** | [.scratch/cockpit-layout-20261016/acceptance.md:145](/mnt/d/cursor/datasourceRF/.scratch/cockpit-layout-20261016/acceptance.md:145)记载2694 passed、冒烟2 passed。另如实记磁盘保护脚本权限失败，不能写成当轮保护已生效；本次不运行测试。 |
| 票2 | Codex截图与数值入记录，主agent抽看 | **通过** | [.scratch/cockpit-layout-20261016/acceptance.md:143](/mnt/d/cursor/datasourceRF/.scratch/cockpit-layout-20261016/acceptance.md:143)记录105张截图及数值；[.scratch/cockpit-layout-20261016/issues/15-adjust-integration-acceptance.md:32](/mnt/d/cursor/datasourceRF/.scratch/cockpit-layout-20261016/issues/15-adjust-integration-acceptance.md:32)附近“2026-10-18主agent核验”写明抽看三张关键图。现测补充在本目录。 |
| 票3 | 8067／8068换新代码并可访问 | **已被取代** | 历史换站记录 [.scratch/cockpit-layout-20261016/acceptance.md:142](/mnt/d/cursor/datasourceRF/.scratch/cockpit-layout-20261016/acceptance.md:142)保留；当前正式入口已由 [宏观决定15](/mnt/d/cursor/datasourceRF/.scratch/macro-stage-20261017/decisions.md:54)和 [.scratch/frontend-defects-20261019/issues/04-integration-and-release.md:3](/mnt/d/cursor/datasourceRF/.scratch/frontend-defects-20261019/issues/04-integration-and-release.md:3)取代为8069。本次不探测旧端口。 |
| 票4 | acceptance有本轮逐段清单，等用户勾选 | **通过** | [.scratch/cockpit-layout-20261016/acceptance.md:185](/mnt/d/cursor/datasourceRF/.scratch/cockpit-layout-20261016/acceptance.md:185)有11项待确认清单，原框未代填。 |
| 清单1 | ② 1440三卡等高，各段对齐，观察框320，长名省略／悬停 | **通过** | 三卡高840.17px、顶底差0；图、观察框顶边差0；观察框外高320、client318、scrollHeight318/905/387。长名省略号与title全名／代号见补验；[assets-light-1440.png](shots/assets-light-1440.png)。 |
| 清单2 | ② 一致性／债券归因并排等高，无英文小标题，明细抽屉 | **通过** | 两卡高140.11px，顶底对齐，债券归因中文摘要、明细可开；窄屏堆叠。[assets-dark-1440.png](shots/assets-dark-1440.png) |
| 清单3 | 908堆叠与“908底边齐平”矛盾，保持堆叠或降低断点 | **已被取代** | 后续 [.scratch/frontend-defects-20261019/issues/01-asset-chart-height-ticks.md:3](/mnt/d/cursor/datasourceRF/.scratch/frontend-defects-20261019/issues/01-asset-chart-height-ticks.md:3)明确“908／390宽下照常堆叠”；[.scratch/cockpit-layout-20261016/spec-adjust-20261017.md:23](/mnt/d/cursor/datasourceRF/.scratch/cockpit-layout-20261016/spec-adjust-20261017.md:23)故事7本已要求<1000堆叠。现908确为纵向排列，不再把不同纵坐标的卡底边不齐判失败。 |
| 清单4 | ⑥ 宽屏左右两栏、中文阶段名单写；10-15左侧空态 | **通过** | 1440两栏宽700.80/467.20、高376.38、顶底差0；主列表仅“第三阶段”，无重复Stage III。旧10-15无display，补验显示“旧投影未提供对齐的交易日色带”。[history-light-1440.png](shots/history-light-1440.png)、[old1015-history-light-1440.png](shots/old1015-history-light-1440.png)。 |
| 清单5 | ⑥ 非典型日写“非典型组合，暂无正式阶段” | **已被取代** | [宏观决定2](/mnt/d/cursor/datasourceRF/.scratch/macro-stage-20261017/decisions.md:8)及决定61将新宏观页面术语统一“价格阶段”。当前v0015兼容页仍按原文显示，并非宏观生效后回归；兼容依据 [.scratch/macro-stage-20261017/spec.md:120](/mnt/d/cursor/datasourceRF/.scratch/macro-stage-20261017/spec.md:120)、[src/pring_cycle/cockpit.py:680](/mnt/d/cursor/datasourceRF/src/pring_cycle/cockpit.py:680)。 |
| 清单6 | ⑦ 中文原因／名称、补缺和时效说明、旧统计提示、非典型句 | **通过** | 当前“GDP前后版本不可比”“未配置额外网页检索补缺”、目标日／时效句均可见；当前AI分支有阶段变化句，旧统计提示在10-15导航补验。模板分支静态实现 [src/pring_cycle/cockpit.py:1407](/mnt/d/cursor/datasourceRF/src/pring_cycle/cockpit.py:1407)附近 report_summary 与 [src/pring_cycle/wording.py:99](/mnt/d/cursor/datasourceRF/src/pring_cycle/wording.py:99)。[reading-light-1440.png](shots/reading-light-1440.png)。贷款缺成员抽屉仍有英文维度枚举，列为附注，未混同原因码。 |
| 清单7 | 家数近5日用家数差；近120日解释点列不足 | **通过** | 上涨家数2274，近5日+1108家；下降3129/-1196；90日新高-77、新低-223；250日新高-24、新低-98家。上涨抽屉近120日明确“点列只含120个交易日，无法算120日家数差”，见browser-results.json抽屉8、[上涨家数抽屉截图](shots/advances-drawer-light-1440.png)。 |
| 清单8 | 空库④⑤新卡片空态 | **通过** | 静态确认：[tests/web/test_report_board.py:159](/mnt/d/cursor/datasourceRF/tests/web/test_report_board.py:159)直接以dashboard_page("/", None, (), ())断言政策／信用／过热／物价／库存及库存三线各“等待首次完整运行”。[src/pring_cycle/cockpit.py:1879](/mnt/d/cursor/datasourceRF/src/pring_cycle/cockpit.py:1879)定义空态。未建库、未起空库站；此通过只基于源码／现有测试用例阅读。 |
| 清单9 | 桑基“其他5个来源·5”；逐项表480内滚 | **通过** | 本次真实请求构成是“其他6个来源·6”，N为数据值，格式符合；请求表、逐项表外高480，内高478且scrollHeight更大，补验检查表头吸顶。[chain-light-1440.png](shots/chain-light-1440.png)。 |
| 清单10 | 390宽③每行两张 | **通过** | 十张卡为两列五行，见 [overseas-light-390.png](shots/overseas-light-390.png)、[overseas-dark-390.png](shots/overseas-dark-390.png)及browser-results.json各卡x/y坐标。 |
| 清单11 | 与conclusion-board一起并入main（决定30） | **已被取代** | [宏观决定15](/mnt/d/cursor/datasourceRF/.scratch/macro-stage-20261017/decisions.md:54)已覆盖并授权合并上线；[.scratch/golive-20261019/progress.md:6](/mnt/d/cursor/datasourceRF/.scratch/golive-20261019/progress.md:6)已有正式重装记录。 |

**worker-gap-fixes／07：逐项核对**

原票：[.scratch/worker-gap-fixes-20261017/issues/07-integration-acceptance.md:1](/mnt/d/cursor/datasourceRF/.scratch/worker-gap-fixes-20261017/issues/07-integration-acceptance.md:1)。清单N为该票引用acceptance的对应用户确认框；票N为票面按顺序编号。

| 项 | 原文验收项（简写） | 判定 | 证据／现象 |
|---|---|---|---|
| 票1 | 全套通过或失败处理 | **通过** | [.scratch/worker-gap-fixes-20261017/acceptance.md:25](/mnt/d/cursor/datasourceRF/.scratch/worker-gap-fixes-20261017/acceptance.md:25)历史记录：全套2729 passed（84da04b）；之后社融命名变更另205 passed；未把后者说成同提交全套。本次不重跑。 |
| 票2 | 隔离重放结果与截图写入acceptance | **通过** | [.scratch/worker-gap-fixes-20261017/acceptance.md:33](/mnt/d/cursor/datasourceRF/.scratch/worker-gap-fixes-20261017/acceptance.md:33)记录离线重放run-38581e2f212fe73f6272、投影projection-4d8a569342b0d87c598c、168请求中164原件应答/4离线及逐项截图。本次只核记录，未重放。 |
| 票3 | 用户清单待勾选；正式dev-venv未动 | **已被取代** | 清单保留未改；“尚不重装正式环境”的边界已由 [宏观决定15](/mnt/d/cursor/datasourceRF/.scratch/macro-stage-20261017/decisions.md:54)明确授权取代，并已上线。不能把正式重装当作本轮验收违规。 |
| 清单1 | 审查修复处理方式可接受，尤其Spec1归组与Spec3不升契约 | **无法在浏览器核对** | [.scratch/worker-gap-fixes-20261017/acceptance.md:9](/mnt/d/cursor/datasourceRF/.scratch/worker-gap-fixes-20261017/acceptance.md:9)记录实现与理由；其可执行行为有 [tests/integration/test_awaiting_release_group.py:130](/mnt/d/cursor/datasourceRF/tests/integration/test_awaiting_release_group.py:130)等用例，但“处理方式可接受”是用户判断，需该项确认记录，不能凭程序判通过。 |
| 清单2 | ⑦ 中间价10-15已持有，不再列落后一期 | **无法在浏览器核对** | 当前10-19中间价为6.7208（卡片6.72），不在缺口；正式库10-15原旧投影未回填，source_claim按指标＋period_end=2026-10-15查询为0行。原隔离重放10-15=6.7253仅见存档，未访问它。实现用例 [tests/integration/test_central_parity_full_run.py:176](/mnt/d/cursor/datasourceRF/tests/integration/test_central_parity_full_run.py:176)支持修复；要验证该日期的重放事实仍需原隔离投影／日志，不能以10-19替代10-15通过。详见db-evidence.json fx_1015。 |
| 清单3 | 社融明确已取得／仍缺成员，分项长行可接受 | **无法在浏览器核对** | 当前9月总量3个成员、分项24个成员在coverage均complete，无社融缺口；9月存量同比7.1%已入正式库。部分缺成员中文渲染静态用例 [tests/web/test_reading_release_members.py:19](/mnt/d/cursor/datasourceRF/tests/web/test_reading_release_members.py:19)与[tests/web/test_reading_release_members.py:46](/mnt/d/cursor/datasourceRF/tests/web/test_reading_release_members.py:46)存在。现页已无当时8已取/16缺失长行，无法判断其长度是否被用户接受；需原截图用户裁定或另行取消该审美待办。 |
| 清单4 | EIA Brent／WTI等待发布，标下次日期和依据，不计缺失 | **通过** | 全部缺口抽屉“等待发布(3)”含EIA两项；目标期2026-10-19，下次2026-10-21，依据“来源原件写明”；catalog两个对应period均release_gate=awaiting_release，计门禁不计missing。[drawer-00-light-1440.png](shots/drawer-00-light-1440.png)、coverage-check.json。 |
| 清单5 | 仓单历史缺期首页摘要、抽屉明细 | **通过** | 首页“历史缺期2期共缺6个成员”；抽屉07-21缺铜/螺纹钢/天然橡胶/原油/纸浆，09-09缺聚丙烯，与投影一致。[reading-light-1440.png](shots/reading-light-1440.png)、[drawer-00-light-1440.png](shots/drawer-00-light-1440.png)。 |
| 清单6 | 两口径“其他缺失”与缺口条目对得上 | **不通过** | 模型口径2期可对上（贷款2025-09、GDP 2026-Q3）；目录口径7期中，两只债券观察指数 CN_BOND_FULL_PRICE_CNY030、CN_BOND_10Y_930916 的2026-10-19缺期在coverage为missing，却未在全部8条缺口中列出。详细对账见下文。[reading-light-1440.png](shots/reading-light-1440.png)、[drawer-00-light-1440.png](shots/drawer-00-light-1440.png)、coverage-check.json。 |
| 清单7 | AI正文有原始代号仍保存，并标含未翻译代号 | **通过** | 静态确认：[src/pring_cycle/reports.py:1340](/mnt/d/cursor/datasourceRF/src/pring_cycle/reports.py:1340)成功分支加untranslated_codes后以completed保存；[src/pring_cycle/dashboard.py:2329](/mnt/d/cursor/datasourceRF/src/pring_cycle/dashboard.py:2329)渲染标注；[tests/reports/test_report_boundary.py:638](/mnt/d/cursor/datasourceRF/tests/reports/test_report_boundary.py:638)用例断言保存与标记。当前报告未命中代号条件；未生成新报告、未调用AI，此通过不是当前库反例实跑。 |
| 清单8 | 同意后正式重装，并在首轮确认9月社融存量同比 | **已被取代** | 后续 [宏观决定15](/mnt/d/cursor/datasourceRF/.scratch/macro-stage-20261017/decisions.md:54)已授权正式重装／10-19运行；[.scratch/golive-20261019/progress.md:6](/mnt/d/cursor/datasourceRF/.scratch/golive-20261019/progress.md:6)记录实施。正式库当前投影已使用9月存量同比7.1%，来源中国人民银行，④可见；db-evidence.json sf_september、datasets-current.json。原“等待同意”不再成立。 |

**不通过项详情：WG清单6，目录口径缺期与缺口清单不一致**

模型口径：应有1015＝已持有1013＋其他缺失2；2期分别为贷款结构2025-09、GDP 2026-Q3，全部缺口清单都能找到。

目录口径：应有3065＝已持有3055＋门禁／等待发布3＋其他缺失7。等待发布3期是融资10-19、EIA Brent 10-19、EIA WTI 10-19，归组正确。7个其他缺失如下：

| 指标／期 | coverage状态 | 全部缺口抽屉是否列出 |
|---|---|---|
| 中债030全价，2026-10-19 | missing | **未列出** |
| 10年国债价格指数930916，2026-10-19 | missing | **未列出** |
| 期货注册仓单，2026-07-21 | missing | 已列出，5成员 |
| 期货注册仓单，2026-09-09 | missing | 已列出，1成员 |
| 贷款结构，2025-09 | missing | 已列出，9成员 |
| GDP，2026-Q3 | missing | 已列出，3个产业实际同比 |
| 美元兑人民币16:30收盘，2026-10-16 | missing | 已列出 |

全部缺口的“8条”按指标/归组计数，不应直接和“7期”相减；本结论是按**指标＋期**逐个比对得出。信用脉冲另为派生失败，也不能补上漏列的两只债券指数。原始查询来自analytical_dataset：macro.coverage.catalog.periods与cycle_overview.gap_list，见 [coverage-check.json](coverage-check.json)，页面见 [缺口抽屉](shots/drawer-00-light-1440.png)。

后续 [.scratch/golive-leftovers-20261019/issues/04-targeted-index-scope.md:3](/mnt/d/cursor/datasourceRF/.scratch/golive-leftovers-20261019/issues/04-targeted-index-scope.md:3)修的是这两只指数补取时请求／校验／入库范围不一致；它没有决定“允许coverage缺失不列缺口”。新代码修复不会回填已发布10-19投影，所以现页不满足此验收项，仍判不通过；本次没有重新运行来判断后续数据是否已经修复。

**附注与证据边界**

贷款历史缺成员抽屉还显示 `enterprise、ytd_increment、long_term` 等成员枚举；这是当前实测可读性遗留，不是本轮确认的“原始原因码未翻译”，故没有重复计入票15清单6不通过。⑥区间抽屉中的Stage III／projection ID等技术标识与主列表“阶段名只写一次中文”分开判断。

主脚本在已完成六组页面、83个抽屉与11个导航后，对10-15旧投影误等了不存在的价格图，末尾出现选择器超时；这是验收脚本的等待条件问题。已由supplement_browser.py改等旧投影文字并完整补验首页／阶段史／链路空态，截图和结果均落盘；主脚本等待条件也已修正，但未重复整轮运行。浏览器console/pageerror计数与该脚本异常分开报告。

未执行任何pytest、完整运行、报告生成、隔离重放、环境切换或空库起站。测试数字均为所链接历史验收记录；静态阅读的测试表示代码中已有对应断言，不表示本次运行通过。10-15中间价及社融长行的当前浏览器证据不足已明确列为无法核对，不用10-19的数据冒充它们。
