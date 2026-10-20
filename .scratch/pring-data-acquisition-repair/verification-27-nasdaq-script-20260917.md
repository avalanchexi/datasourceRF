# 27：Nasdaq 历史取用机制

按照 `plan-27-nasdaq-script-20260917.md`，只执行 1 次 GET，取得历史页明确引用的 `History.js`，HTTP 200、77,395 字节。原件与时间/哈希回执在 `evidence-27-nasdaq-script-20260917/`。

该脚本表明历史表由 `/Index/HistoryData` 的 POST 响应填充，参数为 `id`、`startDate`、`endDate`、`timeOfDay`，结果使用 `aaData`。原 HTML 表格为空，因此不足以判断历史不可用。

脚本也定义了页面导出链接：`/Index/ExportHistory/{symbol}?startDate=...&endDate=...&timeOfDay=...`；原 HTML 的收盘选项值为 `EOD`。这些是从真实原件提取的接口与参数，不是猜测路径。

本批没有调用数据接口或导出接口，尚不能证明能取得 SOX 历史行或满足使用边界；下一步可在单独明确的有界请求中验证页面的真实导出链接，保留失败样本。仍未进行指标迁移或来源认证。
