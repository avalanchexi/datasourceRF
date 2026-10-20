# Standards review — historical multiple-grant Q1 compatibility, batch 182

Read-only incremental review of `tests/models/test_capacity_historical_contract.py`, the new fixture's README/provenance/local ignore file and the referenced export script. No tests, installation, database edits or actual staging performed. All 274 inputs and four protected files match freeze 182. Compared with freeze 179, the only changed existing input is this test module; production bytes remain unchanged.

## Standards and behavior boundary

No documented-standard violation identified. The common `historical_runtime` helper centralizes fixture byte checks and private runtime copying without adding a production hook. The original six cases preserve their prior behavior.

The four added cases assert an original manifest without the service marker, two distinct mappings and independent basis artifacts. PUBLIC selection at 2026-04-16 explicitly chooses 73.6, and the damaged dependency is located through the *other* raw-document identity (`tests/models/test_capacity_historical_contract.py:145-168`). Positive retrieval selection and actual context adoption precede each fault. Afterwards the test checks rejection of the old YTD claim, retention of diagnostic identities and unchanged model identity/manifest (lines 186-213). This exercises the documented old all-dependency interpretation through public consumers, without simulating history by removing a marker from a newly admitted model.

## Fixture integrity and delivery

Independently verified database SHA-256 `22269ee3532be8b79b5944eab910ac2b444a95c17d4985bd03826a03f51b9d55`, all 22 artifact hashes/lengths and absence of WAL/SHM sidecars. Provenance explicitly identifies the one restored mapping (`c7766b1a…ffd9fd`) and its existing hash-matched source copy. The export script copies the database unchanged and verifies source/destination bytes; it restores only the new fixture's CAS object. README keeps the original failed snapshot and synthetic/real-acceptance distinction explicit.

Both Git enumeration and `git add --dry-run` include all 26 new fixture files. The local ignore exception therefore avoids review 179's prior delivery problem without changing global runtime exclusions.

## Result

**0 hard standards violations, 0 actionable baseline smells, and 0 new material cleanup/concurrency/delivery hazards identified.** The added assertions address the previously missing multiple-grant distinction in test scope. Actual success of the ten cases and typing checks still requires their real terminal results; this source review does not certify runtime success, complete Q1 acceptance or real source certification.
