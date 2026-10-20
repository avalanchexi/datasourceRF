# A18 首次导入两项异常的证据边界

研究日期：2026-09-09，Asia/Shanghai。仅新增本文；读取实际交付、当前绑定源码、隔离库与 CAS。未调用应用/parser、测试、网络，也未修改旧交付、数据库或生产。本次数据库访问通过 WSL Python 标准库 `sqlite3` 的 `mode=ro` 完成。

**index 22 已定位到“规范化制品保存后、validated 时间写入前”的时钟检查失败；规范化对象实际存在，只是未挂到失败收据，也未导出。index 223 的获取收据已 validated，两项数据及原件/规范化字节可独立复核；最符合现有证据的原因是 driver 后置 UTC 上界检查遇到时钟回拨，但当次上界采样和 traceback 未保存，不能把这一推断写成已记录的确切失败行。** [实际回执](evidence-a18-import-20260909/receipts.json)、[已有交付验收](evidence-a18-import-20260909/delivery-verification.json)、[driver 后置断言](verification-catalog/import_a18_originals.py#L147)、[规范化与时间检查](../../src/pring_cycle/acquisition.py#L216)。

## 绑定材料和本次复核范围

原 driver SHA256 `9195385ea3abe6d889353c3db240b0a3153d8fd1d1f33268aac47acf012635a5` 与 started/terminal 两份记录一致。回执文件仍为 **433,467 字节**，SHA256 `199e384c879ebbb7a7fc19278529e89492dc8deecb075be990abd56afffc3b6c`。本次核对 `progress.jsonl` 的全部 268 条对象与回执列表逐项相等，并对两项异常及紧随其后的 index 23/224 数据库行逐字段核对。[started](evidence-a18-import-20260909/started.json)、[progress](evidence-a18-import-20260909/progress.jsonl)、[driver](verification-catalog/import_a18_originals.py)。

只读数据库严格限定为：

`/home/tywin/.cache/pring-cycle/verification/a18-document-import-20260909/data/pring-cycle.sqlite3`

CAS 严格限定为同一运行根的 `data/artifacts/sha256/`。查询入口为 `sqlite3.connect(Path(database).as_uri() + '?mode=ro', uri=True)`；只执行 `SELECT`，不升级数据库、不调用初始化。核对结果：268 条 acquisition_request，518 条 artifact；source_claim、source_claim_acquisition、registered_metric_catalog、model_version、active_model、model_activation、model_acceptance、model_replay、parent_run 均为 0。这是本次只读查询结果，不是依据字段名推测没有模型写入。

## index 22：贷款 2024-08 的确切失败阶段

| 事实 | 实际记录 |
|---|---|
| 调用身份 | `pbc_loan_structure / 2024-08`，`preparation_result_index=22` |
| acquisition_id | `acquisition-88434090b13544f58601a9fd5b7b18ad` |
| started_at | `2026-09-09T07:47:35.405799+00:00` |
| received_at | `2026-09-09T07:47:35.439637+00:00` |
| 终态 | `failed`，`ValueError: acquisition_time_invalid`；validated_at、receipt.normalized_hash 均为 null |
| 原件 | 38,553 字节，SHA256 `6a73b31453129d53f6aedaa6fc11c78e856904665fa7f275367a9530d0ce30f8`；旧交付和隔离 CAS 实物一致 |
| 已保存但未挂接的规范化对象 | 4,502 字节，SHA256 `a64d0b6d5ddf6dc80ceeee9654287def4eea5d0002b44ca88561910a362116ff`；隔离 CAS 实物存在，旧交付目录中没有这个文件 |

来源：[旧回执](evidence-a18-import-20260909/receipts.json)、[原件](evidence-a18-import-20260909/6a73b31453129d53f6aedaa6fc11c78e856904665fa7f275367a9530d0ce30f8)、[隔离库规范化实物](//wsl.localhost/Ubuntu-22.04/home/tywin/.cache/pring-cycle/verification/a18-document-import-20260909/data/artifacts/sha256/a6/a64d0b6d5ddf6dc80ceeee9654287def4eea5d0002b44ca88561910a362116ff)。

以 `artifact_reference.source_reference` 精确查询得到：

| source_reference | content_hash | byte_count | artifact.created_at |
|---|---|---:|---|
| `acquisition-88434090b13544f58601a9fd5b7b18ad:raw` | `6a73b31453129d53f6aedaa6fc11c78e856904665fa7f275367a9530d0ce30f8` | 38553 | `2026-09-09T07:47:35.468638+00:00` |
| `acquisition-88434090b13544f58601a9fd5b7b18ad:normalized` | `a64d0b6d5ddf6dc80ceeee9654287def4eea5d0002b44ca88561910a362116ff` | 4502 | `2026-09-09T07:47:35.519776+00:00` |

两项源引用都关联实际 artifact 行及重新核过 SHA/字节的 CAS 文件。规范化 JSON 保留完整发布身份及 9 个贷款成员；剥离原准备的 5 个研究注解、只统一 release/public 时间表达后，全部发布字段及 9 个标量字段与原准备 index 22 相同；按原规范化参数重编码也逐字节相同。**这是已存规范化对象的只读比较，不是本次重新运行 parser。** [准备包](evidence-13-preparation-v2/preparation.json)、[研究注解边界](a18-document-import-readiness.md#L70)。

精确定位来自以下控制流及持久证据：

1. `_check_time(started_at)` 在请求创建前执行。现在有请求、received_at 和原件，可排除开始时刻检查失败。
2. `_receive` 在写 received_at/原件前检查 received_at >= started_at。现在原件和接收时间已存在且二者顺序正确，可排除接收阶段的时间检查失败。
3. capture 随后调用 parse，成功返回后才进入 `complete_validation(normalize(value))`。已经存在以本 acquisition_id 命名的完整规范化 artifact_reference，证明这次运行已经越过解析与规范化序列化阶段。
4. `complete_validation` 先 `store_artifact(...:normalized)`，再采 `validated_at = clock()`，随后在 **acquisition.py:242** 调用 `_check_time(validated_at, receipt.received_at)`，通过后才更新收据的 normalized_hash、validated_at、state。现在恰好呈现“规范化制品已注册，但这些收据字段未写入”的状态，且错误字符串由 `_check_time` 发出。

代码依据：[capture 顺序](../../src/pring_cycle/acquisition.py#L142)、[接收检查](../../src/pring_cycle/acquisition.py#L259)、[完成校验](../../src/pring_cycle/acquisition.py#L216)、[错误来源](../../src/pring_cycle/acquisition.py#L328)。因此失败阶段可以确定为完成校验中的时钟检查，不能归类为贷款原文字段解析失败或规范化制品不存在。

默认 clock 是 `datetime.now(UTC)`，产生有时区的 datetime；本 driver 未替换它。结合上述唯一路径，失败条件是该次采到的 validated 候选时刻早于 received_at。**被拒绝的具体 clock 值没有持久化，因此其具体倒退幅度不可恢复。** artifact.created_at 来自另一处 `datetime.now(UTC)`，不能代填被拒绝的 validated_at。[默认 clock](../../src/pring_cycle/acquisition.py#L20)、[制品登记时钟](../../src/pring_cycle/artifacts.py#L62)。

`receipt.normalized_hash=null` 与“已有未挂接 normalized 制品”必须同时保留。获取仓库的公开 `read_content(id, 'normalized')` 只沿收据 hash 读取，此处仍会报 unavailable；`parse_official_acquisition` 也拒绝 failed 收据。不能把 artifact_reference 中找到的 hash 补写进旧收据，或据此把旧失败改成成功。[公开读取](../../src/pring_cycle/acquisition.py#L303)、[公开重建入口](../../src/pring_cycle/official_context.py#L259)、[终态不可变](../../src/pring_cycle/acquisition.py#L392)。

## index 223：OMO 2026-07-01 的后置断言逐项排除

| 事实 | 实际记录 |
|---|---|
| acquisition_id | `acquisition-9b050ab4e654489ca1f7418650703573` |
| started_at | `2026-09-09T07:48:06.942310+00:00` |
| received_at | `2026-09-09T07:48:06.957425+00:00` |
| validated_at | `2026-09-09T07:48:07.052583+00:00` |
| 数据库获取终态 | `validated`，error_type 为 null |
| driver 结果 | `failed`，`AssertionError`，error 为空字符串；无 traceback/断言标签 |
| raw | 30,790 字节，SHA256 `4a210c639102924ca1540b542cf7b042bb4429b23bb046c196971d827c0c6910` |
| normalized | 1,173 字节，SHA256 `38f7b59e290f92d04e44931fd513e3cbc88f47f2203589d76d2c868f9e58219d` |

来源：[旧回执](evidence-a18-import-20260909/receipts.json)、[OMO 原件](evidence-a18-import-20260909/4a210c639102924ca1540b542cf7b042bb4429b23bb046c196971d827c0c6910)、[OMO 完整规范对象](evidence-a18-import-20260909/38f7b59e290f92d04e44931fd513e3cbc88f47f2203589d76d2c868f9e58219d)。本次直接核对数据库行、两项 artifact_reference、CAS 与导出副本；SHA、字节及内容全部一致。

规范对象两项值为 7 天期利率 **1.4%**、投放 **1000 亿元**，所有 8 个发布字段、每项 13 个标量字段与原准备对应结果相同。HTML 的利率字符被标签拆成 `1.`、`40`、`%`，金额为 `1000`、`亿元`；本次只读 HTMLParser 文本检查与已存标量一致，不将版式分片视为额外数值或再一次网络样本。页头候选为 2026-07-01 09:20:30，仍不是历史首发版本认证。[原件](evidence-a18-import-20260909/4a210c639102924ca1540b542cf7b042bb4429b23bb046c196971d827c0c6910)、[规范对象](evidence-a18-import-20260909/38f7b59e290f92d04e44931fd513e3cbc88f47f2203589d76d2c868f9e58219d)。

| 可能位置 | 本次能够核实的事实 | 可排除程度/仍有限制 |
|---|---|---|
| parse 回调 L119：received_at 非空；L120：raw 长度/SHA | 获取最终为 validated；在相同 capture 中，任一回调断言失败会进入 fail_validation。raw 的当前长度/SHA 也匹配 | 可排除这两个前置断言是这次 driver 失败来源；它们若失败不会留下该 validated 终态 |
| 后置 L151：重建对象与 acquired.value 一致 | 已存完整 normalized 对象规范重编码 SHA 相同，全部字段与原准备相同。公开重建器只有重建规范 hash 等于 receipt.normalized_hash 才返回 | 没有字段差异证据；正常控制流下两对象受同一规范快照约束。原内存对象和逐行执行轨迹未单独保存，本研究不调用 parser；主线的公开重建复核才是新增执行证据 |
| 后置 L152：receipt.raw_hash == 原件 SHA | 数据库、旧回执、固定准备原件及两份原件实物 SHA 一致 | 此项保存值可完整重验且通过；未发现能解释 AssertionError 的持久不一致 |
| 后置 L153：received_at/validated_at 非空 | 两项时间在数据库与回执中精确一致、均非空 | 保存值可完整重验且通过 |
| 后置 L154 的前三项：started <= received <= validated | 三个已存 UTC 时刻满足顺序 | 保存值可完整重验且通过；不能把整条 chained assert 统称为已复验通过 |
| 后置 L154 最后一项：validated <= utc_now() | **当次 utc_now() 未存**。当前时间或批次 completed_at 均不是那次采样 | 不能重验原断言。后续串行回执已有低于该 validated_at 的 UTC，支持此项因回拨失败；精确失败行仍是推断 |
| L155/L156：导出后 hash 相等；export 内 L76：既有文件字节相等 | 两个导出文件和 CAS 当前逐字节一致。此前 index 0—222 没有引用这两个导出文件名；异常处理自身又按相同 export 函数导出了两件且正常返回，后续循环继续 | 当前可重验内容全部通过。原目录变更的逐步日志未存，不能以今天文件存在证明首次 export 曾通过；没有持续制品损坏证据 |
| L162 的 `matches` | 完整规范字段与原准备相同；源码这里只赋 bool，然后选择 `captured`/`captured_with_parser_difference` | 此处没有 assert，不会自行抛本次 AssertionError；错误不是把准备差异状态误记为 AssertionError |

定位依据：[driver 回调/后置/异常分支](verification-catalog/import_a18_originals.py#L114)、[export](verification-catalog/import_a18_originals.py#L72)、[公开重建的 SHA 合同](../../src/pring_cycle/official_context.py#L259)、[capture 失败转移](../../src/pring_cycle/acquisition.py#L194)。异常分支只保存 `type(error).__name__` 和 `str(error)`，没有 traceback，也没有为每个断言保存操作标签或上界时钟。这是无法唯一恢复 index 223 历史失败行的实际证据限制。

## 已保存数据确实显示 UTC 非单调，但不能推定系统根因

本 driver 按列表串行执行、写完本项 progress 后再启动下一项。紧随异常之后的数据库行与 progress 已独立核对一致：

| 已先发生的采样 | 串行后续采样 | 后采样减前采样 |
|---|---|---:|
| index22 received：`07:47:35.439637Z` | index23 started：`07:47:34.576799Z` | **−0.862838 秒** |
| index223 validated：`07:48:07.052583Z` | index224 started：`07:48:06.128943Z` | **−0.923640 秒** |

这些是确有先后顺序的已存 UTC 采样，证明本批记录的 wall-clock 不是单调递增。它们不是 index22 被拒绝的 validated 候选值，也不是 index223 后置 assert 的 utc_now 值；两者不得混填。仅靠这些记录无法确定是宿主时钟校正、WSL 时间同步、虚拟时钟或其他机制导致，也不能从约 0.9 秒的差值声称每次恰好回拨 1 秒。[串行循环](verification-catalog/import_a18_originals.py#L241)、[progress](evidence-a18-import-20260909/progress.jsonl)、[默认 UTC 采样](../../src/pring_cycle/acquisition.py#L20)。

## 最小真实恢复及验收建议

1. **index22：追加一次真实贷款原件获取。** 使用全新 acquisition_id 和实际当前 UTC，在专属新隔离运行/交付中按相同原件、家族、期次走公开 capture；保留旧 failed 回执及其未挂接规范化制品。新增回执必须真实 validated、公开 read_content 与 parse_official_acquisition 可重建，并对 9 个完整标量字段、原件 SHA 与准备包复核。不能调用 complete_validation 修改旧终态，也不能以旧 orphan normalized 的存在替代新成功回执。
2. **index223：公开只读重建并单独出具当前复核。** 使用原 validated 回执和实际原件调用公开重建入口，核对规范 SHA、两个完整值、三个持久时刻顺序。此次复核另记实际开始/完成时刻，保持旧 driver `failed` 记录。它解决“当前原获取制品能否通过公开重建”，不宣称恢复当次未保存的 post-check 采样。
3. **新恢复脚本记录具体检查名及真实 clock 采样。** 不再把新的 `utc_now()` 内联在没有标签的复合 assert 里；若需要比较就先保存该次实际采样。发生时钟倒退仍明确失败并保留实际采样，不用 `max(received_at, now)`、旧发布日期或合成时刻使记录通过。monotonic 时钟可辅助诊断耗时，但不能替换证据时间戳。
4. **验收按真实尝试和逻辑覆盖分别计数。** 如果只有上述 1 次贷款新增 capture 且成功，那么总获取尝试是旧 268 + 新 1 = **269**；268 个不同三元身份的完成证据可由旧 266 完整结果 + 1 个 OMO 新复核 + 1 个贷款新成功组成。旧失败数仍保留，不能把旧包改写为 268 首次全成功或把 OMO 复核计作新网络获取。这个计数是验收期望，本文未执行恢复，不预报通过。

恢复后继续核对原准备、原回执及旧 progress 字节不变，确认源声明/关联、registered catalog、模型/激活仍为 0；Q1 源映射 pending 仍为 1，历史 SYSTEM 恢复、历史 PUBLIC 认证、正式来源认证与模型采用均不能因此置为 true。[规格的原件与时钟条款](spec.md#L93)、[原导入边界](a18-document-import-readiness.md)。

旧交付的 **517 个导出制品、1849 个已匹配标量字段** 有其明确范围：验收器跳过 index22 收据未挂接的规范化对象。本研究发现隔离库第 518 个 artifact 并核对其 9 格，不原地修改那份历史验收结果，也不把它升级成第 268 个 validated 收据。[旧验收脚本](verification-catalog/verify_a18_import.py#L255)、[旧验收结果](evidence-a18-import-20260909/delivery-verification.json)。

## 输入指纹和方法边界

| 输入 | 字节 | SHA256 |
|---|---:|---|
| [原 driver](verification-catalog/import_a18_originals.py) | 11871 | `9195385ea3abe6d889353c3db240b0a3153d8fd1d1f33268aac47acf012635a5` |
| [原验收器](verification-catalog/verify_a18_import.py) | 15477 | `94637f031206614fb3b27e1c8cbe483921f6dbc76bd44ea75f71c96f7ac2f5ab` |
| [started](evidence-a18-import-20260909/started.json) | 851 | `a2bad1e4366a7ff13259e528b659da40ad800b7a8b32282e30e3db3ded0f1db7` |
| [receipts](evidence-a18-import-20260909/receipts.json) | 433467 | `199e384c879ebbb7a7fc19278529e89492dc8deecb075be990abd56afffc3b6c` |
| [progress](evidence-a18-import-20260909/progress.jsonl) | 366486 | `b5d583d1da9c465f2aa63a9973ddfb5a9f3113874ef60ec09c2490044e4c99d3` |
| [delivery verification](evidence-a18-import-20260909/delivery-verification.json) | 1934 | `3d56fbc2e2094249355a63b70ab03dec1d8032d47505fde2cfb945577965fb48` |
| [acquisition.py](../../src/pring_cycle/acquisition.py) | 14584 | `ed81eef2b153417009c0beb356be64bbe8fd164a9f3ea0d6eafe9cdc66ad69f8` |
| [official_context.py](../../src/pring_cycle/official_context.py) | 84300 | `fb0a54664e8582a2c00ee00b790a7d4d9cb6cda162c69e6dfc3f077bf9f56b11` |
| [artifacts.py](../../src/pring_cycle/artifacts.py) | 3022 | `114427470f2c3f8140eb22d214465620e99a1b2a7baa8c3c1717b8ba4e750ea4` |

四个涉事原件/规范化实物的精确 SHA 和字节已在两项异常表内列明；其中 index22 未挂接 normalized 的事实来自只读 `artifact_reference JOIN artifact` 及 CAS 重哈希。研究最初尝试 Windows SQLite URI 时分别得到 invalid URI authority 和 database is locked，随后改用 WSL 原生 `mode=ro` 查询成功；这两项研究访问错误与先前业务导入异常无关，没有被计为新获取失败或用于解释原失败原因。
