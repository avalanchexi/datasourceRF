# LPR 官方来源认证

## 冻结身份

- 规范指标：`CN_LPR_1Y_5Y`
- 官方提供方：中国外汇交易中心暨全国银行间同业拆借中心“中国货币网”
- 来源代码：`CHINAMONEY_LPR`
- 统计频率：月度
- 单位：百分比
- 维度：`tenor=1y`、`tenor=5y_plus`
- 发布时区：`Asia/Shanghai`

## 一手来源依据

中国货币网的 [LPR 基准页](https://www.chinamoney.com.cn/chinese/bklpr/) 说明，LPR 包含
1 年期和 5 年期以上两个品种；报价行在每月 20 日（遇节假日顺延）9 时前报价，并于当日
9 时公布。公众可在全国银行间同业拆借中心和中国人民银行网站查询。

2026 年 8 月的
[官方公告](https://www.chinamoney.com.cn/chinese/rdgz/20260820/3399885.html)
显示页面发布时间为 2026-08-20 09:00，并在同一公告中发布两个期限值。适配器把页面时间
解释为北京时间，分别记录 `release_at`、`public_available_at` 和本机实际抓取形成的
`available_at`。

## 认证边界

认证适配器只接受 `https://www.chinamoney.com.cn/chinese/rdgz/YYYYMMDD/CONTENT_ID.html`
形状的 URL，并要求 URL 日期、标题日期、页面发布时间日期、请求统计期完全一致。正文必须
同时包含人民银行授权语句、1 年期和 5 年期以上唯一数值；缺字段、重复字段、非 UTF-8、
异常单位、非 200、非 HTML、跨域重定向或超限响应全部 fail closed。

离线契约 fixture 只能验证解析器，不能写入认证 claim。真实烟雾不保存正文；正式 refresh
才保存内容寻址公告并写入两条不可变 claim。通用证据入口不能把人工输入升级为 certified。
