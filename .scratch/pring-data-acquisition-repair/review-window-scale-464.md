# 09 窗口广度有界规模测量 464

已通过公开采集与声明父项读取，确认 **CAS 会去重磁盘内容，但父项读取仍按收据保留相同 normalized 内容的多个 bytes 对象**。两个测量均正常结束、退出码 0；这是 463 冻结版本的 50 只股票小规模测量，不是 5000 只股票、120 个可见输出的容量验收。

## 固定环境与方法

- 使用 `/home/tywin/.cache/pring-cycle/verification/window-benchmark-464/` 下的独立环境、脚本及两份临时运行库。未修改共享源码、测试、旧原件或主线程 venv。
- 安装非 editable 的 463 wheel，SHA256 `40e1baf669fb2fd90be5dd576d3bc6869f20bd5c832076d401e376e6a0e76772`。前后核对 91 个安装源码文件与 wheel 字节一致，53 项依赖版本与指定来源环境一致，冻结测试 helper 及 conftest 哈希未变。
- 复用冻结 helper 的公开来源认证候选准入与原件审查协议，保留完整 61 项目录。合成 50 只普通 A 股（沪20、深20、北10），长期上市、正收盘价、无停牌／调整事件；日历为明确标识的合成工作日序列。
- 外部 transport 返回合成日历、行情及空停牌响应，无真实网络或凭据。外部时钟固定为 2026-09-14 UTC 起递进，沿用冻结 conftest 的时间边界。
- 分别调用 `TushareContextAdapter.acquire_scalars` → `market_breadth`，随后用 `EvidenceRepository.source_claim_acquisitions_many` 一次读取该次产生的全部声明父项。没有直接调用内部计算器。
- 每个独立进程设 180 秒墙钟上限、2 GiB 地址空间上限；两次顺序执行。采集与读取各自单独启动 tracemalloc。报告的 RSS 是进程累计高水位，包含导入及准备；耗时包含 tracemalloc 开销。

## 实际结果

| 指标 | 120 输入／1 可见输出 | 121 输入／2 可见输出 |
|---|---:|---:|
| 可见日期 | 2026-08-28 | 2026-08-27 至 08-28 |
| validated 获取收据 | 243 | 245 |
| 来源声明 | 3 | 6 |
| 父项引用数（跨声明） | 729 | 1,470 |
| 独立 normalized 哈希数 | 1 | 1 |
| 独立 normalized 内容字节 | 78,672 | 157,867 |
| 父项读取保留的不同 normalized bytes 对象 | 243 | 245 |
| 上述不同 bytes 对象载荷总字节 | 19,117,296 | 38,677,415 |
| 载荷相对单份 CAS 内容倍数 | 243× | 245× |
| 公开采集耗时（秒） | 16.332 | 20.411 |
| 全部声明父项读取耗时（秒） | 0.637 | 0.981 |
| 采集 tracemalloc 峰值（字节） | 7,320,772 | 7,380,229 |
| 父项读取 tracemalloc 峰值（字节） | 20,520,603 | 40,981,126 |
| 进程 RSS 高水位（字节） | 93,982,720 | 114,671,616 |
| 整个测量进程耗时（秒） | 19.426 | 23.617 |

bytes 对象数通过所有返回父项中的 `id(item.normalized)` 去重，返回结果保持存活；再分别统计载荷长度及内容 SHA256。跨声明共享同一收据的对象没有重复计入该对象数，因此这里证明的是按收据重复保留内容，不能将 729／1,470 个引用误算为独立缓冲区。

两个独立 normalized 哈希分别为 `a77020ccb12d001588f27af3db1ace184e5a64cc26a8458d8c624b69d1ecbfc3` 与 `d5eb0b0e55cadc45dbf0186da08e36a55575877f94977a197e186f35d608a6e2`；每组内所有 normalized 内容相同。实际磁盘内容去重成立，不能据内存复制倍数声称重复占盘。

## 最小建议与边界

优先考虑在一次父项批量读取中，按制品哈希缓存已经校验的 raw／normalized bytes，同时保留每份收据的身份与状态校验。这样可以直接针对已测得的内容复制，不需要先改变窗口公式或原件协议。修复后复跑同两个公开场景，再扩大实际股票池与可见窗口测量。

同批次的 normalized JSON 解码也可按内容哈希缓存；若进一步缓存原件到窗口结果的重建，缓存键应包含完整必要输入集合及窗口、公式、目录等影响结果的上下文，不能仅按指标或单个输出值缓存。重建缓存的收益尚未由本测量分离证明，建议先完成可局部验证的 bytes 缓存，再按实际热点决定。现有两组证据不足以要求重构存储协议，也不足以证明局部缓存能解决未经测量的全部规模问题。

本次尚未测量每份收据重复序列化所占的独立 CPU 时间，也未测量后续完整回放、5000 只股票或 120 个可见输出；不能从上述两个点给出最终容量、线性外推或认证结论。未实施任何优化。

## 可复核制品

- [探测脚本](/home/tywin/.cache/pring-cycle/verification/window-benchmark-464/probe-464.py)，SHA256 `96a37471022a916524af201c05e99481c420085a67b8eebf0e79fc9c39d90f71`。
- [120／1 结果](/home/tywin/.cache/pring-cycle/verification/window-benchmark-464/case-120-1-result.json)及[合并日志](/home/tywin/.cache/pring-cycle/verification/window-benchmark-464/case-120-1.log)。
- [121／2 结果](/home/tywin/.cache/pring-cycle/verification/window-benchmark-464/case-121-2-result.json)及[合并日志](/home/tywin/.cache/pring-cycle/verification/window-benchmark-464/case-121-2.log)。
- [环境、实际命令、退出码及全部制品哈希](/home/tywin/.cache/pring-cycle/verification/window-benchmark-464/verification-464.json)，SHA256 `728ce5aebc1cf3866ee8e9eed7d1066497e891ea1793d56e1d2cbd04a04027e1`。

实际执行命令使用独立 venv 的 `python -B probe-464.py --input-days 120 --output-days 1` 和 `--input-days 121 --output-days 2`，工作目录为上述专属原生目录。结果文件中的 argv 由 Python 收集，因此解释器选项 `-B` 另在核验清单的实际命令中保留。
