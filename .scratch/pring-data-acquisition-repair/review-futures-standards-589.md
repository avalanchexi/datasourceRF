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
