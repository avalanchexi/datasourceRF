"""One symbol's bad warrant delivery leaves the other symbols' histories held.

Run findings 2026-09-26, ticket 01: a PTA row with a negative quantity used to refuse every
symbol's receipts of the run, since all eight were fetched in one acquisition. Held apart,
a symbol still missing on the target day keeps the metric in the gap list. TA and CF now
come from CZCE's own report (ticket 02, ADR-0032), unreachable here, so TuShare is asked for
the other six only and a crude oil row stands in for the bad one.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Iterator
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from pring_cycle.acquisition import own_acquisitions
from pring_cycle.acquisition_outcome import AcquisitionOutcomes
from pring_cycle.batches import processing_batch
from pring_cycle.context_projection import ContextProjectionRules
from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.freshness import gap_list, record_run_freshness
from pring_cycle.models import EFFECTIVE_CATALOG_VERSION, ModelRepository, effective_model_manifest
from pring_cycle.retrieval import RetrievalAdapterResponse
from pring_cycle.retrieval_ledger import RetrievalLedger, utc_now
from pring_cycle.runs import RetrievalScope, RunRecord, RunRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.targeted_context import _warrant_symbols_to_refetch, retrieve_tushare_context
from pring_cycle.trading_calendar import TradingCalendar
from pring_cycle.tushare_context import (
    WARRANT_SYMBOLS,
    ContextObservationsMissingError,
    warrant_answer_days,
)
from pring_cycle.worker import refresh_context_sources
from tests.conftest import install_runtime_clock

# The newest model, whatever it is numbered.
CURRENT_MODEL = str(effective_model_manifest()["model_version_id"])

TARGET = date(2026, 8, 3)
CLOCK = datetime(2026, 8, 4, 1, tzinfo=UTC)
EXCHANGES = {"CF": "CZCE", "PTA": "CZCE", "SC": "INE", "PP": "DCE"}
UNITS = {"CF": "张", "PTA": "张", "SC": "桶"}


def warrant_response(
    payload: dict[str, Any], *, unavailable: str | None = None, negative: str | None = None
) -> bytes:
    """One warehouse a symbol every weekday; ``negative`` adds a misplaced negative row."""
    params = payload["params"]
    symbol = params["symbol"]
    if symbol == unavailable:
        raise OSError("fixture_warrant_unavailable")
    start = datetime.strptime(params["start_date"], "%Y%m%d").date()
    end = datetime.strptime(params["end_date"], "%Y%m%d").date()
    days = [start + timedelta(days=n) for n in range((end - start).days + 1)]
    exchange, unit = EXCHANGES.get(symbol, "SHFE"), UNITS.get(symbol, "吨")
    rows: list[list[object]] = [
        [day.strftime("%Y%m%d"), symbol, f"{symbol}-warehouse", None, 20, 0, unit, exchange]
        for day in days
        if day.weekday() < 5
    ]
    if symbol == negative and rows:
        rows.append([rows[-1][0], symbol, f"{symbol}-warehouse", None, -144, None, unit, exchange])
    fields = ["trade_date", "symbol", "warehouse", "pre_vol", "vol", "vol_chg", "unit", "exchange"]
    return json.dumps({"code": 0, "data": {"fields": fields, "items": rows}}).encode()


class WarrantsOnly:
    unavailable: str | None = None
    negative: str | None = "SC"

    def open(self, request: Any, *, timeout: int) -> BytesIO:
        payload = json.loads(request.data)
        if payload["api_name"] == "fut_wsr":
            return BytesIO(
                warrant_response(payload, unavailable=self.unavailable, negative=self.negative)
            )
        raise OSError("fixture_context_unavailable")


class CopperUnavailable(WarrantsOnly):
    unavailable = "CU"
    negative = None


def offline(*args: object, **kwargs: object) -> Any:
    raise OSError("offline")


def prepared(
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
    root: Path,
    opener: type[WarrantsOnly] = WarrantsOnly,
) -> tuple[RuntimePaths, RunRecord]:
    install_runtime_clock(monkeypatch, request, CLOCK)
    monkeypatch.setattr("pring_cycle.eia_html.open_no_redirects", offline)
    monkeypatch.setattr("pring_cycle.quote_sources.open_no_redirects", offline)
    monkeypatch.setattr("pring_cycle.ecb_reference.open_no_redirects", offline)
    monkeypatch.setattr("pring_cycle.source_adapters.build_opener", opener)
    monkeypatch.setattr("pring_cycle.tushare_context.build_opener", lambda *handlers: opener())
    paths = RuntimePaths.discover(root / "runtime")
    initialize_runtime(paths)
    paths.secrets.write_text("TUSHARE_TOKEN=fixture-secret\n", encoding="utf-8")
    models = ModelRepository(paths.database)
    models.register(effective_model_manifest())
    models.activate(CURRENT_MODEL, explicitly_approved=True)
    run = RunRepository(paths.database).submit_manual_full(
        target_business_date=TARGET.isoformat(),
        client_request_id="warrant-symbol-isolation",
        model_version_id=CURRENT_MODEL,
        system_as_of=datetime.now(UTC),
    )
    return paths, run


def refresh(paths: RuntimePaths, run: RunRecord) -> None:
    with own_acquisitions(paths.database, run.run_id, "direct_context_refresh"):
        refresh_context_sources(
            paths, TARGET.isoformat(), definition_version=EFFECTIVE_CATALOG_VERSION
        )


def warrant_outcomes(paths: RuntimePaths) -> dict[str, set[tuple[str, str | None, str | None]]]:
    with sqlite3.connect(paths.database) as connection:
        rows = connection.execute(
            """SELECT parameters_json, state, rejection_reason, ingest_result
               FROM acquisition_request WHERE api_name='fut_wsr'"""
        ).fetchall()
    outcomes: dict[str, set[tuple[str, str | None, str | None]]] = {}
    for parameters, state, reason, ingest in rows:
        symbol = json.loads(parameters)["symbol"]
        outcomes.setdefault(symbol, set()).add((state, reason, ingest))
    return outcomes


@pytest.fixture(scope="module")
def refreshed(
    tmp_path_factory: pytest.TempPathFactory, request: pytest.FixtureRequest
) -> Iterator[RuntimePaths]:
    with pytest.MonkeyPatch.context() as monkeypatch:
        paths, run = prepared(monkeypatch, request, tmp_path_factory.mktemp("warrant-isolation"))
        refresh(paths, run)
        yield paths


def test_a_bad_symbol_leaves_the_other_symbols_held(refreshed: RuntimePaths) -> None:
    points = EvidenceRepository(refreshed.database).metric_series(
        "CN_FUTURES_WARRANTS",
        mode=AsOfMode.SYSTEM,
        as_of=datetime.now(UTC),
        definition_version=EFFECTIVE_CATALOG_VERSION,
    )
    held_days = {
        symbol: {p.period_end for p in points if p.dimensions["symbol"] == symbol}
        for symbol in WARRANT_SYMBOLS
    }

    # Crude refused; TA and CF are CZCE's, unreachable in this run.
    assert held_days["SC"] == held_days["TA"] == held_days["CF"] == set()
    others = {s: days for s, days in held_days.items() if s not in {"SC", "TA", "CF"}}
    # Every weekday from two weeks before the window's first day, here the target itself
    # (no calendar holds a window), for each of the five clean TuShare symbols (ticket 30).
    assert {len(days) for days in others.values()} == {
        sum((TARGET - timedelta(days=n)).weekday() < 5 for n in range(15))
    }


def test_only_the_bad_symbols_receipts_are_refused(refreshed: RuntimePaths) -> None:
    outcomes = warrant_outcomes(refreshed)

    assert outcomes.pop("SC") == {("failed", "tushare_warrant_quantity_negative", None)}
    # TuShare is never asked for TA (PTA) or CF (ADR-0032).
    assert set(outcomes) == {"CU", "PP", "RB", "RU", "SP"}
    assert all(found == {("validated", None, "accepted")} for found in outcomes.values())


def test_a_symbol_missing_on_the_target_day_keeps_the_warrants_listed_as_a_gap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    # Copper fails first; the six symbols fetched after it succeed and hold the target day.
    paths, run = prepared(monkeypatch, request, tmp_path, CopperUnavailable)
    refresh(paths, run)
    definitions = ContextProjectionRules.from_manifest(
        ModelRepository(paths.database).manifest(CURRENT_MODEL)
    ).metric_definitions

    record_run_freshness(paths.database, run.run_id, definitions, utc_now(), TradingCalendar())
    (warrants,) = (
        gap
        for gap in gap_list(paths.database, run.run_id, definitions)
        if gap["metric_id"] == "CN_FUTURES_WARRANTS"
    )

    assert warrants["category"] == "fetch_failed"
    # Each failed symbol keeps its own reason (ticket 20); CZCE's are unreachable here.
    members = {item["symbol"]: item["reason"] for item in warrants["failed_members"]}
    assert members["CU"] == "fixture_warrant_unavailable"
    assert warrants["reason"] == warrants["failed_members"][0]["reason"]


class PassThroughLedger:
    def __init__(self, database: Path, *, scope_run: RunRecord | None = None) -> None:
        pass

    def trace_acquisition(
        self,
        run_id: str,
        channel: str,
        release_event_id: str,
        query: str,
        operation: Callable[[Callable[[str], None]], RetrievalAdapterResponse],
        *,
        defer_completion: bool = False,
    ) -> RetrievalAdapterResponse:
        return operation(lambda acquisition_id: None)

    def complete(self, request_id: str, *, outcome: str, classification: str) -> None:
        pass


def test_a_gap_day_refetch_holds_the_symbols_that_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    paths, run = prepared(monkeypatch, request, tmp_path)
    # What is under test is the refetch's acquisitions, not the retrieval budget ledger.
    monkeypatch.setattr("pring_cycle.targeted_context.RetrievalLedger", PassThroughLedger)
    day = TARGET.isoformat()
    scope_run = replace(
        run,
        retrieval_scope=RetrievalScope(
            f"warrants:{day}", ("CN_FUTURES_WARRANTS",), day, "P2", None
        ),
    )

    with (
        own_acquisitions(paths.database, run.run_id, "gap_retrieval"),
        pytest.raises(ValueError, match="tushare_warrant_quantity_negative"),
    ):
        retrieve_tushare_context(paths, run.run_id, "fixture-secret", scope_run=scope_run)

    outcomes = warrant_outcomes(paths)
    assert outcomes.pop("SC") == {("failed", "tushare_warrant_quantity_negative", None)}
    assert set(outcomes) == {"CU", "PP", "RB", "RU", "SP"}
    assert all(found == {("validated", None, "accepted")} for found in outcomes.values())


class EverySymbolAvailable(WarrantsOnly):
    negative = None


def test_a_gap_day_refetch_asks_only_for_the_symbols_still_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    """Run findings 2026-09-28, ticket 02: with only copper missing, a gap day was refetched
    for all six TuShare symbols, 714 calls where 119 would do."""
    paths, run = prepared(monkeypatch, request, tmp_path, CopperUnavailable)
    refresh(paths, run)
    monkeypatch.setattr(
        "pring_cycle.tushare_context.build_opener", lambda *handlers: EverySymbolAvailable()
    )
    monkeypatch.setattr("pring_cycle.targeted_context.RetrievalLedger", PassThroughLedger)
    day = TARGET.isoformat()
    scope_run = replace(
        run,
        retrieval_scope=RetrievalScope(
            f"warrants:{day}", ("CN_FUTURES_WARRANTS",), day, "P2", None
        ),
    )

    with own_acquisitions(paths.database, run.run_id, "gap_retrieval"):
        retrieve_tushare_context(paths, run.run_id, "fixture-secret", scope_run=scope_run)

    with sqlite3.connect(paths.database) as connection:
        refetched = connection.execute(
            """SELECT r.parameters_json, r.state FROM acquisition_request r
               JOIN full_run_acquisition a USING (acquisition_id)
               WHERE a.phase='gap_retrieval' AND r.api_name='fut_wsr'"""
        ).fetchall()
    assert [(json.loads(p)["symbol"], state) for p, state in refetched] == [("CU", "validated")]


def test_a_gap_day_refetch_clears_the_symbol_the_direct_refresh_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    """Ticket 17: the refetch's success names its symbol, as the refresh's failure did."""
    paths, run = prepared(monkeypatch, request, tmp_path, CopperUnavailable)
    outcomes = AcquisitionOutcomes(paths.database).for_batch(run.run_id)
    with processing_batch(run.run_id):
        refresh(paths, run)
        assert "CU" in {item.symbol for item in outcomes.failures()["CN_FUTURES_WARRANTS"]}
        monkeypatch.setattr(
            "pring_cycle.tushare_context.build_opener", lambda *handlers: EverySymbolAvailable()
        )
        monkeypatch.setattr("pring_cycle.targeted_context.RetrievalLedger", PassThroughLedger)
        day = TARGET.isoformat()
        scope_run = replace(
            run,
            retrieval_scope=RetrievalScope(
                f"warrants:{day}", ("CN_FUTURES_WARRANTS",), day, "P2", None
            ),
        )
        with own_acquisitions(paths.database, run.run_id, "gap_retrieval"):
            retrieve_tushare_context(paths, run.run_id, "fixture-secret", scope_run=scope_run)

    # CZCE's own symbols stay failed, unreachable here; copper no longer is.
    failed = {item.symbol for item in outcomes.failures()["CN_FUTURES_WARRANTS"]}
    assert failed and "CU" not in failed and failed <= {"CF", "TA"}


class CopperRefused(EverySymbolAvailable):
    """TuShare answers copper's request with a business code instead of data."""

    code = 40203
    message = "抱歉，您每分钟最多访问该接口200次"

    def open(self, request: Any, *, timeout: int) -> BytesIO:
        payload = json.loads(request.data)
        if payload["api_name"] == "fut_wsr" and payload["params"]["symbol"] == "CU":
            return BytesIO(json.dumps({"code": self.code, "msg": self.message}).encode())
        return super().open(request, timeout=timeout)


@pytest.mark.parametrize(
    ("code", "message", "classification"),
    [
        (40203, "抱歉，您每分钟最多访问该接口200次", "rate_limited"),
        # The same code for a missing permission waits as a refused permission does.
        (40203, "抱歉，您没有访问该接口的权限", "forbidden_unknown"),
        (2002, "拒绝", "semantic_validation_failed"),
    ],
)
def test_a_gap_day_refetch_backs_off_as_tushare_s_code_says(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
    code: int,
    message: str,
    classification: str,
) -> None:
    """Ticket 22: TuShare's rate limit backs off as one, not as a refused answer."""
    paths, run = prepared(monkeypatch, request, tmp_path, CopperUnavailable)
    refresh(paths, run)
    refused = type("Refused", (CopperRefused,), {"code": code, "message": message})
    monkeypatch.setattr("pring_cycle.tushare_context.build_opener", lambda *handlers: refused())
    day = TARGET.isoformat()
    scope_run = replace(
        run,
        retrieval_scope=RetrievalScope(
            f"warrants:{day}", ("CN_FUTURES_WARRANTS",), day, "P2", None
        ),
    )
    RetrievalLedger(paths.database).bind_run(scope_run, EFFECTIVE_CATALOG_VERSION)

    with own_acquisitions(paths.database, run.run_id, "gap_retrieval"):
        retrieve_tushare_context(paths, run.run_id, "fixture-secret", scope_run=scope_run)

    with sqlite3.connect(paths.database) as connection:
        rows = connection.execute(
            "SELECT classification, cache_expires_at FROM retrieval_physical_request "
            "WHERE run_id=? AND channel='tushare'",
            (run.run_id,),
        ).fetchall()
    (found, expires) = rows[-1]
    assert found == classification
    now = utc_now()
    until = datetime.fromisoformat(expires)
    if classification == "rate_limited":  # an hour, with no Retry-After to say otherwise
        assert now + timedelta(minutes=59) < until <= now + timedelta(hours=1)
    elif classification == "forbidden_unknown":  # the next day, 00:05 in Shanghai
        local = now.astimezone(ZoneInfo("Asia/Shanghai"))
        assert until == local.replace(hour=0, minute=5, second=0, microsecond=0) + timedelta(days=1)
    else:  # a refused answer of a P2 scope waits a day
        assert now + timedelta(hours=23, minutes=59) < until <= now + timedelta(hours=24)


def test_a_gap_day_missing_only_czce_symbols_asks_tushare_for_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    """TA and CF are CZCE's alone (ADR-0032); CZCE is unreachable here, so they stay missing."""
    paths, run = prepared(monkeypatch, request, tmp_path, EverySymbolAvailable)
    refresh(paths, run)
    monkeypatch.setattr("pring_cycle.targeted_context.RetrievalLedger", PassThroughLedger)
    day = TARGET.isoformat()
    scope_run = replace(
        run,
        retrieval_scope=RetrievalScope(
            f"warrants:{day}", ("CN_FUTURES_WARRANTS",), day, "P2", None
        ),
    )

    with own_acquisitions(paths.database, run.run_id, "gap_retrieval"):
        response = retrieve_tushare_context(
            paths, run.run_id, "fixture-secret", scope_run=scope_run
        )

    with sqlite3.connect(paths.database) as connection:
        refetched = connection.execute(
            """SELECT count(*) FROM acquisition_request r
               JOIN full_run_acquisition a USING (acquisition_id)
               WHERE a.phase='gap_retrieval' AND r.api_name='fut_wsr'"""
        ).fetchone()[0]
    assert refetched == 0
    assert response.classification == "incomplete_model_input"


ALL_TUSHARE = ("CU", "PP", "RB", "RU", "SC", "SP")


@pytest.mark.parametrize(
    ("missing", "asked"),
    [
        ((), ()),
        (("symbol_missing:CF", "symbol_missing:TA"), ()),
        (("symbol_missing:CF", "symbol_missing:TA", "warehouse_member_missing:CU"), ("CU",)),
        (("symbol_missing:SC", "warehouse_member_missing:CU"), ("CU", "SC")),
        (("delivery_conflicted:RB",), ("RB",)),
        (("unrecognised",), ALL_TUSHARE),
        (("symbol_missing:SC", "unrecognised"), ALL_TUSHARE),
    ],
)
def test_a_gap_day_refetch_asks_for_every_symbol_its_shortfall_names(
    monkeypatch: pytest.MonkeyPatch, missing: tuple[str, ...], asked: tuple[str, ...]
) -> None:
    """Each kind of shortfall naming a symbol asks for that symbol; one naming none asks for all
    six, even beside shortfalls that do name one."""
    members = tuple(
        f"CN_FUTURES_WARRANTS:{m}" if m != "unrecognised" else "CN_FUTURES_WARRANTS:unknown"
        for m in missing
    )
    monkeypatch.setattr(
        "pring_cycle.targeted_context.select_retrieval_input",
        lambda paths, run: SimpleNamespace(missing_members=members),
    )

    assert _warrant_symbols_to_refetch(Path("unused"), None) == asked  # type: ignore[arg-type]


# Every ``fut_wsr`` request that went out, as ``(symbol, start_date, end_date)``.
ASKED: list[tuple[str, str, str]] = []


def unpublished(
    symbol: str, day: date, *, base: type[WarrantsOnly] = EverySymbolAvailable
) -> type[WarrantsOnly]:
    """An opener whose answers hold no row of ``symbol`` on ``day``, as TuShare's did for the
    days a symbol's warrants went unpublished (audit 2026-10-10, ticket 11)."""

    class Unpublished(base):  # type: ignore[valid-type, misc]
        def open(self, request: Any, *, timeout: int) -> BytesIO:
            payload = json.loads(request.data)
            answer: BytesIO = super().open(request, timeout=timeout)
            if payload["api_name"] != "fut_wsr":
                return answer
            document = json.loads(answer.read())
            document["data"]["items"] = [
                item
                for item in document["data"]["items"]
                if not (item[1] == symbol and item[0] == day.strftime("%Y%m%d"))
            ]
            return BytesIO(json.dumps(document).encode())

    return Unpublished


class Counted(EverySymbolAvailable):
    def open(self, request: Any, *, timeout: int) -> BytesIO:
        payload = json.loads(request.data)
        if payload["api_name"] == "fut_wsr":
            params = payload["params"]
            ASKED.append((params["symbol"], params["start_date"], params["end_date"]))
        return super().open(request, timeout=timeout)


def warrant_day_scope(run: RunRecord) -> RunRecord:
    """The run scoped to the target day's warrants, at a gap's P1 priority."""
    day = TARGET.isoformat()
    return replace(
        run,
        retrieval_scope=RetrievalScope(
            f"warrants:{day}", ("CN_FUTURES_WARRANTS",), day, "P1", None
        ),
    )


def refetched_receipts(paths: RuntimePaths, run: RunRecord) -> list[tuple[str, str, str | None]]:
    with sqlite3.connect(paths.database) as connection:
        rows = connection.execute(
            """SELECT r.parameters_json, r.state, r.rejection_reason FROM acquisition_request r
               JOIN full_run_acquisition a USING (acquisition_id)
               WHERE a.run_id=? AND a.phase='gap_retrieval' AND r.api_name='fut_wsr'""",
            (run.run_id,),
        ).fetchall()
    return [(json.loads(p)["symbol"], state, reason) for p, state, reason in rows]


def test_a_gap_day_the_runs_own_answer_held_empty_is_not_asked_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    """Audit 2026-10-10, ticket 11: the run's own window answer already said TuShare holds no
    paper-oil row that day, so the gap day is not asked for it once more."""
    paths, run = prepared(monkeypatch, request, tmp_path, unpublished("SP", TARGET, base=Counted))
    refresh(paths, run)
    scope_run = warrant_day_scope(run)
    RetrievalLedger(paths.database).bind_run(scope_run, EFFECTIVE_CATALOG_VERSION)
    assert _warrant_symbols_to_refetch(paths, scope_run) == ("SP",)
    ASKED.clear()

    with own_acquisitions(paths.database, run.run_id, "gap_retrieval"):
        response = retrieve_tushare_context(
            paths, run.run_id, "fixture-secret", scope_run=scope_run
        )

    assert ASKED == []
    assert refetched_receipts(paths, run) == []
    with sqlite3.connect(paths.database) as connection:
        physical = connection.execute(
            "SELECT count(*) FROM retrieval_physical_request WHERE run_id=? AND channel='tushare'",
            (run.run_id,),
        ).fetchone()[0]
    assert physical == 0
    # Said as what it is: the source has nothing that day, by the run's own answer.
    assert (response.status, response.classification) == (
        "not_found",
        "warrant_day_empty_in_run_answer",
    )


def test_a_gap_day_held_back_by_its_negative_cache_leaves_no_failed_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    """Audit 2026-10-10, ticket 11: an empty answer holds the same request back for six hours.
    Held back, nothing goes out and no receipt is written, so none fails; the deferral is
    the ledger's, with the time the day may be asked again. Past it, the next run asks again
    and takes what TuShare published late."""
    paths, first = prepared(monkeypatch, request, tmp_path, CopperUnavailable)
    runs = RunRepository(paths.database)

    def run_at(clock: datetime, name: str) -> RunRecord:
        install_runtime_clock(monkeypatch, request, clock)
        return runs.submit_manual_full(
            target_business_date=TARGET.isoformat(),
            client_request_id=name,
            model_version_id=CURRENT_MODEL,
            system_as_of=clock,
        )

    def refetch(run: RunRecord, opener: type[WarrantsOnly]) -> RetrievalAdapterResponse:
        # Copper's window request fails each run: the gap day is the only way to it.
        monkeypatch.setattr(
            "pring_cycle.tushare_context.build_opener", lambda *handlers: CopperUnavailable()
        )
        refresh(paths, run)
        monkeypatch.setattr("pring_cycle.tushare_context.build_opener", lambda *handlers: opener())
        scope_run = warrant_day_scope(run)
        RetrievalLedger(paths.database).bind_run(scope_run, EFFECTIVE_CATALOG_VERSION)
        ASKED.clear()
        with own_acquisitions(paths.database, run.run_id, "gap_retrieval"):
            return retrieve_tushare_context(
                paths, run.run_id, "fixture-secret", scope_run=scope_run
            )

    # The first run asks copper's day and TuShare answers it empty.
    with pytest.raises(ContextObservationsMissingError):
        refetch(first, unpublished("CU", TARGET, base=Counted))
    assert ASKED == [("CU", "20260803", "20260803")]
    assert refetched_receipts(paths, first) == [("CU", "validated", None)]
    runs.cancel(first.run_id)

    # An hour on, the next run's request is held back before anything is written. The first
    # run's empty answer is no answer of this run's, so the day is not skipped (ticket 11 ①).
    held_at = CLOCK + timedelta(hours=1)
    second = run_at(held_at, "warrant-negative-cache-second")
    response = refetch(second, unpublished("CU", TARGET, base=Counted))
    assert ASKED == []
    assert refetched_receipts(paths, second) == []
    assert (response.status, response.classification, response.cache_hit) == (
        "not_attempted",
        "negative_cache_active",
        True,
    )
    with sqlite3.connect(paths.database) as connection:
        deferred = connection.execute(
            "SELECT classification, physical_request_id, next_eligible_at FROM retrieval_query "
            "WHERE run_id=? AND channel='tushare'",
            (second.run_id,),
        ).fetchall()
        failed = connection.execute(
            "SELECT count(*) FROM acquisition_request WHERE rejection_reason=?",
            ("negative_cache_active",),
        ).fetchone()[0]
        attempts = connection.execute(
            "SELECT outcome, safe_metadata_json FROM retrieval_attempt "
            "WHERE metric_id='CN_FUTURES_WARRANTS' ORDER BY rowid"
        ).fetchall()
    assert failed == 0
    ((classification, physical, eligible),) = deferred
    assert (classification, physical) == ("negative_cache_active", None)
    assert held_at < datetime.fromisoformat(eligible) <= CLOCK + timedelta(hours=6, minutes=5)
    # How the day ended for copper: not attempted, held back, no request sent.
    copper_day = [
        (outcome, metadata)
        for outcome, encoded in attempts
        if (metadata := json.loads(encoded)).get("symbol") == "CU"
        and metadata.get("business_date") == TARGET.isoformat()
    ]
    outcome, metadata = copper_day[-1]
    assert (outcome, metadata["condition"], metadata["request_sent"]) == (
        "not_attempted",
        "negative_cache_active",
        "false",
    )
    runs.cancel(second.run_id)

    # Seven hours on, the cache has lapsed: TuShare is asked again and has published since.
    third_at = CLOCK + timedelta(hours=7)
    third = run_at(third_at, "warrant-negative-cache-third")
    # Asked and answered; CZCE's TA and CF stay missing, unreachable here.
    assert refetch(third, Counted).classification == "incomplete_model_input"
    assert ASKED == [("CU", "20260803", "20260803")]
    assert refetched_receipts(paths, third) == [("CU", "validated", None)]
    held = {
        point.period_end
        for point in EvidenceRepository(paths.database).metric_series(
            "CN_FUTURES_WARRANTS",
            mode=AsOfMode.SYSTEM,
            as_of=third_at + timedelta(hours=1),
            definition_version=EFFECTIVE_CATALOG_VERSION,
        )
        if point.dimensions["symbol"] == "CU"
    }
    assert TARGET.isoformat() in held


WARRANT_FIELDS = ["trade_date", "symbol", "warehouse", "vol", "unit", "exchange"]


@pytest.mark.parametrize(
    ("document", "days"),
    [
        (
            {"code": 0, "data": {"fields": WARRANT_FIELDS, "items": []}},
            frozenset(),
        ),
        (
            {
                "code": 0,
                "data": {
                    "fields": WARRANT_FIELDS,
                    "items": [["20260721", "CU", "w", 20, "吨", "SHFE"]],
                },
            },
            frozenset({"20260721"}),
        ),
        # At the response limit the answer may have been cut short: it says nothing.
        (
            {
                "code": 0,
                "data": {
                    "fields": WARRANT_FIELDS,
                    "items": [["20260720", "CU", f"w{n}", 20, "吨", "SHFE"] for n in range(1000)],
                },
            },
            None,
        ),
        ({"code": 40203, "msg": "rate limited"}, None),
        ({"code": 0, "data": {"fields": ["symbol"], "items": []}}, None),
    ],
)
def test_a_warrant_answer_says_which_days_it_holds_only_when_complete(
    document: dict[str, Any], days: frozenset[str] | None
) -> None:
    """Audit 2026-10-10, ticket 11: only a complete answer may stand for an empty day."""
    assert warrant_answer_days(json.dumps(document).encode()) == days
    assert warrant_answer_days(b"not json") is None
