"""Ticket 23: only 120 sessions of details, summaries and batches outlive a successful run."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from datetime import UTC, date, datetime
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
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.worker import process_pending_run
from tests.integration.test_core_history_refresh import historical_response

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
        latest = runner.run(TARGET, "target-day")
        states = ProjectionSetRepository(paths.database).current().datasets["core_assets"]
        yield {
            "paths": paths,
            "runner": runner,
            "old": old,
            "latest": latest,
            "old_raw": old_raw,
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
    failed = pruned["runner"].run("2026-08-04", "failing-day")

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
                    "INSERT INTO claim_matched_quote VALUES (?, 'media_page', '原话', '标题', "
                    "'财联社', NULL, ?, NULL, 'news-rules-v0001')",
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
                "INSERT INTO claim_matched_quote VALUES (?, 'tushare_news', '原话', '标题', "
                "'新华网', NULL, ?, NULL, 'news-rules-v0001')",
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


def test_retention_command_is_a_no_op_without_a_successful_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)

    main(["retention-prune", "--runtime-root", str(paths.override_root), "--json"])

    assert json.loads(capsys.readouterr().out)["window_start"] is None
