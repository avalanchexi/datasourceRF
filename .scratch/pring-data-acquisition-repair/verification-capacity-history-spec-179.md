# Spec review — historical capacity catalog fixture, 179

Read-only review of the new historical-consumption test, README/provenance, export/inspection records, original engineering boundary, and relevant legacy mapping code. No pytest, installation, or application/test changes. All **247 frozen inputs plus 4 protected files** match snapshot179.

## Findings

1. **[P2] The broad legacy-dependency distinction remains partially untested.** The engineering boundary requires “旧目录接受集合不变” (`capacity-q1-implementation-boundary.md:55`); the preserved implementation requires every unclassified legacy basis before selecting a matching grant (`source_contract_review.py:510-518`), whereas typed grants check only matching bases later (`:696-728`). This historical fixture contains exactly one mapping, enforced by `test_capacity_historical_contract.py:62`; its `basis` fault therefore always damages the selected mapping's own basis (`:64-68`). Both legacy-global and typed-lazy basis validation reject that case. Deleting the eager legacy-basis check while retaining the later selected-basis check could leave all six new parameters green. Before closing the complete historical-dependency boundary, add a legitimately preserved/reproduced pre-contract catalog with multiple grants and damage an unselected grant's basis; old semantics must still reject adoption. Do not manufacture it by stripping a current admitted marker. The current six cases remain useful and correctly scoped, but cannot alone prove this legacy-versus-typed distinction.

## Fidelity and limits

No fabricated historical state or production/spec defect found. Independently opened the exported SQLite database with `mode=ro&immutable=1`: integrity is `ok`, no WAL exists, the database SHA matches provenance, the admitting model lacks `source_mapping_reference_contract`, and its manifest hash matches the preserved record. All ten artifact byte counts/SHA values match. Export178 copies bytes rather than updating a model or activation pointer; README clearly identifies synthetic historical test state and excludes real certification/replay acceptance.

The new test copies an independent runtime, first establishes three readable and adopted claims, then damages only its temporary artifact copy. Negative assertions correctly separate retained diagnostic identities from ytd adoption and verify model record/manifest immutability (`test_capacity_historical_contract.py:71-116`), consistent with boundary lines57/80/91. `ordinary_fields` is also referenced by historical semantics; this case proves a shared ordinary prerequisite remains mandatory, not an isolated fields-only rule.

**Spec findings: 1 verification gap for broad historical closure; 0 demonstrated incorrect implementations.** Actual179 execution remains the owning agent's terminal-evidence responsibility; this report makes no pass claim and does not certify historical PUBLIC availability, a full candidate, 120-day replay, or cutover.
