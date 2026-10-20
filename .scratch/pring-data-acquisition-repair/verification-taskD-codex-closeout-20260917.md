# 任务 D 最终核验（2026-09-17）

Claude 启动、Codex 接续观察的两段测试均已结束，未重复启动。

| 范围 | 终态 |
|---|---|
| 默认全套，排除两个重型文件 | 1672 passed，4633.38 秒，exit=0 |
| `test_isolated_lifecycle.py` + `test_worker_registered_catalog.py` | 12 passed，3767.86 秒，exit=0 |
| 合计 | **1684 passed** |

终态原件与 SHA256 清单见 [evidence-taskD-final-20260917/receipt.json](evidence-taskD-final-20260917/receipt.json)。父脚本和 pytest 原进程已结束，控制台有 `=== done ===`。资源守护未触发；结束时 C 盘约 14 GB 可用。

## 输入一致性与限制

起始 HEAD 为 `5fe9cf8`，后两次为 `37696ba`，不能称为同一个冻结测试树。三次记录的 `src/**/*.py` 聚合哈希相同，五个重型材料构建输入文件哈希也相同。

从起始提交到结束，`src/`、`tests/` 的实际差异仅为 `tests/catalog/test_official_fallback_candidates.py`：Claude 在第一段进行中删除了一项重复目录常量的测试。两段结果因此按实际执行版本记账，不能冒充一个干净提交的完整冻结验收。

原测试结束后，Codex 清除了该文件不再使用的常量、帮助函数和过期说明，保留同族官方页面一致性用例。对主目录当前文件单独补验 **1 passed in 0.14s**，见 [verification-taskD-catalog-followup-20260917.txt](verification-taskD-catalog-followup-20260917.txt)。源码尚未整合独立工作树的 #25 业务改动。

旧的 1682 项通过记录属于更早版本；本轮 1684 项通过不代表来源认证、120 交易日真实回放、系统切换完成，也不覆盖独立工作树后续 #25 的新实现。
