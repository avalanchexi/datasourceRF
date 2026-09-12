# 票09规模审查488：5000成员、239输入、120输出的受限实验

冻结483软件在本次180秒限制内没有完成。全部239份每日5000行行情已经交付，但首次公开 `market_breadth` 调用尚未返回。观察到的是实验超时，不是业务SLA失败、来源认证结果或内存耗尽证明。

## 冻结输入与边界

- 独立ext4目录：[window-benchmark-488](/home/tywin/.cache/pring-cycle/verification/window-benchmark-488)。只在此处创建环境、脚本和隔离运行库；共享源码、测试、root环境及旧464/477材料未修改。
- 483 wheel：350015字节，SHA256 `a22e104fdd63ce7cef3b43ff571e13cf8fa7841a1f81f8462d57df9fc7402e27`。从独立477环境复制53项确切依赖，再离线安装该wheel；运行前后91份安装源码逐字节对应wheel，53项依赖版本一致。
- 冻结484 helper：SHA256 `7182a6e2033bee429cc7b5ead6ca8c17efcfc2b2421d64070ab8cc2708ca6b54`；conftest为 `d93f92709ba2f4e46be5d78f96083102e75f61e206df5d86399acac13605a33c`。
- 日期直接复用484的 `china_window_input_dates()`：119个隐藏输入日2025-09-03至2026-03-06，加120个显示日2026-03-09至08-28。239日序列SHA256 `c7bde36decbb903de7d6c881a56814bb5f3e745e93f11b0f44ed741458e25bee`，未沿用464的185自然日生成器。
- 5000个合成普通A身份：SH 600000–601999共2000个；SZ 002000–003999共2000个；BJ 920000–920999共1000个。代码唯一且在产品支持范围；每份daily恰5000行，小于6000行饱和边界。无停牌、无调整，合法正价逐日递增；这些假定不认证真实股票池或历史PUBLIC。
- 复用公开候选准入 → `acquire_scalars` / `market_breadth`，仅合成外部transport和时钟。以公开retrieve进入/返回标记及外部响应进度定位，不替换算法或读取私有运行状态。使用RSS及地址空间采样，未启用tracemalloc。

## 实际终态

有效脚本：[run-02 probe](/home/tywin/.cache/pring-cycle/verification/window-benchmark-488/run-02-ordinary-codes/probe-488.py)，SHA256 `2f7f2b456c2e8977049ed6581d98864b2e130070b5ec7cf23f04a053f291e342`。

```text
/home/tywin/.cache/pring-cycle/verification/window-benchmark-488/run-02-ordinary-codes/venv/bin/python -B /home/tywin/.cache/pring-cycle/verification/window-benchmark-488/run-02-ordinary-codes/probe-488.py --members 5000 --input-days 239 --output-days 120
```

由保存的 `supervise-488.py` 启动，子进程从启动即设2GiB `RLIMIT_AS`；179秒软信号用于诊断收尾，180秒由独立监督进程硬终止。

| 可观察阶段/资源 | 实测 |
| --- | --- |
| 公开候选准入完成 | 2.277秒，61项定义 |
| 首次公开market_breadth进入 | 2.386秒 |
| 第239份daily响应构造完成 | 52.373秒，各5000行；当时峰值RSS 496,787,456字节 |
| 公开market_breadth返回 / acquire_scalars返回 | 均未到达 |
| 监督采样峰值RSS | 1,635,725,312字节，约1.523GiB |
| 监督采样VmPeak | 1,655,672,832字节，约1.542GiB |
| 停止 | 179秒TimeoutError后收尾未完成，180秒SIGKILL；子进程退出-9 |
| 监督进程终态 | 退出0，含回收进程共180.136秒；exec session 73793 |

终止后经公开收据/证据接口单独检查：481份收据完整存在，包含239 daily、239 suspend_d和3份共享输入；141份已标failed/TimeoutError，340份仍received。独立raw哈希243个，normalized哈希为0，SYSTEM查询窗口指标值为0。此检查不属于继续执行超时的计算。

完整异常栈和子进程最终result.json未保存下来：产品捕获软TimeoutError后仍在逐收据失败收尾，硬期限先到。监督终态、逐阶段日志、RSS采样及持久收据共同支持上述停点，不能据此进一步声称具体某个内部循环耗尽了资源。

## 可支持的最小结论

本次尚未到外层 `acquire_scalars` 的完整normalized构建及每收据 `complete_validation`，因此不能把这次超时归因于该阶段重复序列化。也没有观察到MemoryError；VmPeak低于地址空间上限不能单独证明所有大分配均可成功。

若继续优化，应先对首次公开 `market_breadth` 内部的原件重建与窗口构建做有界被动采样，再决定是否缓存已验证的日结果或减少重复价格材料；此次数据不足以选定某项重构。保留每收据完整性校验，暂不据此修改存储协议。477的bytes共享证据仍仅属于476的小样本，不能与本次受限结果拼成最终容量验收。

首次启动因探测代码生成器跨入非普通A代码段而在2.740秒遭门禁拒收，未发出daily请求；其脚本、日志、运行库和退出1全部保留，明确归为夹具准备错误。第二次仅修SZ/BJ代码段，未减少5000成员、239输入或120输出，也未更换483软件。

全部命令、退出码、输入/脚本/日志哈希及前后环境核验见 [verification-488.json](/home/tywin/.cache/pring-cycle/verification/window-benchmark-488/verification-488.json)，SHA256 `785f5ab7db1a8eb8c60985475628a5d1d7db63709e52503e1d004b69ee4daebf`。原始日志和监督结果均在该清单定位；不冒充真实源实测或固定120日正式验收。
