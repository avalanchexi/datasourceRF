"""New immutable A18 parser-v4 preparation; no acquisition, DB, or certification.

Default: read-only reparse and compare. --write-new refuses existing output.
The old preparation helper is reused read-only; its main/writer is never invoked.
"""
import argparse
import hashlib
import json
import runpy
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
OLD = BASE / "evidence-13-preparation"
OUTPUT = HERE / "preparation.json"
FAMILIES = {
    "nbs_core_cpi": "cpi", "nbs_ppi": "ppi", "nbs_pmi": "pmi",
    "nbs_industrial_finance": "industrial-finance",
    "nbs_industrial_value_added": "industrial-va",
    "nbs_capacity_utilization": "capacity-utilization", "pbc_money": "money",
    "pbc_tool_liquidity_monthly": "tool-liquidity",
    "pbc_loan_structure": "loan-structure", "pbc_social_financing": "social-financing",
    "pbc_omo_notice": "omo",
}
ANNOTATIONS = {"independent_period_binding_status", "field_unit_dimension_shape_status", "independent_review_status"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def core(scalar):
    return {key: value for key, value in scalar.items() if key not in ANNOTATIONS}


def execute():
    assert sha(OLD / "preparation.json") == "a9fe475c47303fb7791b27df04849dcef0aacabde27b64f57023972c9a4ec20a"
    assert sha(OLD / "prepare.py") == "e9295dcd722d9ff1f67e9fb0e57db6154c297510f80df344258b69971f638b27"
    previous = json.loads((OLD / "preparation.json").read_text(encoding="utf-8"))
    helpers = runpy.run_path(str(OLD / "prepare.py"))
    result = helpers["execute"]()
    result["schema"] = "p1-official-preparation-v2"
    result["execution"]["purpose"] = "current_parser_revalidation_of_saved_bytes_not_new_acquisition"
    data = result["data"]
    assert set(data["family_summary"]) == set(FAMILIES)
    assert data["summary"]["scalar_count"] == 1858
    assert data["summary"]["parse_status_counts"] == {"parsed_current_public_interface": 268}
    previous_rows = {(row["artifact_sha256"], row["family"]): row for row in previous["data"]["results"]}
    changes = []
    reviews = Counter()
    audit_files = []
    for family, suffix in FAMILIES.items():
        path = BASE / f"p1-{suffix}-full-value-audit.md"
        audit_files.append({"family": family, "path": path.relative_to(BASE).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)})
    for row in data["results"]:
        prior = previous_rows[(row["artifact_sha256"], row["family"])]
        assert row["expected_period"] == prior["expected_period"] and row["source_url"] == prior["source_url"]
        current_parsed = row["parsed"]
        old_parsed = prior["parsed"]
        assert {key: val for key, val in current_parsed.items() if key != "scalars"} == {key: val for key, val in old_parsed.items() if key != "scalars"}
        for index, (scalar, old_scalar) in enumerate(zip(current_parsed["scalars"], old_parsed["scalars"], strict=True)):
            current, old = core(scalar), core(old_scalar)
            if current != old:
                assert row["family"] == "pbc_money" and row["expected_period"] == "2026-02"
                assert scalar["source_field"] == "m2" and scalar["value"] == 3492200.0
                assert old_scalar["value"] == 3492200.0000000005
                assert {k: v for k, v in current.items() if k != "value"} == {k: v for k, v in old.items() if k != "value"}
                changes.append({"artifact_sha256": row["artifact_sha256"], "family": row["family"], "period": row["expected_period"], "scalar_index": index, "source_field": scalar["source_field"], "old_value": old_scalar["value"], "new_value": scalar["value"], "basis": "saved_PBC_literal_349.22_trillion_CNY_times_10000_and_public_parser_regression"})
                review = "literal_expectation_matches_after_decimal_scaling_fix"
            elif row["family"] == "nbs_capacity_utilization" and row["expected_period"] == "2026-Q1" and scalar["source_field"] == "industrial_capacity_utilization_ytd_pct":
                assert scalar["value"] == 73.6
                review = "same_interval_quarter_cell_reuse_source_mapping_pending"
            else:
                review = "unchanged_from_independently_literal_audited_old_scalar"
            scalar["independent_review_status"] = review
            scalar["independent_review_report"] = f"p1-{FAMILIES[row['family']]}-full-value-audit.md"
            scalar["review_scope"] = "saved_literal_field_unit_period_only_not_source_authentication"
            reviews[review] += 1
        row["release_at_qualification"] = "parser_page_time_candidate_not_first_vintage_certification"
        row["system_acquisition_time"] = None
    assert len(changes) == 1
    assert reviews == {
        "unchanged_from_independently_literal_audited_old_scalar": 1856,
        "literal_expectation_matches_after_decimal_scaling_fix": 1,
        "same_interval_quarter_cell_reuse_source_mapping_pending": 1,
    }
    assert data["raw_artifacts"] == previous["data"]["raw_artifacts"]
    assert len(data["raw_artifacts"]) == 250
    data["lineage"] = {
        "previous_preparation": "evidence-13-preparation/preparation.json",
        "previous_preparation_sha256": sha(OLD / "preparation.json"),
        "readonly_helper_sha256": sha(OLD / "prepare.py"),
        "current_parser_receipt_version": "official-context-parser-v0004",
        "audit_files": audit_files, "changes": changes,
        "certification_state": "not_performed", "model_adoption_state": "not_performed",
        "historical_public_first_vintage": "not_certified",
        "historical_system_acquisition": "unknown",
    }
    data["summary"]["full_value_review_counts"] = dict(reviews)
    data["summary"]["literal_matching_scalars"] = 1857
    data["summary"]["source_mapping_pending_scalars"] = 1
    data["summary"]["prior_preparation_changed_scalar_count"] = 1
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-new", action="store_true")
    args = parser.parse_args()
    if args.write_new and OUTPUT.exists():
        raise FileExistsError("Immutable preparation already exists; use default read-only verification")
    result = execute()
    if args.write_new:
        with OUTPUT.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    else:
        saved = json.loads(OUTPUT.read_text(encoding="utf-8"))
        assert saved["data"] == result["data"], "Source, parser, audit, or values differ from immutable preparation"
    print(json.dumps({"mode": "write_new" if args.write_new else "read_only_reparse", "preparation_sha256": sha(OUTPUT), "elapsed_seconds": result["execution"]["elapsed_seconds"], **result["data"]["summary"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
