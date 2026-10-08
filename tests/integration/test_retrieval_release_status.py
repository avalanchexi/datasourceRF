"""Whether a retrieval scope's period is published: one series read per metric and cutoff."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from pring_cycle.evidence import EvidenceRepository, EvidenceValueState, SourceClaimInput
from pring_cycle.runs import RetrievalScope
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.worker import SeriesReads, _retrieval_release_status

SHANGHAI = ZoneInfo("Asia/Shanghai")
VERSION = "metric-catalog-v0001"
# Thursday noon in Shanghai: DR007 for the 27th is out at 12:00, the 28th is not yet due.
CUTOFF = datetime(2026, 8, 28, 12, 30, tzinfo=SHANGHAI)


def dr007(day: date, public: datetime) -> SourceClaimInput:
    return SourceClaimInput(
        metric_id="CN_DR007",
        definition_version=VERSION,
        period_kind="business_day",
        period_start=day.isoformat(),
        period_end=day.isoformat(),
        dimensions={},
        value=1.5,
        value_state=EvidenceValueState.REPORTED_VALUE,
        unit="scalar",
        provider="fixture",
        source_reference=f"fixture:dr007:{day}",
        release_event_id=f"fixture:dr007:{day}",
        release_at=public,
        public_available_at=public,
        fetched_at=public,
        available_at=public,
        quality_status="validated",
    )


@pytest.fixture
def paths(tmp_path: Path) -> RuntimePaths:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    EvidenceRepository(paths.database).append_source_claims(
        (
            dr007(date(2026, 8, 25), datetime.combine(date(2026, 8, 25), time(12), SHANGHAI)),
            dr007(date(2026, 8, 26), datetime.combine(date(2026, 8, 26), time(12), SHANGHAI)),
            # Held, but public only after the cutoff: the claim cannot show it released.
            dr007(date(2026, 8, 27), CUTOFF + timedelta(hours=1)),
        )
    )
    return paths


def scopes() -> list[RetrievalScope]:
    daily = [
        RetrievalScope(f"full:dr007:{day}", ("CN_DR007",), day, "P1", None)
        for day in ("2026-08-25", "2026-08-26", "2026-08-27", "2026-08-28", "2026-08-31")
    ]
    lpr = [
        RetrievalScope(f"full:lpr:{period}", ("CN_LPR_1Y_5Y",), period, "P1", None)
        for period in ("2026-08", "2026-09")
    ]
    return daily + lpr


def statuses(paths: RuntimePaths, reads: SeriesReads | None, **options: Any) -> list[str]:
    return [
        _retrieval_release_status(
            paths, scope, CUTOFF, definition_version=VERSION, reads=reads, **options
        )
        for scope in scopes()
    ]


@pytest.mark.parametrize("latest_only", [False, True])
def test_shared_reads_give_the_status_each_fresh_read_gives(
    paths: RuntimePaths, latest_only: bool
) -> None:
    fresh = statuses(paths, None, latest_only=latest_only)
    shared = statuses(
        paths, SeriesReads(EvidenceRepository(paths.database)), latest_only=latest_only
    )

    assert shared == fresh
    # Released from a held claim, from the registry, and awaiting release all occur.
    assert fresh[0] == "released"
    assert "awaiting_release" in fresh
    assert fresh[-2] == "released"  # August's LPR was fixed on the 20th
    assert fresh[-1] == "awaiting_release"  # September's is fixed on the 21st


@pytest.mark.parametrize(
    ("metric_id", "period", "expected"),
    [
        # A month a model's lookback reads back to, out by its own release rule (L01).
        ("CN_INDUSTRIAL_VA", "2025-08", "released"),
        ("CN_CAPACITY_UTILIZATION", "2025-Q3", "released"),
        ("CN_TOOL_LIQUIDITY_MONTHLY", "2026-06", "released"),
        # A month not out yet stays behind the gate.
        ("CN_INDUSTRIAL_VA", "2026-08", "awaiting_release"),
        # No release rule to judge it by: an event, or a metric the registry does not know.
        ("CN_RRR_EVENT", "2026-08-03", "unknown_release_configuration"),
        ("CN_USDCNH_FXCM", "2026-08-03", "unknown_release_configuration"),
        # An earlier session of a daily series is not searched day by day (ticket 19).
        ("CN_DR007", "2026-08-24", "earlier_session_not_searched"),
    ],
)
def test_a_full_run_judges_each_history_period_by_its_own_release_rule(
    paths: RuntimePaths, metric_id: str, period: str, expected: str
) -> None:
    scope = RetrievalScope(f"full:{metric_id}:{period}", (metric_id,), period, "P1", None)

    assert (
        _retrieval_release_status(
            paths, scope, CUTOFF, definition_version=VERSION, latest_only=True
        )
        == expected
    )


def test_a_public_cutoff_before_the_claims_is_respected_through_shared_reads(
    paths: RuntimePaths,
) -> None:
    early = datetime(2026, 8, 25, 9, tzinfo=SHANGHAI)
    fresh = statuses(paths, None, public_as_of=early)
    shared = statuses(paths, SeriesReads(EvidenceRepository(paths.database)), public_as_of=early)

    assert shared == fresh
    assert fresh[0] == "awaiting_release"


def test_each_metric_is_read_once_per_cutoff(
    paths: RuntimePaths, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = EvidenceRepository(paths.database)
    reads: list[str] = []
    original = repository.metric_series

    def counted(metric_id: str, **kwargs: Any) -> Any:
        reads.append(metric_id)
        return original(metric_id, **kwargs)

    monkeypatch.setattr(repository, "metric_series", counted)
    shared = SeriesReads(repository)

    statuses(paths, shared)
    statuses(paths, shared)

    assert sorted(reads) == ["CN_DR007", "CN_LPR_1Y_5Y"]
    # A different cutoff is a different read.
    _retrieval_release_status(
        paths, scopes()[0], CUTOFF + timedelta(minutes=1), definition_version=VERSION, reads=shared
    )
    assert reads.count("CN_DR007") == 2
