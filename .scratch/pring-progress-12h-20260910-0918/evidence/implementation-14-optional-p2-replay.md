# P2 可选缺口与回放证据校验

状态：**合并回归130已完成，484通过、0失败、1545.32秒；根验收133通过。** 2026-09-10；基点 `99c495a217b66d4bca9d6ceae4688ee69d4382bb`。129未取得终态的原记录保留。本批未提交，整票14/19及完整项目仍在实施。

## 结果与范围

本批修复可选 P2 缺口错误地变成核心/P1 回放硬门的问题，同时保持 GDP 等 P1 公式必要父项的认证与完整性要求。受影响的 P2 仍逐日保留可用值或明确缺口、来源快照及实际采用关系；没有给未知 PUBLIC、未认证来源或不合格数据授予资格。

修改五个文件：`context_replay_scope.py`、`model_evaluation.py`、`model_outputs.py`、`test_candidate_admission.py`、`test_candidate_replay.py`。其余源码未在本批修改。

- 区分需要严格证据的 P1/核心依赖与可选 P2 展示范围，GDP 作为信用脉冲必要父项仍受严格检查。
- 来源范围保留候选与比较两侧可能使用的受影响来源；公式范围考虑任一侧配置公式的版本、输入及输出定义变化。双方禁用的公式不会因输出定义变更重新引入父项硬门。
- 可选当前行必须对应合格定义及有效来源；原始值/单位/期次/身份、派生公式/数值/单位/父项，以及实际采用集合须一致。
- 当前行按同一截止日和既有 `evidence_max_age_days` 复核鲜度。保留合法前期方向输入，不把历史诊断值冒充当前采用值。

## 真实 RED/GREEN 记录

前期 100–119 的测试设置失败、实际反例和增量修复日志均原样保留。119 的 19 项通过之后补充了合法前期方向输入正例；该最新正例在 121/122 实际运行。

| 本轮边界 | 实际失败 | 修复后结果 |
|---|---|---|
| 派生输出自身待认证，父项仍合格 | [RED121](verification-p2-output-red-121.txt)：1 失败、1 通过，15.13 秒 | [GREEN122](verification-p2-output-green-122.txt)：2 通过，13.88 秒，含合法前期方向正例 |
| 仅候选 P2 父项降级，比较版合法来源被漏掉 | [RED123](verification-p2-comparison-red-123.txt)：1 失败，26.01 秒 | [GREEN123](verification-p2-comparison-green-123.txt)：1 通过，16.11 秒 |
| 陈旧原始行重标 current 后被采用 | [RED124](verification-p2-freshness-red-124.txt)：1 失败，19.85 秒 | [GREEN124](verification-p2-freshness-green-124.txt)：22 通过，24.24 秒 |
| 只降级派生输出、其父项与公式均不变 | [RED126](verification-p2-output-scope-red-126.txt)：1 失败，22.31 秒 | [GREEN126](verification-p2-output-scope-green-126.txt)：1 通过，11.64 秒 |
| 双方禁用 credit，修改其输出却误引 GDP 硬门 | [RED128](verification-p2-disabled-red-128.txt)：1 失败，23.64 秒 | [GREEN128](verification-p2-disabled-green-128.txt)：4 通过，11.37 秒，含既有启用/禁用投影场景 |

这些有重叠，不能累加为最终套件数量。公开入口使用真实证据仓库、投影、回放和存档校验；合成来源/legacy 两日或一日组件均明确隔离，不替代正式完整候选及固定 120 日验收。

## 当前验证状态

- [实际终态130](verification-p2-terminal-130.json)记录pytest退出0及后验退出0；[根验收133](verification-p2-acceptance-133.json)复核日志484通过、1545.32秒、228输入及4受保护文件不变，前后91安装源码/53依赖匹配。持久执行器PID34089已退出，不再轮询为运行中。
- [格式128](verification-p2-format-128.txt)：五文件无需格式变更；[Ruff129](verification-p2-ruff-129.txt)通过。
- [mypy129](verification-p2-mypy-129.txt)：94 个文件通过。
- [Standards129](verification-p2-standards-review-129.md)：硬规范 0、实质气味 0；[Spec129](verification-p2-spec-review-129.md)：剩余发现 0。旧 120/125/127 报告保留其当时发现。
- [输入清单129](verification-p2-inputs-129.json)冻结 228 项，较 98 仅上述五文件改变；4 个受保护文件不变。
- [运行核验前129](verification-p2-runtime-before-129.json)：独立 Python 3.12.12 环境、53 依赖、91 安装源码及全部冻结输入匹配。
- 原[运行记录129](verification-p2-running-129.json)绑定会话6968；会话丢失后，WSL核对已无旧测试/包装进程，[旧日志](verification-p2-joint-129.txt)停在14%。[未完成记录](verification-p2-interrupted-130.json)保留退出码/数量未知，未推定中断原因。中断后[再次核验](verification-p2-runtime-after-interruption-130.json)全部输入与运行身份仍一致。
- 已用[独立执行器130](verification-p2-durable-130.py)重跑相同五文件范围：candidate_admission、candidate_replay、model_lifecycle、context_model_certification、derived_context_freshness。它在仓库内自行保存各阶段日志、真实退出码、时间、文件哈希及后验结果，不依赖本轮工具会话收尾。[状态130](verification-p2-running-130.json)与[日志130](verification-p2-joint-130.txt)现已完成，实际终态和后验由上述根验收核对。没有重启共享服务。

[mypy120](verification-p2-mypy-120.txt)与[首次 GREEN121](verification-p2-output-green-121.txt)均遇到 WSL 服务错误，没有得到应用检查结果。后一失败后[只读进程核对](verification-p2-processes-121.txt)确认无专属验证或 wrapper 残留，才新开 GREEN122；旧错误日志未覆盖。未重启 WSL、共享 Worker 或 Web 服务。

## 仍未完成的项目要求

默认全套最近实际结果仍为 1146 通过、2 失败；报告时钟已有独立修复，SQLite 锁根因未解决，全套未重新验收。本批不改变这项记录。

历史真实 PUBLIC/修订与正式来源认证、北交所/CNY030/估值/广度/商品证据及规则、其余 P1/P2、GDP 信用脉冲整窗修订基线、Q1 产能显式映射、Worker/官方定向路由、Tavily/Exa 正式实测和真实 AI 报告链路仍各自待完成。完整真实候选、固定 2026-03-09 至 2026-08-28 的 120 中国交易日重放、合格真实 AI 输出和正式切换仍均为 0。

下一步落实已研究明确的Q1同区间源映射；首个公开测试补丁已准备，待实际RED后实施。Worker新目录运行仍须保持真实模型生命周期前置，不用替换机器验收构造伪通过。
