# 17: 获取尝试的归属契约

**What to build:** 每条新写入的获取尝试显式记录所属运行 id、目录版本、品种与日期（适用时）和关联回执，不再依赖"带回执才补入运行"；Worker 不再为整个家族追加覆盖逐项细节的汇总记录。

**Blocked by:** 16

**勿并行：** 02、05、08、10、15、23、24、25、29、30（同改：Worker 编排与取数；证据仓库；逐区明细见 [README](../README.md)「串行约束」）

**Status:** ready-for-agent

来源：[架构评审](../README.md) 候选 4 差异 16、19、20（用户判定为遗漏，2026-09-29），并为 19、20 两票提供前提。 规格：[spec.md](../spec.md)「五、获取结果模块」。

## 现状

- `record_retrieval_attempt`（`evidence.py:1296`）只在收到 `acquisition_ids` 且都关联到同一运行时补入 `run_id／target_business_date`；缺凭据（`worker.py:1573`、`:1761`）、Worker 汇总记录（`worker.py:1663`）、核心历史（`core_history.py:189`）、LPR 失败（`official_lpr.py:430`）没有可靠归属。
- TuShare 上下文底层成功记录不带品种（`tushare_context.py:1155`），Worker 失败包装记录带（`worker.py:1924`）；单日补缺走前者（`targeted_context.py:159`），清不掉直接刷新留下的品种失败（差异 16）。
- EIA HTML 底层已逐指标写 `verified_candidate／missing_values`（`eia_html.py:458`），Worker 又按整个循环有无异常给两指标统一写成功或失败（`worker.py:1609`–`:1634`），覆盖逐项结果（差异 19）。
- 郑商所尝试有 `business_date＋symbol`，但没有目录版本（`czce_warrants.py:439`）（差异 20）。

## 已定决定

- 归属字段由模块（票 16）定义，写入方填写；缺凭据等未发请求的记录允许"有运行、无回执"。
- Worker 只记自己的决定（缺凭据、未配置），获取细节由实际执行的适配器记录；家族汇总由获取结果模块读取时生成，不再落库。
- 旧记录不迁移：`retrieval_attempt` 随留存期删除（`retention.py:167`），过渡期读取端对无归属旧记录退回时间区间。

## 验收

- [ ] 所有获取尝试写入点带运行 id 与目录版本；仓单带品种与日期；TuShare 成功与失败记录的品种字段一致。
- [ ] EIA HTML 不再被 Worker 二次概括；某一项失败不改写另一项的结果。
- [ ] 按 TDD：缺凭据记录可按运行 id 取到；TuShare 单日补缺成功能与同品种失败对上；EIA HTML 一项成功、一项失败时两项结果各自保留。
- [ ] 受影响测试经 `check.py quick` 通过；切片收尾冒烟通过。
- [ ] 代码审查无阻断。
