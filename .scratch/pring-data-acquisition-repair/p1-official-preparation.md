# A18 常规官方来源：当前纯解析器准备包

研究始于北京时间 2026-09-07，交付于 2026-09-08；逐次执行保留原始 UTC 时刻。依据 [27 项准备清单](p1-certification-readiness.md) 的 A 组，已在指定 WSL 环境重新执行公开纯解析接口：**250 份官方原件、20,069,217 字节，11 个家族共 268 次解析成功，覆盖 18 项指标、1858 个标量**。其中 18 个代表性标量通过预先明确的数值/字段/单位/期次期望，其余 **1840 个标量未逐格独立事实审计**。

本包是来源材料准备，不是来源认证、候选采用矩阵或历史 PUBLIC 合格结果。没有新 HTTP、搜索、账户/密钥、数据库操作、目录/模型创建或生产导入；没有修改安装环境、应用源码或旧原件。LPR、DR007、Shibor、RRR、仓单、4 项纯派生及 GDP 不在本次 A18 执行范围。

## 当前执行与旧记录分开

公开接口是 `pring_cycle.official_context.parse_official_context_document(content, family, source_url, expected_period, fetched_at)`。执行限定为 Ubuntu-22.04 用户 tywin，`env -u PYTHONPATH`，`/home/tywin/.local/share/pring-cycle/dev-venv/bin/python -B`，模块实际位于该 venv 的 `site-packages/pring_cycle/official_context.py`。检查安装元数据无 editable 标志；81 个安装 Python 文件与工作树按 LF 标准化逐字节相同。此次官方解析模块的安装/工作树精确 SHA 均为 `fae1b0310e6534b2d6ebd6a439614460f1ce4ecfdd4dcbd70361319736ad9d73`。

[preparation.json](evidence-13-preparation/preparation.json) 的 `execution` 保存本次最终生成的起止 UTC、耗时、解释器、用户、每次解析调用的开始/完成和状态。`parser_fetched_at_argument` 只是本次研究验证时钟，用于接口“不早于发布”的纯校验参数，**不是原件取得时钟、历史 SYSTEM 或 PUBLIC 时间**。原 transport 未复制进本包，`acquisition_time=null`；已有请求/导入时间仍由原来源包持有。

旧 [270 件历史清单](evidence-13/69f29104d4152da5082013214ae6817634a9a268dd9f9859aa85cda985417eec) 包含 GDP 11 件、LPR 9 件；本次排除后为 250 件。旧 [288 次/13 家族解析](evidence-13/history-verification.json) 排除 GDP 11 次、LPR 9 次后，对应本次的 **268 次/11 家族**。同一金融统计页服务多个家族，故 268 次调用不等于 268 份原件。268 个当前结果与对应旧结果在统一 datetime JSON 表示后相同，比较发生在添加本包独立检查标志之前；这证明未出现已比较输出差异，不给旧时间标签追加认证。

生成阶段执行了两次完整当前解析，每次 268 次：首次生成后补入独立日历期次检查，再生成本轮最终 JSON。首次执行 2026-09-07T15:54:03.395399Z—15:54:10.584316Z，耗时 7.188912857 秒；第二次精确事件记录保留在最终 JSON。另执行一次默认只读重跑，结果保存在 [重跑输出](evidence-13-preparation/read-only-reparse-output.json)。三轮累计 **804 次纯解析调用**，不增加独立原件、期次、指标、标量或样本分母。两次生成只更新本轮新文件，没有覆盖旧研究结果。

## 可复算清单结构和独立检查边界

[预先明确的代表性期望](evidence-13-preparation/anchor-expectations.json) 为每项 A18 指标给一条来自已核官方原件的明确期望；它不是从当前输出自动生成的答案。包括 DR007 之外的 OMO 1.4%/200 亿元、PMI 新订单 48.5、存货 72700 亿元、M1 1154600 亿元、企业中长期累计增量 53200 亿元等。数值采用 Decimal 比较，同时检查 metric、family、请求期次、dimensions、source_field 和 unit；18/18 通过。

机器清单保留：

| 区段 | 内容 | 证明边界 |
|---|---|---|
| `data.raw_artifacts` | 250 件准确 CAS 路径、源 URL、SHA/长度、原请求期次、原页 meta 与可见时间候选/上下文 | SHA 证明所读字节身份；没有新抓取或首次发表认证 |
| `data.results` | 268 个真实当前调用结果；逐标量 metric/source_field/值/unit/维度/period_kind/start/end、解析 release/public、旧结果比较、独立检查状态 | 当前公开纯解析器可读；不等于字段逐格人工审定或已迁移旧源声明 |
| `data.anchor_checks` | 18 条固定代表性数值期望、对应原件和比较结果 | 只对选中的 18 个标量作独立数值核验，其他 1840 个明确 `not_individually_fact_audited` |
| `independent_period_binding_status` | 用标准库 calendar 按请求日/月/季和 period_kind 独立核对 start/end；1858/1858 符合 | 日历绑定正确；不是每篇正文实际统计身份的第二次完整人工审计 |
| `page_time_review` | 268/268 解析时间有独立收集的可见日期文本对应；保留分钟/秒精度、meta 和附近正文 | 是词法对应检查，尚未将所有候选逐篇人工判断为页头、首次发布或未修订版本；Asia/Shanghai 沿用项目解释 |
| `metric_summary` / `family_summary` | 18 指标及 11 家族分别统计标量、实际期次、字段/单位/频率和未认证状态 | 不是来源调用成功率混成指标可用率，不是候选模型采用矩阵 |

每份原件有拥有该事实的官方 `source_url`，不是检索摘要或第三方替代值。代表性原文与单位/口径的已核依据见 [A18 逐行原件及官方 URL](p1-certification-readiness.md)；本次不重复搬运 20 MB 原件，清单引用只读 CAS，每次复算重新校验精确 SHA。

## 11 家族与 18 指标的准确分母

| 家族 | 原件×家族调用数 | 实际期次 | 标量数 | 对应指标 |
|---|---:|---|---:|---|
| nbs_capacity_utilization | 3 | 3 季，2025-Q4—2026-Q2 | 9 | CN_CAPACITY_UTILIZATION |
| nbs_core_cpi | 8 | 8 月，2025-12—2026-07 | 46 | CN_CPI_HEADLINE 23、CN_CORE_CPI 23 |
| nbs_industrial_finance | 7 | 7 期，2025-12—2026-07，不单列 1 月 | 70 | CN_INDUSTRIAL_FINANCE 42、CN_FINISHED_GOODS_INVENTORY 14、CN_INVENTORY_TURNOVER 14 |
| nbs_industrial_value_added | 7 | 7 期，含 1—2 月合并报告 | 20 | CN_INDUSTRIAL_VA |
| nbs_pmi | 7 | 7 月，2026-01—07 | 56 | CN_PMI_ACTIVITY 28、CN_PMI_INVENTORY 14、CN_PMI_PRICES 14 |
| nbs_ppi | 8 | 8 月，2025-12—2026-07 | 69 | CN_PPI |
| pbc_loan_structure | 31 | 31 月，2024-01—2026-07 | 279 | CN_LOAN_STRUCTURE |
| pbc_money | 7 | 7 月，2026-01—07 | 28 | CN_M1_M2 |
| pbc_omo_notice | 131 | 131 操作日，2026-02-24—08-28 | 252 | CN_OMO_7D_AMOUNT 131、CN_OMO_7D_RATE 121 |
| pbc_social_financing | 51 | 31 月，部分存量/增量分别成文 | 837 | CN_SF_TOTAL 93、CN_SF_COMPONENTS 744 |
| pbc_tool_liquidity_monthly | 8 | 8 月，2025-12—2026-07 | 192 | CN_TOOL_LIQUIDITY_MONTHLY |
| **合计** | **268 次；250 份不同原件** | **不跨频率相加为统一期数** | **1858** | **18 个唯一指标** |

这些值是当前原件解析结果，不是旧数据库某个 PUBLIC/SYSTEM 查询点数。例如当前 CPI headline 23 个标量并不能消除旧 PUBLIC 只读到 6 月的问题；那仍需新源声明与版本选择的正式验证。

## 缺列、合并期与零操作的五条专项检查

这五条都从准确原件重新收集可见文本，再核对公开解析器输出，不修改业务口径。结果全通过，详见 `data.special_cases` 中的源 URL、完整 SHA、明确文本锚点和结果。

1. 2026-01 headline CPI：仅 2 个 MoM/YoY 标量，不虚构 `cumulative_average_yoy`；[官方页](https://www.stats.gov.cn/sj/zxfb/202602/t20260211_1962588.html)，原件 SHA `f65b52d3c2418f40a43e0991d041e0295e56941ca7d9bc9bad76e0d5d0cab964`。
2. 同页核心 CPI：同样 2 个标量，累计平均字段未单列。第一、二项是一个原件服务两个指标，不计成两份原件。
3. 2026-01 PPI：3 类 × MoM/YoY 共 6 个标量，不凑成 9；[官方页](https://www.stats.gov.cn/sj/zxfb/202602/t20260211_1962587.html)，SHA `e7e65eb8ae0656afae92ab36bcb8a6c261be5af0422352fadbecf45c4a0e2943`。
4. 2026-01—02 工业增加值：YTD 实际同比和 02 月季调 MoM 共 2 个标量，没有独立 02 月实际同比；[官方页](https://www.stats.gov.cn/sj/zxfb/202603/t20260316_1962782.html)，SHA `2115d7cc67a22dd15a88c93101be752711a72e7f41534b01b1e8f7528f341f8e`。
5. 2026-08-11 OMO：原文明确操作量为零，解析没有利率标量。该项防止把无利率列写成 0%；[官方公告](https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/125431/125475/2026081108552245312/index.html)，SHA `3a06a019cbde41e74f2a90ff532d688d49b01242c69a80f8bb5afb9480a87c2a`。

专项检查只是上述代表性边界，不宣称已经独立人工核完全部 10 份无利率公告。各历史标量的独立事实审计状态仍保留。

## 仍需的认证材料和下一动作

本次给 A18 增加了当前解析版本、原件/指标/标量关联、独立期次与样本状态，可以据此整理正式家族认证包。但以下门槛尚未执行：

- 以来源实际取得记录、新源声明及修订版本承接原件，不能把此次纯解析 `fetched_at` 写成原始取得或历史 SYSTEM。旧清单 `release_at` 只是只读比较参考，未迁移到任何新来源声明。
- 针对所引用版本审查真实发布时间证据、日期精度及变更后时间；词法匹配不证明历史首发或页面没有修订。没有可靠时间的未来版本仍保持未知，不能以旧值补齐。
- 各家族的完整字段、单位、统计边界、用途、原件血缘和必要预热通过正式来源/定义认证。18 样本只是抽样准备，不是要求逐历史值双来源，也不是省略家族许可/范围条件。
- OMO 政策有效期与净投放到期量、月季发布时点、社融/贷款同年 YTD 差分及修订留存按原契约验收。没有重建 120 个 cutoff 的实际候选输入，也没有创建新目录、模型或正式切换。

下一步可以从该机器清单形成 A18 新来源认证材料草案，优先处理逐期成员状态和可靠时间承接。B/C 组仍按 [准备清单](p1-certification-readiness.md) 各自缺件推进，不把 A18 完成研究包装成票 13 完成。

## 精确交付和默认只读复算

最终精确交付为 **8 个文件**，名单见 [delivery-files.txt](evidence-13-preparation/delivery-files.txt)，每份交付的字节/SHA 在 [manifest](evidence-13-preparation/delivery-verification.json)。重跑 JSON 是外层 PowerShell 对脚本 stdout 的捕获，默认重跑脚本自身不写文件。不复制原 CAS，不修改旧历史报告。manifest 自身列入名单但不递归自哈希。

[prepare.py](evidence-13-preparation/prepare.py) 默认重新调用当前安装公开纯解析器、读取原件、独立检查并与最终 JSON 比较；不写文件。仅显式 `--write-report` 写本轮 `preparation.json`。重跑必须使用指定 WSL 环境：

```powershell
wsl.exe -d Ubuntu-22.04 -u tywin -- env -u PYTHONPATH /home/tywin/.local/share/pring-cycle/dev-venv/bin/python -B /mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/evidence-13-preparation/prepare.py
```

[verify_delivery.py](evidence-13-preparation/verify_delivery.py) 默认只用标准库核查交付 SHA、250 份 CAS 原件、1858/18/1840 分母、输入摘要和本地链接，不导入应用；Windows 访问 CAS 使用明确的 WSL 共享路径。仅显式 `--write-report` 生成本包清单/manifest：

```powershell
C:/Python313/python.exe -B D:/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/evidence-13-preparation/verify_delivery.py
```

如父代理后续改变安装/工作树源码，纯解析重跑应明确报告代码指纹不一致或结果变化，由新的研究执行产生新版本；不能为通过旧包验证而覆盖旧代码或篡改记录。标准库 hash 校验与真实解析重跑是两种不同验证，二者都不授予认证。
