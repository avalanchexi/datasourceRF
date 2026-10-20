# Standards follow-up — durable native verification driver, batch 177

Read-only incremental review of `verification-worker-lifetime-durable-177.py`, its referenced verifier and the unchanged native runner. Reviewed driver SHA-256: `d1c7ad062e159eb4db52cf6441aba8894cc06f4e47dc113062da389d2e01b17d`. No tests, installation or application edits performed. Review 176's standards sources and native-environment evidence boundaries remain applicable.

## Previous findings

1. **Resolved: failure propagation.** `verification-worker-lifetime-durable-177.py:151` exits zero only for final `passed`; recorded precheck, test, postcheck and harness failures produce a nonzero driver exit. Tests passing cannot override failed native receipts or changed helper inputs.

2. **Resolved for the identified persistence-error path: child ownership.** Lines 71-83 put the wait in `finally`, record the reaped child PID and actual exit code, and reject a pytest wrapper that returns while the test volume remains mounted. A `save_running()` failure therefore cannot reach the outer terminal-writing handler before the already-started wrapper finishes. Waiting for the authorized work preserves fixture/postcheck/unmount cleanup and is an acceptable alternative to killing it. During that wait, the driver is still running; no terminal result is issued.

## Additional verification

Native before/after receipt documents, sizes and hashes are bound into the final record (lines 116-129). The driver, both verifiers, shell wrapper, installation receipt and frozen manifest are hashed before execution and compared after execution (lines 32-41,137-142). Changed helpers cannot produce `passed`.

The empty explicit test list invokes the repository's default `tests` collection, as defined by `pyproject.toml:32-34`; it does not skip pytest. This is broader than the prior associated subset, and runtime acceptance must use the actual collected/executed count and terminal output.

## Result

**0 documented-standard violations, 0 actionable baseline smells, and 0 new material hazards identified. Both review-176 findings are resolved in this follow-up driver.** This is source review only: it does not establish that batch 177 ran or passed. Any later runtime claim requires the real terminal record, complete pytest result and successful associated pre/postchecks.
