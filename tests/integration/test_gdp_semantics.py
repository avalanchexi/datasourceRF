from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from pring_cycle.acquisition import AcquisitionRepository, own_acquisitions
from pring_cycle.context_projection import build_context_projection
from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.models import CALIBRATION_BASELINE, ModelRepository
from pring_cycle.official_context import (
    FetchedOfficialContextDocument,
    ingest_official_context_document,
    refresh_official_context_document,
)
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.tushare_context import ContextScalar, TushareContextAdapter, ingest_context_scalars


@pytest.mark.usefixtures("runtime_clock")
def test_gdp_acquisition_preserves_levels_without_mislabeling_disputed_yoy(tmp_path: Path) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    # A transport-shaped fixture from the archived Q2 comparison. NBS single
    # quarter total/secondary/tertiary are 4.3/3.0/5.1, not 4.7/3.9/5.2.
    row = {
        "quarter": "2026Q2",
        "gdp": 695704.0,
        "gdp_yoy": 4.7,
        "pi": 31521.8,
        "pi_yoy": 3.7,
        "si": 250472.9,
        "si_yoy": 3.9,
        "ti": 413709.2,
        "ti_yoy": 5.2,
    }
    originals = []

    def transport(payload):
        assert payload["api_name"] == "cn_gdp"
        fields = payload["fields"].split(",")
        raw = json.dumps(
            {"code": 0, "data": {"fields": fields, "items": [[row[f] for f in fields]]}}
        ).encode()
        originals.append(raw)
        return raw

    adapter = TushareContextAdapter("fixture-secret", transport=transport)
    result = adapter.acquire_scalars(
        paths,
        lambda: adapter.gdp(start_quarter="2026Q2", end_quarter="2026Q2"),
        definition_version="metric-catalog-v0002",
    )
    assert result.observation_count == 4
    evidence = EvidenceRepository(paths.database)
    points = evidence.metric_series(
        "CN_GDP",
        mode=AsOfMode.SYSTEM,
        as_of=datetime.now(UTC),
        definition_version="metric-catalog-v0002",
    )
    assert {p.dimensions["measure"] for p in points} == {"nominal_ytd_level"}
    assert {p.dimensions["aggregate"]: p.claims[0].value for p in points} == {
        "total": 695704.0,
        "primary": 31521.8,
        "secondary": 250472.9,
        "tertiary": 413709.2,
    }
    assert all(p.claims[0].public_available_at is None for p in points)
    receipts = AcquisitionRepository(paths.database, paths.artifacts)
    receipt = receipts.history()[0]
    assert receipts.read_content(receipt.acquisition_id, "raw") == originals[0]
    normalized = json.loads(receipts.read_content(receipt.acquisition_id, "normalized"))
    assert {item["source_field"] for item in normalized["rejected_fields"]} == {
        "gdp_yoy",
        "pi_yoy",
        "si_yoy",
        "ti_yoy",
    }
    assert {item["reason"] for item in normalized["rejected_fields"]} == {
        "gdp_yoy_period_semantics_unverified"
    }
    assert receipt.parser_version == "tushare-gdp-parser-v0003"


@pytest.mark.parametrize("later_failure", [None, "http", "parse"])
@pytest.mark.usefixtures("runtime_clock")
def test_official_gdp_quarter_yoy_keeps_its_distinct_verified_table_columns(
    tmp_path: Path, later_failure: str | None
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    models = ModelRepository(paths.database)
    models.record_acceptance("model-v0001", CALIBRATION_BASELINE)
    models.activate("model-v0001", explicitly_approved=True)
    run = RunRepository(paths.database).submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id="official-gdp-candidate",
        model_version_id="model-v0001",
        system_as_of=datetime.now(UTC),
    )
    digest = "60b12f6257d62842e7ea13e5c79bf868438fb382e7857bd6f88ab4110c588915"
    content = (
        Path(__file__).resolve().parents[2]
        / ".scratch/pring-data-acquisition-repair/evidence-14"
        / digest
    ).read_bytes()
    assert hashlib.sha256(content).hexdigest() == digest
    EvidenceRepository(paths.database).record_retrieval_attempt(
        metric_id="CN_GDP",
        channel="tushare",
        outcome="missing_credentials",
        fetched_at=datetime.now(UTC),
        safe_metadata={
            "period": "2026-08-28",
            "target_business_date": "2026-08-28",
            "definition_version": "metric-catalog-v0001",
        },
    )
    with own_acquisitions(
        paths.database, run.run_id, "gap_retrieval", metric_ids=("CN_GDP",), period="2026-Q2"
    ):
        result = ingest_official_context_document(
            paths,
            content,
            family="nbs_gdp",
            source_url="https://www.stats.gov.cn/sj/zxfb/202607/t20260716_1964142.html",
            expected_period="2026-Q2",
            fetched_at=datetime.now(UTC),
            definition_version="metric-catalog-v0001",
        )
    assert result.observation_count == 8
    evidence = EvidenceRepository(paths.database)
    points = evidence.metric_series(
        "CN_GDP",
        mode=AsOfMode.SYSTEM,
        as_of=datetime.now(UTC),
        definition_version="metric-catalog-v0001",
    )
    quarter = [p for p in points if p.dimensions["measure"] == "real_quarter_yoy"]
    assert {p.dimensions["aggregate"]: p.claims[0].value for p in quarter} == {
        "total": 4.3,
        "primary": 3.7,
        "secondary": 3.0,
        "tertiary": 5.1,
    }
    assert {p.claims[0].public_available_at for p in quarter} == {
        datetime(2026, 7, 16, 1, 30, tzinfo=UTC)
    }
    assert all(p.claims[0].certification_status == "awaiting_source_certification" for p in points)
    attempt = evidence.latest_retrieval_attempt(
        "CN_GDP",
        period=None,
        target_business_date="2026-08-28",
        as_of=datetime.now(UTC),
        definition_version="metric-catalog-v0001",
    )
    assert attempt is not None
    assert attempt.outcome == "verified_candidate"
    assert attempt.safe_metadata["period"] == "2026-Q2"
    assert attempt.safe_metadata["target_business_date"] == "2026-08-28"
    assert attempt.safe_metadata["run_id"] == run.run_id
    context = build_context_projection(
        evidence,
        as_of=datetime.now(UTC),
        model_manifest=models.manifest("model-v0001"),
        target_business_date="2026-08-28",
    )
    rows = [row for row in context.macro["international_context"] if row["metric_id"] == "CN_GDP"]
    assert {row["acquisition_status"] for row in rows} == {"verified_candidate"}
    assert {row["certification_status"] for row in rows} == {"awaiting_source_certification"}
    assert all(row["value"] is None for row in rows)
    if later_failure is None:
        return

    before_failure = datetime.now(UTC)
    started: list[str] = []

    def failed_fetch(url: str) -> FetchedOfficialContextDocument:
        if later_failure == "http":
            raise OSError("fixture source unavailable")
        return FetchedOfficialContextDocument(b"<html>no GDP table</html>", "text/html", url, 200)

    with (
        own_acquisitions(
            paths.database, run.run_id, "gap_retrieval", metric_ids=("CN_GDP",), period="2026-Q2"
        ),
        pytest.raises(OSError if later_failure == "http" else ValueError),
    ):
        refresh_official_context_document(
            paths,
            family="nbs_gdp",
            source_url="https://www.stats.gov.cn/sj/zxfb/202607/t20260716_1964142.html",
            expected_period="2026-Q2",
            fetched_at=datetime(2026, 7, 16, tzinfo=UTC),
            fetcher=failed_fetch,
            definition_version="metric-catalog-v0001",
            on_acquisition_started=started.append,
        )
    latest = evidence.latest_retrieval_attempt(
        "CN_GDP",
        period=None,
        target_business_date="2026-08-28",
        as_of=datetime.now(UTC),
        definition_version="metric-catalog-v0001",
    )
    assert latest is not None
    outcome = "source_failed" if later_failure == "http" else "validation_failed"
    assert latest.outcome == outcome
    assert latest.fetched_at >= before_failure
    assert len(started) == 1
    assert latest.safe_metadata["acquisition_ids"] == started[0]
    assert latest.safe_metadata["period"] == "2026-Q2"
    assert latest.safe_metadata["run_id"] == run.run_id
    assert (
        evidence.latest_retrieval_attempt(
            "CN_GDP",
            period=None,
            target_business_date="2026-08-28",
            as_of=before_failure,
            definition_version="metric-catalog-v0001",
        )
        == attempt
    )
    refreshed = build_context_projection(
        evidence,
        as_of=datetime.now(UTC),
        model_manifest=models.manifest("model-v0001"),
        target_business_date="2026-08-28",
    )
    gdp_rows = [r for r in refreshed.macro["international_context"] if r["metric_id"] == "CN_GDP"]
    assert {r["acquisition_status"] for r in gdp_rows} == {outcome}
    assert (
        evidence.metric_series(
            "CN_GDP",
            mode=AsOfMode.SYSTEM,
            as_of=datetime.now(UTC),
            definition_version="metric-catalog-v0001",
        )
        == points
    )


def test_direct_scalar_ingestion_cannot_restore_the_rejected_provider_mapping(
    tmp_path: Path,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    scalar = ContextScalar(
        metric_id="CN_GDP",
        api_name="cn_gdp",
        source_field="gdp_yoy",
        period_kind="quarter",
        period_start="2026-04-01",
        period_end="2026-06-30",
        dimensions={"aggregate": "total", "measure": "real_quarter_yoy"},
        value=4.7,
        unit="percent",
    )
    with pytest.raises(ValueError, match="gdp_yoy_period_semantics_unverified"):
        ingest_context_scalars(
            paths,
            (scalar,),
            fetched_at=datetime.now(UTC),
            definition_version="metric-catalog-v0002",
        )
    assert (
        EvidenceRepository(paths.database).metric_series(
            "CN_GDP",
            mode=AsOfMode.SYSTEM,
            as_of=datetime.now(UTC),
            definition_version="metric-catalog-v0002",
        )
        == ()
    )
