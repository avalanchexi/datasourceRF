# #22 同版本默认全套（2026-09-20）

## 结果

驱动 `verify-current-full-v9-20260920.py`，收据 `verification-current-full-v9-20260920.json`，日志 `verification-current-full-v9-20260920.txt`（sha256 `06a9c1b09fafdcc80aa4312b39f20be9b4ca95d4e09f10bbb58abc8bc654d6ec`）。

- **exit_code 0、1889 passed、8273.68 秒（2 小时 17 分 53 秒）、`supervisor_reason=null`**
- 范围：`default discovery, no selectors`——不传选择器，pytest 默认完整发现
- `frozen_inputs_unchanged=true`、`source_inputs_unchanged=true`、`installed_artifact_unchanged=true`
- 基点 `git_head=c5f079601e23fb2ad60a322473060e6095ea14ed` 加本批未提交改动

## 冻结与安装身份

- **软件输入 231 条**（`src/`、`tests/`、`tools/` 加 `pyproject.toml`、`uv.lock`、`.python-version`、`README.md`），冻结副本与源码树逐一相同
- **安装制品 103 个文件**，经 `uv pip install --no-deps --target` 离线构建，与 `src/pring_cycle` 逐字节一致；非 editable
- 解释器实际从 `/tmp/datasourceRF-current-verify-20260920-v9/site/pring_cycle/__init__.py` 导入，已由子进程自身探针确认，不是工作树也不是 dev-venv 里那份主目录旧安装
- 材料身份两个 profile 均记录并命中缓存：`legacy` key `1b92d28d1232e3e7…`、`acquisition-repairs` key `92bc920c0aaefdbf…`

全套通过后又修改了 `docs/agents/testing.md`，随后复算软件清单仍为 231 条且与收据逐一相同——文档是验证输出不是软件输入，故不使收据失效。这实地验证了本批[软件输入身份切片](implementation-22-software-input-identity-20260919.md)的设计意图。

## 资源实测

C 盘起 2.44GiB、终 4.08GiB（不降反升，Windows 侧自行回收，与本次运行无关）；VHD 内部终值 713.5G；**basetemp 峰值 60.51 GiB**。

前一次尝试（v8）在 45% 因旧口径的 C 盘保护中止，已记为环境中断且不构成通过结论，详见[磁盘中断诊断](diagnosis-22-full-suite-disk-abort-20260920.md)。本次保护改为 C 盘 1.5GiB 与 VHD 内部 50G 双门，依据是「写入 4GiB 而 C 盘纹丝不动」的实测。

## 本批覆盖的改动

`tools/inputs.py`（新增，软件输入清单与实际导入发行物）、`tools/check.py`（重型清单补入 `test_material_preflight.py`、格式修复）、`src/pring_cycle/search_evidence.py`（族校验按期收窄、采纳循环与其同源）、`src/pring_cycle/metric_contracts.py`（`event_period_limit`、密度公式唯一定义）、`src/pring_cycle/worker.py` 与 `warrant_inputs.py`（改调共享密度函数）、`src/pring_cycle/material_preflight.py` 等 #19 预检 WIP、`tests/maintenance/test_verification_inputs.py`、`tests/models/test_registered_commodity.py` 新增两项、`docs/agents/testing.md`。

## 本项不代表什么

本全套只关闭**软件**验证这一层。真实来源认证、真实完整候选、120 日真实配对检索、真实产品交付与系统切换均不在其内；#19 预检 `checks_complete=false` 保持，#19/#22 的真实交付验收条件继续不勾选。

## 两轴复核：规格轴

独立规格轴子代理两次进入 idle 但结论始终未送达，已两次请求。为不让提交无限期挂起，以下由本会话自行核对，**独立性弱于标准轴，如实标明**；若该子代理后续交付结论，以其发现为准另行处理。

**(a) 要求但仅部分实现**

- #19「逐项预检**完整目录、维度、原件、点时及派生父项**；材料无法通过时列出具体缺件」——**部分**。`pending_checks` 五项全部保留、`checks_complete=false`，维度无专项反例、全公式父项诊断范围未审、日历声明分支资格未验。已在[剩余检查评估](plan-19-preflight-remaining-checks-20260920.md)逐项列明，**未在任何记录中宣称该条完成，#19 该验收条件不勾选**。

**(b) 未被要求的行为（范围蔓延）**

- `worker.py:1207` 与 `warrant_inputs.py:76` 改调 `minimum_context_daily_observations`：#19/#22 均未要求，来自 code-review 对既有重复的发现。理由是阈值漂移会使 worker 准入门与 evaluation 判定失配，且当时重型验收本就要重跑，边际验证成本为零。**属蔓延，已记录理由，不掩饰。**
- `tools/inputs.py` 的 `imported_package()`：超出「输入清单接入实际驱动」的字面要求，但直接服务于已确认规则「执行时先核对工作树、源码与安装制品、依赖、测试及软件验收实际使用的配置和材料身份」——本环境恰好存在 dev-venv 装的是主目录旧构建这一真实风险，故判定为规则内而非蔓延。

**(c) 看似实现但实现有误**：未发现。期收窄的行为等价性经两条路径确认——事件指标在质量检查前即只保留最新期次，更早的点无法被采纳；标准轴独立复核亦确认 `adoptable()` 与采纳循环判定逐字等价，且回退 `search_evidence.py` 至 HEAD 后只有新增的那条反例失败。

**(d) 本会话另行核对的 #22 明文要求**

- 「默认全套确实覆盖原完整运行跨期共享硬搜索预算失败行为」——成立：`test_full_run_shares_hard_search_budget_across_periods` 在默认收集内，随 1889 项全部通过。
- 「不默认排除 slow/live」——成立：日志中 **0 skipped、0 deselected**。
- 「保存实际退出码、结束时间、日志及前后指纹」——成立：收据含 exit 0、耗时、日志 sha256 与前后三项身份校验。

**(e) 记录准确性自查**：本批记录中所有「通过」均绑定实际收据与退出码；v8 的 45% 中止明确记为环境中断且不构成通过结论；成本对照明确标注为「探针而非同版本收据」；整窗预检明确标注跑的是合成隔离输入、不代表真实候选就绪。未发现以合成材料冒充真实来源认证的表述。

### 规格轴独立结论（后到，已并入）

独立规格轴最终交付，三条发现，均经本会话逐行核实属实：

- **(a) 完整目录漏两项 P0**：`material_preflight.py:101-106` 裸 `continue` 跳过 `CN_RELEASE_SCHEDULE`、`SOURCE_OBSERVED_AVAILABILITY`，而仿照来源 `full_retrieval.py:213-220` 保留 `operational_evidence` 条目。
- **(b) 范围蔓延**：密度常量去重确在本批要求外，代价是作废并重跑 1 小时 38 分重型验收——与本会话自查结论一致。
- **(c) 实现有误**：密度统计从不比较 `public_available_at` 与 business_date，`point_in_time` 在密度维度未生效。

其对实施记录的真实性核查未发现虚报，唯一偏松处是「必需 gaps 0」缺少限定——该措辞已补上两条限定，见[预检实施记录](implementation-19-material-preflight-20260919.md)。(a)(c) 已并入[剩余检查评估](plan-19-preflight-remaining-checks-20260920.md)作为下一切片的优先驱动。

**为何不在本批修复**：(a)(c) 都要改 `material_preflight.py`，即作废刚通过的 1889 项全套（约 2 小时 18 分）。它们不是本批引入的回归，而是 #19 预检 WIP 的既有缺口，且该票 `checks_complete=false`、五项 `pending_checks` 全部保留，从未宣称完成。因此按「先提交已验证的检查点，再以反例驱动下一切片」处理，而不是在一次提交里无限滚雪球。

本会话自行做的规格核对遗漏了 (a)(c) 两条，独立轴的价值在此得到验证——两轴分离不该因子代理迟交而被我自己的核对替代。
