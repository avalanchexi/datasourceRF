"""Exercise real official acquisition into a fresh isolated candidate store."""

from __future__ import annotations

import hashlib
import argparse
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from pring_cycle.acquisition import AcquisitionRepository
from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.official_context import refresh_official_context_document
from pring_cycle.runtime import RuntimePaths, initialize_runtime


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", action="store_true")
    arguments = parser.parse_args()
    output = Path(__file__).resolve().parent
    root = Path("/home/tywin/.cache/pring-cycle/verification/repair-14-live-official-20260907a")
    if root.exists() and not arguments.resume:
        raise RuntimeError("Refusing to reuse an existing acquisition runtime")
    paths = RuntimePaths.discover(root)
    if not paths.database.exists():
        initialize_runtime(paths)
    receipts = AcquisitionRepository(paths.database, paths.artifacts)
    evidence = EvidenceRepository(paths.database)
    records = []
    for family, metric_id, period, url in (
        (
            "pbc_usdcny_central_parity", "CN_USDCNY_CENTRAL_PARITY", "2026-09-04",
            "https://www.pbc.gov.cn/zhengcehuobisi/125207/125217/125925/2026090409004494582/index.html",
        ),
        (
            "nbs_gdp", "CN_GDP", "2026-Q2",
            "https://www.stats.gov.cn/sj/zxfb/202607/t20260716_1964142.html",
        ),
    ):
        record = {"family": family, "metric_id": metric_id, "period": period, "url": url}
        before = {r.acquisition_id for r in receipts.history()}
        acquired = [r for r in receipts.history() if r.parameters == {
            "source_url": url, "period": period, "family": family,
        }]
        if acquired:
            if not arguments.resume or len(acquired) != 1:
                raise RuntimeError("Unexpected existing request history")
            record.update(status="stored_candidate" if acquired[0].state == "validated" else "failed",
                          resumed_export=True, new_requests_this_resume=0)
        else:
            try:
                result = refresh_official_context_document(
                    paths, family=family, source_url=url, expected_period=period,
                    fetched_at=datetime.now(UTC), definition_version="metric-catalog-v0002",
                )
                record.update(status="stored_candidate", ingestion=asdict(result))
            except (OSError, TypeError, ValueError) as error:
                record.update(status="failed", error_type=type(error).__name__, error=str(error))
            acquired = [r for r in receipts.history() if r.acquisition_id not in before]
        record["receipts"] = [asdict(r) for r in acquired]
        for receipt in acquired:
            for kind, digest in (("raw", receipt.raw_hash), ("normalized", receipt.normalized_hash)):
                if digest is not None:
                    content = receipts.read_content(receipt.acquisition_id, kind)
                    if hashlib.sha256(content).hexdigest() != digest:
                        raise RuntimeError("Acquisition artifact hash mismatch")
                    destination = output / digest
                    if destination.exists() and destination.read_bytes() != content:
                        raise RuntimeError("Refusing to overwrite different artifact bytes")
                    destination.write_bytes(content)
        points = evidence.metric_series(
            metric_id, mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC),
            definition_version="metric-catalog-v0002",
        )
        record["claims"] = [
            {
                "claim_id": claim.claim_id,
                "period_start": point.period_start,
                "period_end": point.period_end,
                "dimensions": point.dimensions,
                "value": claim.value,
                "unit": claim.unit,
                "public_available_at": claim.public_available_at,
                "fetched_at": claim.fetched_at,
                "available_at": claim.available_at,
                "certification_status": claim.certification_status,
            }
            for point in points for claim in point.claims
        ]
        record["traces"] = [asdict(evidence.trace(
            point.observation_id, mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC)
        )) for point in points]
        records.append(record)
        report = {
            "scope": "real HTTP through public acquisition; fresh isolated candidate store",
            "runtime": str(root), "definition_version": "metric-catalog-v0002",
            "recorded_at": datetime.now(UTC), "attempted_families": len(records),
            "certification_grants": 0, "production_writes": 0,
            "model_activations": 0, "public_replay_completed": False,
            "records": records,
        }
        (output / "result.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8"
        )
        print(json.dumps({"family": family, "status": record["status"],
                          "requests": len(acquired), "claims": len(record["claims"])},
                         ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
