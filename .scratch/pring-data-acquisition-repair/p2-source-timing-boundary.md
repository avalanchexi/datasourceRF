Execution: completed-code-batch

# 14续：把已经取得的来源期次与批次计划传给读取投影

已于2026-09-08完成，见[实施与682项全套结果](implementation-14-p2-source-timing.md)。下文保留原始定位、反例和实现边界。

票14要求保留真实期次，并区分发布与陈旧原因。Treasury公开候选入口已经在取得记录保存逐指标`latest_source_period`；EIA公开HTML入口已经保存`release_date`、`next_release_date`与`release_timezone`。当前`build_context_projection`的P2 `latest_acquisition`只选择condition等字段，丢弃上述已经校验的元数据；Dashboard也只显示获取结果标签。这使当前值的统计期与来源已观测最新期无法同时检查。

真实原件、外部transport替换和公开取得→上下文接口已复现：[实际缺字段RED](verification-14-p2-source-timing-owned-red.txt)2失败、18.60秒。隔离库建立既有builtin模型及任务，以已有公开own_acquisitions关联取得，投影确实读到获取记录但丢弃latest_source_period/release_date。没有实际联网、生产模型激活或新来源认证。

此前三次测试设置失败分别保留：导入不存在的目录别名1个collection error、2.19秒；错误期待PUBLIC未知候选有目标期次2失败、3.64秒；未关联任务的独立下载被正确排除2失败、5.66秒。它们均不是产品缺陷。未知PUBLIC在目标模型视图保持缺口、无归属取得不关联目标任务，两个既有保护不修改。

最小改动应传递已记录的来源时区、来源最新期和批次发布/计划日期，并在P2详情可读展示。日期字段保持其语义：EIA当前批次发布日期不等于每条历史日值首发，下一发布日期只是计划，Treasury已见最新源期不等于目标历史窗口缺失。未取得字段继续为空，失败/其他目标/未来取得不能借别次元数据补齐。

不据这些元数据自动授予认证、倒填PUBLIC或覆盖旧统计期；本批不自行冻结跨市场鲜度阈值。已存数据的认证状态、当前公式、正式阶段门禁分别保留。此draft不属于正在运行的库存期次默认全套验收。
