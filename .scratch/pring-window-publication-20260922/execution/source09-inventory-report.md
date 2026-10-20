**结论：指定证据链内，新120日窗口现有31日已核值原件，缺89日；默认259日公式输入缺228日。历史98次失败主要是传输环境问题，不能据此判定官方文件不存在。当前正式核心链只接受TuShare，南华PDF尚无完整接入入口。**

本次只读核验文件哈希、目录、文章发布时间字段和代码；未联网、未读凭据或应用库、未运行测试。PDF数值沿用已保存核对记录，未重新渲染逐页目验。

1. **历史原件位置、身份与失败性质**

   - 历史材料位于 `.scratch/pring-data-acquisition-repair/evidence-04/`；直接索引是 `receipts.json`、`nh-daily-batch-receipts.json`、`verification-summary.json`。本次重验其中27个南华成功响应原件，全部存在且SHA-256一致；`research-04.md`哈希也与原验证文件一致：`40d6c8c352948599af6d5ee1e6ec37d83c4aa584b789d568d327315643002ca3`。[索引说明](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/research-04.md:11)
   - 可复用的15个历史日报日期为：**2026-08-07、08-10至14、08-18至21、08-24至28**，均按交易日列举。保存的核对记录确认首页`NHII / Today Close`与当时TuShare比较值一致；这是身份与数值对账，尚非逐版本发布时间认证。[逐件清单](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/research-04.md:134)
   - **08-17仍是错链**：标题写日报20260817，附件却是08-14周报；PDF哈希为`87d01b4c239555057fbb2af2b38e1fe71d58c955a807ed390d061385b6fe16fb`。本次比较09-06与09-22保存目录，重叠记录的标题、链接和createTime无变化，不能认定已经修复。[错链证据](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/research-04.md:92)
   - **纠正旧报告：98次失败实际为97次ProxyError、1次ReadTimeout**，后者是05-12、读取超时10秒。回执没有这些请求的404或成功响应原件；前者明确发生于代理连接阶段，后者只能定位为读取超时，不能进一步断定服务端原因。无证据说明这是本地路径错误或权限拒绝。[统计](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/evidence-04/verification-summary.json:1153)、[05-12原回执](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/evidence-04/nh-daily-batch-receipts.json:657)
   - 新增材料位于旧effort的`evidence-publication-rescue-20260922/20260922T064537521872Z/objects/`，09-07补件位于新effort的`evidence-09-followup/20260922T080643656322Z/objects/`。**16组文章/PDF共32件本次全部重验哈希通过。**09-07此前是“周报”标题过滤造成漏项，现已有4122.92原件；09-02、03、04、08也已有核值记录，不能继续列为缺值。[纠正记录](/mnt/d/cursor/datasourceRF/.scratch/pring-window-publication-20260922/evidence-09-value-review.md:7)

2. **按当前窗口重算的覆盖与缺口**

   当前代码默认`120日均线＋20日斜率`，首次基础测量需要140点；因此本轮基础输入为**2025-08-29至2026-09-22，共259日**，其中窗口前139日。这不保证8日持续确认已满足。[实际公式](/mnt/d/cursor/datasourceRF/src/pring_cycle/domain/trend.py:62)、[日期清单](/mnt/d/cursor/datasourceRF/.scratch/pring-window-publication-20260922/calendar-plan.json:225)

   | 范围 | 已核值原件 | 缺少合格原件 |
   |---|---:|---:|
   | 新增17日：08-31至09-22 | 16 | 1：09-22 |
   | 正式120日：04-01至09-22 | 31 | 89 |
   | 计算预热139日：2025-08-29至2026-03-31 | 0 | 139 |
   | 基础公式输入259日 | 31 | 228 |

   以上按历史15日与[新增16日逐值表](/mnt/d/cursor/datasourceRF/.scratch/pring-window-publication-20260922/evidence-09-followup/20260922T080643656322Z/nhii-sixteen-value-reconciliation.json:4)取日期集合交集，**不是照抄旧统计，也不是应用库覆盖结论**。

   - 正式窗口89日缺口＝**82个历史传输失败日＋08-17错件＋5个历史目录缺日＋09-22**。5日为05-08、05-22、06-09、06-10、07-16。
   - 预热139日＝**16个历史传输失败日＋113个已有目录线索但未见合格下载核值原件的日期＋10个目录缺日**。
   - 预热目录缺日：2025-09-25、26、29、30，11-14、20，12-15、26，2026-01-12、03-26。本次同时检查标题、附件名及createTime，未发现类似09-07的同日隐藏记录。这里只证明保存目录缺项。
   - **03-26虽移出展示窗口，仍在计算预热内，不能删除缺口。**09-22最新保存观察止于北京时间16:06–16:07；之后是否发布未联网实测。[观察边界](/mnt/d/cursor/datasourceRF/.scratch/pring-window-publication-20260922/evidence-09-value-review.md:26)

3. **正式入口与最小接通合同**

   现有路径是：

   `core-history-refresh → TushareCoreAdapter → AcquisitionRepository → refresh_core_history → 来源声明 → evidence-query / metric_series`

   CLI明确实例化TuShare适配器；历史刷新因响应没有可靠发布字段，将`release_at/public_available_at`保留为空。[CLI](/mnt/d/cursor/datasourceRF/src/pring_cycle/cli.py:365)、[声明构造](/mnt/d/cursor/datasourceRF/src/pring_cycle/core_history.py:129)

   **仅增加PDF解析器不够，至少有四处现存合同约束：**

   - 原件重解析硬限定`provider=tushare`、API、字段、解析器版本及规范化哈希。[source_adapters.py](/mnt/d/cursor/datasourceRF/src/pring_cycle/source_adapters.py:25)
   - 注册来源身份要求TuShare及其source_reference格式。[source_contract_review.py](/mnt/d/cursor/datasourceRF/src/pring_cycle/source_contract_review.py:164)
   - 声明写入会重解析关联核心原件，消费者也再次检查来源身份、日期和值。[写入门](/mnt/d/cursor/datasourceRF/src/pring_cycle/evidence.py:266)、[消费门](/mnt/d/cursor/datasourceRF/src/pring_cycle/source_adapters.py:72)
   - 通用`evidence-ingest`明确拒绝P0和人工标记certified；现有官方上下文解析入口处理其登记家族HTML，不是NHII PDF入口。[导入限制](/mnt/d/cursor/datasourceRF/src/pring_cycle/cli.py:908)、[官方解析入口](/mnt/d/cursor/datasourceRF/src/pring_cycle/official_context.py:218)

   最小正式交付需明确：**独立南华来源身份与版本化合同；文章、PDF、链接和哈希绑定；NHII、目标日、Today Close、单位的真实解析；具体数值版本的发布时间与精度；不可变声明及SYSTEM实际校验时间；写入和消费者一致的原件复核。**发布时间文章与数值PDF应区分证据角色，不能把两者都塞入当前“每件关联原件必须解析出行情”的合同。最后经现有PUBLIC/SYSTEM查询读回值和血缘，并保留来源审核门。

   可复用测试先例：注册核心[精确原件拒收](/mnt/d/cursor/datasourceRF/tests/models/test_candidate_admission.py:9558)、[回放再次核验原件](/mnt/d/cursor/datasourceRF/tests/models/test_candidate_admission.py:9671)、[未知发布时间保持空](/mnt/d/cursor/datasourceRF/tests/integration/test_core_history_refresh.py:144)。[日期精度测试](/mnt/d/cursor/datasourceRF/tests/integration/test_core_history_refresh.py:611)明确使用合成领域输入，只证明时间选择语义，不证明官方PDF已接通。本次均未运行。

4. **发布日期证明力与优先补取线索**

   - **具体值的候选发布证据**：新增16篇文章正文确有各自“发布时间”，本次重新抽取，与保存记录一致；配合文章所链PDF及该PDF中的值，可开展逐版本绑定审核。旧15日报目前主要有目录createTime，宜补对应文章正文。08-28目录时间比附件Last-Modified早51秒，已说明不能直接把文章秒级时间授予当前附件。[差异记录](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/research-04.md:104)
   - **方法材料不是逐值发布证据**：2025细则、2025/2026权重工作簿、2025-08-15生效的强制移仓公告，只支持身份、计算和有效期。新基础输入从08-29开始，已不跨旧报告提及的08-15规则边界；仍跨2026-06-01年度换权。[方法边界](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/research-04.md:44)、[ADR0018](/mnt/d/cursor/datasourceRF/docs/adr/0018-tiered-evidence-for-historical-publication-dates.md:7)
   - **优先补取已有精确URL，先验证环境恢复**：98条失败链接已保存在回执，无需重新发现；可先用[05-12官方PDF](https://www.nanhua.net/cmsbigfile/2026/05/3f2ab934-9f51-4979-97e9-3c5626f679de/南华商品指数日报20260512.pdf)作小批复取检查。成功与否本次未实测。
   - **预热首日已有明确日报线索**：[2025-08-29文章](https://www.nanhua.net/news/2025/08/b81f4874-1fef-44a4-99a5-3f60fa4c07ad.html)及其同UUID日报PDF；目录另有同日周报，不能按日期任取一件。08-17则应优先核[对应文章](https://www.nanhua.net/news/2026/08/ecfc24cc-2072-4ceb-9d43-1c6a29d9bbcc.html)是否存在正确附件线索。
   - 其余目录缺日和09-22，继续使用官网`queryNewsListByTypeForJson.shtm?site=newnanhua&type=404205&start=…&limit=…`及记录自带`url/href`定位；不要猜UUID或只按“日报”标题过滤。可靠日期仍须按下一本地日可见；计算预热同样受此约束。[ADR0019](/mnt/d/cursor/datasourceRF/docs/adr/0019-formula-warmup-requires-publication-evidence.md:7)