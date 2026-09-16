# 合并验证（任务 A/B/C 同版本，2026-09-16 夜间）

覆盖同一工作区版本上的三项改动：[租约心跳交叠](implementation-17-lease-heartbeat-overlap.md)（`9d44c7d`）、[家族选择链注册表](implementation-search-family-registry.md)（`fcebc3d`）、[填报值改名](implementation-22-timing-slice.md#命名跟进2026-09-16任务-c)（`d24d4aa`）。

## 范围与取舍

C 盘当时 4.6GB，隔离材料重建加用例副本峰值约 6GB，不够。按计划的第二个选项执行**轻量合并验证**：默认发现全部测试，仅排除两个材料依赖文件（`tests/models/test_isolated_lifecycle.py`、`tests/integration/test_worker_registered_catalog.py`）。这两个文件的验证待 C 盘回收后补做。

## 结果

| 项 | 值 |
|---|---|
| 用例 | **1667 通过，1 失败** |
| 耗时 | 4163.6 秒（1:09:23） |
| 失败项 | `tests/e2e/test_local_runtime_cli.py::test_installed_cli_keeps_bytecode_outside_the_source_tree` |

**该失败是运行方式造成的，不是产品缺陷。** 本次以 `PYTHONPATH=src` 运行且未设 `PYTHONDONTWRITEBYTECODE=1`，解释器把字节码写进了 `src/pring_cycle/__pycache__`，正好被这条守护用例抓到——它的职责就是保证安装后的 CLI 不把字节码留在源码树（对应 `docs/development/local-runtime.md` 的非可编辑安装边界）。目录中还残留 `cpython-310` 的旧文件，说明此前也有过同类写入。

清理 `src`、`tests` 下全部 `__pycache__` 后，按规定方式（`PYTHONDONTWRITEBYTECODE=1`）复跑该文件：**10 通过/37.9秒**，源码树保持干净。

## 之前已单独完成的部分

- 租约心跳：新用例 2 通过，变异检查有效；Worker 相关回归 59 通过/175.4秒。
- 家族注册表等价性：`test_full_run_retrieval` + `test_candidate_admission` **691 通过/3104.1秒**，零失败。
- 填报值改名：`test_acceptance_timing` + `test_rehearsal_cutover` 23 通过/69.8秒。
- ruff check/format 与 `mypy src`（96 源文件）在三项改动后均通过。

## 材料相关部分（2026-09-17 补跑，已完成）

轻量版排除的两个文件随后仍在同一工作区版本上跑完，未等 C 盘回收：

| 项 | 值 |
|---|---|
| 目标 | `tests/models/test_isolated_lifecycle.py`、`tests/integration/test_worker_registered_catalog.py` |
| 结果 | **12 通过，0 失败** |
| 耗时 | 3076.8 秒（51:16），含一次材料重建 |
| 记录 | `verification-taskD-material-20260917.txt` |

敢在 4.3GB 余量下开跑的依据：WSL 内部已先腾出约 6GB 可复用空间，且上一轮重建时 C 盘全程持平。守护收紧为「可用内存<1.5GB 或 C 盘<2500MB，连续两次采样」才终止。

运行期间 C 盘一度从 4295MB 降到 3158MB，随后自行回升到 4150MB 并保持。同期核对：WSL 虚拟磁盘 287.60GB **未变**，swap 仅由 16.5GB 增至 16.7GB——**下降来自 Windows 侧的临时占用，不是本次运行**，与 2026-09-16 那次 5GB 瞬时占用同源。守护未触发。

至此任务 A/B/C 三项改动在同一版本上的合并验证覆盖完整：轻量部分 1667 通过（另有 1 项因运行方式失败，已查明并复跑通过），材料部分 12 通过。

## 待办

票17 心跳项还要求"经公开任务提交 → 持久任务 → Worker 执行 → 投影与状态查询"的完整链路验证，本次未做，**票17 不勾选任何条件**。
