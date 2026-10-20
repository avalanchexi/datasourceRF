# Spec review — native verification environment, 176

Read-only review of diagnosis 175, actual 173/174 records, preparation/verification scripts 175, native wrapper 175, and durable driver 176. No installation, application modification, or test execution performed. Independently rehashed frozen172: **233 inputs and 4 protected files match**, including unchanged application and tests.

## Findings

**0 spec defects found.** Moving the verified installed package/dependencies to the owned ext4 verification volume preserves the SQLite acceptance contract; it does not weaken assertions or replace the failing workload.

- Actual 173 retains the 30-second watchdog and reports timeout after 19 completed rounds; fingerprint work totals 25.335 seconds and observed descriptors remain five. Its five stack samples identify DrvFS package reads/scans/stat. Actual 174 executes the original extracted child string, including 64 rounds, disabled GC and descriptor limit 128, with the same 30-second timeout (`test_runtime_views_native_174.py:27-32,47-60`). Its 95 copied package-file hashes and original/result fingerprints match; child completion is 4.421 seconds. The recorded scope remains an isolated counterfactual, not complete regression acceptance.
- Preparation175 uses the same base executable and exact dependency versions, installs offline, and compares actual original/native package bytes (`test_native_environment_175.py:26-53`). Native verifier175 checks interpreter hash, exact dependency set, frozen inputs, installed sources and all 95 package files. The shell wrapper removes PYTHONPATH, invokes the installed native interpreter, and performs its postcheck even after test failure (`run-native-175.sh:26-35`).
- Driver176 preserves all five original172 test selections and adds the two native lifetime cases through their test file (`verification-worker-lifetime-durable-176.py:17-24`). It neither increases the original watchdog nor treats diagnostic174 as the original test passing. Diagnosis175 correctly preserves failed172 and distinguishes this performance issue from the reproduced WAL-close fault.

## Outstanding execution evidence

**176 is not certified passed by this review.** Its outer `runtime_before/runtime_after` checks still inspect the old DrvFS environment (`durable-176.py:13,85,102`). Final acceptance must additionally inspect the actual native before/after receipts produced inside the mounted wrapper: `verification-native-runtime-before-official-worker-lifetime-joint-176.json` and corresponding `after` file, plus the real terminal/test log. The outer checks alone do not establish native execution identity. Issue17:39 still requires same-version related and full verification; neither successful preparation nor counterfactual174 closes that gate or identifies historical59's unrecorded lock holder.
