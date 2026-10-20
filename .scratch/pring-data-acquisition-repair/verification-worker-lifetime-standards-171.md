# Standards follow-up — SQLite Worker lifetime, batch 171

Reviewed the final five-file scope against `verification-worker-lifetime-inputs-171.json`; all five current hashes match. Production `storage.py` and `worker.py` are unchanged from review 169. Read-only review; no tests run. Standards sources and baseline remain those listed in `verification-worker-lifetime-standards-169.md`.

## Previous findings

1. **Resolved: buffered stdout could conceal completion.** `tests/integration/test_worker_database_lifetime.py:83-107` now reads the selected descriptor with `os.read`, frames every complete newline-delimited message explicitly, and carries any partial bytes into the final output parsing. Both events in one pipe read are consumed before waiting again.

2. **Resolved: cleanup killed only the tracer.** `tests/integration/test_worker_database_lifetime.py:68,108-112` creates a dedicated session and kills its process group when communication has not completed, then reaps the process. The new shutdown test applies the same ownership pattern at lines 147 and 180-188, closes its parent pipe ends, and releases its gate during failure cleanup.

## Added shutdown regression

`tests/fixtures/worker_heartbeat_shutdown.py:25-38` retains real SQLite SQL, transaction completion and close; only scheduling at the external database close boundary is controlled. It exercises the actual periodic heartbeat, with no production testing hook. The integration test observes durable `action_required`, attempts lease acquisition while the heartbeat is held, then releases the heartbeat and verifies the lease becomes acquirable (`tests/integration/test_worker_database_lifetime.py:160-179`). This follows the repair spec's accepted public Worker/persistent-state testing boundary.

The new test's single `readline()` after readiness does not recreate finding 1: its child cannot produce the later `worker_returned` message until the parent sends `finish_run` and releases the separate close gate.

## Result

**0 documented-standard violations; 0 actionable baseline smells; 0 new material resource/concurrency hazards identified. Both prior P2 findings are resolved by inspection.** Runtime verification remains the root agent's separate responsibility; this report does not claim tests passed.
