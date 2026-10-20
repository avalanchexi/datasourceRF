# Standards review — historical Q1 catalog fixture, batch 179

Read-only review of `tests/models/test_capacity_historical_contract.py`, fixture README/provenance and the relevant runtime/source-contract boundaries. No tests, installation or database mutations performed. All 247 inputs and four protected files match freeze 179; every file shared with freeze 172 is unchanged. Independently matched the snapshot database hash and all ten artifact hashes/lengths to provenance.

## Documented standards

No hard standard violation found. The six parameter combinations exercise public model, evidence, task, retrieval-selection and context-projection interfaces. Positive selection/actual-use checks precede each missing/damaged dependency; negative checks retain diagnostic observation identities and model immutability. Fault injection affects only the per-case copied runtime, with no shared fixture mutation or production testing hook.

The copied historical manifest is asserted to lack the service marker; the test never obtains that state by rewriting a current admitted manifest. This follows `implementation-19-capacity-mapping.md`'s explicit historical-compatibility boundary and the repair spec's observable-behavior tests. README/provenance clearly identify synthetic state and exclude real certification/activation/replay acceptance claims. Native `RuntimePaths.discover` policy remains effective.

## Delivery finding

**[P2] Required fixture bytes are excluded by Git ignore rules** — `tests/models/test_capacity_historical_contract.py:26-39`. The test unconditionally reads the archived SQLite database and ten CAS artifacts. `git check-ignore -v` confirms `.gitignore:19` (`*.sqlite3`) excludes the database and `.gitignore:27` (`artifacts/`) excludes every artifact. `git ls-files` currently contains none of this fixture; ordinary `git status --untracked-files=all` exposes only README/provenance. Ordinary staging of this directory therefore omits required test inputs, producing `FileNotFoundError` on a clean checkout. Before landing, explicitly include the exact synthetic database/artifact allowlist (or provide a narrowly scoped fixture exception) and verify the resulting tracked file manifest. Do not weaken exclusions for real runtime data.

This is a reproducibility/delivery issue, not evidence that the current local runtime test failed.

## Baseline and result

No actionable Fowler smell or new cleanup/concurrency hazard identified. **0 hard standards violations; 1 P2 fixture-delivery finding.** Runtime success, static typing and any broader Q1 completion must be established from their actual terminal results; this review does not certify them.
