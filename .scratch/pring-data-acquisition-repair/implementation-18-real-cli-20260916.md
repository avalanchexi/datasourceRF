# 票18：真实 CLI 合格输出（2026-09-16）

前置见 [连通性实测](verification-connectivity-20260916.md)：codex-cli 0.154.0 已登录，WSL 出口可用，2026-09-09 记录的网络阻塞已不成立。

## 第一次真实尝试暴露的适配器缺陷

复用既有诊断脚本（冻结历史证据包、独立运行库、不写正式数据库、不发布报告），首次真实调用结果：`completed_degraded` / `tool_use_rejected`，工具事件 1，耗时 27.4 秒、退出码 0、输出 1605 字节（`824c4e9c…`）。

排查（一次最小 codex 调用，只看事件类型）发现：codex 0.154 会发出 `item.completed` 且 `item.type="error"` 的事件，内容是 CLI 自己的提示——"Skill descriptions were shortened to fit the skills context budget…"。而 `_cli_event_audit` 把"`item` 类型不是 reasoning/agent_message"一律计为工具调用，于是把这条提示判成模型越界使用工具。**这不是模型行为问题，是适配器事件分类缺陷。**

## 修复

- 新增 `CODEX_NON_TOOL_ITEMS = {"reasoning", "agent_message", "error"}`：CLI 自述型事件不计为工具调用；**未知类型仍计为工具调用**，保持从严（既有反例 `codex_other_tool`/`image_view` 仍被拒收）。
- `error` 事件的文本收进审计字段 `cli_notices`，不静默丢弃。
- RED：新增 `test_a_codex_notice_is_recorded_without_counting_as_tool_use`，未修复时以 `completed_degraded` 失败。GREEN 后 `tests/reports/test_cli_protocol.py` 25 项通过/9.4秒。

## 真实合格输出

修复后第二次真实调用（新的独立运行库）：

| 项 | 值 |
|---|---|
| 结果 | `status=completed`，`outcome=succeeded` |
| 工具事件 | 0 |
| CLI 版本 | codex-cli 0.154.0 |
| 退出码 / 耗时 | 0 / 27,629 ms（monotonic，未发生时钟倒退） |
| schema | `report-schema-v0003`，sha256 `859431b4…` |
| 提示版本 | `report-prompt-v0003`，sha256 `3ada821c…` |
| 模型输出 | sha256 `975975a3…` |
| 模型标识 | CLI 未上报（`model_reporting=not_reported`），如实记录 |
| CLI 提示 | 技能描述被截断的通知，已留证 |

证据：`evidence-18/real-20260916b-codex_cli.json`、`evidence-18/real-20260916b-bundle.json`，运行库在 `~/.cache/pring-cycle/verification/repair-18-real-20260916b-codex_cli/`。

## 边界

- 本次只解释冻结的历史核心状态证据包，**不是当前市场报告**，不写正式数据库，不发布模型或报告，也不构成来源认证。
- 与既有假协议测试分开存放：假协议在 `tests/reports/test_cli_protocol.py`，真实样本只在本记录与 `evidence-18/` 下。
- 票18 第二项"至少一份真实 CLI 合格输出"的条件已具备；第一项（逐段支持/反证与引用越界核验）仍未勾。
