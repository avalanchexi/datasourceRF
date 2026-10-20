# 新模型的 SYSTEM 目标日使用边界

2026-09-18，独立 P2 工作树提交 `26a0b84`，基点 `dc44076`。用户 #26 和 ECB 决定已生效，无待答问题。

新增冻结规则 `point_in_time_rule_version=dual-cutoff-v0003`，PUBLIC 仍要求可靠公开时间，SYSTEM 同时约束实际取得截止及目标日。完整规则见 [实施计划](plan-27-system-target-inputs-20260918.md) 与工作树 `docs/operations/ecb-reference-cross.md`。没有新时间字段、回填历史公开时间、改写旧模型或降低认证/质量条件。

仓库在选择修订版本前过滤目标时间，避免后续 vintage 遮住先前可见值；目标日投影和 ModelInputSelector 使用同一冻结规则。注册模型完整 manifest 必须与已准入版本一致，正反方向临时改写时间字段均被拒收。ECB 的模型输入选择还核验来源原件，与投影一致。

公开反例覆盖规则准入、模型清单改写、损坏 raw/normalized；后续用例覆盖跨日修订、历史 PUBLIC 缺口、DR007/Shibor 实际 SYSTEM、LPR 精确发布与日期精度。仅控制外部时钟/HTTP，合成认证夹具不代表真实来源通过认证。

最终独立离线安装包：**199 passed in 113.24s (0:01:53)，exit=0**。99 源/安装文件、11 选定测试文件和 96 全部测试输入在始终保持一致。Ruff 与 Mypy 通过；安装结果见 [终态回执](verification-27-system-target-installed-final-20260918.json)。之前源码相关回归74通过，属于重构前补验，最终以安装包199项为准。

两轴审查未发现硬问题。Standards 的重复查询参数建议已通过 `_query_at_target` 合并，限定复审通过；SQL 粗筛与 Python 精确时点检查职责不同，均保留。Spec 复核确认符合计划、ADR0006/0012 和用户决定。两名审查者只读，未运行测试。

当前仍未交付：完整 Worker 实际采集路径、真实来源认证、真实候选与120中国交易日回放、显式激活/切换。固定真实验收目标2026-09-11不会自动挪到当前日期；本次9月18日实际取得且PUBLIC未知的数据不会填入较早目标日。MAIN原17项WIP保持，本提交未合并/推送。
