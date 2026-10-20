# 贷款月增与 OMO 净投放：最小真实原件测试样本

2026-09-09，只读研究。HEAD 读取值 `99c495a217b66d4bca9d6ceae4688ee69d4382bb`；源码、测试均为下表指定的工作树读取快照，不跟随主线后续修改。未运行应用或测试，未发网络请求，未授来源认证。Windows 标准库读取了既有 D 盘文件及已可访问的 WSL CAS 文件，没有启动 WSL 命令、复制或改写 CAS。

最小正例：贷款需要六月、七月两份公告，七月企业中长期月增 **−2300 亿元**；加入五月即能识别“坏最新期退回旧两期”的错误 **+5600 亿元**。OMO 需要 08-21、08-28 两份公告及合格的 08-28 日历父项，按既有 v2 公式期望 **−750 亿元**；再用 08-07、08-14 组成“真实零投放仍有到期回笼”的 **−10 亿元** 正例。

## 贷款：三份原公告，一组身份

均为 `family=pbc_loan_structure`、`provider=中国人民银行`、`metric_id=CN_LOAN_STRUCTURE`、`source_field=ytd_increment_100m`、`unit=hundred_million_cny`、`period_kind=year_to_month`；选取维度 `{"borrower":"enterprise","tenor":"long_term","measure":"ytd_increment"}`。三期起日均为 2026-01-01；不可把“累计增加”改成贷款余额或同月原报增量。

| 期次/截止日 | 官方 URL | 精确原件路径；SHA256 为链接完整文件名 | bytes | 原文字面与独立归一化 | 页头时间 |
|---|---|---|---:|---|---|
| 2026-05 / 05-31 | [五月金融统计](https://www.pbc.gov.cn/diaochatongjisi/116219/116225/2026061217051611931/index.html) | [8f71dd1e…](evidence-macro-derived/8f71dd1e651d2e5d8e7120555a000c54a517c41fb01d94b39948183badab9769#L366) | 44651 | L366“前五个月”企（事）业单位中长期贷款“增加4.99万亿元”→49900亿元 | L328：2026-06-12 17:00:01 |
| 2026-06 / 06-30 | [上半年金融统计](https://www.pbc.gov.cn/diaochatongjisi/116219/116225/2026071515025183948/index.html) | [9ebce7e2…](evidence-macro-derived/9ebce7e21c93d92980814be8f754dcc255ebe29dbbdf2531973e09361832c168#L366) | 44903 | L366“上半年”企（事）业单位中长期贷款“增加5.55万亿元”→55500亿元 | L328：2026-07-15 15:00:09 |
| 2026-07 / 07-31 | [七月金融统计](https://www.pbc.gov.cn/diaochatongjisi/116219/116225/2026081416320925645/index.html) | [933f3546…](evidence-13/933f3546fc3f8232014dc9e2cab854a331ff5da5a9509d3063ada2d3678dfcef#L366) | 44692 | L366“前七个月”企（事）业单位中长期贷款“增加5.32万亿元”→53200亿元 | L328：2026-08-14 16:30:05 |

本轮先从各原段独立读出 4.99、5.55、5.32，再与 [v2 准备 JSON](evidence-13-preparation-v2/preparation.json)的三个 family/原件/期次绑定对照：各公告准备 9 标量，以上三格分别为 49900、55500、53200，单位及累计区间相符。此前独立审计对应[五月 EL](p1-loan-structure-full-value-audit.md#L725)、[六月 EL](p1-loan-structure-full-value-audit.md#L749)、[七月 EL](p1-loan-structure-full-value-audit.md#L773)。没有复制应用解析输出生成期望，也不重审其余 24 格。

独立手算采用原文字面十进制：

- 六月月增：`(5.55 − 4.99) × 10000 = +5600` 亿元。
- 七月月增：`(5.32 − 5.55) × 10000 = −2300` 亿元。负数合法，表示两份累计披露的差分；不是原公告独立披露的七月单月数，也不额外宣称已完成跨版本可比性认证。
- 若存在五月、六月、七月声明而七月原件失效，结果应保留七月缺口；不能用五月→六月的 `+5600` 作为最新可用月增。若六月失效，既不能用五月跨月计算 `(5.32−4.99)×10000=3300`，也不能把七月累计 `53200` 当月增。

五月、六月的仓库副本由根代理复制，见[复制回执](evidence-macro-derived/archive-copy.json)；本轮复核其 hash/长度与先读取的 CAS 原件一致。复制不是新 HTTP 取得、历史首发、声明导入或认证。

## OMO：两组可区分零与缺失的原表

四份均为 `family=pbc_omo_notice`、`provider=中国人民银行`。`CN_OMO_7D_AMOUNT` 的原报字段为 `injection_100m`、维度 `{"measure":"injection"}`、亿元、business_day，起止日均为公告正文操作日。原件**没有直接披露下表的到期回笼与净投放**；它们是现有模型公式在指定日历下的派生值。

| 操作日 | 官方 URL | 精确已存原件；完整文件名即 SHA256 | bytes | 原表字面 | 页头 L327 |
|---|---|---|---:|---|---|
| 2026-08-21 | [第162号](https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/125431/125475/2026082108525095972/index.html) | [d5673e8e…](//wsl.localhost/Ubuntu-22.04/home/tywin/.local/share/pring-cycle/artifacts/sha256/d5/d5673e8e4351bc2a1ff1afdcdd89da9ba2c3c7a8fe946c3cd463c164da0cd834#L350) | 30798 | T16 R2：7天 L361；操作利率1.40% L362；中标量950亿元 L364 | 2026-08-21 09:20:30 |
| 2026-08-28 | [第168号](https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/125431/125475/2026082808585347002/index.html) | [ee19f9d0…](evidence-13/ee19f9d0ca925b95875448bda4f354558ee7c6f06c36d9a3a62eafb9d59e4a1a#L350) | 31000 | T16 R2：7天 L361；操作利率1.40% L362；中标量200亿元 L364 | 2026-08-28 09:20:30 |
| 2026-08-07 | [第152号](https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/125431/125475/2026080708590296440/index.html) | [5e1143e7…](//wsl.localhost/Ubuntu-22.04/home/tywin/.local/share/pring-cycle/artifacts/sha256/5e/5e1143e701f9d3b15568ea07503ee90753d1fdc31586bd727d095f4d0ccc161e#L350) | 30778 | T16 R2：7天 L361；操作利率1.40% L362；中标量10亿元 L364 | 2026-08-07 09:20:30 |
| 2026-08-14 | [第157号](https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/125431/125475/2026081409033914683/index.html) | [1366cecb…](//wsl.localhost/Ubuntu-22.04/home/tywin/.local/share/pring-cycle/artifacts/sha256/13/1366cecb1866585ca167908a27d375c74b6835cb53ff3ac5ab01979f3de68baa#L350) | 29828 | 正文“7天期逆回购操作量为零”；三列表 T16 R2：7天 L360、中标量0亿元 L362，**无利率列** | 2026-08-14 09:20:30 |

四页 L350 正文与表格同日金额一致。T16 是按全文 table 开始标签计数，包含页面布局表；金额取“中标量”，不能因投标量恰好相等就互换字段。已审身份/表头依据见[OMO 全值报告](p1-omo-full-value-audit.md#L15)，四行分别见[08-07](p1-omo-full-value-audit.md#L163)、[08-14](p1-omo-full-value-audit.md#L168)、[08-21/28](p1-omo-full-value-audit.md#L173)。08-28 后文的隔夜操作不得并入 7 天数值。

按已存在 `repo-net-injection-trading-calendar-v0002`，操作日加 **7 个自然日**，再取不早于该日的首个合格交易日，见[成熟日函数](../../src/pring_cycle/context_projection.py#L1040)。在分别提供 08-28、08-14 为有效日的隔离测试日历时：

- 08-21 的 950 于 08-28 到期；08-28 净投放 `200−950=−750` 亿元。父项是两条 injection 声明及 08-28 日历声明，不包含操作利率。坏到期父项不能被过滤后得到“到期0、净投放+200”。
- 08-07 的 10 于 08-14 到期；08-14 原报投放确为 0，净额 `0−10=−10` 亿元。不能因为零值而删掉 08-14 的原报父项，不能把缺失利率列补 0，也不能把缺少/坏掉 08-07 原件解释为真实到期 0。
- 两组分别在独立 runtime 运行；若混入其他操作或延伸日历，必须明确目标上界和到期集合，避免让最晚派生日漂移。此两份/两份是软件最小数据集，不证明真实世界完整到期台账或独立交易日历全覆盖。

四页相同的 09:20:30 是本轮逐份读取的可见页头字面值；不据此给其他日期设固定发布点。URL 内数字、meta createDate、复制时间均不替代首次公开时间。原页时间可以按既有解析规则用于隔离测试，不等于正式历史首发版本认证；旧准备包无 acquisition 的事实仍保持，测试须由真实公开导入函数生成新隔离回执。

## 新登记目录的公开构造与反例顺序

1. 复用 [`prepared_request` 与 submit/save](../../tests/models/test_candidate_admission.py#L56)创建**合成审查、隔离新目录**；其 accepted review 只证明软件接缝，不代表真实来源通过。取得该 model 的 manifest/catalog version，以公开 `ingest_official_context_document` 导入整页，用 family、官方 URL、expected_period 和隔离 `clock` 构造真实 raw+normalized acquisition。不要手工复制准备 JSON 成声明，也不要只 monkeypatch 资格函数。
2. 贷款沿[现成官方导入纵向用例](../../tests/models/test_candidate_admission.py#L2927)，连续导入 May/June/July，每页 9 个原报成员。使用已登记模型的 `loan-ytd-monthly-change-v0002`，公开 `build_context_projection(..., model_manifest=manifest, persist_derived=True)`；通过 credit evidence 找 enterprise/long_term/monthly_change，期望七月 `−2300`，`input_observation_version_ids` 精确为 June+July 这两个原报 claim，`derived_trace` 同样绑定两者。总 `model_input_observation_version_ids` 可能合法包含其他原报成员，不能整体强断为仅两个。
3. 贷款分别损坏 July、June acquisition 的 normalized，另加 raw 缺失/错误 hash 参数。先证明 pristine 输出，再从相同公开投影/检索入口观察缺口；断言坏 claim 不被采用，且没有 June 的 `+5600` 或 July 的 `+3300/+53200` 伪替代派生。保留诊断 observation IDs；不删除版本历史。[当前快照的贷款选取](../../src/pring_cycle/context_projection.py#L950)先筛 `_certified_point` 再取最后两期，因此这是具体静态风险，须由本轮公开 RED 确认。
4. OMO 复用[旧 v2 公开净投放及 derived_trace 用例](../../tests/integration/test_context_projection.py#L132)的断言结构，但将 2500/3000 合成金额改为上述真实950/200公告导入，并使用新目录。日历父项需由合格 `CN_EQUITY_CORE_000985` 输入形成；可复用[现成新目录 core-history 公开 seam](../../tests/models/test_candidate_admission.py#L5119)构造有 raw/normalized 的隔离 core 响应。该 core 测试的默认 PUBLIC 未知，**不能直接用作历史目标日有效日历**；若测试选择 PUBLIC/target-bound 模式，应明确提供合成 PUBLIC 资格的完整 core 声明及其原 acquisition 关联，或使用另有真实 PUBLIC 证据的日历。不得仅写一个 date 列表就声称通过当前源资格，更不能给生产 core 原件倒填时间。
5. 对 OMO 分别破坏旧操作、当前操作、日历父项，期望缺口而非 0；本报告重点旧操作950的 normalized/原件失效不能转成净投放+200。可沿[当前无效操作及到期集合](../../src/pring_cycle/context_projection.py#L698)把共享资格失败保留为 invalid 输入，让既有 invalid_maturity_dates 阻止计算，不能在分组前静默丢掉坏父项。08-14 真零正例保持 `−10`，与“公告不存在”和“公告存在但不合格”分开。
6. PUBLIC 回放后续修订反例：先用相同两/三份原件和确切页头时间建立公开正常值；对同一期新增修订字节而不增加原页发布时间，保持其 SYSTEM-only，旧 PUBLIC 截止点仍选旧版本。给出更晚真实或明确合成测试发布时间的修订才可改变该 cutoff 之后的选择。所有这些时钟都明确是隔离测试构造；不能把今天导入时钟当旧原件历史首次取得。原有 v1 同日净额和贷款一月重置语义保持，本切片不另冻规则。

## 输入快照及校验范围

原件 7 份共 **256650 bytes**：本轮逐份读取，7/7 SHA256 与完整文件名相符；五月/六月仓库副本也与 CAS 相符。最小贷款正例读取 2 份，回退反例增加 1 份；最小 OMO 正例读取 2 份，真零反例增加 2 份。原件内容已核与测试独立期望已给出，**本轮应用执行、测试执行、外部请求均为 0**。

源码与审计输入指纹固定如下；前两次工作树读取的不同测试快照是主线正在修改的结果，本报告采用 03:26:29 UTC 快照的函数定位，不拿此后文件内容覆盖旧指纹。当前实现是否已经修复，应由根代理自己的 RED/GREEN 记录确认。

| 输入 | bytes | SHA256 | 读取快照 UTC |
|---|---:|---|---|
| `src/pring_cycle/context_projection.py` | 84130 | `38943a1398869e5e29bd3ac139908cd27f913fb6405b8218001c02e2ef8660a2` | 2026-09-09 03:22:53 |
| `tests/integration/test_context_projection.py` | 59768 | `82e2c192745e43088a120bc831c67090b9f920cd4ad361e60ce8b4027e2e2a19` | 2026-09-09 03:22:53 |
| `tests/models/test_candidate_admission.py`（早期部分读取，未用于最终函数行号） | 233081 | `957f6cb681b0526c309363e083f504aa640be3b87b338b0b2a6a7ffcb90f471a` | 2026-09-09 03:22:53 |
| `tests/models/test_candidate_admission.py`（本文函数定位快照） | 237130 | `8ca7c2b5d518213988f7ec59ea41cc42b7913716fb5dc0d9c8184a61d1f84a02` | 2026-09-09 03:26:29 |
| `p1-loan-structure-full-value-audit.md` | 66620 | `2d4d1b4a3e1966cbfeccb0f6892ed31937f941edc7a75d09609424a2e767dcae` | 2026-09-09 03:22:53 |
| `p1-omo-full-value-audit.md` | 81481 | `d1af0e4bd294fedede1aaa32be505c88a013965c36be2d4d297f5f8b616c617e` | 2026-09-09 03:22:53 |
| `evidence-13-preparation-v2/preparation.json` | 3189072 | `92f44dbb435ea56fd1b08813373f4abf4749d76db33f364547098e290fb58034` | 2026-09-09 本轮只读 |
| `evidence-macro-derived/archive-copy.json` | 1256 | `2c7c5a81294e38d7a60d39c411f5e778f83256a04eb9355070f222bc2c307f53` | 2026-09-09 03:26:29 |

唯一交付为本 Markdown；不新增采集、认证或模型制品。最终 bytes/SHA 与链接校验结果在交付消息给出，文件内不存自身 hash。
