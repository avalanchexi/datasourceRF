# 25: 新模型 v0014：12 个月信用脉冲、停用 12 月代理

**What to build:** 按 [ADR-0035](../../../docs/adr/0035-metric-horizon-at-most-one-year.md) 新建模型 v0014：信用脉冲换成 12 个月公式版本，停用公开 Pring 12 月代理；其余规则继承 v0013。

**Blocked by:** 23、24

**勿并行：** 15、16、17、18、26、27、28（同改：Worker 编排与取数；信用脉冲模块；逐区明细见 [README](../README.md)「串行约束」）

**Status:** ready-for-agent

来源：[架构评审](../README.md) 候选 5 访谈（Q17′–Q30，2026-09-29）；盘点见 [codex-survey-c5b.md](../codex-survey-c5b.md)。 规格：[spec.md](../spec.md)「六、信用脉冲模块与指标尺度」。

## 已定决定

- **12 个月信用脉冲**（`CONTEXT.md`：信用脉冲）：值＝近 12 个月社融增量 ÷ 近 4 季名义 GDP，单位百分比；方向由本月与上月比例比较，两者用本月可得的同一个近 4 季 GDP 作分母（即方向只由本月社融增量是否多于去年同月决定）。输入社融 13 个月、GDP 4 季，年初至今差分时各加一期基期；GDP 数据版本规则沿用。作为模块里的第四个版本策略加入（新公式版本名如 `credit-impulse-12m-flow-share-v0003`）。
- 信用脉冲仍担任信用响应附加证据（`credit_impulse`）、过热"信用"角色与库存 `credit_physical_inventory`；映射不变。
- **停用 12 月代理**：新模型趋势规则加开关关闭 `proxy_12m`；旧模型照旧计算。关闭后核心页不展示、候选事件记录不带该字段（`trend.py:211`、`dashboard.py:874`、`p0.py:331`）。
- 核心趋势、广度 250 日、事件现行基准、商品篮子基日不变。
- 继承 `effective_model_manifest()` 的做法：以 v0013 为基底、改规则、赋新版本号（`models.py:484`）。单位由百分点改为百分比属于指标定义变化：现行目录中 `CN_CREDIT_IMPULSE` 的单位是 `percentage_points`（2026-09-29 核对），因此另起新目录版本，单位改为百分比并同步 `definition_version`（勘察第二份 38；目录与模型都不可原地改写）。
- **注册与生效由用户执行**：`pring-cycle model-register --manifest <json> --json`、`pring-cycle model-activate --model model-v0014 --confirm --json`。本票只交付清单构造、校验与测试，不代为激活。

## 验收

- [ ] v0014 清单与新目录版本可构造并通过上下文规则校验；`effective_model_manifest()` 按现行惯例指向最新模型 v0014。
- [ ] 按 TDD 在模块接口上测 12 个月版本：成功计算与值；方向在 GDP 新季度发布前后不因分母翻转；社融、GDP 各一种差分；缺期状态；需求 13／4 及基期。
- [ ] 模型关闭 12 月代理时，核心展示与候选事件不含 `proxy_12m`；旧模型仍计算。
- [ ] 回退到 v0013 后信用脉冲仍按两年版本计算（一例）。
- [ ] `CONTEXT.md`"公开 Pring 12 月代理"的"已停用"注明自 v0014 起停用、旧模型仍计算（措辞与用户确认）。
- [ ] 受影响测试经 `check.py quick` 通过；切片收尾冒烟通过；加跑完整目录正例，记录退出码与耗时。
- [ ] 代码审查无阻断；Comments 写明用户执行注册与激活的命令。
