# Standards — P2 可选依赖与回放存档

固定基点：`99c495a217b66d4bca9d6ceae4688ee69d4382bb`。本次确认 HEAD 同基点、其后提交列表为空；只审指定五文件的 P2 增量，未运行应用、测试、WSL、SQL 或网络。

## 明文标准违反：1

**高：可选 P2 的已采用输入被同时豁免资格与完整性校验。** `src/pring_cycle/model_outputs.py:551–558` 新增 `metric_id in required_metrics`，使可选 P2 跳过 `621–676` 的成员、认证、质量及 reported_value 校验，即使该点已列入 `macro.model_input_observation_version_ids`。前面的 `596–620` 只验证关联、值、单位和时间。静态反例：保留合法 current 行和采用 ID，将对应 claim 的质量改成 invalid／认证改成 awaiting，或把该指标的 source_inputs 清空，仍可通过这一路校验。上述反例尚未由本审查运行复现。

依据：`CONTEXT.md:268` 明确 P2 “仍须完成来源认证才能进入正式投影”；`docs/adr/0012-atomic-model-versions-and-parallel-replay.md:7` 要求认证区间内的质量与回归验收；规格 Testing 11 要求回放检查完整性与认证生效。允许无值不应允许已采用坏值。建议将“必须存在”与“实际采用须合格且可追溯”分开，通过公开存档／validator 反例覆盖，并按当前 scope 核对引用，避免误拒绝范围外合法核心日历 ID。

## 启发式建议：0

未发现新增实质气味。共享 scope 的必需公式依赖分类保留 GDP 对信用脉冲的必需关系；评价侧 `model_evaluation.py:881–894` 仍检查可选公式实际输出的非空血缘。存档接口原有逐公式血缘检查不足已另报主代理，不重复计入本次新增问题。

新测试沿公开准入、评价和存档校验边界；当前修正后的未知 PUBLIC 正例排除确切 P2 claim ID，不再错误要求所有采用 ID 为空。本报告不代表新目录 120 日回放、来源认证或激活验收。
