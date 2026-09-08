# 标准化制品在消费时的完整性边界

2026-09-09，上下文快照批的关联测试运行期间只读定位。以下是待执行的公开反例，不是已确认生产缺陷，也不关闭票02或票19。

## 现有证据

票02要求一次采集后可从声明读回实际响应、标准化结果与时间，哈希必须对应可读内容。`AcquisitionRepository.read_content`对raw和normalized都能按各自hash读取并校验，但是否实际检查取决于消费者。

- `EvidenceRepository.source_claim_originals_many`批量读取声明的确切获取关联，要求validated并核raw内容；目前不读取normalized。
- `CoreInputValidator`使用上述原件集合重新解析核心价格，与声明日期/值对应，因此已证明的raw丢失/损坏防护继续成立。这还不能证明normalized丢失/损坏会使新目录声明失去完整可追溯资格。
- `EvidenceRepository.source_claim_publication`则同时核raw和normalized，并将标准化文档与原件重解析比较。但全源码调用链只把它接到新目录RRR完整公告选择，不能据此称LPR或常规官方宏观已经覆盖。该RRR分支不能因核心的静态疑点重新列为未实现。

## 下一可执行反例

复用 `tests/models/test_candidate_admission.py` 已登记核心来源与消费原件用例，先通过真实采集/选择/历史评价入口建立可用数据。在独立fixture的确切获取收据中，仅损坏其normalized内容（raw、声明和关联保持），再由相同公开消费入口检查是否仍被当成完整证据。必须另外保留尚未在目标PUBLIC时点可见的版本，避免未来坏制品误伤早期有效版本。

若反例确认，再沿实际消费链修复，并测试同一声明多次取得的一个坏关联、旧历史记录未知状态，以及Worker共享路径。不能仅验证`read_content`自己会报错，因为它已有这个能力；关键是实际模型消费者是否调用并兑现完整性要求。

这不改变来源认证、历史公开时间或业务规则，不将原件与声明数值已经一致的事实改写为“数值错误”。暂未运行本反例，正式来源与完整120日验收仍依原前置。

[五类消费者源码映射](normalized-consumption-source-map.md)补齐核心、LPR、常规宏观/RRR、银行间和仓单的实际调用路径。根代理核对文件hash、28个本地链接及关键调用点，均为静态证据，不增加测试通过或认证计数。
