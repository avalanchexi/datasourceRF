Status: ready-for-agent
Category: bug
Type: task

# 07（02a）— 相同定义：读取与选值跨版本归并

**What to build:** 一个"相同定义版本组"的答案，加上证据仓库的序列读取按它归并。给定指标与目录版本，系统能说出哪些目录版本与它是相同定义（[ADR-0036](../../../docs/adr/0036-observation-identity-by-same-definition.md)）；`metric_series`／`preload_metric_series` 读出这些版本的来源声明，同一统计期＋规范维度归为一个观测，再走现有修订与冲突规则。

**Blocked by:** 无（父票 [02](02-catalog-switch-hides-unchanged-claims.md)）

**勿并行：** 08、09（同改证据仓库）

## 验收

- [ ] 相同定义：比较单位、允许单位、频率、维度、来源代码；两版模型都登记了该指标的派生公式时，公式版本也须相同。名称、优先级、角色、候选网址、认证状态、发布规则不参与。旧定义从内置目录与库中 `registered_metric_catalog` 读取。
- [ ] v0013 下取得的普通指标声明（如 OMO 利率、DR007）在 v0014 下由 `metric_series` 读出；定义变化的指标（信用脉冲单位变化、v0012→v0013 广度来源代码变化）旧版本不读出。
- [ ] 同一统计期、维度的跨版本声明只形成一个观测点；同一来源取最新修订（ADR-0022），跨来源超出 0.5% 判冲突（ADR-0033）。
- [ ] 双向：回退到旧模型时，新版本下取得的相同定义声明也读出。
- [ ] 观测点的 `observation_id` 为请求版本下按身份计算的编号（存储编号不改写）。
- [ ] 受影响测试、两例冒烟、`test_worker_registered_catalog.py`、`test_core_carry_forward.py` 通过；Codex 两轴审查无阻断。

## Comments
