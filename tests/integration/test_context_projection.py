from __future__ import annotations

import calendar
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

import pring_cycle.context_projection as context_module
import pring_cycle.evidence as evidence_module
from pring_cycle.catalog import metric_definition
from pring_cycle.context_projection import build_context_projection
from pring_cycle.evidence import (
    AsOfMode,
    EvidenceRepository,
    EvidenceValueState,
    SourceClaimInput,
)
from pring_cycle.official_lpr import ingest_lpr_document
from pring_cycle.runtime import RuntimePaths, initialize_runtime

OFFICIAL_URL = "https://www.chinamoney.com.cn/chinese/rdgz/20260820/3399885.html"


def test_empty_context_is_structured_local_degradation_not_empty_placeholders(
    tmp_path: Path,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)

    context = build_context_projection(
        EvidenceRepository(paths.database),
        as_of=datetime(2026, 8, 30, tzinfo=UTC),
    )

    assert context.macro["policy_direction"] == "insufficient_data"
    assert context.macro["credit_response"] == "insufficient_data"
    assert context.macro["overheat_state"] == "insufficient_data"
    assert context.macro["price_pressure"] == "insufficient_data"
    assert context.macro["score"] is None
    assert len(context.macro["international_context"]) == 13  # type: ignore[arg-type]
    assert all(
        item["status"] == "awaiting_source_certification"
        for item in context.macro["international_context"]  # type: ignore[union-attr]
    )
    assert context.inventory["quadrant"] is None
    assert len(context.inventory["cards"]) == 7  # type: ignore[arg-type]
    assert context.inventory["score"] is None
    assert context.inventory["semantics"] == {
        "pmi_inventory": "diffusion_index_not_inventory_quantity",
        "futures_warrants": "registered_receipts_not_total_industrial_inventory",
    }


def test_certified_lpr_enters_credit_evidence_with_point_in_time_source_fields(
    tmp_path: Path,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    content = (
        Path(__file__).parents[1] / "fixtures/chinamoney_lpr_20260820.html"
    ).read_bytes()
    ingested = ingest_lpr_document(
        paths,
        content,
        source_url=OFFICIAL_URL,
        fetched_at=datetime(2026, 8, 20, 1, 2, tzinfo=UTC),
        expected_period="2026-08",
    )

    context = build_context_projection(
        EvidenceRepository(paths.database),
        as_of=datetime(2026, 8, 20, 2, tzinfo=UTC),
    )
    lpr_rows = context.macro["credit"]["evidence"][:2]  # type: ignore[index]

    assert {row["dimensions"]["tenor"] for row in lpr_rows} == {"1y", "5y_plus"}
    assert {row["status"] for row in lpr_rows} == {"current"}
    assert {row["source_reference"].split("#", maxsplit=1)[0] for row in lpr_rows} == {
        OFFICIAL_URL
    }
    assert {row["available_at"] for row in lpr_rows} == {"2026-08-20T01:02:00+00:00"}
    assert set(ingested.claim_ids) <= set(context.observation_version_ids)
    assert context.macro["credit_response"] == "insufficient_data"
    assert context.macro["policy_direction"] == "insufficient_data"


def test_lpr_carries_the_previous_period_as_awaiting_release_not_source_failure(
    tmp_path: Path,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    content = (
        Path(__file__).parents[1] / "fixtures/chinamoney_lpr_20260820.html"
    ).read_bytes()
    ingest_lpr_document(
        paths,
        content,
        source_url=OFFICIAL_URL,
        fetched_at=datetime(2026, 8, 20, 1, 2, tzinfo=UTC),
        expected_period="2026-08",
    )

    context = build_context_projection(
        EvidenceRepository(paths.database),
        as_of=datetime(2026, 9, 10, 2, tzinfo=UTC),
    )
    lpr_rows = context.macro["credit"]["evidence"][:2]  # type: ignore[index]

    assert {row["period"] for row in lpr_rows} == {"2026-08-31"}
    assert {row["status"] for row in lpr_rows} == {"awaiting_release"}


def test_lpr_gap_uses_a_recorded_source_failure_after_the_release_window(
    tmp_path: Path,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    repository = EvidenceRepository(paths.database)
    failed_at = datetime(2026, 8, 20, 5, tzinfo=UTC)
    repository.record_retrieval_attempt(
        metric_id="CN_LPR_1Y_5Y",
        channel="certified_official_direct",
        outcome="source_failed",
        fetched_at=failed_at,
        safe_metadata={"period": "2026-08"},
    )

    context = build_context_projection(repository, as_of=failed_at)
    lpr_rows = context.macro["credit"]["evidence"][:1]  # type: ignore[index]

    assert lpr_rows[0]["status"] == "source_failed"
    assert lpr_rows[0]["value"] is None


def test_conflicted_certified_sources_keep_every_claim_and_do_not_drive_state(
    tmp_path: Path,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    repository = EvidenceRepository(paths.database)
    content = (
        Path(__file__).parents[1] / "fixtures/chinamoney_lpr_20260820.html"
    ).read_bytes()
    ingested = ingest_lpr_document(
        paths,
        content,
        source_url=OFFICIAL_URL,
        fetched_at=datetime(2026, 8, 20, 1, 2, tzinfo=UTC),
        expected_period="2026-08",
    )
    conflicting = repository.append_source_claim(
        SourceClaimInput(
            metric_id="CN_LPR_1Y_5Y",
            definition_version="metric-catalog-v0001",
            period_kind="month",
            period_start="2026-08-01",
            period_end="2026-08-31",
            dimensions={"tenor": "1y"},
            value=3.1,
            value_state=EvidenceValueState.REPORTED_VALUE,
            unit="percent",
            provider="certified-secondary-fixture",
            source_reference="fixture:conflicting-lpr-1y",
            release_event_id="fixture:lpr:2026-08",
            release_at=datetime(2026, 8, 20, 1, tzinfo=UTC),
            public_available_at=datetime(2026, 8, 20, 1, tzinfo=UTC),
            fetched_at=datetime(2026, 8, 20, 1, 3, tzinfo=UTC),
            available_at=datetime(2026, 8, 20, 1, 3, tzinfo=UTC),
            certification_status="certified",
            quality_status="validated",
        )
    )

    context = build_context_projection(
        repository,
        as_of=datetime(2026, 8, 20, 2, tzinfo=UTC),
    )
    lpr_1y = next(
        row
        for row in context.macro["credit"]["evidence"]  # type: ignore[index]
        if row["dimensions"] == {"tenor": "1y"}
    )

    assert lpr_1y["status"] == "conflicted"
    assert {claim["value"] for claim in lpr_1y["claims"]} == {3.0, 3.1}
    assert set(ingested.claim_ids) | {conflicting.claim_id} <= set(
        context.observation_version_ids
    )
    assert context.macro["credit_response"] == "insufficient_data"


def test_credit_impulse_is_persisted_with_exact_point_in_time_input_vintages(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    repository = EvidenceRepository(paths.database)
    certified_ids = {"CN_SF_TOTAL", "CN_GDP"}

    def certified_definition(metric_id: str):  # type: ignore[no-untyped-def]
        definition = metric_definition(metric_id)
        return (
            replace(definition, certification_status="certified")
            if metric_id in certified_ids
            else definition
        )

    monkeypatch.setattr(evidence_module, "metric_definition", certified_definition)
    monkeypatch.setattr(context_module, "metric_definition", certified_definition)
    input_claim_ids = []
    for index in range(24):
        year = 2024 + index // 12
        month = index % 12 + 1
        end_day = calendar.monthrange(year, month)[1]
        value = 2.0 if year == 2024 else 3.0
        input_claim_ids.append(
            repository.append_source_claim(
                _certified_claim(
                    metric_id="CN_SF_TOTAL",
                    period_start=f"{year:04d}-{month:02d}-01",
                    period_end=f"{year:04d}-{month:02d}-{end_day:02d}",
                    dimensions={"measure": "monthly_increment"},
                    value=value,
                    unit="hundred_million_cny",
                )
            ).claim_id
        )
    for index, (period_start, period_end) in enumerate(
        (
            ("2024-01-01", "2024-03-31"),
            ("2024-04-01", "2024-06-30"),
            ("2024-07-01", "2024-09-30"),
            ("2024-10-01", "2024-12-31"),
            ("2025-01-01", "2025-03-31"),
            ("2025-04-01", "2025-06-30"),
            ("2025-07-01", "2025-09-30"),
            ("2025-10-01", "2025-12-31"),
        )
    ):
        input_claim_ids.append(
            repository.append_source_claim(
                _certified_claim(
                    metric_id="CN_GDP",
                    period_start=period_start,
                    period_end=period_end,
                    dimensions={"aggregate": "total", "measure": "nominal_quarterly_level"},
                    value=25.0 if index < 4 else 30.0,
                    unit="hundred_million_cny",
                )
            ).claim_id
        )

    cutoff = datetime(2026, 1, 31, tzinfo=UTC)
    context = build_context_projection(repository, as_of=cutoff)
    formula = context.macro["credit"]["formula"]  # type: ignore[index]
    impulse = next(
        row
        for row in context.macro["credit"]["evidence"]  # type: ignore[index]
        if row["metric_id"] == "CN_CREDIT_IMPULSE"
    )

    assert formula["status"] == "available"
    assert formula["formula_version"] == "credit-impulse-rolling-share-v0001"
    assert impulse["value"] == pytest.approx(6.0)
    assert impulse["direction"] == "up"
    assert set(impulse["input_observation_version_ids"]) == set(input_claim_ids)
    derived_id = str(impulse["derived_observation_id"])
    assert derived_id in context.observation_version_ids
    trace = repository.derived_trace(derived_id, mode=AsOfMode.SYSTEM, as_of=cutoff)
    assert set(trace.input_observation_version_ids) == set(input_claim_ids)


def _certified_claim(
    *,
    metric_id: str,
    period_start: str,
    period_end: str,
    dimensions: dict[str, str],
    value: float,
    unit: str,
) -> SourceClaimInput:
    available = datetime(2026, 1, 15, tzinfo=UTC)
    return SourceClaimInput(
        metric_id=metric_id,
        definition_version="metric-catalog-v0001",
        period_kind="quarter" if metric_id == "CN_GDP" else "month",
        period_start=period_start,
        period_end=period_end,
        dimensions=dimensions,
        value=value,
        value_state=EvidenceValueState.REPORTED_VALUE,
        unit=unit,
        provider="certified-fixture",
        source_reference=f"fixture:{metric_id}:{period_end}:{sorted(dimensions.items())}",
        release_event_id=f"release:{metric_id}:{period_end}",
        release_at=available,
        public_available_at=available,
        fetched_at=available,
        available_at=available,
        certification_status="certified",
        quality_status="validated",
    )
