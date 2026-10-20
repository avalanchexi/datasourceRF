# 默认验收的历史内存峰值污染（2026-09-18）

## 原始失败及最小复现

v3 完整验证的真实终态为 `1 failed, 7 passed in 3939.51s`，监督单调耗时 3949.22 秒、exit 1、冻结输入不变，后代残留为空。7 个重型节点包括 legacy 强制冷生命周期 2002.15 秒全部通过。第 8 个节点 `test_unified_offline_acceptance_covers_all_35_regressions_and_hard_gates` 3.66 秒失败，返回 `blocked`。

失败制品 `82d1c18714658d73642dfeaace2d8a5b779deb131d69dc7569bd74035cca62cf` 中 35 个功能项与 8 类故障注入通过，唯一失败是 `idle_rss_bytes=3609169920` 大于原 1.5 GiB 硬门。不是价格/认证回归，也不是监督超时。

[最小复现驱动](diagnose-acceptance-order-20260918.py)运行**同一冻结安装上的原测试**，在进程启动时真实分配并释放 1700 MiB，再正常执行公开验收，不替换内存 API、不改变门槛：8.29 秒得到同一原断言失败。释放后当前 RSS 34,893,824 字节，而进程生命周期峰值仍 1,817,407,488 字节，验收把后者记为空闲 RSS。见[RED 收据](verification-acceptance-order-red-20260918.json)及[日志](verification-acceptance-order-red-20260918.txt)。

## 假设及对照

1. 历史峰值污染：干净进程同一原测试应通过；真实瞬时分配释放足以让它失败。
2. 当前软件/材料回归：干净进程中相同公开验收仍应失败。
3. 应用真实空闲内存超限：默认独立 Web/Worker 进程探测应同样超过 1.5 GiB。

[对照驱动](verify-acceptance-order-controls-20260918.py)及[终态](verification-acceptance-order-controls-20260918.json)：干净进程原测试通过，3.08 秒。另一个专属进程先经历同样瞬时分配，随后执行默认 `run_v1_acceptance()`，真正启动独立 Web/Worker；全部门通过，6.37 秒。其历史峰值 1,844,957,184 字节，但独立进程空闲 RSS 106,708,992 字节，仍按原 1.5 GiB 门判定。该对照证明成因，不替代当前全套结束后的正式独立进程验收。

## 成因与修正范围

`include_process_probe=False` 的轻量进程内测试形态以 `getrusage(RUSAGE_SELF).ru_maxrss` 作内存估计，读取的是进程生命周期峰值。我为优先取得重型结果在 v3 observer 中重排了用例，把重型测试放到了原本最先执行的验收测试前面，引入顺序污染。默认产品入口的空闲内存来自独立 Web/Worker 进程，未因该重排改变。

本轮修正外部验证编排，恢复 pytest 原始默认发现顺序，不改产品/测试、阈值或预期，不跳过已通过的重型用例。[v4 收集预检](verification-current-full-v4-collection-preflight-20260918.json)实际退出 0、2.48 秒，1848 个节点及顺序逐项等于 v3 保存的原始收集。两份合法材料的 key/完整 identity、安装及完整环境在启动前强制与 v3 核对；身份不符即停止。已存在同身份材料供消费者复用，原强制冷构建测试仍会执行。

Spec/Standards 复核各指出同一个启动前环境比较问题：Python tuple 列表与 JSON list 列表直接比较会误失败。已规范化 JSON 表示后比较，双方复核关闭，未解决 0。这个准备缺陷未启动测试、不构成产品失败。

## 执行及终态要求

v4 监督句柄 `35508`，pytest 启动 PID `2110832`；后代监督句柄 `32185`，后续队列 `49142`。以实际收据和 PID/start_ticks 核对存活，不把本记录当实时状态。v4 后代 watcher 第一次在主驱动仍预检、收据尚未创建时调用，因 FileNotFoundError 退出，未产生监督收据；收到主驱动 running 回执后才重新连接现有 PID，没有重启测试。

v3 的原全套、收集、事件、后代及未启动后续队列记录全部保留。v4 必须取得自身的完整终态、输入未变与空残留审计；成功后队列才执行 money 必需字段变异及默认独立进程验收。不得拼接先前通过节点宣称完整成功。
