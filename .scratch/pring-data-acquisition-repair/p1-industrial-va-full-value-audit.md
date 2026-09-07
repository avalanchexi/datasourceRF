# 工业增加值：20 个准备标量逐值核对

研究日期：2026-09-08（Asia/Shanghai）。独立字面期望与准备值的数值、身份检查执行于 2026-09-07T17:22:49.384258+00:00，即北京时间 2026-09-08 01:22:49。

实际家族确为 **`nbs_industrial_value_added`**，指标为 `CN_INDUSTRIAL_VA`。实际准备范围是 7 期：2025-12、2026-02 至 2026-07。**20 个标量全部相符，冲突 0，无法独立核验 0**；字段、单位、维度、统计期边界也为 20/20 相符。单月实际同比 6 格、累计实际同比 7 格、季调环比 7 格。

7 份唯一原件共 **2,664,666 字节**，原始字节及 SHA 全部重新核对一致。与旧 18 个代表锚点重叠 **1 格**，本次新增独立逐值覆盖 **19 格**。这不是 20 个新增锚点，也不是 P1 认证或 120 交易日重放通过。

## 输入与独立方法

已读取 [准备脚本](evidence-13-preparation/prepare.py)、[准备快照](evidence-13-preparation/preparation.json)、[旧代表锚点](evidence-13-preparation/anchor-expectations.json)。按实际家族得到 7 条解析记录、7 份原件和 20 个唯一标量身份；未扩展其他工业家族。

本次只用 Windows `C:/Python313/python.exe -B` 标准库处理已有原件。`HTMLParser` 记录原始表、行、单元格文本及起始源码行，解码实体并合并空白。先独立阅读官方表头、主指标行、环比表和首段，显式录入字面数字期望，再以 `Decimal` 比较准备快照。没有用准备输出生成期望、复制应用正则/计算逻辑或调用应用解析器，也未重跑或修改 `prepare.py`。

全部目标数字都在原表直接存在，首段另有相同期间和数字复证。保持 `percent` 数值标度，不除以 100，无单位换算、无容差放行。此结论针对固定准备快照，不称为当前安装应用的解析回归。

| 固定输入 | 字节数 | SHA-256 |
| --- | ---: | --- |
| `evidence-13-preparation/prepare.py` | 18456 | `e9295dcd722d9ff1f67e9fb0e57db6154c297510f80df344258b69971f638b27` |
| `evidence-13-preparation/preparation.json` | 2767926 | `a9fe475c47303fb7791b27df04849dcef0aacabde27b64f57023972c9a4ec20a` |
| `evidence-13-preparation/anchor-expectations.json` | 4152 | `e4ba9fe88c93701d7fa6ba7f2cca1e37387b95ba2f91771b320fa7be7035eafe` |
| `evidence-13/receipts.json` | 11329 | `edb8fa76f4254b96867d3c55bcd58b1ba432a5d8f71cedbd5c372773663c37c9` |
| `evidence-13/imports.json` | 5145 | `07da00c64b09c728052b2c2ab5ff7156df6e403714f28653e86d4b9c9855b875` |

## 官方精确原件

6 份给出既有 CAS 的本机 UNC 路径，7 月原件另有既有仓库相对路径，未复制或联网下载。下表摘要是原始字节 SHA，不是去标签文本摘要。

| 原件 | 准备截至期与官方出处 | 精确原件路径 | 字节数 | SHA-256 |
| --- | --- | --- | ---: | --- |
| R01 | [2025-12 国家统计局](https://www.stats.gov.cn/sj/zxfb/202601/t20260119_1962329.html) | [CAS 原件](//wsl.localhost/Ubuntu-22.04/home/tywin/.local/share/pring-cycle/artifacts/sha256/26/26b1c5458d483c9be7ef53b7dacd1a97a3c26c0d73448312cb9ad6b24eb8d41f) | 406130 | `26b1c5458d483c9be7ef53b7dacd1a97a3c26c0d73448312cb9ad6b24eb8d41f` |
| R02 | [2026-02 国家统计局](https://www.stats.gov.cn/sj/zxfb/202603/t20260316_1962782.html) | [CAS 原件](//wsl.localhost/Ubuntu-22.04/home/tywin/.local/share/pring-cycle/artifacts/sha256/21/2115d7cc67a22dd15a88c93101be752711a72e7f41534b01b1e8f7528f341f8e) | 282785 | `2115d7cc67a22dd15a88c93101be752711a72e7f41534b01b1e8f7528f341f8e` |
| R03 | [2026-03 国家统计局](https://www.stats.gov.cn/sj/zxfb/202604/t20260416_1963329.html) | [CAS 原件](//wsl.localhost/Ubuntu-22.04/home/tywin/.local/share/pring-cycle/artifacts/sha256/48/481bb421c08fde4958091570e3e4fc1a6dffab863779b984469cef239bcb3176) | 410317 | `481bb421c08fde4958091570e3e4fc1a6dffab863779b984469cef239bcb3176` |
| R04 | [2026-04 国家统计局](https://www.stats.gov.cn/sj/zxfb/202605/t20260518_1963731.html) | [CAS 原件](//wsl.localhost/Ubuntu-22.04/home/tywin/.local/share/pring-cycle/artifacts/sha256/2e/2e43dd7ae7710d1183f4b78091319d638b0cdfa2d3ad39ecb6760227b317126f) | 384311 | `2e43dd7ae7710d1183f4b78091319d638b0cdfa2d3ad39ecb6760227b317126f` |
| R05 | [2026-05 国家统计局](https://www.stats.gov.cn/sj/zxfb/202606/t20260616_1963953.html) | [CAS 原件](//wsl.localhost/Ubuntu-22.04/home/tywin/.local/share/pring-cycle/artifacts/sha256/13/1390e559c07b647b5097ebea3e9fb23ff93e153d536e2a4d7f499f251dccf623) | 385165 | `1390e559c07b647b5097ebea3e9fb23ff93e153d536e2a4d7f499f251dccf623` |
| R06 | [2026-06 国家统计局](https://www.stats.gov.cn/sj/zxfb/202607/t20260715_1964123.html) | [CAS 原件](//wsl.localhost/Ubuntu-22.04/home/tywin/.local/share/pring-cycle/artifacts/sha256/e8/e81c7eb1fbbac305dd51797d8aead0825ec28cbf19826386856ec9b90e789ddb) | 402627 | `e81c7eb1fbbac305dd51797d8aead0825ec28cbf19826386856ec9b90e789ddb` |
| R07 | [2026-07 国家统计局](https://www.stats.gov.cn/sj/zxfb/202608/t20260817_1965055.html) | [既有原件](evidence-13/d8a9cc4305ea657b6d9eeecc8633afcf6934bc05f7da72c9969c89e465833609) | 393331 | `d8a9cc4305ea657b6d9eeecc8633afcf6934bc05f7da72c9969c89e465833609` |

各页数据首段起始源码行是 L331，T1 从 L332 开始。R02 标题为“2026年1—2月份规模以上工业增加值增长6.3%”；R04 标题为“2026年1—4月份规模以上工业增加值增长5.6%”，其 4 月单月同比另为 4.1%。标题上的数字不能一律绑定为单月同比。

每页包含 T1/T2 数据表和 T3/T4 重复布局；7 页共 **14 对相关表**（T1↔T3、T2↔T4）全部单元格去空白后相同。重复布局不计作双源。T1 均有 73 行，R02 的 T2 有 15 行，其余 T2 为 14 行。

| 原件组 | T1 起始行 | T2 起始行 | T3/T4 起始行 | 当期环比位置 |
| --- | ---: | ---: | --- | --- |
| R02 | L332 | L841 | L937 / L1446 | T2 R15 C1“2月”，数值 C2 L922 |
| R01、R03—R07 | L332 | L1132 | L1223 / L2023 | T2 R14 C1 对应月，数值 C2 L1208 |

T/R/C 以文档次序从 1 起，C 是当前 HTML 行实际单元格次序，L 是单元格开始标签源码行，数字可能在随后内层段落。T2 年份使用纵向合并单元格，当期行只有“月份、数值”两格；年份需结合上方合并单元格和本期正文，不能只按月份或第三列机械选值。

## 字段、单位和期间

全部 `metric_id=CN_INDUSTRIAL_VA`、`unit=percent`。同比是扣除价格因素的实际增长率，环比是季节调整后增长率，均不是增加值金额或基期为 100 的水平值。T1“绝对量”列在本指标行显示“…”；不能把“…”当作 0，或套用表中出口交货值的亿元单位。

| measure | source_field | period_kind | 原表身份 |
| --- | --- | --- | --- |
| current_month_real_yoy | industrial_va_yoy_real_pct | month | 除 R02 外的当月同比增长（%），T1 R3 C3 |
| ytd_real_yoy | industrial_va_ytd_yoy_real_pct | year_to_month | 1—N 月同比增长（%），通常 T1 R3 C5；R02 合并期为 T1 R3 C3 |
| mom_seasonally_adjusted | industrial_va_mom_sa_pct | month | T2“环比增速（%）”，附注说明季节调整模型修订及本期环比 |

一般月份 T1 的当月列组在 R1 C2 L337，1—N 月列组在 R1 C3 L339；二者分别跨“绝对量/同比增长”两列。R2 的同比表头 L344/L349 对应数据行 C3/C5。R02 只有 R1 C2“1—2月”列组，R2 L342 的同比表头对应数据行 C3；同一个物理 C3 在这两种表头下不能绑定为相同的单月字段。

`month` 起止为统计月首日至月末，`year_to_month` 为该年 1 月 1 日至统计月末，20 组均已独立按日历核对。R01 全年累计覆盖 2025-01-01 至 12-31；R02 累计覆盖 2026-01-01 至 02-28，环比覆盖 2026-02 的月份标识。不能把 1—2 月累计同比表示为仅 2 月单月同比。

所有页首段 L331 同时给出实际同比和当月环比语义，累计同比亦在首段明确：R01 全年 5.9%、R02 1—2 月 6.3%、R03 1—3 月 6.1%、R04 1—4 月 5.6%、R05 1—5 月 5.4%、R06 1—6 月 5.4%、R07 1—7 月 5.3%。这是原表定位以外的字面复证，未用累计平均推导单月值。

## 20 格原表期望与准备值

期望保留原始小数位。`0.40` 与 JSON `0.4` 只作十进制表示等值比较，无舍入或容差。准备值列用等值十进制显示。

| 编号 | 原件/准备期 | measure | 原表定位 | 字面期望（%） | 准备值（%） | 结果 | 与旧18锚点重叠 |
| ---: | --- | --- | --- | ---: | ---: | --- | --- |
| 01 | R01 / 2025-12 | current_month_real_yoy | T1 R3 C3 L357 | 5.2 | 5.2 | 相符 | 否 |
| 02 | R01 / 2025-12 | ytd_real_yoy | T1 R3 C5 L361 | 5.9 | 5.9 | 相符 | 否 |
| 03 | R01 / 2025-12 | mom_seasonally_adjusted | T2 R14 C2 L1208 | 0.49 | 0.49 | 相符 | 否 |
| 04 | R02 / 2026-02 | ytd_real_yoy | T1 R3 C3 L350 | 6.3 | 6.3 | 相符 | 否 |
| 05 | R02 / 2026-02 | mom_seasonally_adjusted | T2 R15 C2 L922 | 0.83 | 0.83 | 相符 | 否 |
| 06 | R03 / 2026-03 | current_month_real_yoy | T1 R3 C3 L357 | 5.7 | 5.7 | 相符 | 否 |
| 07 | R03 / 2026-03 | ytd_real_yoy | T1 R3 C5 L361 | 6.1 | 6.1 | 相符 | 否 |
| 08 | R03 / 2026-03 | mom_seasonally_adjusted | T2 R14 C2 L1208 | 0.28 | 0.28 | 相符 | 否 |
| 09 | R04 / 2026-04 | current_month_real_yoy | T1 R3 C3 L357 | 4.1 | 4.1 | 相符 | 否 |
| 10 | R04 / 2026-04 | ytd_real_yoy | T1 R3 C5 L361 | 5.6 | 5.6 | 相符 | 否 |
| 11 | R04 / 2026-04 | mom_seasonally_adjusted | T2 R14 C2 L1208 | 0.05 | 0.05 | 相符 | 否 |
| 12 | R05 / 2026-05 | current_month_real_yoy | T1 R3 C3 L357 | 4.5 | 4.5 | 相符 | 否 |
| 13 | R05 / 2026-05 | ytd_real_yoy | T1 R3 C5 L361 | 5.4 | 5.4 | 相符 | 否 |
| 14 | R05 / 2026-05 | mom_seasonally_adjusted | T2 R14 C2 L1208 | 0.40 | 0.40 | 相符 | 否 |
| 15 | R06 / 2026-06 | current_month_real_yoy | T1 R3 C3 L357 | 5.3 | 5.3 | 相符 | 否 |
| 16 | R06 / 2026-06 | ytd_real_yoy | T1 R3 C5 L361 | 5.4 | 5.4 | 相符 | 否 |
| 17 | R06 / 2026-06 | mom_seasonally_adjusted | T2 R14 C2 L1208 | 0.76 | 0.76 | 相符 | 否 |
| 18 | R07 / 2026-07 | current_month_real_yoy | T1 R3 C3 L357 | 4.5 | 4.5 | 相符 | 是 |
| 19 | R07 / 2026-07 | ytd_real_yoy | T1 R3 C5 L361 | 5.3 | 5.3 | 相符 | 否 |
| 20 | R07 / 2026-07 | mom_seasonally_adjusted | T2 R14 C2 L1208 | 0.11 | 0.11 | 相符 | 否 |

| 实际分母 | 标量数 | 相符 | 冲突 | 无法独立核验 | 与旧锚点重叠 |
| --- | ---: | ---: | ---: | ---: | ---: |
| current_month_real_yoy | 6 | 6 | 0 | 0 | 1 |
| ytd_real_yoy | 7 | 7 | 0 | 0 | 0 |
| mom_seasonally_adjusted | 7 | 7 | 0 | 0 | 0 |
| 合计 | 20 | 20 | 0 | 0 | 1 |

旧锚点唯一重叠完整身份为 `family=nbs_industrial_value_added`、`metric_id=CN_INDUSTRIAL_VA`、`period=2026-07`、`measure=current_month_real_yoy`、`source_field=industrial_va_yoy_real_pct`、`unit=percent`、`value=4.5`。按这一身份计算交集，不能因 2026-05 也有 4.5 就多算重叠。旧锚点全集 18，本次交集 1，新增独立逐值覆盖为 20−1=19；旧文件未改写。

## 合并期与不能补造的值

R02 的标题、首段和 T1 表头只提供 1—2 月累计同比 6.3，并无该处 2 月单月同比字面值。准备包未生成该格，不属于 20 格分母内的核验失败；不能填零、复制累计值或按两个月平均拆分。

R02 L841 的附注明确工业生产报表按月调查、1 月数据免报。但**免报不等于原件没有任何 1 月环比**：同页 T2 R14 C1 为“2026年”、C2 为“1月”、C3 L917 为 `0.39`，随后 R15 给出 2 月 `0.83`。这个 1 月环比不在本次准备标量范围，既不能擅自加进分母，也不能宣称原件没有它。

R04 的标题/首句先写累计 5.6，之后才写 4 月单月 4.1，是拒绝“标题数字就是单月同比”的真实反例。R05 环比 0.40% 与正文“同比增速比上月加快 0.4 个百分点”数值相近，但须按环比表和明确环比句选值，不能凭数字出现认定字段。这些是验收边界，不是宣告当前应用已经发生上述误配。

## 真实修订与历史版本

原文附注明确环比数据随季节调整模型自动修正；本轮并非仅凭假设提出修订风险。每页同时发布当前月环比和前期修订表：

| 原件 | 附注位置 | 原文说明的修订历史范围 | 同页当前环比范围 |
| --- | --- | --- | --- |
| R01 | L1132 | 2024 年 12 月至 2025 年 11 月 | 2025 年 12 月 |
| R02 | L841 | 2025 年 1 月至 12 月 | 2026 年 1、2 月 |
| R03 | L1132 | 2025 年 3 月至 2026 年 2 月 | 2026 年 3 月 |
| R04 | L1132 | 2025 年 4 月至 2026 年 3 月 | 2026 年 4 月 |
| R05 | L1132 | 2025 年 5 月至 2026 年 4 月 | 2026 年 5 月 |
| R06 | L1132 | 2025 年 6 月至 2026 年 5 月 | 2026 年 6 月 |
| R07 | L1132 | 2025 年 7 月至 2026 年 6 月 | 2026 年 7 月 |

这些文字证明修订机制与所述窗口，不代表本轮逐一核验过历史窗口中所有数值是否实际改变。本次 20 格只与其各自原件绑定，未将晚期页面的历史行覆盖先前版本，也未拼接晚期修订值与早期发布日期。历史点时重放仍需选择当时有资格的原件版本。

同处附注还说明，企业年度进出、新建/破产/注销及跨地区重复产量剔重会导致与上年公布数的口径差异，同期数应尽可能匹配本期范围。本次使用官方已披露增长率，不由跨年度金额或其他产品产量重算实际同比。

## PUBLIC 和回执边界

各页 L11 `PubDate` 与可见页头 L277 同时标注下列分钟精度时间，与准备字段的年月日、时、分一致：

| 原件 | 页头及 PubDate | 本次可证明范围 |
| --- | --- | --- |
| R01 | 2026/01/19 10:00 | 已存页面所标时间，精度到分钟 |
| R02 | 2026/03/16 10:00 | 已存页面所标时间，精度到分钟 |
| R03 | 2026/04/16 10:00 | 已存页面所标时间，精度到分钟 |
| R04 | 2026/05/18 10:00 | 已存页面所标时间，精度到分钟 |
| R05 | 2026/06/16 10:00 | 已存页面所标时间，精度到分钟 |
| R06 | 2026/07/15 10:00 | 已存页面所标时间，精度到分钟 |
| R07 | 2026/08/17 15:00 | 已存页面所标时间，精度到分钟 |

R07 真实页头为 **15:00**，不能沿用其余六页的 10:00，也不能套用 CPI/PPI 的 09:30。时间字段未声明时区或秒数；项目按 Asia/Shanghai 解释不是本次新增的源时区证明，分钟标注也不能补证准备字段的 `:00` 秒。页面标注时间不独立证明当前保存字节就是历史首次公开版本。

[原研究 HTTP 回执](evidence-13/receipts.json) 的 15 条记录按这 7 个 SHA 或源 URL 匹配，原始获取回执匹配数为 **0**。[原件导入记录](evidence-13/imports.json) 只有 R07 匹配：`imported_at=2026-09-06T16:16:32.087933+00:00`、393331 字节，CAS 路径和 SHA 一致。它是复制/导入时间，不是首次 HTTP 获取或历史首次公开；其他 6 份未在该导入文件匹配。这一结论仅限定于已审阅文件，不推断其他未读存储一定没有回执。

准备包对这些原件均保存 `original_transport_receipt_in_this_package=false`、`acquisition_time=null`、`historical_first_publication_certified=false`，本次未覆盖状态。正式认证仍需关联来源声明、取得并校验完成时间、源时间资格和修订版本。本次 **认证 0、模型采用 0**，不宣告候选矩阵、当前模型结论、报告解释或 120 交易日重放通过。

## 精确交付和只读校验

本任务仅新增：

```text
.scratch/pring-data-acquisition-repair/p1-industrial-va-full-value-audit.md
```

无网络请求、应用解析器执行、凭证读取或生产/认证/模型写入，未改旧包、旧报告和应用。复核包括 7 份原件字节/SHA、14 对重复表、20 格数字/位置/身份/单位/期间、与旧 18 锚点的唯一交集及全部本地 Markdown 链接。报告最终字节数和 SHA 在交付消息提供，避免文件包含自身摘要的循环。

项目根目录只读检查：

```powershell
Get-Item -LiteralPath '.scratch/pring-data-acquisition-repair/p1-industrial-va-full-value-audit.md' | Select-Object Length
Get-FileHash -LiteralPath '.scratch/pring-data-acquisition-repair/p1-industrial-va-full-value-audit.md' -Algorithm SHA256
```
