"""Freshness by due period, recorded per batch, and the target day picked from launch time."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from pring_cycle.cli import main
from pring_cycle.evidence import EvidenceRepository, EvidenceValueState, SourceClaimInput
from pring_cycle.freshness import batch_freshness
from pring_cycle.models import ModelRepository
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.worker import process_pending_run

SHANGHAI = ZoneInfo("Asia/Shanghai")
# Wednesday 2026-09-23 18:00: after the 17:00 index close, before EIA's evening release.
CUTOFF = datetime(2026, 9, 23, 18, tzinfo=SHANGHAI)


def runtime(root: Path) -> RuntimePaths:
    paths = RuntimePaths.discover(root / "runtime")
    initialize_runtime(paths)
    models = ModelRepository(paths.database)
    models.activate("model-v0001", explicitly_approved=True)
    return paths


def seed(
    evidence: EvidenceRepository,
    metric_id: str,
    start: date,
    end: date,
    *,
    kind: str,
    unit: str = "scalar",
    dimensions: dict[str, str] | None = None,
) -> None:
    known = datetime.combine(end, datetime.min.time(), tzinfo=UTC)
    evidence.append_source_claim(
        SourceClaimInput(
            metric_id=metric_id,
            definition_version="metric-catalog-v0001",
            period_kind=kind,
            period_start=start.isoformat(),
            period_end=end.isoformat(),
            dimensions=dimensions or {},
            value=1.0,
            value_state=EvidenceValueState.REPORTED_VALUE,
            unit=unit,
            provider="fixture",
            source_reference=f"fixture:{metric_id}:{end}",
            release_event_id=f"fixture:{metric_id}:{end}",
            release_at=known,
            public_available_at=known,
            fetched_at=known,
            available_at=known,
            # Registered sources need no certification (ADR-0021); only structure is checked.
            certification_status="awaiting_source_certification",
            quality_status="validated",
        )
    )


def daily(evidence: EvidenceRepository, metric_id: str, day: date, unit: str = "scalar") -> None:
    seed(evidence, metric_id, day, day, kind="business_day", unit=unit)


def monthly(evidence: EvidenceRepository, metric_id: str, end: date, **kwargs: Any) -> None:
    seed(evidence, metric_id, end.replace(day=1), end, kind="month", **kwargs)


@pytest.fixture(scope="module")
def recorded(tmp_path_factory: pytest.TempPathFactory) -> Iterator[dict[str, dict[str, object]]]:
    """One Worker run whose seeded holdings sit on each frequency's boundaries."""
    paths = runtime(tmp_path_factory.mktemp("freshness"))
    evidence = EvidenceRepository(paths.database)
    daily(evidence, "CN_EQ_CSI300", date(2026, 9, 23))
    daily(evidence, "CN_EQ_CSI500", date(2026, 9, 22))
    daily(evidence, "CN_EQ_CSI1000", date(2026, 9, 21))
    daily(evidence, "CN_BOND_10Y_930916", date(2026, 9, 18))
    daily(evidence, "EIA_BRENT_RBRTE", date(2026, 9, 18), "usd_per_barrel")
    daily(evidence, "EIA_WTI_RWTC", date(2026, 9, 4), "usd_per_barrel")
    daily(evidence, "CN_USDCNH_FXCM", date(2026, 9, 22), "index_points")
    monthly(
        evidence,
        "CN_CPI_HEADLINE",
        date(2026, 8, 31),
        unit="percent",
        dimensions={"measure": "yoy", "category": "headline"},
    )
    monthly(
        evidence,
        "CN_PPI",
        date(2026, 7, 31),
        unit="percent",
        dimensions={"measure": "yoy", "category": "headline"},
    )
    monthly(evidence, "CN_LPR_1Y_5Y", date(2026, 8, 31), unit="percent", dimensions={"tenor": "1y"})
    seed(
        evidence,
        "CN_GDP",
        date(2026, 4, 1),
        date(2026, 6, 30),
        kind="quarter",
        unit="percent",
        dimensions={"aggregate": "gdp", "measure": "yoy"},
    )
    seed(
        evidence,
        "CN_CAPACITY_UTILIZATION",
        date(2026, 1, 1),
        date(2026, 3, 31),
        kind="quarter",
        unit="percent",
        dimensions={"industry": "total", "measure": "utilization_rate"},
    )
    seed(
        evidence,
        "CN_RRR_EVENT",
        date(2025, 5, 8),
        date(2025, 5, 8),
        kind="event",
        unit="percentage_points",
        dimensions={"scope": "all", "measure": "rrr_change"},
    )
    run = RunRepository(paths.database).submit_manual_full(
        target_business_date="2026-09-23",
        client_request_id="freshness",
        model_version_id="model-v0001",
        system_as_of=CUTOFF,
        cutoff_mode="explicit",
    )
    process_pending_run(paths, report_adapters=())
    yield batch_freshness(paths.database, run.run_id)


@pytest.mark.parametrize(
    ("metric_id", "status", "behind"),
    [
        ("CN_EQ_CSI300", "current", 0),
        ("CN_EQ_CSI500", "awaiting_release", 0),
        ("CN_EQ_CSI1000", "stale", 1),
        ("CN_BOND_10Y_930916", "stale", 2),
        ("CN_DR007", "missing", None),
        ("EIA_BRENT_RBRTE", "current", 0),
        ("EIA_WTI_RWTC", "awaiting_release", 0),
        ("CN_CPI_HEADLINE", "current", 0),
        ("CN_PPI", "stale", 1),
        ("CN_LPR_1Y_5Y", "awaiting_release", 0),
        ("CN_GDP", "current", 0),
        ("CN_CAPACITY_UTILIZATION", "stale", 1),
        ("CN_RRR_EVENT", "current", 0),
        ("CN_USDCNH_FXCM", "unconfigured", None),
        ("CN_DR007_POLICY_SPREAD", "missing", 0),
    ],
)
def test_batch_records_each_frequency_boundary(
    recorded: dict[str, dict[str, object]], metric_id: str, status: str, behind: int | None
) -> None:
    row = recorded[metric_id]

    assert (row["status"], row["periods_behind"]) == (status, behind)


def test_public_time_is_the_earlier_of_inferred_release_and_first_acquisition(
    recorded: dict[str, dict[str, object]],
) -> None:
    # CPI for August is inferred at 2026-09-10 09:30 but was held from 2026-08-31.
    cpi = datetime.fromisoformat(str(recorded["CN_CPI_HEADLINE"]["public_available_at"]))
    # The CSI 300 close was held from its own day's midnight UTC, before 17:00 Shanghai.
    csi = datetime.fromisoformat(str(recorded["CN_EQ_CSI300"]["public_available_at"]))

    assert cpi == datetime(2026, 8, 31, tzinfo=UTC)
    assert csi == datetime(2026, 9, 23, tzinfo=UTC)
    assert recorded["CN_EQ_CSI300"]["basis"]


class LaunchClock(datetime):
    launched_at = CUTOFF

    @classmethod
    def now(cls, tz: Any = None) -> datetime:  # type: ignore[override]
        return cls.launched_at.astimezone(tz)


@pytest.fixture
def submit_at(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> Any:
    paths = runtime(tmp_path)
    monkeypatch.setattr("pring_cycle.cli.datetime", LaunchClock)

    def submit(launched_at: datetime) -> str:
        LaunchClock.launched_at = launched_at
        main(
            [
                "run-submit",
                "--runtime-root",
                str(paths.override_root),
                "--request-id",
                f"launch-{launched_at.isoformat()}",
                "--json",
            ]
        )
        return str(json.loads(capsys.readouterr().out)["target_business_date"])

    submit.paths = paths  # type: ignore[attr-defined]
    return submit


@pytest.mark.parametrize(
    ("launched_at", "target"),
    [
        (datetime(2026, 9, 21, 16, tzinfo=SHANGHAI), "2026-09-18"),
        (datetime(2026, 9, 22, 10, tzinfo=SHANGHAI), "2026-09-21"),
        (datetime(2026, 9, 22, 17, 30, tzinfo=SHANGHAI), "2026-09-22"),
    ],
)
def test_run_submit_picks_the_latest_session_whose_core_update_has_passed(
    submit_at: Any, launched_at: datetime, target: str
) -> None:
    assert submit_at(launched_at) == target


def test_run_submit_reads_holidays_from_the_sse_calendar(
    submit_at: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = submit_at.paths
    paths.secrets.write_text("TUSHARE_TOKEN=fixture-secret\n", encoding="utf-8")
    holiday = {date(2026, 10, 1) + timedelta(days=offset) for offset in range(7)}

    class CalendarOpener:
        def open(self, request: Any, *, timeout: int) -> BytesIO:
            payload = json.loads(request.data)
            assert payload["api_name"] == "trade_cal"
            start = datetime.strptime(payload["params"]["start_date"], "%Y%m%d").date()
            end = datetime.strptime(payload["params"]["end_date"], "%Y%m%d").date()
            items = []
            for offset in range((end - start).days + 1):
                day = start + timedelta(days=offset)
                if day.weekday() < 5 and day not in holiday:
                    items.append([day.strftime("%Y%m%d"), 1])
            document = {"code": 0, "data": {"fields": ["cal_date", "is_open"], "items": items}}
            return BytesIO(json.dumps(document).encode())

    monkeypatch.setattr("pring_cycle.source_adapters.build_opener", CalendarOpener)

    assert submit_at(datetime(2026, 10, 8, 10, tzinfo=SHANGHAI)) == "2026-09-30"


def test_run_submit_on_a_closed_day_ending_the_calendar_targets_the_last_session(
    submit_at: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Mid-Autumn 2026-09-25 (Friday): TuShare lists it with is_open=0, so the fetched
    # range ends on a closure and the last open session alone understates its coverage.
    paths = submit_at.paths
    paths.secrets.write_text("TUSHARE_TOKEN=fixture-secret\n", encoding="utf-8")
    calls = []

    class CalendarOpener:
        def open(self, request: Any, *, timeout: int) -> BytesIO:
            payload = json.loads(request.data)
            calls.append(payload["params"])
            start = datetime.strptime(payload["params"]["start_date"], "%Y%m%d").date()
            end = datetime.strptime(payload["params"]["end_date"], "%Y%m%d").date()
            items = []
            for offset in range((end - start).days + 1):
                day = start + timedelta(days=offset)
                is_open = int(day.weekday() < 5 and day != date(2026, 9, 25))
                items.append([day.strftime("%Y%m%d"), is_open])
            document = {"code": 0, "data": {"fields": ["cal_date", "is_open"], "items": items}}
            return BytesIO(json.dumps(document).encode())

    monkeypatch.setattr("pring_cycle.source_adapters.build_opener", CalendarOpener)

    # Fetched at launch, then read back from the stored response.
    assert submit_at(datetime(2026, 9, 25, 18, 30, tzinfo=SHANGHAI)) == "2026-09-24"
    assert submit_at(datetime(2026, 9, 25, 20, tzinfo=SHANGHAI)) == "2026-09-24"
    assert len(calls) == 1
