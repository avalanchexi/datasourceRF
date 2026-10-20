# 美债新目录 CLI 候选采集修复

2026-09-10；阶段：implement；本批尚未提交，正式来源认证与模型采用继续开放。

新登记指标目录调用 Treasury CSV CLI 时，指标定义查询缺少 `paths.database`，在发出采集请求前报 `unknown_metric_definition_version`。已向定义查询传入当前运行库路径，保留两个指标现有维度和来源状态。

公开 CLI 反例 [RED88](verification-ust-catalog-red-88.txt) 为 1 失败、16.14 秒，修复后 [GREEN88](verification-ust-catalog-green-88.txt) 为 1 通过、20.04 秒。新测试使用已保存的官方 CSV 原件及替代 HTTP 响应，核对完整原件、实际获取收据、系统取得时间、2Y 4.37% 和 10Y 4.78% 两个独立字面值；取得前 SYSTEM 不可见，PUBLIC 继续未知，状态仍为 `awaiting_source_certification`。这不是新真实网络请求或来源认证。

[关联回归90](verification-ust-catalog-terminal-90.json) 主会话 87891 实际退出 0：**28 通过、0 失败，81.20 秒**。范围为新增新目录 CLI 用例及整个 `tests/integration/test_treasury_csv_acquisition.py`。前后 228 冻结输入、4 受保护文件未变，91 安装源码匹配；mypy 93 文件、Ruff 与格式检查通过。Spec 和 Standards 只读审查剩余各 0，审查范围仅本次查询修复及新增测试。

审查及验证绑定：

- `src/pring_cycle/treasury_context.py`：`5f1ec125a4d6e3a44e79d1bbc234218ba8ab6349aae9af46aaea481b8e38d9b0`
- `tests/models/test_candidate_admission.py`：`701ffbd0f309d83f7eda500da90502a6e0d2208e0f9990809b8c5231fae7f4a5`

下一步依照 [美债来源合同边界](ust-registered-source-contract-boundary.md) 接通正式 Treasury 来源合同、原件与规范化制品消费校验、2s10s 派生与 Worker 路由；官方 CSV 来源身份不得静默替代旧 TuShare 绑定。默认全套尚未复验，SQLite 锁根因未解决。完整真实候选、固定 120 交易日重放、合格真实 AI 输出及正式切换仍未验收。
