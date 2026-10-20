Status: assessment-only
Type: bounded-source-probe-and-capture
Date: 2026-09-22

# 发布证据补查与新增 17 日原件保存

本轮在用户确认[公式预热同等取证](../../docs/adr/0019-formula-warmup-requires-publication-evidence.md)后，
补查真正债券核心 000012，并执行此前已授权的新增 17 日公开原件保存。
保存成功、机械解析、来源认证是三个不同状态；本轮没有执行应用入库或签发认证。

## 核心与确认指标的有界补查

| 对象 | 本轮实际结果 | 结论边界 |
|---|---|---|
| 000012，2026-09-21 | 中证日线接口 HTTP 200，返回正确代码和日期的收盘 230.70；没有发布字段，响应头没有 Last-Modified/ETag | 数值取得，公开时间缺件仍未解除 |
| 上交所每日债市 | 官方页面 HTTP 200；正文的“页面生成时间”是 2023-11-08，数值通过动态查询加载；对应 2026-09-21 查询返回 HTTP 200、空 result | 模板时间不能绑定目标日数值；空响应不能证明该日从未发布 |
| 000985 替代官方入口 | 独立限定检索没有取得目标日数值与发布证据同时绑定的新原件 | 未找到；不能扩大为所有官方来源都不存在 |
| 深交所每日统计候选路径 | 独立研究给出的路径在主会话实际请求中返回 404；正式融资栏目返回 200，其 Last-Modified 仍是 2026-08-29 的模板修改时间 | 该候选路径失效；正式栏目模板不证明逐值发布时间 |
| CNY030，2026-09-21 | 官方衍生列表 HTTP 200，列出 `000012CNY030`、国债指数（全）；日线接口 HTTP 200、data 为空 | 身份可证，目标数值及发布证据尚未取得；不宣称该指数不存在 |

官方入口：

- [000012 目标日行情](https://www.csindex.com.cn/csindex-home/perf/index-perf?indexCode=000012&startDate=20260921&endDate=20260921&lang=zh_CN)
- [上交所每日债市页面](https://bond.sse.com.cn/trainings/research/daily/indexD.shtml?TRADEDATE=2026-09-21)
- [页面实际调用的指数查询](https://query.sse.com.cn/commonQuery.do?isPagination=false&sqlId=COMMON_BOND_PXYFW_YJFX_MEZS2_L&TradeDate=2026-09-21)
- [深交所融资栏目](https://www.szse.cn/disclosure/margin/margin/index.html)
- [CNY030 目标日行情](https://www.csindex.com.cn/csindex-home/perf/index-perf?indexCode=000012CNY030&startDate=20260921&endDate=20260921&lang=zh_CN)
- [000012 官方衍生指数列表](https://www.csindex.com.cn/csindex-home/perf/get-derivative-index?indexCode=000012)

本地可复核原件与请求收据：

- [首次主会话访问](evidence-publication-followup-20260922/parent-access-064638454950.json)
- [动态债市查询及深交所栏目](evidence-publication-followup-20260922/parent-followup-2.json)
- [CNY030 身份与日线](evidence-publication-followup-20260922/parent-cny030.json)
- [独立探测原文](evidence-publication-followup-20260922/delegated-probe.md)

独立探测通过只读 Codex CLI 执行、退出 0。其直接网络访问受到本地沙箱限制，网页检索可用；
主会话随后实际访问并保存上述原件，已覆盖这些入口的环境阻断结论。未放开子进程写权限。
任何本地权限错误均不计作发布者拒绝或数据不存在。

## 新增 17 日原件保存结果

范围按既有窗口决定限定为 2026-08-31 至 2026-09-22 的 17 个目标交易日；
仅取得一个含 40 条记录的南华目录响应，不抓全历史附件。执行脚本为
[capture-publication-rescue-20260922.py](capture-publication-rescue-20260922.py)。

请求从 2026-09-22 06:45 UTC 左右开始，至 06:47:08 UTC 完成，退出 0：

- 48 次 HTTP 获取尝试，47 个成功响应；原件约 27.5 MB，以 SHA-256 命名保存，全部对象哈希重验通过。
- 南华：保存 15 个目标日的文章页面和 PDF。15 份 PDF 首页日期均与目标日一致；机械解析取得其中
  11 份的 NHII 行，09-02、09-03、09-04、09-08 的 NHII 数值仍需检查，不能将日期匹配算作数值验收。
- 南华本次目录未列出 09-07 和 09-22；这是目录观察结果，不证明它们从未发布，也不填空白值。
- 上交所：保存 16 个目标日 XLS，均识别为有效 OLE 文件并读出“汇总信息”表；09-22 文件返回 404，
  错误响应原件亦保留。日期身份依赖官方 URL；没有将 HTTP 修改时间自动认定为首次公开时间。
- 抓取在北京时间 14:45–14:47 进行，09-22 的上述观察是这一时点的状态，不是该日终态。

全部请求的来源、目标日期、获取时刻、选定响应头、原件哈希及传输结果在
[receipts.jsonl](evidence-publication-rescue-20260922/20260922T064537521872Z/receipts.jsonl)，
终态在 [summary.json](evidence-publication-rescue-20260922/20260922T064537521872Z/summary.json)，
机械内容检查在 [content-check.json](evidence-publication-rescue-20260922/20260922T064537521872Z/content-check.json)。
原件存于同目录 `objects/`。

本批尚未与应用声明逐值对账、验证历史版本修订、覆盖完整 120 日及各公式预热，也未纳入应用 CAS。
哈希命名的研究原件库不能冒充正式应用的入库及认证收据。未运行软件测试，生产代码和模型未修改。

## 对后续规格的输入

1. 保持 PUBLIC 无前视门槛和固定 09-22 窗口，分别列明基础数值、发布证据、方法与修订版本的缺口。
2. 用户已选择 [CNY030 降为 P2](../../docs/adr/0020-cny030-optional-pending-certification.md)，目录迁移尚未实施；
   这一项不再要求以 P1 交付，不外推到其他指标。
3. 来源未齐的三核心和其他 P1 继续阻塞相应认证与真实候选，不能以采集脚本成功或研究报告完成替代验收。
4. 原件保存可以复用本次结果；后续仅补缺件、检查适用版本与时间语义，并按正式入口完成导入。

## 2026-09-22 后续纠正

新一轮[原件复核](../pring-window-publication-20260922/evidence-09-value-review.md)已核出上述四份PDF的NHII值，并查实09-07在本批原始目录中已有记录：标题写“周报”，被旧脚本只匹配“日报”的过滤条件误漏。此前“目录未列09-07”不准确；原始目录及历史抓取收据保留。现已补取09-07页面/PDF并核值，09-22于16:07复查仍未列；完整来源认证仍未完成。
