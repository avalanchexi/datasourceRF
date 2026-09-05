"""Bounded, local source review; never certifies or changes the active runtime DB.

Run with the project's WSL Python and PYTHONPYCACHEPREFIX outside the checkout.
Raw responses go to the existing content-addressed artifact directory. Candidate
claims are exercised only in a separate review runtime under the native cache.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from urllib.request import Request, urlopen
from xml.etree import ElementTree
from zipfile import ZipFile

from pring_cycle.catalog import MARGIN_FINANCING_V0002, metric_definition
from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.secrets import parse_data_source_secrets
from pring_cycle.source_adapters import TUSHARE_ENDPOINT, TushareCoreAdapter
from pring_cycle.tushare_context import TushareContextAdapter, ingest_context_scalars


def main() -> None:
    active_paths = RuntimePaths.discover()
    token = parse_data_source_secrets(active_paths.secrets).get("TUSHARE_TOKEN")
    if not token:
        raise ValueError("tushare_not_configured")
    receipts: list[dict[str, object]] = []

    def store(raw: bytes) -> str:
        digest = hashlib.sha256(raw).hexdigest()
        path = active_paths.artifacts / digest[:2] / digest
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if path.exists():
            assert path.read_bytes() == raw
        else:
            with path.open("xb") as stream:
                stream.write(raw)
            path.chmod(0o600)
        return digest

    def read(digest: str) -> bytes:
        raw = (active_paths.artifacts / digest[:2] / digest).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == digest
        return raw

    def transport(payload: dict) -> dict:
        request = Request(
            TUSHARE_ENDPOINT,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=30) as response:
            raw = response.read()
        document = json.loads(raw)
        if document.get("code") != 0:
            raise ValueError("tushare_source_rejected")
        if token.encode() in raw:
            raise ValueError("response_contains_secret")
        receipts.append({
            "url": TUSHARE_ENDPOINT,
            "request": {key: value for key, value in payload.items() if key != "token"},
            "raw_sha256": store(raw),
            "bytes": len(raw),
            "fetched_at": datetime.now(UTC).isoformat(),
        })
        return document

    days = TushareCoreAdapter(token, transport=transport).trading_days(
        date(2026, 3, 9), date(2026, 8, 28)
    )
    assert len(days) == 120 and len(set(days)) == 120
    scalars = TushareContextAdapter(token, transport=transport).margin_financing_candidate(
        trading_days=days
    )
    assert len(scalars) == 240
    assert all(item.public_available_at is None and item.release_at is None for item in scalars)

    provider = json.loads(read(str(receipts[-1]["raw_sha256"])))
    fields = provider["data"]["fields"]
    sample = {
        row["exchange_id"]: row
        for values in provider["data"]["items"]
        if (row := dict(zip(fields, values, strict=True)))["trade_date"] == "20260828"
    }
    sse_hash = "fa7f73716372a7be474ff766b2eb8cebd7260d71d7e87c94884cd5727d6e5eed"
    szse_hash = "a0bccdd0398381440b43432cb8fc777f6e46a7e271a79d08ac6fdc56b031ab1c"
    sse = json.loads(read(sse_hash))["result"][0]
    assert sse["opDate"] == "20260828"
    from io import BytesIO
    with ZipFile(BytesIO(read(szse_hash))) as workbook:
        sheet = ElementTree.fromstring(workbook.read("xl/worksheets/sheet1.xml"))
    namespace = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    cells = {
        cell.attrib["r"]: "".join(cell.itertext())
        for cell in sheet.findall(".//s:sheetData/s:row/s:c", namespace)
    }
    assert cells["A1"] == "\u878d\u8d44\u4e70\u5165\u989d(\u5143)"
    assert cells["B1"] == "\u878d\u8d44\u4f59\u989d(\u5143)"
    official = {
        "SSE": {"rzye": sse["rzye"], "rzmre": sse["rzmre"]},
        "SZSE": {"rzye": cells["B2"].replace(",", ""),
                 "rzmre": cells["A2"].replace(",", "")},
    }
    comparisons = [
        {"exchange": exchange, "field": field, "unit": "cny",
         "official": str(value), "tushare": str(sample[exchange][field]),
         "equal": Decimal(str(value)) == Decimal(str(sample[exchange][field]))}
        for exchange, values in official.items()
        for field, value in values.items()
    ]
    assert all(item["equal"] for item in comparisons)

    review_paths = RuntimePaths.discover(active_paths.cache / "margin-review-20260905")
    initialize_runtime(review_paths)
    fetched_at = datetime.fromisoformat(str(receipts[-1]["fetched_at"]))
    result = ingest_context_scalars(
        review_paths, scalars, fetched_at=fetched_at, definition_version=MARGIN_FINANCING_V0002
    )
    repository = EvidenceRepository(review_paths.database)
    public = repository.metric_series(
        "CN_MARGIN_BALANCE", mode=AsOfMode.PUBLIC, as_of=fetched_at,
        definition_version=MARGIN_FINANCING_V0002,
    )
    assert not public
    normalized = json.dumps([asdict(item) for item in scalars], sort_keys=True).encode()
    manifest = {
        "kind": "margin_source_review_v0002",
        "status": "awaiting_source_certification",
        "official_comparison_date": "2026-08-28",
        "official_sample_hashes": {"SSE": sse_hash, "SZSE": szse_hash},
        "comparisons": comparisons,
        "raw_receipts": receipts,
        "definition": asdict(metric_definition("CN_MARGIN_BALANCE",
                                               definition_version=MARGIN_FINANCING_V0002)),
        "first_day": days[0].isoformat(), "last_day": days[-1].isoformat(),
        "trading_days": len(days), "exchange_rows": 360, "observations": len(scalars),
        "normalized_sha256": store(normalized),
        "unknown_publication_observations": len(scalars),
        "review_runtime": str(review_paths.override_root),
        "review_claim_count": len(result.claim_ids),
        "public_as_of_points": len(public),
        "active_database_modified": False,
        "remaining_gaps": ["BSE_official_numeric_sample", "actual_publication_evidence"],
    }
    manifest_hash = store(json.dumps(manifest, sort_keys=True, ensure_ascii=False).encode())
    print(json.dumps({"manifest_sha256": manifest_hash, **manifest}, ensure_ascii=False))


if __name__ == "__main__":
    main()
