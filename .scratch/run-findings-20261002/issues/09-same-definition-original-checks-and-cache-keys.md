Status: ready-for-agent
Category: bug
Type: task

# 09（02c）— 相同定义：原件复核与缓存键

**What to build:** 旧版本声明能通过各来源的原件复核并被采用；按版本组成的缓存键在相同定义下命中。

**Blocked by:** 07

**勿并行：** 07、08

## 验收

- [ ] 原件复核认相同定义版本组：TuShare 一般／银行间／仓单 normalized 标量的版本、ECB 声明与原件参数、美债原件参数、`source_claims_matching_registered_contract`、`acquisition_outcome` 的版本条件。
- [ ] 仓单解析缓存键、检索负缓存键在相同定义下命中同一结果，定义变化时不命中。
- [ ] 回归：v0013 下取得、带原件的声明在 v0014 下通过可采用复核并进入投影（OMO 利率基准沿用、DR007 政策利差算出）。
- [ ] 受影响测试、两例冒烟、`test_worker_registered_catalog.py`、`test_core_carry_forward.py` 通过；Codex 两轴审查无阻断。

## Comments
