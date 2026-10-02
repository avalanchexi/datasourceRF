Status: done
Category: bug
Type: task

# 07（02a）— 相同定义：读取与选值跨版本归并

**What to build:** 一个"相同定义版本组"的答案，加上证据仓库的序列读取按它归并。给定指标与目录版本，系统能说出哪些目录版本与它是相同定义（[ADR-0036](../../../docs/adr/0036-observation-identity-by-same-definition.md)）；`metric_series`／`preload_metric_series` 读出这些版本的来源声明，同一统计期＋规范维度归为一个观测，再走现有修订与冲突规则。

**Blocked by:** 无（父票 [02](02-catalog-switch-hides-unchanged-claims.md)）

**勿并行：** 08、09（同改证据仓库）

## 验收

- [x] 相同定义：比较单位、允许单位、频率、维度、来源代码；派生指标（模型必备的派生公式所计算的）公式版本也须相同且已知——一个目录的公式只有在所有使用它的模型都写明同一版本时才已知；内置目录、模型缺该公式、多个模型公式不一，都算未知，派生指标不跨版本共享。名称、优先级、角色、候选网址、认证状态、发布规则不参与。旧定义从内置目录与库中 `registered_metric_catalog`（校验哈希与接纳模型）读取。
- [x] v0013 下取得的普通指标声明（如 OMO 利率、DR007）在 v0014 下由 `metric_series` 读出；定义变化的指标（信用脉冲单位变化、v0012→v0013 广度来源代码变化）旧版本不读出。
- [x] 同一统计期、维度的跨版本声明只形成一个观测点；同一来源取最新修订（ADR-0022），跨来源超出 0.5% 判冲突（ADR-0033）。
- [x] 双向：回退到旧模型时，新版本下取得的相同定义声明也读出。
- [x] 观测点的 `observation_id` 是存储键：被选中声明的存储编号（无选中时取首条）；`query`／`trace` 从任一版本的存储编号都能回读该观测全部相同定义版本的声明。不指定版本读取时不跨版本归并。
- [x] 受影响测试、两例冒烟、`test_worker_registered_catalog.py`、`test_core_carry_forward.py` 通过；Codex 两轴审查无阻断。

## Comments

**2026-10-03 实施记录**

- **新模块** `same_definition.py`：`same_definition_versions(connection, database_path, metric_id, version)` 给出与该版本定义相同的全部目录版本。比较 `IDENTITY_FIELDS`（单位、允许单位、频率、维度、来源代码）；派生指标（`catalog._REQUIRED_FORMULAS` 中公式所计算，键为指标名去 `cn_` 小写）另要求公式版本相同且已知——汇总 `model_version` 中所有使用该目录的模型清单，只有全部写明同一版本时才已知。内置目录（v0001/v0002/v0003/margin-financing-v0002）从代码读，公式未知。登记目录按 `catalog_registry` 惯例校验哈希与接纳模型绑定，只在 `shared_read_scope` 内共享，作用域外每次重读；只容忍"no such table"，其余数据库错误传播、不缓存。
- **证据仓库** `evidence.py`：`metric_series`／`preload_metric_series` 指定版本时读出相同定义各版本的声明，按统计期＋规范维度归为一个观测（`_observation_key`），再走原有的每来源最新修订与 ADR-0033 冲突规则（`_select_merged_rows`）；未指定版本时仍按存储编号分组、不归并。版本组在读取所用连接内计算（预载路径复用预载时的组），后登记的目录对已打开仓库可见。观测点编号是存储键（被选中声明的存储编号）；`query`／`trace` 从任一版本的存储编号按相同定义展开回读。`EvidenceRepository.same_definition_versions` 供后续片使用。
- **改写原测试**：`tests/evidence/test_point_in_time.py::test_metric_series_isolated_by_frozen_definition_version` 要求 CPI 在 v0001/v0002 间隔离，而两版定义相同——固化的是被 ADR-0036 取代的旧规则；改为 `test_metric_series_merges_an_unchanged_definition_across_frozen_versions`（同来源取最新修订、两版读出同一结果）。定义变化的隔离由新测试覆盖。
- **过渡状态（只记录）**：原件复核与 TuShare normalized 版本仍按版本严格相等（`evidence.py` `source_claims_matching_registered_contract`、`tushare_context.py` 复核等），跨版本取最新修订后可能被复核拒收——属票 09。实施顺序改为 07 → 09 → 08，09 完成前不跑全套与真实运行。
- **测试**：新增 `tests/integration/test_same_definition.py` 15 例——相同定义判断（v0012/v0013/v0014 实际清单、内置目录双向、派生公式已知且相同、同目录多公式、模型缺公式、后登记可见、哈希篡改被拒）、旧版本声明被新模型读出及回退、跨版本一个观测取最新修订、跨来源跨版本超 0.5% 冲突、定义变化隔离、不指定版本不归并、旧编号 query／trace 回读、预载一致。先红后绿。
- **验证**（`PYTHONPATH=src` 直跑 pytest）：受影响 13 个文件＋两例冒烟＋`test_worker_registered_catalog.py`＋`test_core_carry_forward.py` 共 187 例全过（7 分 43 秒，改动前同范围 182 例 7 分 38 秒）；最后一轮修正后相关 9 个文件 149 例全过（6 分 31 秒）。ruff 通过。
- **审查**（Codex 只读，四轮）：首轮 7 个阻断——不指定版本时误归并、内置目录未参与、公式缺省误判、实例缓存漏后登记目录、登记目录未校验与跨作用域缓存、数据库错误被吞并缓存、原件复核仍按版本（转票 09）；二轮 1 个（内置目录公式未知却归并派生指标）；三轮 2 个（登记入口不强制公式齐全、同目录可被多公式模型复用）；均已修复，四轮无阻断。未采纳的建议：接纳绑定不符、锁错误重试、跨作用域重校验的额外测试（实现已有，内存探针验证）。

