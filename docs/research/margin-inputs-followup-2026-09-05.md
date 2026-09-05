# 融资汇总：官方元级比对与候选合同验证

复核日期：2026-09-05。本文件补充[原市场来源审查](market-source-semantic-review-2026-09-05.md)，不修改其冻结内容，也不签发来源认证。依据 [ADR0013](../adr/0013-tushare-delivery-with-official-sampling.md)，官方样本用于核对交付渠道的语义和实值，完整认证还需要发布时间及许可等证据。

## 已解决的数值问题

对 2026-08-28 的官方汇总与当前获授权 TuShare 账户响应进行同日、同字段比较，沪深两个字段均达到**元级相等**：

|交易所|融资余额 rzye（元）|融资买入额 rzmre（元）|比较结果|
|---|---:|---:|---|
|SSE|1,342,943,855,079|94,338,686,041|两个字段与 TuShare 相等|
|SZSE|1,278,973,655,069|95,431,661,788|两个字段与 TuShare 相等|

上交所字段取自其[官方汇总 JSON](https://query.sse.com.cn/commonSoaQuery.do?sqlId=RZRQ_HZ_INFO&beginDate=20260828&endDate=20260828&isPagination=false)，响应 `opDate=20260828`。汇总含调出标的范围后的余额，不能用当前标的明细求和替代。[上交所汇总说明](https://www.sse.com.cn/market/othersdata/margin/sum/)

深交所[网页 JSON](https://www.szse.cn/api/report/ShowReport/data?SHOWTYPE=JSON&CATALOGID=1837_xxpl&txtDate=2026-08-28&tab1PAGENO=1)显示 12,789.73 和 954.31 **亿元**，但同报表的[官方 Excel 导出](https://www.szse.cn/api/report/ShowReport?SHOWTYPE=xlsx&CATALOGID=1837_xxpl&txtDate=2026-08-28&TABKEY=tab1)表头明确是**元**，并保存上述精确数值。Excel 本身没有日期单元格，日期绑定来自同一查询参数、报表目录及 JSON 元数据 `subname=2026-08-28`，不能把请求日期单独当作响应内日期证明。

这修正了原审查中的舍入假设：两个网页数与精确数的差分别是 0.00655069、0.00661788 亿元，超过假设普通四舍五入得到的 0.005 容差。因此本次**改用元级官方 Excel 比较**，没有扩大容差来强行通过，也没有据这两个样本宣称已证明所有网页日期的截断算法。

TuShare [margin 官方文档](https://tushare.pro/document/2?doc_id=58)定义 `rzye`、`rzmre` 为元，交易所标识为 SSE、SZSE、BSE；提示单次最多 4,000 行。一次 120 日、三交易所的响应只有 360 行，且通过了完整矩阵校验，未以返回行数代替成员检查。

## 原始证据清单

所有 hash 均针对 HTTP 原始响应字节。文件已保存至 WSL 的 `/home/tywin/.local/share/pring-cycle/artifacts/sha256/<前2位>/<完整hash>`；已有同 hash 文件只验证、不覆盖。时间为下载完成的 UTC 时间，不是历史首次发布时间。

|原件|下载时间（2026-09-05 UTC）|字节|SHA-256|
|---|---|---:|---|
|SSE 20260828 汇总 JSON|10:25:05.522979|804|`fa7f73716372a7be474ff766b2eb8cebd7260d71d7e87c94884cd5727d6e5eed`|
|SZSE 20260828 报表 JSON|10:25:05.744374|8,383|`c795098426ebe987b7971ffcadc1bd36a34cbe3f5b9fc2295baa1883fbc77277`|
|SZSE 同日报表 XLSX|10:26:32.604056|3,711|`a0bccdd0398381440b43432cb8fc777f6e46a7e271a79d08ac6fdc56b031ab1c`|
|TuShare margin 单日响应|10:25:42.514088|328|`3cb57edb3e560a118fd2a84c94d471a53179547489b5ef0936649c63e4ae4548`|
|TuShare trade_cal 20260309—20260828|10:37:48.356948|2,759|`d0740f44c9648b5adc6ba98fe9acb59565858e8195cdf25df09e59f691b94635`|
|TuShare margin 20260309—20260828|10:37:48.446971|17,550|`a03de595618ce8aa3fa74ce97fff980bbbe3e2197e9f5064b7157756dd7b2afd`|

TuShare 请求发送至 `https://api.tushare.pro`，只记录不含 token 的 API 名、参数、字段和响应 hash。单日 `margin` 参数为 `trade_date=20260828`；区间请求为 `start_date=20260309,end_date=20260828`，字段均为 `trade_date,exchange_id,rzye,rzmre`。交易日历使用 `trade_cal,exchange=SSE` 和相同日期区间，字段为 `cal_date,is_open`。原始响应未包含密钥；没有在文档或日志保存认证请求体。

## 新候选定义及实际验证

增加独立的指标定义 `margin-financing-v0002`，仅用于该融资指标的来源复核；它不是整个目录的 v4，也不是一个已通过认证的新模型。定义状态固定为 `awaiting_source_certification`，旧 `metric-catalog-v0003` 的 hash 与历史语义保持不变。

- 汇总范围明确写为 `SSE+SZSE+BSE`，延续旧适配器测试已包含的三个交易所，而不再使用含混的 `all_exchanges`。
- 调用者传入完整的预期中国交易日日历；每个日期必须恰有三个交易所各一行。缺交易所、缺整日、重复行、额外日期和未知交易所均拒绝。实际零值与缺失分开，数值必须有限且非负。
- 元转换为亿元仍除以 1e8；只使用融资余额与融资买入额，不替换成两融总余额。
- 没有可靠首次发布时间时，`release_at` 与 `public_available_at` 都保持 null。单独记录成功抓取后的系统可用时间，不复制旧版本的次日零点，也不把抓取时刻当成首次公开时间。
- 新候选 scalar 必须显式绑定新定义入库，旧 scalar 不能直接重标；来源引用与发布事件身份包含新版本，避免沿用旧版本时间。

使用[有界复核脚本](../../.scratch/pring-cycle-dashboard/verify_margin_candidate_20260905.py)实测 2026-03-09 至 2026-08-28：120 个唯一交易日、360 条交易所原始记录、240 条两维汇总观测。隔离复核运行时位于 `/home/tywin/.cache/pring-cycle/margin-review-20260905`，240 条观测均为待认证、未知公开时间；`public_as_of` 可见点数为 0。没有写入正式运行数据库、切换模型或发布报告。

可复核产物：

- 规范化候选响应：`a8fed6eccabcef230c87e5a2fcd7f87a604b1e96f21cc44494eb3631aa46a15b`。
- 包含原始请求收据、四字段对比、定义、数量和未解项的复核清单：`c0bbdf18fa19fcf0a2025b602c7a57f7317e60822b54ac90ff3fc11fd3d5dc6f`。

这是来源候选验证，不是新旧模型的 120 日点时重放，也不提供认证授权。

## 尚未解决

1. **BSE 官方数值样本**：TuShare 单日响应有融资余额 8,332,418,348 元、融资买入额 659,105,185 元；但[北交所官方页面](https://www.bse.cn/disclosure/rzrq_trans_list.html)两次有界请求均因 302 重定向循环失败，未取得同日官方原件，不能把渠道值视为已交叉核验。网页检索内容说明其展示单位为万元，后续取得实际原件仍须核对单位、精度、日期和汇总范围。
2. **实际发布时间**：TuShare 文档的次日上午更新时间是交付时限提示，且明确深交所、北交所周五数据在下周一更新；它不能证明每次实际首次发布时刻。本次官方响应只有交易日期，没有足以回填历史发布时间的证据。现行候选保留 unknown，不能直接进入要求公开点时可见的模型回放。
3. **模型纳入与认证**：只有 family 的官方样本、时间和其他认证条件闭合后，才能形成后续不可变认证定义及新模型，完成相应重放和激活流程。当前候选不会自动解除 v3 暂停。
