# Spec follow-up — SQLite Worker lifetime, 171

Reviewed the new `tests/fixtures/worker_heartbeat_shutdown.py`, both cases in `tests/integration/test_worker_database_lifetime.py`, and the proposed existing CLI startup/stop coverage. Production `storage.py` and `worker.py` hashes still match frozen snapshot 169. Read-only review; these new tests have not been executed or certified by this review.

## Prior finding

The principal cleanup-order coverage gap from Spec-169 is **addressed in test design, pending execution**. The new fixture uses the Worker's real normal-period heartbeat and real SQLite SQL/commit/close. It pauses scheduling immediately before real connection close, after commit, so task-terminal writes can proceed while the heartbeat is still outstanding (`worker_heartbeat_shutdown.py:25-43`). The parent observes `action_required`, waits beyond the old one-second join, requires a competing public lease acquisition to fail, releases the heartbeat, and then requires Worker return plus successful subsequent lease acquisition (`test_worker_database_lifetime.py:160-179`). This meaningfully distinguishes the old cleanup sequence without replacing Worker or RunRepository behavior or fabricating evidence. It implements the ordering contract in `implementation-17-sqlite-lifetime.md:35`.

## Remaining finding

1. **[P2] Existing CLI cleanup cannot certify graceful Worker shutdown.** The slice promises coverage for “Worker服务整个循环” (`implementation-17-sqlite-lifetime.md:34`), and issue 17:39 requires same-version related lifecycle verification. The proposed `test_web_and_worker_start_offline_as_independent_local_processes` calls `stop_process(worker)` but does not assert successful graceful exit (`tests/e2e/test_local_runtime_cli.py:291-297`). Its helper silently falls back from SIGTERM to SIGKILL after five seconds (`:89-97`). Consequently a regression that hangs the newly wrapped `run_worker` exit can still pass this test. Assert the Worker exits normally and records `worker_stopped`, while retaining forced cleanup only for test-finally recovery. This is a remaining verification gap, not a demonstrated production fault.

No new production/spec mismatch or scope creep found. The revised native query test still preserves unresolved evidence as `action_required`; subprocess group cleanup and byte-oriented message reading do not alter product behavior. Cancellation/error handling remains the unchanged common Worker path, whose related regression execution is still pending. Reproduced slow WAL last-close locking remains distinct from the unrecorded historical59 lock holder.

Spec findings: **1 remaining verification gap; 0 demonstrated implementation defects.** No runtime pass claim.
