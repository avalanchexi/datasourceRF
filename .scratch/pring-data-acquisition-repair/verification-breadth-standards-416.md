# 08 日广度 Standards 窄复核 416（接口调整待复审）

状态：仅记录已核对的 416 原补丁，不作为最终签核。根代理随后发现共享工作区中旧 WIP 的时间参数仍为必填，正在协调与 HEAD 预览的兼容接口；调整后的输入快照、接口调用及工具终态需要另行复审。以下哈希与判断仅覆盖调整前的 416。

固定基点仍为 `fb13723` 及 `breadth-baseline-373.json` 保存的既有工作区；本批尚无提交。本次核对 `breadth-review-diff-416.patch`、`breadth-review-inputs-416.json` 和 `breadth-index-preview-416.patch`，延续 410 的规范及十二项 Fowler smell 审查，不扩大到其他工作区改动。

独立核验：七文件及审查补丁哈希全部匹配；逐文件比较工作区增量与 HEAD 提交预览的新增／删除行，内容完全一致，未混入额外旧 WIP。预览 SHA256：`979b4f83ec066b2445c8e18eabf79001dd7f0adb88640f823f817cbce7d3228a`。

## 明确规范违规

未发现新增违规或重要回退。HEAD 的 `require_registered_source_contract` 不接受 `release_at`、`public_available_at`，416 已从新增调用移除这两个关键字，没有扩大提交以引入旧 WIP 签名。日统计的时间核验仍由 `validate_daily_breadth_scalars`、输入重解析和采用时原件复核承担，符合 ADR 0006；候选及来源认证边界仍符合 ADR 0012/0013。

## 判断性 smell

无待处理重要项。410 已闭合的 `DailyBreadthResult` 和统一六标量转换保持完整。相邻区间使用 `zip(..., strict=False)` 保持原比较语义；显式类型的 `retrieve` 用默认参数绑定循环当次适配器和输入哈希，保持回放两侧隔离。短注释修改不改变行为。

调整前 416 的静态审查未发现明确规范违规或重要 smell；接口调整及最终验收仍待复核。本报告不替代最终测试终态或整票真实来源验收。除本报告外未修改任何文件。
