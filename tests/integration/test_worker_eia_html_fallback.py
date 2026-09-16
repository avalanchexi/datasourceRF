"""Without a usable EIA API key the Worker still reads Brent and WTI from the key-free page.

The published rows stay background-only and awaiting source certification; what changes is that
their value comes from the official history page, whose publication time is known only to the day.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.acquisition import AcquisitionRepository
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
    # The API channel is recorded as unusable, and the page channel carries the values.
    recorded = {item["channel"]: item for item in attempts}
    assert recorded["eia_official_candidate"]["outcome"] == "missing_credentials"
    page = recorded["eia_html_candidate"]
    assert page["outcome"] == "verified_candidate"
    assert page["publication_precision"] == "release_date_only"
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

    def rejected(*_args: Any, **_kwargs: Any) -> None:
        raise OSError("HTTP Error 403: Forbidden")

    monkeypatch.setattr("pring_cycle.worker.acquire_eia_spot_prices", rejected, raising=False)
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
    recorded = {item["channel"]: item for item in attempts}
    assert recorded["eia_official_candidate"]["outcome"] == "source_failed"
    assert recorded["eia_official_candidate"]["error_type"] == "OSError"
    assert recorded["eia_html_candidate"]["outcome"] == "verified_candidate"
