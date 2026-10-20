# Spec incremental preparation review — 188

Read-only inspection of patch188, preparation188 and relevant existing evidence-query source. Patch SHA matches `0d84d47a36521037659421f76bf7249a4426b27f11b529f521a52d48bf85f86b`. No source/test/frozen-input changes, pytest/static-tool execution, application execution, or mount operations.

## Prior finding resolved in design

The single-condition problem in Spec187 is addressed. Patch lines 57-64 create the same coherent synthetic corpus and replace exactly one occurrence of the 2025-Q4 GDP cumulative cell, 1400000→1401000. Its quarterly cell, source URL, publication time and other 33 parents remain unchanged. The intact `actual_revised` corpus remains a separate scenario. This meets issue19's paired-input requirement in design; execution is still pending. Fixed acquisition/availability clocks at lines 48-51/71-77 also remove wall-clock freshness drift.

## New preparation finding

**[P2] The one-microsecond early query overasserts an empty series.** Patch lines 79-83 require `metric_series(...) == ()` at `fixture_time - 1 microsecond`. Existing SQLite selection intentionally uses coarse `julianday` filtering (`evidence.py:995-1004`), which can include rows rounded across that sub-millisecond boundary. Exact filtering then returns an `unavailable` result with no claims (`:1299-1323`), but `metric_series` still constructs the corresponding point (`:1023-1038`). Thus legal absence of available claims need not mean an empty tuple, and this assertion can fail before either GDP-baseline assertion.

For this first vertical pair, use a one-second pre-acquisition cutoff, or assert the actual public contract: no selected claim/value and no available claims for any returned point. Keep microsecond empty-series normalization, if desired, as a separately diagnosed API concern; do not treat this preparation failure as the credit-comparability RED or loosen application cutoff filtering.

During review, the owning agent accepted retaining the one-microsecond cutoff while checking each point's `selected_claim_id is None`, `selected_value is None`, and `claims == ()`; this correction is planned for draft189 and is not yet present in the reviewed188 bytes.

No gate bypass or other new spec mismatch found. Real admission, intact raw ingestion, 34-parent checks, independent arithmetic, trace and model immutability remain. PUBLIC revision-before/after, damaged complete-window inputs, no fallback to older windows and full temporal closure remain explicitly open. This report certifies neither RED/GREEN nor full Worker, source certification, credit completion, activation, or 120-day acceptance.
