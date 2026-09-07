# PMI 活动、库存、价格：56 个准备标量逐值核对

研究日期：2026-09-08（Asia/Shanghai）。显式原表数字期望与准备值的数值、身份检查执行于 2026-09-07T16:56:42.295856+00:00，即北京时间 2026-09-08 00:56:42。范围仅为 `nbs_pmi` 家族内 `CN_PMI_ACTIVITY`、`CN_PMI_INVENTORY`、`CN_PMI_PRICES` 三项指标。

**实际准备范围为 7 期（2026-01 至 2026-07）、每期 8 格，共 56 格：活动 28，库存 14，价格 14。独立原表核对相符 56，冲突 0，无法独立核验 0。** 字段、指标身份、维度、单位、统计月起止边界也为 56/56 相符。7 份唯一原件合计 **2,894,481 字节**，原始字节 SHA 全部重新核对一致。

这 8 格不是 8 个指标家族，也不是预设的 9 个字段。其共同 `measure=level`、`unit=diffusion_index_points`；原表标“单位：%”，表示调查指数的百分比标度，不能转述为价格/产量同比涨跌幅。56 格数值核对不授予历史 PUBLIC、来源认证、模型采用或 120 交易日重放通过。

## 输入快照与独立方法

已读取 [准备脚本](evidence-13-preparation/prepare.py)、[准备快照](evidence-13-preparation/preparation.json)、[既有锚点期望](evidence-13-preparation/anchor-expectations.json)。锚点在本范围仅覆盖 2026-07 的新订单 48.5、产成品库存 48.6、主要原材料购进价格 53.2 三格；另外 53 格旧状态是 `not_individually_fact_audited`。本次不把三个代表锚点扩大成全历史已核对。

使用 Windows `C:/Python313/python.exe -B` 标准库 `html.parser.HTMLParser` 只读原始 HTML，按实际表、行、单元格次序定位，记录 `<td>` 起始源码行，解码实体并合并文本空白。先阅读原表完整双层表头和目标年月行，独立录入下面 56 个字面数字，再用 `Decimal` 对照准备快照。没有导入应用、调用公开解析器、复制应用正则/计算方法或用准备值生成期望。

每页表 1/2 包含跨 13 个月的历史行。本次只核对准备快照所请求的统计月：该月由原表日期标签明确识别，在本批原件中位于 T1 R16、T2 R15；不能仅因“最后一行”就不核对年份和月份，也不把其余历史行增加到 56 格分母。后一期页面里的前期回顾行不自动证明前期首次公开的版本。

本次不重跑或修改不可变准备包，不把这些结果改称当前安装应用版本的解析回归。输入指纹为：

| 输入 | 字节数 | SHA-256 |
| --- | ---: | --- |
| `evidence-13-preparation/prepare.py` | 18456 | `e9295dcd722d9ff1f67e9fb0e57db6154c297510f80df344258b69971f638b27` |
| `evidence-13-preparation/preparation.json` | 2767926 | `a9fe475c47303fb7791b27df04849dcef0aacabde27b64f57023972c9a4ec20a` |
| `evidence-13-preparation/anchor-expectations.json` | 4152 | `e4ba9fe88c93701d7fa6ba7f2cca1e37387b95ba2f91771b320fa7be7035eafe` |
| `evidence-13/receipts.json` | 11329 | `edb8fa76f4254b96867d3c55bcd58b1ba432a5d8f71cedbd5c372773663c37c9` |
| `evidence-13/imports.json` | 5145 | `07da00c64b09c728052b2c2ab5ff7156df6e403714f28653e86d4b9c9855b875` |

## 官方精确原件

6 份原件给出既有 CAS 的本机 UNC 路径，7 月原件另有既有仓库相对路径；没有新增副本或网络下载。以下均为原始字节 SHA，不是提取文本的摘要。各文章标题为对应年月的“中国采购经理指数运行情况”；正文 L332 署名国家统计局服务业调查中心、中国物流与采购联合会，并明确进入“中国制造业采购经理指数运行情况”。

| 原件 | 统计期与官方出处 | 精确原件路径 | 字节数 | SHA-256 |
| --- | --- | --- | ---: | --- |
| R01 | [2026-01 国家统计局](https://www.stats.gov.cn/sj/zxfb/202601/t20260131_1962416.html) | [CAS 原件](//wsl.localhost/Ubuntu-22.04/home/tywin/.local/share/pring-cycle/artifacts/sha256/6e/6ef53006136e5a396533fe406f620e1799e7b0bc4246b380fb18e6294edab423) | 399277 | `6ef53006136e5a396533fe406f620e1799e7b0bc4246b380fb18e6294edab423` |
| R02 | [2026-02 国家统计局](https://www.stats.gov.cn/sj/zxfb/202603/t20260304_1962699.html) | [CAS 原件](//wsl.localhost/Ubuntu-22.04/home/tywin/.local/share/pring-cycle/artifacts/sha256/2d/2d5629a61b4ed28718746b3b2559505ba4162612891f5352604a7c1f2a9075ba) | 406069 | `2d5629a61b4ed28718746b3b2559505ba4162612891f5352604a7c1f2a9075ba` |
| R03 | [2026-03 国家统计局](https://www.stats.gov.cn/sj/zxfb/202603/t20260331_1962889.html) | [CAS 原件](//wsl.localhost/Ubuntu-22.04/home/tywin/.local/share/pring-cycle/artifacts/sha256/31/31fc72c16f315e6da565e3cc2fac132d8b3a883878e84e302bbe68b2aad1acfa) | 422725 | `31fc72c16f315e6da565e3cc2fac132d8b3a883878e84e302bbe68b2aad1acfa` |
| R04 | [2026-04 国家统计局](https://www.stats.gov.cn/sj/zxfb/202604/t20260430_1963473.html) | [CAS 原件](//wsl.localhost/Ubuntu-22.04/home/tywin/.local/share/pring-cycle/artifacts/sha256/83/83ee41d92e01359a9397413cc26b6db9088d1d61e05db19a7eae147b946b4aa0) | 422339 | `83ee41d92e01359a9397413cc26b6db9088d1d61e05db19a7eae147b946b4aa0` |
| R05 | [2026-05 国家统计局](https://www.stats.gov.cn/sj/zxfb/202605/t20260531_1963824.html) | [CAS 原件](//wsl.localhost/Ubuntu-22.04/home/tywin/.local/share/pring-cycle/artifacts/sha256/1b/1b0658de10a52ac891f491ef1e6f7120da9b16a25e7d73ca1005dcb8148bcbf3) | 422319 | `1b0658de10a52ac891f491ef1e6f7120da9b16a25e7d73ca1005dcb8148bcbf3` |
| R06 | [2026-06 国家统计局](https://www.stats.gov.cn/sj/zxfb/202606/t20260630_1964032.html) | [CAS 原件](//wsl.localhost/Ubuntu-22.04/home/tywin/.local/share/pring-cycle/artifacts/sha256/f0/f0cc6558252e9d754645aaaedcd8bd5f20f04cc1de5765ba2c6761d4222e159c) | 422863 | `f0cc6558252e9d754645aaaedcd8bd5f20f04cc1de5765ba2c6761d4222e159c` |
| R07 | [2026-07 国家统计局](https://www.stats.gov.cn/sj/zxfb/202607/t20260731_1964253.html) | [既有原件](evidence-13/fff072e83f897a0a9e981e147105ecb81535958dfeaeafcf7881c24ede2a10d6) | 398889 | `fff072e83f897a0a9e981e147105ecb81535958dfeaeafcf7881c24ede2a10d6` |

每页实际含 T1—T8 八个 HTML 表：T1/T2 为制造业表 1/2，T3/T4 为非制造业表，T5—T8 重复前四表。本任务对相关的 T1↔T5、T2↔T6 进行去空白后全表单元格文本比较，**7 页共 14 对相关表完全一致**。只取 T1/T2 对应统计月，不能将重复布局计作双源验证。T1 有 16 行，T2 有 15 行，两者均含单位/表头行。

| 原件组 | T1 起始行 | T2 起始行 | T5/T6 起始行 | 目标日期单元格 |
| --- | ---: | ---: | --- | --- |
| R01—R03 | L332 | L551 | L1214 / L1433 | T1 R16 C1 L538；T2 R15 C1 L809 |
| R04—R07 | L332 | L551 | L1215 / L1434 | T1 R16 C1 L538；T2 R15 C1 L810 |

T/R/C 从 1 起；C 表示该 HTML `<tr>` 实际列出的单元格次序。L 是原始 UTF-8 HTML 中 `<td>` 开始标签的行号，字面数字可能在随后内层 `<p>`。T1 的 `rowspan/colspan` 特别需要区分：T1 R2 C1（日期表头）和 C2（PMI 表头）各 `rowspan=2`，C3 为 `colspan=5`；所以 T1 R3 的第一个实际单元格“生产”对应数据行 C3，第二个“新订单”对应数据行 C4，第三个“原材料库存”对应数据行 C5，不能按 R3 的单元格序号直接错配数据列。

## 精确身份、表头与单位

全部 `period_kind=month`，`period_start` 是原表所标统计月 1 日，`period_end` 为该月最后一日；这 56 组起止边界均按日历独立核对。`measure` 均为 `level`，以下 `series` 与 `source_field` 都是准备包实际身份：

| 指标 | series | source_field | 原表表头与位置 | 对应目标月数据列 |
| --- | --- | --- | --- | --- |
| `CN_PMI_ACTIVITY` | `manufacturing` | `manufacturing_pmi` | T1 R2 C2“PMI”，L340；制造业表 1 | T1 R16 C2 |
| `CN_PMI_ACTIVITY` | `production` | `production` | T1 R3 C1“生产”，L345 | T1 R16 C3 |
| `CN_PMI_ACTIVITY` | `new_orders` | `new_orders` | T1 R3 C2“新订单”，L347 | T1 R16 C4 |
| `CN_PMI_ACTIVITY` | `purchase_volume` | `purchase_volume` | T2 R2 C4“采购量”，L564 | T2 R15 C4 |
| `CN_PMI_INVENTORY` | `raw_materials` | `raw_materials` | T1 R3 C3“原材料库存”，L349 | T1 R16 C5 |
| `CN_PMI_INVENTORY` | `finished_goods` | `finished_goods` | T2 R2 C7“产成品库存”，R01—R03 L571、R04—R07 L572 | T2 R15 C7 |
| `CN_PMI_PRICES` | `purchase_prices` | `purchase_prices` | T2 R2 C5“主要原材料购进价格”，L566 | T2 R15 C5 |
| `CN_PMI_PRICES` | `output_prices` | `output_prices` | T2 R2 C6“出厂价格”，R01—R03 L568、R04—R07 L569 | T2 R15 C6 |

原表 T1 R1 C1 L335、T2 R1 C1 L554 均标“单位：%”；正文中官方表 1 标题 L332、表 2 标题 L551 均注明“经季节调整”。结合附注，准备包以 `diffusion_index_points` 存储其原始 0—100 标度、保留数字本身，与原文语义相符；例如原文 `49.2%` 对应值 `49.2`，不除以 100、不赋予同比或环比涨跌幅含义。

## 56 格字面期望与准备值

“活动”“库存”“价格”分别是上述三项 `CN_PMI_*` 指标的简称。每行的 `series` 加共同的 `measure=level` 唯一指定准备维度。字面期望直接抄录指定原表格，保留一位小数；比较没有四舍五入或容差放行。

| 编号 | 原件/统计期 | 指标 | series | 原表定位 | 字面期望 | 准备值 | 结果 |
| ---: | --- | --- | --- | --- | ---: | ---: | --- |
| 01 | R01 / 2026-01 | 活动 | manufacturing | T1 R16 C2 L540 | 49.3 | 49.3 | 相符 |
| 02 | R01 / 2026-01 | 活动 | production | T1 R16 C3 L542 | 50.6 | 50.6 | 相符 |
| 03 | R01 / 2026-01 | 活动 | new_orders | T1 R16 C4 L544 | 49.2 | 49.2 | 相符 |
| 04 | R01 / 2026-01 | 活动 | purchase_volume | T2 R15 C4 L815 | 48.7 | 48.7 | 相符 |
| 05 | R01 / 2026-01 | 库存 | raw_materials | T1 R16 C5 L546 | 47.4 | 47.4 | 相符 |
| 06 | R01 / 2026-01 | 库存 | finished_goods | T2 R15 C7 L821 | 48.6 | 48.6 | 相符 |
| 07 | R01 / 2026-01 | 价格 | purchase_prices | T2 R15 C5 L817 | 56.1 | 56.1 | 相符 |
| 08 | R01 / 2026-01 | 价格 | output_prices | T2 R15 C6 L819 | 50.6 | 50.6 | 相符 |
| 09 | R02 / 2026-02 | 活动 | manufacturing | T1 R16 C2 L540 | 49.0 | 49.0 | 相符 |
| 10 | R02 / 2026-02 | 活动 | production | T1 R16 C3 L542 | 49.6 | 49.6 | 相符 |
| 11 | R02 / 2026-02 | 活动 | new_orders | T1 R16 C4 L544 | 48.6 | 48.6 | 相符 |
| 12 | R02 / 2026-02 | 活动 | purchase_volume | T2 R15 C4 L815 | 48.2 | 48.2 | 相符 |
| 13 | R02 / 2026-02 | 库存 | raw_materials | T1 R16 C5 L546 | 47.5 | 47.5 | 相符 |
| 14 | R02 / 2026-02 | 库存 | finished_goods | T2 R15 C7 L821 | 45.8 | 45.8 | 相符 |
| 15 | R02 / 2026-02 | 价格 | purchase_prices | T2 R15 C5 L817 | 54.8 | 54.8 | 相符 |
| 16 | R02 / 2026-02 | 价格 | output_prices | T2 R15 C6 L819 | 50.6 | 50.6 | 相符 |
| 17 | R03 / 2026-03 | 活动 | manufacturing | T1 R16 C2 L540 | 50.4 | 50.4 | 相符 |
| 18 | R03 / 2026-03 | 活动 | production | T1 R16 C3 L542 | 51.4 | 51.4 | 相符 |
| 19 | R03 / 2026-03 | 活动 | new_orders | T1 R16 C4 L544 | 51.6 | 51.6 | 相符 |
| 20 | R03 / 2026-03 | 活动 | purchase_volume | T2 R15 C4 L815 | 50.9 | 50.9 | 相符 |
| 21 | R03 / 2026-03 | 库存 | raw_materials | T1 R16 C5 L546 | 47.7 | 47.7 | 相符 |
| 22 | R03 / 2026-03 | 库存 | finished_goods | T2 R15 C7 L821 | 46.7 | 46.7 | 相符 |
| 23 | R03 / 2026-03 | 价格 | purchase_prices | T2 R15 C5 L817 | 63.9 | 63.9 | 相符 |
| 24 | R03 / 2026-03 | 价格 | output_prices | T2 R15 C6 L819 | 55.4 | 55.4 | 相符 |
| 25 | R04 / 2026-04 | 活动 | manufacturing | T1 R16 C2 L540 | 50.3 | 50.3 | 相符 |
| 26 | R04 / 2026-04 | 活动 | production | T1 R16 C3 L542 | 51.5 | 51.5 | 相符 |
| 27 | R04 / 2026-04 | 活动 | new_orders | T1 R16 C4 L544 | 50.6 | 50.6 | 相符 |
| 28 | R04 / 2026-04 | 活动 | purchase_volume | T2 R15 C4 L816 | 51.1 | 51.1 | 相符 |
| 29 | R04 / 2026-04 | 库存 | raw_materials | T1 R16 C5 L546 | 49.3 | 49.3 | 相符 |
| 30 | R04 / 2026-04 | 库存 | finished_goods | T2 R15 C7 L822 | 47.5 | 47.5 | 相符 |
| 31 | R04 / 2026-04 | 价格 | purchase_prices | T2 R15 C5 L818 | 63.7 | 63.7 | 相符 |
| 32 | R04 / 2026-04 | 价格 | output_prices | T2 R15 C6 L820 | 55.1 | 55.1 | 相符 |
| 33 | R05 / 2026-05 | 活动 | manufacturing | T1 R16 C2 L540 | 50.0 | 50.0 | 相符 |
| 34 | R05 / 2026-05 | 活动 | production | T1 R16 C3 L542 | 51.2 | 51.2 | 相符 |
| 35 | R05 / 2026-05 | 活动 | new_orders | T1 R16 C4 L544 | 49.9 | 49.9 | 相符 |
| 36 | R05 / 2026-05 | 活动 | purchase_volume | T2 R15 C4 L816 | 49.8 | 49.8 | 相符 |
| 37 | R05 / 2026-05 | 库存 | raw_materials | T1 R16 C5 L546 | 48.6 | 48.6 | 相符 |
| 38 | R05 / 2026-05 | 库存 | finished_goods | T2 R15 C7 L822 | 49.3 | 49.3 | 相符 |
| 39 | R05 / 2026-05 | 价格 | purchase_prices | T2 R15 C5 L818 | 60.5 | 60.5 | 相符 |
| 40 | R05 / 2026-05 | 价格 | output_prices | T2 R15 C6 L820 | 51.9 | 51.9 | 相符 |
| 41 | R06 / 2026-06 | 活动 | manufacturing | T1 R16 C2 L540 | 50.3 | 50.3 | 相符 |
| 42 | R06 / 2026-06 | 活动 | production | T1 R16 C3 L542 | 51.4 | 51.4 | 相符 |
| 43 | R06 / 2026-06 | 活动 | new_orders | T1 R16 C4 L544 | 51.2 | 51.2 | 相符 |
| 44 | R06 / 2026-06 | 活动 | purchase_volume | T2 R15 C4 L816 | 51.4 | 51.4 | 相符 |
| 45 | R06 / 2026-06 | 库存 | raw_materials | T1 R16 C5 L546 | 48.4 | 48.4 | 相符 |
| 46 | R06 / 2026-06 | 库存 | finished_goods | T2 R15 C7 L822 | 47.7 | 47.7 | 相符 |
| 47 | R06 / 2026-06 | 价格 | purchase_prices | T2 R15 C5 L818 | 54.2 | 54.2 | 相符 |
| 48 | R06 / 2026-06 | 价格 | output_prices | T2 R15 C6 L820 | 48.2 | 48.2 | 相符 |
| 49 | R07 / 2026-07 | 活动 | manufacturing | T1 R16 C2 L540 | 49.2 | 49.2 | 相符 |
| 50 | R07 / 2026-07 | 活动 | production | T1 R16 C3 L542 | 49.9 | 49.9 | 相符 |
| 51 | R07 / 2026-07 | 活动 | new_orders | T1 R16 C4 L544 | 48.5 | 48.5 | 相符 |
| 52 | R07 / 2026-07 | 活动 | purchase_volume | T2 R15 C4 L816 | 49.4 | 49.4 | 相符 |
| 53 | R07 / 2026-07 | 库存 | raw_materials | T1 R16 C5 L546 | 48.3 | 48.3 | 相符 |
| 54 | R07 / 2026-07 | 库存 | finished_goods | T2 R15 C7 L822 | 48.6 | 48.6 | 相符 |
| 55 | R07 / 2026-07 | 价格 | purchase_prices | T2 R15 C5 L818 | 53.2 | 53.2 | 相符 |
| 56 | R07 / 2026-07 | 价格 | output_prices | T2 R15 C6 L820 | 47.8 | 47.8 | 相符 |

| 实际准备分母 | 标量数 | 相符 | 冲突 | 无法独立核验 |
| --- | ---: | ---: | ---: | ---: |
| CN_PMI_ACTIVITY：4 个 series × 7 期 | 28 | 28 | 0 | 0 |
| CN_PMI_INVENTORY：2 个 series × 7 期 | 14 | 14 | 0 | 0 |
| CN_PMI_PRICES：2 个 series × 7 期 | 14 | 14 | 0 | 0 |
| 合计：8 个 series × 7 期 | 56 | 56 | 0 | 0 |

本范围没有原表缺格或无法定位格。页面还含其他分类、非制造业指数和综合 PMI 产出指数，但它们不属于本次已准备的三个指标范围；不能擅自增加字段，也不能把没有准备这些字段称作本次 56 格采集失败。56 格均为实际数字，不存在本次需填零或推算的缺值。

## 扩散指数语义与可审阅反例

R07 L1201、附注 4—5（R01—R03 对应 L1200）明确：分类指数按正向回答企业百分比加回答不变百分比的一半计算；制造业 PMI 由 5 个分类扩散指数加权构成，新订单、生产、从业人员、供应商配送时间、原材料库存的权数依次为 30%、25%、20%、15%、10%，供应商配送时间在合成时反向处理。采购量、产成品库存、购进价格、出厂价格是其他分类指数，不能把制造业总指数复制给它们。现发布指数均经过季节调整。这里引用官方计算说明以核对语义，本次不重算或替代官方已披露值。

同处附注说明 PMI 高于/低于 50 的扩张/收缩解释，正文也分别解释分类指数；这不代表指数的数值是实际产量或价格的增长百分比。可直接用已有原件检查以下拒绝反例：

| 触发反例 | 应拒绝的对应关系 | 原件依据 |
| --- | --- | --- |
| 7 月把 headline `49.2` 填成生产或新订单 | 生产实际 `49.9`、新订单实际 `48.5`，须保留不同 series | R07 T1 R16 C2/C3/C4；正文 L332 同样逐项说明 |
| 把“原材料库存”与“产成品库存”当同一字段 | 前者 `48.3`，后者 `48.6` | R07 T1 R16 C5、T2 R15 C7 |
| 在全篇搜索到非制造业“新订单”就采纳 | 非制造业为 `44.4`，本范围制造业新订单为 `48.5` | R07 T3 R15 C3 L1034；T1 R16 C4 L544 |
| 把制造业购进价格 `53.2` 解读为价格上涨 53.2% | 它是价格扩散指数水平，不是 PPI 涨跌幅 | R07 T2 R15 C5；附注 L1201 的扩散指数定义 |
| 用月环比变化“下降 1.1 个百分点”替代 PMI 水平 | 该变化是解释文本；准备的 manufacturing 水平为 `49.2` | R07 正文 L332 与 T1 R16 C2 |
| 把 5 月 `50.0` 当缺值或整数缺省值 | 该格有明确的官方字面 `50.0`，应保留 | R05 T1 R16 C2 L540 |
| 将目标统计月误选成同名月份的上一年 | 先核对日期列的完整年/月，不能仅按“7月”匹配 | R07 T1 R16 C1“2026年7月”；表内另有 2025 年历史行 |
| 把制造业 PMI 与综合 PMI 产出指数混用 | 7 月分别为 `49.2` 与 `49.3`，不是同一身份 | R07 T1 R16 C2；“三、中国综合PMI产出指数运行情况”L1201 |

上述反例是字段/语义验收边界，不是本次发现当前公开解析器已发生这些错误。当前报告只证明所审阅的准备快照与原表相符。

## PUBLIC、回执和版本仍未完成的边界

7 页 L11 的 `PubDate` 与可见页头 L277 均给出相同的年月日、时、分，本次与准备记录逐页核对一致：

| 原件 | 页头及 PubDate 原文 | 可证范围 |
| --- | --- | --- |
| R01 | 2026/01/31 09:30 | 原文标注，精度到分钟 |
| R02 | 2026/03/04 09:30 | 原文标注，精度到分钟 |
| R03 | 2026/03/31 09:30 | 原文标注，精度到分钟 |
| R04 | 2026/04/30 09:30 | 原文标注，精度到分钟 |
| R05 | 2026/05/31 09:30 | 原文标注，精度到分钟 |
| R06 | 2026/06/30 09:30 | 原文标注，精度到分钟 |
| R07 | 2026/07/31 09:30 | 原文标注，精度到分钟 |

2 月统计期的原文标注时间是 **2026/03/04 09:30**，不能由“PMI 通常月末发布”推算成 2 月 28 日，也不能用 URL 发布月代替统计月。其余月末页头也不构成未来全部期次的固定发布日历证明。

这些字段证明已存页面的标注时间；原文时间字段没有声明时区或秒数。本次没有独立补证首次发布、时区声明或之后替换/更正记录。项目采用 Asia/Shanghai 的解释不等于本次新增的官方时区依据，`09:30:00` 的秒数也没有从分钟精度原文得到证明；不能直接将旧准备包的 `public_available_at` 标签升级为历史 PUBLIC 认证。

[原研究 HTTP 回执](evidence-13/receipts.json) 的 15 条记录按这 7 份 SHA 或源 URL 匹配，匹配到的原始获取回执为 **0**。[原件导入记录](evidence-13/imports.json) 仅 R07 匹配：`imported_at=2026-09-06T16:16:32.099813+00:00`，398889 字节、CAS 路径和 SHA 一致。它是复制/导入时间，不是原始 HTTP 首次取得或历史首次公开时间；其余 6 份未在该导入记录中匹配。这个结论仅限定于所审阅文件，不断言其他未读存储一定没有回执。

准备包对这 7 份均保留 `original_transport_receipt_in_this_package=false`、`acquisition_time=null`、`historical_first_publication_certified=false`；本报告不改这些状态。季节调整和页面历史行使原件版本需要单独保留，7 个保存版本及其当前月对照不证明“从未修订”、也不是完整历史原始版本链。未读取企业级调查原始问卷，不将官方数值核对宣称成独立重算指数。

R07 页脚 L3232 显示“版权所有：国家统计局”和“服务条款”入口；本轮未扩展读取对应条款全文，不作新增法律许可判断。版权署名不单独证明个人本机分析被禁止，也不证明所有再分发用途都已许可；维持既有任务范围，不额外增设采购或审批门槛。

本材料可供这 56 格的候选认证准备使用，仍需在正式流程中关联取得并校验完成时间、来源声明、源时间资格、原件版本与修订边界。本次新增认证 **0**、模型采用 **0**；不宣告 P1 候选矩阵、历史 120 交易日、当前模型结论或报告解释通过。

## 精确交付和只读复核

本任务仅新增：

```text
.scratch/pring-data-acquisition-repair/p1-pmi-full-value-audit.md
```

没有网络请求、应用解析器执行、凭证读取或生产/认证/模型写入，未改旧准备包和应用。复核范围包括 7 份原件 SHA/字节、14 对相关重复表全表一致、56 格原表数字与源码定位、56 格准备身份/单位/统计月边界，以及本报告全部本地 Markdown 链接。最终报告字节数与 SHA 在交付消息提供，避免自包含摘要循环。

项目根目录的只读报告校验命令：

```powershell
Get-Item -LiteralPath '.scratch/pring-data-acquisition-repair/p1-pmi-full-value-audit.md' | Select-Object Length
Get-FileHash -LiteralPath '.scratch/pring-data-acquisition-repair/p1-pmi-full-value-audit.md' -Algorithm SHA256
```

