# 双会话改动的联合回归（HEAD `1fa16c5`，2026-09-16）

覆盖同一版本上的两批改动：前台会话的代码健康项（`2b0e4ad`：期货读取器拆分为 `futures_input_reads.py`，材料内容校验跳过 SQLite 旁文件）与本会话的美债时钟修复（`1fa16c5`）。两者都使前一份隔离材料失效，因此合并为一次重建。

方式：在 `1fa16c5` 的干净 git worktree 检出上构建轮子并非可编辑安装到验证虚拟环境，核对安装源码与检出逐字节一致；分组顺序运行，`-o tmp_path_retention_policy=failed`，每组通过后立即删除该组 basetemp；守护每10秒采样，可用内存<1.5GB或C盘<2GB即终止并保留现场（未触发）。材料重建在 lifecycle 组内完成，新材料身份 `ddeace1d…`（3.0GB）。

| 组 | 目标文件 | 结果 | 用例 | 秒 |
|---|---|---|---:|---:|
| adapters | test_futures_inputs, test_commodity_basket | passed | 91 | 48.9 |
| replay | test_candidate_replay, test_context_output_references | passed | 86 | 26.5 |
| admission | test_candidate_admission | passed | 656 | 1039.9 |
| lifecycle | test_isolated_lifecycle | passed | 3 | 1853.8 |
| worker | test_worker_registered_catalog, test_worker_execution, test_full_run_retrieval | passed | 67 | 3559.1 |

合计 903 项通过、0 失败，累计约 108 分钟。逐组记录见 `verification-joint-20260916-<组>.json/.txt`。

要点：

- admission 组 656 项全通过；此前失败的 6 个美债用例已随固定时间线修复，其余用例不受影响。
- lifecycle 组 3 项（比之前多一项）包含前台会话新增的"材料内容校验忽略 sqlite 旁文件"反例，材料重建与副本校验均通过。
- worker 组包含注册目录 8 项及 Worker 执行、完整运行检索全部用例，在期货读取器拆分后行为不变。
- 资源：全程 C 盘保持 12GB，可用内存最低约 4.8GB，守护未触发。
- 本次不等同于"最终同版本默认全套"：范围是两批改动的相关回归，票17仍保留该项为未关闭条件。
