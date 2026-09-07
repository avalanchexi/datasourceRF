from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from pring_cycle.acquisition import own_acquisitions
from pring_cycle.context_projection import build_context_projection
from pring_cycle.eia_html import FetchedEiaHistory, refresh_eia_history
from pring_cycle.evidence import EvidenceRepository
from pring_cycle.models import CALIBRATION_BASELINE, ModelRepository
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.treasury_context import FetchedTreasuryYieldCsv, refresh_treasury_yields


@pytest.mark.parametrize("source", ["treasury", "eia"])
def test_acquired_source_timing_survives_public_context_projection(
    tmp_path: Path, source: str
) -> None:
    root = next(
        path for path in Path(__file__).resolve().parents if (path / "pyproject.toml").exists()
    )
    evidence_root = root / ".scratch/pring-data-acquisition-repair"
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    target = date(2026, 8, 28)
    models = ModelRepository(paths.database)
    models.record_acceptance("model-v0001", CALIBRATION_BASELINE)
    models.activate("model-v0001", explicitly_approved=True)
    run = RunRepository(paths.database).submit_manual_full(
        target_business_date=str(target),
        client_request_id="source-timing-fixture",
        model_version_id="model-v0001",
        system_as_of=datetime.now(UTC),
    )
    if source == "treasury":
        raw = (
            evidence_root
            / "evidence-14-treasury-followup"
            / "a14a321adffded36dfd9ab1aec72cc81423aeca271110f76569d37dd02ca4ee5"
        ).read_bytes()
        with own_acquisitions(paths.database, run.run_id, "gap_retrieval"):
            refresh_treasury_yields(
                paths,
                start_date=target,
                end_date=target,
                definition_version="metric-catalog-v0001",
                fetcher=lambda url: FetchedTreasuryYieldCsv(raw, url, 200, "text/csv"),
            )
        metric = "UST10Y_NOMINAL_YIELD"
        expected = {"latest_source_period": "2026-09-04", "source_timezone": "America/New_York"}
    else:
        raw = (
            evidence_root
            / "evidence-14"
            / "b078a362332a3d6b34ae2a5dc5a91b98ddfacc7979410b32081f07e9dadc243e"
        ).read_bytes()
        with own_acquisitions(paths.database, run.run_id, "gap_retrieval"):
            refresh_eia_history(
                paths,
                series_id="RBRTE",
                start_date=target,
                end_date=target,
                definition_version="metric-catalog-v0001",
                fetcher=lambda url: FetchedEiaHistory(raw, url, 200, "text/html; charset=utf-8"),
            )
        metric = "EIA_BRENT_RBRTE"
        expected = {
            "release_date": "2026-09-02",
            "next_release_date": "2026-09-10",
            "release_timezone": "America/New_York",
        }
    manifest = models.manifest("model-v0001")
    context = build_context_projection(
        EvidenceRepository(paths.database),
        as_of=datetime.now(UTC),
        model_manifest=manifest,
        target_business_date=str(target),
        persist_derived=False,
    )
    row = next(row for row in context.macro["international_context"] if row["metric_id"] == metric)
    # Unknown historical PUBLIC is excluded by the target-bound model view.
    assert row["period"] is None
    assert row["public_available_at"] is None
    assert row["value"] is None
    assert row["status"] == "awaiting_source_certification"
    acquisition = row["latest_acquisition"]
    assert acquisition is not None
    for key, value in expected.items():
        assert acquisition.get(key) == value
