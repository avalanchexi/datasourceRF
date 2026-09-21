Status: ready-for-agent
Type: task-batch
Date: 2026-09-21

# 可并行任务组（验证成本收口的后续）

## 调度约束（先读这一条）

**重型计算仍然串行，一次只跑一个。** 这台机器 9.7 GB 内存 / 12 核，一轮完整套件的
`--basetemp` 会涨到 20 GB 以上；2026-09-20 就发生过一轮在跑、另一轮启动，双双被系统杀掉。
本文件的 P1–P4 之所以可以并行，是因为它们**都不运行重型验证**：三项只读调查加一项目录清理。

**P2 与 P3 只调查，不得改代码。** 两者都在读 `src/pring_cycle/commodity_basket.py`，
同时改会互相覆盖。它们的产出是判断与清单，改动由后续切片按结论统一进行。

完整套件按 [ADR-0014](../../docs/adr/0014-full-suite-only-at-freeze-points.md) 需要显式
`tools/check.py full --freeze`，本组任何一项都不触发它。

## P1 · 清除源码树内的字节码，使基线全绿

2026-09-21 基线为 1891 passed / 1 failed，唯一失败是
`tests/e2e/test_local_runtime_cli.py::test_installed_cli_keeps_bytecode_outside_the_source_tree`。
它守的是 [本机开发与运行](../../docs/development/local-runtime.md) 的边界：字节码不得写回
位于 Windows 挂载盘的源码树。源码树内现存三个目录，时间戳为 2026-09-19 20:20，来自某次
直接以 `src` 在导入路径上运行 Python，早于本轮全部操作。

- 删除 `src/pring_cycle/__pycache__`、`src/pring_cycle/domain/__pycache__`、
  `src/pring_cycle/migrations/__pycache__`
- 复验：`pytest tests/e2e/test_local_runtime_cli.py::test_installed_cli_keeps_bytecode_outside_the_source_tree`
- 这是真实的边界违例，不是测试缺陷；不要修改该测试的断言

完成证据：该用例通过，且 `find src/pring_cycle -name __pycache__` 为空。

## P2 · 查清 JSON 重复解析的 65 秒（只读）

对 `tests/integration/test_worker_registered_catalog.py::test_full_worker_falls_back_to_official_ppi_and_exposes_delivery_in_report`
取 cProfile，`json/decoder.py:raw_decode` 为 **548,960 次调用 / 65.01 秒**，占该用例约 13.8%。
已知 `_commodity_document`（`commodity_basket.py:383`）每次调用会 `json.loads` 同一快照的
`raw` 与 `normalized` 两份，但它自身只有 440 次调用，远不足以解释 54.8 万次。

需要回答：

1. 这 54.8 万次解析的调用点分布，按次数排序
2. 其中有多少是**同一份字节被反复解析**（同一 `raw`/`normalized`/制品文件）
3. 若存在重复，一次解析后传对象是否会破坏现有的身份校验语义
   （`_commodity_document` 用 `document != json.loads(snapshot.normalized)` 做一致性判定，
   以及 `receipt.parameters` 中的 `result_hash`——解析结果复用不得让这些校验失去意义）

产出：写入 `.scratch/pring-data-acquisition-repair/finding-json-decode-cost-20260921.md`，
含调用点清单、重复率、以及"能否安全复用"的结论与理由。**不改任何源码。**

## P3 · 查清 `_commodity_facts` 的 24.63 秒（只读）

同一份 profile 中 `_commodity_facts`（`commodity_basket.py:319`）为
**53,848,240 次调用 / 2,200 个顶层入口 / 24.63 秒**。它是无缓存的递归遍历，
三个调用点：`_commodity_publication`（377 行）、406 行、465 行。

需要回答：

1. 这三个调用点是否在同一次处理中对**同一个 `result`** 各遍历一次
2. 若是，一次遍历产出三处各自需要的东西是否可行，三者分别需要什么
3. 这样做会不会改变任何一处的语义（注意 `_commodity_publication` 对 `None` 的处理：
   任一 `public_available_at` 为空即整体返回 `None`）

产出：写入 `.scratch/pring-data-acquisition-repair/finding-commodity-facts-cost-20260921.md`。
**不改任何源码。**

## P4 · 本轮改动的静态检查（只读）

本轮已改动：`src/pring_cycle/commodity_basket.py`、`tools/check.py`、
`tests/adapters/test_commodity_basket.py`。

```bash
export PRING_CYCLE_DEV_ENV="${XDG_DATA_HOME:-$HOME/.local/share}/pring-cycle/dev-venv"
UV_PROJECT_ENVIRONMENT="$PRING_CYCLE_DEV_ENV" uv run --no-editable mypy
UV_PROJECT_ENVIRONMENT="$PRING_CYCLE_DEV_ENV" uv run --no-editable ruff check src tests tools
```

注意：改源码后必须 `uv sync --extra dev --no-editable --reinstall-package pring-cycle`，
否则检查到的是虚拟环境里的旧副本（见本机开发与运行的"源码改动后必须重装"）。

产出：报告全部问题，不自行修复超出本轮改动范围的既有告警。

## 串行项（不进本组）

- **S1 收益测量**：`_commodity_meaning_equal` 改动前后对同一用例的耗时对比（改动前 271 秒）。
  正在进行，是 S2 的前提。
- **S2 提交**：需 P4 通过且 S1 有数字后进行。
- **S3 重型验收**：一次一个，需 `--freeze`。

## 与 P2/P3 结论的衔接

两项合计 89.6 秒，占该用例约 19%，是 `_commodity_meaning`（75.07 秒）之后最大的两块。
它们的结论决定后续切片是否值得开，以及应当如何改；结论为"不可安全复用"同样是有效产出，
应当写明理由，避免下一轮重新调查一遍。
