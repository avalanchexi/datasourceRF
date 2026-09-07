# LPR 直连中国货币网：已有用途依据复核

研究日：2026-09-08，Asia/Shanghai。范围仅为 `CHINAMONEY_LPR / CN_LPR_1Y_5Y` 的**个人本机、非商业、保存原件与标量、计算并生成仅本人阅读的报告、不对外分发**。这是本轮待对应的用途，不是本研究新授予的许可。读取时 Git HEAD 为 `656eaa03c41efc31d7ee37de56865f52db4e0af0`；没有审查或执行当前应用。

**结论：已找到公众查询的明确依据，也找到了必须正面处理的网站抓取、复制及存储条款；没有在本轮限定仓库材料和官方检索中找到足以明确覆盖上述全部用途的 LPR 专属例外或许可记录。** 因而不能把用途 finding 写成已接受，也不能断言用户没有权利或必须购买服务。剩余最小缺件是一个**针对 CFETS 直连 LPR 公告实际用途的适用依据及审查结论**，不是再次征求个人非商业意愿，不是要求补齐另一套数值样本。

## 1. 已有材料实际证明了什么

| 材料与定位 | 可核实证据 / 短引文 | 本用途可用的结论 | 不能推断的部分 |
| --- | --- | --- | --- |
| [已接受 ADR0013，第7、9行](../../docs/adr/0013-tushare-delivery-with-official-sampling.md#L7) | 明确 TuShare 可作结构化交付渠道，并已有本地个人、非商业、不可转让、未经许可不再分发的使用边界。 | 同一既有用途不需要再问一遍；官方抽样与使用许可审查已经是既有要求。 | 其提供方和适用对象是 TuShare，不能由此生成 CFETS 直连的书面许可或认定两渠道权利相同。 |
| [旧 LPR 来源说明，第15–17行](../../docs/research/lpr-official-source.md#L15)，对应 [官方 LPR 基准页](https://www.chinamoney.com.cn/chinese/bklpr/) | 文档记录公众可以在全国银行间同业拆借中心及人民银行网站查询；此前基准页读取的 URL、时钟、响应摘要及 hash 见 [旧缺口矩阵的网络回执](lpr-certification-gap-matrix.md#L57)。 | LPR 是公开发布、供公众查询的指标；不应仅见版权署名就说连阅读或公开查询都需要额外采购。 | 该段没有明确授予电子采集、原件长期存储、自动计算、报告生成的全部权利；旧来源说明的标题也不是独立许可凭证。旧回执中的基准页响应未另存原始字节，不能把其摘要 hash 冒充已登记原件。 |
| [2026-08-20 公告原件，第60、77行](evidence-13/5b4ddec501ddfe52bfec15d471c8c6d4548b643da9a61f35f9a978825bc04bd5#L77)，[官方公告](https://www.chinamoney.com.cn/chinese/rdgz/20260820/3399885.html) | 正文明确人民银行授权全国银行间同业拆借中心公布当期两期限数值及有效期；页面提供打印功能（第69行）。 | 证明公布主体及公开公告身份。 | 这里的授权对象是公布机构，不是将其授权转授给所有使用者；打印按钮本身没有说明批量电子采集或用途许可范围。原件正文未给出个人非商业存储/分析许可条款。 |
| [CFETS 数据服务说明原件，第656–658行](evidence-13/1732c0c0fe89a07456d80ffdaef80aa483fba7b3af7de903a6e2767a288ccf50#L656)，[官方说明](https://www.chinamoney.com.cn/chinese/dssjfwgl/) | 数据定义包括基准、公告、通知及主管机构授权或要求披露的信息；第657行列复制、存储、使用、加工等行为的“书面许可”条件。第658行同时列最终用户从“公共信息发布渠道”或正式授权信息商等正规途径取得和使用数据。 | 两段必须一起审查：有明确的行为限制，也有公共渠道这一正规取得路径。公开 GET 不能独自解决用途；正规公共路径也不能被省略。 | 正文未明确说明，最终用户从公共渠道取得 LPR 是否及如何满足前一段条件，或哪种个人用途例外适用。研究不能自行认定“任何个人绝无权利”，也不能把后段视为对所有存储/开发的无条件许可。 |
| [原研究13的用途边界，第185行起](research-13.md#L185)；[旧在岸收盘价研究，第212行起](../../docs/research/official-gap-source-audit.md#L212) | 前者已区分公开 GET 和使用范围；后者的自动持久化限制针对在岸市场收盘序列。 | 有既有来源审查边界可复用；不需要再制造一个笼统“CFETS 全部不可用”结论。 | 在岸收盘价的具体执行结论不是 LPR 独立用途审查，不能直接复制成 LPR 的禁止或许可。 |
| [本次 document_import 回执](evidence-lpr-import-20260908/receipts.json#L1) | 静态 JSON 有9份 `validated` 收据和18个 `parsed_unreviewed_release` 值，记录 `source_claims_created=0`、`source_certification_grants=0`、`production_writes=0`。本研究只读 JSON 核对数量及状态。 | 旧原件本次导入/解析的准备步骤已有可读收据，不再将“缺本次导入收据”列为待办。 | 取得或解析成功不授予使用权；导入收据也不是历史首次公开证明或已形成来源认证。数值逐格和7状态审查由主代理另行完成，本研究不重复授信。 |

本轮检索范围为仓库 `docs/adr/`、`docs/research/` 与修复项目已有 Markdown 来源/授权说明；没有读取账户、凭据或合同私密目录。在此**限定可读范围内未检出**专门覆盖 CFETS 直连 LPR 的用户许可记录；这不表示用户在别处没有相关许可。

## 2. 两份新增官方资料及适用边界

### A. 中国货币网《法律声明》：有针对获取方式的明确文字

[官方法律声明](https://www.chinamoney.com.cn/chinese/legaldeclaration/)第一节除列出复制等行为外，还明确提到“电子抓取系统获取”；同节保留“法律另有规定”和“另有约定”的例外。它的陈述对象包括网站内容和基准指标，不能仅因本项目不对外分发就忽略获取、复制环节。该判断是条款文本与本用途的对应，不是认定所有数值均受同一种权利保护，也不是判断例外是否依法适用。

页面末署2010-09-17；本轮工具读取到的是当前返回的声明文本，没有取得各历史时点的条款版本。这一日期不能证明2025-12至2026-08期间一直无修改，也不为旧采集追授或撤销权利。对当前直连用途审查，应将其和上表公共渠道段落一起解释。

这份资料新增的具体信息是：限制并不只针对商业出售或向外传播，还点到了采集方式。因此“个人、不分发，所以自动满足全部条款”没有得到本轮原文支持。反过来，文本保留的例外和可能已有的双方约定，也不允许本研究断言用户一定无权。

### B. 《CFETS 基准指标基本原则》：非商业条款不能跨对象使用

搜索命中一份题为《CFETS 基准指标基本原则》的[官方 PDF](https://www.chinamoney.com.cn/dqs/cm-s-notice-query/fileDownLoad.do?contentId=3140426&mode=open&priority=0)，封面为2025年12月，20页。第20页有“基于非商业目的”和“使用本方法”的文字，第18页讨论指标研究用途。但第4页的适用范围只列回购定盘利率、外汇掉期曲线、利率互换曲线、债券收益率曲线、估值和债券指数，没有 LPR。

所以它至少证明：CFETS 并非所有文件都完全不谈非商业使用，必须读具体对象；但这份文件的“本方法”以及列明的指标范围，不足以成为 LPR 公告原件、LPR 历史序列的许可依据。不能只摘搜索命中的非商业短句放进 LPR 认证包。这是范围比对的研究结论，不是替 LPR 判定任何法律例外。

以上两份新资料没有既存本地原件路径；本轮使用网页工具读取正文/提取的 PDF 文本，未另存 HTML/PDF 原始字节。链接和章节可在线复核，不能把工具抽取文本称为 HTTP 原始字节或已有 CAS artifact。若正式审查采用这两份资料，需在其原件登记步骤准确保存所采用版本；这只是被引用证据的保存要求，不是要求新增大量许可研究。

## 3. 按实际用途收口

| 本轮用途项 | 现有支持与限制 | 用途 finding 的准确状态 |
| --- | --- | --- |
| 从公布机构的公开公告页面查询 LPR | 既有官方发布规则明确公众可查询；公告身份可核验；没有账户读取要求。 | **公众查询路径已证。** 不等同整条自动化用途已接受。 |
| 保存已取得 HTML 原件及18个规范标量 | 原件和本次收据已存在；数据服务说明明确涉及存储，网站声明涉及复制及电子获取。 | **实际材料已取得；适用使用依据待对应。** 不因使用审查未完就把已取得事实改成“获取失败”。 |
| 仅本人本机计算变化并生成非商业报告 | 与已确定个人使用范围一致；公共渠道段落是正面依据；尚无专门适用 LPR 的完整解释。 | **用途边界已明确，许可适用性未确认。** 不用其他基准方法的非商业许可替代。 |
| 不对外发布、出售、再分发 | 本任务已限定不发生这些行为；无需申请本任务用不到的分发产品权限。 | **范围外。** 不把商业再分发许可或付费采购设为本任务默认门槛；也不以不分发抹掉存储/获取条款。 |

**最小下一步只有一项：**受信来源审查应明确采用哪一条依据来覆盖 **CFETS 直连 LPR 公告的个人本机非商业保存、计算和仅本人报告**，并解释它与数据服务说明及网站声明的关系。足够材料可以是：已存在的相关许可/双方约定的可引用范围摘要；提供方对这组用途的公开具体说明；或针对明确例外形成的、可核查依据支持的适用审查。三者是可能的解决路径，不是要求同时收集三份，也不由本研究作法律结论。

若可读既有记录中已具备其中一种，直接复用并记录来源、适用对象、行为和范围，不再次向用户索要相同批准。不把用户再说一次“同意”当作 CFETS 授权，不自行申请许可、采购或联系他人。当前本报告能提交的是**已有支持、明确限制及尚未证明的对应关系**；无法替主审写成 `accepted`。

在这一用途 finding 收口前，主代理仍可完成9原件、18值、当前导入时间及真实点时状态的独立审查准备；本项没有增加数值样本、历史双源或一律重新下载要求。来源认证是独立步骤，机器完整性检查不能代替实际用途审查，见[候选准入信任边界，第7–9行](candidate-admission-contract.md#L7)。也不能仅为绕过用途问题静默改用 PBC/TuShare URL 并继承现有 `CHINAMONEY_LPR` 身份。

## 4. 本轮网络动作与证据保存边界

共 **4个逻辑搜索查询、3个 open 操作、2个唯一新官方 URL**；网页工具均返回可读正文或 PDF 提取文本，没有工具报告的访问失败。第三个 open 是同一 PDF 的后半段定位读取，不是第三份来源。实际底层 HTTP 请求数、状态码、重定向链、响应原始字节长度及 SHA256 均未由该工具提供，保持未知，不将3个 open 写成3次 HTTP 200。没有重试旧失败 URL、调用账户接口或猜测后台路径。

查询依次为：

1. `site:chinamoney.com.cn LPR 个人 非商业 使用 版权`
2. `site:chinamoney.com.cn 免责声明 版权所有 个人 使用`
3. `site:chinamoney.com.cn "LPR" "非商业"`
4. `site:chinamoney.com.cn "贷款市场报价利率" "许可" "使用"`

前两项发现本报告两份新增材料及既有数据服务说明；后两项未带来可用于本用途的专属条款，出现的交易产品介绍不作为个人公告用途许可。没有把搜索摘要作为完整条款。未使用剩余两页额度凑数。

| 新材料 | 实际读取定位 | 返回内容与时间边界 | 本地保存范围 |
| --- | --- | --- | --- |
| [法律声明](https://www.chinamoney.com.cn/chinese/legaldeclaration/) | 网页工具提取行6–11、39–47；版权节、语言优先级、署期 | text/html，48行提取文本；精确 HTTP 时间未知。 | 本 MD 的短引文、摘要及 URL；未保存原始 HTML。 |
| [基准指标基本原则](https://www.chinamoney.com.cn/dqs/cm-s-notice-query/fileDownLoad.do?contentId=3140426&mode=open&priority=0) | 第4页范围、第18页用途、第20页免责；两次 open 定位 | application/pdf，20页、434行提取文本；封面2025年12月不是已证首次公开时刻。 | 本 MD 的短引文、摘要及 URL；未保存原始 PDF。 |

两轮新资料读取完成后的首次时钟记录为 **2026-09-07 21:26:20 UTC（2026-09-08 05:26:20 +08:00）**。这是研究工具观察完成的记录点，不冒充请求开始、HTTP 接收完成、源首次发布或过去用户许可时刻。

## 5. 输入指纹、交付与默认只读复核

下表是本轮实际引用的9个本地输入；两个原件的 SHA256 与其文件名相符。本研究只核验静态文件及 JSON，不连接回执中记载的数据库，不运行应用。

| 本地输入 | bytes | SHA256 |
| --- | ---: | --- |
| [ADR0013](../../docs/adr/0013-tushare-delivery-with-official-sampling.md) | 1089 | `8580553c46299947b55e1dfef8718e43c121019a60e54b4f9b91f466ef4cac4b` |
| [旧 LPR 来源说明](../../docs/research/lpr-official-source.md) | 1695 | `13ad855518f1abd38dd3dc8c26e4da8e412b9945cf272817c38de65a9fedd0dd` |
| [旧官方缺口研究](../../docs/research/official-gap-source-audit.md) | 26565 | `17e7f9c5bf94bbaf14c33a481064b868a7b51be22b90eef556fcb3d7bfe95a24` |
| [研究13](research-13.md) | 31765 | `dcbdf9a07095e5bfb2110ff2f3a51e9049dc1bece87b3859207df1ece0f973e1` |
| [LPR 旧缺口矩阵](lpr-certification-gap-matrix.md) | 21941 | `b132c53abeb9a6653de37b84cd6001877a58a2cdfa7d893c5d7ee43341bd8c21` |
| [候选准入契约](candidate-admission-contract.md) | 4937 | `649b65963e52f1f1dc2a217dd513427ba0f1d7084c062f1266df56c15ff551fc` |
| [CFETS 数据服务说明原件](evidence-13/1732c0c0fe89a07456d80ffdaef80aa483fba7b3af7de903a6e2767a288ccf50) | 89404 | `1732c0c0fe89a07456d80ffdaef80aa483fba7b3af7de903a6e2767a288ccf50` |
| [8月 LPR 公告原件](evidence-13/5b4ddec501ddfe52bfec15d471c8c6d4548b643da9a61f35f9a978825bc04bd5) | 11000 | `5b4ddec501ddfe52bfec15d471c8c6d4548b643da9a61f35f9a978825bc04bd5` |
| [本次 LPR 导入收据](evidence-lpr-import-20260908/receipts.json) | 15463 | `31e1572983801245e76e1b4c33f57616029ba14bc304d2a276b9c1d1977d2d22` |

精确交付清单只有 `.scratch/pring-data-acquisition-repair/lpr-usage-evidence-review.md`。没有新增原件文件、代码、认证、来源声明或模型；没有改动上述输入。

以下在仓库根执行，仅检查9个本地输入、所有本地链接/行号、收据数量状态以及报告 bytes/SHA256，不写文件、不联网、不导入应用：

```powershell
@'
from pathlib import Path
from urllib.parse import unquote
import hashlib, json, re
report = Path('.scratch/pring-data-acquisition-repair/lpr-usage-evidence-review.md')
raw = report.read_bytes()
text = raw.decode('utf-8')
links = re.findall(r'\[[^\]]+\]\(([^)]+)\)', text)
local_links = [s for s in links if not s.startswith(('https://', 'http://'))]
for target in local_links:
    name, _, anchor = target.partition('#')
    path = report.parent / unquote(name)
    assert path.is_file(), target
    if re.fullmatch(r'L\d+', anchor):
        assert 1 <= int(anchor[1:]) <= len(path.read_text(encoding='utf-8').splitlines())
inputs = re.findall(r'^\| \[[^\]]+\]\(([^)]+)\) \| (\d+) \| `([0-9a-f]{64})` \|$', text, re.M)
assert len(inputs) == 9
for name, size, digest in inputs:
    content = (report.parent / name).read_bytes()
    assert len(content) == int(size), name
    assert hashlib.sha256(content).hexdigest() == digest, name
data = json.loads((report.parent / 'evidence-lpr-import-20260908/receipts.json').read_bytes())
assert len(data['receipts']) == 9
assert sum(len(r['parsed_unreviewed_release']['observations']) for r in data['receipts']) == 18
assert {r['receipt']['state'] for r in data['receipts']} == {'validated'}
assert data['source_claims_created'] == data['source_certification_grants'] == data['production_writes'] == 0
print({'inputs': len(inputs), 'local_links': len(local_links), 'receipts': 9,
       'parsed_unreviewed_values': 18, 'bytes': len(raw),
       'sha256': hashlib.sha256(raw).hexdigest()})
'@ | C:/Python313/python.exe -B -
```
