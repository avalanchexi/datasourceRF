# #27 人民币汇率其他口径调查

2026-09-17 22:48 用户授权调查其他口径是否存在可靠数据，同时明确TMA暂无授权并保留缺口。

先做公开网页检索，以HKMA、HKEX、CFETS/中国货币网等官方原始资料核对经济定义、历史端点与使用条件。初始检索最多3组、每组3条。具体数值采样仅使用资料中实际出现的官方链接；先记录端点、参数和范围，再做至多4个GET、每次20秒/2MB、无重试无付费认证。不猜测数据端点，不发送消息，不写正式证据库。若仅有在岸汇率/期货等不同口径，记录差异与独立指标身份建议，不擅自拼入TMA或FXCM历史。

## 首轮有界GET（端点均来自官方检索页）

1. https://apidocs.hkma.gov.hk/documentation/ — 查询参数语义。
2. https://www.hkma.gov.hk/gb_chi/other-information/terms-and-conditions-of-use/ — API取用条件。
3. https://api.hkma.gov.hk/public/market-data-and-statistics/monthly-statistical-bulletin/er-ir/er-eeri-daily?offset=0 — 文档示例原样读取默认首批，仅检查实值、字段和覆盖。
4. https://www.chinamoney.com.cn/chinese/homefxrrm/ — 官方人民币参考汇率方法及历史入口，保存网页以读真实链接。

20秒/2MB每次，不重试/不跟随重定向，间隔2秒；不对TMA做额外取数。Web检索抓取HKMA超时只记为工具层限制，不据此认定来源不可达。

## 央行备选来源后续4GET

初轮HKMA取得100个真实日度行，但当前首行仅2026-08-31，字段为每单位外币兑HKD的cny，仍不能证明它是CNH。CFETS只取到参考汇率说明，未取得历史数值。官方检索另找到美联储H10（纽约中午买入价、每周发布）及ECB参考汇率（欧元基准、每日发布），均有明确公开取用条款。为形成可审阅替代方案，继续以下4个已发现链接，20秒/2MB各一次、无重试/重定向、间隔2秒：

- https://www.federalreserve.gov/RELEASES/H10/hist/dat00_ch.htm ：官方China链接的2000年以来人民币历史页。
- https://www.federalreserve.gov/disclaimer.htm ：网站复制与分发条件。
- https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html ：值、口径及真实下载链接。
- https://www.ecb.europa.eu/services/using-our-site/disclaimer/html/index.en.html ：已解析最终版权页链接。

不把纽约时点或ECB交叉汇率命名为CNH，不假设日度观测当天已经公开。只调查，暂不更改目录身份。

## ECB历史样本1GET

原件5fb65626d74541d498ec86c79787a95b5c6fc89d4fa1077df39e7d766302e873中真实链接：https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip?b59ff8e198cf5d409c4b4adff1f9421a
只GET该链接一次，20秒/2MB，无重试/重定向。下载后离线校验ZIP文件成员、解压总量不超过10MB、CSV日期与CNY/USD双腿，派生值明确标记交叉计算，不写正式库。
