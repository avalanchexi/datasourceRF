# 剩余任务的测试执行

继续implement时先读当前票及`.scratch/pring-data-acquisition-repair/continuation-status.md`。旧“正在运行”记录须核实际进程/终态；有效在途重型任务先收结果，不重复启动或修改其绑定输入。

## 日常反馈

使用当前已核对源码/安装身份的Python环境，从仓库根目录显式选择受影响测试：

```bash
python tools/check.py quick tests/integration/test_worker_reviewed_context.py
```

此命令要求具体文件或node ID，拒绝整个目录以及已知会构建完整模型的重型文件。快速目标约3分钟；超出如实记录，不删必要测试凑时限。返回码沿用pytest，未选范围不计通过。选择依据是变更及其调用方：解析变更覆盖对应解析/公开获取；选值、点时、认证变更覆盖相应消费者；共享逻辑或影响不明时扩大范围。

已测示例：候选天数夹具的相关反馈使用 `python tools/check.py quick tests/integration/test_candidate_duration.py`，2项通过、28.06秒。扩大到13个直接调用Worker的文件时，187项通过但需要923.74秒；不要把这组文件当作每次小改动的默认命令。完整检索文件中若干节点单次约30–40秒，局部变更先选对应node ID，受影响范围仍在收尾时补齐。具体版本、命令、结果与成本见[夹具诊断](../../.scratch/pring-data-acquisition-repair/diagnosis-duration-calendar-fixture-20260918.md)和[慢用例清单](../../.scratch/pring-data-acquisition-repair/slow-test-inventory-20260918.md)，这些数值不保证后续环境或其他变更的耗时。

## 重型验收与最终验证

模型材料、准入/回放/激活、Worker编排、发布和恢复关键路径有变化时，执行受影响重型文件，完成后才报告该切片验证完成。用原验收驱动或显式`python -m pytest <具体文件>`留存日志、实际退出码及终态。普通目录命名不能证明轻重；新增完整生命周期用例时更新`tools/check.py`的重型文件清单。

必要改动稳定后完成同版本默认全套：

```bash
python tools/check.py full
```

该入口不传选择器，原`python -m pytest`的完整发现保持。不同票引用同一全套收据，不能累加不同版本的专项数。独立产品性能、真实来源认证、真实回放和切换仍按各自门执行，全套十分钟为优化目标。

## 材料、时间与磁盘

- 同一时刻只跑一个重型测试/校准/回放，性能测量排除竞争负载；保留机器日常使用余量。
- 核对源码、安装、测试/输入及材料身份；只复用有效不可变材料，每个用例独立可变运行库。身份失配须重新准备，不为提速缩小缓存键。
- 计时随必跑验证采集，分别记录冷/热材料、准备/复制、测试和清理成本；同范围同身份才比较收益。
- 重型执行检查C盘实际余量，不能用WSL虚拟盘的逻辑空闲替代；用监督器定期记录进度与空间。可清理未使用的可再生成副本，保留失败证据、有效材料与正式运行数据；WSL内删除只保证释放可复用块，不保证C盘立即缩小。
- 普通软件回归以外部HTTP/时钟替身保持离线；意外外网等待应在测试边界修正，不能以延长超时掩盖。

## 当前解释器的诊断方式

本机 Python 3.12.12 上，SQLite 连接创建/关闭与 `faulthandler.dump_traceback_later` 的原生 watchdog 组合可稳定触发 SIGSEGV。完整验证中的一次崩溃已由独立最小复现确认：开启原生计时器3/3崩溃，关闭计时器或普通Python线程采样各3/3完成30000次连接；原Worker场景更换诊断方式后通过。见[诊断与原始证据](../../.scratch/pring-data-acquisition-repair/diagnosis-verification-faulthandler-20260918.md)。

该环境保持 pytest 默认 `faulthandler_timeout=0`，长时验证用独立监督进程记录单调耗时、C盘空间、当前节点与退出码；需要线程栈时，由普通Python线程取得 `sys._current_frames()` 后记录文件、函数和行号，不输出局部变量。Python线程可能在GIL长期不释放时无法采样，资源上限和终态收尾仍由外部监督负责。解释器升级后需重新核验，不能把本机结果外推至所有Python版本。
