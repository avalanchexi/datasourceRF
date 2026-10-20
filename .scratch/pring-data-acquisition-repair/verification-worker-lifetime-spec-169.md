# Spec review — SQLite Worker lifetime, snapshot 169

Reviewed `git diff 99c495a217b66d4bca9d6ceae4688ee69d4382bb -- src/pring_cycle/storage.py src/pring_cycle/worker.py` and the two new lifetime test files. No intervening commits; other worktree changes excluded. All four reviewed file hashes match `verification-worker-lifetime-inputs-169.json`. Read-only review; no tests executed.

## Findings

1. **[P2] Shutdown ordering remains unverified.** Issue 17:39 requires “先有公开回归反例，再验证任务、心跳及查询交叠”; the slice contract, `implementation-17-sqlite-lifetime.md:35`, further requires “心跳线程必须退出后才释放租约和保留连接”. The new test proves a query can survive a heartbeat close during execution, but its fixture starts a separate executor heartbeat and waits for it before returning from the retrieval adapter (`tests/fixtures/worker_sqlite_lifetime.py:33-54`). It therefore does not arrange an outstanding production heartbeat when Worker cleanup begins. Reverting only `heartbeat.join()` to the old one-second join at `src/pring_cycle/worker.py:202-206` can leave this regression green. Add a public lifecycle case with a genuine production heartbeat still writing when execution completes, is cancelled, or raises; verify it finishes before lease release and final close, preserving the observable terminal state. The outer `run_worker` keeper/stop path at `worker.py:95-110` also lacks a direct lifecycle check in this slice. This is an acceptance gap, not evidence that the new ordering itself is incorrect.

## Scope and evidence

No production implementation defect or scope creep found. The keeper opens a pager without retaining a transaction (`storage.py:30-39`); per-operation connections remain separate. Cancellation/error branches retain their existing behavior, while cleanup now waits for the actual heartbeat thread before releasing its lease. This respects ADR-0007:7-9 and ADR-0010:7.

The native 165 trace shows successful exclusive locking at line 1185 and delayed `sqlite3WalCheckpoint -> sqlite3WalClose` fsync at lines 1216-1220. Its child reports `SQLITE_BUSY` after 5.037 seconds; keeper-166 reports query success in 0.116 seconds without an open transaction; RED-167 fails at the public query assertion. These establish the reproduced slow-last-connection-close failure class. They do **not** identify the unrecorded historical59 lock holder; the implementation note correctly preserves that limit. Same-version related/full verification remains required by issue 17:39 and is not certified by this review.

Spec findings: **1 verification gap; 0 demonstrated implementation defects.**
