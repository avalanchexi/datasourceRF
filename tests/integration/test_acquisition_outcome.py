"""Acquisition outcomes: what the recorded attempts say, read in one module."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.acquisition import AcquisitionRepository, CandidateSkipped, own_acquisitions
from pring_cycle.acquisition_outcome import AcquisitionOutcomes
from pring_cycle.batches import processing_batch
from pring_cycle.catalog import metric_definition
from pring_cycle.context_projection import build_context_projection
from pring_cycle.evidence import EvidenceRepository
from pring_cycle.freshness import FreshnessAssessment, gap_list, record_batch_freshness
from pring_cycle.models import ModelRepository
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.storage import database_connection

VERSION = "metric-catalog-v0001"
TARGET = "2026-08-28"


@pytest.fixture
def paths(tmp_path: Path) -> RuntimePaths:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    ModelRepository(paths.database).activate("model-v0001", explicitly_approved=True)
    return paths


def record(
    paths: RuntimePaths,
    metric_id: str,
    outcome: str,
    at: datetime,
    *,
    channel: str = "fixture_channel",
    version: str | None = None,
    **metadata: str,
) -> str:
    return EvidenceRepository(paths.database).record_retrieval_attempt(
        metric_id=metric_id,
        channel=channel,
        outcome=outcome,
        fetched_at=at,
        safe_metadata={
            **metadata,
            **({"definition_version": version} if version is not None else {}),
        },
    )


def submit(paths: RuntimePaths, request_id: str) -> tuple[str, datetime]:
    # Any batch will do: one that is not a full run is never merged with another.
    run = RunRepository(paths.database).submit(
        command_type="report_generation",
        target_business_date=TARGET,
        client_request_id=request_id,
        model_version_id="model-v0001",
        system_as_of=datetime.now(UTC),
    )
    with database_connection(paths.database) as connection:
        accepted = connection.execute(
            "SELECT accepted_at FROM parent_run WHERE run_id=?", (run.run_id,)
        ).fetchone()[0]
    return run.run_id, datetime.fromisoformat(accepted)


def test_an_attempt_is_not_visible_a_microsecond_before_it_was_recorded(
    paths: RuntimePaths,
) -> None:
    # Moved from test_full_run_retrieval.
    recorded = datetime(2026, 8, 28, 10, 0, 0, 100, tzinfo=UTC)
    record(paths, "EIA_BRENT_RBRTE", "source_failed", recorded, period=TARGET)
    outcomes = AcquisitionOutcomes(paths.database)

    assert (
        outcomes.latest(
            "EIA_BRENT_RBRTE", as_of=recorded - timedelta(microseconds=1), period=TARGET
        )
        is None
    )
    seen = outcomes.latest("EIA_BRENT_RBRTE", as_of=recorded, period=TARGET)
    assert seen is not None and seen.recorded_at == recorded


def test_latest_keeps_to_the_target_day_and_catalog_asked_for(paths: RuntimePaths) -> None:
    at = datetime(2026, 8, 28, 10, tzinfo=UTC)
    older = record(
        paths,
        "VIX",
        "verified_candidate",
        at,
        target_business_date=TARGET,
        definition_version=VERSION,
    )
    record(
        paths,
        "VIX",
        "source_failed",
        at + timedelta(minutes=1),
        target_business_date="2026-08-27",
        definition_version=VERSION,
    )
    record(
        paths,
        "VIX",
        "source_failed",
        at + timedelta(minutes=2),
        target_business_date=TARGET,
        definition_version="another-catalog",
    )
    outcomes = AcquisitionOutcomes(paths.database)
    later = at + timedelta(hours=1)

    chosen = outcomes.latest(
        "VIX", as_of=later, target_business_date=TARGET, definition_version=VERSION
    )
    assert chosen is not None and chosen.attempt_id == older
    newest = outcomes.latest("VIX", as_of=later)
    assert newest is not None and newest.definition_version == "another-catalog"


def test_the_attempt_names_the_receipts_it_recorded(paths: RuntimePaths) -> None:
    # What the ECB refresh compares, within its catalog, to decide whether the failure it
    # caught was already recorded against the same receipts.
    metric, at = "CN_USDCNY_ECB_REFERENCE_CROSS", datetime(2026, 8, 28, 10, tzinfo=UTC)
    record(paths, metric, "source_failed", at, acquisition_ids="a,b", definition_version=VERSION)
    record(paths, metric, "source_failed", at + timedelta(seconds=1), definition_version="other")
    outcomes = AcquisitionOutcomes(paths.database)
    later = at + timedelta(minutes=1)

    same_catalog = outcomes.latest(metric, as_of=later, definition_version=VERSION)
    assert same_catalog is not None and same_catalog.acquisition_ids == ("a", "b")
    other = outcomes.latest(metric, as_of=later, definition_version="other")
    assert other is not None and other.acquisition_ids == ()


def test_a_batch_owns_the_attempts_between_its_acceptance_and_the_next(
    paths: RuntimePaths,
) -> None:
    first, first_accepted = submit(paths, "first")
    # Recorded before the next batch is accepted, a moment later.
    record(paths, "CN_DR007", "source_failed", first_accepted + timedelta(microseconds=1))
    second, second_accepted = submit(paths, "second")
    record(paths, "CN_SHIBOR_ON_1W_3M", "source_failed", second_accepted + timedelta(seconds=1))
    outcomes = AcquisitionOutcomes(paths.database)

    assert set(outcomes.for_batch(first).failures()) == {"CN_DR007"}
    assert set(outcomes.for_batch(second).failures()) == {"CN_SHIBOR_ON_1W_3M"}


def test_an_attempt_recorded_in_a_batch_is_that_batch_s_without_a_receipt(
    paths: RuntimePaths,
) -> None:
    # Ticket 17: a missing credential sends no request, so no receipt names the run.
    first, _ = submit(paths, "first")
    second, second_accepted = submit(paths, "second")
    with processing_batch(first):
        record(
            paths,
            "CN_GDP",
            "missing_credentials",
            second_accepted + timedelta(seconds=1),
            condition="TUSHARE_TOKEN_not_configured",
            request_sent="false",
        )
    outcomes = AcquisitionOutcomes(paths.database)

    ((attempt,),) = outcomes.for_batch(first).failures().values()
    assert (attempt.metric_id, attempt.metadata["run_id"]) == ("CN_GDP", first)
    assert attempt.target_business_date == TARGET and attempt.acquisition_ids == ()
    assert outcomes.for_batch(second).failures() == {}


def test_a_resumed_run_keeps_its_own_attempts_and_no_later_run_s(paths: RuntimePaths) -> None:
    """Ticket 19: a run resumed after another for the same day sees only what it recorded."""
    first, _ = submit(paths, "first")
    second, second_accepted = submit(paths, "second")
    at = second_accepted + timedelta(seconds=1)
    with processing_batch(second):
        record(paths, "CN_DR007", "source_failed", at)
    with processing_batch(first):  # resumed: recorded long after the next run's acceptance
        record(paths, "CN_SHIBOR_ON_1W_3M", "source_failed", at + timedelta(hours=1))
    outcomes = AcquisitionOutcomes(paths.database)

    assert set(outcomes.for_batch(first).failures()) == {"CN_SHIBOR_ON_1W_3M"}
    assert set(outcomes.for_batch(second).failures()) == {"CN_DR007"}
    # The target day's view crosses batches: the day's latest, whichever run recorded it.
    latest = outcomes.latest("CN_DR007", as_of=at + timedelta(hours=2), target_business_date=TARGET)
    assert latest is not None and latest.metadata["run_id"] == second


def test_attempts_of_one_instant_follow_the_order_they_were_written(paths: RuntimePaths) -> None:
    """Ticket 19: both views order by the exact time, then by writing order."""
    run, accepted = submit(paths, "ties")
    at = accepted + timedelta(seconds=1)
    with processing_batch(run):
        # A success written in another offset, then a failure of the same instant after it:
        # as text the success would sort last.
        record(
            paths,
            "CN_DR007",
            "succeeded",
            at.astimezone(timezone(timedelta(hours=8))),
            version=VERSION,
        )
        record(paths, "CN_DR007", "source_failed", at, version=VERSION)
    outcomes = AcquisitionOutcomes(paths.database)

    assert set(outcomes.for_batch(run).failures()) == {"CN_DR007"}
    latest = outcomes.latest("CN_DR007", as_of=at)
    assert latest is not None and latest.outcome == "source_failed"


def test_both_views_keep_to_the_catalog(paths: RuntimePaths) -> None:
    """Ticket 19: an attempt for another catalog is no part of this batch, nor of a day's
    view asked for this catalog."""
    run, accepted = submit(paths, "catalog")
    at = accepted + timedelta(seconds=1)
    with processing_batch(run):
        record(paths, "CN_DR007", "source_failed", at, version="metric-catalog-v0099")
        record(paths, "CN_SHIBOR_ON_1W_3M", "source_failed", at, version=VERSION)
    outcomes = AcquisitionOutcomes(paths.database)

    assert set(outcomes.for_batch(run).failures()) == {"CN_SHIBOR_ON_1W_3M"}
    assert outcomes.latest("CN_DR007", as_of=at, definition_version=VERSION) is None


def test_a_later_success_clears_a_failure_of_the_same_symbol_only(paths: RuntimePaths) -> None:
    run, accepted = submit(paths, "warrants")
    at = accepted + timedelta(seconds=1)
    record(paths, "CN_DR007", "source_failed", at)
    record(paths, "CN_DR007", "verified_candidate", at + timedelta(seconds=1))
    record(paths, "CN_FUTURES_WARRANTS", "validation_failed", at, symbol="CU", reason="unit")
    record(paths, "CN_FUTURES_WARRANTS", "source_failed", at, symbol="AU")
    record(
        paths, "CN_FUTURES_WARRANTS", "verified_candidate", at + timedelta(seconds=1), symbol="AU"
    )
    record(
        paths, "CN_FUTURES_WARRANTS", "verified_candidate", at + timedelta(seconds=1), symbol="AL"
    )

    failures = AcquisitionOutcomes(paths.database).for_batch(run).failures()

    assert set(failures) == {"CN_FUTURES_WARRANTS"}
    ((cu),) = failures["CN_FUTURES_WARRANTS"]
    assert (cu.symbol, cu.outcome, cu.detail) == ("CU", "validation_failed", "unit")


def test_a_symbol_s_failure_one_day_stands_though_another_day_succeeded(
    paths: RuntimePaths,
) -> None:
    """Ticket 20 (ADR-0032): only that symbol that day is missing."""
    run, accepted = submit(paths, "warrant-days")
    at = accepted + timedelta(seconds=1)
    record(
        paths, "CN_FUTURES_WARRANTS", "source_failed", at, symbol="TA", business_date="2026-05-19"
    )
    record(
        paths,
        "CN_FUTURES_WARRANTS",
        "succeeded",
        at + timedelta(seconds=1),
        symbol="TA",
        business_date="2026-09-02",
    )

    ((ta),) = AcquisitionOutcomes(paths.database).for_batch(run).failures()["CN_FUTURES_WARRANTS"]

    assert (ta.symbol, ta.business_date) == ("TA", "2026-05-19")


def test_a_window_s_failure_is_cleared_by_a_later_day_s_success_of_its_symbol(
    paths: RuntimePaths,
) -> None:
    """Ticket 20: a failure naming no day (the window's request) gives way to a gap day's
    refetch; one naming its day stands against another day's success."""
    run, accepted = submit(paths, "warrant-window")
    at = accepted + timedelta(seconds=1)
    record(paths, "CN_FUTURES_WARRANTS", "source_failed", at, symbol="CU")
    record(
        paths, "CN_FUTURES_WARRANTS", "source_failed", at, symbol="RB", business_date="2026-08-27"
    )
    later = at + timedelta(seconds=1)
    for symbol in ("CU", "RB"):
        record(
            paths,
            "CN_FUTURES_WARRANTS",
            "succeeded",
            later,
            symbol=symbol,
            business_date="2026-08-28",
        )

    failed = AcquisitionOutcomes(paths.database).for_batch(run).failures()["CN_FUTURES_WARRANTS"]

    assert [(item.symbol, item.business_date) for item in failed] == [("RB", "2026-08-27")]


def test_the_gap_list_names_each_failed_symbol_with_its_reason(paths: RuntimePaths) -> None:
    """Ticket 20: one row for the metric, every failed symbol and why, page and report alike."""
    from pring_cycle.dashboard import _gap_list

    run, accepted = submit(paths, "warrant-symbols")
    at = accepted + timedelta(seconds=1)
    record(paths, "CN_FUTURES_WARRANTS", "source_failed", at, symbol="CU", reason="timeout")
    record(
        paths, "CN_FUTURES_WARRANTS", "structure_rejected", at, symbol="SC", rule_reason="negative"
    )
    with database_connection(paths.database) as connection:
        record_batch_freshness(connection, run, (assess("CN_FUTURES_WARRANTS", "missing"),), at)
    definition = metric_definition(
        "CN_FUTURES_WARRANTS", definition_version=VERSION, database_path=paths.database
    )

    (gap,) = gap_list(paths.database, run, (definition,))

    assert (gap["category"], gap["reason"]) == ("fetch_failed", "timeout")
    assert gap["failed_members"] == [
        {"symbol": "CU", "reason": "timeout"},
        {"symbol": "SC", "reason": "negative"},
    ]
    assert "失败品种 CU（timeout）；SC（negative）" in str(_gap_list([gap]))


def capture(paths: RuntimePaths, run: str, error: Exception) -> None:
    def refuse(raw: bytes) -> Any:
        raise error

    with (
        own_acquisitions(paths.database, run, "gap_retrieval", metric_ids=("CN_DR007",)),
        pytest.raises(type(error)),
    ):
        AcquisitionRepository(paths.database, paths.artifacts).capture(
            provider="tushare",
            api_name="repo_daily",
            parameters={"trade_date": "20260828"},
            fields="ts_code",
            parser_version="fixture-parser",
            fetch=lambda: b"{}",
            parse=refuse,
            normalize=lambda value: value,
        )


def test_a_detail_recorded_as_null_gives_way_to_the_next(paths: RuntimePaths) -> None:
    run, accepted = submit(paths, "null-detail")
    at = accepted + timedelta(microseconds=1)
    EvidenceRepository(paths.database).record_retrieval_attempt(
        metric_id="CN_DR007",
        channel="fixture_channel",
        outcome="source_failed",
        fetched_at=at,
        safe_metadata={"reason": None, "condition": "timeout"},  # type: ignore[dict-item]
    )

    failures = AcquisitionOutcomes(paths.database).for_batch(run).failures()

    assert failures["CN_DR007"][0].detail == "timeout"


def test_a_skipped_candidate_is_not_a_structure_rejection(paths: RuntimePaths) -> None:
    run, _accepted = submit(paths, "rejections")
    capture(paths, run, ValueError("fields_missing"))
    capture(paths, run, CandidateSkipped("another_candidate_chosen"))

    rejections = AcquisitionOutcomes(paths.database).for_batch(run).structure_rejections()

    assert [(item.metric_ids, item.api_name, item.reason) for item in rejections] == [
        (("CN_DR007",), "repo_daily", "fields_missing")
    ]


def assess(metric_id: str, status: str) -> FreshnessAssessment:
    return FreshnessAssessment(
        metric_id=metric_id,
        source=None,
        frequency="daily",
        status=status,
        held_period=None,
        released_period=TARGET,
        due_period=TARGET,
        periods_behind=None,
        public_available_at=None,
        basis=None,
    )


def test_the_gap_list_names_why_a_registered_source_failed(paths: RuntimePaths) -> None:
    # Moved from test_gap_source_repairs: the reasons, read without a full run.
    run, accepted = submit(paths, "gaps")
    at = accepted + timedelta(seconds=1)
    record(paths, "CN_DR007", "source_failed", at, error_type="OSError")
    record(
        paths,
        "CN_INDEX_VALUATION",
        "validation_failed",
        at,
        reason="tushare_response_period_mismatch",
    )
    with database_connection(paths.database) as connection:
        record_batch_freshness(
            connection,
            run,
            (assess("CN_DR007", "missing"), assess("CN_INDEX_VALUATION", "missing")),
            at,
        )
    definitions = tuple(
        metric_definition(metric_id, definition_version=VERSION, database_path=paths.database)
        for metric_id in ("CN_DR007", "CN_INDEX_VALUATION")
    )

    gaps = {str(gap["metric_id"]): gap for gap in gap_list(paths.database, run, definitions)}

    assert (gaps["CN_DR007"]["category"], gaps["CN_DR007"]["reason"]) == (
        "fetch_failed",
        "OSError",
    )
    assert (gaps["CN_INDEX_VALUATION"]["category"], gaps["CN_INDEX_VALUATION"]["reason"]) == (
        "ingest_rejected",
        "tushare_response_period_mismatch",
    )
    # No web page carries either: a property of the gap, not why it is missing.
    assert gaps["CN_DR007"]["no_web_fallback"] is True
    assert gaps["CN_INDEX_VALUATION"]["no_web_fallback"] is True
    assert "no_searchable_source" not in {gap["category"] for gap in gaps.values()}


def test_the_gap_list_reads_how_an_acquisition_ended_in_the_new_words(
    paths: RuntimePaths,
) -> None:
    """Ticket 18: each result maps to its gap; a partial or empty delivery is no failure."""
    run, accepted = submit(paths, "classified")
    at = accepted + timedelta(seconds=1)
    record(paths, "CN_DR007", "local_failed", at, step="local", error_type="TypeError")
    record(paths, "CN_SHIBOR_ON_1W_3M", "structure_rejected", at, rule_reason="bad_date")
    record(paths, "CN_INDEX_VALUATION", "source_failed", at, external_code="40203")
    # A later partial delivery of the same metric clears its earlier failure.
    record(
        paths,
        "CN_INDEX_VALUATION",
        "succeeded",
        at + timedelta(seconds=1),
        completeness="partial_members_missing",
    )
    metrics = ("CN_DR007", "CN_SHIBOR_ON_1W_3M", "CN_INDEX_VALUATION")
    with database_connection(paths.database) as connection:
        record_batch_freshness(
            connection, run, tuple(assess(metric, "missing") for metric in metrics), at
        )
    definitions = tuple(
        metric_definition(metric_id, definition_version=VERSION, database_path=paths.database)
        for metric_id in metrics
    )

    gaps = {str(gap["metric_id"]): gap for gap in gap_list(paths.database, run, definitions)}

    assert (gaps["CN_DR007"]["category"], gaps["CN_DR007"]["reason"]) == (
        "fetch_failed",
        "TypeError",
    )
    assert (gaps["CN_SHIBOR_ON_1W_3M"]["category"], gaps["CN_SHIBOR_ON_1W_3M"]["reason"]) == (
        "ingest_rejected",
        "bad_date",
    )
    assert gaps["CN_INDEX_VALUATION"]["category"] == "missing"


def test_a_p2_row_shows_the_target_day_s_latest_acquisition(paths: RuntimePaths) -> None:
    # Moved from test_full_run_retrieval: the page channel has the last word, and a derived
    # spread shows its inputs' acquisitions instead of its own.
    at = datetime(2026, 8, 28, 10, tzinfo=UTC)
    common = {"target_business_date": TARGET, "definition_version": VERSION}
    record(
        paths,
        "EIA_BRENT_RBRTE",
        "missing_credentials",
        at,
        channel="eia_official_candidate",
        request_sent="false",
        **common,
    )
    record(
        paths,
        "EIA_BRENT_RBRTE",
        "source_failed",
        at + timedelta(seconds=1),
        channel="eia_html_candidate",
        **common,
    )
    record(paths, "UST2Y_NOMINAL_YIELD", "missing_fields", at, **common)
    record(paths, "UST10Y_NOMINAL_YIELD", "verified_candidate", at, **common)

    context = build_context_projection(
        EvidenceRepository(paths.database),
        as_of=at + timedelta(hours=1),
        model_manifest=ModelRepository(paths.database).manifest("model-v0001"),
        target_business_date=TARGET,
    )
    rows = {row["metric_id"]: row for row in context.macro["international_context"]}

    brent = rows["EIA_BRENT_RBRTE"]
    assert brent["acquisition_status"] == "source_failed"
    assert brent["latest_acquisition"]["channel"] == "eia_html_candidate"
    assert brent["latest_acquisition"]["definition_version"] == VERSION
    assert brent["latest_acquisition"]["request_sent"] is None
    assert rows["UST2Y_NOMINAL_YIELD"]["acquisition_status"] == "missing_fields"
    spread = rows["UST_2S10S_SPREAD"]
    assert spread["acquisition_status"] == "derived_from_inputs"
    assert spread["latest_acquisition"] is None
    assert {
        item["metric_id"]: item["acquisition_status"] for item in spread["input_acquisition"]
    } == {"UST2Y_NOMINAL_YIELD": "missing_fields", "UST10Y_NOMINAL_YIELD": "verified_candidate"}
