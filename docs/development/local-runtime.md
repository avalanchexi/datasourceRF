# 本机开发与运行

## 环境边界

V1 运行在 WSL2，源码可以位于 `/mnt/d/cursor/datasourcerf`，但 Python 环境和全部可变
运行状态必须位于 WSL 原生文件系统。不要把虚拟环境、SQLite、WAL、日志、制品或密钥放在
`/mnt/c`、`/mnt/d` 等 Windows 挂载目录。

需要已安装的 `uv`。项目的 `.python-version` 会让 `uv` 获取并使用 Python 3.12。源码在
Windows 挂载盘时，按下面方式把项目虚拟环境放入 WSL 原生 XDG 数据目录：

```bash
export PRING_CYCLE_DEV_ENV="${XDG_DATA_HOME:-$HOME/.local/share}/pring-cycle/dev-venv"
UV_PROJECT_ENVIRONMENT="$PRING_CYCLE_DEV_ENV" uv sync --extra dev
export PATH="$PRING_CYCLE_DEV_ENV/bin:$PATH"
```

`uv.lock` 固定 FastAPI、Dash 4.2、SQLAlchemy、Alembic 和其他依赖版本。应用启动和日常离线
验收不安装依赖，也不访问包索引。

## 初始化与诊断

首次运行显式初始化，然后执行诊断：

```bash
pring-cycle init
pring-cycle doctor
```

默认目录为：

| 内容 | 默认路径 |
| --- | --- |
| 普通配置与密钥 | `${XDG_CONFIG_HOME:-$HOME/.config}/pring-cycle/` |
| SQLite、WAL 与内容寻址制品 | `${XDG_DATA_HOME:-$HOME/.local/share}/pring-cycle/` |
| JSONL 日志与运行状态 | `${XDG_STATE_HOME:-$HOME/.local/state}/pring-cycle/` |
| 可重建缓存 | `${XDG_CACHE_HOME:-$HOME/.cache}/pring-cycle/` |

测试和一次性验收可以传入 WSL 原生临时目录：

```bash
PRING_CYCLE_VERIFY_ROOT="$(mktemp -d)"
pring-cycle init --runtime-root "$PRING_CYCLE_VERIFY_ROOT"
pring-cycle doctor --runtime-root "$PRING_CYCLE_VERIFY_ROOT" --json
```

`init` 是幂等的。它创建 SQLite WAL、升级到当前 Alembic head，并建立
`artifacts/sha256` 内容寻址目录。制品先写入同目录临时文件，校验 SHA-256 后原子改名，
最后才在 SQLite 登记字节数、媒体类型与来源引用，因此数据库不会指向半文件。Web 和
Worker 不会隐式初始化；未初始化时固定返回 `runtime_not_initialized`，也不会创建运行文件。

`doctor` 会报告 Python 版本、`uv.lock`、运行路径、SQLite/WAL、Alembic、制品注册表和三个
数据源适配器的启用状态。缺少凭据只把对应外部能力标记为 `disabled`，不阻止离线启动。

## 密钥边界

密钥文件为仓库外的 `secrets.env`，权限由应用保持为 `0600`。只允许配置：

```dotenv
TUSHARE_TOKEN=
TAVILY_API_KEY=
EXA_API_KEY=
```

不要提交真实值。应用不会把值或认证头写入 CLI 输出、浏览器、日志、报告或验收结果。
Codex CLI 与 Claude Code CLI 的登录状态不由应用读取或保存；Ticket 01 的离线启动不要求任一
CLI 已登录，也不接收模型厂商 API key。

## 启动 Web 与 Worker

在两个 WSL 终端中使用同一正式 CLI：

```bash
pring-cycle worker
```

```bash
pring-cycle web --port 8050
```

Windows 浏览器访问 `http://127.0.0.1:8050/`。Web 只绑定 `127.0.0.1`；没有可配置的
局域网监听地址。健康页与 `/api/v1/health` 分别显示 Web、Worker、SQLite/Alembic 和制品
目录状态。关闭页面或停止 Web 不会停止独立 Worker。

启动 Web、打开页面或启动 Worker 都不会补跑任务、联网、刷新证据或调用 AI。浏览器命令入口
同时校验 `Host` 和 `Origin`；不受信网页得到脱敏的 `403`，不能进入后续命令追加接缝。

## 统一离线验收

以下命令在临时 SQLite 和制品目录中重复初始化，执行原子制品写入/登记/读回，启动正式
Web 与 Worker，执行健康探测和恶意 Origin 负例，最后停止两个进程：

```bash
PRING_CYCLE_VERIFY_ROOT="$(mktemp -d)"
pring-cycle verify --runtime-root "$PRING_CYCLE_VERIFY_ROOT" --json
pring-cycle verify --runtime-root "$PRING_CYCLE_VERIFY_ROOT" --json
```

两次应得到同一稳定文档，包含 `network_requests=0` 和 `processes=stopped`。验收只连接
`127.0.0.1`，不需要项目凭据或 AI CLI 登录。`pring-cycle test` 是同一验收入口的别名，
不会建立第二套测试编排路径。

开发检查使用同一 WSL 原生虚拟环境：

```bash
UV_PROJECT_ENVIRONMENT="$PRING_CYCLE_DEV_ENV" uv run pytest
UV_PROJECT_ENVIRONMENT="$PRING_CYCLE_DEV_ENV" uv run mypy
UV_PROJECT_ENVIRONMENT="$PRING_CYCLE_DEV_ENV" uv run ruff check src tests
```

`pring_cycle.domain` 提供框架无关的正式阶段、核心资产状态和证据/模型/投影/运行/报告身份
边界类型；导入它不会加载 Web、SQLite 或网络框架。

## 无备份风险

`doctor` 固定显示 `backup_mode=none`，运行数据 RPO 与 RTO 均为 `not_guaranteed`。V1 不创建
日常备份、升级前快照、Windows 副本或通用 `backup` 命令。GitHub 只恢复源码、迁移和静态
定义；SQLite、证据、报告、日志或密钥丢失后，只能尽力重新初始化，不能重建原来的系统点时
历史。
