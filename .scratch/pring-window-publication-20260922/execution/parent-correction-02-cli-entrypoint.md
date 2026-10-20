# 02公开进程命令校正

原heavy-request-r2.md的示例 `python -m pring_cycle.cli run-submit ...` 不执行入口；该模块没有main守卫。应使用 `python -m pring_cycle run-submit ...` 或已安装的 pring-cycle 命令。原文件及哈希保持，修正未来验证命令，不把空exit0算运行成功。该问题由主代理真实日历预检首次空输出查实；v2正确入口已有预检与持久重读输出。

CNY030公开Python CLI main红绿实际有效，不受示例拼写影响。完整Worker报告反例仍须合法生命周期材料与主代理重型调度。
