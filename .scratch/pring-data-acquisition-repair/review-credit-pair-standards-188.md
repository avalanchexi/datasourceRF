# Standards follow-up — unapplied credit-window pair, draft 188

Read-only incremental review. Source hash matches the receipt; patch SHA-256 is `0d84d47a36521037659421f76bf7249a4426b27f11b529f521a52d48bf85f86b`. The anchor remains unique and the in-memory replacement parses. No application/parser, pytest, static-check tool, database operation, mount or frozen-file mutation was executed.

## Review 187 findings

**Both P2 findings resolved:** patch lines 48-77 consistently fix fetched/validation time and SYSTEM cutoff to 2026-08-29; lines 125-127 narrow model-input IDs to a list before constructing a set. The previous no-expression f-string at line 21 and 104-character line 15 remain minor formatting cleanup, not new behavioral findings.

## New finding

**[P2] Microsecond visibility assertion expects an unsupported empty-series shape** — patch lines 79-83. The new query runs one microsecond before the fixed acquisition boundary and asserts `metric_series(...) == ()`. `evidence.py:993-1040` first groups rows admitted by SQLite's coarse `julianday` filter, then appends a point for each group. Its documented sub-millisecond handling at lines 1299-1323 removes future claims precisely but returns an unavailable result with empty claims and null selected ID/value; the surrounding series code retains that point. Therefore coarse-filter matches can yield nonempty unavailable placeholders without any early evidence visibility. This would stop all six scenarios before the formula assertions and misclassify a test-contract error as the intended product counterexample.

Use the existing exact-boundary convention in `tests/models/test_candidate_admission.py:5947-5955`: assert every returned point has no claims, selected claim ID or selected value. This retains the one-microsecond invariant without requiring absent observation identities.

## Added negative and boundary

`synthetic_inconsistent` changes exactly one GDP cumulative cell from 1400000 to 1401000 while preserving its stated quarterly value 350000, URL and publication time. The byte replacement requires exactly one match; its target exists in the inspected synthetic shape. This isolates an explicit disagreement for subsequent formula validation, with raw ingestion and parent-count assertions retained.

**Result:** prior P2 findings closed; one new P2 precondition/expectation finding. No new hard architectural violation or actionable Fowler smell identified. Draft 188 remains unapplied and unexecuted; neither the positive nor either negative has been established by runtime evidence.
