# CNY030 官方目标日实值：新入口排查边界

研究日：2026-09-08（Asia/Shanghai）。固定目标为 **2026-08-28、官方完整代码 `000012CNY030`、国债指数（全）/ Government Bond Index (Full)**。本项目指标是 `CN_BOND_FULL_PRICE_CNY030`，交付方后缀 `.CSI` 不自动属于官方代码。范围依据[票06](issues/06-market-index-certification.md#L7)；不替换指数、移动目标日或更新认证。

**结果：仍未取得目标日 CNY030 官方点位。** 本轮独立校验旧身份/空响应/表头导出后，沿一个此前未验证的官方入口完成3个唯一URL的有界GET，均返回200；第三页源码明确使用 `000012` 母指数，不能充当CNY030。没有继续调用母指数的行情接口，也没有重复旧空接口或404地址。新的有效目标样本为0；这只说明本轮证据不足，不证明官方不存在此数据或必须付费采购。

## 1. 旧证据链经本轮核对后的准确状态

本轮先读[研究06](research-06.md#L58)、[最新官方文件路径专项](../../docs/research/index-official-resolution-2026-09-05.md#L32)和[之前的接口/导出跟进](../../docs/research/market-indices-valuation-followup-2026-09-05.md#L121)。后者已经尝试的失败路径没有再次访问。

| 已有证据 | 本轮只读复核结果 | 不能据此声称什么 |
| --- | --- | --- |
| [000012官方派生列表原件](evidence-06/0182843a2d891af5ab5cbb822ec2347a6742bce8493a04b49283004e88e6ffb8.json)，[官方URL](https://www.csindex.com.cn/csindex-home/perf/get-derivative-index?indexCode=000012) | JSON中精确存在 `000012CNY030` 和两个中英文全价名称；同时另列净价H00012、利息N00012。 | 身份明确不等于已经得到任一交易日点位。Full不能改成总回报或另一个债券指数。 |
| [官方下载元数据原件](evidence-06/4e59132fa2f6cb5f04f9367cdffe0124e485e1912c98a8c90bff092c6457b7c9.json)，[官方URL](https://www.csindex.com.cn/csindex-home/indexInfo/index-details-data?indexCode=000012&fileLang=2) | 列有 CNY030 专属factsheet路径；其余样本权重/名单路径属于000012母指数。 | 专属factsheet在旧请求为404，不能把列有下载链接当已取得文件；母指数权重不能反推出CNY030点位。 |
| [精确代码基本信息原件](evidence-06/38dbe39b0f3719e98c1e36d24dff52b4140f8cb1b5fd2037af745e4e025da643.json)，[官方URL](https://www.csindex.com.cn/csindex-home/indexInfo/index-basic-info/000012CNY030?lang=zh_CN) | `data`的29个字段全部null；HTTP/业务200并没有真实基本信息行。 | 不能确认币种、基日、推出日、文件交付代码或系统归属；不能从代码包含CNY来补全空字段。 |
| [历史日线原件](evidence-06/8309cff714d5f872cea03bfa413b0270b30b5db6545e99d9dd2b59bc489344eb.json)，[既有请求URL](https://www.csindex.com.cn/csindex-home/perf/index-perf?indexCode=000012CNY030&startDate=20250806&endDate=20260828&lang=zh_CN) | 55字节，`data=[]`；[原回执](evidence-06/receipts.json)记2026-09-06T14:21:39.672961+00:00接收。 | 不能将请求中的起止日期当返回覆盖，不能将空数组当点位0或给定日无交易的证明。 |
| [既有导出XLSX](evidence-06/37bf6b5edaefd3d6e51ad28df98455d1ce1657dd59ce4de44570c53720239b07.xlsx) | 标准库解压XML确认工作表 `000012CNY030perf` 只有1行、15个表头单元格；A1是日期，B1是指数代码，J1是收盘Close，无数据行。 | 文件格式有效和hash完整不等于日期/数值样本有效。 |

明确不重复的既有失败入口包括：精确代码 `index-perf` 日线（已覆盖目标窗及其他多段日期）、`index-basic-info`、`get-index-yield-item`、`index-perf-oneday`、`exportExcel/downloadindex-perf`及CNY030专属factsheet。原请求参数、空结果、旧404和取得时间仍见上述旧跟进；本轮没有用换日期、换语言参数来重复探针。

[文件路径专项第44–48行](../../docs/research/index-official-resolution-2026-09-05.md#L44)已有另一条正确的条件路径：先取得真实 `indexbasicinfo` 中的互联网代码/交付代码/系统对应行，再读取对应系统行情文件。官方格式规范是该路径的依据，不是实际目标数据或已验证匿名URL。本轮没有猜拼 `Vendor/basic`、FTP、`YYYYMMDD*_perf`或日报服务器下载地址。

## 2. 新发现入口：可读，但源码证实为母指数

官方域搜索给出[上交所债券市场数据入口](https://bond.sse.com.cn/data/)。检索本项目既有研究Markdown及回执未发现该入口已被本项目请求的记录，因此沿它公开引用的菜单脚本顺序读取。这里的“未尝试”仅针对已审阅的项目记录，不宣称所有外部历史中都未访问过。

1. **市场数据页**返回HTML；其 `script src` 明确引用 `/xhtml/js/bond_map.js?v=3.2.1`。未加载或执行页面脚本、第三方CDN、其他无关资源。
2. **官方菜单脚本**第194、199行列“指数走势/上证国债指数”，实际路径为 `/data/standard/indecies/tbindex/`。按这个原文路径继续，不猜URL。
3. **上证国债指数页面**第19行标题为上证国债指数，第426行明确 `var BONDCODE = "000012";`，第427行按该代码构造快照URL。由该页取得的是母指数入口，未取得CNY030目标日数据行。于是停止，不修改BONDCODE参数请求另一个未经入口证实的代码，不调用它的下游POST行情。

这是本轮新增且可以审阅的排除依据：**新官方门户中的国债指数菜单不等于CNY030入口**。官网存在这个母指数页面不证明派生指数不存在，也不允许用母指数替代。

| 请求 | 原始URL = 最终URL | 开始UTC → 接收完成UTC | HTTP / 类型 / bytes | 精确响应SHA256 |
| --- | --- | --- | --- | --- |
| GET01 | https://bond.sse.com.cn/data/ | 2026-09-07T22:25:49.392240+00:00 → 2026-09-07T22:25:49.693348+00:00 | 200 / text/html / 23066 | `88e8c07e395b733037608b4b659a812adde78ef30c66b59b9891fefb7bbcb97f` |
| GET02 | https://bond.sse.com.cn/xhtml/js/bond_map.js?v=3.2.1 | 2026-09-07T22:26:17.654204+00:00 → 2026-09-07T22:26:17.917769+00:00 | 200 / application/javascript / 13403 | `cb7e9ffcd56d929305da02e09658d5dd3c8bd99b21c3e763a467ea03c9c7218d` |
| GET03 | https://bond.sse.com.cn/data/standard/indecies/tbindex/ | 2026-09-07T22:26:46.578312+00:00 → 2026-09-07T22:26:46.931552+00:00 | 200 / text/html / 27399 | `11aca967d67306d5d7c0b5b7022a3860ed5741e3b74d66bed1c4fd76bc4c467c` |

每次均为Windows Python标准库直接GET，15秒超时、500001字节上限、不跟随重定向；3份响应合计63,868字节，均未截断。网页第18行的“页面生成时间2023-12-19”与本次HTTP Date都不是目标指数在2026-08-28的发布时刻。

**新响应原始字节未写入文件/CAS。** 按单MD交付，本报告保存URL、实际回执、响应hash和必要源码摘录；没有把hash称为已登记原件，也没有截图/浏览器DOM证据。上述3份内存响应可说明本轮读取和排除过程；如以后正式引用该新入口，应保存被引用响应的新实际原件，不能用本MD重建原始HTTP字节。

## 3. 实际计数与仍缺的最小对象

本轮执行3个网页搜索工具调用，共6个逻辑查询：

1. `site:csindex.com.cn "000012CNY030" "2026"`
2. `site:csindex.com.cn "20260828" "国债" "指数"`
3. `site:csindex.com.cn "CNY030"`
4. `site:sse.com.cn "国债指数(全)"`
5. `site:csindex.com.cn "国债指数" "2026-08-28"`
6. `site:csindex.com.cn "000012CNY030" "下载"`

首尾两组查询返回空结果；中间组给出上交所门户和交易所技术规范等候选，没有CNY030目标日数值。只读取与新门户路径有关的3个唯一官方URL，实际直接HTTP请求3次、成功3次、失败0次；未使用第4个URL额度凑数。搜索引擎内部HTTP次数未知，不能与直接GET数混合。**HTTP成功率3/3只是研究传输统计，有效目标数值样本0、认证授予0、模型采用0。** 本轮不是Tavily/Exa配对试验，不进入它们的请求成功率或模型可用缺口补齐率。

| 需要解决的事实 | 现有可用证据 | 最小下一对象 / 动作 |
| --- | --- | --- |
| 精确身份 | `000012CNY030`对应国债指数（全）已有官方派生列表。 | 保留完整代码，不缩为000012，不改成净价、利息、10年国债或总回报系列。 |
| 2026-08-28官方点位及精度 | 仍没有目标点位原件；[研究06第74行](research-06.md#L74)的111.2608是旧规范化交付声明，不是官方独立期望。 | **一份官方发布物直接给出完整目标代码/全价身份、目标日期、收盘点位和实际小数表示即可成为数值锚点候选。** 不要求为了第一个锚点先补全120天双源。 |
| 文件交付代码映射 | 只有格式/目录规范；精确代码的基本信息接口全空。 | 若文件使用另一交付代码，须同时取得实际 `indexbasicinfo` 对应行和20260828该代码的行情行；不能猜系统包。若同一公开发布物已清楚绑定完整目标身份和日期/点位，不额外强制另找基本信息文件才承认该样本。 |
| 单位及小数精度 | 项目要求 `index_points`，但本次没有目标数值去验证官方显示/交付精度。 | 使用目标原件实际单位、小数位及舍入说明与111.2608对照；其他CSI网页两位小数不自动成为CNY030容差规则。 |
| 实际公开时间/修订 | 历史请求日期、交易日、本次收到时间及首页生成时间均不证明目标发布时刻。 | 在取得目标实值后记录该原件可证的实际发布日期/时间及修订边界；不能预设15:30，也不能将无发布证明的交易日期按次日规则冒充PUBLIC。 |

目前没有发现新的、已证实能交付CNY030的匿名查询或下载URL；不继续重试旧空路径。下一次研究应由上述**新具体目标原件或有明示目标映射的官方入口**触发，不只因为已有格式规范就继续枚举。这里没有判断用户是否拥有某项服务、没有读取凭据、申请许可或进行采购。数值锚点准备与正式来源包、历史覆盖、点时查询和候选模型验收仍是不同结果；本报告不宣布票06通过。

## 4. 本地输入指纹和默认只读复核

前5项是所读文档/回执，后5项是本轮实际重新核验的官方原件，合计原件6,446字节。精确交付清单只有 `.scratch/pring-data-acquisition-repair/cny030-official-next-boundary.md`；没有改动旧文件、代码、证书、模型或数据库。

| 输入 | bytes | SHA256 |
| --- | ---: | --- |
| [票06](issues/06-market-index-certification.md) | 2892 | `97c55db140f75bf59a82d9ec4598464db9a84744bcf8f9aa713b9303744eb9d8` |
| [研究06](research-06.md) | 36738 | `955e25954a1a305d2b4aed42ea9de565a48164eb2785d92a9a686c0fd8fe43dc` |
| [旧回执](evidence-06/receipts.json) | 21592 | `61a7c16efa7b0d72aaed7d13397010cfeba5ac3f36b5fcf2f74f8383040a9d98` |
| [官方文件路径专项](../../docs/research/index-official-resolution-2026-09-05.md) | 17153 | `85ddc94d8eaaa29495e395874a36c464b568d68d036abd69c25aa66c92af52bc` |
| [早前接口与导出跟进](../../docs/research/market-indices-valuation-followup-2026-09-05.md) | 28178 | `2b73dfd9a4fc75c828bacf9ab5312a0cae6f6bb8408225353f07fd877d8bad2e` |
| [派生身份JSON](evidence-06/0182843a2d891af5ab5cbb822ec2347a6742bce8493a04b49283004e88e6ffb8.json) | 358 | `0182843a2d891af5ab5cbb822ec2347a6742bce8493a04b49283004e88e6ffb8` |
| [下载元数据JSON](evidence-06/4e59132fa2f6cb5f04f9367cdffe0124e485e1912c98a8c90bff092c6457b7c9.json) | 1635 | `4e59132fa2f6cb5f04f9367cdffe0124e485e1912c98a8c90bff092c6457b7c9` |
| [全空基本信息JSON](evidence-06/38dbe39b0f3719e98c1e36d24dff52b4140f8cb1b5fd2037af745e4e025da643.json) | 637 | `38dbe39b0f3719e98c1e36d24dff52b4140f8cb1b5fd2037af745e4e025da643` |
| [空日线JSON](evidence-06/8309cff714d5f872cea03bfa413b0270b30b5db6545e99d9dd2b59bc489344eb.json) | 55 | `8309cff714d5f872cea03bfa413b0270b30b5db6545e99d9dd2b59bc489344eb` |
| [表头导出XLSX](evidence-06/37bf6b5edaefd3d6e51ad28df98455d1ce1657dd59ce4de44570c53720239b07.xlsx) | 3761 | `37bf6b5edaefd3d6e51ad28df98455d1ce1657dd59ce4de44570c53720239b07` |

仓库根运行以下标准库代码，仅验证10输入、链接/行号及旧失败材料的具体内容，并打印本报告bytes/SHA；不联网、不导入应用、不写文件。它不能重新验证本轮未保存的3份网络原始字节，也不将失败材料校验通过当数值样本通过。

```powershell
@'
from pathlib import Path
from urllib.parse import unquote
import hashlib, json, re, zipfile, xml.etree.ElementTree as ET
p = Path('.scratch/pring-data-acquisition-repair/cny030-official-next-boundary.md')
raw = p.read_bytes()
text = raw.decode('utf-8')
links = re.findall(r'\[[^\]]+\]\(([^)]+)\)', text)
local_links = [x for x in links if not x.startswith(('https://', 'http://'))]
for target in local_links:
    name, _, anchor = target.partition('#')
    q = p.parent / unquote(name)
    assert q.is_file(), target
    if re.fullmatch(r'L\d+', anchor):
        assert 1 <= int(anchor[1:]) <= len(q.read_text(encoding='utf-8').splitlines())
inputs = re.findall(r'^\| \[[^\]]+\]\(([^)]+)\) \| (\d+) \| `([0-9a-f]{64})` \|$', text, re.M)
assert len(inputs) == 10
for name, size, digest in inputs:
    b = (p.parent / name).read_bytes()
    assert len(b) == int(size) and hashlib.sha256(b).hexdigest() == digest, name
base = p.parent / 'evidence-06'
identity = json.loads((base / '0182843a2d891af5ab5cbb822ec2347a6742bce8493a04b49283004e88e6ffb8.json').read_bytes())
assert [r['indexCode'] for r in identity['data'] if r['indexCode'] == '000012CNY030'] == ['000012CNY030']
empty = json.loads((base / '8309cff714d5f872cea03bfa413b0270b30b5db6545e99d9dd2b59bc489344eb.json').read_bytes())
assert empty['data'] == []
basic = json.loads((base / '38dbe39b0f3719e98c1e36d24dff52b4140f8cb1b5fd2037af745e4e025da643.json').read_bytes())['data']
assert len(basic) == 29 and all(v is None for v in basic.values())
ns = {'x': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
with zipfile.ZipFile(base / '37bf6b5edaefd3d6e51ad28df98455d1ce1657dd59ce4de44570c53720239b07.xlsx') as z:
    sheet = ET.fromstring(z.read('xl/worksheets/sheet1.xml'))
    rows = sheet.findall('.//x:row', ns)
    cells = sheet.findall('.//x:c', ns)
    assert len(rows) == 1 and len(cells) == 15
    assert 'Close' in ''.join(cells[9].itertext())
print({'inputs': len(inputs), 'local_links': len(local_links),
       'official_numeric_samples': 0, 'bytes': len(raw),
       'sha256': hashlib.sha256(raw).hexdigest()})
'@ | C:/Python313/python.exe -B -
```
