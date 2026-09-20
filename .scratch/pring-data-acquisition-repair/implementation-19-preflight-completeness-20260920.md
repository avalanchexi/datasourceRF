# #19 预检完整性：点时密度与运维证据可见性（2026-09-20）

基点 `dc65c98`。起点是该提交的两轴复核中规格轴的 (a)(c) 两条发现，均已逐行核实属实后实施。一次冻结、批量实现、一次验证——今天已因分批改动重跑过一次 1 小时 38 分的重型验收，不再重复该代价。

## 切片 1：密度绕过点时（规格轴 (c)）

`material_preflight.py` 统计日频覆盖时，`observed` 只要求 `public_available_at is not None`，**从不与该 business_date 比较**。后果是覆盖率检查退化为「这行有没有发布时间」，而不是「这一天当时看得见吗」。

反例 `test_density_counts_only_values_public_by_their_own_business_date`：20 个交易日的融资余额全部在 2026-09-14 才公开，窗口为 8 月末的 20 日。实际 RED——`daily_coverage_missing` 为**空列表**，一个整窗全部事后发布的材料被判为完全覆盖。

修复：`observed` 增加 `item.public_available_at <= public_cutoff(item.period_end)`。GREEN 后预检文件 30 passed / 89 秒，收紧口径未误伤任何既有用例。

顺带消除标准轴指出的重复：`datetime.combine(..., time.max, ZoneInfo("Asia/Shanghai"))` 原在三处逐字重复（窗口末日 cutoff、逐日 `historical_cutoff`、核心历史 cutoff），现统一为 `public_cutoff(day)`，接受 `date` 或 ISO 字符串。

## 切片 2：两项 P0 从清单消失（规格轴 (a)）

`material_preflight.py` 按 id 裸 `continue` 跳过 `CN_TRADE_CALENDAR`、`CN_RELEASE_SCHEDULE`、`SOURCE_OBSERVED_AVAILABILITY`。日历另有专项检查，但后两项实为 **P0 / awaiting_source_certification**，材料全缺也不产生任何条目——在结果里与「已通过」不可区分。它所仿照的 `full_retrieval.py:213-220` 则保留 `{"metric_id": ..., "status": "operational_evidence"}` 逐项记录。

反例 `test_operational_evidence_stays_visible_instead_of_vanishing`：实际 RED 为 `KeyError: 'operational_evidence'`——结果里根本没有这一项。修复后预检结果新增按 metric_id 排序的 `operational_evidence` 数组，与运行计划口径一致。「P0 运维证据不伪装标量」由此恢复为「不伪装标量，但仍然可见」。

## 切片 3：维度专项——判定为合同上不可达

尝试为 `CN_MARGIN_BALANCE`（要求 `financing_balance` 与 `financing_buy_amount` 两个 measure）构造缺成员反例，两条路都被合法公开守卫在**产生任何声明之前**拦住：

1. 持久化时过滤掉该 measure 的标量 → `registered_margin_acquisition_values_mismatch`
2. 原件本身去掉 `rzmre` 列 → `tushare_response_required_field_missing`

与本票历史上日历声明分支同型。按既定规矩不绕合同造夹具，该测试已撤除，**未留失败用例，也不记为产品 RED**。后续方向见[剩余检查评估](plan-19-preflight-remaining-checks-20260920.md)新增段落：换成员集合合法可变的家族，或逐家族核对后把 `dimensions` 从 `pending_checks` 移出并记为合同上不可达。

## 验证

Ruff、格式、`mypy src/pring_cycle/material_preflight.py`、`git diff --check` 全部通过。

- 预检文件显式重型验收：**30 passed / 89.08 秒**。注意 `tools/check.py quick` 现已正确拒绝该文件并要求显式重型——这是 `dc65c98` 中标准轴 `HEAVY_FILES` 修复的实地生效。
- 相关回归 16 文件：**926 passed / 2503.58 秒（41 分 43 秒）、退出 0**。较上一轮少 28 项，因为预检文件已划归重型单独执行。超 180 秒快速反馈目标，如实记录。
- 同版本默认全套：见下节。

改动范围仅 `src/pring_cycle/material_preflight.py` 与 `tests/models/test_material_preflight.py`。

## 本项不代表什么

`checks_complete=false` 保持，`pending_checks` 五项一项未减。点时的**其余模式**（任意双截止 SYSTEM 回放）、完整目录的逐项汇总、全公式父项诊断范围、完整有效材料正例与生命周期接入均未完成。#19 验收条件不勾选；真实来源认证与真实候选依赖不变。

## 同版本默认全套

驱动 `verify-current-full-v10-20260920.py`，收据 `verification-current-full-v10-20260920.json`，日志 sha256 `b1c4024a4a057dc676a6144e2883c782fce7b7eb898bcb2aa7925230c671574f`。

- **exit_code 0、1891 passed、10725.31 秒（2 小时 58 分 45 秒）、`supervisor_reason=null`**
- 范围 `default discovery, no selectors`；**0 skipped、0 deselected**
- `frozen_inputs_unchanged`/`source_inputs_unchanged`/`installed_artifact_unchanged` 三项均真
- 基点 `git_head=dc65c98` 加本批未提交改动；软件输入 231 条、安装制品 103 文件，解释器自 SITE 导入
- C 盘 4.03→3.64GiB，basetemp 峰值 60.51 GiB，与上轮一致

1891 项较上轮 1889 多 2 项，即本批新增的两个反例。

### 耗时增加的归因订正

总耗时自上轮 8273.68 秒升至 10725.31 秒（+2452 秒，+30%）。**我最初怀疑是新增的点时密度检查**（每条 vintage 构造当日截止时刻），这个猜测**不成立**，证据有三：

1. 慢用例榜首 `test_integrated_worker_core_gap.py::test_missing_core_delivery_blocks_a_full_run_and_keeps_its_original` 从上轮 53.11 秒升至 1015.74 秒，而该文件**完全不涉及预检**（grep 无任何 preflight 引用）。
2. top30 合计 6129.73→8689.70 秒，增量全部集中在重型用例，不呈现"每个日频指标多一点"的弥散特征。
3. 决定性证据：两轮收据的 `material_bindings`。v9 两个 profile 的材料 key 均 `cache_exists=true`（热）；v10 因本批修改了 `src/pring_cycle/material_preflight.py`，材料身份绑定的 `code_hash` 随之改变，两个 key 全变且 `cache_exists=false`，整轮走了冷材料构建。

**结论：+2452 秒是冷材料构建的成本，不是点时密度检查的成本。** 冷构建恰好落在 core_gap 用例上，使其看起来异常。若按最初的猜测去为 `public_cutoff` 加缓存，就是照着错误的靶子改代码。

这也说明一条通则：任何 `src/pring_cycle` 内的改动都会使材料缓存整体失效，下一轮全套必然包含一次冷构建；比较两轮全套耗时前必须先核 `cache_exists`，否则会把冷热差异误读成代码回归。

## 自查发现的未决语义问题（密度修复）

修复把 `observed` 的条件改为 `item.public_available_at <= public_cutoff(item.period_end)`——即「该期次的值在**它自己那一天结束前**已公开」。这与逐日 `select` 用当日 `historical_cutoff` 的模型一致，但它是一个**语义选择，不是唯一解**：

- 另一种合理读法是「在**评估截止**（窗口末日）前已公开」。两者在「某来源习惯次日早上发布当日数据」时结论相反：按当前规则每一天都会被判为覆盖缺口，按后者则完全正常。
- **现有测试无法区分两者**：夹具 `synthetic_public_scalars` 一律把发布时间设为期次当日 08:00 UTC（上海 16:00，当日内），所以全套 1891 项通过**不能证明**次日发布场景下的行为正确。该方向目前完全未测。
- 真实 TuShare 标量的 `public_available_at` 默认为 `None`（适配器不编造发布时间），已被原有条件排除，故本改动当前只作用于确实携带发布时间的来源。影响面因此有限，但不为零。

**结论：本项修复关闭了「密度完全不看点时」这个洞，但没有确定「点时」在密度维度的正确口径。** 下一步应先补一条次日发布的反例，据实际期望确定口径，再决定是否调整。在此之前不得宣称 `point_in_time` 在密度维度已完成；`pending_checks` 保留该项本身也正确反映了这一点。
