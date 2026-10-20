# Standards follow-up — historical Q1 fixture delivery, batch 180

Read-only verification of the fixture-local `.gitignore` and review 179's sole P2 finding. No tests, installation, database changes or actual staging performed.

**Resolved:** `capacity-historical-fixture-178/.gitignore` now re-includes `pring-cycle.sqlite3` and `artifacts/` inside this synthetic fixture directory. Both `git ls-files --others --exclude-standard` and `git add --dry-run` enumerate all 14 required files: the database, ten CAS artifacts, README, provenance and local ignore file. Ordinary staging will therefore include the complete fixture rather than only its descriptive files. The global `.gitignore` is unchanged, so exclusions elsewhere still protect real runtime state.

All 247 inputs and four protected files from freeze 179 remain byte-identical. The local ignore addition changes delivery eligibility only; it does not alter the regression's data, assertions or production behavior.

**Result: review 179's P2 is closed; 0 new standards violations, actionable smells or material hazards identified.** The fixture is now eligible for complete delivery, but this review does not claim it has been staged or committed.

This follow-up does not broaden the six-case regression's meaning. Historical multi-grant/full-basis compatibility remains a separate open coverage item. Runtime and typing results remain the responsibility of their real terminal records; no tests were rerun for this review.
