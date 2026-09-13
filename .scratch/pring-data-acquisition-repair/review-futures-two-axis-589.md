# 票11两轴复审589

根线程已全文读取两报告并核SHA；固定589快照，不代表后续代码验收。

## Standards

# 票 11 Standards 复审（589）

固定 HEAD：`5e186f740be3d275cba5664a13ef0290e6a57916`；commit list：空。
授权 WIP 比较命令：`cat .scratch/pring-data-acquisition-repair/futures-review-589/changes.patch`。
已核 [manifest](futures-review-589/manifest.json)：三文件快照 SHA-256 全部匹配；补丁 SHA-256 为 `05c26c29b1c59cdc8aa5fd699290b88698f7c418724282dc9bba9ea0d5374e94`。范围仅为新 `futures_inputs.py`、新 `test_futures_inputs.py`、TuShare 新增方法与结果类型导入；538 前 WIP 排除。

硬规范违规：**未发现**。依据 AGENTS.md、docs/agents/domain.md、CONTEXT.md、ADR 0004/0006/0012/0013、docs/development/local-runtime.md 与 spec.md Testing Decisions；沿用已授权的公开 adapter → 真实 AcquisitionRepository/raw/CAS → 公开输入查询边界。工具覆盖的格式、导入与类型事项不列入人工发现。

判断性 smell：**1 项，P3，非阻断**。

- **Possible Duplicated Code**：冻结 `test_futures_inputs.py` 的 148–155、177–184、222–229、395–402、461–468、508–515、641–648、832–839、1086–1093 行重复同一响应变更形状，例如 `document = json.loads(raw)` → `column = document["data"]["fields"].index(field)` → `document["data"]["items"][0][column] = value` → `return json.dumps(document).encode()`。今后维护响应形状时容易分散修改；可考虑一个仅服务本文件的单字段响应变更辅助函数，保留各例明确的业务输入与独立期望值。这是维护性判断，不违反 Testing Decisions，也不要求本阶段预重构。

565 所述 publication/session 的重复校验已消除：冻结 `futures_inputs.py:143` 定义 `_validate_publication`，两条路径在 218、234 行复用。TuShare 委托方法符合 ADR 0004 的明确适配接缝，不按 Middle Man 报告。其余 smell 基线未见值得报告的问题。

本次只读静态复审；未运行测试、安装依赖、联网或修改源码、测试、冻结输入；未读取另一轴报告。

结论：Standards 硬违规 0，判断性 smell 1；最严重项为非阻断 P3 测试准备逻辑重复。

## Spec

# Spec 复审：票11 / 589

固定 HEAD：`5e186f740be3d275cba5664a13ef0290e6a57916`；commits：`[]`。比较命令：`cat .scratch/pring-data-acquisition-repair/futures-review-589/changes.patch`。三快照及补丁 SHA256 均与 [manifest](futures-review-589/manifest.json) 一致；补丁为 `05c26c29b1c59cdc8aa5fd699290b88698f7c418724282dc9bba9ea0d5374e94`。仅审新增输入模块、测试及适配器方法/返回类型导入；不含538前WIP。依据 AGENTS、CONTEXT、规格、业务决定和 ADR0006/0012/0013，只读静态审查，未运行测试或查看 Standards 报告。

(a) 遗漏/部分实现：**P1 — 缺少对既有采集原件追加已审时间的公开路径。** [票11:25](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/issues/11-futures-contract-evidence.md:25)要求“经公开采集和输入查询……事件发布时间和原件关联”；[规格:130](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/spec.md:130)要求“公开时间必须有可靠依据”。冻结 [futures_inputs.py:449](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/futures-review-589/futures_inputs.py:449)先读已审包，再于463–501请求新响应；[258–276](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/futures-review-589/futures_inputs.py:258)却只用本批新收据的 API、参数和完整 raw_hash 绑定证明。先采集→审查→再次调用默认网络采集时，只要响应请求标识变化，已审原件便永远无法匹配，PUBLIC继续缺值；拒绝将旧证明绑定到新原件是正确控制，软件缺口在于旧收据没有后审追加入口。

这不是缺官方认证材料：已核哈希的真实 [204 SHFE原响应:1](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/futures-metadata-204/1dea9648626d0de399b767a7be4acce5af12b15dddb50011df32d613c9970cc9.json:1)含 `request_id=0a21f513-7b15-4bb8-b6c8-6848971f9d68`，[DCE原响应:1](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/futures-metadata-204/a9998e8f69aafc8211f0979507e34d358357a5e295dfabf433a35f4c376b310d.json:1)为另一请求标识。冻结[合成transport:18](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/futures-review-589/test_futures_inputs.py:18)省略该字段并重复返回稳定字节，未覆盖此路径。应以既存收据/原件追加新的已审输入版本，保留旧标准化内容和SYSTEM历史。此结论来自静态可达路径。后续须先保存重采仍缺PUBLIC的绿色控制，再以新增后审入口取得“能力缺失”RED；不把正确哈希拒配称为算法错误，未宣称已复现。

(b) 越界：未发现。(c) 其他看似实现却错误：未发现足够确定的新问题。同PUBLIC冲突、到期区间缺件及采用原件校验在589已有处理。仅日期保守PUBLIC晚于审查/接收并非错误；未来实际发布时间的一致性未作为确定缺陷列入。

共1项软件发现。真实PP发布方样本、历史PUBLIC及许可认证仍缺，本票保持blocked；12仍负责实际选约、篮子及注册合同，本报告不把这些未完成事项计为票11软件bug。

Standards：硬违规0、判断性P3建议1（测试准备重复）；Spec：P1能力缺口1（既存原件后审绑定），越界/其他确定性错误0。
