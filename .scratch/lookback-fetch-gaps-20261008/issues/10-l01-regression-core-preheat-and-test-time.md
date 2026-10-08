Status: ready-for-agent
Category: bug
Type: task

# 10：L01 后的回归——同日第三次运行三核心预热未读入；受影响测试变慢

## 现象（L08 在 rebase 到含 L01 的 main 后发现，2026-10-08）

1. `tests/integration/test_retention.py` 中 L08 新增的核心用例：同一目标日**连续第三次**运行时，三核心都变成 `insufficient_history`，模型输入只剩窗口内 120 条，本轮取到的预热没有读进来。rebase 前（基于 130a337，不含 L01 `aa46a60`）同一用例通过；把 `retention.py` 换回 main 版复跑，结果相同——疑为 L01 引入。L08 已把该用例的"已知代价"断言移到第一轮之后，未修此问题（见 [L08 票面](08-pre-window-lookback-claims-untraceable.md) 实施记录）。
2. 受影响测试耗时从约 423 秒变为约 1287 秒；L01 自报冒烟从约 41 秒变为约 238 秒。L01 票面"残余风险"：历史期放行后 PMI、CPI/PPI、M1/M2、社融、GDP 每个历史期再按期请求 TuShare，受分钟限额等待。

## 要做的事

- 用二分或对照（130a337 与 aa46a60）复现并定位现象 1 的根因，先写会失败的回归测试（同一目标日连续三次运行，三核心历史充足），再修复。核心趋势计算逻辑本身不得改变（L08 方案 B 的约束）。
- 核实现象 2 的来源：是测试替身里的限频真实等待，还是生产路径多出的请求。生产上新增请求属于 L01 的既定行为；若只是测试替身等待，按仓库惯例让离线测试不真实 sleep。若涉及"历史期要不要再请求 TuShare"的取舍（与 L03 相关），按推荐方案实现并标 needs-info。

## 验收

- [ ] 回归测试：同一目标日连续三次运行，三核心不出现 `insufficient_history`（修复前红、修复后绿）；L08 的已知代价断言可恢复到原位置。
- [ ] 受影响测试与冒烟耗时回到 L01 前的量级，或在票面写明不可避免的原因。
- [ ] 受影响测试、冒烟、重型两例通过；Codex 两轴审查无阻断。

## Comments

### 2026-10-08 追加现象 3（L04 发现）

`tests/integration/test_gap_source_repairs.py::test_the_basket_is_chained_from_its_base_on_settlements` 在 HEAD 源码上失败、在 130a337（L01 前）源码上通过：断言篮子与板块贡献不应出现在缺口里，现在出现了。疑同为 L01（aa46a60）引入，一并定位修复。
