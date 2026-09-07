"""Prepare factual LPR review inputs; default verifies the saved draft read-only.

Standard library only. No app imports, network, claims, or certification writes.
Run in WSL; --write creates a new draft once, never replaces existing evidence.
"""

import argparse
import hashlib
import html
import json
import re
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUTS = ROOT / "evidence-lpr-import-20260908"
OUTPUT = Path(__file__).with_name("review-inputs.json")
CALENDAR_HASH = "d0740f44c9648b5adc6ba98fe9acb59565858e8195cdf25df09e59f691b94635"
RECEIPT_HASH = "31e1572983801245e76e1b4c33f57616029ba14bc304d2a276b9c1d1977d2d22"
EXPECTED_DATES = (
    "2025-12-22",
    "2026-01-20",
    "2026-02-24",
    "2026-03-20",
    "2026-04-20",
    "2026-05-20",
    "2026-06-22",
    "2026-07-20",
    "2026-08-20",
)


def checked_bytes(path, digest):
    content = path.read_bytes()
    assert hashlib.sha256(content).hexdigest() == digest, str(path)
    return content


def build():
    receipts = json.loads(checked_bytes(INPUTS / "receipts.json", RECEIPT_HASH))
    calendar = json.loads(
        checked_bytes(
            ROOT / "evidence-05" / f"{CALENDAR_HASH}.json",
            CALENDAR_HASH,
        )
    )
    assert calendar["code"] == 0 and calendar["data"]["has_more"] is False
    assert calendar["data"]["fields"] == ["cal_date", "is_open"]
    days = {date.fromisoformat(day): is_open for day, is_open in calendar["data"]["items"]}
    assert len(days) == len(calendar["data"]["items"])
    start, end = date(2026, 3, 9), date(2026, 8, 28)
    assert set(days) == {start + timedelta(days=i) for i in range((end - start).days + 1)}
    assert set(days.values()) == {0, 1}
    trading_days = sorted(day.isoformat() for day, is_open in days.items() if is_open == 1)
    assert (
        len(trading_days) == 120 and trading_days[0] == str(start) and trading_days[-1] == str(end)
    )
    database = Path(receipts["database"])
    assert database == Path(
        "/home/tywin/.cache/pring-cycle/verification/lpr-document-import-20260908/data/pring-cycle.sqlite3"
    )
    records = []
    assert len(receipts["receipts"]) == len(EXPECTED_DATES)
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as connection:
        for table in ("source_claim", "registered_metric_catalog"):
            assert connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
        for item, release_date in zip(receipts["receipts"], EXPECTED_DATES, strict=True):
            receipt, parsed = item["receipt"], item["parsed_unreviewed_release"]
            raw = checked_bytes(INPUTS / receipt["raw_hash"], receipt["raw_hash"])
            lines = raw.decode("utf-8").splitlines()
            normalized = json.loads(
                checked_bytes(INPUTS / receipt["normalized_hash"], receipt["normalized_hash"])
            )
            assert normalized == parsed
            # Independent literal extraction from each body line, not the application's parser.
            body = [
                (number, re.sub(r"\s+", "", html.unescape(re.sub(r"<[^>]+>", "", line))))
                for number, line in enumerate(lines, 1)
                if "中国人民银行授权" in line
            ]
            body = [(number, text) for number, text in body if "中国人民银行授权" in text]
            assert len(body) == 1
            body_line, text = body[0]
            for literal in ("1年期LPR为3.0%", "5年期以上LPR为3.5%", "LPR在下一次发布LPR之前有效"):
                assert text.count(literal) == 1, (release_date, literal)
            y, m, d = map(int, release_date.split("-"))
            assert f"{y}年{m}月{d}日" in text
            timestamp = release_date + " 09:00"
            time_lines = [
                number for number, line in enumerate(lines, 1) if f">{timestamp}</span>" in line
            ]
            assert len(time_lines) == 1
            assert parsed["period"] == release_date[:7] == receipt["parameters"]["period"]
            assert parsed["release_at"] == timestamp + ":00+08:00"
            assert parsed["public_available_at"] == parsed["release_at"]
            assert {part["tenor"]: part["value"] for part in parsed["observations"]} == {
                "1y": 3.0,
                "5y_plus": 3.5,
            }
            clocks = [
                datetime.fromisoformat(receipt[key])
                for key in ("started_at", "received_at", "validated_at")
            ]
            assert clocks == sorted(clocks) and clocks[0] > datetime.fromisoformat(
                parsed["release_at"]
            )
            reference = receipt["acquisition_id"] + ":raw"
            assert connection.execute(
                "SELECT 1 FROM artifact_reference WHERE content_hash=? AND source_reference=?",
                (receipt["raw_hash"], reference),
            ).fetchone() == (1,)
            records.append(
                {
                    "period": parsed["period"],
                    "source_url": parsed["source_url"],
                    "artifact_hash": receipt["raw_hash"],
                    "source_reference": reference,
                    "body_line": body_line,
                    "publication_line": time_lines[0],
                    "source_publication_literal": timestamp,
                    "source_timezone": "Asia/Shanghai",
                    "source_precision": "minute",
                    "values_percent": {"1y": 3.0, "5y_plus": 3.5},
                    "acquisition_id": receipt["acquisition_id"],
                    "received_at": receipt["received_at"],
                    "validated_at": receipt["validated_at"],
                    "first_vintage_bytes_proven": False,
                    "historical_system_available_at": None,
                    "certified_public_available_at": None,
                }
            )
    coverage = []
    for day in trading_days:
        # Calendar-date selection is only a post-announcement expected-state map.
        # It is not an application PUBLIC query or an intraday cutoff decision.
        eligible = [
            record for record in records if record["source_publication_literal"][:10] <= day
        ]
        latest = eligible[-1]
        coverage.append(
            {
                "target_business_date": day,
                "expected_period": latest["period"],
                "artifact_hash": latest["artifact_hash"],
            }
        )
    states = []
    for record in records[2:]:
        covered = [
            row["target_business_date"]
            for row in coverage
            if row["expected_period"] == record["period"]
        ]
        assert covered
        states.append(
            {
                "period": record["period"],
                "first_target_date": covered[0],
                "last_target_date": covered[-1],
                "target_day_count": len(covered),
            }
        )
    assert sum(state["target_day_count"] for state in states) == 120
    return {
        "schema_version": "lpr-review-inputs-draft-v0001",
        "decision": "draft_not_certified",
        "metric_id": "CN_LPR_1Y_5Y",
        "provider": "中国货币网",
        "source_code": "CHINAMONEY_LPR",
        "semantic_scope": "贷款市场报价利率，两期限，月度公布，下一次发布前有效",
        "definition_binding": None,
        "manifest_hash": None,
        "certified_from": None,
        "receipt_hash": RECEIPT_HASH,
        "calendar_hash": CALENDAR_HASH,
        "calendar_status": "existing_tushare_sample_not_new_calendar_certification",
        "records": records,
        "expected_quote_states": states,
        "expected_target_date_coverage": coverage,
        "assessments": {
            "semantics": "literal_evidence_prepared_pending_complete_definition_binding",
            "fields": "18_of_18_literals_verified_two_tenors_percent",
            "history": "9_pages_7_required_quote_states_revision_inventory_not_proven",
            "time": (
                "page_minute_metadata_and_current_import_clocks_separated_formal_review_pending"
            ),
            "permissions": "see_lpr_usage_evidence_review_no_grant_in_this_draft",
            "usage": "see_lpr_usage_evidence_review_no_grant_in_this_draft",
        },
        "source_claims_created": 0,
        "certification_grants": 0,
        "model_adoptions": 0,
        "real_replay_cutoffs_executed": 0,
        "network_requests": 0,
        "production_writes": 0,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    result = build()
    content = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    if args.write:
        with OUTPUT.open("xb") as stream:
            stream.write(content)
    else:
        assert OUTPUT.read_bytes() == content, "saved_draft_does_not_match_originals"
    print(
        json.dumps(
            {
                "originals": len(result["records"]),
                "literal_values": 18,
                "quote_states": len(result["expected_quote_states"]),
                "expected_target_dates": len(result["expected_target_date_coverage"]),
                "real_replay_cutoffs_executed": 0,
                "bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        )
    )
