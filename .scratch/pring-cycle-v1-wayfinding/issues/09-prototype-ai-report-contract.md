Type: prototype
Status: resolved
Blocked by: 02, 04, 05

# 验证双 AI CLI 的证据报告协议

## Question

Codex CLI 与 Claude Code CLI 在本地实际接受什么结构化输入、如何返回可验证输出，并能否在不读取密钥、不自由搜索、不修改正式阶段的约束下生成一致的中文报告？用同一小型证据包验证调用、超时、取消、替代、引用、确定性简版降级和30天不可变快照契约，形成两个可互换适配器的共同协议。

## Answer

已冻结[《双AI CLI证据报告共同协议》](../assets/ai-cli-report-contract.md)：Codex CLI与Claude Code CLI在Ubuntu/WSL2中使用自身登录消费同一证据包和共同Schema，不使用API key。两者均完成真实合格输出；共同Schema、零工具边界、后置校验、300秒超时、取消、替代、确定性简版和不可变快照语义已通过原型并经用户确认。

首选适配器可配置且默认Codex；同次运行每个适配器最多一次，失败后调用Claude；双失败生成`completed_degraded`确定性事实骨架快照。AI只解释确定性事实骨架，可互换按结构与语义一致验收，不要求正文逐字相同。实测依据见[原型观察记录](../assets/ai-cli-report-prototype-observations.md)和[编排逻辑原型](../prototypes/ai-report-contract/ai-report-protocol-prototype.html)，架构取舍见[ADR-0009](../../../docs/adr/0009-cli-only-evidence-report-adapters.md)。

## Comments

### 2026-08-24 第一轮真实 CLI 探针

- 已建立同一合成证据包、共同约束提示、严格报告JSON Schema和一次性进程探针；全部位于`.scratch`，不是正式实现。
- Codex CLI极小JSON烟雾调用成功且无工具事件；完整证据包调用因传输降级后网络不可达达到180秒硬超时，没有最终对象或快照。
- Claude Code CLI当前认证无法刷新；用户确认当前用量窗口耗尽，待恢复后补测。没有改用API key、其他账号或其他渠道绕过。
- 失败、超时和部分输出均未形成报告快照；本票保持`claimed`，共同适配器协议尚未冻结。

### 2026-08-24 认证边界确认

- 用户确认只允许通过本机Codex CLI和Claude Code CLI调用，不使用模型厂商API key。
- 应用不得接收、读取、保存或注入API key；CLI未登录、认证失效或额度耗尽时只报告不可用，不得转为直接API调用。
- 一个CLI不可用时可尝试另一个；两个CLI均不可用时进入确定性简版，不阻塞结构化驾驶舱。

### 2026-08-24 Ubuntu环境复测

- 已确认运行环境为Ubuntu 22.04.5 LTS on WSL2，Claude Code CLI版本为2.1.229。
- 极小结构化调用在发送输入token前失败，CLI报告OAuth会话过期且无法刷新；未发送完整证据包、未产生工具调用或报告快照。
- 若额度已经恢复，需要用户在同一Ubuntu/WSL环境完成`claude auth login`后再继续真实报告探针。

### 2026-08-24 最终共同夹具通过

- 用户在Ubuntu/WSL环境恢复Claude Code CLI登录；两个适配器均仅通过本机CLI登录调用，未使用API key。
- Codex CLI与Claude Code CLI已分别对同一`eb-prototype-v1`证据包和最终共同Schema完成一次合格输出：Codex 34.459秒，Claude 31.022秒；两者工具事件均为0，Stage II未被改写，引用与治理缺口通过后置校验。
- 共同Schema采用能力交集：`const`/`enum`显式声明类型；Codex不支持的`uniqueItems`移至本地后置校验；数据质量使用独立`governance_refs`，不再强迫引用无关市场观测。
- Claude另一次在180.675秒触发进程组硬超时且未产生快照，验证了部分输出拒收与取消边界；成功耗时存在明显波动。
- 已形成共同协议草案（后经HITL确认为[最终协议](../assets/ai-cli-report-contract.md)）及[单文件编排逻辑原型](../prototypes/ai-report-contract/ai-report-protocol-prototype.html)。当时等待确认首选顺序、超时、重试、确定性简版、取消与事实/解释分层。

### 2026-08-24 HITL最终确认

- 用户确认Q124—Q130全部采用推荐方案A。
- `preferred_adapter`可配置且默认Codex；Claude作为替代；单适配器硬超时300秒、终止宽限5秒，总进程预算约610秒。
- 同一报告运行中每个适配器最多尝试一次，不自动重试同一适配器。
- 双失败生成`completed_degraded`确定性简版；取消只保留运行审计，重新生成创建新的不可变版本。
- 采用“确定性事实骨架 + AI解释段”；可互换按输入、Schema、不变量和引用语义一致验收，不要求逐字相同。
