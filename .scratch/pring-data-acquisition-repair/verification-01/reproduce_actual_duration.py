"""Read a retained normalized artifact; never write to the live runtime."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, replace
from datetime import date
from pathlib import Path

from pring_cycle.domain.trend import PricePoint, TrendRules, evaluate_trend

ARTIFACT_HASH = "0605b3d9a8f2a9eb196fd220a03f90cf31d0acb464430569ead89287702ab61b"
ARTIFACT = Path("/home/tywin/.local/share/pring-cycle/artifacts/sha256/06") / ARTIFACT_HASH
TARGET = "2026-08-03"


def main() -> None:
    raw = ARTIFACT.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == ARTIFACT_HASH
    document = json.loads(raw)
    old_rules = TrendRules()
    new_rules = replace(old_rules, candidate_duration_rule_version="candidate-duration-v0002")
    # Literal expected durations come from the frozen audit, not a second run
    # of this implementation. Synthetic hand examples separately test counting.
    expected = {"CN_BOND_CORE_000012": 0, "CN_EQUITY_CORE_000985": 7, "CN_COMMODITY_CORE_NHII": 0}
    results = {}
    for metric, expected_days in expected.items():
        rows = [row for row in document["series"][metric] if row["business_date"] <= TARGET]
        points = [
            PricePoint(date.fromisoformat(row["business_date"]), row["close"]) for row in rows
        ]
        old = evaluate_trend(points, old_rules)
        new = evaluate_trend(points, new_rules)
        assert old == new  # Stable state, measurements and algorithm are unchanged.
        assert new.stable_state is not None and new.stable_state.value == "bull"
        assert new_rules.candidate_days_for_output(new) == expected_days
        assert old_rules.candidate_days_for_output(old) == 8
        assert len(points) == 2326 and rows[-1]["business_date"] == TARGET
        results[metric] = {
            "input_rows": len(rows),
            "last_close": rows[-1]["close"],
            "result": asdict(new),
            "legacy_output_candidate_days": old_rules.candidate_days_for_output(old),
            "new_output_candidate_days": new_rules.candidate_days_for_output(new),
            "algorithm_result_unchanged": old == new,
        }
    receipt = {
        "schema_version": "candidate-duration-forensic-check-v1",
        "target_business_date": TARGET,
        "artifact_sha256": ARTIFACT_HASH,
        "evidence_kind": "retained_normalized_history_not_http_original_or_official_confirmation",
        "network_requests": 0,
        "production_writes": 0,
        "old_rules": asdict(old_rules),
        "new_rules": asdict(new_rules),
        "results": results,
    }
    output = Path(__file__).with_name("actual-duration.json")
    output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": True, "receipt": str(output), "assets_checked": 3}))


if __name__ == "__main__":
    main()
