# 双 AI CLI 证据报告共同协议

> 状态：已由真实Ubuntu CLI探针验证并经用户确认冻结。  
> 适用：Codex CLI 0.149.1、Claude Code CLI 2.1.229；不承诺未来版本无需兼容性复测。

## 1. 协议结论

Codex CLI与Claude Code CLI可以作为同一报告端口的两个适配器。可互换的含义是：接受同一冻结证据包、遵守同一不变量、产出同一结构协议并通过同一后置校验；不要求自然语言正文逐字相同。

AI不生成事实骨架或正式阶段。Worker先确定性生成报告身份、正式阶段、核心资产状态、指标值、治理缺口和证据引用；CLI只为这些结构化事实生成受约束解释。失败时事实骨架本身就是确定性简版。

## 2. 认证与进程边界

- 只调用Ubuntu/WSL2中已安装并已登录的`codex`或`claude`命令；
- 应用不接收、读取、保存或注入模型厂商API key；
- CLI未安装、未登录、认证失效或额度耗尽时，该适配器返回不可用；
- 每次调用使用独立进程组和空临时工作目录；
- 环境变量使用白名单，只保留基础运行变量及经检查不含凭据的网络代理；
- 临时输入和输出在生成不可变快照或失败审计后清理。

## 3. 共同输入

一次调用冻结：

- `bundle_id`、`projection_set_id`、业务日和`report_cutoff`；
- `system_as_of`和120日证据窗口；
- 正式阶段、三核心资产状态、模型和趋势规则版本；
- 证据观测、转折观察、宏观状态、库存状态和治理缺口；
- `allowed_evidence_ids`与`allowed_governance_refs`；
- 报告Schema版本、提示合同版本及禁止项。

CLI没有读取项目文件、旧`.env`或自由搜索的必要。证据包通过stdin进入子进程；输出Schema由Worker提供。

## 4. 两个适配器的隔离

### Codex CLI

- `codex exec`非交互调用；
- `--ephemeral`、忽略用户配置/规则、只读沙箱、空临时工作根；
- JSONL事件审计和独立最终消息文件；
- 当前CLI没有与`--tools ""`等价的总开关，因此任何命令、文件修改、MCP或Web事件都会令结果无效；
- 最终实现必须显式关闭不需要的可选功能，并在CLI版本升级后重跑探针。

### Claude Code CLI

- `claude --print`非交互调用；
- safe mode、禁用斜杠命令、`--tools ""`、不保存会话、`dontAsk`权限；
- 读取`structured_output`，不把普通stdout或部分流当作报告。

## 5. 共同Schema兼容层

共同Schema采用两个CLI实际支持的交集：

- 每个`const`或`enum`都显式声明`type`；
- 不使用Codex当前不支持的`uniqueItems`；唯一性和跨字段规则由本地后置校验器执行；
- 每个对象拒绝额外字段；
- `current_stage`、`bundle_id`和截止点由每份证据包固化为常量；
- 分析段使用`evidence_ids`，数据治理段使用`governance_refs`；
- 未认证来源必须有`proxy_used=false`。

## 6. 后置校验

CLI退出成功仍不等于报告成功。Worker必须拒绝以下输出：

- 非JSON、Schema不符或出现额外字段；
- `current_stage`、截止点、证据包身份被修改；
- 缺少必需分节或出现重复引用；
- 使用白名单外证据或治理引用；
- 资产候选状态被写成候选阶段或阶段预测；
- 未认证来源使用代理；
- 出现工具事件、交易建议或密钥类文本；
- 叙述中出现无法由所引用证据、治理记录或确定性元数据追溯的数字。

为降低对AI文字的信任，最终报告由“确定性事实骨架 + AI解释段”合并。事实、数值、阶段、引用和缺口由系统渲染，AI解释段逐段绑定支持证据与反证。

## 7. 运行状态机

```text
queued
  → preflight
  → primary_running
      → validating → succeeded → snapshot_written
      → unavailable/failed/timed_out/invalid
          → alternate_running
              → validating → succeeded → snapshot_written
              → unavailable/failed/timed_out/invalid
                  → deterministic_fallback → fallback_snapshot_written

任意running → cancelling → cancelled
```

只有`succeeded`或`deterministic_fallback`能够写报告快照。失败尝试只写运行审计；stdout、部分JSON和校验失败对象不写正文。

编排参数冻结为：

- `preferred_adapter`可配置，默认`codex_cli`；替代为`claude_code_cli`；
- 单适配器硬超时300秒，终止宽限5秒；两个适配器总进程预算约610秒；
- 同一报告运行内每个适配器最多调用一次，不自动重试同一适配器；
- 首选失败、不可用、超时或校验不合格后才调用替代适配器；
- 两个适配器均未成功时生成确定性事实骨架快照，报告状态为`completed_degraded`；
- 主动取消只保留运行审计，不保存部分正文或报告快照；再次生成创建新的同日版本。

## 8. 错误分类

- `cli_not_installed`
- `cli_not_authenticated`
- `cli_quota_exhausted`
- `transport_failed`
- `timed_out`
- `cancelled`
- `nonzero_exit`
- `invalid_json_schema`
- `invalid_json_output`
- `schema_validation_failed`
- `stage_mutation_rejected`
- `evidence_reference_rejected`
- `tool_use_rejected`
- `forbidden_content_rejected`

每次尝试只保存分类、版本、开始/结束时间、时长、退出码、是否有工具事件和安全摘要，不保存认证信息或完整错误响应。

## 9. 快照

合格报告快照绑定：

- 报告业务日、同日版本和`report_snapshot_id`；
- 证据包、输入Schema、提示合同、CLI适配器、CLI版本、模型标识；
- 投影、模型和趋势规则版本；
- 规范化输出哈希和生成时长；
- 成功、确定性简版或取消/失败审计状态。

同日重跑创建新版本，不覆盖旧快照。自然语言正文保留30天；结构化事实骨架、证据引用、哈希、版本和运行审计长期保留。

## 10. 实测基线

| 适配器 | 最终共同夹具 | 时长 | 工具事件 | 结果 |
| --- | --- | ---: | ---: | --- |
| Codex CLI | 合成Stage II证据包 | 34.459秒 | 0 | Schema与后置校验通过 |
| Claude Code CLI | 同一证据包 | 31.022秒 | 0 | Schema与后置校验通过 |

Claude另一次调用在180.675秒被终止，证明耗时存在显著波动，不能以单次成功时长设置过紧上限。

## 11. 冻结决策

用户确认：默认Codex、可配置首选并以Claude替代；单适配器300秒；每个适配器同次运行最多一次；双失败按`completed_degraded`保存确定性简版；取消不保存部分正文；采用“确定性事实骨架 + AI解释段”；可互换按输入、Schema、不变量和引用语义一致验收，不要求逐字相同。
