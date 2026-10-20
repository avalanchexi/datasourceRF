# Spec preparation review — full credit window pair, 187

Read-only review of the unapplied patch, preparation receipt, manifest186, current admission/projection source, and spec Testing 1/4/6 plus issue19. No application/test execution, source/test mutation, or test-volume mounting. Patch and destination-source SHA match preparation187. All 34 original files match manifest byte counts/SHA, with 25 distinct social-financing months and 9 distinct GDP quarters.

## First-example blocker

**[P2] Patch187 is not yet a single-condition paired counterexample.** Issue19 requires “每项先有合法正例，再改变一个条件并核实际采用集合”. Patch lines 52-53 replace all nine GDP releases; its helper changes values, URLs, release times and table contents (lines 8-27). Thus `coherent` versus `actual_revised` does not isolate the GDP-baseline inconsistency. Preserve the intact real corpus as a separate observed counterexample, and add the proposed `synthetic_inconsistent` case: keep the coherent 34-parent corpus identical except 2025-Q4 GDP cumulative 1400000→1401000; quarter 350000, URL, timestamp and other 33 parents stay unchanged. Require the coherent public path to succeed first and the one-cell case to reject derivation. This accepted correction was communicated during review but is **not present in the reviewed 187 patch**.

## Subsequent acceptance gaps, not blockers to the first vertical pair

Patch lines 60-65/74-89 query each mode only after all inputs are visible. PUBLIC/SYSTEM parameterization alone does not prove revision-before/after cutoff, before-acquisition invisibility, old-cutoff reproducibility, or no fallback to an older complete window (spec Testing 4/6). Add these to the explicitly open follow-up matrix, together with raw/normalized failures. Use an external controlled clock: the current wall-clock SYSTEM cutoff can eventually make the fixed July 2026 input stale, changing line 100's expected status for unrelated reasons. These limits must remain open when reporting the first pair.

## Sound parts and scope

The public helper performs real synthetic-reviewed candidate admission, including already-implemented GDP binding; no gate/active-pointer bypass or repeated prerequisite is needed. Real ingestion, validated receipts, selected 34-parent identities, independent numeric expectation, derived trace, and model immutability provide observable assertions (patch lines 46-84/99-116). The real negative independently preserves Q4 cross-release differences 399338/386843 versus same-release quarter cells 373726/387911; rejecting an unsupported derived value is materially stronger than merely asserting no exception.

Preparation187 correctly says unapplied/unexecuted and orders positive→negative→fix after suite183 finishes. This is neither RED/GREEN nor complete Worker, actual source certification, full credit-revision closure, model activation, or 120-day acceptance.
