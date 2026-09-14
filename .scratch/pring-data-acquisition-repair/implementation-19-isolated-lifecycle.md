# 票19 完整合法隔离生命周期材料

2026-09-14起。基线HEAD `c566702`（票12 `59b7ce5`及既有成果三批提交之后，见[分批提交记录](wip-batches-commit-20260914.md)）。沿用已确认公开边界：`model-source-certify`准入 → 机器校准 → 对当前active的精确120交易日回放 → 显式激活；只替换外部transport与时钟，合成PUBLIC时间以`synthetic:`发布事件标识，不登记为真实来源认证，不接触正式运行库。

## 探针 probe-19（只读能力摸底，不是验收测试）

[脚本](probe-19-lifecycle-20260914.py)、[日志](probe-19-lifecycle-20260914.log)、[回放缺口](probe-19-lifecycle-20260914-gaps.json)。原生运行库`/home/tywin/.cache/pring-cycle/verification/probe19-20260914`，工作区源码经PYTHONPATH加载。

1. 隔离对照基线沿用既有测试先例：内置`model-v0001`以`CALIBRATION_BASELINE`记录验收后激活（非强化规则）。候选本身不走任何捷径。
2. `prepared_request`合成完整61项请求经公开CLI准入成功。
3. [core-transport-196](core-transport-196/receipts.json)真实原始字节经`TushareCoreAdapter.acquire_core_bars`采集，三核心各2345日；候选目录声明挂接采集收据，v0001对照目录为fixture声明；PUBLIC均为交易日08:00 UTC的合成时间。
4. **机器校准通过**：asset_direction_changes 21、formal_stage_changes 11、fast_reversals_20d 0、median_confirmation_delay_days 23；评估1995日、输入2338日、起点2017-01-03；26.0秒。
5. 回放2026-03-09—08-28：120个共同交易日，`quality_passed=false`，48项缺口，48.7秒（缺口时提前返回，不代表完整回放耗时）：
   - `candidate_context_evidence_missing` 45项：CSI300/500/1000、CNY030、930916、NHCI、估值、融资、日广度2项、窗口广度2项、金额占比、商品篮子/贡献、仓单8品种、DR007、Shibor、OMO利率/金额、RRR、LPR、PMI×3、CPI/核心CPI/PPI、工业增加值/财务、产成品库存、存货周转、产能利用率、M1M2、社融总量/分项、贷款结构、工具流动性。
   - `candidate_context_sources_uncertified:CN_GDP`：GDP为P2但是信用脉冲必需输入，完整材料须按`admitted_gdp_manifest`先例将其定义标为certified并提供合法输入。
   - `comparison_context_evidence_missing:CN_LPR_1Y_5Y`：v0001对照侧也需LPR窗口证据。
   - `candidate_context_formula_output_missing`：7个公式随输入缺失。

## 实施方案

公开验收测试新建于`tests/models/`：完整合法候选经准入、校准、回放、激活成功，旧active被替代、正式投影/发布历史不写；回放缺口必须为空。TDD以探针同形态的实际缺口为RED，按家族逐个接入，每次以缺口清单缩小为观察点；不预先堆全部家族，不镜像实现公式。

家族接入顺序（复用已提交的各家族公开采集/审查辅助，扩展到回放窗口及必要预热）：

1. LPR（候选与对照两侧）、银行间DR007/Shibor、OMO利率/金额、RRR
2. 官方宏观：PMI×3、CPI/核心CPI/PPI、工业、库存、M1M2、社融、贷款、工具流动性；GDP certified及信用脉冲；Q1产能映射
3. 市场：六指数、估值、融资、日广度、窗口广度（120日预热）、金额占比、仓单8品种
4. 商品篮子/贡献（需11期货输入与固定基点）

材料复用：同一源码指纹下将构建完成的隔离运行库及内容寻址目录保存为不可变快照（附清单：源码/依赖/输入/模型身份/各阶段收据），不同状态测试各自复制使用；指纹不符即重建。票17 Worker验证消费同一快照。每次运行按本目录既有`verification-*`形式留终态；重型任务一次一个。
