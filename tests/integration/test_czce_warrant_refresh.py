"""Run findings 02: TA and CF warrants taken from CZCE's own daily report (ADR-0032).

One serial request a trading day not yet held, each symbol-day held or refused on its own,
and the consumers' reparse accepts what was taken.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from itertools import count
from pathlib import Path

import pytest

from pring_cycle.czce_warrants import refresh_czce_warrants
from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.metric_contracts import CZCE_PROVIDER, czce_warrant_url
from pring_cycle.models import EFFECTIVE_CATALOG_VERSION, ModelRepository, effective_model_manifest
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.warrant_inputs import select_warrant_inputs
from tests.conftest import _clock_datetime
from tests.fixtures.czce_report import czce_exchange, czce_report

# The newest model, whatever it is numbered.
CURRENT_MODEL = str(effective_model_manifest()["model_version_id"])

FIXTURES = Path(__file__).parents[1] / "fixtures" / "czce_warrants"
MAY_19, SEP_02 = date(2026, 5, 19), date(2026, 9, 2)
FILES = {
    czce_warrant_url(MAY_19): (FIXTURES / "FutureDataWhsheet-20260519.txt").read_bytes(),
    czce_warrant_url(SEP_02): (FIXTURES / "FutureDataWhsheet-20260902.txt").read_bytes(),
}


@pytest.fixture
def paths(tmp_path: Path) -> RuntimePaths:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    models = ModelRepository(paths.database)
    models.register(effective_model_manifest())
    models.activate(CURRENT_MODEL, explicitly_approved=True)
    return paths


class Exchange:
    def __init__(self, files: dict[str, bytes]) -> None:
        self.files = files
        self.requested: list[str] = []
        self.slept: list[float] = []

    def fetch(self, url: str) -> bytes:
        self.requested.append(url)
        if url not in self.files:
            raise OSError("czce_warrant_http_404")
        return self.files[url]

    def refresh(self, paths: RuntimePaths, *days: date) -> dict[str, int]:
        return refresh_czce_warrants(
            paths,
            days=days,
            definition_version=EFFECTIVE_CATALOG_VERSION,
            fetch=self.fetch,
            sleep=self.slept.append,
        )


def held(paths: RuntimePaths) -> dict[tuple[str, str], dict[str, float]]:
    """Held CZCE warehouse totals by symbol and day."""
    result: dict[tuple[str, str], dict[str, float]] = {}
    for point in EvidenceRepository(paths.database).metric_series(
        "CN_FUTURES_WARRANTS",
        mode=AsOfMode.SYSTEM,
        as_of=datetime.now(UTC),
        definition_version=EFFECTIVE_CATALOG_VERSION,
    ):
        claim = next(c for c in point.claims if c.claim_id == point.selected_claim_id)
        if point.dimensions["measure"] == "registered_receipts":
            assert claim.provider == CZCE_PROVIDER
            assert point.selected_value is not None
            key = (point.dimensions["symbol"], point.period_end)
            result.setdefault(key, {})[point.dimensions["warehouse"]] = point.selected_value
    return result


def attempts(paths: RuntimePaths) -> list[tuple[str, str, str, str | None]]:
    with sqlite3.connect(paths.database) as connection:
        rows = connection.execute(
            "SELECT outcome, safe_metadata_json FROM retrieval_attempt "
            "WHERE channel='czce_official' ORDER BY fetched_at, rowid"
        ).fetchall()
    return [
        (
            outcome,
            meta["business_date"],
            meta["symbol"],
            meta.get("rule_reason") or meta.get("reason"),
        )
        for outcome, meta in ((row[0], json.loads(row[1])) for row in rows)
    ]


def test_each_day_not_held_is_requested_once_serially_and_held_days_never_again(
    paths: RuntimePaths,
) -> None:
    exchange = Exchange(FILES)

    newly = exchange.refresh(paths, SEP_02, MAY_19)

    assert newly == {"CF": 2, "TA": 2}
    # One request a day for both symbols, oldest first, a pause between the two.
    assert exchange.requested == [czce_warrant_url(MAY_19), czce_warrant_url(SEP_02)]
    assert exchange.slept == [1.0]
    holdings = held(paths)
    assert len(holdings["TA", "2026-05-19"]) == 27
    assert holdings["TA", "2026-05-19"]["长江国际"] == 1176
    assert sum(holdings["TA", "2026-05-19"].values()) == 180755
    assert sum(holdings["TA", "2026-09-02"].values()) == 1069
    assert sum(holdings["CF", "2026-09-02"].values()) == 8858

    assert exchange.refresh(paths, MAY_19, SEP_02) == {"CF": 0, "TA": 0}
    assert exchange.requested == [czce_warrant_url(MAY_19), czce_warrant_url(SEP_02)]


def test_a_changed_pta_block_refuses_only_that_symbol_day(paths: RuntimePaths) -> None:
    changed = FILES[czce_warrant_url(MAY_19)].replace(
        "|仓单数量(完税)  |仓单数量(保税)  |当日增减  |有效预报  |升贴水".encode(),
        "|仓单数量(完税)  |当日增减  |有效预报  |升贴水".encode(),
        1,
    )
    exchange = Exchange({**FILES, czce_warrant_url(MAY_19): changed})

    assert exchange.refresh(paths, MAY_19, SEP_02) == {"CF": 2, "TA": 1}

    assert ("TA", "2026-05-19") not in held(paths)
    assert (
        "structure_rejected",
        "2026-05-19",
        "TA",
        "czce_warrant_header_mismatch",
    ) in attempts(paths)
    with sqlite3.connect(paths.database) as connection:
        checks = connection.execute(
            "SELECT json_extract(parameters_json, '$.symbol'), "
            "json_extract(parameters_json, '$.business_date'), structure_check, rejection_reason "
            "FROM acquisition_request WHERE provider=?",
            (CZCE_PROVIDER,),
        ).fetchall()
    assert sorted(checks) == [
        ("CF", "2026-05-19", "passed", None),
        ("CF", "2026-09-02", "passed", None),
        ("TA", "2026-05-19", "rejected", "czce_warrant_header_mismatch"),
        ("TA", "2026-09-02", "passed", None),
    ]


def test_a_day_without_its_file_leaves_only_that_day_missing(paths: RuntimePaths) -> None:
    missing_day = date(2026, 5, 20)
    exchange = Exchange(FILES)

    assert exchange.refresh(paths, MAY_19, missing_day, SEP_02) == {"CF": 2, "TA": 2}

    assert len(exchange.requested) == 3
    assert {
        (symbol, reason)
        for outcome, day, symbol, reason in attempts(paths)
        if day == "2026-05-20" and outcome == "source_failed"
    } == {("CF", "czce_warrant_http_404"), ("TA", "czce_warrant_http_404")}


def test_an_unreachable_exchange_stops_the_run_s_requests(paths: RuntimePaths) -> None:
    exchange = Exchange(FILES)

    def unreachable(url: str) -> bytes:
        exchange.requested.append(url)
        raise OSError("timed out")

    exchange.fetch = unreachable  # type: ignore[method-assign]

    assert exchange.refresh(paths, MAY_19, SEP_02) == {"CF": 0, "TA": 0}
    assert exchange.requested == [czce_warrant_url(MAY_19)]
    assert exchange.slept == []


@pytest.mark.parametrize(
    ("reading", "failed_at"),
    [(1, "received"), (2, "validated")],
    ids=["received", "validated"],
)
def test_a_clock_stepping_back_fails_only_that_symbol_day(
    paths: RuntimePaths, monkeypatch: pytest.MonkeyPatch, reading: int, failed_at: str
) -> None:
    """Run findings 2026-10-02, ticket 04 (a): the system clock stepped back while CF's
    5/18 receipt was in flight; that one failure skipped TA's day and every later day."""
    exchange = Exchange(FILES)
    # A day behind, a millisecond a reading: every reading is past what the test reads at.
    origin, ticks = datetime.now(UTC) - timedelta(days=1), count()
    step_back = timedelta()
    readings_after_answer: int | None = None

    def now() -> datetime:
        nonlocal step_back, readings_after_answer
        if readings_after_answer is not None:
            readings_after_answer += 1
            if readings_after_answer == reading:
                # The receipt's first reading after the answer is when it was received, the
                # second when it was validated: the clock steps back there and stays back.
                step_back = timedelta(seconds=7)
                readings_after_answer = None
        return origin + timedelta(milliseconds=next(ticks)) - step_back

    def fetch(url: str) -> bytes:
        nonlocal readings_after_answer
        content = Exchange.fetch(exchange, url)
        if url == czce_warrant_url(MAY_19):
            readings_after_answer = 0
        return content

    exchange.fetch = fetch  # type: ignore[method-assign]
    monkeypatch.setattr("pring_cycle.acquisition.datetime", _clock_datetime(now))

    assert exchange.refresh(paths, MAY_19, SEP_02) == {"CF": 1, "TA": 2}

    # TA was taken from the same one response, and the later day as ever.
    assert exchange.requested == [czce_warrant_url(MAY_19), czce_warrant_url(SEP_02)]
    assert ("CF", "2026-05-19") not in held(paths)
    assert {("TA", "2026-05-19"), ("CF", "2026-09-02"), ("TA", "2026-09-02")} <= set(held(paths))
    assert (
        "local_failed",
        "2026-05-19",
        "CF",
        "acquisition_time_invalid",
    ) in attempts(paths)
    with sqlite3.connect(paths.database) as connection:
        receipt = connection.execute(
            "SELECT state, received_at IS NOT NULL, rejection_reason FROM acquisition_request "
            "WHERE provider=? AND json_extract(parameters_json, '$.symbol')='CF' "
            "AND json_extract(parameters_json, '$.business_date')='2026-05-19'",
            (CZCE_PROVIDER,),
        ).fetchone()
    assert receipt == ("failed", failed_at == "validated", "acquisition_time_invalid")


def _store_failing(error: Exception) -> tuple[str, Callable[..., None]]:
    def store_artifact(*_args: object, **_kwargs: object) -> None:
        raise error

    return "pring_cycle.acquisition.store_artifact", store_artifact


def _ingest_failing(error: Exception) -> tuple[str, Callable[..., None]]:
    def append_source_claims(*_args: object, **_kwargs: object) -> None:
        raise error

    return "pring_cycle.evidence.EvidenceRepository.append_source_claims", append_source_claims


@pytest.mark.parametrize(
    ("failing", "error", "recorded"),
    [
        (_store_failing, OSError("disk full"), [("local_failed", "2026-05-19", "CF")]),
        (
            _store_failing,
            ValueError("artifact_store_failed"),
            [("local_failed", "2026-05-19", "CF")],
        ),
        # The database failing is no outcome the refresh records: it stops it unrecorded.
        (_store_failing, sqlite3.OperationalError("database is locked"), []),
        (_ingest_failing, OSError("disk full"), [("local_failed", "2026-05-19", "CF")]),
    ],
    ids=["disk", "local_value_error", "database", "ingest_disk"],
)
def test_any_other_local_failure_still_stops_the_refresh(
    paths: RuntimePaths,
    monkeypatch: pytest.MonkeyPatch,
    failing: Callable[[Exception], tuple[str, Callable[..., None]]],
    error: Exception,
    recorded: list[tuple[str, str, str]],
) -> None:
    exchange = Exchange(FILES)
    monkeypatch.setattr(*failing(error))

    with pytest.raises(type(error), match=str(error)):
        exchange.refresh(paths, MAY_19, SEP_02)

    assert exchange.requested == [czce_warrant_url(MAY_19)]
    assert [(outcome, day, symbol) for outcome, day, symbol, _reason in attempts(paths)] == recorded


def test_the_consumers_reparse_accepts_the_czce_members(paths: RuntimePaths) -> None:
    Exchange(FILES).refresh(paths, SEP_02)
    repository = EvidenceRepository(paths.database)
    points = repository.metric_series(
        "CN_FUTURES_WARRANTS",
        mode=AsOfMode.SYSTEM,
        as_of=datetime.now(UTC),
        definition_version=EFFECTIVE_CATALOG_VERSION,
    )

    selection = select_warrant_inputs(
        repository,
        points,
        period="2026-09-02",
        mode=AsOfMode.SYSTEM,
        definition_version=EFFECTIVE_CATALOG_VERSION,
    )

    # The six TuShare symbols hold nothing here; TA and CF are complete.
    assert not [m for m in selection.missing_members if m.endswith((":TA", ":CF"))]
    assert len(selection.selected_claim_ids) == 2 * (26 + len(held(paths)["CF", "2026-09-02"]))


def test_an_older_tushare_claim_for_the_same_warehouse_is_not_selected(
    paths: RuntimePaths,
) -> None:
    Exchange(FILES).refresh(paths, SEP_02)
    # TuShare delivered TA until ADR-0032; such a claim stays stored but is never selected
    # nor a conflict, though it names the same warehouse and day.
    with sqlite3.connect(paths.database) as connection:
        connection.execute(
            """
            INSERT INTO source_claim (
                claim_id, observation_id, metric_id, definition_version, period_kind,
                period_start, period_end, dimensions_json, value, value_state, unit, provider,
                source_reference, release_event_id, release_at, public_available_at,
                fetched_at, available_at, certification_status, quality_status,
                supersedes_claim_id, inferred_public_at
            )
            SELECT 'claim-tushare-ta', observation_id, metric_id, definition_version,
                   period_kind, period_start, period_end, dimensions_json, value + 7,
                   value_state, unit, 'tushare', 'tushare:fut_wsr:vol:2026-09-02',
                   'tushare:fut_wsr:2026-09-02', release_at, public_available_at, fetched_at,
                   available_at, certification_status, quality_status, NULL,
                   inferred_public_at
            FROM source_claim
            WHERE provider=? AND json_extract(dimensions_json, '$.symbol')='TA'
              AND json_extract(dimensions_json, '$.measure')='registered_receipts'
            LIMIT 1
            """,
            (CZCE_PROVIDER,),
        )
    points = EvidenceRepository(paths.database).metric_series(
        "CN_FUTURES_WARRANTS",
        mode=AsOfMode.SYSTEM,
        as_of=datetime.now(UTC),
        definition_version=EFFECTIVE_CATALOG_VERSION,
    )

    assert {p.selection_status for p in points} == {"selected"}
    assert all(c.provider == CZCE_PROVIDER for p in points for c in p.claims), (
        "the retired TuShare claim is not among the point's claims"
    )


def test_a_gap_day_refetch_notes_a_change_that_disagrees_with_the_held_session_before(
    paths: RuntimePaths,
) -> None:
    monday, tuesday = date(2026, 9, 21), date(2026, 9, 22)
    reports = {
        monday: czce_report(monday, pta=[("甲库", 100, 0)], cotton=[("乙库", 30, 0)]),
        # PTA moved by +5 but reports +3; cotton agrees.
        tuesday: czce_report(tuesday, pta=[("甲库", 105, 3)], cotton=[("乙库", 28, -2)]),
    }
    exchange = czce_exchange(lambda day: False, overrides=reports)
    refresh_czce_warrants(
        paths, days=(monday,), definition_version=EFFECTIVE_CATALOG_VERSION, fetch=exchange
    )

    # A gap day's refetch asks for that day alone.
    refresh_czce_warrants(
        paths, days=(tuesday,), definition_version=EFFECTIVE_CATALOG_VERSION, fetch=exchange
    )

    with sqlite3.connect(paths.database) as connection:
        notes = {
            meta["symbol"]: json.loads(meta["reconciliation"])
            for meta in (
                json.loads(row[0])
                for row in connection.execute(
                    "SELECT safe_metadata_json FROM retrieval_attempt "
                    "WHERE channel='czce_official' AND outcome='succeeded'"
                )
            )
            if meta["business_date"] == "2026-09-22"
        }
    assert notes == {
        "CF": [],
        "TA": [{"warehouse": "甲库", "total": 105, "previous_total": 100.0, "change": 3}],
    }
