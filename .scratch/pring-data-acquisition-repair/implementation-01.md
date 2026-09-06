# 01 候选持续天数修复

实施基线：`aeb6b412fcc16d2c94fbe7bd442966b16b8bf588`（已发布规格与 22 票）。
范围：[01-candidate-duration.md](issues/01-candidate-duration.md)。实施、验证与两路审查均已完成。

## 行为与版本

趋势引擎原本已经正确维护连续候选计数，但 Worker 与离线 fixture 将 `persistence_days` 确认门槛写入了 `candidate_days`。现在 `TrendResult.candidate_days` 暴露实际计数，两个输出入口使用同一版本策略。

新候选清单必须明确设置：

```json
{"trend_rules": {"candidate_duration_rule_version": "candidate-duration-v0002"}}
```

该字段属于原有完整 `trend_rules` 清单的一部分；示例不是可独立运行的模型。缺省或 `candidate-duration-v0001` 保留历史输出语义；v0002 输出实际连续候选天数，无候选为 0。`persistence_days` 保留作为原有确认门槛，趋势、牛熊确认和阶段映射算法不变。未知输出规则版本在输出入口拒绝执行。

未修改既有模型清单或生产生效指针，也未创建生产候选；票 19 汇总来源证据后负责绑定本规则，票 21 验证 120 日回放的候选字段，票 22 负责实际生效。仅修代码不会改变已有页面快照。

## 验证依据

- 领域 RED：新增独立短序列，102…109 确认 bull，随后 100…94 是 7 个 bear 信号；修复前因缺少实际计数字段失败，修复后通过。
- Worker RED：真实隔离证据仓库 → 手动任务 → Worker → 只读投影，修复前断言得到 `8 != 7`，修复后任务、CLI 查询、REST `/api/v1/projections/current` 路由、页面和报告事实骨架均为 7，稳定 bull / Stage III 不变。旧模型投影与报告重新读取的规范 JSON 字节一致。
- Fixture RED：离线验收入口同样先得到 `8 != 7`，接入同一版本策略后通过；验收标签仍为 acceptance-only。
- 人工短序列覆盖无候选、第 8 天确认、中断后重新计数、回到稳定方向及确认后的反向候选。
- [真实样本收据](verification-01/actual-duration.json)：留存标准化 CAS SHA256 `0605b3d9a8f2a9eb196fd220a03f90cf31d0acb464430569ead89287702ab61b` 校验通过。截到 2026-08-03，三核心各 2,326 点，默认 MA120 / slope20 / noise1.5 规则下，股票 7、债券和商品 0；新旧规则的趋势结果、测量值和稳定状态相等。
- 该 CAS 是标准化历史，不是逐请求 HTTP 原件或独立官方认证。它只用于复现既有缺陷；来源与公开时间证据仍由后续任务解决。
- 既有 v3 隔离回归 4 项通过，未修改隔离判断。

[可重跑核对脚本](verification-01/reproduce_actual_duration.py) 只读 CAS，无网络请求或生产写入。[完整检查收据](verification-01/checks.json) 记录安装环境、命令、退出码、输出和耗时。

最终结果：完整 pytest **418 passed in 128.39s**；Ruff 通过；mypy **68 个源文件通过**。全套通过后，在同一集成测试中补充 REST 路由断言，针对该文件复验 **2 passed in 3.32s**，Ruff 再验通过；应用源码未再改变，因此未重复完整测试。

运行库遵循 ADR-0007 及 `RuntimePaths` 既有硬门，放在 WSL 原生专属验证缓存 `/home/tywin/.cache/pring-cycle/verification/repair-01-*`；仓库内保存脚本和收据。源码目录内的临时运行库会被拒绝，首次两次集成测试的环境设置失败不计入业务 RED。完整测试使用离线重装后的 dev-venv 包，未设置 PYTHONPATH。

## Standards

固定实施基线后暂存的 7 个文件已独立审查：0 项明确违规，0 项需要整改的 smell。模型清单选择新旧语义，实际计数来自既有趋势计算，阶段映射与历史快照规则保持符合 CONTEXT 和 ADR-0001/0004/0008/0012。审查为只读静态检查，测试由实施方另行执行。

## Spec

独立审查 0 项发现：无本票遗漏、越界行为或实现错误。实际 CAS 证明留存数据上的计数；测试模型运行不代表生产认证。现有历史模型回放接口仅比较稳定状态/阶段，候选字段的完整 PUBLIC 输出验收明确交由票 21，未把本票的离线核对冒充正式回放。两路审查基线均为上述提交，因实现尚未提交使用 `git diff --cached <base> --` 审查暂存差异。

最终增量（REST 路由断言、检查收据、完成状态与后续交接）经 Spec 再次独立复核，0 项问题；收据中的 5 个文件指纹与工作区匹配。

审查汇总：Standards 0 项，Spec 0 项；两轴均无待整改问题。

## 后续入口

01 完成后，无依赖可执行票仍为 [02 核心采集原件与双点时](issues/02-core-acquisition-receipts.md) 和 [18 报告解释](issues/18-report-cli-evidence.md)。融资、CNY030、估值、广度、商品规则与来源认证、Tavily/Exa 真实补缺测量、新候选和真实切换均未在本票完成。
