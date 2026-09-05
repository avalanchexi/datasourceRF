"""Capture/replay 120 source input matrices; no certification or runtime DB writes."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.request import Request, urlopen

from pring_cycle.runtime import RuntimePaths
from pring_cycle.runtime_fingerprint import execution_fingerprint
from pring_cycle.market_breadth import FullDaySuspensionEvidence
from pring_cycle.secrets import parse_data_source_secrets
from pring_cycle.source_adapters import TUSHARE_ENDPOINT
from pring_cycle.tushare_context import TushareContextAdapter


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--limit", type=int, default=120)
    parser.add_argument("--without-official-resolutions", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.limit <= 120:
        raise ValueError("review_day_limit_invalid")
    paths = RuntimePaths.discover()
    review = paths.cache / "breadth-review-20260905"
    review.mkdir(parents=True, exist_ok=True, mode=0o700)
    receipt_path = review / "receipts.json"
    receipts = json.loads(receipt_path.read_text()) if receipt_path.exists() else []
    token = "offline" if args.offline else parse_data_source_secrets(paths.secrets)["TUSHARE_TOKEN"]
    network_requests = 0
    last_request = 0.0

    def store(raw: bytes) -> str:
        digest = hashlib.sha256(raw).hexdigest()
        path = paths.artifacts / digest[:2] / digest
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if path.exists():
            assert path.read_bytes() == raw
        else:
            with path.open("xb") as stream:
                stream.write(raw)
            path.chmod(0o600)
        return digest

    def read(digest: str) -> bytes:
        raw = (paths.artifacts / digest[:2] / digest).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == digest
        return raw

    def transport(payload: dict) -> dict:
        nonlocal network_requests, last_request
        request_data = {key: value for key, value in payload.items() if key != "token"}
        for receipt in receipts:
            if receipt["request"] == request_data:
                return json.loads(read(receipt["raw_sha256"]))
        if args.offline:
            raise ValueError("offline_receipt_missing")
        time.sleep(max(0.0, 0.5 - (time.monotonic() - last_request)))
        last_request = time.monotonic()
        request = Request(TUSHARE_ENDPOINT, data=json.dumps(payload).encode(),
                          headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(request, timeout=30) as response:
            raw = response.read()
        network_requests += 1
        if token.encode() in raw:
            raise ValueError("response_contains_secret")
        document = json.loads(raw)
        if document.get("code") != 0:
            raise ValueError("tushare_source_rejected")
        receipts.append({"url": TUSHARE_ENDPOINT, "request": request_data,
                         "fetched_at": datetime.now(UTC).isoformat(),
                         "raw_sha256": store(raw), "bytes": len(raw)})
        temporary = receipt_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(receipts, indent=2))
        temporary.chmod(0o600)
        temporary.replace(receipt_path)
        return document

    calendar_hash = "d0740f44c9648b5adc6ba98fe9acb59565858e8195cdf25df09e59f691b94635"
    calendar = json.loads(read(calendar_hash))["data"]
    days = sorted(date.fromisoformat(row["cal_date"])
                  for values in calendar["items"]
                  if str((row := dict(zip(calendar["fields"], values, strict=True)))["is_open"]) == "1")
    assert len(days) == len(set(days)) == 120
    days = days[:args.limit]
    official_evidence = [] if args.without_official_resolutions else [
        {"business_date": "2026-06-16", "ts_code": "603159.SH",
         "document_sha256": "f6103823d476d069330acc1080c1df8e245799625146d23fada44605dac87329",
         "url": "https://big5.sse.com.cn/site/cht/www.sse.com.cn/disclosure/listedinfo/announcement/c/new/2026-06-16/603159_20260616_1C14.pdf",
         "assertion": "full_day_suspension", "publication_precision": "date_only"},
        {"business_date": "2026-07-06", "ts_code": "002731.SZ",
         "document_sha256": "ac25307c061923f16bfc4e5aa63fc06bd995fc25813592ce869b0689aee0106c",
         "url": "https://static.cninfo.com.cn/finalpage/2026-07-06/1225410169.PDF",
         "assertion": "full_day_suspension", "publication_precision": "date_only"},
    ]
    evidence = tuple(
        FullDaySuspensionEvidence(date.fromisoformat(item["business_date"]), item["ts_code"],
                                  item["document_sha256"])
        for item in official_evidence if date.fromisoformat(item["business_date"]) in days
    )
    for item in evidence:
        assert read(item.document_sha256).startswith(b"%PDF-")
    source = TushareContextAdapter(token, transport=transport)
    checks = []
    for index, day in enumerate(days):
        try:
            frame = source.market_breadth_inputs(
                trading_days=(day,),
                full_day_suspension_evidence=tuple(item for item in evidence if item.business_date == day),
            )[0]
        except ValueError as error:
            check = {"date": day.isoformat(), "status": "failed", "reason": str(error)}
        else:
            normalized = json.dumps(asdict(frame), sort_keys=True, default=str).encode()
            check = {"date": day.isoformat(), "status": "inputs_validated",
                     "listed": len(frame.listed_codes), "suspended": len(frame.suspended_codes),
                     "quoted": len(frame.quotes),
                     "unknown_after_hours": sum(q.after_hours_amount is None for q in frame.quotes),
                     "normalized_sha256": store(normalized)}
        checks.append(check)
        if check["status"] == "failed" or (index + 1) % 10 == 0:
            print(json.dumps({"completed_days": index + 1, **check}), flush=True)
    manifest = {"kind": "breadth_source_input_review", "status": "awaiting_source_certification",
                "execution_fingerprint": execution_fingerprint(paths),
                "review_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "calendar_sha256": calendar_hash, "days": checks, "receipts": receipts,
                "official_suspension_evidence": official_evidence,
                "input_validation_status": "passed" if all(item["status"] == "inputs_validated" for item in checks) else "failed",
                "network_requests_this_run": network_requests,
                "validated_days": sum(item["status"] == "inputs_validated" for item in checks),
                "requested_days": len(days), "active_database_modified": False,
                "publication_claims_created": 0, "certification_records_created": 0}
    digest = store(json.dumps(manifest, sort_keys=True).encode())
    (review / "review.json").write_text(json.dumps({"manifest_sha256": digest, **manifest}, indent=2))
    print(json.dumps({key: value for key, value in {"manifest_sha256": digest, **manifest}.items()
                      if key not in ("days", "receipts")}), flush=True)
    if manifest["input_validation_status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
