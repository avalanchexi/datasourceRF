# CPI 新目录消费：正式来源审查的最小前置

2026-09-08，Asia/Shanghai。范围仅 `nbs_core_cpi` 家族的 `CN_CPI_HEADLINE` 和 `CN_CORE_CPI`，沿用已有8期原件和逐值审查；没有重抓8个数值页面、运行应用、修改旧证据或授予认证。

**8期官方页头与 PubDate 已重新逐页核对，全部一致；46个字段/数值的既有独立审查可以直接复用。国家统计局服务条款本轮已实际 GET 成功，明确支持下载和使用其发布的统计数据，个人本机保存、计算不应再被列为笼统“待采购/待用户许可”阻塞。** 下一步主要是把这些已有事实绑定到新定义的真实原件登记、取得收据和六项正式审查，分别处理具体修订与系统时间；软件成功消费本身不会生成正式 `accepted`。

## 1. 可以直接复用的字段事实

[逐值审查](p1-cpi-full-value-audit.md#L5)已完成8期、8份唯一原件、46个准备标量的独立原表定位：46相符、0冲突、0无法核验。每个指标23格；本轮复用这一完成结果，**没有重新宣称执行46格审计或当前应用解析回归**。本轮新增检查是8原件 SHA/长度及逐页两个发布时间位置的对应。

| 指标 / category | 可用 measure 与 source_field | 单位与期次 |
| --- | --- | --- |
| `CN_CPI_HEADLINE / headline` | `mom → headline_cpi_mom_pct`；`yoy → headline_cpi_yoy_pct`；`cumulative_average_yoy → headline_cpi_ytd_avg_yoy_pct` | `percent`；统计月，原表百分数不再除100。累计列标识其截至月，不当作该月单月同比。 |
| `CN_CORE_CPI / ex_food_energy` | `mom → core_cpi_mom_pct`；`yoy → core_cpi_yoy_pct`；`cumulative_average_yoy → core_cpi_ytd_avg_yoy_pct` | `percent`；同一原表“不包括食品和能源”行，不能从总体减去其他项推算。 |

[原表列与身份说明](p1-cpi-full-value-audit.md#L57)已证明：2026-01原表没有累计列，两指标各2格，其余7期各3格，合计 `7×6+1×4=46`。没有 `level` 维度；1月缺累计不填0、不复制同比。2025-12的累计是全年平均同比，真实0.0和负环比都不是缺值。原响应内重复表格不能算第二来源。

2026-01原件附注第670行记载开始采用2025年基期及分类、规格品、调查点、权数变化；这是应保留的来源口径事件，不是让各值减去基期影响估计。旧文档把累计列统一称必填的措辞，应以已核实的1月缺列事实及本次新定义实际规则审查，不能强制制造48格。[旧研究](../../docs/research/official-gap-source-audit.md#L102)可作家族语义背景，不能覆盖这份逐月原表检查。

## 2. 8期时间逐页一致，可以作为来源时间证据

下表每页均重新读取精确原件，校验字节数及 SHA。`PubDate` 为原始 HTML 第11行，可见页头为第277行；**8/8两个位置字面一致，8/8与既有逐值报告时间一致**。两个位置属于同一页面，不算两个独立来源。

| 统计期 / 官方来源 | PubDate = 可见页头 | 原件（第277行） | bytes | SHA256 |
| --- | --- | --- | ---: | --- |
| [2025-12](https://www.stats.gov.cn/sj/zxfb/202601/t20260109_1962273.html) | 2026/01/09 09:30 | [R01](//wsl.localhost/Ubuntu-22.04/home/tywin/.local/share/pring-cycle/artifacts/sha256/02/029d16d76ba6c207b46be0cf4a13ca2c88ae431540aec335778644e97830da7f#L277) | 220743 | `029d16d76ba6c207b46be0cf4a13ca2c88ae431540aec335778644e97830da7f` |
| [2026-01](https://www.stats.gov.cn/sj/zxfb/202602/t20260211_1962588.html) | 2026/02/11 09:30 | [R02](//wsl.localhost/Ubuntu-22.04/home/tywin/.local/share/pring-cycle/artifacts/sha256/f6/f65b52d3c2418f40a43e0991d041e0295e56941ca7d9bc9bad76e0d5d0cab964#L277) | 198964 | `f65b52d3c2418f40a43e0991d041e0295e56941ca7d9bc9bad76e0d5d0cab964` |
| [2026-02](https://www.stats.gov.cn/sj/zxfb/202603/t20260309_1962732.html) | 2026/03/09 09:30 | [R03](//wsl.localhost/Ubuntu-22.04/home/tywin/.local/share/pring-cycle/artifacts/sha256/32/321b7693d1e112a92c83fc16293cc115429b0dee88e4201f115668850cf97043#L277) | 246192 | `321b7693d1e112a92c83fc16293cc115429b0dee88e4201f115668850cf97043` |
| [2026-03](https://www.stats.gov.cn/sj/zxfb/202604/t20260410_1963264.html) | 2026/04/10 09:30 | [R04](//wsl.localhost/Ubuntu-22.04/home/tywin/.local/share/pring-cycle/artifacts/sha256/ac/acaf1bd86124b1aca4c7ed1cee26560d0fe24c665d614ca4ca2b10c2601a811a#L277) | 246454 | `acaf1bd86124b1aca4c7ed1cee26560d0fe24c665d614ca4ca2b10c2601a811a` |
| [2026-04](https://www.stats.gov.cn/sj/zxfb/202605/t20260511_1963659.html) | 2026/05/11 09:30 | [R05](//wsl.localhost/Ubuntu-22.04/home/tywin/.local/share/pring-cycle/artifacts/sha256/5b/5b35264f5e63c0776701fb2586ffd8511f28fdc4360547a791de51e2cc7750c4#L277) | 236292 | `5b35264f5e63c0776701fb2586ffd8511f28fdc4360547a791de51e2cc7750c4` |
| [2026-05](https://www.stats.gov.cn/sj/zxfb/202606/t20260610_1963923.html) | 2026/06/10 09:30 | [R06](//wsl.localhost/Ubuntu-22.04/home/tywin/.local/share/pring-cycle/artifacts/sha256/f0/f021e838ebf280e92cde9f4d965cf6b40d4efba391ff4225970731662493559f#L277) | 234920 | `f021e838ebf280e92cde9f4d965cf6b40d4efba391ff4225970731662493559f` |
| [2026-06](https://www.stats.gov.cn/sj/zxfb/202607/t20260709_1964084.html) | 2026/07/09 09:30 | [R07](//wsl.localhost/Ubuntu-22.04/home/tywin/.local/share/pring-cycle/artifacts/sha256/57/57665164e369235239d22d66d37d19f86172b2ac20a5e755c72199ad7a953d84#L277) | 233834 | `57665164e369235239d22d66d37d19f86172b2ac20a5e755c72199ad7a953d84` |
| [2026-07](https://www.stats.gov.cn/sj/zxfb/202608/t20260809_1965008.html) | 2026/08/09 09:30 | [R08](evidence-13/a4b8c84fa4b005807a9c30b4a41c06726f571bd203e753db81532be4dee54a49#L277) | 233412 | `a4b8c84fa4b005807a9c30b4a41c06726f571bd203e753db81532be4dee54a49` |

合计1,850,811 bytes。原页时间精度到分钟，没有秒或时区字串；项目已有 `Asia/Shanghai` 定义可继续使用并写明这是项目的解释，不把补齐`:00`说成独立秒级证据，也不为同一时区重复增加业务批准。

**这些可靠原页时间可直接进入 time finding 的证据清单。** [研究13第42行](research-13.md#L42)已允许用原页时间证明所引用页面的公开时间，并针对无新发布时间的后续修订保留未知。未保存“历史第一次发布的全部精确字节”不等于原页没有可靠时间；不能将8页 PUBLIC 一律设未知，也不能用通常9:30日程、统计月末或取得时钟替代这8个实际日期。

具体修订仍按事实区分。[旧查询快照](evidence-13/legacy-read-matrix.json)的 `metrics[15]` 中，7月核心 CPI 的原 PUBLIC 样本引用 `1ae383d1…`，后来的 SYSTEM 样本引用 `a4b8c84f…`，三个新声明均有 `supersedes_claim_id`，但旧/新所列 MoM、YoY、累计值同为0.3、0.9、1.1，原页时间同为8月9日09:30。**哈希变化或 supersedes 标签本身不能证明官方改过数值。** 本轮只核上述快照，没有重新读取前一哈希原件，因此不声称完成全部旧/新字节或官方修订链审查。

正式 time finding 应解释实际选用原件的时间和版本：已证页面时间可以使用；若具体比较发现数值或语义后来变化且没有可靠的新发布时间，该新 vintage 的历史 PUBLIC 保持未知，旧版本保留。只为这种实际冲突补更正公告、旧原件或可证明的新时间，不要求8期一律补第二来源或全档首发证明。

## 3. 用途已有官方正面依据，不增加许可泛化门

8页页脚均指向同一个[国家统计局服务条款](https://www.stats.gov.cn/wzgl/202302/t20230217_1912857.html)，例如R02第2170行、R08第2366行。旧逐值审查仅见入口，本轮补读了正文。

该条款第三节“数据使用”明确用户可以“下载和使用”国家统计局发布的统计数据，并要求个人及组织机构依法、准确使用。第一节要求转载/引用注明国家统计局网站和网址；第二节区分统计内容与第三方作品、特别授权内容及页面设计/程序等例外。**对本任务的官方 CPI 数值、个人本机保存和计算，这提供了可直接引用的正面用途依据。** 本用途不涉及取得第三方作品或复制网站程序来再发布；不能因网页页脚有版权署名就推定数据下载分析需要另购许可。

八份月报页面第284行的来源逻辑均写国家统计局，正文是其统计发布；未见本范围数据另附禁止使用说明。这里的用途结论是对实际公开统计数据与条款的对应，可进入正式审查草案；没有给所有网站内容、商业分发或其他未知用途作法律结论，也没有授予来源认证。

本轮已取得服务条款的**真实 HTTP 200 原文**，不只依赖搜索摘要；但单MD交付未保存完整响应文件或登记 raw artifact。最小补件是正式原件登记阶段对这份条款保存一次带收据的原件并关联引用，**不必为用途再抓8份数值页，也不必再让用户确认同一项个人使用意愿**。

| 服务条款核验项 | 实际记录 |
| --- | --- |
| 原始/最终 URL | https://www.stats.gov.cn/wzgl/202302/t20230217_1912857.html |
| 起始 UTC | 2026-09-07T21:52:50.079313+00:00 |
| 接收完成 UTC | 2026-09-07T21:52:50.273577+00:00 |
| 方法 / 状态 / 类型 | GET / 200 / text/html；不跟随重定向 |
| 精确响应 bytes / SHA256 | 127670 / `fcb330d080046d9700e53c9a6416b3a97ca52a5cea770e7d467c2ea98589b5fe` |
| 条文源码定位 | UTF-8第284行：第一至五节；第298行重复同一正文。第三节是数据下载/使用依据。 |
| 读取边界 | Windows Python标准库，15秒超时，最多300001 bytes；本次未截断。 |
| 保存边界 | 本 MD 保存回执及短引文；`raw_saved=false`，无新增CAS或原始HTML文件。此hash不能当已经登记的artifact。 |

完整失败分母：同一新URL首次网页工具 open 返回 `Timeout fetching`，工具错误括号中的400不被认作已证官方HTTP400；随后1个官方域搜索查询返回条款正文；最后上述1次标准库GET成功。共1个唯一新官方URL、1次工具open失败、1次搜索、1次直接GET成功；网页工具底层HTTP请求数未知。没有对8个数值URL发起新请求，未使用第二个URL额度，也没有隐去失败或将失败泛化为来源不可达。

## 4. 能立即推进的正式审查准备及真正剩余步骤

| 部分 | 现在可直接提交的证据 | 仍需完成的具体动作 |
| --- | --- | --- |
| semantics / fields | 两指标原表身份、6种成员映射、单位、1月缺列、46格独立字面核对、2026基期事件。 | 将这些事实绑定到新定义和选用原件，而非复制旧目录 `certified` 标签；新目录不得把缺累计列变为0或level。 |
| history / time | 8个月覆盖、8份原件、逐页PubDate/页头一致；实际发布早于后续取得可分别表达。 | 写明具体原件版本和分钟精度；对确实存在的语义/数值修订单独核时间。无需先求全历史首次字节档案。 |
| permissions / usage | 国家统计局直发统计数据和本轮实际读取的明确下载/使用条款；个人本机保存计算有正面依据。 | 正式保存/登记这1份条款原件，绑定数据与条款的引用，写本任务用途finding。没有发现需要新增采购、账户许可或用户批准的事实。 |
| 系统取得 / 制品登记 | 8份既有数值原件可受控导入；旧报告已记录缺原HTTP收据的边界。 | 若本次新目录尚未生成真实导入收据，对8份现存原件做 `document_import`，取得并校验完成后记本次SYSTEM时间和正确raw关联。没有旧取得记录就不倒填历史SYSTEM；原件复制时间也不补成旧HTTP时间。 |
| 正式review与模型使用 | 软件消费路径和本报告可以支持审查准备；它们本身不授信。 | 完成受信维护流程的六项finding/evidence、完整新定义/subject hash与真实原件登记绑定，再形成不可变包。真实入库、点时选值及目标日输出另行验收；本报告不填 `decision=accepted`。 |

[原HTTP回执](evidence-13/receipts.json)及[原件导入记录](evidence-13/imports.json)的既有审查结果是：这8份原件在该包未匹配原始HTTP收据，仅R08有2026-09-06复制记录。这个范围限制可以原样保留，不能据此要求重做8次网络采集。[正式准入契约第31行](candidate-admission-contract.md#L31)要求六项实质审查及真实 artifact/source_reference 关联；MD、fixture或 `accepted` 字符串都不能代替它。

最窄真实消费验收可直接使用现有原件：3月9日08:00的PUBLIC不能见到2月发布，3月9日当天结束时可按其09:30页面证据选2月；8月28日应使用已于8月9日公布的7月值，不能因旧7月声明误写8月31日PUBLIC而继续停在6月。新导入的SYSTEM截点早于本次完成时间仍不可见。这里是待验证的期次/时间期待，不是已完成120交易日模型重放；也不要求8月28日前获得尚未发布的8月月值。[旧时间错配事实](research-13.md#L164)仍须通过新声明修复，旧版本不原地改写。

## 5. 本地输入与只读复核

除上表8份原件外，本轮引用的7个本地文件指纹如下。旧逐值结论与本轮时间核对分开计数；没有给当前工作树软件或生产数据库作验证声明。

| 输入 | bytes | SHA256 |
| --- | ---: | --- |
| [逐值审查](p1-cpi-full-value-audit.md) | 19071 | `1f57b4ee4670e928364225944f685823ef30817a7968a42194892489d1c8c751` |
| [研究13](research-13.md) | 31765 | `dcbdf9a07095e5bfb2110ff2f3a51e9049dc1bece87b3859207df1ece0f973e1` |
| [正式准入契约](candidate-admission-contract.md) | 4937 | `649b65963e52f1f1dc2a217dd513427ba0f1d7084c062f1266df56c15ff551fc` |
| [旧查询快照](evidence-13/legacy-read-matrix.json) | 463940 | `740f094e922ae40ddc21098f86629df8ffcaf416c8dc4595def22f93ba5c8b46` |
| [旧HTTP回执](evidence-13/receipts.json) | 11329 | `edb8fa76f4254b96867d3c55bcd58b1ba432a5d8f71cedbd5c372773663c37c9` |
| [旧导入记录](evidence-13/imports.json) | 5145 | `07da00c64b09c728052b2c2ab5ff7156df6e403714f28653e86d4b9c9855b875` |
| [官方缺口研究](../../docs/research/official-gap-source-audit.md) | 26565 | `17e7f9c5bf94bbaf14c33a481064b868a7b51be22b90eef556fcb3d7bfe95a24` |

精确交付清单只有 `.scratch/pring-data-acquisition-repair/cpi-certification-next-boundary.md`。以下代码从仓库根执行，只读检查7输入、8原件hash/长度/时间、所有本地链接，打印本报告 bytes/SHA；不运行应用、不联网、不写文件。

```powershell
@'
from pathlib import Path
from urllib.parse import unquote
import hashlib, re
p = Path('.scratch/pring-data-acquisition-repair/cpi-certification-next-boundary.md')
raw = p.read_bytes()
text = raw.decode('utf-8')
def local(target):
    name = unquote(target.partition('#')[0])
    return Path(name) if name.startswith('//') else p.parent / name
links = re.findall(r'\[[^\]]+\]\(([^)]+)\)', text)
local_links = [s for s in links if not s.startswith(('https://', 'http://'))]
for target in local_links:
    q = local(target)
    assert q.is_file(), target
    anchor = target.partition('#')[2]
    if re.fullmatch(r'L\d+', anchor):
        assert 1 <= int(anchor[1:]) <= len(q.read_text(encoding='utf-8').splitlines())
inputs = re.findall(r'^\| \[[^\]]+\]\(([^)]+)\) \| (\d+) \| `([0-9a-f]{64})` \|$', text, re.M)
originals = re.findall(r'^\| \[[^\]]+\]\(https://[^)]+\) \| ([0-9/]+ 09:30) \| \[R\d+\]\(([^)]+)\) \| (\d+) \| `([0-9a-f]{64})` \|$', text, re.M)
assert len(inputs) == 7 and len(originals) == 8
for name, size, digest in inputs + [(n,s,d) for _,n,s,d in originals]:
    data = local(name).read_bytes()
    assert len(data) == int(size) and hashlib.sha256(data).hexdigest() == digest, name
for expected, name, _, _ in originals:
    lines = local(name).read_text(encoding='utf-8').splitlines()
    assert re.search(r'<meta name="PubDate" content="([^"]+)">', lines[10]).group(1) == expected
    assert lines[276].strip() == expected
assert sum(int(size) for _,_,size,_ in originals) == 1850811
print({'inputs': len(inputs), 'originals': len(originals), 'time_pairs_equal': 8,
       'local_links': len(local_links), 'bytes': len(raw),
       'sha256': hashlib.sha256(raw).hexdigest()})
'@ | C:/Python313/python.exe -B -
```
