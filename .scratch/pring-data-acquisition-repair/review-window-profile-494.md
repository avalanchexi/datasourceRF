# 票09有界栈诊断494

三次主线程采样均落在首次 `calculate_window_breadth` 的窗口成员循环：逐日价格读取、价格归一化、精确MA计算。至180秒仍未完成公开 `market_breadth`。本次已将488的停点收窄到首次窗口构建；采样不足以计算各子循环耗时占比，也没有证明内存耗尽。

## 输入与观察边界

独立ext4目录：[window-profile-494](/home/tywin/.cache/pring-cycle/verification/window-profile-494)。复制488已冻结的483环境、484 helper和已纠正的5000成员探测输入，未安装新依赖或修改产品源码。仍为SH/SZ/BJ各2000/2000/1000成员、239输入日和120显示日；日期直接复用484的固定239日fixture，显示范围2026-03-09至08-28。每日5000行情行，无事件和停牌，外部网络调用为0。

483 wheel SHA256：`a22e104fdd63ce7cef3b43ff571e13cf8fa7841a1f81f8462d57df9fc7402e27`；484 helper SHA256：`7182a6e2033bee429cc7b5ead6ca8c17efcfc2b2421d64070ab8cc2708ca6b54`。运行前后53项依赖、91份安装源码及冻结输入一致；488原清单22项制品和清单本身均保持原哈希。

新增观察仅为标准库 `faulthandler.register(SIGUSR1)`，监督进程在90、150、175秒发信号保存主线程栈；保留原公开retrieve进入/返回标记、transport计数和RSS采样。没有内部函数mock或内部状态读取，也未把采样位置写成业务断言。[观察增量](</home/tywin/.cache/pring-cycle/verification/window-profile-494/observation-diff-494.patch>)保存了脚本差异。

## 三次实际采样

三次调用链均为 `acquire_scalars → retrieve → market_breadth → _reviewed_window_breadth → parse_window_breadth_acquisitions → calculate_window_breadth`，属于第一次公开retrieve内的计算。

| 实际秒数 | 冻结483代码位置 | 当时操作 | RSS字节 |
| --- | --- | --- | --- |
| 90.000541 | market_breadth.py:968 | `prices[period].get(identity)`，遍历成员的窗口日期 | 977,453,056 |
| 150.000498 | market_breadth.py:1026 | 遍历价格来源与窗口价格，构造精确归一化序列 | 1,619,705,856 |
| 175.000289 | market_breadth.py:1039；fractions.py:615 | `current * 120 > sum(known)`，栈顶为Fraction运算 | 1,801,371,648 |

[完整栈日志](/home/tywin/.cache/pring-cycle/verification/window-profile-494/stack-samples-494.log) SHA256：`830cf6ddff4bef6383dbcc15a5005df2e756058510f3c25ba99f07e195e57a3b`。三次均已进入窗口构建，足以排除这三个时点仍停留于最初transport或原件解析的猜测；不表示90至175秒之间每个瞬间均处于同一子循环。

## 终态及判断

239份每日行情在50.761秒全部构造完成。179秒软TimeoutError后产品开始逐收据失败收尾，180秒监督进程SIGKILL，子进程退出-9；监督进程退出0，含回收共180.136秒（exec session 64444）。限额仍为2GiB地址空间和180秒墙钟，未延长收尾或再次运行。

采样峰值RSS为1,830,469,632字节，VmPeak为1,874,571,264字节。终止后公开接口读到481份收据：239 daily、239 suspend_d及3份共享输入；105份failed/TimeoutError、376份received；normalized哈希0个，SYSTEM指标序列值0个。公开retrieve及acquire均未返回，子进程最终result.json来不及写出；监督日志和三份栈已完整保留。

当前证据支持将后续性能工作集中到窗口成员计算，先核算跨窗口/成员重复的日期处理、基础价格转换及精确汇总成本。任何改动仍须保留精确比较、事件PUBLIC、停牌延续和必要父项，并用同一公开协议复测。本次没有到外层完整normalized逐收据序列化，不能据此修改该阶段；也不能仅凭栈采样删去120价格审计表示。样本均为合成输入，受限未完成不等于业务SLA失败或正式容量/认证结论。

## 可复核制品

实际监督命令：

```text
/home/tywin/.cache/pring-cycle/verification/window-profile-494/venv/bin/python -B /home/tywin/.cache/pring-cycle/verification/window-profile-494/supervise-494.py
```

监督脚本启动保存的 `probe-494.py --members 5000 --input-days 239 --output-days 120`。probe SHA256：`ef355abc54b789a6e845c529784a7e706937a126692ecbbe14b65a30a15c9eff`；supervisor SHA256：`2cacb9a064132b49e896c9e5a319181c5420586e6deaac83e27b18e23d2da632`。

全部输入、代码、观察差异、命令、退出码、采样及前后完整性核验见 [verification-494.json](/home/tywin/.cache/pring-cycle/verification/window-profile-494/verification-494.json)，SHA256：`50c128bf84321fd613d9d411d192af03ffb521f7ca9b8b4abeeeac80d0938034`。后置公开收据检查及完整性核验在终止后执行并退出0，不构成继续运行超时的计算。
