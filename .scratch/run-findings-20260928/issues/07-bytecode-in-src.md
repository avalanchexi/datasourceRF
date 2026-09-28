Status: wontfix
Category: chore
Type: task

# 07 — 源码目录残留字节码

## 原始发现

- 全套中 `tests/e2e/test_local_runtime_cli.py::test_installed_cli_keeps_bytecode_outside_the_source_tree` 失败：`src/pring_cycle/__pycache__` 里有 9/26 00:24 用系统 Python 3.10 生成的 `breadth.cpython-310.pyc`。有人直接从 `src/` 导入调试，没有加 `PYTHONDONTWRITEBYTECODE=1`。
- 已删除（目录被 git 忽略，没有受版本控制的文件），单独复跑通过。

只作记录，不需要实施。
