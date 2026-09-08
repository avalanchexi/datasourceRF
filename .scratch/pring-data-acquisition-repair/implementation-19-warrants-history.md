# 仓单历史完整日覆盖

基点 `b8cf9b3`。本批修复新登记目录的Worker仓单覆盖门；正式来源认证、真实完整候选和120日重放仍未完成。

旧Worker按“品种当天存在一个已认证当值”计天，原件中另一个仓库缺值也可能被计入密度。现在投影在原有逐期解析中复用 `select_warrant_inputs` 的完整交付结果，返回每品种已通过原行、字段、修订和全部仓库当值检查的日期。Worker先据此要求120个唯一目标交易日内，每品种至少114个完整日，再执行原当前成员、认证、鲜度及密度检查。未改变既有95%规则，也未把它提高为八品种日期交集达到95%。

PUBLIC与SYSTEM继续使用各自可见的声明和交付顺序，目标期次由已有目标约束仓库过滤。未知值不填零，可选字段不充当缺失的当值；定义未认证时不产生可用历史覆盖。旧内置目录保持旧行为。新增覆盖结果是投影到Worker之间的输入事实，不是独立的正式来源认证，也不写入模型生效或真实回放记录。

## 验证范围

公开 `build_context_projection` 入口使用已保存CSI原件的120个实际日期（2026-03-09至2026-08-28）；仓单数量、时间和认证均为明确合成夹具。铜第二仓库缺6天得114，缺7天得113；119个日期或重复的第120个日期均不可用。额外用例让铜和PP分别缺6个不同日期，二者完整日期交集为108天，各自114天仍可通过，防止无意收紧规则。

[RED](verification-warrants-history-red-01.txt)2失败，84.91秒，暴露原公开投影没有历史完整性事实；[首轮GREEN](verification-warrants-history-green-01.txt)2通过，42.45秒。此RED证明新增公开能力缺失，旧Worker计天缺陷另由原函数条件定位，没有伪称已在真实生产任务中重现。

新增错开日期用例后的[关联回归](verification-warrants-history-associated-01.txt)219项全部通过，471.53秒；[mypy](verification-warrants-history-mypy-final.txt)87文件通过，[Ruff](verification-warrants-history-ruff-final.txt)、[格式](verification-warrants-history-format-final.txt)4文件通过，[86份安装源码](verification-warrants-history-fingerprint.json)一致。Spec和Standards静态审查分别0项。精确文件绑定见[检查点](verification-warrants-history/checkpoint.json)。投影测试没有激活新正式候选，也没有替换Worker认证门；Worker接线经静态两轴复审及既有运行回归验证。真实新目录Worker发布仍依赖合法完整候选，不能用本批通过替代。

## 下一步

继续新登记目录三核心采集与选值入口；当前 `refresh_core_history` 查目录未传数据库路径，修正后还有三核心注册来源契约未接通。随后仍需实际来源/时间认证、未冻结业务规则、真实模型输入/报告与120日逐点时验收。整个项目和票19、21保持未完成。
