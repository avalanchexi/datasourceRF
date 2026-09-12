# 09：平安银行2026-025实施公告的第一方披露日期锚点

2026-09-13，Asia/Shanghai；后台研究434。只研究[429报告](research-09-adjustment-sample-429.md)所用同一公告的公开日期，不扩展行情、复权公式或认证。实际发起2次匿名公开请求，均成功，取得后结束；未使用账户接口、凭据、行情请求，也未改源码、测试、任务状态、运行库、模型、429报告或旧原件。

**已取得可绑定同一PDF的深交所披露列表记录，可以补足这个公告的日期级公开锚点：2026-06-05。返回的`00:00:00`不按已证明的真实发布时分秒使用。** 按项目现行日期精度规则，推导的保守PUBLIC起点为上海时间**2026-06-06 00:00:00（UTC 2026-06-05 16:00:00）**；这是本报告的研究映射结论，尚未创建或校验任何来源声明，也不认证行情公开时间或完整复权链。[深交所原始列表响应](research-09-publication-434/0f00b733e8ca0cfc6ff606af8fccce0d74cbdfdf2cbd58537dea0b0f56fca1e9.bin)、[CONTEXT](../../CONTEXT.md:173)

## 1. 唯一披露记录与原公告的身份链

匿名读取[深交所公告列表接口](https://www.szse.cn/api/disc/announcement/annList)，方法为POST，但语义是公开公告检索。请求未携带Cookie、token或其他凭据；只传股票、日期和列表分页条件：

```json
{"seDate":["2026-06-05","2026-06-05"],"stock":["000001"],"channelCode":["listedNotice_disc"],"pageSize":30,"pageNum":1}
```

响应`announceCount=1`，`data`只有一条记录。以下全部字段来自响应正文，不是本地填入的请求条件、搜索摘要或PDF文件名推断：[列表原件](research-09-publication-434/0f00b733e8ca0cfc6ff606af8fccce0d74cbdfdf2cbd58537dea0b0f56fca1e9.bin)。

|返回字段|实际值|证明范围|
|---|---|---|
|`secCode` / `secName`|`["000001"]` / `["平安银行"]`|将记录绑定到该证券主体。|
|`title`|`平安银行：2025年年度权益分派实施公告`|与429所用实施公告标题对应。|
|`id`|`d6d1bbd3-113f-458e-a289-9eb5750bc1c3`|当前深交所列表记录ID；不与附件ID混用。|
|`annId`|`1225352449`|响应给出的公告标识；本轮未另请求CNINFO详情，不推断它的跨系统时钟含义。|
|`publishTime`|`2026-06-05 00:00:00`|官方披露记录将该条目归在6月5日；保守采用日期精度，见第2节。|
|`attachPath`|`/disc/disk03/finalpage/2026-06-05/bde1eece-e914-4a31-a51d-5de619feb208.PDF`|列表直接指向429所用附件UUID；日期不是由此路径抽取的。|
|`attachFormat` / `attachSize`|`PDF` / `137`|附件格式及展示大小；`137`单位未在本响应说明，未用于验证实际字节长度。|

第二次请求使用返回的`attachPath`，在深交所公开附件域名上读取[PDF](https://disc.static.szse.cn/disc/disk03/finalpage/2026-06-05/bde1eece-e914-4a31-a51d-5de619feb208.PDF)。实际返回139278字节，SHA-256为`8e9d5facebfd8c46e049f0e6b0839e2be31ef292a5e3db903591fc08be9af5b8`，并与[429所用旧原件](/home/tywin/.local/share/pring-cycle/artifacts/sha256/8e/8e9d5facebfd8c46e049f0e6b0839e2be31ef292a5e3db903591fc08be9af5b8)逐字节比较完全相同。旧下载URL有`/download/disc/`前缀，本次按列表使用`/disc/`；身份相同由字节相等证明，不靠猜测两种URL是否等价。

本轮重新提取新PDF：第1页明确证券代码`000001`、公告编号`2026-025`和完整实施公告标题；第2页末尾落款6月5日。**公告编号由正文拥有，披露日期由列表拥有，两者通过同一附件和字节哈希绑定。** 这比“PDF落款和URL含6月5日”多取得了独立的第一方披露记录。[新PDF原件](research-09-publication-434/8e9d5facebfd8c46e049f0e6b0839e2be31ef292a5e3db903591fc08be9af5b8.pdf)

## 2. 日期精度和真实时分秒的区别

`publishTime`虽然带有时间格式，但本轮没有取得该接口把午夜解释为真实首发时刻的语义文档，也没有第一方精确时间戳或当时取得记录交叉证明。不能因值恰好为`00:00:00`，就宣称公告在6月5日零点已经对所有用户可得。此记录足以作为官方声明的**披露日期**锚点，不足以证明同日开市前、任意同日小时或精准午夜可知。[列表原件](research-09-publication-434/0f00b733e8ca0cfc6ff606af8fccce0d74cbdfdf2cbd58537dea0b0f56fca1e9.bin)

按照[公开可用时间定义](../../CONTEXT.md:173)，仅有可靠日期时从下一本地日开始，故研究映射为：

```text
source_disclosure_date = 2026-06-05
publication_precision = date
source_timezone = Asia/Shanghai
exact_publication_timestamp = unknown
conservative_public_available_at = 2026-06-06T00:00:00+08:00
                                = 2026-06-05T16:00:00+00:00
```

以上为拟用于验收的解释，不是已入库字段。它没有把未来除息日6月12日当作发布时间，也没有用签署日期、URL日期、HTTP Last-Modified或本轮取得时间替代披露日期。6月11日收市后登记、6月12日除息和现金支付仍由PDF第2页拥有；公告提前可知不使除息效果提前生效。[公告第2页](research-09-publication-434/8e9d5facebfd8c46e049f0e6b0839e2be31ef292a5e3db903591fc08be9af5b8.pdf)

当前检索结果声明的是历史披露日。本轮字节一致性又证明这份正文与9月5日已存副本相同，但没有证明6月5日至9月5日期间从未存在过修订、撤回或重新发布。对本次单公告日期锚点而言，这不应被改写成“精确首发时间已认证”；对完整历史事件链仍应保留修订覆盖要求。[旧获取记录](../../docs/research/market-breadth-inputs-followup-2026-09-05.md:47)、[ADR0006](../../docs/adr/0006-dual-as-of-and-immutable-evidence-vintages.md:7)

## 3. 两份新响应的取得记录

所有时刻为本轮实际观察的UTC时间；另用单调时钟记录持续时间，未利用HTTP Last-Modified。重定向自动跟随已关闭，两次均直接HTTP200、最终URL与请求URL相同。实际请求数为2，未重试；搜索只定位第一方线索，第三方结果未作为证明材料。

|请求|开始/收到时间UTC|单调持续时间|结果与本地原件|
|---|---|---:|---|
|1 POST `https://www.szse.cn/api/disc/announcement/annList`；完整body见第1节|2026-09-12T19:35:50.302241+00:00 / 2026-09-12T19:35:51.622151+00:00|1.319898055秒|200；`application/json;charset=UTF-8`；520字节；[原响应](research-09-publication-434/0f00b733e8ca0cfc6ff606af8fccce0d74cbdfdf2cbd58537dea0b0f56fca1e9.bin)，SHA-256 `0f00b733e8ca0cfc6ff606af8fccce0d74cbdfdf2cbd58537dea0b0f56fca1e9`。|
|2 GET `https://disc.static.szse.cn/disc/disk03/finalpage/2026-06-05/bde1eece-e914-4a31-a51d-5de619feb208.PDF`|2026-09-12T19:36:20.890297+00:00 / 2026-09-12T19:36:21.009449+00:00|0.119075554秒|200；`application/pdf`；139278字节；[原响应](research-09-publication-434/8e9d5facebfd8c46e049f0e6b0839e2be31ef292a5e3db903591fc08be9af5b8.pdf)，SHA-256 `8e9d5facebfd8c46e049f0e6b0839e2be31ef292a5e3db903591fc08be9af5b8`。|

两份保存文件再次计算哈希，与上述值一致；PDF比较和提取均在本地完成，没有申请第三份响应。没有读取或更改运行库，故本轮取得记录不是证据仓库的首次通过校验时间，不宣称已进入SYSTEM模型输入。

## 4. 对429缺口的增量及仍未完成的事项

本报告只补429第7节第1项中的**这一个公告的日期级披露锚点**。保留429原文及原结论作为当时研究记录，用新报告说明新增证据；不回写旧未知字段。后续若要作为软件的真实原件样本，可分别绑定列表哈希、公告哈希、记录ID、公告编号、日期精度和事件有效日，经公开采集/校验入口新建版本。[429报告](research-09-adjustment-sample-429.md:93)、[票09](issues/09-breadth-window-metrics.md:24)

仍未证明：公告精确首发时分秒、两日日行情的历史PUBLIC、所有证券及预热期间的完整事件/修订链、实际历史adj_factor比值、来源许可与认证包、120日回放及模型切换。本报告不以取得一个日期锚点解除这些门，也不阻塞独立的软件窗口TDD。
