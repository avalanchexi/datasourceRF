# 后续步骤规划（2026-09-16，基线 HEAD `8039b69`）

本文件供跨会话接手使用。当前两个 Claude 会话并行，只允许同时运行一个重型本地任务。

## 已收口

- 票19 隔离生命周期材料；票17 Worker 注册目录纵向验收（`31735d6`）；#16 回放上下文输出去重（`4618af7`，630MB→52MB）；代码健康两项（`2b0e4ad`）；美债时钟定时炸弹（`1fa16c5`）。
- 联合回归 `8039b69`：903 项通过、0 失败。

## 步骤

### 步骤1：票22 计时规则纵向切片（现在就能做）

`issues/22-live-acceptance-cutover.md` 的「2026-09-13 计时规则独立纵向切片」，`Software blocked by: None`。未勾选项：统一验收生成端与切换消费端的计时口径；600秒作为优化目标而非硬门（硬门全过而仅时长超标不判失败，但实测值、计时范围与未达目标可见）；区分内部阶段计时与 pytest 全程总耗时，标明故障注入等阶段是否计入；不改写历史通过标记。

做法：`/mattpocock-skills:implement`，TDD、干净检出验证、两轴 `/code-review`、提交。预计不触发材料重建（除非改动 src 或构建器）。

### 步骤2：冻结同版本默认全套（票22 列出的最终软件验收）

前置：09 必要容量改动、12 商品软件交付、17 Worker 必要改动、19 完整隔离生命周期材料/Q1、22 计时切片——前四项已收口，只差步骤1。

做法：冻结同一源码、依赖、安装包与输入，在干净检出上跑全部无网络功能测试、相关回归、故障恢复、性能硬门、前后指纹核验与两轴审查。十分钟是优化目标，不删测试凑时限，不以旧的 1287 项或专项之和替代。重型，按分组顺序跑、通过即删 basetemp，保留失败现场。

### 步骤3：记录与关闭

以步骤2的结果分别更新票17、票19、票22 的勾选项与 continuation-status；`verification-*` 记录随各票提交。

### 步骤4：外部阻塞项（需要用户授权或材料，代码侧推不动）

- 票13/14：官方样本与来源认证原件，需要授权的有界抓取。
- 票18：一条实际可达且已授权的 CLI 网络路径。
- 票20：Tavily/Exa 对照检索。
- 票21/22 真实部分：真实120日回放与当前目标日切换。

处理方式：用 `/mattpocock-skills:to-questionnaire` 把所需授权、账号、样本整理成一份问卷交给用户；拿到后再按票推进。

### 步骤5：常态代码健康

`/mattpocock-skills:improve-codebase-architecture` 定期巡检；已知小项：`tests/adapters/test_commodity_basket.py` 20 个既有 mypy 报错（`**dict` 调用）。

## 执行守则（每步都适用）

1. 重型任务同一时间只跑一个；开跑前先告知另一会话。
2. 开跑前 `df -h /mnt/c`：低于 8GB 先清理（只清与任务无关的 Windows 临时文件和缓存），低于 2GB 立即停止。
3. 守护：可用内存 <1.5GB 或 C 盘 <2GB 即终止并保留现场；`-o tmp_path_retention_policy=failed`。
4. 改 `src/`、`tests/conftest.py`、`tests/models/test_candidate_admission.py`、`tests/models/test_isolated_lifecycle.py`、`tests/adapters/test_commodity_basket.py`、`tests/fixtures/isolated_lifecycle_inputs.py` 会使隔离材料失效（重建约30分钟），尽量把重建攒到一次。
5. 读材料数据库一律 `immutable=1`，或先复制再读。
6. 每张工单开工前 `/clear`，保持在高质量推理区间。
7. 提交只列本票归属文件；`src/pring_cycle/assets/dashboard.css|js` 属于其他工作，不要带入。
