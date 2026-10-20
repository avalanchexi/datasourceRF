# Standards review — unapplied credit-window pair, draft 187

Read the patch, preparation script/receipt, manifest and relevant parser, projection, acquisition and evidence signatures. Used only read-only files, hashes and standard-library in-memory AST/arithmetic checks. No application/parser, pytest, static-check tool, mount operation or source mutation was run.

## Static findings

1. **[P2] SYSTEM positive depends on the calendar date** — patch lines 60,64-65,100. The SYSTEM cutoff is the real current time, but the frozen last SF month is July 2026 and the expected status is always `available`. `evidence_max_age_days` allows 95 days for monthly data; from **2026-11-04**, `context_projection.py:2191-2234` produces `stale_inputs` even for correct arithmetic. Use an explicit acquisition/validation clock and fixed SYSTEM cutoff consistently, so freshness does not become an unrelated positive failure.

2. **[P2] Missing type narrowing at the adoption assertion** — patch line 108. `ContextProjection.macro` is `dict[str, object]` (`context_projection.py:95-99`), so `set(context.macro["model_input_observation_version_ids"])` supplies non-iterable static type `object`. Bind the value and assert `isinstance(..., list)` as nearby historical-contract tests do before converting it. This is a source-level predicted typing failure, not an executed mypy result.

3. **Minor explicit format check requested:** patch line 21 prefixes a literal containing no expression with `f` (F541); line 15 is 104 characters against the repository's 100-character setting. Neither is counted as a non-tooling standards violation.

## Verified static evidence

Source/patch hashes match the preparation receipt; the replacement anchor occurs once and the in-memory complete file parses. Required imports and both new function names are present/unique.

All 34 raw files match manifest length/hash and are not Git-ignored; 33 are not yet tracked, so final delivery must include the manifest's exact paths. The 25 consecutive SF parents produce 24 differences totaling 373800/338600; nine GDP parents cover eight quarters. The independently specified positive equals **-2.514285714285714** percentage points.

Synthetic GDP headers, row widths, period titles and price-basis note match the inspected parser contract. All parent release times precede PUBLIC cutoff; the synthetic model enables the intended formula. No additional definite ingestion pre-blocker was identified statically. Runtime positivity and the intended negative failure remain unproven; this draft must not be called an executed regression or certification result.
