"""Ticket 23: only 120 sessions of details, summaries and batches outlive a successful run."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.acquisition import AcquisitionRepository
from pring_cycle.cli import main
from pring_cycle.evidence import (
    AsOfMode,
    EvidenceRepository,
    EvidenceValueState,
    SourceClaimInput,
)
from pring_cycle.models import ModelRepository
from pring_cycle.projections import ProjectionSetRepository
from pring_cycle.retention import QUOTA_COUNTED, prune_to_window
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.source_adapters import CORE_API_IDENTITIES
from pring_cycle.worker import process_pending_run
from tests.conftest import install_runtime_clock
from tests.integration.test_core_history_refresh import historical_response
from tests.integration.test_trading_calendar import sse_adapter

OLD, TARGET = "2026-01-05", "2026-08-03"


def query(paths: RuntimePaths, sql: str, *args: object) -> list[tuple[Any, ...]]:
    connection = sqlite3.connect(paths.database)
    try:
        return connection.execute(sql, args).fetchall()
    finally:
        connection.close()


class Runner:
    def __init__(self, paths: RuntimePaths, monkeypatch: pytest.MonkeyPatch) -> None:
        self.paths = paths
        self.calendar_unavailable = False

        runner = self

        class FixtureOpener:
            def open(self, request: Any, *, timeout: int) -> BytesIO:
                payload = json.loads(request.data)
                if payload["api_name"] == "trade_cal" and runner.calendar_unavailable:
                    raise OSError("fixture calendar unavailable")
                code = payload["params"].get("ts_code")
                if payload["api_name"] != "trade_cal" and code not in {
                    "000985.CSI",
                    "000012.SH",
                    "NHII.NH",
                }:
                    raise OSError("fixture_context_unavailable")
                return BytesIO(historical_response(payload))

        monkeypatch.setattr("pring_cycle.source_adapters.build_opener", FixtureOpener)
        monkeypatch.setattr(
            "pring_cycle.tushare_context.build_opener", lambda *handlers: FixtureOpener()
        )
        monkeypatch.setattr(
            "pring_cycle.eia_html.open_no_redirects",
            lambda *args, **kwargs: (_ for _ in ()).throw(OSError("offline")),
        )

    def run(self, target: str, request_id: str) -> str:
        run = RunRepository(self.paths.database).submit_manual_full(
            target_business_date=target,
            client_request_id=request_id,
            model_version_id="model-v0001",
            system_as_of=datetime.now(UTC),
        )
        process_pending_run(self.paths, report_adapters=())
        return run.run_id


@pytest.fixture(scope="module")
def pruned(tmp_path_factory: pytest.TempPathFactory) -> Iterator[dict[str, Any]]:
    with pytest.MonkeyPatch.context() as monkeypatch:
        paths = RuntimePaths.discover(tmp_path_factory.mktemp("retention") / "runtime")
        initialize_runtime(paths)
        paths.secrets.write_text("TUSHARE_TOKEN=fixture-secret\n", encoding="utf-8")
        ModelRepository(paths.database).activate("model-v0001", explicitly_approved=True)
        runner = Runner(paths, monkeypatch)
        old = runner.run(OLD, "old-day")
        old_raw = {row[0] for row in query(paths, "SELECT raw_hash FROM acquisition_request")}
        stored = RunRepository(paths.database).get(old)
        assert stored.status == "completed", stored.error_classification
        from pring_cycle.reports import (
            ReportRepository,
            ReportService,
            report_input_from_projection,
        )

        old_input = report_input_from_projection(ProjectionSetRepository(paths.database).current())
        repository = ReportRepository(paths.database)
        # An audit artifact is retained while its input bundle remains, even if rejected.
        output_hash = repository.save_output(old_input, {"rejected": "fixture"})
        assert (paths.artifacts / output_hash[:2] / output_hash).exists()
        ReportService(repository, ()).generate(
            old_input, client_request_id="retention-output-owner"
        )
        repository.record_attempt(
            "report-cancelled-without-snapshot",
            adapter="codex_cli",
            adapter_version="fixture",
            outcome="cancelled",
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            tool_events=0,
            output_hash=output_hash,
            process_audit={"bundle_id": old_input.bundle_id},
        )
        latest = runner.run(TARGET, "target-day")
        states = ProjectionSetRepository(paths.database).current().datasets["core_assets"]
        yield {
            "paths": paths,
            "runner": runner,
            "old": old,
            "latest": latest,
            "old_raw": old_raw,
            "old_output": output_hash,
            "states": [(a["asset"], a["state"]) for a in states["assets"]],
        }


def window_start(paths: RuntimePaths, run_id: str) -> str:
    [(document,)] = query(
        paths,
        "SELECT document_json FROM full_run_gap_plan WHERE run_id=? AND phase='final'",
        run_id,
    )
    return str(json.loads(document)["daily_window"]["dates"][0])


def test_details_summaries_and_batches_before_the_window_are_deleted(
    pruned: dict[str, Any],
) -> None:
    paths = pruned["paths"]
    start = window_start(paths, pruned["latest"])
    assert (
        query(
            paths,
            "SELECT acquisition_id FROM acquisition_dispatch WHERE acquisition_id "
            "NOT IN (SELECT acquisition_id FROM acquisition_request)",
        )
        == []
    )

    assert query(paths, "SELECT count(*) FROM source_claim WHERE period_end < ?", start) == [(0,)]
    assert query(paths, "SELECT count(*) FROM source_claim WHERE period_end >= ?", start)[0][0] > 0
    assert query(paths, "SELECT run_id FROM parent_run") == [(pruned["latest"],)]
    assert query(
        paths, "SELECT count(*) FROM report_snapshot WHERE target_business_date=?", OLD
    ) == [(0,)]
    assert query(
        paths,
        "SELECT count(*) FROM projection_set "
        "WHERE json_extract(envelope_json, '$.target_business_date') < ?",
        start,
    ) == [(0,)]
    assert ProjectionSetRepository(paths.database).current().envelope.target_business_date == TARGET


def test_unreferenced_originals_are_removed_from_disk(pruned: dict[str, Any]) -> None:
    paths = pruned["paths"]
    # Once the day's TuShare quota no longer counts them (ticket 31).
    prune_to_window(paths, now=datetime.now(UTC) + QUOTA_COUNTED + timedelta(days=1))
    kept = {row[0] for row in query(paths, "SELECT raw_hash FROM acquisition_request")}

    gone = pruned["old_raw"] - kept
    assert gone
    assert all(not (paths.artifacts / h[:2] / h).exists() for h in gone if h)
    assert all((paths.artifacts / h[:2] / h).exists() for h in kept if h)


def test_lookback_is_not_kept_but_the_batch_keeps_its_calls(pruned: dict[str, Any]) -> None:
    paths = pruned["paths"]
    start = window_start(paths, pruned["latest"])
    calls = query(
        paths,
        """
        SELECT r.api_name, r.parameters_json, r.raw_hash FROM full_run_acquisition a
        JOIN acquisition_request r USING (acquisition_id) WHERE a.run_id=?
        """,
        pruned["latest"],
    )

    # The core series was fetched with lookback before the window, and only its call remains.
    core = [
        c
        for c in calls
        if json.loads(c[1]).get("ts_code") in {"000985.CSI", "000012.SH", "NHII.NH"}
    ]
    assert core and all(json.loads(c[1])["start_date"] < start.replace("-", "") for c in core)
    assert all(c[2] for c in core)


def test_rerunning_with_transient_lookback_computes_the_same_states(
    pruned: dict[str, Any],
) -> None:
    paths = pruned["paths"]

    pruned["runner"].run(TARGET, "target-day-again")

    current = ProjectionSetRepository(paths.database).current().datasets["core_assets"]
    assert [(a["asset"], a["state"]) for a in current["assets"]] == pruned["states"]


def test_core_prices_a_projection_cites_do_not_pile_up_run_after_run(
    pruned: dict[str, Any],
) -> None:
    """Lookback 08: the cores' trend reads every price held, so prices a projection cites
    are not kept for it; otherwise each run would read, cite and keep them again."""
    paths = pruned["paths"]
    cores = sorted(CORE_API_IDENTITIES)
    assert len(pruned["states"]) == 3 and all(state is not None for _, state in pruned["states"])

    for request_id in ("target-day-third", "target-day-fourth"):
        run = pruned["runner"].run(TARGET, request_id)

        assert RunRepository(paths.database).get(run).status == "completed"
        start = window_start(paths, run)
        assert query(
            paths,
            "SELECT count(*) FROM source_claim WHERE period_end < ? "
            "AND metric_id IN (SELECT value FROM json_each(?))",
            start,
            json.dumps(cores),
        ) == [(0,)]
        # Lookback 10: each run reads the preheat it fetched, however many ran that day.
        current = ProjectionSetRepository(paths.database).current().datasets["core_assets"]
        assert [(a["asset"], a["state"]) for a in current["assets"]] == pruned["states"]
    # The known cost: the trend's preheat before the window, though cited, is gone.
    current = ProjectionSetRepository(paths.database).current().datasets["core_assets"]
    claims = {row[0] for row in query(paths, "SELECT claim_id FROM source_claim")}
    assert set(current["model_input_observation_version_ids"]) - claims


def test_a_failed_run_deletes_nothing_and_the_command_does(
    pruned: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    paths = pruned["paths"]
    old = date(2025, 1, 2)
    EvidenceRepository(paths.database).append_source_claim(
        SourceClaimInput(
            metric_id="CN_DR007",
            definition_version="metric-catalog-v0001",
            period_kind="business_day",
            period_start=old.isoformat(),
            period_end=old.isoformat(),
            dimensions={},
            value=1.5,
            value_state=EvidenceValueState.REPORTED_VALUE,
            unit="scalar",
            provider="fixture",
            source_reference="fixture:old",
            release_event_id="fixture:old",
            release_at=None,
            public_available_at=None,
            fetched_at=datetime.now(UTC),
            available_at=datetime.now(UTC),
            quality_status="validated",
        )
    )
    pruned["runner"].calendar_unavailable = True
    # A Saturday: the calendar the earlier runs fetched on to their cutoffs has it closed,
    # and none other can be fetched, so the run has no window to judge by.
    failed = pruned["runner"].run("2026-08-08", "failing-day")

    assert RunRepository(paths.database).get(failed).status != "completed"
    assert query(paths, "SELECT count(*) FROM source_claim WHERE period_end=?", str(old)) == [(1,)]

    main(["retention-prune", "--runtime-root", str(paths.override_root), "--json"])

    assert json.loads(capsys.readouterr().out)["window_end"] == TARGET
    assert query(paths, "SELECT count(*) FROM source_claim WHERE period_end=?", str(old)) == [(0,)]


def test_matched_quotes_go_with_their_claims(
    pruned: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    """Phase two #07: a value's matched quote is kept exactly as long as the value."""
    paths = pruned["paths"]
    start = window_start(paths, pruned["latest"])
    [old_claim] = EvidenceRepository(paths.database).append_source_claims(
        (
            SourceClaimInput(
                metric_id="CN_DR007",
                definition_version="metric-catalog-v0001",
                period_kind="business_day",
                period_start=OLD,
                period_end=OLD,
                dimensions={},
                value=1.6,
                value_state=EvidenceValueState.REPORTED_VALUE,
                unit="scalar",
                provider="财联社",
                source_reference="media_page:https://www.cls.cn/detail/1",
                release_event_id="media_page:old",
                release_at=None,
                public_available_at=None,
                fetched_at=datetime.now(UTC),
                available_at=datetime.now(UTC),
                quality_status="validated",
            ),
        )
    )
    [(kept_claim,)] = query(
        paths, "SELECT claim_id FROM source_claim WHERE period_end >= ? LIMIT 1", start
    )
    connection = sqlite3.connect(paths.database)
    try:
        with connection:
            for claim_id in (old_claim.claim_id, kept_claim):
                connection.execute(
                    "INSERT INTO claim_matched_quote (claim_id, route, quote, title, "
                    "source_name, published_at, body_hash, url, rules_version) "
                    "VALUES (?, 'media_page', '原话', '标题', '财联社', NULL, ?, NULL, "
                    "'news-rules-v0001')",
                    (claim_id, "0" * 64),
                )
    finally:
        connection.close()

    main(["retention-prune", "--runtime-root", str(paths.override_root), "--json"])
    capsys.readouterr()

    assert query(paths, "SELECT claim_id FROM claim_matched_quote") == [(kept_claim,)]


def test_the_latest_event_before_the_window_stays_as_the_current_baseline(
    pruned: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    """Event #05 (ADR-0028): the RRR cut in force is kept however old; the one before goes."""
    paths = pruned["paths"]

    def rrr_cut(day: str, change: float) -> str:
        [claim] = EvidenceRepository(paths.database).append_source_claims(
            (
                SourceClaimInput(
                    metric_id="CN_RRR_EVENT",
                    definition_version="metric-catalog-v0001",
                    period_kind="event",
                    period_start=day,
                    period_end=day,
                    dimensions={
                        "scope": "excluding_5_percent_institutions",
                        "measure": "rrr_change",
                    },
                    value=change,
                    value_state=EvidenceValueState.REPORTED_VALUE,
                    unit="percentage_points",
                    provider="tushare_news",
                    source_reference=f"tushare_news:{day}",
                    release_event_id=f"tushare_news:rrr:{day}",
                    release_at=None,
                    public_available_at=None,
                    fetched_at=datetime.now(UTC),
                    available_at=datetime.now(UTC),
                    quality_status="validated",
                ),
            )
        )
        return claim.claim_id

    earlier, latest = rrr_cut("2024-09-27", -0.5), rrr_cut("2025-05-15", -0.5)
    connection = sqlite3.connect(paths.database)
    try:
        with connection:
            connection.execute(
                "INSERT INTO claim_matched_quote (claim_id, route, quote, title, "
                "source_name, published_at, body_hash, url, rules_version) "
                "VALUES (?, 'tushare_news', '原话', '标题', '新华网', NULL, ?, NULL, "
                "'news-rules-v0001')",
                (latest, "0" * 64),
            )
    finally:
        connection.close()

    main(["retention-prune", "--runtime-root", str(paths.override_root), "--json"])
    capsys.readouterr()

    kept = {row[0] for row in query(paths, "SELECT claim_id FROM source_claim")}
    assert latest in kept
    assert earlier not in kept
    assert (latest,) in query(paths, "SELECT claim_id FROM claim_matched_quote")


def test_a_derived_value_in_the_window_keeps_the_claims_it_was_computed_from(
    pruned: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    """Ticket 29: a kept derived value's parents stay with their originals, however old."""
    paths = pruned["paths"]
    evidence = EvidenceRepository(paths.database)
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)

    def old_claim(name: str, value: float) -> tuple[str, str, str]:
        receipt = acquisitions.capture(
            provider="fixture",
            api_name=f"lookback_{name}",
            parameters={"month": "202512"},
            fields="value",
            parser_version="fixture-parser",
            fetch=lambda: f"lookback {name}".encode(),
            parse=lambda raw: raw,
            normalize=lambda raw: raw.decode(),
        ).receipt
        assert receipt.received_at and receipt.validated_at
        [claim] = evidence.append_source_claims(
            (
                SourceClaimInput(
                    metric_id="CN_DR007",
                    definition_version="metric-catalog-v0001",
                    period_kind="business_day",
                    period_start=OLD,
                    period_end=OLD,
                    dimensions={},
                    value=value,
                    value_state=EvidenceValueState.REPORTED_VALUE,
                    unit="scalar",
                    provider="fixture",
                    source_reference=f"fixture:lookback:{name}",
                    release_event_id=f"fixture:lookback:{name}",
                    release_at=None,
                    public_available_at=None,
                    fetched_at=receipt.received_at,
                    available_at=receipt.validated_at,
                    quality_status="validated",
                    acquisition_id=receipt.acquisition_id,
                ),
            )
        )
        return claim.claim_id, receipt.acquisition_id, str(receipt.raw_hash)

    def derived(inputs: tuple[str, ...], cutoff: datetime) -> str:
        return evidence.append_derived_observation(
            metric_id="CN_CREDIT_IMPULSE",
            formula_version="fixture-formula",
            input_observation_version_ids=inputs,
            as_of_mode=AsOfMode.SYSTEM,
            as_of_cutoff=cutoff,
            computed_at=datetime.now(UTC),
            value=1.0,
            unit="percent",
        ).derived_observation_id

    read, read_call, read_raw = old_claim("read", 1.71)
    expired, expired_call, expired_raw = old_claim("expired", 1.72)
    unread, unread_call, unread_raw = old_claim("unread", 1.73)
    kept = derived((read,), datetime(2026, 8, 3, 7, tzinfo=UTC))
    gone = derived((expired,), datetime(2026, 1, 5, 7, tzinfo=UTC))

    main(["retention-prune", "--runtime-root", str(paths.override_root), "--json"])
    capsys.readouterr()

    claims = {row[0] for row in query(paths, "SELECT claim_id FROM source_claim")}
    derived_ids = {
        row[0] for row in query(paths, "SELECT derived_observation_id FROM derived_observation")
    }
    calls = {row[0] for row in query(paths, "SELECT acquisition_id FROM acquisition_request")}
    assert kept in derived_ids and gone not in derived_ids
    # Every derived value kept can be read back to the claims it was computed from.
    for (inputs,) in query(
        paths, "SELECT input_observation_version_ids_json FROM derived_observation"
    ):
        assert set(json.loads(inputs)) <= claims
    assert (read, read_call) in query(
        paths, "SELECT claim_id, acquisition_id FROM source_claim_acquisition"
    )
    assert read_call in calls and (paths.artifacts / read_raw[:2] / read_raw).exists()
    # Older claims nothing kept reads go as before, the expired value's parents with it.
    assert not {expired, unread} & claims
    assert not {expired_call, unread_call} & calls
    assert not any((paths.artifacts / h[:2] / h).exists() for h in (expired_raw, unread_raw))


def test_a_kept_projection_keeps_the_claims_it_cites_until_it_expires(
    pruned: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    """Lookback 08: a kept projection's cited claims stay with their originals, however old.

    Shaped as the real run cited M1: twelve months, seven of them before the window. A claim
    only expired projections cited goes with the last of them; one an expired projection
    shares with a kept one stays, and so does the evidence a kept one froze.
    """
    paths = pruned["paths"]
    start = window_start(paths, pruned["latest"])
    evidence = EvidenceRepository(paths.database)
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)

    def m1_claim(period: date) -> tuple[str, str, str]:
        receipt = acquisitions.capture(
            provider="fixture",
            api_name="lookback_m1",
            parameters={"month": period.strftime("%Y%m")},
            fields="m1_yoy",
            parser_version="fixture-parser",
            fetch=lambda: f"m1 {period}".encode(),
            parse=lambda raw: raw,
            normalize=lambda raw: raw.decode(),
        ).receipt
        assert receipt.received_at and receipt.validated_at
        [claim] = evidence.append_source_claims(
            (
                SourceClaimInput(
                    metric_id="CN_M1_M2",
                    definition_version="metric-catalog-v0001",
                    period_kind="month",
                    period_start=period.replace(day=1).isoformat(),
                    period_end=period.isoformat(),
                    dimensions={"aggregate": "m1", "measure": "yoy"},
                    value=4.0,
                    value_state=EvidenceValueState.REPORTED_VALUE,
                    unit="percent",
                    provider="fixture",
                    source_reference=f"fixture:m1:{period}",
                    release_event_id=f"fixture:m1:{period}",
                    release_at=None,
                    public_available_at=None,
                    fetched_at=receipt.received_at,
                    available_at=receipt.validated_at,
                    quality_status="validated",
                    acquisition_id=receipt.acquisition_id,
                ),
            )
        )
        return claim.claim_id, receipt.acquisition_id, str(receipt.raw_hash)

    def month_end(year: int, month: int) -> date:
        return date(year + month // 12, month % 12 + 1, 1) - timedelta(days=1)

    first = date.fromisoformat(start)
    months = [month_end(first.year, first.month - 7 + offset) for offset in range(12)]
    assert sum(month.isoformat() < start for month in months) == 7
    m1 = [m1_claim(month) for month in months]
    cited = tuple(claim for claim, _call, _raw in m1)
    alone, alone_call, alone_raw = m1_claim(month_end(first.year, first.month - 9))
    framed, framed_call, framed_raw = m1_claim(month_end(first.year, first.month - 10))

    [(envelope_json,)] = query(
        paths,
        "SELECT envelope_json FROM projection_set WHERE projection_set_id="
        "(SELECT projection_set_id FROM current_projection)",
    )

    def publish(
        target: str, macro_cites: tuple[str, ...], frozen: tuple[str, ...], frozen_on: str
    ) -> str:
        """A published set citing claims as the real one does: in its documents and in
        the evidence it froze."""
        projection_set_id = f"projection-cites-{target}"
        snapshot = evidence.freeze_snapshot(
            frozen,
            mode=AsOfMode.SYSTEM,
            as_of=datetime.fromisoformat(f"{frozen_on}T07:00:00+00:00"),
        )
        envelope = {
            **json.loads(envelope_json),
            "projection_set_id": projection_set_id,
            "target_business_date": target,
            "evidence_snapshot_id": snapshot.evidence_snapshot_id,
        }
        member = {"name": "m1", "observation_version_ids": list(macro_cites)}
        macro = {
            "confirmation": {
                "dimensions": [
                    {"key": "credit", "key_indicators": [{"key": "money", "members": [member]}]}
                ]
            }
        }
        connection = sqlite3.connect(paths.database)
        try:
            with connection:
                connection.execute(
                    "INSERT INTO projection_set(projection_set_id, envelope_json) VALUES (?, ?)",
                    (projection_set_id, json.dumps(envelope)),
                )
                connection.execute(
                    "INSERT INTO analytical_dataset(projection_set_id, dataset_name, "
                    "document_json) VALUES (?, 'macro', ?)",
                    (projection_set_id, json.dumps(macro)),
                )
        finally:
            connection.close()
        return projection_set_id

    # Two expired sets share a claim and one of them M1; two kept sets share M1 in their
    # documents alone, and the later one froze its evidence, a claim of its own, before
    # the window.
    expired = publish(OLD, (*cited, alone), (alone,), OLD)
    expired_too = publish("2026-01-06", (alone,), (alone,), "2026-01-06")
    earliest_kept = publish(start, cited, ("fixture:unrelated",), start)
    later_kept = publish(TARGET, cited, (framed,), OLD)

    main(["retention-prune", "--runtime-root", str(paths.override_root), "--json"])
    capsys.readouterr()

    projections = {row[0] for row in query(paths, "SELECT projection_set_id FROM projection_set")}
    claims = {row[0] for row in query(paths, "SELECT claim_id FROM source_claim")}
    links = set(query(paths, "SELECT claim_id, acquisition_id FROM source_claim_acquisition"))
    calls = {row[0] for row in query(paths, "SELECT acquisition_id FROM acquisition_request")}
    assert not {expired, expired_too} & projections
    assert {earliest_kept, later_kept} <= projections
    # Every month of M1 a kept projection cites can be read back to its source and original,
    # the seven before the window included; so can a claim only its frozen evidence lists.
    for claim, call, raw in (*m1, (framed, framed_call, framed_raw)):
        assert claim in claims and (claim, call) in links and call in calls
        assert (paths.artifacts / raw[:2] / raw).exists()
    # What only expired sets cited goes once the last of them has expired.
    assert alone not in claims and alone_call not in calls
    assert not (paths.artifacts / alone_raw[:2] / alone_raw).exists()


def test_quarters_and_months_read_back_past_the_window_are_cleared_by_a_successful_run(
    pruned: dict[str, Any],
) -> None:
    """Macro semantics ticket 07: GDP's earlier quarters and loans' t-13, fetched again by
    each run, go at its end; one a kept derived value was computed from stays."""
    paths = pruned["paths"]
    evidence = EvidenceRepository(paths.database)

    def old_claim(
        metric_id: str, kind: str, start: str, end: str, dimensions: dict[str, str]
    ) -> str:
        [claim] = evidence.append_source_claims(
            (
                SourceClaimInput(
                    metric_id=metric_id,
                    definition_version="metric-catalog-v0001",
                    period_kind=kind,
                    period_start=start,
                    period_end=end,
                    dimensions=dimensions,
                    value=100.0,
                    value_state=EvidenceValueState.REPORTED_VALUE,
                    unit="hundred_million_cny",
                    provider="fixture",
                    source_reference=f"fixture:lookback:{metric_id}:{end}",
                    release_event_id=f"fixture:lookback:{metric_id}:{end}",
                    release_at=None,
                    public_available_at=None,
                    fetched_at=datetime.now(UTC),
                    available_at=datetime.now(UTC),
                    quality_status="validated",
                ),
            )
        )
        return claim.claim_id

    nominal = {"aggregate": "total", "measure": "nominal_ytd_level"}
    quarter = old_claim("CN_GDP", "quarter", "2025-07-01", "2025-09-30", nominal)
    parent = old_claim("CN_GDP", "quarter", "2025-04-01", "2025-06-30", nominal)
    t_13 = old_claim(
        "CN_LOAN_STRUCTURE",
        "month",
        "2025-07-01",
        "2025-07-31",
        {"borrower": "enterprise", "tenor": "long_term", "measure": "ytd_increment"},
    )
    kept = evidence.append_derived_observation(
        metric_id="CN_CREDIT_IMPULSE",
        formula_version="fixture-formula",
        input_observation_version_ids=(parent,),
        as_of_mode=AsOfMode.SYSTEM,
        as_of_cutoff=datetime(2026, 8, 3, 7, tzinfo=UTC),
        computed_at=datetime.now(UTC),
        value=1.0,
        unit="percent",
    ).derived_observation_id

    run = pruned["runner"].run(TARGET, "target-day-lookback-cleared")

    assert RunRepository(paths.database).get(run).status == "completed"
    claims = {row[0] for row in query(paths, "SELECT claim_id FROM source_claim")}
    assert not {quarter, t_13} & claims
    assert parent in claims
    assert query(
        paths, "SELECT 1 FROM derived_observation WHERE derived_observation_id=?", kept
    ) == [(1,)]


def test_today_s_tushare_calls_stay_for_the_day_s_quota(
    pruned: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    """Ticket 31: a call nothing refers to still counts against the day's quota."""
    paths = pruned["paths"]
    receipt = (
        AcquisitionRepository(paths.database, paths.artifacts)
        .capture(
            provider="tushare",
            api_name="major_news",
            parameters={"page": "orphan"},
            fields="title",
            parser_version="fixture-parser",
            fetch=lambda: b"{}",
            parse=lambda raw: raw,
            normalize=lambda raw: raw.decode(),
        )
        .receipt
    )

    main(["retention-prune", "--runtime-root", str(paths.override_root), "--json"])
    capsys.readouterr()

    assert query(
        paths, "SELECT 1 FROM acquisition_request WHERE acquisition_id=?", receipt.acquisition_id
    ) == [(1,)]


def test_a_calendar_the_run_judged_by_stays_with_the_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    """Ticket 30: fetched by no run and long past the day's quota, the response stating the
    days from the target on to the cutoff stays while the run that judged by it does."""
    install_runtime_clock(monkeypatch, request, datetime(2026, 8, 10, 10, tzinfo=UTC))
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    paths.secrets.write_text("TUSHARE_TOKEN=fixture-secret\n", encoding="utf-8")
    ModelRepository(paths.database).activate("model-v0001", explicitly_approved=True)
    runner = Runner(paths, monkeypatch)
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    launched = sse_adapter(at=datetime(2026, 8, 4, tzinfo=UTC))
    judged = launched.acquire_calendar(acquisitions, date(2026, 8, 4), date(2026, 8, 11)).receipt
    unread = launched.acquire_calendar(acquisitions, date(2025, 1, 1), date(2025, 1, 31)).receipt

    run_id = runner.run(TARGET, "judged-by-a-stored-calendar")
    prune_to_window(paths, now=datetime.now(UTC) + QUOTA_COUNTED + timedelta(days=1))

    held = {row[0] for row in query(paths, "SELECT acquisition_id FROM acquisition_request")}
    assert judged.acquisition_id in held
    assert unread.acquisition_id not in held
    assert query(
        paths,
        "SELECT phase FROM full_run_acquisition WHERE run_id=? AND acquisition_id=?",
        run_id,
        judged.acquisition_id,
    ) == [("referenced",)]


def test_retention_command_is_a_no_op_without_a_successful_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)

    main(["retention-prune", "--runtime-root", str(paths.override_root), "--json"])

    assert json.loads(capsys.readouterr().out)["window_start"] is None


def test_report_output_artifact_expires_with_report_input(pruned: dict[str, Any]) -> None:
    paths = pruned["paths"]
    digest = pruned["old_output"]
    assert query(paths, "SELECT content_hash FROM artifact WHERE content_hash=?", digest) == []
    assert not (paths.artifacts / digest[:2] / digest).exists()
    assert (
        query(
            paths,
            "SELECT attempt_id FROM report_attempt WHERE report_snapshot_id=?",
            "report-cancelled-without-snapshot",
        )
        == []
    )
