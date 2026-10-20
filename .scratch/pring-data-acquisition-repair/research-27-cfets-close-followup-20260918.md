# CFETS 16:30 收盘价入口增量核查

本轮仅查询官方公开页面和链接，没有取得新汇率历史原件、写入声明或认证来源。原指标继续缺口。

[CFETS 2022-12-30延长交易时间通知](https://www.chinamoney.com.cn/chinese/rdgz/20221230/2526857.html)明确区分9:15中间价与16:30人民币对美元即期收盘价，后者发布时间当时保持不变；这支持口径存在，不证明某个历史值或版本的实际首次发布时间。

[市场行情页](https://www.chinamoney.com.cn/chinese/mkdatapfx/)公开文本列人民币外汇即期报价和日内走势图。本轮沿其“每日速递”真实链接到[日报页](https://www.chinamoney.com.cn/chinese/mtdexdaily/)，页面列本币拆借/回购/现券等日报，未提供本指标的历史正文。不能据此断言动态接口不存在。

[参考汇率历史页](https://www.chinamoney.com.cn/chinese/homefxrrm/)说明各参考时点采用此前30秒成交价加权，无成交时用报价计算；没有证据把该参考序列等同16:30收盘价。中间价、整点参考、掉期曲线及ECB交叉参考均不得自动填入`CN_USDCNY_CLOSE_1630`。

下一条有依据的调查入口是市场行情页所实际加载的公开组件/脚本及其历史能力，再核精确16:30标签、交易日期与来源说明；不拼猜接口、不扩大到登录或付费边界。该项为P2，不阻塞当前软件回归；保留TMA授权缺口和已批准ECB独立口径。

## 公开组件跟进结果

随后按`plan-27-cfets-component-probe-20260918.md`完成7/8预算内GET，全部来自入口HTML、组件或共享脚本的实际引用。原件与回执位于`evidence-27-cfets-component-20260918/`。这批取得的是当前公开行情组件及一份当前快照，仍不是历史收盘价原件。

路径链：市场行情页 → `dollar-ask-day-chart.html` → cm-basic.js定义的DURL前缀与组件明确引用的`fx/rfx-sp-iday-chrt.json`。端点为[公开日内图JSON](https://www.chinamoney.com.cn/r/cms/www/chinamoney/data/fx/rfx-sp-iday-chrt.json)。快照原件`255aeacfbaebf833bd770b699afa54a322032a6a98f3caea190ac8d6835346a1`包含`closeSpotPrice`字段，但本次其值为`---`；`lastDate=2026-09-18 10:50`，`spotPriceStr=6.6985`。后者是页面标注的当前成交价，不能当16:30收盘价。

组件说明note-960表明数据每10分钟更新；note-978区分T+2成交价格与包含T+0/T+1/T+2的成交量。日内图字符串不是严格JSON，不能执行其JavaScript内容来解析；更不能因为显示逻辑把空白时间标签补成16:30，就推断该行是有可靠日期和版本证明的收盘值。

未找到日期查询参数或历史入口，本批在7次后结束，不构造额外参数遍历。新依据是可供日后实采核验的明确`closeSpotPrice`字段；仍需收盘后的真实非空原件、指标语义和历史能力/用途证据，才能考虑接入。2026-09-11历史仍未取得。第一条研究请求记录到宿主UTC小幅回拨（结束早于开始），原始时间未改写；后续增加单调计时，本批时间不会导入为应用可用时间或历史PUBLIC。
