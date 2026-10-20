# 最新资格失效被丢弃导致旧窗继续可用

2026-09-11，生产修改前记录。253运行期间生产保持248版本不变。

[253实际日志](verification-credit-window-quality-red-joint-253.txt)为8失败、20排除、145.85秒；GDP/社融 × quality invalid/awaiting source certification × PUBLIC/SYSTEM全部错误返回available，期望missing_certified_inputs。[254根核验](verification-credit-quality-red-254.json)确认315输入/4保护、前后53依赖/91源码/95包文件、实际退出1、进程结束和卷卸载。

每例公开导入35份原件（原34父项加一更早季度或月份），先核原父项和有效收据，再用公开追加声明接口记录对同一最新原始值的合成质量/资格复审。新声明保留原件、值和公告时间，追加available_at，并在两模式明确确认新声明已是该期selected claim；未直接写数据库、patch选值或损坏制品。此合成复审只验证资格消费，不声称已经认证真实历史修订PUBLIC时间。社融额外月份经[公开解析252](verification-credit-quality-fixture-252.json)验证9字段。

根因：`_credit_impulse_proxy`的直接月社融、累计社融、直接季度GDP及累计GDP四条列表都在保留期次之前应用`_certified_point`。合格标签变化使最新点被删除，后续窗口长度、连续性、原件完整性与GDP末期约束看到的都是已退后的序列，故仍可产生旧窗口派生值。上一轮末期约束只能识别仍在序列中的非正差分，不能识别已被过滤的最新点。

影响：两种点时、社融/GDP两类输入，及共用此消费者的旧内置目录均受影响；直接值路径拥有同一筛选结构，也应遵守“先选完整必要期次，再审核父项资格”。派生trace和模型采用ID不可在坏最新输入被丢掉后照常产生。

修复范围：四条列表保留在查询点时确实可见的期次，窗口及差分父项选定后统一核其`_certified_point`资格，再执行原件/规范化联合校验和GDP相容性。只保留`point.claims`非空的点：SQLite julianday粗过滤可能产生严格截止前尚无claim的空点，不能把它冒充已可见期次而提前阻断。未选更早坏件继续不阻断；任何必需父项不合格都返回既有missing_certified_inputs及空采用ID，在派生写入前停止。无新公式、字段、认证授予或历史覆盖。

验证：新增8例RED后，联合运行完整28个新目录窗口场景与20个既有回归，并作类型/格式检查和两轴审查。社融最新差分因前月实际缺期而消失的窗口末期约束、数值修订的真实PUBLIC/SYSTEM矩阵及消费者/Worker仍须独立收口；本轮不以合成资格复审替代这些验收。
