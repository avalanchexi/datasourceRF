# 27：SOX 官方历史导出样本已核验

按 `plan-27-nasdaq-export-20260917.md` 完成 2 次有界 GET，无重试、重定向或登录：先取得页面引用的 Site.js 确认日期编码，再请求 History.js 定义的 SOX/EOD 导出，日期范围 2026-09-09 至 2026-09-16。

Nasdaq 返回 HTTP 200、6,981 字节的原生 XLSX，附件名 `EODHist_20260909-20260916_SOX.xlsx`。原件 SHA256 为 `954f951d602068ea6bf2066fc21d2fc9eee1fba2f96f8a586c995014cfa00d27`。全部请求回执、脚本、原件与解析证据保存在 `evidence-27-nasdaq-export-20260917/`。

工作簿含 Trade Date、Index Value、Net Change、High、Low 五列，6 个互异交易日：09-09、09-10、09-11、09-14、09-15、09-16。复核 Excel 1900 日期系统、请求区间、有限数值、高低区间和相邻日变动一致性；没有公式或 Excel 错误单元格。目标 09-11 的 Index Value 原始精度为 `11823.99806856453`。完整逐行结果见 `validated-sample.json`。

读取遵循 xlsx 技能，未修改官方工作簿。运行环境未安装 openpyxl，使用标准库 ZIP/XML 只读解析并限定解压总大小，无需安装或改动测试环境。

本批证明少量官方历史行可取得并解析，纠正“HTML 空表即没有历史”的推断。尚未核验完整历史覆盖、可靠发布时间和使用许可，仍为 `awaiting_source_certification`，没有写正式证据仓库、迁移指标或激活模型。页面 Trade Date 只表明交易日期，不擅自变成实际发布时间。
