# #22 显式快速验证入口（2026-09-18）

在既有剩余任务安排内增加 `tools/check.py` 和 `docs/agents/testing.md`，由 AGENTS.md 指向指南。`quick`要求具体相关文件/node ID，拒绝目录和已知完整生命周期重型文件；`full`使用原pytest默认完整发现。输出实际范围、命令、单调耗时和退出码；约3分钟是目标，不截断必要测试，不把专项通过计为全套。

验证环境：项目Python3.12，PYTHONPATH指向#25/#27已核验非可编辑安装；未修改绑定产品或测试输入。

- `quick tests/domain/test_pring_stage.py`：10 passed，pytest 0.17秒，入口0.69秒，退出0。
- quick目录/已知重型文件、full带选择器：均拒绝并退出2。
- `quick tests/domain/test_pring_stage.py::not_an_existing_test`：pytest退出4，入口保持退出4，0.48秒；不会将未找到测试记为通过。
- `full --collect-only`：1843项，pytest5.86秒，入口6.8秒，退出0。日志在主工作树`verification-22-full-collection-20260918.txt`。这只证明完整发现，不是1843项执行通过。
- ruff检查通过；mypy `--follow-imports=silent tools/check.py`通过1个文件。

## Standards

按cc819496042f8bc3838ea6809eb47fc90af357e9基线审查工具增量：硬违规0、判断项0。quick/full范围限制、退出码传播和AGENTS入口一致。整合树续接文件仍含9月16日旧状态，继续工作须以主工作树本轮执行记录与实际进程为准，交付时同步更新。

## Spec

工具增量无阻断项；遵守已确认Q1–Q4，未改变pytest默认完整发现或产品硬门。已知重型清单需随新增生命周期测试维护，快速目标不能代替完整验收。

此切片只交付测试入口与执行约定；#22真实验收及当前版本最终全套仍开放。
