1. **结论：复核完成，但不能判为全部通过（DONE_WITH_CONCERNS）。** macro-followups 的宏观区间展示、债券归因说明、启动壳、新完整度表头及副标题均已生效；新报告确为 **AI 解读 · codex_cli**。仍有一处普通正文残留“正式阶段”：报告详情第三节“价格验证与偏离”写“正式阶段为空”。它不属于 JSON 原文例外。旧投影“滞回状态未记录”和“其他缺失 4”均符合不回填约定，不计作本次回归。四组视口与主题均无整页或所测抽屉横向溢出、无应用控制台错误；手机⑦表格有可滚动的内部横向溢出，详见第 8 条。

   核对时间：2026-10-20 15:55 起，报告整理于 16:03:55（北京时间）。浏览器入口仅为 `http://127.0.0.1:8069/`，资源与只读渲染回调均限同源。身份为目标日 **2026-10-19**、`model-v0016`、投影 `projection-59421326f99c005d1801`、运行 `run-3ebbe323c86a1eff93ca`；分析截止 **2026-10-20 09:55:23 北京时间**。本次没有生成报告或发布投影。

2. **报告区与①解读提示：通过。** 报告版本为 **`report-7e4ac01e3e8d15331f6e`**。⑦显示“AI 解读 · codex_cli”；报告详情显示“确定性输出：已生成”“AI解释：已生成”“解读来源：AI 解读 · codex_cli”。证据核查状态仍是“结构与结论已校验，语义待核查”，不能据此声称语义核查已完成。①提示原文为“解读：宏观判断为第三阶段，把握程度为倾向。 全文”，不再显示“确定性模板”。

   正文首节标题：**“宏观判断与五维依据”**。首节正文完整原文：

   > 宏观判断为第三阶段，把握程度为倾向。依据报告输入的确定性规则，五维均已知，政策中性、增长上行和主动补库存与第三阶段吻合，信用下行、物价上行不吻合；第三阶段、第四阶段、第五阶段各得3分，规则选取离上次确认第三阶段最近者，因此并非明确结论，也未退回价格组合推断，本次没有滞回保持。政策中性反映观察窗口内没有利率或准备金率调整，流动性投放增加及DR007下行不参与政策维投票；信用由社融与M1/M2下行形成，贷款内部存在分化；增长由PMI、工业增加值和GDP上行，与产能利用率及工业企业盈利下行共同形成，PMI和盈利内部亦有分化；物价由PPI、CPI及PMI价格同向上行形成。库存结论保持主动补库存，需求、生产及名义库存主线均上行，但PMI产成品库存下行，辅助成员分化。库存采用的统计期落后于多数月度指标，工业企业盈利亦有发布滞后；GDP和库存象限的来源字段为空，不补填来源。宏观维度吻合不等于确认度支持：本次确认度不适用，全部关键指标均记为不适用，各维支持、反证、仅观察和未确认均为零；报告输入确认度计数中，政策与过热各有5项不适用、信用与物价各有3项不适用、库存有1项不适用。

   证据：[⑦报告区](shots/1440-light-reading.jpg)、[①提示](shots/1440-light-conclusion.jpg)、[报告身份与正文](shots/1440-light-drawer-reading-report.jpg)。

3. **⑥宏观区间抽屉：通过；价格区间保留原有展示。** 在“区间按”切到“宏观判断”，点击“10-19 第三阶段（倾向）”。开关状态为价格阶段 `aria-pressed=false`、宏观判断 `true`。四组抽屉内容一致，逐日原文为：

   > 2026-10-19 · 第三阶段（倾向）  
   > 滞回状态未记录  
   > 投影 projection-59421326f99c005d1801

   抽屉标题“第三阶段（倾向） · 10-19”，代码“Stage III”。宏观逐日行没有价格阶段描述，也没有上一确认、价格原因、缺口或模型行。旧投影没有发布后的 `macro_hysteresis` 展示字段，因此“滞回状态未记录”正确；不能要求它显示主结论块中的 `initial`，也不能当作新发布逻辑已在本投影得到验证。

   价格区间“08-04～10-19”抽屉中，10-19 行仍为：

   > 2026-10-19 · 非典型组合，暂无价格阶段  
   > 上一确认 第三阶段 · Stage III · 原因 非典型组合，暂无价格阶段 · 无 P0 缺口 · 模型 model-v0016  
   > 投影 projection-59421326f99c005d1801

   这与上线前参考的价格展示一致。证据：[宏观抽屉](shots/1440-light-macro-confirm.jpg)、[手机暗色宏观抽屉](shots/390-dark-drawer-history-macro-interval-2026-10-19.jpg)、[价格区间抽屉](shots/1440-light-drawer-history-interval-2026-08-04.jpg)。

4. **②债券归因文案通过；全页普通文字清零未通过。** ②抽屉末段已改为：

   > 债券状态旁的解释附注：不计入确认度，不由宽松程度推算或改写债券牛熊与价格阶段

   计数按稳定页面文本节点计算，含全部 **86 个预渲染抽屉**，排除 script/style；同一文案不因四次视口检查重复累计。另对整个 body 复查，结果一致。

   | 范围 | “正式阶段”次数 | 判定 |
   |---|---:|---|
   | 默认首页可见正文 | 0 | 通过 |
   | ②债券归因普通说明 | 0 | 通过 |
   | 报告详情第三节“价格验证与偏离”的普通段落 | **1** | **未通过** |
   | 报告详情“已验证结果”JSON：`confirmation.bond_attribution.boundary` | 1 | 原文例外，单列 |
   | 全页含所有抽屉，普通文字／JSON 合计 | **1／1，共 2** | 普通文字未清零 |

   普通正文残留所在句原文：

   > TuShare提供的三核心状态为上证国债指数牛市、中证全指熊市、南华工业品指数牛市，构成非典型组合，正式阶段为空，价格阶段亦为空，不能据此推测某一价格阶段。

   JSON 例外原文：“债券状态旁的解释附注：不计入确认度，不由宽松程度推算或改写债券牛熊与正式阶段”。两处均出现在同一新报告详情中，但前者是面向读者的普通说明，不能一并豁免。稳定页面与抽屉“暂无正式阶段”为 0。

   证据：[②已改正](shots/1440-light-drawer-assets-attribution.jpg)、[报告第三节残留](shots/1440-light-report-wording-residual.jpg)。本次只记录，不改正文或代码。

5. **启动壳：通过。** 四组均在 `domcontentloaded` 后、`#reading` 尚不存在时捕获；“正式阶段”及“暂无正式阶段”均为 **0**。主体加载前原文包含：

   > 三核心资产与周期结论  
   > 宏观判断：第三阶段（倾向，5 维中 3 维吻合）· 相对上次确认第三阶段 不变  
   > 本机运行状态  
   > 交互驾驶舱正在启动…  
   > Loading...

   初次自然加载已观察到相同主结论；正式取证为稳定捕获该短暂状态，暂缓浏览器侧 Dash 布局／依赖／只读渲染请求，拍摄后继续原请求，没有改响应或页面文案。证据：[1440 明色启动壳](shots/1440-light-startup.jpg)、[390 暗色启动壳](shots/390-dark-startup.jpg)。

6. **⑦完整度：新表头与说明通过；数字按旧投影保留。** 表头完整原文为：**“口径｜计划期数｜已持有｜门禁 / 等待发布 / 未到应有期｜其他缺失”**。

   | 口径 | 计划期数 | 已持有 | 门禁 / 等待发布 / 未到应有期 | 其他缺失 |
   |---|---:|---:|---:|---:|
   | 模型所需 | 1015 | 1015 | 0 | 0 |
   | 目录全部 | 3065 | 3059 | 2 | **4** |

   用户所指的口径说明实际位于**表上方**，完整原文：

   > 按最终计划的指标 × 统计期计数；期内缺维度仍算缺失。模型口径为三核心与确认规则所需，目录口径包含纯观察指标。等待发布等门禁单列，不计作已持有。晚于应有期、尚未持有的计划期还未到应有期（如已发布的下一期），计在门禁一列，不列为缺口；有已持有期的指标沿用其最新一期。

   实际紧接表下的时间说明原文：

   > 目标日 2026-10-19；时效截至 2026-10-20 09:55（北京）。目标日决定分析日期，时效按运行冻结时点判断。

   “其他缺失 4”与门禁 2 仍是该投影发布时的计数，未前端重算成 3／3；这符合 issues/15 的旧投影不回填要求。本次不能证明下一次发布后的完整度重分类已运行，也未触发发布来验证。证据：[1440 明色⑦](shots/1440-light-reading.jpg)、[390 暗色⑦](shots/390-dark-reading.jpg)。

7. **副标题：通过。** 四组均为：

   > 五维定宏观判断阶段 · 价格表象作验证 · 库存 · 归因，一板看完

   证据：[1440 暗色①](shots/1440-dark-conclusion.jpg)、[390 明色①](shots/390-light-conclusion.jpg)。

8. **横向溢出与控制台：整页、所测抽屉通过；内部滚动与截断单独记录。** 高度 1000 px，设备比例 1；宽度 1440、390，主题 light、dark。主题均通过 `localStorage['pring-cycle-theme']` 设置后 reload，并核对根节点 `data-theme`；实际 body 背景分别为 `rgb(245, 243, 237)` 与 `rgb(3, 18, 39)`。

   | 宽度／主题 | 整页 scrollWidth / clientWidth | 所测抽屉 scrollWidth / clientWidth | ②可检测截断单元格数 | console error / warning / pageerror |
   |---|---|---|---:|---|
   | 1440-light | 1440 / 1440 | 519 / 519 | 15 | 0 / 0 / 0 |
   | 1440-dark | 1440 / 1440 | 519 / 519 | 15 | 0 / 0 / 0 |
   | 390-light | 390 / 390 | 390 / 390 | 21 | 0 / 0 / 0 |
   | 390-dark | 390 / 390 | 390 / 390 | 21 | 0 / 0 / 0 |

   每组均检查债券归因、价格区间、宏观区间、报告详情四个抽屉，打开后整页宽度仍相等。1440 下抽屉外宽 520 px、内宽 519 px；390 下全宽 390 px。没有发现明暗正文不可读或所测抽屉关键文字被遮挡。

   **手机⑦完整度表有内部横向溢出**：390 明色实测容器 `clientWidth=364`、`scrollWidth=401`、`overflow-x:auto`。初始最右侧“其他缺失”不能完整看到；横向滚动 37 px 后，目录行的 **4** 正常可见，最右单元格右边界约 377.33 px，在 390 px 视口内。它没有撑宽整页，不应写成“所有容器都无横向溢出”。证据：[初始表格](shots/390-light-reading.jpg)、[内部横滚后](shots/390-light-coverage-scrolled.jpg)。

   ②同类观察名称列仍有 `overflow:hidden` 截断，例如“站上 250 日均线占比”“中证 1000 市盈率”；桌面名称列约 93 px、手机约 73 px。以上计数含表格内部纵向滚动区的单元格，属于卡内可读性观察，不属于整页溢出。手机版分区导航也使用内部横向滚动。

   四组正式取证的浏览器错误与警告数组均为 `[]`，页面异常数组 `[]`，请求失败和 HTTP ≥400 数组均为 `[]`，越界／命令请求拦截数组 `[]`。两次成功的补充取证也没有控制台错误、页面异常或越界请求。脚本曾遇到定位器多匹配、截图格式参数和锚点定位错误，均已调整后重新取证；这些自动化脚本错误不混入产品控制台统计。

9. **只读边界与产物。** 使用系统 `python3` 的 `playwright.sync_api`、无头 Chromium。仅创建并关闭核对所需浏览器实例；未启停正式服务或其他业务进程。只访问指定首页与同源资源，没有访问其他端口或外网；加载协议仅放行白名单输出 `page-content`、`runtime-poll`、`projection-strip`、`view-fingerprint`、`refresh-notice` 的 Dash 只读 POST 回调，拒绝 `command-refresh` 触发。这些是页面读取回调，没有提交业务命令或表单。

   页面点击仅用于抽屉触发／关闭与区间切换，主题仅按指定 localStorage 键设置后 reload；另做了读取所需的页面／容器滚动。没有点击“发起运行”“生成报告”“刷新”“提交”“重试”，没有打开报告生成工作区。没有写正式数据、配置或仓库；持久产物只有当前目录 `report.md` 和 `shots/`。

   只读参考：`/mnt/d/cursor/datasourceRF/.scratch/macro-stage-20261017/investigations/browser-v0016-first-day.md` 与同目录上级 `issues/11-macro-interval-drawer.md`、`15-completeness-matches-gap-list.md`、`16-wording-leftovers.md`。本次未核验新发布投影，也未尝试修复任何问题。

   四组截图索引：

   | 视口／主题 | 整页 | 启动壳 | 结论 | 阶段史 | 数据说明 | 抽屉 |
   |---|---|---|---|---|---|---|
   | 1440-light | [整页](shots/1440-light-full.jpg) | [启动壳](shots/1440-light-startup.jpg) | [①](shots/1440-light-conclusion.jpg) | [⑥](shots/1440-light-history.jpg) | [⑦](shots/1440-light-reading.jpg) | [债券归因](shots/1440-light-drawer-assets-attribution.jpg) · [价格区间](shots/1440-light-drawer-history-interval-2026-08-04.jpg) · [宏观区间](shots/1440-light-drawer-history-macro-interval-2026-10-19.jpg) · [报告详情](shots/1440-light-drawer-reading-report.jpg) |
   | 1440-dark | [整页](shots/1440-dark-full.jpg) | [启动壳](shots/1440-dark-startup.jpg) | [①](shots/1440-dark-conclusion.jpg) | [⑥](shots/1440-dark-history.jpg) | [⑦](shots/1440-dark-reading.jpg) | [债券归因](shots/1440-dark-drawer-assets-attribution.jpg) · [价格区间](shots/1440-dark-drawer-history-interval-2026-08-04.jpg) · [宏观区间](shots/1440-dark-drawer-history-macro-interval-2026-10-19.jpg) · [报告详情](shots/1440-dark-drawer-reading-report.jpg) |
   | 390-light | [整页](shots/390-light-full.jpg) | [启动壳](shots/390-light-startup.jpg) | [①](shots/390-light-conclusion.jpg) | [⑥](shots/390-light-history.jpg) | [⑦](shots/390-light-reading.jpg) | [债券归因](shots/390-light-drawer-assets-attribution.jpg) · [价格区间](shots/390-light-drawer-history-interval-2026-08-04.jpg) · [宏观区间](shots/390-light-drawer-history-macro-interval-2026-10-19.jpg) · [报告详情](shots/390-light-drawer-reading-report.jpg) |
   | 390-dark | [整页](shots/390-dark-full.jpg) | [启动壳](shots/390-dark-startup.jpg) | [①](shots/390-dark-conclusion.jpg) | [⑥](shots/390-dark-history.jpg) | [⑦](shots/390-dark-reading.jpg) | [债券归因](shots/390-dark-drawer-assets-attribution.jpg) · [价格区间](shots/390-dark-drawer-history-interval-2026-08-04.jpg) · [宏观区间](shots/390-dark-drawer-history-macro-interval-2026-10-19.jpg) · [报告详情](shots/390-dark-drawer-reading-report.jpg) |
