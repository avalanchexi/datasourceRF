Status: needs-triage
Category: enhancement
Type: task

# 29：补算证据运行级预载；WAL `synchronous` 取舍（票 24 剩余热点）

## 现象（票 24 连接池合入后剖析，2026-10-10）

同一节点（`test_gap_source_repairs.py::test_treasury_yields_are_held_from_tushare_us_tycr`）剖析，连接池合入后一次完整运行的分布：补算约 54%，检索约 20%，背景源刷新约 14%，evaluate 约 7%。主要热点：

- `EvidenceRepository.metric_series` 1.35 万次，约 30 秒，占剖析总时长约 27%；`select_warrant_inputs` 约 20 秒（约 18%，与前者重叠）。`evidence.py:1144` 已有预加载分支，但只支持 `public_as_of=None`，生产路径未用；逐日补算带公开截止点（`day_summary.py:387`）。
- `commit` 7.1 万次，约 9.5 秒（约 8%），一次运行 10,953 次 fsync。WAL 默认 `synchronous=FULL`。

## 待分流时确认

- 预载：限定生命周期的运行级证据快照或批量读取，必须保持双时间边界（系统截止／公开截止）、修订冲突、资讯复核与模型版本语义；涉及 `evidence.py`、`day_summary.py`、`context_projection.py`。
- `synchronous=NORMAL`：WAL 下断电可能丢最后几笔已提交事务，但不损坏库；属耐久性取舍，需用户决定。

## Comments
