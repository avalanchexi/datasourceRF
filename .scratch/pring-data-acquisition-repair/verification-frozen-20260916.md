# 最终同版本冻结默认全套（HEAD `9929b45`，2026-09-16）

计划 [`plan-next-steps-20260916.md`](plan-next-steps-20260916.md) 步骤2。冻结对象为同一源码、依赖、安装包与输入证据身份。

## 冻结与执行方式

- 在 `9929b45` 的干净 git worktree 检出上构建轮子并以 `--no-deps --force-reinstall` 非可编辑安装到验证虚拟环境；运行前后各记一次指纹（HEAD、`src`+`tests` 树哈希、依赖清单、安装源码与检出逐字节一致）。
- 默认发现全部测试：`python -m pytest -q --tb=short -p no:cacheprovider -o tmp_path_retention_policy=failed --durations=25`，材料根指向本次运行专用目录。
- 守护每15秒采样，可用内存<1.5GB或C盘<2GB即终止并保留现场；全程未触发。
- 验证期间未并行修改绑定输入，也未运行干扰性安装或校准；另一会话只写 `.scratch` 文档并做只读检查。

## 结果

| 项 | 值 |
|---|---|
| 状态 | **passed**，退出码 0 |
| 用例 | **1671 通过，0 失败** |
| 开始/结束 | 2026-09-16T12:17:08+08:00 / 2026-09-16T14:22:31+08:00 |
| 墙钟耗时 | 7523 秒（按上面两个时间戳） |
| pytest 自报耗时 | 8067.81 秒（2:14:27） |
| 前后指纹 | HEAD 与树哈希一致（`07df0da3…`），依赖清单一致，安装源码与检出一致 |
| 记录 | `verification-frozen-20260916.json`、`verification-frozen-20260916-suite.txt`（log sha256 `f56f3158…`）、`-fingerprint-before/after.json` |

两个耗时口径相差约 545 秒，本机 WSL 墙钟此前已出现过倒退（见票17 记录中的 `acquisition_availability_time_invalid` 处理），因此两值都如实保留，不取其一冒充实测；十分钟目标本就不是硬门（见 [票22 计时切片](implementation-22-timing-slice.md)）。

## 覆盖确认

- 跨期共享硬搜索预算失败行为：`tests/integration/test_full_run_retrieval.py::test_full_run_shares_hard_search_budget_across_periods` 在默认发现范围内并通过（该文件的用例出现在 `--durations=25` 明细中）。
- 最慢用例前两名均来自 `tests/integration/test_full_run_retrieval.py`（约52.9秒、52.7秒），详见日志。
- 本次运行包含一次隔离材料重建（材料根 `frozen-20260916/materials`）。

## 资源

C盘从约12GB降至6.8GB；其中约3GB为材料重建导致的WSL虚拟磁盘增长（虚拟磁盘只增不减），运行中已删除上一轮 `joint-20260916/materials`（3.0GB）让后续写入复用。WSL根目录用量118GB。

## 范围说明

本记录只证明"同一冻结版本的默认全套取得实际终态"。真实来源认证、真实120日回放、真实配对检索与真实切换仍按票18/20/21 的原依赖开放，不因本次通过而关闭。
