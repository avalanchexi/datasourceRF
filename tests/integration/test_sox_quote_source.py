"""Ticket 09 (residuals 2026-10-14): SOX is held from Nasdaq's own history of the index.

Nasdaq Global Indexes, SOX's administrator, answers its history page's table for a window
(ADR-0042). Each session's end-of-day value is held by its U.S. trade date; an answer that
no longer reads as that table is a source failure with its reason code, never a value.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import parse_qs

import pytest

from pring_cycle.acquisition import AcquisitionRepository
from pring_cycle.acquisition_outcome import SOURCE_FAILED, SUCCEEDED, AcquisitionOutcomes
from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.quote_sources import NASDAQ_SOX, refresh_quote_source
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from tests.conftest import OfficialFile

METRIC = "NASDAQ_SOX_INDEX"
VERSION = "metric-catalog-v0001"
FIXTURES = Path(__file__).parents[1] / "fixtures" / "quote_sources"
# The site's answer for 2026-10-01..10-13 as taken on 2026-10-14.
HISTORY = (FIXTURES / "nasdaq-sox-history-20261013.json").read_bytes()


@pytest.fixture
def paths(tmp_path: Path) -> RuntimePaths:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    return paths


def serve(monkeypatch: pytest.MonkeyPatch, content: bytes) -> list[dict[str, list[str]]]:
    forms: list[dict[str, list[str]]] = []

    def official(request: Any, *, timeout: float) -> OfficialFile:
        forms.append(parse_qs(request.data.decode()))
        return OfficialFile(request.full_url, content)

    monkeypatch.setattr("pring_cycle.quote_sources.open_no_redirects", official)
    return forms


def refresh(paths: RuntimePaths, start: date, end: date) -> int:
    return refresh_quote_source(
        paths, NASDAQ_SOX, start_date=start, end_date=end, definition_version=VERSION
    )


def held(paths: RuntimePaths) -> dict[str, float | None]:
    return {
        point.period_end: point.selected_value
        for point in EvidenceRepository(paths.database).metric_series(
            METRIC,
            mode=AsOfMode.SYSTEM,
            as_of=datetime.now(UTC) + timedelta(minutes=1),
            definition_version=VERSION,
        )
    }


def last_attempt(paths: RuntimePaths) -> Any:
    return AcquisitionOutcomes(paths.database).latest(
        METRIC, as_of=datetime.now(UTC) + timedelta(minutes=1)
    )


def test_each_session_of_the_window_is_held_by_its_trade_date(
    paths: RuntimePaths, monkeypatch: pytest.MonkeyPatch
) -> None:
    forms = serve(monkeypatch, HISTORY)

    added = refresh(paths, date(2026, 10, 7), date(2026, 10, 13))

    # The index itself over the run's window, at the end of each day.
    assert forms == [
        {
            "id": ["SOX"],
            "startDate": ["2026-10-07T00:00:00.000"],
            "endDate": ["2026-10-13T00:00:00.000"],
            "timeOfDay": ["EOD"],
        }
    ]
    assert added == 5
    assert {day: round(value or 0, 2) for day, value in held(paths).items()} == {
        "2026-10-07": 13066.15,
        "2026-10-08": 12623.71,
        "2026-10-09": 12572.42,
        "2026-10-12": 12236.79,
        "2026-10-13": 12208.79,
    }
    attempt = last_attempt(paths)
    assert attempt.outcome == SUCCEEDED
    # The receipt names the request as it went out: a form posted, not a file got.
    [acquisition_id] = attempt.acquisition_ids
    receipt = AcquisitionRepository(paths.database, paths.artifacts).get(acquisition_id)
    assert (receipt.provider, receipt.api_name) == ("Nasdaq Global Indexes", "official_http_post")


@pytest.mark.parametrize(
    ("content", "reason"),
    [
        (b"<html><iframe src='/_Incapsula_Resource'></iframe></html>", "document_invalid"),
        (
            json.dumps({"aaData": [{"TimeStamp": "/Date(1791864000000)/", "Value": None}]}),
            "value_invalid",
        ),
    ],
)
def test_an_answer_that_is_not_the_history_table_is_a_source_failure(
    paths: RuntimePaths, monkeypatch: pytest.MonkeyPatch, content: bytes | str, reason: str
) -> None:
    serve(monkeypatch, content if isinstance(content, bytes) else content.encode())

    with pytest.raises(ValueError, match=f"nasdaq_index_{reason}"):
        refresh(paths, date(2026, 10, 1), date(2026, 10, 13))

    attempt = last_attempt(paths)
    assert (attempt.outcome, attempt.metadata["reason"]) == (
        SOURCE_FAILED,
        f"nasdaq_index_{reason}",
    )
    assert held(paths) == {}


def test_a_refused_request_keeps_the_sites_status_and_its_page(
    paths: RuntimePaths, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The site's anti-bot service answers a page of its own, the likeliest failure here.
    page = b"<html><iframe src='/_Incapsula_Resource?CWUDNSAI=23'></iframe></html>"

    def refused(request: Any, *, timeout: float) -> OfficialFile:
        raise HTTPError(request.full_url, 403, "Forbidden", None, BytesIO(page))  # type: ignore[arg-type]

    monkeypatch.setattr("pring_cycle.quote_sources.open_no_redirects", refused)

    with pytest.raises(OSError, match="quote_source_http_403"):
        refresh(paths, date(2026, 10, 1), date(2026, 10, 13))

    attempt = last_attempt(paths)
    assert (attempt.outcome, attempt.metadata["reason"], attempt.metadata["external_code"]) == (
        SOURCE_FAILED,
        "quote_source_http_403",
        "403",
    )
    [acquisition_id] = attempt.acquisition_ids
    raw = AcquisitionRepository(paths.database, paths.artifacts).read_content(acquisition_id, "raw")
    assert raw == page
    assert held(paths) == {}
