# 25：期次定位与完整运行回退接续

工作树：`/mnt/d/cursor/datasourceRF-fallback-20260917`；分支 `codex/official-period-fallback`；基点 `37696ba`。PPI切片已提交 `45715b6021ae0e31a7af25438497de43e7a90382`，未合并或正式激活。主目录保留既有改动，记录及证据在主目录。

## 已取得的证据与行为

- 四次正文请求及解析见 `evidence-25-articles-20260917/receipts.json`；GDP 复用原件，见 `verification-25-existing-gdp-20260917.json`。这证明有可解析公告，不代表来源认证。
- 官方列表按期次定位实际公告；索引和正文分别存原件、分别计请求，错误 MIME/域名/重复匹配不写观测。旧版安装包相关 82 项通过记录见 `verification-25-installed-related-20260917.txt`；该结果早于以下完整运行改动。
- 公开完整取数阶段反例发现：`FullRunRetrieval._plan` 原来固定 `source_url=None`，并不是从目录读取；只加候选 URL 不会生效。新目录路径已接通。未知发布时只允许读取配置过的官方列表，尚不开放搜索渠道。
- 已有上期时可另外查找新一期；查询不提前改变必需期次。新公告没找到时，仍沿用原有期次要求。`verification-25-full-not-released-red-20260917.txt` / `...-green-20260917.txt` 留下反例与修复。
- TuShare 已有该期行但 PUBLIC 时间未知时不触发“缺行”回退。该判断独立于可采用性，避免把本票扩大为数值对账或历史时间修复。
- 新目录的官方族原先也拒收 TuShare。当前仅为 PPI 增加显式来源契约标识 `tushare:cn_ppi:official-sampled-v0001`，绑定 API、字段、维度、单位和期次；原件及规范化结果复算后仍需通过注册契约。标识自身不授予认证，其他七项双通道尚未实现。

## 审查发现与待处理

两轴审查使用 `code-review` 技能，由 `fallback_spec_review` 与 `fallback_standards_review` 对同一基点的 WIP 独立只读审查。

### Standards

发现并已修复一个硬问题：通用 TuShare 原件比较会清除发布时间再比较经济字段，因此“在标量中自行填入日期”可以与规范化记录互证，却没有独立发布时间原件。PPI 新通道现在拒收无独立证据的非空 PUBLIC 时间，错误为 `registered_ppi_publication_evidence_required`。`verification-25-unproven-public-time-red-20260917.txt` 证明旧实现不拒收，`...-green-20260917.txt` 证明修复。带日期测试夹具不再被当作生产时间证明。原 `verification-25-dual-channel-integrity-20260917.txt` 的六项通过记录保留为发现过程，**不能作为安全收口证据**。

当前 PPI TuShare 契约仅支持无时间的 SYSTEM 交付；有真实官方时间的 PUBLIC 绑定机制仍待实现。不得把“拒收伪时间”当成全部双通道 PUBLIC 验收完成。

非阻断建议：未知发布时只调用官方，其他搜索渠道的账本应说明“发布未证实”，而非笼统记作 `not_configured`。

### Spec

先前两项缺陷（把不可采用当缺行、提前把新一期变为必需输入）已按反例修复。剩余验收包括完整 Worker 混合交付运行、投影与报告可见的通道、双缺失的失败语义，以及其余七项的明确双通道契约。

CPI/PMI 同一公告含多个指标，现有公告入库会存整族。扩展这些家族前必须验证：仅一个指标缺期时，读取整页不能改变已有 TuShare 值的兄弟指标通道或引入冲突。

## 验证与运行边界

- 当前八个修改过的源文件通过 mypy 与 Ruff。修复时间漏洞后，取数阶段与报告边界相关 **19 项通过**，见 `verification-25-projection-channel-green-20260917.txt`。价格投影此前只保留派生信号摘要，现补入已有标准证据行，因此报告的价格上下文也能携带按指标/期次的交付来源。
- 更广相关回归 `verification-25-full-related-20260917.txt` 在旧代码完成 107 项后由 Codex 主动发送 SIGINT，退出码 2，以实施已发现的时间边界修复。**该轮未完成，不记作完整通过**；不是资源耗尽，不是任务 D 被中断。
- 新完整取数用例没有绕过流程宣称候选已激活：它调用的是独立候选的公开取数阶段，完整生命周期/Worker 验证仍须另做。
- 独立工作树已补齐缺失的 272 件归档输入；只复制主目录中不存在于工作树的文件，没有覆盖已有文件，清单为 `verification-25-worktree-materials-20260917.json`。
- 任务 D 已取得最终 1672+12 项通过及两段 exit=0，见 `verification-taskD-codex-closeout-20260917.md`。结束后才启动独立工作树的一项完整 Worker 回退/报告用例，日志 `verification-25-full-worker-20260917.txt`；该进程可能需要先构建新候选生命周期材料，未取得终态前不算通过。
- 最新安装包与工作树 Python/CSS/JS 字节核对记录为 `verification-25-full-install-20260917.json`，安装目录 `/tmp/datasourceRF-fallback-verify-20260917/site`；重型新用例用该安装包执行。C 盘仍约 14 GB 可用，未清理活动缓存或运行目录。
- 独立安装副本的两项变异验证均按预期失败：移除官方通道后，取数阶段测试因实际公告未被请求失败（3.86 秒）；移除标准证据行的 provider 后，测试在所选来源断言失败（5.45 秒）。日志分别为 `verification-25-mutation-without-official-20260917.txt`、`verification-25-mutation-without-provider-20260917.txt`。只改变 `/tmp/datasourceRF-fallback-mutations-20260917/` 的副本，不改正在运行的完整 Worker 输入；它们约束阶段/投影行为，不冒充完整 Worker 变异测试。
- Standards 最后复审确认时间硬问题关闭，现有证据行能经报告结构传递 provider，无新增硬问题；独立发布时间证据绑定仍待交付。复审只读，未运行测试。

## 下一步

2026-09-17 22:10 更新：完整 Worker 用例已取得终态 **1 passed in 2160.98s，exit=0**，会话64602结束，PID1480922已退出。安装和源码的99项初始指纹复核全部未变；终态回执为 `verification-25-full-worker-final-20260917.json`。它经过合成候选的准入、回放、隔离激活和完整 Worker，确认自动官方PPI采用与投影/报告交付来源一致；不是其他七项双通道或真实来源认证的完成证明。正在补当前安装包的适配器/账本/目录/阶段相关回归，然后保存这一已验证切片，再继续其余家族。

1. 观察已启动的完整 Worker 用例，处理真实失败后完成报告来源与移除适配器的变异证明；不要同时启动另一项材料构建。
2. 完成相关回归与两轴复审；设计可靠发布时间原件绑定，不能从采集时间倒推，也不能用未经绑定的规范化日期证明 PUBLIC。
3. 扩展并逐项验证剩余双通道，接通新目录的真实认证材料；再推进 #19、#20/#21、#22 依赖链。不能以本次软件切片替代真实认证、回放或切换。

## 22:22 已验证切片保存

完整 Worker 结果见上；后续102相关回归与2 targeted Worker路径均通过，日志分别为 verification-25-ppi-related-final-20260917.txt、verification-25-targeted-worker-final-20260917.txt。20个任务文件已提交45715b6，原272个未跟踪材料未提交或删除。下一步以公开取数阶段补CPI共享公告仅填缺失指标的反例。当前没有活动测试，旧“正在运行”记录只保留作历史。

## 2026-09-17 22:39 CPI切片已保存

继PPI提交45715b6后，CPI显式交付契约与共享公告按指标入库已提交 `955a2160a2b558edd819bfd43690f1c797f1641a`。独立安装包123相关用例通过，完整实施/红绿过程/审查修复见 [CPI记录](implementation-25-cpi-scope-20260917.md)。当前无活动测试；旧PPI完整Worker的通过只绑定45715b6前的输入，不冒充当前CPI代码的完整Worker验证。现支持八项中的CPI/PPI两项，余下PMI三项、M1/M2、SF总量、GDP六项及真实认证仍开放。下一步先补这些快速行为契约，再统一执行新输入的完整Worker混合回退和失败语义，避免反复重建重型材料。

## 2026-09-17 23:07 最新软件进度

PPI 45715b6、CPI 955a216 后，PMI 三指标提交 e19834e；详见 implementation-25-pmi-fallback-20260917.md。当前八项重叠完成五项阶段契约，剩余 M1/M2、SF 总量、GDP。当前新输入完整 Worker 尚未执行，不能复用旧 PPI 的重型通过结论。

## 2026-09-17 23:17 最新契约阶段

M1/M2 提交 07bd8f9，安装包相关 158 通过；六项阶段契约已验证，SF/GDP 待处理。M1/M2 Worker 尚未选择四字段参数，不代表自动刷新完成。参见 implementation-25-money-contract-20260917.md 和 plan-25-remaining-families-20260917.md。

## 2026-09-17 23:53 SF阶段保存

SF总量提交e2fd6a2，安装包169相关通过；七项有阶段契约，GDP尚未，M1/SF Worker接线仍开放。详见 implementation-25-sf-total-20260917.md。

## 2026-09-18 GDP 切片完成

提交 `0946735d706257bef44009beb270188e0ee901a4`，190安装包相关通过；四名义累计/拒收同比原件审计、季度目录及新期发现已验证。八必需成员和历史PUBLIC限制保持。详见 [GDP实施](implementation-25-gdp-fallback-20260918.md)。M1/SF Worker接线、当前完整运行、真实认证/回放/激活仍开放；不据此关闭整票。
