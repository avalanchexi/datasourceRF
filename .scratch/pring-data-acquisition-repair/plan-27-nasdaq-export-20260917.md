# 27：Nasdaq 日期编码与历史导出核验

请求前冻结；沿用用户继续 #27 的授权。依据已归档历史页面（SHA256 `69fd34f2b0dbcd2a743167d8ca77b38c686b02759ea98291ae98e5010d49d49a`）和 History.js（`42ffc7c0adb7c36cb16dcbb5067cb994a0a770331ec615167f5c86ccc9b0520e`）。页面标记 `historyFree`，SOX、EOD 与导出路径均来自原件。

- 本批最多 2 次 GET，各 URL 只请求一次，无重试、无重定向，20 秒超时、每响应最多 2 MB。
- 第一次仅取页面已引用的 `https://indexes.nasdaq.com/Scripts/Site.js?v=2.0.0.38118`，作为文本确认 `toISONonUtcString` 编码。
- 仅当编码已确认且未发现认证/许可门时，第二次取 History.js 定义的 `/Index/ExportHistory/SOX`，范围为 2026-09-09 至 2026-09-16，`timeOfDay=EOD`。最终编码后的 URL 在发送前写入本批回执。
- 任一步失败、超限或返回访问门即停止；不登录、不绕过限制、不扩展日期范围。保存状态、响应类型、原件、时间和哈希。
- 只判断少量历史样本的取用和格式；不能据此标记来源认证完成，不写正式数据库或改动目录。
