"""Ticket 29: a backfill reads its series from one in-memory copy of the claims.

Each backfilled day read every metric's whole history again at that day's public cutoff,
about 13.5 thousand reads a full run. Inside ``series_snapshot`` the same reads come from
claims loaded once; every field of every point must be what the database would have given.
"""

from __future__ import annotations

import itertools
from dataclasses import replace
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

import pring_cycle.evidence as evidence_module
from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.runtime import RuntimePaths
from tests.integration.test_claim_adoption import news_claim
from tests.integration.test_same_definition import V0012, V0013, V0014, claim, register, stored
from tests.integration.test_worker_execution import runtime

SHANGHAI = ZoneInfo("Asia/Shanghai")
METRICS = ("CN_DR007", "CN_CREDIT_IMPULSE", "CN_INDUSTRIAL_VA")


def day_end(day: str) -> datetime:
    return datetime.combine(datetime.fromisoformat(day).date(), time.max, tzinfo=SHANGHAI)


@pytest.fixture
def paths(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> RuntimePaths:
    """Claims covering what a read decides: revisions, conflicts across versions, a changed
    definition, publication after storage, sub-millisecond times and unstated news."""
    paths = runtime(tmp_path)
    register(paths, tmp_path, capsys)
    repository = EvidenceRepository(paths.database)
    at = datetime(2026, 9, 30, tzinfo=UTC)
    # A revision across like-defined versions, and two sources that conflict.
    stored(repository, claim(V0013, 1.38, day="2026-09-28", available=at))
    stored(repository, claim(V0014, 1.40, day="2026-09-28", available=at + timedelta(days=1)))
    stored(repository, claim(V0012, 1.38, day="2026-09-29", available=at))
    stored(repository, claim(V0014, 1.50, day="2026-09-29", provider="pbc-official"))
    # Public only after it was stored: read at a public cutoff only when system time may do.
    stored(
        repository,
        replace(
            claim(V0014, 1.36, day="2026-09-25", available=datetime(2026, 9, 26, 2, tzinfo=UTC)),
            public_available_at=datetime(2026, 9, 27, 2, tzinfo=UTC),
            release_at=datetime(2026, 9, 27, 2, tzinfo=UTC),
        ),
    )
    # Stored a fraction of a millisecond after a cutoff that SQLite rounds to the same instant:
    # listed, never selected. Such a point keeps the first stored observation's id, which is
    # not that of the first claim by id (ifind's).
    stored(
        repository,
        claim(V0014, 1.37, day="2026-09-26", available=at + timedelta(microseconds=300)),
    )
    stored(
        repository,
        claim(
            V0014,
            1.37,
            day="2026-09-26",
            provider="ifind",
            available=at + timedelta(microseconds=250),
        ),
    )
    stored(
        repository,
        claim(
            V0013,
            1.35,
            day="2026-09-26",
            provider="pbc-official",
            available=at + timedelta(microseconds=200),
        ),
    )
    # Dated neither by its source nor by the cadence: never visible at a public cutoff.
    with pytest.MonkeyPatch.context() as undated:
        undated.setattr(evidence_module, "_inferred_public_time", lambda _claim: None)
        stored(
            repository,
            replace(
                claim(V0014, 1.33, day="2026-09-24", provider="undated", available=at),
                public_available_at=None,
            ),
        )
    # A changed definition: v0013's credit impulse is not v0014's.
    for version, value, unit in ((V0013, 0.5, "percentage_points"), (V0014, 20.0, "percent")):
        stored(
            repository,
            replace(
                claim(version, value, metric_id="CN_CREDIT_IMPULSE", unit=unit),
                period_kind="month",
                period_start="2026-08-01",
                period_end="2026-08-31",
            ),
        )
    # News: a province's figure the rules no longer state, and the country's they do.
    known = datetime(2026, 9, 16, 2, tzinfo=UTC)
    news_claim(
        paths,
        V0014,
        "tushare_news",
        6.1,
        "1—8月，全省规模以上工业增加值同比增长6.1%。",
        known + timedelta(days=5),
    )
    news_claim(
        paths, V0014, "tushare_news", 5.3, "1—8月份，规模以上工业增加值同比增长5.3%。", known
    )
    return paths


def reads() -> list[dict[str, Any]]:
    """Every combination a backfill could ask, its cutoffs going back as well as forth."""
    system_cutoffs = (
        datetime(2026, 10, 2, tzinfo=UTC),
        datetime(2026, 9, 30, tzinfo=UTC) + timedelta(microseconds=100),
        datetime(2026, 9, 30, 12, tzinfo=UTC),
        datetime(2026, 9, 26, 12, tzinfo=UTC),
    )
    public_cutoffs = (
        None,
        day_end("2026-09-29"),
        day_end("2026-09-26"),
        day_end("2026-10-01"),
        day_end("2026-09-20"),
        day_end("2026-09-30"),
    )
    combinations = itertools.product(
        METRICS,
        (None, V0012, V0013, V0014),
        public_cutoffs,
        system_cutoffs,
        (AsOfMode.SYSTEM, AsOfMode.PUBLIC),
        (False, True),
        (None, 0.2),
    )
    return [
        {
            "metric_id": metric_id,
            "definition_version": version,
            "public_as_of": public,
            "as_of": as_of,
            "mode": mode,
            "allow_system_at_public_cutoff": allow,
            "tolerance": tolerance,
        }
        for metric_id, version, public, as_of, mode, allow, tolerance in combinations
        if not allow or (public is not None and mode is AsOfMode.SYSTEM)
    ]


def test_a_snapshot_reads_every_point_as_the_database_does(paths: RuntimePaths) -> None:
    direct = EvidenceRepository(paths.database)
    expected = [direct.metric_series(**read) for read in reads()]
    assert any(point.selection_status == "conflicted" for series in expected for point in series)
    assert any(point.selection_status == "unavailable" for series in expected for point in series)

    snapshot = EvidenceRepository(paths.database)
    with snapshot.series_snapshot():
        # Twice: the second pass reads what the first one kept.
        for _ in range(2):
            assert [snapshot.metric_series(**read) for read in reads()] == expected


def test_a_snapshot_reselects_and_queries_nothing_it_already_read(
    paths: RuntimePaths, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = EvidenceRepository(paths.database)
    read: dict[str, Any] = {
        "mode": AsOfMode.SYSTEM,
        "as_of": datetime(2026, 10, 2, tzinfo=UTC),
        "public_as_of": day_end("2026-09-29"),
        "definition_version": V0014,
    }
    with repository.series_snapshot():
        first = repository.metric_series("CN_DR007", **read)
        selections = []
        original = evidence_module._select_merged_rows

        def counting(*args: Any, **kwargs: Any) -> Any:
            selections.append(args)
            return original(*args, **kwargs)

        def no_database() -> Any:
            raise AssertionError("the snapshot went back to the database")

        monkeypatch.setattr(evidence_module, "_select_merged_rows", counting)
        monkeypatch.setattr(repository, "_connect", no_database)
        assert repository.metric_series("CN_DR007", **read) == first
        assert selections == []


@pytest.mark.parametrize("writer", ["same", "another"])
def test_a_claim_appended_inside_a_snapshot_is_read_next(paths: RuntimePaths, writer: str) -> None:
    repository = EvidenceRepository(paths.database)
    read: dict[str, Any] = {
        "mode": AsOfMode.SYSTEM,
        "as_of": datetime(2026, 10, 2, tzinfo=UTC),
        "public_as_of": day_end("2026-10-01"),
        "definition_version": V0014,
    }
    with repository.series_snapshot():
        before = repository.metric_series("CN_DR007", **read)
        appender = repository if writer == "same" else EvidenceRepository(paths.database)
        (added,) = appender.append_source_claims(
            (
                replace(
                    claim(V0014, 1.41, day="2026-09-30"),
                    certification_status="awaiting_source_certification",
                ),
            )
        )
        after = repository.metric_series("CN_DR007", **read)

    assert added.claim_id not in {point.selected_claim_id for point in before}
    assert after == EvidenceRepository(paths.database).metric_series("CN_DR007", **read)
    assert added.claim_id in {point.selected_claim_id for point in after}


def test_a_preloaded_series_reads_a_claim_another_repository_appended(
    paths: RuntimePaths,
) -> None:
    """The preload goes before the snapshot; it must not outlive the claims either."""
    repository = EvidenceRepository(paths.database)
    read: dict[str, Any] = {
        "mode": AsOfMode.SYSTEM,
        "as_of": datetime(2026, 10, 2, tzinfo=UTC),
        "definition_version": V0014,
    }
    repository.preload_metric_series({("CN_DR007", V0014)})
    with repository.series_snapshot():
        before = repository.metric_series("CN_DR007", **read)
        (added,) = EvidenceRepository(paths.database).append_source_claims(
            (
                replace(
                    claim(V0014, 1.41, day="2026-09-30"),
                    certification_status="awaiting_source_certification",
                ),
            )
        )
        after = repository.metric_series("CN_DR007", **read)

    assert added.claim_id not in {point.selected_claim_id for point in before}
    assert after == EvidenceRepository(paths.database).metric_series("CN_DR007", **read)


def test_a_snapshot_is_let_go_when_its_scope_ends(paths: RuntimePaths) -> None:
    repository = EvidenceRepository(paths.database)
    with repository.series_snapshot():
        with repository.series_snapshot():
            repository.metric_series(
                "CN_DR007", mode=AsOfMode.SYSTEM, as_of=datetime(2026, 10, 2, tzinfo=UTC)
            )
        assert repository._series_snapshot is not None
    assert repository._series_snapshot is None
    with pytest.raises(RuntimeError), repository.series_snapshot():
        raise RuntimeError("a backfill stopped")
    assert repository._series_snapshot is None
