# Standards review — native verification environment, batch 176

Read the 175 diagnosis, 173/174 profile receipts, environment installer/verifier, native shell runner and durable 176 driver (including its referenced verifier). No installation or tests run. Independently checked all 233 inputs and four protected files against freeze 172: no mismatch.

## Documented standards

No hard repository-standard violation identified. The environment follows ADR-0007's native WSL storage boundary and the repair spec's isolated verification requirements. Experiment 174 retains the original 64 iterations/30-second watchdog and verifies all 95 application files plus the execution fingerprint. It supports the documented DrvFS diagnosis without replacing original regression acceptance. Batch 172's failure remains recorded.

The native runner removes `PYTHONPATH`, uses an installed package, checks interpreter bytes, exact dependency versions, application bytes and frozen inputs before/after testing, and runs the postcheck even after pytest fails. These checks do not substitute a permissive test implementation. Dependency equality is version equality; the scripts do not claim or establish byte-for-byte equality of every dependency distribution.

## Material harness findings

1. **[P2] Driver process reports success on recorded failure** — `verification-worker-lifetime-durable-176.py:103-117`. `precheck_failed`, `failed` and `harness_failed` are written into JSON, but execution then falls off the script with exit status zero. A caller relying on the process result can treat failed validation as success. Preserve the detailed receipt and exit nonzero unless final status is `passed`.

2. **[P2] Harness errors can leave an untracked test process running** — `verification-worker-lifetime-durable-176.py:60-70,108-115`. A `save_running()` failure after `Popen` but before `wait()` reaches the outer exception handler without terminating or waiting for the child. The handler then deletes `child_pid` and may write a terminal `harness_failed` receipt while the shell/pytest process still operates on the mounted volume. Give `run_phase` explicit child ownership through `try/finally`; on errors, preserve its identity, stop/reap the owned process tree and allow/verify volume cleanup before marking the phase terminal.

## Result and evidence boundary

0 hard standards violations; 2 P2 harness lifecycle findings; no additional actionable baseline smells. Neither finding proves batch 176 failed. **Runtime conclusions must come from its real terminal JSON, each actual phase exit code and corresponding complete logs; launch success, driver exit zero and experiment 174 alone are insufficient.** This review does not claim batch 176 passed.
