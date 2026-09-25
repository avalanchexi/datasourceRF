Status: done
Type: task

# 01 — check.py 按内容比对安装副本

**问题：** 2026-09-25 验收误用仓库内旧 `.venv`（7 个模块内容与 `src/` 不同），`tools/check.py` 的 `_stale_environment` 只比顶层 `*.py` 文件名，未报；子包（`domain/`、`migrations/`）与资源文件也不在比对范围。

**修复：** 新增 `_package_drift(tree, installed)`，递归比对包内全部文件的字节内容（排除 `__pycache__`/`.pyc`），分别列出 missing / stale / changed。`docs/development/local-runtime.md` 的“数文件个数”核对改为说明 check.py 的内容比对。

- [x] 内容不同、子包增删、完全一致三例（`tests/maintenance/test_check_tool.py`）
- [x] 当前 dev-venv 实测：同步时返回 `None`；改源码未重装时报 `changed 1: tushare_context.py`
- [x] 树侧按 `git ls-files -co --exclude-standard` 筛选（hatchling 打包跳过 git 忽略文件，否则会误报 missing），git 不可用时退回全量；新增例覆盖

## Comments

- 2026-09-25 Codex 只读复核：源码与 dev-venv 各 112 个非字节码文件、字节数一致；指出 hatchling 按 `.gitignore` 排除导致的 missing 误报边界，已修。
- 2026-09-25 验证（01–03 合并一轮，dev-venv 重装后）：受影响 28 个文件 `check.py quick` 569 例过，用时 2137.8 秒（超 180 秒目标：文件多且含检索集成用例，照实记录）；切片冒烟 2 例过，86 秒；完整目录正例 `test_worker_registered_catalog.py` 1 例过，133 秒；三核心反例 `test_core_carry_forward.py` 3 例过，185 秒。C 盘始终 67G 余量。
