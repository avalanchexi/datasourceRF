# 万亿元转亿元：货币余额的数值边界与入口

研究日期：2026-09-08（Asia/Shanghai）。范围限定为已有 2026-02 官方货币原件、旧准备快照、`official_context.py` / `tushare_context.py` 及调用它们的现有入口。只读源码、规格和原件；仅运行 Windows Python 标准库的字节、AST 和 Decimal 算术检查，没有运行应用、测试、网络、数据库或认证操作。

结论：**原始十进制字面应先完成单位换算，再进入现有浮点标量边界。** 对真实 `349.22 万亿元`，结果应为 `3492200 亿元`。当前读取的官方货币路径先转 float 再乘一万；旧快照确实保存为 `3492200.0000000005`。不能通过“把乘完的 float 再放入 Decimal”恢复原文字面精度。这个发现支持局部金额归一化修复，没有依据要求全系统改用 Decimal。

**两个货币入口的源单位不同。** 官方正文 M1/M2 余额是万亿元，需要换算；TuShare `cn_m` 的当前代码契约是亿元直接接收，倍率为1。不能给所有 M1/M2 再乘一万。下文把当前行为、建议契约和待执行反例分开；未把研究结果当作来源认证或模型采用。

## 真实输入与现有单位契约

[2026年2月金融统计数据报告的官方出处](https://www.pbc.gov.cn/diaochatongjisi/116219/116225/2026031317020260950/index.html)，本次只读取[已保存精确原件](//wsl.localhost/Ubuntu-22.04/home/tywin/.local/share/pring-cycle/artifacts/sha256/37/377f455aa92273c23d57540d2b33e5b4b99f01e6ebfa7beacae157c21c5632cc)，没有重新请求。HTML L359 明示2月末：

| 原文字段 | 字面值及单位 | 独立归一化期望 | 旧准备值 |
| --- | --- | ---: | ---: |
| M1余额 | 115.93 万亿元 | 1159300 亿元 | 1159300 |
| M1同比增长 | 5.9 % | 5.9 % | 5.9 |
| M2余额 | 349.22 万亿元 | 3492200 亿元 | 3492200.0000000005 |
| M2同比增长 | 9 % | 9 % | 9 |

`1 万亿元 = 10000 亿元`；不用同比推算余额，不把百分比除以100。原件另有M0和净投放现金，不能替代M1/M2或扩大本次准备范围。[既有逐值审计](p1-money-full-value-audit.md)已固定7期28格的27精确相符、1表示微差分类；本报告未修改其分母或结果。

| 公开解析入口 | 身份及字段 | 输入单位与行为 | 输出契约 |
| --- | --- | --- | --- |
| `parse_official_context_document(family="pbc_money")` | `CN_M1_M2`；`m1,m2`；aggregate=m1/m2、measure=balance | 正文正则要求“万亿元”；`_bounded_number`先转float，`balance * 10_000` | `hundred_million_cny`；month、月初至月末 |
| 同一官方入口 | `m1_yoy,m2_yoy`；measure=yoy | 原文增长/下降百分数，下降取负；无金额倍率 | `percent`，两条余额加两条同比共4格 |
| `TushareContextAdapter.money` | `CN_M1_M2`；`m1,m2` | `cn_m` 当前字段约定为亿元，默认倍率1 | `hundred_million_cny` |
| 同一TuShare入口 | `m1_yoy,m1_mom,m2_yoy,m2_mom` | 百分数，默认倍率1；None不生成标量 | `percent`；字段全有值时共6格，不能冒充官方4格的同一范围 |
| `TushareContextAdapter.social_financing` | `CN_SF_TOTAL / stk_endval / measure=stock_end` | `sf_month` 存量倍率为10000；增量字段倍率为1 | `hundred_million_cny` |

证据定位：[官方解析器](../../src/pring_cycle/official_context.py) L179–225、L527–562、L1761–1806；[TuShare适配器](../../src/pring_cycle/tushare_context.py) L334–384、L1581–1606。这里的TuShare单位描述是**读取到的代码契约**，不是本次重新取得的渠道单位认证。

M1定义仍须与原件注5绑定：2025年1月起修订口径，包含M0、单位活期存款、个人活期存款、非银行支付机构客户备付金；2024可比回溯另属版本。数值换算修复不补齐旧快照 `definition_version=null`，也不让后期回溯获得早期PUBLIC。

## 两个模块中的全部万亿缩放点

对本次读取的两个文件作文本查找及标准库 AST 检查：官方模块有 **5个显式乘10000位置**；TuShare模块有 **1个字段倍率配置**，经公共月度装配器应用。这个计数是两文件内的代码位置，不是指标数、标量数或全系统所有单位转换数。

| 位置（本次指纹的行号） | 可到达的家族及影响字段 | 当前处理 | 修复审查边界 |
| --- | --- | --- | --- |
| 官方 L1074，`_parse_industrial_finance_live` | `nbs_industrial_finance / CN_FINISHED_GOODS_INVENTORY / finished_goods_inventory_100m / nominal_end_level` | 正文存货万亿元→float→×10000，无显式舍入 | 只有库存余额走这个倍率；收入/成本/利润使用表内亿元，不能一并重乘 |
| 官方 L1524，`_parse_social_financing`表格分支 | `pbc_social_financing`；`CN_SF_TOTAL`总量及`CN_SF_COMPONENTS`分项；`stock_end_trillion / stock_end` | 表头“期末存量（万亿元）”→float→×10000 | 映射是总量加10分项，共11行；`source_field`仍名trillion，但输出单位已经是亿元 |
| 官方 L1803，`_parse_money` | `pbc_money / CN_M1_M2 / m1,m2 / balance` | 捕获字面→`_bounded_number`→float→×10000 | 本轮真实反例；同比不乘倍率，M0不在该输出中 |
| 官方 L2086，`_stock_level_and_yoy` | `pbc_social_financing`正文分支：总存量及8个正文分项的`stock_end_trillion` | float×10000后`round(...,6)` | 与表格分支不同；六位是代码现状，不是原件证明的统一披露精度 |
| 官方 L2099，`_signed_amount_after_label` | 社融正文总量/8分项`ytd_increment_100m`，以及贷款正文`CN_LOAN_STRUCTURE / ytd_increment_100m`的9种borrower/tenor组合 | 字面带万亿元才float×10000并round6；带亿元不缩放；减少取负 | 不能把亿元增量、负方向或累计期次改成余额；同一helper被两个家族复用 |
| TuShare L376→L1602 | `sf_month / CN_SF_TOTAL / stk_endval / stock_end` | `_number`先转float，再乘字段倍率`10000.0` | `inc_month`和`inc_cumval`保持亿元；`cn_m`不配置该倍率 |

官方映射位置L36–83、社融分支L1490–1666、贷款正文L1707–1758、数字函数L2049–2100。工业表格版原有亿元数据、贷款表格版“月末存量（亿元）”、`_pbc_amount`“亿元”以及M1/M2同比均不是万亿缩放点。不能把上述相邻入口的风险描述成已经用真实数据逐项复现；本研究只有货币真实尾差这一数值事实。

## 实际调用入口，不另造第二套解析路径

官方路径都汇入 `parse_official_context_document`，先校验官方URL、带时区取得时间、大小和年份/统计期，再分派家族。`pbc_money`只允许既有PBC宿主，见[家族登记](../../src/pring_cycle/source_families.py) L65–66。修复私有换算函数后仍需从公开入口验证，不能仅调用 `_parse_money`绕过这些边界。

| 调用层 | 已读到的实际入口 |
| --- | --- |
| 离线公开契约 | [CLI](../../src/pring_cycle/cli.py) L147–161 的 `official-context-contract` 读入原件并调用公开parse；官方模块L477–510的smoke也调用它，但正常smoke具有GET行为，本研究未运行 |
| 已有原件导入 | 官方模块L238–275的`ingest_official_context_document`捕获原件并解析，再进入`ingest_acquired_official_release`；[历史来源流程](../../src/pring_cycle/source_history.py) L168与L253分别调用公开parse和该导入入口 |
| 官方刷新 | 官方模块L403–457的`refresh_official_context_document`获取/校验HTTP后调用公开parse；[Worker](../../src/pring_cycle/worker.py) L817–825调用该刷新入口 |
| 搜索候选与认证准备 | [搜索证据流程](../../src/pring_cycle/search_evidence.py) L224–232与[来源准备流程](../../src/pring_cycle/source_certification.py) L327–334调用相同刷新入口；搜索有1600字符限制，金额修复不能绕过它 |
| TuShare公开取数 | `money` / `social_financing`→`_call`→`_monthly_scalars`；模块L1481/L1486的smoke、Worker L1403–1414的家族采集、[定向上下文流程](../../src/pring_cycle/targeted_context.py) L42–52均复用这两个方法 |
| TuShare取得并入库 | `acquire_scalars` L151–212包装取数并保留回执/标准化结果，后交给`ingest_context_scalars`；该层接收已有`ContextScalar.value`，不再次做万亿元换算 |

公开官方导入最终把 `scalar.value`交给来源声明（L345–371），原件、标准化制品分别保留。它不是在入库时凭单位标签猜一次倍率；否则修复可能引入重复缩放。共享的 `ingest_acquired_official_release`还有LPR调用者，但LPR不属于本次金额转换入口。

当前数值类型边界是 `ContextScalar.value: float`（TuShare L76–90），官方 `_official_scalar`直接传递value。TuShare `_canonical_json`为`json.dumps(..., default=str)`（L1819–1820）。因此，局部Decimal算术后在既有边界转回float与把全链路对象改成Decimal，是两种不同范围的改动；后者还会影响标准化JSON类型，不能顺带完成。

## 字符串Decimal与float再转Decimal

下表是本次 Windows Python 标准库独立算术的实际输出；Decimal计算使用精度60，不导入任何应用。`x="349.22"`，`v=float(x)`，`post=v*10000`。

| 运算 | 结果 | 能证明什么 |
| --- | --- | --- |
| `Decimal(x) * 10000` | `3492200.00` | 从原文字面完成十进制换算 |
| `Decimal(v) * 10000` | `3492200.000000000272848410531878471374511718750000` | 精确保留已有二进制float的值，不是恢复源字面 |
| `Decimal(str(v)) * 10000` | `3492200.00` | 此样本的float最短表示恰为349.22；一般不能保证找回原始JSON/源数字的全部位数 |
| `Decimal(post)` | `3492200.0000000004656612873077392578125` | 乘法尾差已经产生，直接Decimal只把它展开 |
| `Decimal(str(post))` | `3492200.0000000005` | 已产生的尾差仍在；与旧准备快照文本对应 |
| `round(post,6)` | `3492200.0` | 对本样本可消掉尾差，不证明六位适合所有源数据 |
| `float(Decimal(x)*10000)` | `3492200.0` | 本样本的整数亿元可在既有float输出边界精确表示 |

区别不仅是选择哪种Decimal构造器，还包括**何时保留原始字面**：

- 官方HTML金额捕获值本来就是字符串。可在金额缩放这一窄边界保留字面、做十进制缩放，再返回既有标量类型；无需让百分比、日历、库存状态等改用Decimal。
- TuShare `_call` L1108–1117对原始bytes采用普通`json.loads`，数值小数在进入`_number`前已是float；注入的dict transport也可能直接给float。`_number` L1799–1810还会将字符串转float。因此在 `value * field.multiplier` 之后补Decimal太晚。若局部选择`Decimal(str(value))`，应明确它按现存数值的十进制表示进行缩放，不等于保全原始JSON字面。
- 如果必须保留JSON小数原始精度，应从响应解析边界设计局部保留方案；不能直接全局加入`json.loads(parse_float=Decimal)`。当前`_number`只接受int/float/str、拒绝bool和其他类型，会拒绝Decimal；`default=str`又可能把Decimal序列化成字符串。两处都是明确可见的兼容边界。
- 原始披露精度、规范单位下精度和来源冲突允许误差是不同概念。不能把原文两位万亿元解释为新增多位亿元精度；也不能用扩大冲突容差掩盖本次已识别的转换尾差。

建议的最小契约为：**对声明为万亿元的金额字面做十进制×10000，仅在原本要求float的标量边界转换；已为亿元的输入倍率为1，百分比和符号按原有定义处理。** 这是实现建议，不是已冻结的新模型或来源容差规则。若源码允许远多于现有样本的有效位数，需明确输出float可表达范围与非有限数拒收，不宣称任意长度十进制都能无损转float。现有`_bounded_number`没有统一的isfinite检查，TuShare`_number`有；不得在换算时顺带放宽其拒收边界。

## 可由公开入口验证的最小反例

下列是给实现流程的输入与独立预期，**本研究没有运行这些应用入口**。当前应用的RED/GREEN记录由主代理另行保留，不能把下面的标准库算术冒充公开入口测试通过。[修复规格](spec.md) L91–98、L132–137要求真实反例、公开行为验证、原件与标准化结果分离，也明确不做无必要的全局预重构。

| 编号/优先级 | 公开入口与输入 | 应断言的独立结果 | 目的及事实性质 |
| --- | --- | --- | --- |
| R1 必需 | `parse_official_context_document`；上述44,639B真实原件、family=pbc_money、原官方URL、expected_period=2026-02、带时区且不早于页头的fetched_at | 4格身份完整；M2余额严格`3492200.0`亿元、M1`1159300.0`、两同比5.9/9；同比及期次不变 | 真原件；避免`pytest.approx`或显示格式四舍五入把尾差隐藏。应在应用运行时确认，不能只运行私有数字helper |
| R2 若处理共享金额逻辑 | 同一公开parse的内存合成HTML，将M1余额也设为349.22万亿元，其余日期和层次保留 | M1和M2均为3492200.0，字段各自绑定正确 | 明示合成反例，不能登记为官方M1事实；排除仅为m2特判 |
| R3 TuShare缩放入口 | `TushareContextAdapter(..., transport=离线桩).social_financing`；sf_month字段含month、inc_month、inc_cumval、stk_endval，后者给JSON数字349.22；再给JSON字符串"349.22"及dict内float349.22 | stk_endval严格3492200.0；已有亿元增量保持原值 | 三种输入类型属于公开transport契约的离线候选；349.22在此是合成社融数据，不能借用PBC货币事实授社融认证 |
| C1 必需防回归 | `adapter.money`；cn_m的m2给3492200、m1给1159300、同比9/5.9，m1_mom/m2_mom字段存在且值None | 两余额保持亿元原值；两同比不变；两个None不生成标量 | 防止对cn_m重复乘一万；必需字段名齐全，不用省字段制造另一种schema失败 |
| C2 按影响扩展 | 如果将共用缩放用于社融表格或工业库存，用现有完整公开HTML夹具，仅将该万亿元字段设为349.22 | 对应stock_end或库存余额为3492200.0，旁边原为亿元/百分比/天数的字段不变 | 覆盖上表另外两处无round缩放；属合成反例，不要求本轮重新审计全部家族 |
| C3 保留既有边界 | 若改动正文社融/贷款helper，通过对应family完整公开HTML给“增加/减少1.19万亿元”和“增加/减少11900亿元”，并保留其必需完整成员与累计期标识 | 归一化为相同的±11900亿元；累计增量身份不变；余额不得允许负值 | 现有round6路径不是空白实现；应防丢符号、亿元重复缩放、累计量误当月量。不可只调私有helper证明公开解析通过 |

当前已读[TuShare测试](../../tests/adapters/test_tushare_context.py) L147–175使用`365.77`万亿元→`3657700.0`；该样本不触发349.22的尾差。其money测试L96–138验证成员/单位，但没有这个真实金额反例。[官方测试文件](../../tests/adapters/test_official_context.py)含社融两种版式与工业财务完整夹具，可作C2/C3公开入口输入基础。读取这些旧测试不等于本次运行它们，也不等于尚在并行开发的新测试不存在。

本轮金额问题不授予M1定义版本、历史首次公开、取得时间或修订链资格；仍须保留原件和新标准化版本，不就地改写旧准备包。根据[ADR0013](../../docs/adr/0013-tushare-delivery-with-official-sampling.md)，官方语义抽样与渠道认证是独立工作，也不要求借本次尾差修复扩展为每条历史数据双源。

## 输入指纹与交付

以下为 **2026-09-07T17:56:02.161409+00:00** 的实际读取指纹。主代理正并行维护应用，后续源码可变化；本报告行号绑定这些字节，不回写报告以追随新实现。官方文件已包含当时的产能列宽改动，货币函数L1761–1806仍为float后乘。为避免无关函数变动影响定位，另记录`_parse_money`函数正文按LF连接、无末尾换行的UTF-8片段：**1566B，SHA-256 `13268fa9b3747daf4932e220b1b43feda2dd881e6e686f8584276d99075a49f8`**；这不是磁盘原件摘要。

| 读取输入（相对项目根，原件除外） | 字节数 | SHA-256 |
| --- | ---: | --- |
| src/pring_cycle/official_context.py | 80058 | 370ac84bf4a93e1dec155a5b8a3f3fb77bd77c15e999f60fe8f18aefdce2adba |
| src/pring_cycle/tushare_context.py | 68390 | e48f670b8f25b596cb4612cfb6e1f587727d59cf98747e9ceacc80c6fa6cb2bd |
| src/pring_cycle/cli.py | 37479 | bcedbfaf97d2710f22c231919e22f57e443787823e7a17c7a153d11f5a1573c3 |
| src/pring_cycle/worker.py | 57660 | 3dbb9e0bf0ebf4323c3d8d8b0ffb9ad53acfc9ea8045d71e5f9fb86b5825ea5e |
| src/pring_cycle/targeted_context.py | 5936 | 065a5342fc01694cd832c237122f706914a95a9a5a41febaea054a16fbdee25a |
| src/pring_cycle/search_evidence.py | 12778 | 06983dc3e978484487678e2225cc51128fae5562b4734588409f6ee4c8c5e75e |
| src/pring_cycle/source_history.py | 26596 | 393420b63609d8dc12e63da21c3373fdd430c2d07304d4dfd34787d559577f2e |
| src/pring_cycle/source_certification.py | 15659 | e585ce624de989ec6f9def5ff4f44130ebad22c449d6c8a1a2f0c9d64e44a963 |
| src/pring_cycle/source_families.py | 2487 | 420a241b90fc0ff63cafe5e9119f15a375e90617834cae2698e403ccbcaa5f6e |
| tests/adapters/test_tushare_context.py | 32439 | f4715a16ae1b3a93f7ecec6b18dd26d7635d03a0ff00ee54598490c987a75ae4 |
| tests/adapters/test_official_context.py | 39818 | 5eac49a556f07f0e3dbf7903a52b484a1f271ba16c48054f6e0b6e6f77e434d2 |
| CONTEXT.md | 20103 | f0cdf13436e1dd178b86ac6181de916757c3ef59edb7024ec6e980f151e5a102 |
| docs/adr/0013-tushare-delivery-with-official-sampling.md | 1089 | 8580553c46299947b55e1dfef8718e43c121019a60e54b4f9b91f466ef4cac4b |
| .scratch/pring-data-acquisition-repair/spec.md | 27762 | f5c32c407f216841b2afed0aaab3863868bdc394d9057207d25dbc9e9a561cc4 |
| .scratch/pring-data-acquisition-repair/p1-money-full-value-audit.md | 16643 | 44ea8fbc4d0c649343068b987921ea47463f5b8e5067fd39aec09f314cec5eda |
| .scratch/pring-data-acquisition-repair/evidence-13-preparation/preparation.json | 2767926 | a9fe475c47303fb7791b27df04849dcef0aacabde27b64f57023972c9a4ec20a |
| 上述UNC中的2026-02官方原件 | 44639 | 377f455aa92273c23d57540d2b33e5b4b99f01e6ebfa7beacae157c21c5632cc |

仅新增 `.scratch/pring-data-acquisition-repair/money-normalization-boundary.md`，未创建脚本/副本、未改旧证据或任何应用文件。最终字节数、SHA及本地链接复核结果在交付消息给出。项目根目录可只读取得：

```powershell
Get-Item -LiteralPath '.scratch/pring-data-acquisition-repair/money-normalization-boundary.md' | Select-Object Length
Get-FileHash -LiteralPath '.scratch/pring-data-acquisition-repair/money-normalization-boundary.md' -Algorithm SHA256
```

