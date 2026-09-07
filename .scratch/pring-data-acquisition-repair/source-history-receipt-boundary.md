# 来源历史烟测：逐请求收据遗漏与最窄修复边界

2026-09-08，Asia/Shanghai。初读基点 `6341dd2be0699734512e672c4ff2618ca624d4fc`；交付源码证据固定为Git提交 `a569fd757c7d19a4ae95b980bd2b1c0c51cba973` 原文。本研究已核对两提交之间相关来源源码/测试无差异。根代理随后开始的工作树目录修复不属于本文代码结论范围，以下“当前”均指这一固定基点。依据现有源码、票03/13、测试和已接受规格；没有网络请求、应用导入/执行、数据库操作或代码修改。唯一新增文件为本文。下列接受例由静态源码确定；根代理另已执行首目录HTTP503的公开RED，具体结果单列，不冒称本研究执行。

**结论：`smoke_source_history` 的目录发现及原件下载没有接通 `AcquisitionRepository`，这是现有公开入口的真实收据遗漏。首个目录请求发生HTTPError时，错误正文及请求状态均没有持久记录；成功目录也不存原件。后续正文只有部分成功路径存CAS，仍缺逐请求received/validated与标准化收据。票03已经修复的历史导入路径不能证明这一抓取路径已覆盖。** 最小第一个RED只需公开烟测的首个discovery请求失败，不需要取得270份正文。

## 规格与已交付范围

[规格 L93—98](spec.md#L93) 要求每次采集保存接口/参数、请求开始/接收完成/校验完成、原始与标准化制品，以及明确声明关联；历史无法证明的关联保持未追溯，不造时间。来源认证、数值有效、点时可见分开。[票03 L17—22](issues/03-context-acquisition-receipts.md#L17) 包含“对来源家族保留真实响应、字段/单位/期次验证、接收完成与校验完成时间及声明关联”。[票13 L17—21](issues/13-remaining-p1-evidence.md#L17) 要求来源依据和可追溯矩阵，不能以旧来源标签代替认证。

票03的[逐路径迁移说明 L9—15](implementation-03.md#L9)明确列的是官方上下文refresh、文件导入、**source-history导入**、LPR导入/refresh等。它没有列出source-history smoke目录发现和下载已接通。这个遗漏不推翻已经通过的导入、TuShare、LPR和EIA回归；也不能继续用“03完成”推出所有source-history网络入口都有收据。

| 入口 | 已有代码行为 | 本次判定 |
|---|---|---|
| `ingest_official_context_document` | [official_context.py L239—276](../../src/pring_cycle/official_context.py#L239) 通过capture保存document_import原件、解析v4和实际验证；L346—369将receipt关联到声明 | 已接通，记录的是本次导入SYSTEM，不是原文件当年HTTP取得 |
| `refresh_official_context_document` | [L404—475](../../src/pring_cycle/official_context.py#L404) 请求前capture/on_started，HTTP响应先接收再身份/字段校验，失败attempt关联acquisition | 已接通；不是source_history下载当前实际调用的入口 |
| `refresh_source_history` | [source_history.py L210—271](../../src/pring_cycle/source_history.py#L210) 读取已有CAS并验hash，调用公开official/LPR ingest，每次导入使用当前时刻 | 已接通导入收据；不会给原来smoke目录/正文网络请求补历史received/validated。仍是写入入口，不是纯读取 |
| `ingest_lpr_document` / `refresh_lpr_release` | [official_lpr.py L211—246](../../src/pring_cycle/official_lpr.py#L211)、[L297—349](../../src/pring_cycle/official_lpr.py#L297) 均调用capture；两期限关联同原件 | 已接通；source_history的LPR下载自行urlopen，并未复用refresh |
| `smoke_source_history` discovery及正文 | 下述直接HTTP/CAS调用链，没有capture或acquisition身份 | 本次待修遗漏；不得以导入已修替代 |

## 逐路径缺口及具体触发

### 1. discovery：首个请求即可丢失HTTP错误正文

[CLI L181—195](../../src/pring_cycle/cli.py#L181) 的`source-history-smoke`调用公开 `smoke_source_history(paths, target_business_date, browser_capture_root)`。后者[source_history.py L73—74](../../src/pring_cycle/source_history.py#L73)先调用`_historical_records(target)`，在创建线程池或保存任何正文前，进入L282的`_discover_pbc_financial_reports`。

第一次真实目录地址由L349—355固定产生：`https://www.pbc.gov.cn/diaochatongjisi/116219/116225/11871-1.html`。`_fetch_anchors`在[L452—467](../../src/pring_cycle/source_history.py#L452)直接`urlopen`、读最多1,000,001字节、解析锚点；既不接受paths，也不登记收据/保存原件。`HTTPError`在L461直接逸出；其readable错误正文从未传给CAS。网络未收响应的错误也没有started/failed记录。即使返回200，目录原字节、received、validated和标准化锚点结果仍不持久。

PBC金融目录5页、OMO目录9页均走这个辅助函数（L349—377、L408—435），不是只遗漏某一个家族。请求计数在成功返回后才`+=1`；最终总数只有整个烟测成功后才返回，无法承担失败时的逐物理请求账本。

### 2. 正文HTTP/LPR及并发退出：局部CAS不等于收据

`_fetch_record`在[L295—340](../../src/pring_cycle/source_history.py#L295)中：LPR分支L324直接urlopen；其他正文L333调用`_fetch_official_context_document`这个**transport函数**，没有调用已接通收据的`refresh_official_context_document`。后者transport在[official_context.py L515—525](../../src/pring_cycle/official_context.py#L515)直接读取响应并返回字节/身份，不登记Acquisition。

主线程的`_smoke_document_from_fetched`（[L139—153](../../src/pring_cycle/source_history.py#L139)）先拒绝最终URL或HTTP状态不符，再调用store_artifact。所以必须精确区分：

- HTTPError/网络错误：future.result()在L99抛出，尚未调用保存正文，已收到的错误体丢失。
- 返回了正文但身份/状态不符：L145—146先拒绝，正文也没保存。
- 身份合格但业务解析失败、PUBLIC未知或晚于目标：L147已保存正文，因此不能笼统写成“任何失败都无原件”；但没有failed收据、实际received/validated、标准化身份以及本次请求可查询关联。
- 部分future失败时，线程池上下文会等待已提交工作结束；其他已经发出的请求不能因主循环提前退出而失去收据。当前原件落盘发生在主线程消费future之后，并非每个请求接收时；某些已成功返回但未被消费的正文也可能没有保存。接受条件应覆盖所有实际已发请求，而不是要求本批重写并发调度。

`_FetchedRecord`（L33—39）只有record/content/MIME/final_url/status；烟测结果（L198—207）只有raw hash/期次/家族/release/public/URL，没有acquisition_id、normalized hash或逐次接收/验证时刻。`datetime.now(UTC)`在L161/173只是解析当下的参数，不能视作网络接收时刻。

### 3. owner：区分独立烟测与已有运行上下文

独立CLI烟测没有parent_run参数，当前也不由Worker调用。**独立烟测owner为空本来合法**；本修复不应虚构run或要求先创建模型/Worker任务。应有的是独立acquisition身份、用途（目录发现/历史正文/浏览器导入）及目标/期次参数。

若调用方处于既有 `own_acquisitions` 作用域，则共享仓库已经提供正确机制：[acquisition.py L38—52](../../src/pring_cycle/acquisition.py#L38)保存ContextVar owner，capture在L142—171于请求前事务内写`full_run_acquisition`，L175—205检查取消/终态。在当前未调用capture的smoke路径中，这套机制完全不会运行。

修复还须保留线程边界：正文下载使用 `ThreadPoolExecutor.submit`（source_history L83—108），当前没有显式owner/上下文传递。不能只在主线程建立own_acquisitions，就把后续工作线程的归属称为已证明；应显式传递适用owner或上下文，并由公开行为断言确认。无需新建归属表、给无归属烟测伪造run，或改变已有Worker检索策略。

### 4. browser_capture_root：保留其真实输入类型

该选项在L301—317读取既有capture文件；[L438—449](../../src/pring_cycle/source_history.py#L438)从`### Result`包装中取HTML字符串再编码，不是原HTTP响应字节。返回的status200和MIME是本地包装，不证明原网络响应。最窄修复应把它标为本次本地capture/document import，保存可核对的输入及其转换关系、真实本次导入时间；不计新HTTP、不造旧received/validated，不把DOM导出重新标为原始HTTP。此次不扩展到重做浏览器采集能力或历史PUBLIC认证。

## 最窄公开TDD入口

第一个建议用例可命名 `test_source_history_smoke_retains_first_discovery_http_error`，在隔离运行目录初始化既有schema，调用**公开** `smoke_source_history(paths, target_business_date="2026-08-28")`。只替换实际外部HTTP边界 `source_history.urlopen`（或修复后其公开transport依赖），传输替身接收到`Request`即检查上面的首个官方目录URL，并抛标准库 `HTTPError(url, 503, ..., headers, BytesIO(b"official-history-fixture-error"))`。不mock `_historical_records`、`_discover_*`、`_fetch_anchors`、解析器、coverage、store_artifact或AcquisitionRepository。

预期：公开入口仍向调用方报告源失败；实际外部尝试1次，后续目录/正文0次；通过 `AcquisitionRepository.history()`读取1条failed请求，参数含精确目录URL及本次目标/用途，started不晚于received、received非空、validated/normalized为空；`read_content(id, "raw")`与错误体逐字节相同，hash可复核；无来源声明/认证/候选/报告创建。独立调用无owner合法。**固定基点源码会返回空history；根代理随后实际执行的公开RED已证实期望1条、实际0条，1 failed in 1.81s。** 已读取其[失败日志](verification-history-discovery-red.txt)：用例为 `test_history_discovery_http_error_retains_failed_response`，仅替换HTTP边界、保留真实内部发现链。本研究只是读取完成日志，没有执行测试；该日志可能在根代理finalize时统一编码，本文不以其临时字节作为固定源码指纹。

同一公开入口可以逐个扩展以下有区分力的接受例，不需要完整270篇成功集：

| 用例 | 只控制外部响应/时钟 | 用户可观察接受条件 |
|---|---|---|
| 首目录200、次目录HTTPError | 第一页给真实形状HTML锚点，第二页给错误体；内部目录解析/链接验证照常运行 | 前一成功目录raw与normalized可读，started≤received≤validated；后一failed保留raw、无validated；共2次请求，无正文请求；不能因最终烟测失败丢掉第一条 |
| 首目录响应未到达 | transport抛URLError/超时，不假造body | 有started和failed；received/raw/validated保持空，不保存伪空HTTP响应或默认时间 |
| 返回正文后身份/解析失败 | 返回可读body及错误最终URL/状态，或真实字段非法目录；不替换内部校验 | 先保留收到的有界原件，再记录failed；校验失败不产生“验证成功”时刻和标准化成功制品 |
| 正文并发失败 | 14个真实目录请求可由空锚点HTML响应完成，后续固定正文列表照常产生；让首批至多8个正文HTTPError，完整执行真实discovery及线程池 | 不跑全270篇；所有实际发出的请求各留收据/错误原件，失败退出不遗失已开始的兄弟请求；原始与标准化职责不混淆 |
| 有owner的首目录失败 | 经 `RunRepository.submit_manual_full` 创建隔离合法待运行任务，进入公开 `own_acquisitions` 后调用smoke；仅mockHTTP/时钟 | HTTP替身执行时，公开run audit已能读到该started请求；失败后同一run/target/phase归属及raw保留。不可用手写SQL假owner来让测试通过 |
| 有owner的正文并发失败 | 与上一行相同owner，经过真实14页discovery后进入正文线程 | 每个已发正文请求仍属于原run，显式验证线程边界；不能只检查目录成功有owner就认整个路径通过 |
| 时钟分离 | 使用明确递增的实际请求/接收/验证时钟；原页release文本独立 | 目录/正文各自真实时间，不借统计期、目标日或最后汇总时钟倒填；失败不得有validated；不在本修复修改PUBLIC政策 |

“第一张目录缺业务锚点”不应人为当作数值0或来源声明；若目录解析成功但最终coverage不足，应保持请求层事实与整体coverage结果分开。所有测试的运行继续限定Ubuntu-22.04/tywin、`env -u PYTHONPATH`、指定noneditable dev-venv；本研究没有生成测试代码或执行Windows应用。

## 现有测试真正覆盖到哪里

- [tests/adapters/test_source_history.py L10—40](../../tests/adapters/test_source_history.py#L10)实际上调用的是 `ingest_official_context_document`，验证日期精度下次日PUBLIC；没有调用smoke/discovery/download。文件名不能充当历史HTTP已覆盖的证据。
- [test_official_context.py L275—297](../../tests/adapters/test_official_context.py#L275)的官方单篇smoke只检查结果字段、hash和计数，不检查持久收据；L300—338测的是已接通的refresh失败attempt，与source_history旁路不同。
- [test_context_acquisition_receipts.py L97—129](../../tests/integration/test_context_acquisition_receipts.py#L97)、[L448—530](../../tests/integration/test_context_acquisition_receipts.py#L448)覆盖官方导入、TuShare多维原件及非法值failed收据；[L622—666](../../tests/integration/test_context_acquisition_receipts.py#L622)覆盖官方/LPR刷新超限前缀保存，可复用其外部HTTP替身和真实仓库断言方式。
- [test_full_run_retrieval.py L669—711](../../tests/integration/test_full_run_retrieval.py#L669)验证公开任务→Worker直连请求在HTTP前已有归属及run audit可读；它提供owner行为先例，没有测试历史smoke的线程传播。
- [test_source_certification.py L68—96](../../tests/models/test_source_certification.py#L68)检查历史身份/跨域链接辅助函数，未证明逐请求原件或失败收据。对tests目录搜索公开smoke/refresh调用，本次未发现source_history抓取收据回归。

## 本批接受条件与明确不做

最小产品结果是：历史烟测实际发出的目录/正文请求，以及本地capture导入，均可查询本次真实收据和可读原件；只有请求目的对应的身份/结构/字段验证通过才写validated/normalized。失败保留已知时间和收到的字节，无响应则不造received；有真实run作用域则保留归属，独立调用无owner；多家族共享同一物理正文的关系可追溯，不能为每个family虚增网络请求。

优先复用已交付 `AcquisitionRepository.capture` 的HTTPError留体、实际时钟、owner、CAS及状态能力，不另建历史专用时间/原件协议。内部辅助函数可为传递paths/上下文调整，但测试仍从公开smoke进入。先证明一请求RED/GREEN，再补真实发现/并发边界；无需为第一反例抓270篇，也不得mock内部覆盖检查制造成功烟测。

本批不重新定义历史PUBLIC、官方可靠时间、发布日历或认证生效；不修改旧声明/旧准备包/历史smoke，不用新收据倒填旧原件当年取得；不创建新目录、认证或模型，不自动给smoke加Worker调度。单篇official/LPR smoke等相邻入口若另有收据问题，单独审范围，不借本次source_history发现全局扩改。既有URL/来源校验必须保留；若底层会自动重定向，不能未经核验把多跳HTTP称为一物理请求，本批也不能用放宽来源校验来完成收据。

## 输入指纹

以下16项均取自 `a569fd757c7d19a4ae95b980bd2b1c0c51cba973` 的Git原始blob字节，使用 `git show <commit>:<repo-relative-path>` 直接复核，**不是已开始修复的当前工作树文件**，也不作换行标准化。表中路径以本文目录为基准，展开至仓库相对路径即可复核。本文链接检查存在，行号对应固定Git版本；原件、应用源码和既有测试均未改写。首目录RED已由根代理完成，修复及其余下载/owner接受条件继续分别验证，本文不签署GREEN或整体完成。

| 输入 | Git blob字节 | SHA256 |
|---|---:|---|
| `spec.md` | 27762 | `f5c32c407f216841b2afed0aaab3863868bdc394d9057207d25dbc9e9a561cc4` |
| `issues/03-context-acquisition-receipts.md` | 2792 | `5903d8bf460fd53a694cf5929c9a819fc8373134eb6891829ed20fb4fd3fe755` |
| `issues/13-remaining-p1-evidence.md` | 8104 | `c87d9e0e7526b91d9ee788b5d15d33d7c6475aaf92cc8a4b5c7ce45cb7e74fbf` |
| `implementation-03.md` | 6708 | `fc77b6c494f26d59496050c8923e6f31edd78b108781b0daf77a39bcc7d9cec1` |
| `../../src/pring_cycle/source_history.py` | 26596 | `393420b63609d8dc12e63da21c3373fdd430c2d07304d4dfd34787d559577f2e` |
| `../../src/pring_cycle/official_context.py` | 80084 | `b1cb854a431e0b5f488d2b1330177785713e28806a99f6a0e880c798a1203aaa` |
| `../../src/pring_cycle/official_lpr.py` | 15707 | `2173c4ea5d3c16acd26fb58c9a9a04ae79e5519403be93bf8b46a94f22f290d1` |
| `../../src/pring_cycle/acquisition.py` | 14086 | `eee45f82bf5a6d058dfc781ad0f5908914d09bf3992161319c8dcb98b24f7b58` |
| `../../src/pring_cycle/cli.py` | 37479 | `bcedbfaf97d2710f22c231919e22f57e443787823e7a17c7a153d11f5a1573c3` |
| `../../src/pring_cycle/tushare_context.py` | 68390 | `e48f670b8f25b596cb4612cfb6e1f587727d59cf98747e9ceacc80c6fa6cb2bd` |
| `../../src/pring_cycle/full_retrieval.py` | 26197 | `d82a803a0b9e0bfad3498c2e11685585f980744ca8c655f30f0398d630a04969` |
| `../../tests/adapters/test_source_history.py` | 1803 | `e2e3140226107c924be63fe15f0f3d5c89048c7f46b445ab9b2788791fe9d0cc` |
| `../../tests/adapters/test_official_context.py` | 39818 | `5eac49a556f07f0e3dbf7903a52b484a1f271ba16c48054f6e0b6e6f77e434d2` |
| `../../tests/integration/test_context_acquisition_receipts.py` | 30323 | `1f21eba65dd2888deb0ab08fd49ec80b7d94c5e531bec4764fcf0289d13d9639` |
| `../../tests/integration/test_full_run_retrieval.py` | 53672 | `938d006a4d2cd0947a6bc01864fcebc9381d7351998d044506d538717c3d894f` |
| `../../tests/models/test_source_certification.py` | 3064 | `6f8ee530760cfe86708ced90030d6204c2e3039fb930e17ed6ae7c41ce86f92e` |

Git原文指纹复核时刻：`2026-09-07T18:36:01.009001+00:00`。本研究应用执行0、网络0、数据库读写0。报告自身SHA/字节及链接数在交付消息给出。
