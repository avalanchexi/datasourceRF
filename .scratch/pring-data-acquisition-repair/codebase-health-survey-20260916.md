# 代码健康巡检（只读，2026-09-16，基线 `9929b45`）

冻结全套进行中，本轮不改任何文件，只列候选与理由，供下一批排期。源码 39,347 行、测试 46,460 行。

## 优先级 1：按家族重复的选择链

`search_evidence.py:114 select`（261 行）为每个家族重复同一段形状：取本家族指标的点位、判断非内置目录、调用该家族的 `*_claims_matching_acquisitions`，再把有效声明并进 `selected_ids`。票17 期间已经在商品与广度两处抽出 `claims_checked_once`，但**调用侧的重复仍在**，每加一个家族就要再抄一遍。

建议接缝：把"家族 → 指标集合 → 复核函数"做成注册表，`select` 只遍历注册表。收益是新增家族只加一行，且每个家族的 scope 条件写在一处。风险中等：这是完整运行每次选值都会走的热路径，改动要有等价性验证（票17 已有的 Worker 用例能覆盖）。

## 优先级 2：上下文适配器模块过大

`tushare_context.py` 2,697 行，`TushareContextAdapter` 26 个方法，同一模块里还塞着 `ingest_context_scalars`（1541 起）、`summarize_context_source_smoke`、`smoke_*`。这与拆分前的 `futures_inputs.py` 形状相同：采集、入库与体检混在一处。

建议按刚做过的同一方式拆：适配器（对外请求与解析）、入库（声明写入与发布时间规则）、体检（smoke）。`official_context.py`（2,453 行）是同样的形状，可同批处理。

## 优先级 3：上下文投影的长函数

`context_projection.py` 2,453 行，四个长函数占去大半：`_derived_market_context_rows` 394、`build_context_projection` 339、`_credit_impulse_proxy` 262、`_metric_rows` 236。投影装配、派生行计算、信用脉冲三件事互相独立，可以分成三个模块，装配层只负责按规则拼装。

## 优先级 4：CLI 命令分发

`cli.py:100 _v1_command` 541 行，是全仓最长的函数，一个分发函数里平铺了所有命令。按命令组拆成若干函数（模型生命周期、采集、报告、运维），分发只留路由。

## 优先级 5：验证级联

`source_contract_review.py:111 require_registered_source_contract` 438 行，一连串规则顺序执行。适合改成"规则列表 + 逐条执行"，每条规则带自己的名字和错误码，便于定位与新增。

## 优先级 6：超大测试文件

`tests/models/test_candidate_admission.py` 15,233 行（全套 656 项里多数在这里，单组耗时 1,040 秒）。它同时覆盖准入、目录绑定、容量映射、国债与派生等多个主题。按主题拆成几个文件，能让失败定位更快，也便于分组并行。注意它是材料构建器之一，改动会触发材料重建，要和其他失效改动攒在一起。

## 不建议现在动

- `evidence.py`、`worker.py`、`models.py` 虽然都超过 1,300 行，但职责集中、最近改动频繁且刚验证过，拆分收益不明显。
- `tests/adapters/test_commodity_basket.py` 的 mypy 问题已在 `503e318` 修掉。

## 执行建议

每批只做一项，先写等价性验证再动结构；涉及 `src/` 或构建器的改动攒到同一次材料重建。优先级 1 与 2 的收益最直接：前者消掉每加一个家族就复制一段的重复，后者复用刚刚在期货读取器上验证过的拆法。
