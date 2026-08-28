---
status: accepted
---

# WSL2 单机采用 SQLite 任务账本、独立 Worker 与 Dash/FastAPI

V1 在 WSL2 中以 SQLite WAL 和内容寻址文件目录保存唯一权威状态，由一个 FastAPI + Plotly Dash Web 进程提供 localhost 页面和版本化REST接口，由一个独立Worker通过SQLite持久任务账本执行采集、分类和AI长任务。运行数据放在WSL原生XDG目录，页面只读取投影或幂等追加任务，并用低频自适应轮询观察状态。

这一选择以单用户、低频盘后运行和可恢复性为优先，明确拒绝Redis、Celery、WebSocket、Dash后台回调、Node.js、Docker和第二个Web服务。代价是SQLite只适用于当前单机单Worker边界；若未来需要多机、多Worker或公网多用户，必须新建ADR重新选择协调与存储架构，不能在V1中偷偷扩展。

Windows任务计划程序和持久账本只提供可选自动盘后能力，不意味着项目启动后自动补跑。手动优先、默认关闭自动运行以及中断后显式恢复的语义由[ADR-0010](0010-manual-first-persistent-refresh-runs.md)进一步限定。
