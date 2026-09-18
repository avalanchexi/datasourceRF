# #22 注册来源组件夹具身份修复（2026-09-18）

Status: partial-current-family-regressions-passed

来源选择器的扩大回归发现多组旧测试通过删除 source_certification_packages 把已准入manifest缩成局部回放。完整身份校验已禁止这种做法。修复使用完整保存manifest和公开PUBLIC投影/选值，返回真实结果，未修改产品准入、目录或回放覆盖要求。

本切片迁移范围：融资、两市场指数、估值、日广度、金额广度共7项；PMI、CPI、LPR损坏/缺失和晚修订共22项。市场指标不属于macro的模型输入列表，因此市场节点命名public_selection，证明完整选值、损坏移除成员、comparison不受影响及金额原件恢复。其他三族保持真实macro输入排除、旧期不复活、历史切点、原观察可审计和LPR source_failed。

验证：

- 旧市场夹具7失败22.37秒；迁移初次误把市场声明当macro输入，7失败27.32秒，这是测试假设错误。修正为公开选值边界后[7通过26.84秒](verification-22-market-selection-final-20260918.txt)。
- 旧发布族夹具22失败73.82秒；新[22通过80.64秒](verification-22-release-bound-manifest-20260918.txt)。
- 相关Ruff通过。产品源码未变，不额外重复全源类型检查。

## Standards

硬违规0、判断项0。helper保持真实PUBLIC日末截止、期次与目标日分离；未伪造gap、evaluated_cutoffs或replay output。市场macro相等仅为无关结果保持，不证明市场数据进入macro。

## Spec

本切片无阻断项。**完整回放的聚合分类、覆盖检查和输出封装是从这些组件节点移出的证明**，不能宣称等价恢复；当前版本完整合法生命周期与代表性损坏回放门仍必须执行。warrant输出持久化、RRR/credit/capacity等剩余旧夹具继续逐组处理，最终全套未执行。
