"""A publication time nobody published is presumed to the next day, and says so.

Some official values arrive without any record of when they first became visible: the page
carries the adjustment date but no release time. Dropping them loses real data; guessing an
early time would let a value be used before anyone could have seen it. The presumption takes
the safe direction instead, moving visibility later, and is stored as a presumption so no
reader mistakes it for a time the source actually published.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

from pring_cycle.evidence import (
    AsOfMode,
    EvidenceRepository,
    EvidenceValueState,
    SourceClaimInput,
    presumed_public_time,
)

ANNOUNCED = date(2026, 4, 19)


def claim(*, public_at: datetime | None, basis: str) -> SourceClaimInput:
    return SourceClaimInput(
        metric_id="CN_RRR_EVENT",
        definition_version="metric-catalog-v0001",
        period_kind="event",
        period_start=ANNOUNCED.isoformat(),
        period_end=ANNOUNCED.isoformat(),
        dimensions={"scope": "broad", "measure": "change"},
        value=-0.5,
        value_state=EvidenceValueState.REPORTED_VALUE,
        unit="percentage_points",
        provider="official",
        source_reference="fixture:pbc:rrr:2026-04-19",
        release_event_id="release:pbc:rrr:2026-04-19",
        release_at=None,
        public_available_at=public_at,
        fetched_at=datetime(2026, 9, 17, 1, 0, tzinfo=UTC),
        available_at=datetime(2026, 9, 17, 1, 0, tzinfo=UTC),
        certification_status="awaiting_source_certification",
        quality_status="validated",
        public_time_basis=basis,
    )


def test_a_presumed_value_stays_invisible_on_the_day_it_was_announced(tmp_path: Path) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    presumed = presumed_public_time(ANNOUNCED, "Asia/Shanghai")
    repository.append_source_claim(claim(public_at=presumed, basis="presumed_next_day"))

    def series(as_of: datetime) -> tuple[object, ...]:
        return repository.metric_series(
            "CN_RRR_EVENT",
            mode=AsOfMode.PUBLIC,
            as_of=as_of,
            definition_version="metric-catalog-v0001",
        )

    def visible(as_of: datetime) -> tuple[float | None, ...]:
        return tuple(point.selected_value for point in series(as_of))

    # 23:59 on the announcement day, Shanghai time, is still the announcement day.
    assert visible(datetime(2026, 4, 19, 15, 59, tzinfo=UTC)) == ()
    # Midnight that begins the next day is the first instant it may be used.
    assert visible(datetime(2026, 4, 19, 16, 0, tzinfo=UTC)) == (-0.5,)
    # The presumption is recorded as one, not passed off as a published time.
    point = series(datetime(2026, 4, 19, 16, 0, tzinfo=UTC))[0]
    assert point.claims[0].public_time_basis == "presumed_next_day"


def test_an_observed_release_time_is_not_labelled_a_presumption(tmp_path: Path) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    observed = datetime(2026, 4, 19, 9, 30, tzinfo=UTC)
    repository.append_source_claim(claim(public_at=observed, basis="observed_release"))

    # It is visible from the moment the source published it, with no day-long delay added.
    series = repository.metric_series(
        "CN_RRR_EVENT",
        mode=AsOfMode.PUBLIC,
        as_of=observed,
        definition_version="metric-catalog-v0001",
    )
    assert tuple(point.selected_value for point in series) == (-0.5,)
    assert series[0].claims[0].public_time_basis == "observed_release"


def test_the_presumed_instant_is_midnight_in_the_metric_s_own_timezone() -> None:
    # Shanghai is UTC+8, so the first usable instant is 16:00 UTC on the announcement day.
    assert presumed_public_time(ANNOUNCED, "Asia/Shanghai") == datetime(
        2026, 4, 19, 16, 0, tzinfo=UTC
    )
    # A metric released on London time gets London's midnight, not Shanghai's.
    assert presumed_public_time(ANNOUNCED, "Europe/London") == datetime(
        2026, 4, 19, 23, 0, tzinfo=UTC
    )
