# 双 AI CLI 证据报告协议：原型观察记录

> 状态：已完成；共同协议经HITL确认并冻结。  
> 日期：2026-08-24。  
> 范围：Wayfinder“验证双 AI CLI 的证据报告协议”的一次性实测；不是正式适配器实现。

## 1. 原型问题

验证 Codex CLI 与 Claude Code CLI 能否消费同一份合成证据包，在关闭自由工具/搜索、禁止改写正式阶段的约束下，返回同一 JSON Schema 的中文报告；同时观察超时、取消、替代和不可变快照所需的进程边界。

## 2. 夹具

- [合成证据包](../prototypes/ai-report-contract/evidence-bundle.json)：`fixture_only=true`，正式阶段固定为 Stage II；包含三核心状态、商品资产候选状态、政策/库存/价格证据和一个未认证 VIX 缺口。
- [报告输出 Schema](../prototypes/ai-report-contract/report-output.schema.json)：把 `bundle_id`、截止点和 `current_stage` 固定为常量；所有分节只能引用白名单 evidence ID；未认证 VIX 必须保持无代理。
- [共同约束提示](../prototypes/ai-report-contract/system-prompt.txt)：禁止工具、搜索、重分类、阶段预测和交易建议。
- [一次性探针](../prototypes/ai-report-contract/run_probe.py)：使用临时工作目录、净化后的进程环境、进程组硬超时和独立后置校验。

夹具不读取旧项目 `.env`，不记录 token、API key、认证头或认证存储。两个 CLI 只使用各自既有交互式认证机制；正式适配器也不得接收、读取、保存或注入模型厂商 API key。

## 3. 实测环境

- 操作系统：Ubuntu 22.04.5 LTS（WSL2，内核 `6.6.87.2-microsoft-standard-WSL2`）。

| 适配器 | 本机版本 | 非交互结构化能力 |
| --- | --- | --- |
| Codex CLI | `0.149.1` | `codex exec`、stdin、`--output-schema`、`--output-last-message`、JSONL事件、`--ephemeral` |
| Claude Code CLI | `2.1.229` | `--print`、stdin、`--json-schema`、JSON/stream-json、`--no-session-persistence`、`--tools ""` |

## 4. 隔离方式

### Codex CLI

- 临时空目录作为工作根；
- `--ephemeral`，不保留会话；
- 忽略用户配置和规则；
- 只读沙箱；
- 审计 JSONL 事件，出现命令、文件、MCP 或 Web Search 事件即拒收；
- 当前 CLI 没有与 Claude `--tools ""` 等价的显式总工具关闭参数，因此“零工具事件”必须作为每次验收条件，不能只依赖提示词。

### Claude Code CLI

- safe mode；
- `--tools ""` 显式关闭全部工具；
- 禁用斜杠命令；
- `--no-session-persistence`；
- `dontAsk` 权限模式；
- 单次 JSON 结构输出。

## 5. 当前结果

| 场景 | 结果 | 工具事件 | 是否形成可验收报告 |
| --- | --- | --- | --- |
| Codex 极小 JSON 烟雾调用 | 正常完成，返回 `{"ok":true}` | 0 | 只证明基本非交互输出可用 |
| Codex最终共同夹具 | 34.459秒完成；Schema与后置语义校验均通过；输出哈希`9d8935…c2b` | 0 | 是 |
| Claude极小JSON烟雾调用 | 登录恢复后正常完成，结构输出可读取 | 0（工具已禁用） | 只证明基本非交互输出可用 |
| Claude共同夹具（早期Schema） | 111.46秒完成；Schema与后置语义校验均通过 | 0（工具已禁用） | 证明完整报告能力可用 |
| Claude最终共同夹具，180秒上限 | 进程组在180.675秒被终止 | 0（工具已禁用） | 否；验证超时无半快照 |
| Claude最终共同夹具，300秒上限 | 31.022秒完成；Schema与后置语义校验均通过；输出哈希`45bcbe…b0d` | 0（工具已禁用） | 是 |

用户曾确认 Claude Code 用量窗口耗尽；恢复后在同一Ubuntu环境完成`claude auth login`并通过实测。原型始终未使用 API key、其他账号或其他模型渠道绕过。

实测同时发现网络代理是CLI传输的必要环境：原探针过度净化环境导致Codex网络不可达和Claude 403。最终环境白名单保留不含用户名/密码的HTTP(S)/ALL/NO_PROXY变量，但仍排除任何API key、token、secret或password变量。

若任一CLI未登录、认证失效或额度耗尽，该适配器只返回不可用；编排可以尝试另一CLI，但不得降级为直接模型API。两个CLI均不可用时进入确定性简版路径。

## 6. 已验证的进程语义

- 每个适配器是独立子进程组；硬超时先发送 `SIGTERM`，宽限5秒后才使用 `SIGKILL`。
- 超时、认证失败、网络失败、非零退出、无法解析、Schema失败、阶段不一致或出现工具事件均不能产生报告快照。
- CLI 自身在收到终止信号后可能返回退出码0，因此编排必须以自身记录的 `timed_out` 为准，不能只看退出码。
- 中间 stdout、JSONL事件和部分文本不是报告正文；只有最终结构对象通过后置校验后才有资格写入新快照版本。

## 7. 尚未验证，不能提前冻结

已验证：两个CLI能够对同一最终证据包与共同Schema返回合格中文报告；Stage II保持不变；引用只使用白名单；VIX未使用代理；数据质量使用独立治理引用；工具事件为零；输出可以生成内容哈希。

HITL已确认：首选适配器可配置且默认Codex；Claude为自动替代；单适配器300秒；同一运行每个适配器最多一次；双失败按`completed_degraded`生成确定性简版；取消不生成快照；采用确定性事实骨架与AI解释分层；可互换按结构与语义一致验收。

## 8. 原型结论

CLI能力、共同Schema兼容性和编排策略均已冻结，详见[《双AI CLI证据报告共同协议》](ai-cli-report-contract.md)。正文措辞不同是预期行为；可互换定义为输入、输出、错误、引用和不变量一致。
