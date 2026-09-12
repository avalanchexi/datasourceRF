# Spec专项457：历史close与日涨跌资格

结论：**在身份、合法成交、close、当时可知性及调整链均满足原规则时，历史IPO首日缺官方涨跌参考价，或历史日仅缺pre_close，不应把已有close当作窗口缺价。** 这不授予该历史日涨跌分类，也不让上市不足120个市场日的股票提前进入窗口分母。本问题可以依据已确认规则处理，无需新增业务选择。

依据：[规则记录08](business-decisions-draft.md:22)限定“仅在官方参考价含义和实值均已证明时参加日涨跌”，并说明“它不自动获得MA120资格”；这里规定的是日涨跌比较，未要求每个历史close都必须能计算当天涨跌。[规则记录09](business-decisions-draft.md:30)规定“新股不足完整窗口时退出窗口指标参与基数”，第32行要求连续身份、调整链、预热和同一价格基准。[票09](issues/09-breadth-window-metrics.md:25)要求“完整必要价格、复权事件、公式及父项集合”。因此，在第120个市场日、其他窗口条件均满足时，不能仅因首日涨跌参考价未知，再额外等待一天；也不能仅因某历史日pre_close未知否定已证close。规格Implementation14和Testing7沿用上述规则，没有增加这种门槛。

**P2静态发现：** `tushare_context.py:1119`仅保存advance/decline/flat成员的close；`market_breadth.py:487`的first_day_reference_unproven及`:491`的reference_price_missing因此丢失合法历史价格，最终在`:967`形成insufficient_window。修复须独立验证合法成交和close，不能直接把这些状态全部当作合法价格：当前首日分类先于成交量/close检查，状态本身不证明二者有效。

目标日资格与历史价格输入确实不同，明文例是“目标日全天停牌不参加”而历史全天停牌可延续已证价格（规则第30行）。本结论只纠正历史价格门槛；目标日仍需原有完整窗口及交易资格，08日涨跌仍需官方pre_close。本专项不据历史修复顺带变更目标日筛选。

读取版本：2026-09-12 20:12:15 UTC；HEAD 7272057fcbc5e1bd31c0673ead9f8dc25485e566，含当前WIP。读取前后SHA256一致：tushare_context.py `e82e19a4e8c460b8772624012e8cf8f8b9d88c0b02f2bd503dc5b514b7585f8e`；market_breadth.py `98a3a006c7184e1b6ed4957a6c1b855ebe914a9cde4c4d46ea9c67687164c3a2`。未执行函数、测试或外部请求，未修改代码和测试；这是静态结论，公开RED待主线程安排。
