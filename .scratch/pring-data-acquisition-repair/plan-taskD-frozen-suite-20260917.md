# 任务 D：同版本冻结全套的执行前冻结（2026-09-17）

## 为什么要重做

[2026-09-16 夜间的合并验证](verification-taskD-20260916.md)覆盖的是 `9d44c7d`/`fcebc3d`/`d24d4aa` 那一版：轻量全套 1667 通过、材料两文件 12 通过/51:16。此后 `a6c93f1` 按两轴复审返工，又改了三个源文件：

| 文件 | 改了什么 |
|---|---|
| `src/pring_cycle/worker.py` | `_is_lock_contention` 只重试锁占用；放弃阈值提前一个心跳间隔 |
| `src/pring_cycle/cutover.py` | 读时同时接受 `reported_seconds` 与旧键 `measured_seconds` |
| `src/pring_cycle/search_evidence.py` | 删除未用 `scope` 参数；指标 id 去重；家族结果随家族携带 |

**源码一改，上一版的全套结论就不再是"同版本"证据。** 票17 最后一项要的正是同版本冻结全套，所以必须在 HEAD 上重跑。

## 执行顺序（不可调换）

1. **先等两轴复审结论。** 若复审要求改 src，改完再跑；否则两小时的全套会在一次 `src` 编辑后立刻作废。这条是从上一轮教训来的——勾早了被需求轴退回。
2. 全套跑完前不提交任何 src 改动。

## 冻结参数

| 项 | 值 |
|---|---|
| 版本 | 开跑时的 HEAD，跑完前不动 `src/` 与 builders |
| 运行方式 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src`，开跑前清 `src`/`tests` 下 `__pycache__` |
| 第一段 | 默认发现全套，排除两个材料依赖文件 |
| 第二段 | `tests/models/test_isolated_lifecycle.py`、`tests/integration/test_worker_registered_catalog.py`（含一次材料重建） |
| 临时件保留 | `-o tmp_path_retention_policy=failed` |
| 守护 | 可用内存 <1.5GB **或** C 盘 <2500MB，**连续两次采样**才终止（单次瞬时波动不杀任务） |
| 指纹 | 两段前后各记一次：`git rev-parse HEAD`、`git status --porcelain`、`src/` 内容哈希 |

`PYTHONDONTWRITEBYTECODE=1` 不是可选项：上一轮漏设，解释器把字节码写进 `src/pring_cycle/__pycache__`，被 `test_installed_cli_keeps_bytecode_outside_the_source_tree` 抓到，白报一个失败。

## 预算与前置

| 项 | 值 |
|---|---|
| 预计耗时 | 第一段约 70 分钟，第二段约 51 分钟（含重建），合计约 2 小时 |
| C 盘余量 | 开跑前记录；当前 11GB，材料重建峰值约 3GB |
| 清理规则 | 不足时只清任务**不依赖**的临时件；不得清理当前任务依赖的任何内容 |

## 结论口径

两段都零失败，才算票17 最后一项的"同版本冻结全套"到位；任一失败先定位，不跳过、不挑选样本。全套通过**也不自动勾选**——还需带指纹的两轴复审。
