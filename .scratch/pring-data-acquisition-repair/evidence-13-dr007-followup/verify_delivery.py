"""Offline standard-library verifier for the bounded DR007 research delivery.

Default is read-only. Explicit --write-inspection/--write-manifest only write the
named file in this evidence folder. No application import, DB, WSL or HTTP.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

EVIDENCE = Path(__file__).resolve().parent
PROJECT = EVIDENCE.parent
REPO = PROJECT.parent.parent
OLD = PROJECT / "evidence-13"
REPORT = PROJECT / "dr007-followup.md"
REPORT13_SHA = "dcbdf9a07095e5bfb2110ff2f3a51e9049dc1bece87b3859207df1ece0f973e1"
CONFIG = "4e0479941d0c9f754528b020ae2725998679eebd4f7ddd40f0e01fae3ace9af9"
SEMANTICS_PDF = "60ad3e29e905a9f405e70733cb1ddeffa41fdcc6b9dcbe962e462b2422a2d455"
DAILY = "e678ff47ec2de3537b05f631b4917c3ba0e53a9eac29f566865e998c40bd3f6a"
FRAGMENT = "b3a07aac8d979104bd53b5c6f7ad0bd50dfe78e26f723307c644bdb130cb6c96"
JSON_RAW = "d0a4ce808d3e022625c97a22b774d0387b2108f56f584c6b626c7effc9a0978d"
EMPTY = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    raw = path.read_bytes()
    return {"path": path.relative_to(REPO).as_posix(), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


class HeaderParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.current = None
        self.headers = []

    def handle_starttag(self, tag, attrs):
        if tag == "td" and "data-name" in dict(attrs):
            self.current = {"field": dict(attrs)["data-name"], "label": ""}

    def handle_data(self, data):
        if self.current is not None:
            self.current["label"] += data

    def handle_endtag(self, tag):
        if tag == "td" and self.current is not None:
            self.current["label"] = self.current["label"].strip()
            self.headers.append(self.current)
            self.current = None


def inspect():
    config = (OLD / CONFIG).read_text(encoding="utf-8")
    daily = (EVIDENCE / DAILY).read_text(encoding="utf-8")
    fragment = (EVIDENCE / FRAGMENT).read_text(encoding="utf-8")
    value_doc = load(EVIDENCE / JSON_RAW)
    assert '/r/cms/chinese/chinamoney/html/currency/daily-pledged-repo.html' in daily
    assert "var PR_PUBLISHED_TIME = 2200;" in config
    assert "DQSURL = '/dqs/rest/'" in config and "BK_URL = '/ags/ms/'" in config
    assert "cm-u-dlrp/PrDlyBltnExcel?lang=cn&searchDate=" in fragment
    assert "indexType : \"markInterBankVOList\"" in fragment
    assert 'lang : "en"' in fragment and 'type: "POST"' in fragment
    headers = HeaderParser()
    headers.feed(fragment)
    assert headers.headers[:8] == headers.headers[8:] and len(headers.headers) == 16
    labels = {h["field"]: h["label"] for h in headers.headers}
    assert labels["wghtdAvgRepoRate"] == "加权利率(%)"
    assert labels["clsngRepoRate"] == "收盘利率(%)"
    assert value_doc["head"]["rep_code"] == "200"
    assert value_doc["data"]["lastDate"] == "2026-08-28"
    records = value_doc["records"]
    targets = [r for r in records if r["instrmntCd"] == "DR007"]
    assert len(targets) == 1 and len(records) == 6
    target = targets[0]
    assert Decimal(target["wghtdAvgRepoRate"]) == Decimal("1.3859")
    assert Decimal(target["clsngRepoRate"]) == Decimal("1.3806")
    assert Decimal(target["openRepoRate"]) == Decimal("1.3700")
    legacy_doc = load(OLD / "readonly-checks.json")
    legacy = next(row for row in legacy_doc["legacy_projection"]["macro"]["transmission"]["evidence"] if row["metric_id"] == "CN_DR007")
    assert legacy["period"] == "2026-08-28" and legacy["unit"] == "percent"
    assert Decimal(str(legacy["value"])) == Decimal(target["wghtdAvgRepoRate"])
    receipts = load(EVIDENCE / "receipts.json")
    api_receipt = next(r for r in receipts if r["sha256"] == JSON_RAW)
    query = parse_qs(urlsplit(api_receipt["url"]).query)
    assert query == {"lang": ["en"], "indexType": ["markInterBankVOList"], "searchDate": ["2026-08-28"], "publishedTime": ["2200"]}
    return {
        "target_metric": "CN_DR007", "target_period": "2026-08-28",
        "official_instrument": "DR007", "official_field": "wghtdAvgRepoRate", "official_unit": "percent",
        "official_value": target["wghtdAvgRepoRate"], "official_target_record": target,
        "response_record_count": len(records), "response_instruments": [r["instrmntCd"] for r in records],
        "official_table_headers": headers.headers[:8],
        "legacy_read_at": legacy_doc["read_at"], "legacy_evidence_snapshot": legacy,
        "comparison": {"target_fields_compared": 1, "matched": 1, "source": "Old TuShare observation snapshot vs newly fetched official CFETS weighted rate; no new DB read or certification."},
        "conditional_spread_basis_points": str((Decimal(target["wghtdAvgRepoRate"]) - Decimal("1.4")) * 100),
        "wrong_close_field_spread_basis_points": str((Decimal(target["clsngRepoRate"]) - Decimal("1.4")) * 100),
        "official_response_query": query, "official_response_head": value_doc["head"], "official_response_data": value_doc["data"],
        "publication": {"release_at": None, "public_available_at": None, "reason": "lastDate is observation date; head.tstext is current response time; publishedTime=2200 is a request parameter from reused official JS, not historical release evidence; no row-level release timestamp supplied."},
        "channel_method": {"official_page_uses": "POST for JSON and GET anchor for Excel", "this_research_used": "GET only; JSON endpoint accepted documented read parameters with GET; no POST/auth/challenge bypass"},
        "history_coverage": {"certified_120_chinese_days": False, "observed_startDate": value_doc["data"]["startDate"], "observed_endDate": value_doc["data"]["endDate"], "queried_dates": ["2026-08-28"], "remaining": "One official sample does not establish 120-day channel history or publication vintages; do not expand family sampling into mandatory daily dual-source matching."},
        "reused_evidence_hashes": [digest(OLD / CONFIG), digest(OLD / SEMANTICS_PDF), digest(OLD / "readonly-checks.json")],
        "new_certifications": 0, "production_mutations": 0, "db_reads": 0,
    }


def verify():
    inspection = inspect()
    assert inspection == load(EVIDENCE / "source-inspection.json")
    receipts = load(EVIDENCE / "receipts.json")
    assert len(receipts) == 4 and sorted(r["status"] for r in receipts) == [200, 200, 200, 403]
    for r in receipts:
        actual = digest(EVIDENCE / r["local_file"])
        assert actual["sha256"] == r["sha256"] and actual["bytes"] == r["bytes"]
        assert r["method"] == "GET" and r["truncated"] is False and r["public_available_at"] is None
        assert datetime.fromisoformat(r["received_at"]) >= datetime.fromisoformat(r["started_at"])
    failed = next(r for r in receipts if r["status"] == 403)
    assert failed["bytes"] == 0 and failed["sha256"] == EMPTY
    assert digest(OLD / CONFIG)["sha256"] == CONFIG and digest(OLD / SEMANTICS_PDF)["sha256"] == SEMANTICS_PDF
    assert digest(PROJECT / "research-13.md")["sha256"] == REPORT13_SHA
    prior = load(EVIDENCE / "prior-attempts.json")
    assert prior["old_gets_total"] == len(load(OLD / "receipts.json"))
    assert all(r["url"] not in {p["url"] for p in load(OLD / "receipts.json")} for r in receipts)
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
        "validation": "passed", "new_get_attempts": 4, "http_200": 3, "http_403": 1,
        "new_response_artifacts_including_empty_failure": 4, "new_response_bytes": sum(r["bytes"] for r in receipts),
        "valid_target_value_responses": 1, "official_dr007_20260828_percent": inspection["official_value"],
        "target_value_matches_legacy": True, "public_available_at": None,
        "verified_new_response_artifacts": [digest(EVIDENCE / r["sha256"]) for r in receipts],
        "reused_evidence": inspection["reused_evidence_hashes"], "old_report_sha256_unchanged": REPORT13_SHA,
        "report_local_links_checked": links, "delivery_path_count": len(paths), "files": files,
        "manifest_self_hash_excluded": True, "network_requests_during_verification": 0,
    }


if __name__ == "__main__":
    if sys.argv[1:] == ["--write-inspection"]:
        result = inspect()
        (EVIDENCE / "source-inspection.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({k: result[k] for k in ("official_value", "comparison", "publication")}, indent=2))
    else:
        result = verify()
        path = EVIDENCE / "delivery-verification.json"
        if sys.argv[1:] == ["--write-manifest"]:
            path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        else:
            assert not sys.argv[1:] and result == load(path)
        print(json.dumps({k: result[k] for k in ("validation", "new_get_attempts", "http_200", "http_403", "new_response_bytes", "official_dr007_20260828_percent", "public_available_at", "delivery_path_count")}, indent=2))
