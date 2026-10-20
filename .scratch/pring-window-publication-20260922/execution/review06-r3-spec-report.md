**仅 Spec：未发现可确认的新增问题；前轮第1项可关闭，第2、3项保留，票06仍不能关闭。**

- **已关闭：PUBLIC 正向合同缺失。**依票06验收2/4、ADR-0018及父规格实施6/7，[发布校验](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-06/src/pring_cycle/margin_publication.py:65)绑定每所精确元值、日期、来源、原件、实际获取收据及具名审核；可靠日期取下一自然日，任一侧未知则合计未知。[消费重验](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-06/src/pring_cycle/margin_publication.py:228)重新核查原件、审核和规范化。既有合成用例覆盖修订独立发布时间与损坏拒收。审核 JSON 是应用证明包；真实源尚未认证不否定合法 synthetic 软件正例。未见旧三所语义被改写。

- **P1，前轮第2项仍开放（静态推断）。**父规格测试9/10要求消费者验证实际输入版本；[回放分支](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-06/src/pring_cycle/model_evaluation.py:1251)仍只检查旧 `CN_MARGIN_BALANCE`，新身份未接入共享完整性校验。不能据此声称已经复现错误回放，但损坏后回放拒收尚未证明。

- **P2，前轮第3项仍开放。**票06测试边界、父规格测试1/11要求持久任务→单次完整Worker→投影/报告读回；[当前测试](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-06/tests/integration/test_worker_margin_two_exchange.py:71)仍直接调用刷新函数。重型反例虽已编写，尚无执行收据。

首尾核验：HEAD等于指定基线，11文件哈希全部匹配，按数组顺序重建diff与存档逐字节一致，输入未变；继承文档WIP未计入。104包文件与源码、收据一致，软件/安装/材料前后身份相同；日志为 **58 passed／29.76秒**，不代表重型、完整Worker或回放通过。本次未委派、修改、测试、联网或读取凭据。