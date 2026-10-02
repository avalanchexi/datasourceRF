# 25: 新模型 v0014：12 个月信用脉冲、停用 12 月代理

**What to build:** 按 [ADR-0035](../../../docs/adr/0035-metric-horizon-at-most-one-year.md) 新建模型 v0014：信用脉冲换成 12 个月公式版本，停用公开 Pring 12 月代理；其余规则继承 v0013。

**Blocked by:** 23、24

**勿并行：** 15、16、17、18、26、27、28（同改：Worker 编排与取数；信用脉冲模块；逐区明细见 [README](../README.md)「串行约束」）

**Status:** done（CONTEXT.md 措辞待用户确认）

来源：[架构评审](../README.md) 候选 5 访谈（Q17′–Q30，2026-09-29）；盘点见 [codex-survey-c5b.md](../codex-survey-c5b.md)。 规格：[spec.md](../spec.md)「六、信用脉冲模块与指标尺度」。

## 已定决定

- **12 个月信用脉冲**（`CONTEXT.md`：信用脉冲）：值＝近 12 个月社融增量 ÷ 近 4 季名义 GDP，单位百分比；方向由本月与上月比例比较，两者用本月可得的同一个近 4 季 GDP 作分母（即方向只由本月社融增量是否多于去年同月决定）。输入社融 13 个月、GDP 4 季，年初至今差分时各加一期基期；GDP 数据版本规则沿用。作为模块里的第四个版本策略加入（新公式版本名如 `credit-impulse-12m-flow-share-v0003`）。
- 信用脉冲仍担任信用响应附加证据（`credit_impulse`）、过热"信用"角色与库存 `credit_physical_inventory`；映射不变。
- **停用 12 月代理**：新模型趋势规则加开关关闭 `proxy_12m`；旧模型照旧计算。关闭后核心页不展示、候选事件记录不带该字段（`trend.py:211`、`dashboard.py:874`、`p0.py:331`）。
- 核心趋势、广度 250 日、事件现行基准、商品篮子基日不变。
- 继承 `effective_model_manifest()` 的做法：以 v0013 为基底、改规则、赋新版本号（`models.py:484`）。单位由百分点改为百分比属于指标定义变化：现行目录中 `CN_CREDIT_IMPULSE` 的单位是 `percentage_points`（2026-09-29 核对），因此另起新目录版本，单位改为百分比并同步 `definition_version`（勘察第二份 38；目录与模型都不可原地改写）。
- **注册与生效由用户执行**：`pring-cycle model-register --manifest <json> --json`、`pring-cycle model-activate --model model-v0014 --confirm --json`。本票只交付清单构造、校验与测试，不代为激活。

## 验收

- [x] v0014 清单与新目录版本可构造并通过上下文规则校验；`effective_model_manifest()` 按现行惯例指向最新模型 v0014。
- [x] 按 TDD 在模块接口上测 12 个月版本：成功计算与值；方向在 GDP 新季度发布前后不因分母翻转；社融、GDP 各一种差分；缺期状态；需求 13／4 及基期。
- [x] 模型关闭 12 月代理时，核心展示与候选事件不含 `proxy_12m`；旧模型仍计算。
- [x] 回退到 v0013 后信用脉冲仍按两年版本计算（一例）。
- [ ] `CONTEXT.md`"公开 Pring 12 月代理"的"已停用"注明自 v0014 起停用、旧模型仍计算（措辞与用户确认）。
- [x] 受影响测试经 `check.py quick` 通过；切片收尾冒烟通过；加跑完整目录正例，记录退出码与耗时。
- [x] 代码审查无阻断；Comments 写明用户执行注册与激活的命令。

## Comments

**2026-10-02 实施记录**

- **信用模块** `credit_impulse.py`：
  - `_Version` 增加期数、计算方式、单位与公式说明。
  - 第四版本 `credit-impulse-12m-flow-share-v0003`：社融 13 月、GDP 4 季，两者都可由年初至今差分；值为 `100 × 近 12 月社融 ÷ 近 4 季名义 GDP`，单位 `percent`。方向取本月社融增量与去年同月之差的符号：两者同一分母，所以等价于比较相邻两月的比例，GDP 新季度只改变值、不改变方向。
  - 新版本的社融累计差分用十进制相减，避免浮点尾差把持平判成加速；旧三个版本仍是 24/8、两年占比差、按值的符号给方向、百分点，算法不动。
  - 结果新增 `direction`、`formula`；失败结果也带版本单位。
  - `minimum_requirements`、`fetch_coverage` 与 `_shortfall` 改按版本期数，新版需求为 13/4，非年初窗口各加一期基期（14/5 等）。
- **投影**：信用行方向与公式说明改取模块结果（信用响应、过热"信用"、库存 `credit_physical_inventory` 三处角色共用同一行）。
- **12 月代理开关**：
  - `TrendRules.proxy_12m_enabled`（默认开），正式与 fixture 两套清单解析器都读 `trend_rules.proxy_12m_enabled`，必须是布尔值；
  - 关闭时不计算；`CoreAssetReadiness.proxy_12m_enabled` 传到 P0，关闭时核心资产与候选事件都不带 `proxy_12m` 字段，看板也不显示；开启但历史不足时照旧输出 `null`／"不可用"。
- **模型**：
  - 原 `effective_model_manifest()` 的实现改名为 `model_v0013_manifest()`，目录常量固定为 `MODEL_V0013_CATALOG_VERSION = metric-catalog-v0005`（已核对输出与改前逐字节一致，已注册的 v0013 不受影响）；
  - 新增 `model_v0014_manifest()`：继承 v0013，信用公式换为新版本，`trend_rules.proxy_12m_enabled = false`，目录 `metric-catalog-v0006`（`MODEL_V0014_CATALOG_VERSION`，全部定义同步 `definition_version`），`CN_CREDIT_IMPULSE` 单位与允许单位改为 `percent`；
  - `effective_model_manifest()` 与 `EFFECTIVE_CATALOG_VERSION` 指向 v0014。
- **验证**（`PYTHONPATH=src`）：受影响 70 个测试文件（含两例收尾冒烟、完整目录正例 `test_worker_registered_catalog.py`、三核心反例 `test_core_carry_forward.py`，以及 7 个现跑在 v0014 上的完整运行用例）共 895 例全过，耗时 47.0 分钟。ruff、mypy（改动的源文件）通过。
- **审查**（Codex 只读，两轮）：首轮 2 项阻断——回退验收未真算、十进制持平被浮点尾差误判——均已修，并采纳"v0014 绑定固定目录常量"的建议；次轮无阻断。保留建议：经投影断言三个角色的方向与落库单位（静态核对传递逻辑正确）。
- **CONTEXT.md**：「公开 Pring 12 月代理」改为"自模型 v0014 起停用……旧模型仍按其清单计算"。**措辞待用户确认。**
- **测试**：
  - 信用模块：新版值与三种口径组合、GDP 新季度只动值不动方向、占比为正但方向下降、十进制持平、缺期、13/4 与基期需求、旧版单位与方向不变；
  - 趋势开关（默认兼容、关闭不算、非布尔拒绝）；P0 字段缺席；看板隐藏；
  - `test_model_version_switch.py`：用用户命令（CLI `model-register`、`model-activate --confirm`）注册 v0013、v0014，激活 v0014 后核对公式、目录与单位、代理关闭；回退 v0013 后真实计算两年版本（`available`、百分点、两年公式值）；
  - 原先写死 `model-v0013` 的 7 个测试文件改用 `CURRENT_MODEL`（取自最新清单），现在跑在 v0014 上。
- **用户执行的注册与激活**（本票不代为执行）。`.venv` 里装的是非可编辑的旧副本，不含 v0014，须用 `PYTHONPATH=src` 指向当前源码（或先重装）：
  ```bash
  cd /mnt/d/cursor/datasourceRF
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -c "import json; from pring_cycle.models import model_v0014_manifest; print(json.dumps(model_v0014_manifest(), ensure_ascii=False, default=list))" > model-v0014.json
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/pring-cycle model-register --manifest model-v0014.json --json
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/pring-cycle model-activate --model model-v0014 --confirm --json
  ```
- **行为差异（只记录，未改）**：
  - 取数范围：Worker 普通取数仍是"目标年份减二"，新版需求缩为 13/4 并不缩小实际请求，收缩属票 30。
  - 7 个改用 `CURRENT_MODEL` 的测试现在验证 v0014，不再作为 v0013 的回归证据。
