# 27：TMA 历史页面与取用边界

按 `plan-27-tma-history-20260917.md` 完成 2 次 GET；两次均 HTTP 200，无重试或重定向，间隔约 2.009 秒。页面及其直接链接的 7 页 PDF 原件、时间和哈希见 `evidence-27-tma-history-20260917/receipts.json`。

## 数据事实

TMA 旧页面中的实际站点与路径为 `https://benchmark.tma.org.hk/benchmark/marketdata`，相对链接解析为 `https://benchmark.tma.org.hk/benchmark/history/usd-cny-spot-rate`。历史页不是空表：服务器返回的 Next JSON 中有 09-10、09-11、09-14、09-15、09-16 五个交易日，USD/CNY(HK) Spot Rate 分别为 6.7066、6.7113、6.7077、6.7105、6.7114。完整抽取为 `validated-sample.json`，仅解析文本未执行脚本，没有正式入库。

统计日和围绕 11:00 的计算窗口不等于实际公布时刻。本次没有证明历史 PUBLIC 时间。旧页同时明确 Spot USD/CNY(HK) Fixing 自 2016-08-01 改名为现名，该条确实属于 USD/CNY(HK)，并非混用了相邻 USD/HKD 的说明。

## 来源所述条件

页面直接链接的 `TMA Notice on Licensing Regime with FAQ.pdf`（SHA256 `372a81cfb9005aab00ba98759a75ae8fcd747027948ab83f5f8855bb29c2e497`）说明公开页面提供至少 24 小时延迟的非商业查看；FAQ 第 8 项将完整历史访问面向订阅者。免费页面少量行不足以证明本地持久化/分析所需授权或 120 交易日历史已具备。

已向用户询问是否已有相应历史数据授权；在答复前保持未认证和透明缺口，继续其他任务，不重复询问 TuShare 已被豁免的许可检查。TMA 是另一个渠道，该 TuShare 豁免不自动覆盖它。没有发送任何对外邮件或创建订阅。

PDF 用已有离线缓存中的 pypdf 在隔离 uv 环境只读提取；未修改项目或正在运行测试的虚拟环境。首次表格定位因错误要求完整 CSS class 字符串相等而未找到，改为匹配独立类名后提取 5 个日期和5个数值并核验唯一日期、有限正数；原件不变。
