"""Offline Windows/stdlib verification; no network, app import, database or WSL.

Default verifies the immutable research delivery. --write-inspection and
--write-manifest only create the named JSON in this evidence directory.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import sys
from collections import Counter
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

EVIDENCE = Path(__file__).resolve().parent
PROJECT = EVIDENCE.parent
REPO = PROJECT.parent.parent
OLD = PROJECT / "evidence-14"
REPORT = PROJECT / "vix-followup.md"
OLD_REPORT_HASH = "1bad5c100b8996dfa1286da712c723211b9640d8cc98a1e24cdec8647bedf82b"
CSV_HASH = "9258a25814fb936e7df32a96bcf3914fdbf342afb33cdf8759cdfbc8064ddb72"
HISTORY_HASH = "f4e6c655412ebd198fa83ebf4dc0758e7ce4df6173338d9accc2b8e1c5fa8a83"
TERMS_HASH = "43ab8dce9352bff8d2ed155ad03ab0b2757eda12f7342911baefbcbb508a6f99"
FAQ_HASH = "f066507ce9d468651ab1488db5240899c002e88eb13413a0175928a1181667b8"
FEED_HASH = "526efeacade3a160d48fdca7857565f8e2e8e73194eff276f436469f980de060"
INPUT_HASH = "0f768bfe2860c7b2975dd6dbe92a5c5f8af567a370fedf645d2fb80e1cac3746"


def digest(path: Path) -> dict:
    raw = path.read_bytes()
    return {"path": path.relative_to(REPO).as_posix(), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def raw_anchors(path: Path, needles: list[str]) -> dict:
    raw = path.read_bytes()
    offsets = {needle: raw.find(needle.encode("utf-8")) for needle in needles}
    assert all(offset >= 0 for offset in offsets.values()), offsets
    return {**digest(path), "utf8_byte_offsets": offsets}


def inspect() -> dict:
    raw = (OLD / CSV_HASH).read_bytes()
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    assert reader.fieldnames == ["DATE", "OPEN", "HIGH", "LOW", "CLOSE"]
    rows = list(reader)
    assert all(None not in row and all(v is not None for v in row.values()) for row in rows)
    fields = reader.fieldnames[1:]
    counts = {key: dict(positive=0, zero=0, negative=0, blank=0, special=0) for key in fields}
    dates, anomalies, normalized = [], [], []
    all_equal = 0
    for row in rows:
        day = datetime.strptime(row["DATE"], "%m/%d/%Y").date().isoformat()
        dates.append(day)
        values = {}
        for key in fields:
            text = row[key]
            try:
                value = Decimal(text)
            except InvalidOperation:
                value = None
            category = (
                "blank" if not text.strip() else
                "special" if value is None or not value.is_finite() else
                "positive" if value > 0 else "negative" if value < 0 else "zero"
            )
            counts[key][category] += 1
            values[key] = value
        assert all(v is not None and v.is_finite() for v in values.values())
        reasons = [f"{key}_outside_low_high" for key in ("OPEN", "CLOSE") if not values["LOW"] <= values[key] <= values["HIGH"]]
        if values["LOW"] > values["HIGH"]:
            reasons.append("low_above_high")
        if reasons:
            anomalies.append({"period": day, **row, "reasons": reasons})
        all_equal += len(set(values.values())) == 1
        normalized.append({"period": day, **{key: row[key] for key in fields}})
    assert len(rows) == len(set(dates)) == 9266 and dates == sorted(dates)
    assert len(anomalies) == 47 and all(a["reasons"] == ["OPEN_outside_low_high"] for a in anomalies)
    assert all(not "2026-03-09" <= a["period"] <= "2026-09-04" for a in anomalies)
    normalized_bytes = json.dumps(normalized, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    old_receipts = [r for r in load(OLD / "receipts.json") if r.get("sha256") in (CSV_HASH, HISTORY_HASH, TERMS_HASH)]
    anchors = [
        raw_anchors(OLD / HISTORY_HASH, ["daily closing values", "Updated Daily", "VIX_History.csv"]),
        raw_anchors(OLD / TERMS_HASH, ["personal non-commercial use", "one copy", "electronic retrieval system", "derivative work", "verify or correct", "prior written consent"]),
        raw_anchors(EVIDENCE / FAQ_HASH, ["every 15 seconds", "4:15 p.m. ET", "Originally posted"]),
        raw_anchors(EVIDENCE / FEED_HASH, ["Index Data License Request Form", "Market_Data_Policies.pdf"]),
        raw_anchors(EVIDENCE / INPUT_HASH, ["16:35-19:00", "On early close days", "SFTP"]),
    ]
    return {
        "csv_original": digest(OLD / CSV_HASH),
        "reused_original_receipts": old_receipts,
        "fieldnames": reader.fieldnames,
        "target_metric": "CBOE_VIX_INDEX",
        "target_field": "CLOSE",
        "catalog_unit": "index_points",
        "source_date_format": "%m/%d/%Y",
        "row_count": len(rows),
        "date_range": [dates[0], dates[-1]],
        "duplicate_dates": len(dates) - len(set(dates)),
        "date_order": "ascending",
        "weekend_rows": sum(datetime.fromisoformat(day).weekday() > 4 for day in dates),
        "window_20260309_to_20260904": sum("2026-03-09" <= day <= "2026-09-04" for day in dates),
        "value_classification": counts,
        "ohlc_envelope_anomaly_count": len(anomalies),
        "ohlc_envelope_anomalies": anomalies,
        "ohlc_anomaly_date_range": [min(a["period"] for a in anomalies), max(a["period"] for a in anomalies)],
        "all_ohlc_equal_row_count": all_equal,
        "samples": [r for r in normalized if r["period"] in ("1990-01-02", "2004-11-08", "2020-03-16", "2026-08-28", "2026-09-04")],
        "extrema": {key: {side: normalized[index] for side, index in (("min", min(range(len(rows)), key=lambda i: Decimal(rows[i][key]))), ("max", max(range(len(rows)), key=lambda i: Decimal(rows[i][key]))))} for key in fields},
        "normalized_rows_serialization": "UTF-8 json.dumps(list[dict], ensure_ascii=False, separators=(',',':')); key order period,OPEN,HIGH,LOW,CLOSE; source ascending order",
        "normalized_rows_sha256": hashlib.sha256(normalized_bytes).hexdigest(),
        "official_claim_anchor_offsets": anchors,
        "source_publication": {"index_calculation_timezone": "Eastern Time", "daily_csv_publication_timezone": None, "daily_csv_release_at": None, "historical_row_public_available_at": None},
        "verification_network_requests": 0,
        "new_csv_gets": 0,
        "new_certifications": 0,
        "production_mutations": 0,
    }


def verify() -> dict:
    inspection = inspect()
    assert inspection == load(EVIDENCE / "source-inspection.json")
    receipts = load(EVIDENCE / "receipts.json")
    assert len(receipts) == 3
    reused = inspection["reused_original_receipts"]
    assert len(reused) == 3
    all_raw = []
    for folder, records in ((EVIDENCE, receipts), (OLD, reused)):
        for record in records:
            actual = digest(folder / record["local_file"])
            assert record["status"] == 200 and record["truncated"] is False
            assert actual["sha256"] == record["sha256"] and actual["bytes"] == record["bytes"]
            assert datetime.fromisoformat(record["received_at"]) >= datetime.fromisoformat(record["started_at"])
            all_raw.append(actual)
    assert digest(PROJECT / "research-14.md")["sha256"] == OLD_REPORT_HASH
    links = []
    for target in re.findall(r"\[[^\]]*\]\(([^\n)]+)\)", REPORT.read_text(encoding="utf-8")):
        if target.startswith(("https://", "http://", "#")):
            continue
        assert (PROJECT / target.split("#", 1)[0]).resolve().is_file(), target
        links.append(target)
    paths = (EVIDENCE / "delivery-files.txt").read_text(encoding="utf-8").splitlines()
    assert len(paths) == len(set(paths))
    manifest = EVIDENCE / "delivery-verification.json"
    files = []
    for relative in paths:
        path = (REPO / relative).resolve()
        assert path == REPORT or path.is_relative_to(EVIDENCE)
        if path != manifest:
            files.append(digest(path))
    return {
        "validation": "passed", "new_get_attempts": 3, "new_get_failures": 0,
        "new_original_count": 3, "new_original_bytes": sum(r["bytes"] for r in receipts),
        "reused_original_count": 3, "reused_original_bytes": sum(r["bytes"] for r in reused),
        "verified_originals": all_raw, "all_original_bytes": sum(r["bytes"] for r in all_raw),
        "csv_rows_recomputed": inspection["row_count"], "ohlc_anomalies_recomputed": inspection["ohlc_envelope_anomaly_count"],
        "normalized_rows_sha256": inspection["normalized_rows_sha256"],
        "old_report_sha256_unchanged": OLD_REPORT_HASH, "report_local_links_checked": links,
        "delivery_path_count": len(paths), "files": files, "manifest_self_hash_excluded": True,
        "network_requests_during_verification": 0,
    }


if __name__ == "__main__":
    if sys.argv[1:] == ["--write-inspection"]:
        result = inspect()
        (EVIDENCE / "source-inspection.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"rows": result["row_count"], "anomalies": result["ohlc_envelope_anomaly_count"], "normalized_rows_sha256": result["normalized_rows_sha256"]}, indent=2))
    else:
        result = verify()
        manifest = EVIDENCE / "delivery-verification.json"
        if sys.argv[1:] == ["--write-manifest"]:
            manifest.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        else:
            assert not sys.argv[1:]
            assert result == load(manifest), "Delivery manifest differs from fresh read-only verification"
        print(json.dumps({key: result[key] for key in ("validation", "new_get_attempts", "new_original_bytes", "all_original_bytes", "csv_rows_recomputed", "ohlc_anomalies_recomputed", "delivery_path_count")}, indent=2))
