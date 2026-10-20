# Standards review — SQLite Worker lifetime, batch 169

Reviewed `git diff 99c495a217b66d4bca9d6ceae4688ee69d4382bb -- src/pring_cycle/storage.py src/pring_cycle/worker.py` and the two new test files. No commits in this slice. All four current file hashes match `verification-worker-lifetime-inputs-169.json`. Read-only review; no tests run.

Sources: `AGENTS.md`, `docs/agents/domain.md`, `docs/agents/issue-tracker.md`, `CONTEXT.md`, ADR-0007/0010, the repair spec and `implementation-17-sqlite-lifetime.md`.

## Documented standards

No hard violation found. The change retains ADR-0007's single Worker / SQLite architecture and ADR-0010's existing lease and explicit-run semantics. Storage owns the pager-lifetime detail; the retained connection is not passed between threads or used for application writes. Joining the heartbeat before releasing the lease and retained connection preserves the stated cleanup invariant.

## Resource and concurrency hazards

1. **[P2] Buffered stdout can conceal the completion event** — `tests/integration/test_worker_database_lifetime.py:75-87`. The selector observes the OS pipe, but `process.stdout.readline()` reads through a buffered `TextIOWrapper`. If `query_window` and `heartbeat_finished` arrive together, the first call can prefetch both lines while returning only the first. The next selector call sees an empty pipe although the second line remains in the Python buffer. The fixed implementation has no closing lock to supply the alternative trigger, so this passes into the 40-second failure path despite a completed heartbeat. Use an unbuffered binary pipe with explicit line framing, or a reader thread feeding a queue.

2. **[P2] Failure cleanup does not own the traced child** — `tests/integration/test_worker_database_lifetime.py:100-103`. The `Popen` PID is `strace`; `kill()` targets only that process. A timeout or assertion can leave its traced Python child, heartbeat threads and inherited pipes alive, and the subsequent `communicate(timeout=15)` can itself time out. Launch a dedicated process group/session and terminate the group on cleanup, then reap the tracer; alternatively use a supported tracer option that guarantees tracee termination when the tracer exits.

## Baseline smells

No actionable Fowler smell identified in the production diff. The two findings above are test lifecycle correctness hazards, not invented hard repository rules.

**Result:** 0 documented-standard violations; 0 baseline smells; 2 P2 test-harness hazards.
