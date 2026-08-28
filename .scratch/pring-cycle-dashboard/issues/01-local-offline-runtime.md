# 01 — 本机离线启动与 doctor

**What to build:** 让个人用户在干净 WSL2 环境中以统一 CLI 初始化并检查本机应用，离线启动 Web 与独立 Worker，并从浏览器看到只绑定本机的健康页；这条最小纵切同时建立后续功能共用的运行、配置、存储和验收接缝。

**Blocked by:** None — can start immediately

**Status:** ready-for-human

- [x] 无项目凭据、无 CLI 登录、无网络时，初始化、`doctor`、Web 启动和 Worker 启动均有稳定结果。
- [x] Web 只绑定 `127.0.0.1`，健康页能区分 Web、Worker、SQLite/Alembic 和内容寻址制品目录状态。
- [x] 运行状态、SQLite、WAL、日志、制品和密钥均位于 WSL 原生仓库外目录，源码目录和 Windows 挂载项目目录不产生运行写入。
- [x] 密钥配置使用仓库外 `0600` 文件；日志、错误、页面和验收输出不包含密钥值或认证头。
- [x] 统一无网络验收命令可以在临时运行目录中启动、探活并停止 Web 与 Worker，且重复执行保持幂等。
- [x] `doctor` 明确显示 `backup_mode=none`、RPO/RTO 不保证以及缺少凭据只禁用相应外部能力而不阻止离线启动。
- [x] 不受信 Origin 无法追加命令，并有外部行为测试锁定该边界。
- [x] 开发文档说明环境、目录、安全边界和统一验收入口。

## Comments

- 2026-08-28：开始实施；公开测试接缝固定为统一 CLI、健康页/API 和命令 Origin 边界。
- 2026-08-28：实现与双轴代码审查完成。离线 `verify`/`test`、原子制品往返、默认 XDG、目录拒绝、未初始化失败和 Origin 负例均由外部行为测试覆盖。完整 Markdown 正文安全渲染由 Ticket 20 落地，升级失败的 `reinitialize_required` 由 Ticket 21 落地；Ticket 01 不提前创建这两条后续业务路径。
- 2026-08-28：复审收口。密钥解析边界仅接受 Tushare、Tavily、Exa 三类数据源字段；WSL 原生虚拟环境改为非 editable 安装，并由正常 CLI 外部行为测试确认源码树不产生字节码写入。最终完整回归为 11 个 Python 测试及既有前端原型合约测试全部通过。
