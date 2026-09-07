"""Offline standard-library verification; default read-only, no HTTP/app/DB/WSL.

Explicit --write-inspection and --write-manifest generate only this research
folder's JSON. Verification passing does not certify unavailable BSE data.
"""
import hashlib
import json
import re
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

EVIDENCE = Path(__file__).resolve().parent
PROJECT = EVIDENCE.parent
REPO = PROJECT.parent.parent
OLD = PROJECT / "evidence-05"
REPORT = PROJECT / "margin-bse-followup.md"
OLD_REPORT_SHA = "b4d606f38ff3c59d6478a5d822fd3a5109daf84a689b533d4ed0d92c8a6b2634"
REDIRECT_SHA = "753e0dd54f28c4f7009b9c0b18a68aed175416bd8b7d134858264586eaac56f0"
LEGACY = "3cb57edb3e560a118fd2a84c94d471a53179547489b5ef0936649c63e4ae4548.json"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    raw = path.read_bytes()
    return {"path": path.relative_to(REPO).as_posix(), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def inspect():
    receipts = load(EVIDENCE / "receipts.json")
    old_receipts = load(OLD / "receipts.json")
    assert len(receipts) == 2 <= 5
    assert len({r["url"] for r in receipts}) == 2
    for r in receipts:
        assert r["status"] == 302 and r["automatic_redirects"] is False
        assert r["headers"]["Location"] == r["url"] == r["final_url"]
        assert r["bytes"] == 138 and r["sha256"] == REDIRECT_SHA and not r["truncated"]
        assert r["public_available_at"] is None and r["method"] == "GET"
        assert r["url"] not in {old["url"] for old in old_receipts}
        assert datetime.fromisoformat(r["received_at"]) >= datetime.fromisoformat(r["started_at"])
    raw = (EVIDENCE / REDIRECT_SHA).read_bytes()
    assert len(raw) == 138 and hashlib.sha256(raw).hexdigest() == REDIRECT_SHA
    assert b"302" in raw and b"2026-08-28" not in raw
    legacy = load(OLD / LEGACY)
    fields = legacy["data"]["fields"]
    assert fields == ["trade_date", "exchange_id", "rzye", "rzmre"]
    rows = [dict(zip(fields, row)) for row in legacy["data"]["items"]]
    bse = [row for row in rows if row["exchange_id"] == "BSE" and row["trade_date"] == "20260828"]
    assert len(bse) == 1
    balance = Decimal(str(bse[0]["rzye"]))
    buy = Decimal(str(bse[0]["rzmre"]))
    assert balance == Decimal("8332418348") and buy == Decimal("659105185")
    return {
        "fixed_target_date": "2026-08-28",
        "new_get_budget": 5, "new_get_attempts": len(receipts), "remaining_budget_unused": 3,
        "http_2xx_count": 0, "http_self_redirect_count": 2,
        "received_response_body_bytes_across_requests": sum(r["bytes"] for r in receipts),
        "unique_new_response_artifacts": [digest(EVIDENCE / REDIRECT_SHA)],
        "unique_new_response_bytes": len(raw),
        "valid_target_sample_count": 0,
        "target_fields": [
            {"field": key, "indexed_label": label, "indexed_unit": "ten_thousand_cny", "official_numeric_value": None, "observed_statistical_date": None, "new_http_unit_proof": False}
            for key, label in (("financing_balance", "融资余额"), ("securities_lending_balance", "融券余额"), ("total_margin_balance", "融资融券余额"))
        ],
        "original_ticket_financing_buy_amount_official_sample": None,
        "legacy_provider_reference_only": {
            "source": "Previously acquired TuShare JSON; this followup does not call an account API or DB",
            "statistical_date": "2026-08-28", "exchange": "BSE", "unit": "cny",
            "financing_balance": str(balance.quantize(Decimal("1"))), "financing_buy_amount": str(buy.quantize(Decimal("1"))),
            "securities_lending_balance": None, "total_margin_balance": None,
            "official_bse_value_match_established": False, "source_file": digest(OLD / LEGACY),
        },
        "publication": {"release_at": None, "public_available_at": None, "reason": "No target-date numeric content or actual publication record was obtained; response Date is transport metadata, not historical availability."},
        "stop_reason": "Both documented new public paths self-redirected; bounded discovery found no official new finance query/download script. No repetition, guessed endpoint, challenge bypass, substitute date or residual estimate.",
        "source_certifications": 0, "model_adoptions": 0, "production_mutations": 0,
    }


def verify():
    inspection = inspect()
    assert inspection == load(EVIDENCE / "source-inspection.json")
    prior = load(EVIDENCE / "prior-attempts.json")
    related = [r for r in load(OLD / "receipts.json") if any(h in r["url"] for h in ("www.bse.cn", "www.bseinfo.net"))]
    assert prior["old_http_attempts"] == related and len(related) == 4
    reused = []
    for r in related:
        actual = digest(OLD / r["local_file"])
        assert actual["sha256"] == r["sha256"] and actual["bytes"] == r["byte_count"]
        assert r["status"] == 403
        reused.append(actual)
    legacy_digest = digest(OLD / LEGACY)
    assert legacy_digest["sha256"] == LEGACY.split(".")[0]
    reused.append(legacy_digest)
    assert digest(PROJECT / "research-05.md")["sha256"] == OLD_REPORT_SHA
    links = []
    for target in re.findall(r"\[[^\]]*\]\(([^\n)]+)\)", REPORT.read_text(encoding="utf-8")):
        if target.startswith(("https://", "http://", "#")):
            continue
        assert (PROJECT / target.split("#", 1)[0]).resolve().is_file(), target
        links.append(target)
    manifest = EVIDENCE / "delivery-verification.json"
    paths = (EVIDENCE / "delivery-files.txt").read_text(encoding="utf-8").splitlines()
    assert len(paths) == len(set(paths))
    files = []
    for relative in paths:
        path = (REPO / relative).resolve()
        assert path == REPORT or path.is_relative_to(EVIDENCE)
        if path != manifest:
            files.append(digest(path))
    return {
        "research_delivery_validation": "passed", "new_get_attempts": 2, "http_2xx_count": 0,
        "self_redirects": 2, "valid_target_samples": 0, "unique_new_response_bytes": 138,
        "received_response_body_bytes_across_requests": 276,
        "verified_new_originals": inspection["unique_new_response_artifacts"], "verified_reused_originals": reused,
        "old_report_sha256_unchanged": OLD_REPORT_SHA, "report_local_links_checked": links,
        "delivery_path_count": len(paths), "files": files, "manifest_self_hash_excluded": True,
        "source_certifications": 0, "model_adoptions": 0, "verification_network_requests": 0,
    }


if __name__ == "__main__":
    if sys.argv[1:] == ["--write-inspection"]:
        result = inspect()
        (EVIDENCE / "source-inspection.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({k: result[k] for k in ("new_get_attempts", "http_2xx_count", "valid_target_sample_count")}, indent=2))
    else:
        result = verify()
        manifest = EVIDENCE / "delivery-verification.json"
        if sys.argv[1:] == ["--write-manifest"]:
            manifest.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        else:
            assert not sys.argv[1:] and result == load(manifest)
        print(json.dumps({k: result[k] for k in ("research_delivery_validation", "new_get_attempts", "http_2xx_count", "valid_target_samples", "unique_new_response_bytes", "delivery_path_count")}, indent=2))
