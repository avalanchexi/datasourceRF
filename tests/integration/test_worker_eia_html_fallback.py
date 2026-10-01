"""Without a usable EIA API key the Worker still reads Brent and WTI from the key-free page.

The published rows stay background-only and awaiting source certification; what changes is that
their value comes from the official history page, whose publication time is known only to the day.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, date, datetime
from email.message import Message
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.error import HTTPError

import pytest

from pring_cycle.acquisition import AcquisitionRepository
from pring_cycle.acquisition_outcome import AcquisitionOutcomes
from pring_cycle.eia_context import EiaPetroleumAdapter
from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime

ORIGINALS = {
    "RBRTE": "b078a362332a3d6b34ae2a5dc5a91b98ddfacc7979410b32081f07e9dadc243e",
    "RWTC": "7da3e5b6632942bfedf02642fde22867d24bb0cf6477eff5ac9e5f9be4d92497",
}


def original(series: str) -> bytes:
    content = (
        Path(__file__).resolve().parents[2]
        / ".scratch/pring-data-acquisition-repair/evidence-14"
        / ORIGINALS[series]
    ).read_bytes()
    assert hashlib.sha256(content).hexdigest() == ORIGINALS[series]
    return content


def serve_history_pages(monkeypatch: pytest.MonkeyPatch, requested: list[str]) -> None:
    from pring_cycle.eia_html import FetchedEiaHistory

    def fetch(url: str) -> FetchedEiaHistory:
        requested.append(url)
        series = "RWTC" if "RWTC" in url.upper() else "RBRTE"
        return FetchedEiaHistory(original(series), url, 200, "text/html; charset=utf-8")

    monkeypatch.setattr("pring_cycle.eia_context.fetch_eia_history", fetch, raising=False)
    monkeypatch.setattr("pring_cycle.worker.fetch_eia_history", fetch, raising=False)


@pytest.mark.usefixtures("runtime_clock")
def test_a_missing_key_falls_back_to_the_official_history_page(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pring_cycle.worker import refresh_eia_context

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    requested: list[str] = []
    serve_history_pages(monkeypatch, requested)
    attempts: list[dict[str, Any]] = []

    outcome = refresh_eia_context(
        paths,
        secrets={},
        target=date(2026, 9, 4),
        definition_version="metric-catalog-v0002",
        record=lambda metrics, channel, result, **details: attempts.append(
            {"metrics": tuple(metrics), "channel": channel, "outcome": result, **details}
        ),
    )

    assert outcome == "verified_candidate"
    assert len(requested) == 2
    # The API channel is recorded as unusable, and the page channel carries the values, a
    # publication known only to the day.
    recorded = {item["channel"]: item for item in attempts}
    assert recorded["eia_official_candidate"]["outcome"] == "not_attempted"
    assert recorded["eia_official_candidate"]["request_sent"] == "false"
    assert page_attempts(paths) == {"complete"}
    series = EvidenceRepository(paths.database).metric_series(
        "EIA_BRENT_RBRTE",
        mode=AsOfMode.SYSTEM,
        as_of=datetime.now(UTC),
        definition_version="metric-catalog-v0002",
    )
    brent = [point for point in series if point.period_end == "2026-09-01"]
    assert brent and brent[-1].selected_value == 96.02
    assert brent[-1].claims[0].certification_status == "awaiting_source_certification"
    receipts = [
        item
        for item in AcquisitionRepository(paths.database, paths.artifacts).history()
        if item.api_name == "eia_history_html"
    ]
    assert len(receipts) == 2


@pytest.mark.usefixtures("runtime_clock")
def test_a_rejected_key_records_the_failure_before_falling_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A key that the API rejects is reported as its own failure, never hidden by the fallback."""
    from pring_cycle.worker import refresh_eia_context

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    requested: list[str] = []
    serve_history_pages(monkeypatch, requested)

    def rejected(_parameters: dict[str, object]) -> bytes:
        raise HTTPError(
            "https://api.eia.gov/v2/petroleum/pri/spt/data/",
            403,
            "Forbidden",
            Message(),
            BytesIO(b"forbidden"),
        )

    monkeypatch.setattr(
        "pring_cycle.worker._eia_context_adapter",
        lambda api_key: EiaPetroleumAdapter(api_key, transport=rejected),
    )
    attempts: list[dict[str, Any]] = []

    outcome = refresh_eia_context(
        paths,
        secrets={"EIA_API_KEY": "rejected-key"},
        target=date(2026, 9, 4),
        definition_version="metric-catalog-v0002",
        record=lambda metrics, channel, result, **details: attempts.append(
            {"metrics": tuple(metrics), "channel": channel, "outcome": result, **details}
        ),
    )

    assert outcome == "verified_candidate"
    # The adapter records the API's refusal with its code; the Worker adds nothing (ticket 18).
    assert attempts == []
    refused = channel_attempts(paths, "eia_official_candidate")
    assert {(item["metric_id"], item["outcome"], item["external_code"]) for item in refused} == {
        ("EIA_BRENT_RBRTE", "source_failed", "403"),
        ("EIA_WTI_RWTC", "source_failed", "403"),
    }
    assert page_attempts(paths) == {"complete"}


def channel_attempts(paths: RuntimePaths, channel: str) -> list[dict[str, Any]]:
    with sqlite3.connect(paths.database) as connection:
        rows = connection.execute(
            "SELECT metric_id, outcome, safe_metadata_json FROM retrieval_attempt WHERE channel=?",
            (channel,),
        ).fetchall()
    return [
        {"metric_id": metric_id, "outcome": outcome, **json.loads(metadata)}
        for metric_id, outcome, metadata in rows
    ]


def page_attempts(paths: RuntimePaths) -> set[str]:
    """How each metric's page turned out, as the page recorded it (ticket 17)."""

    outcomes = set()
    for metric_id in ("EIA_BRENT_RBRTE", "EIA_WTI_RWTC"):
        attempt = AcquisitionOutcomes(paths.database).latest(metric_id, as_of=datetime.now(UTC))
        assert attempt is not None and attempt.channel == "eia_html_candidate"
        assert attempt.release_date is not None and attempt.outcome == "succeeded"
        outcomes.add(str(attempt.completeness))
    return outcomes


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("unavailable", ["RBRTE", "RWTC"])
def test_each_history_page_keeps_its_own_outcome(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, unavailable: str
) -> None:
    """Ticket 17: one page failing neither stops the other nor rewrites how it turned out."""
    from pring_cycle.eia_html import FetchedEiaHistory
    from pring_cycle.worker import refresh_eia_context

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    requested: list[str] = []

    def fetch(url: str) -> FetchedEiaHistory:
        requested.append(url)
        series = "RWTC" if "RWTC" in url.upper() else "RBRTE"
        if series == unavailable:
            raise OSError("fixture_page_unavailable")
        return FetchedEiaHistory(original(series), url, 200, "text/html; charset=utf-8")

    monkeypatch.setattr("pring_cycle.worker.fetch_eia_history", fetch, raising=False)
    attempts: list[str] = []

    refresh_eia_context(
        paths,
        secrets={},
        target=date(2026, 9, 4),
        definition_version="metric-catalog-v0002",
        record=lambda metrics, channel, result, **details: attempts.append(channel),
    )

    assert len(requested) == 2
    assert attempts == ["eia_official_candidate"]  # the pages record themselves
    outcomes = {
        metric_id: AcquisitionOutcomes(paths.database).latest(metric_id, as_of=datetime.now(UTC))
        for metric_id in ("EIA_BRENT_RBRTE", "EIA_WTI_RWTC")
    }
    failed = "EIA_BRENT_RBRTE" if unavailable == "RBRTE" else "EIA_WTI_RWTC"
    for metric_id, attempt in outcomes.items():
        assert attempt is not None and attempt.channel == "eia_html_candidate"
        if metric_id == failed:
            assert (attempt.outcome, attempt.error_type) == ("source_failed", "OSError")
        else:
            assert attempt.outcome == "succeeded" and attempt.release_date


@pytest.mark.usefixtures("runtime_clock")
def test_a_page_refused_by_its_structure_check_names_its_metric_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ticket 17: each page's receipt is its own metric's, so the other is not listed."""
    from pring_cycle.acquisition import own_acquisitions
    from pring_cycle.batches import processing_batch
    from pring_cycle.eia_html import FetchedEiaHistory
    from pring_cycle.runs import RunRepository
    from pring_cycle.worker import refresh_eia_context

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)

    def fetch(url: str) -> FetchedEiaHistory:
        series = "RWTC" if "RWTC" in url.upper() else "RBRTE"
        media_type = "application/json" if series == "RWTC" else "text/html; charset=utf-8"
        return FetchedEiaHistory(original(series), url, 200, media_type)

    monkeypatch.setattr("pring_cycle.worker.fetch_eia_history", fetch, raising=False)
    run = RunRepository(paths.database).submit(
        command_type="report_generation",
        target_business_date="2026-09-04",
        client_request_id="eia-pages",
        model_version_id="model-v0001",
        system_as_of=datetime.now(UTC),
    )
    with processing_batch(run.run_id), own_acquisitions(paths.database, run.run_id, "fixture"):
        refresh_eia_context(
            paths,
            secrets={},
            target=date(2026, 9, 4),
            definition_version="metric-catalog-v0002",
            record=lambda *args, **kwargs: None,
        )

    rejected = AcquisitionOutcomes(paths.database).for_batch(run.run_id).structure_rejections()
    assert [item.metric_ids for item in rejected] == [("EIA_WTI_RWTC",)]


@pytest.mark.usefixtures("runtime_clock")
def test_a_series_the_api_left_out_is_taken_from_its_page_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ticket 18: the API's partial delivery stands; only the missing series' page is read."""
    from pring_cycle.worker import refresh_eia_context

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    requested: list[str] = []
    serve_history_pages(monkeypatch, requested)
    brent_only = {
        "response": {
            "frequency": "daily",
            "data": [
                {
                    "period": "2026-09-01",
                    "series": "RBRTE",
                    "series-description": "Europe Brent Spot Price FOB",
                    "value": "71.25",
                    "units": "Dollars per Barrel",
                }
            ],
        }
    }
    monkeypatch.setattr(
        "pring_cycle.worker._eia_context_adapter",
        lambda api_key: EiaPetroleumAdapter(
            api_key, transport=lambda _parameters: json.dumps(brent_only).encode()
        ),
    )

    refresh_eia_context(
        paths,
        secrets={"EIA_API_KEY": "fixture-key"},
        target=date(2026, 9, 4),
        definition_version="metric-catalog-v0002",
        record=lambda *args, **kwargs: None,
    )

    assert len(requested) == 1 and "RWTC" in requested[0].upper()
    brent = AcquisitionOutcomes(paths.database).latest("EIA_BRENT_RBRTE", as_of=datetime.now(UTC))
    wti = AcquisitionOutcomes(paths.database).latest("EIA_WTI_RWTC", as_of=datetime.now(UTC))
    assert brent is not None and brent.channel == "eia_official_candidate"
    assert wti is not None and wti.channel == "eia_html_candidate"


def test_full_run_without_a_key_takes_both_real_history_tables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Phase two #04: the 9/23 tables the first real run rejected are no longer rejected."""
    from pring_cycle.eia_html import FetchedEiaHistory
    from pring_cycle.projections import ProjectionSetRepository
    from pring_cycle.runs import RunRepository
    from pring_cycle.worker import process_pending_run
    from tests.integration.test_eia_html_acquisition import real_history
    from tests.integration.test_gap_list import CUTOFF, TARGET, seed
    from tests.integration.test_worker_execution import runtime

    def fetch(url: str) -> FetchedEiaHistory:
        series = "RWTC" if "RWTC" in url.upper() else "RBRTE"
        return FetchedEiaHistory(real_history(series), url, 200, "text/html")

    monkeypatch.setattr("pring_cycle.worker.fetch_eia_history", fetch, raising=False)
    paths = runtime(tmp_path)
    seed(paths)
    submitted = RunRepository(paths.database).submit_manual_full(
        target_business_date=TARGET.isoformat(),
        client_request_id="eia-real-tables",
        model_version_id="model-v0001",
        system_as_of=CUTOFF,
        cutoff_mode="explicit",
    )

    process_pending_run(paths, report_adapters=())

    assert RunRepository(paths.database).get(submitted.run_id).status == "completed"
    pages = [
        item
        for item in AcquisitionRepository(paths.database, paths.artifacts).history()
        if item.api_name == "eia_history_html"
    ]
    assert {item.state for item in pages} == {"validated"}
    assert len(pages) == 2
    gaps = ProjectionSetRepository(paths.database).current().datasets["cycle_overview"]["gap_list"]
    # The explicit cutoff predates the fixture's acquisition time, so the values are not
    # yet held there; what matters is that no table is rejected.
    assert not [
        g for g in gaps if str(g["metric_id"]).startswith("EIA_") and g["category"] == "rejected"
    ]
