# 09 窗口广度共享内容缓存复测 477

**476 版本消除了这两个样本中按收据重复保留 normalized bytes 的现象。** 两组均从 243／245 个不同对象降为 1 个；公开数值和每条声明的完整收据身份集合核对通过。此结论仅覆盖 50 只普通 A 股、1／2 个可见输出，不能外推最终规模。

## 环境与可比范围

新专属目录为 `/home/tywin/.cache/pring-cycle/verification/window-benchmark-477/`，两组运行库与 venv 均独立。原 464 目录、共享源码、旧原件及主线程环境未修改；464 已登记制品的哈希复核均未变。

本次安装 476 wheel：349,393 字节，SHA256 `610e5aae31dae083773eb3597bfd1e771fc6145982eede92dd04d59dc348e44d`。安装前后核对全部 91 个源码文件与 wheel 一致，53 项依赖版本未变。探测脚本仍为逐字节相同的 `probe-464.py`，冻结候选 helper 和 conftest 也与 464 相同，采用相同合成股票、价格、时钟及日历输入。

两个进程顺序执行，每个限定 180 秒墙钟和 2 GiB 地址空间；实际都正常结束、退出码 0。公开路径仍为候选准入 → `acquire_scalars/market_breadth` → 全部声明父项读取，没有调用内部计算器或真实网络。tracemalloc 分别覆盖采集和父项读取；RSS 为整个进程累计高水位。

476 同时包含 validated 前原件重建等正确性变化，且测量未隔离宿主负载，因此耗时差异不能全归因于内容缓存。本报告主要验证 retained bytes 与父项完整性。

## 实测对照

| 指标 | 120 输入／1 输出：463 → 476 | 121 输入／2 输出：463 → 476 |
|---|---:|---:|
| validated 收据 | 243 → 243 | 245 → 245 |
| 声明数 | 3 → 3 | 6 → 6 |
| 跨声明父项引用数 | 729 → 729 | 1,470 → 1,470 |
| 独立 normalized 哈希数 | 1 → 1 | 1 → 1 |
| 独立 normalized 内容字节 | 78,672 → 78,672 | 157,867 → 157,867 |
| 不同 normalized bytes 对象 | 243 → **1** | 245 → **1** |
| 不同对象载荷总字节 | 19,117,296 → **78,672** | 38,677,415 → **157,867** |
| 父项读取 tracemalloc 当前字节 | 19,891,231 → 829,540 | 39,575,536 → 1,032,726 |
| 父项读取 tracemalloc 峰值字节 | 20,520,603 → **1,536,637** | 40,981,126 → **2,582,722** |
| 采集 tracemalloc 峰值字节 | 7,320,772 → 5,567,123 | 7,380,229 → 5,949,703 |
| 进程 RSS 高水位字节 | 93,982,720 → 86,827,008 | 114,671,616 → 87,293,952 |
| 采集耗时（秒） | 16.332 → 38.119 | 20.411 → 47.845 |
| 父项读取耗时（秒） | 0.637 → 2.058 | 0.981 → 2.089 |
| 整个进程耗时（秒） | 19.426 → 43.651 | 23.617 → 55.188 |

不同 bytes 对象通过返回父项中的 `id(item.normalized)` 去重，所有对象保持存活；再统计内容长度及 SHA256。共享收据在不同声明里的多次引用没有重复计入对象数。CAS 磁盘去重原本已存在；本次新增证据是内存中的相同 normalized 内容也得到共享，不是磁盘容量优化证明。

476 两组 normalized 哈希分别为 `79a07c1349fd69ea329cec9d1f5c47dd5f0d63ac224a88c85ea3c2bcffc33b8c` 与 `a166a0dd745ea5008a53980b2072599682ce4eb36013d148d62b268bf0ebe0a8`。哈希与463不同但长度相同；normalized 包含具体声明／收据身份，不能要求不同运行的内容哈希相等。

## 公开值与血缘核对

计时结束后另用公开 `EvidenceRepository.metric_series` 和 `source_claim_acquisitions_many` 核对，不计入上述性能阶段：

- 每个可见日均读回新高 **50**、新低 **0**、MA120 上方比例 **100%**，符合50只股票价格持续上涨的独立例子。
- 第一组3条、第二组6条声明均存在；每条返回的父项身份集合分别精确等于本次捕获的243／245份收据集合。
- 全部按 PUBLIC 截止点读取的期次为预期1／2日。核对脚本退出码0，详细布尔结果和声明身份保存在下方制品中。

## 判断与后续

按本批内容哈希共享 bytes 已针对464实测缺陷取得正向效果，逐收据身份没有因此合并。无需为了该缺陷先改变持久化协议。

本次未证明速度改善，实际耗时更长；必须将同期正确性重建、重复读取校验及宿主负载与缓存本身区分。normalized 解码／重建缓存的增益仍未单独测量。下一步应随最终软件路径进行真实规模测量，再依据热点决定是否增加局部解析缓存；不能把50只、1／2输出的结果当成5000只、120输出验收。

## 制品与复核

- [原样复用的探测脚本](/home/tywin/.cache/pring-cycle/verification/window-benchmark-477/probe-464.py)，SHA256 `96a37471022a916524af201c05e99481c420085a67b8eebf0e79fc9c39d90f71`。
- [120／1 结果](/home/tywin/.cache/pring-cycle/verification/window-benchmark-477/case-120-1-result.json)及[日志](/home/tywin/.cache/pring-cycle/verification/window-benchmark-477/case-120-1.log)。
- [121／2 结果](/home/tywin/.cache/pring-cycle/verification/window-benchmark-477/case-121-2-result.json)及[日志](/home/tywin/.cache/pring-cycle/verification/window-benchmark-477/case-121-2.log)。
- [公开值及完整父项核对](/home/tywin/.cache/pring-cycle/verification/window-benchmark-477/value-parent-integrity-477.json)与[脚本](/home/tywin/.cache/pring-cycle/verification/window-benchmark-477/inspect-values-477.py)。
- [环境、精确命令、终态及所有脚本／日志／结果哈希](/home/tywin/.cache/pring-cycle/verification/window-benchmark-477/verification-477.json)，SHA256 `c0e8f934073cc76c5e45ab159a4afba3b839c4ea66452f010ff07347cc0b64b7`。

实际命令为独立 venv 的 `python -B probe-464.py --input-days 120 --output-days 1` 和 `--input-days 121 --output-days 2`，工作目录为477专属目录；解释器选项 `-B` 已在核验清单中完整保存。没有在本次测量中修改产品代码或实现额外优化。
