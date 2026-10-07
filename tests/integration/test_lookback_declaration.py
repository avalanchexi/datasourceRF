"""One lookback declaration for the full run's plan and the direct fetch (macro semantics #02).

A reading names a metric, its members, and the released periods it reads: one, N
consecutive, four quarters, N sessions or an explicit set. Existing models read back as
they did before the declaration: the plan requires what it required and the fetch starts
where it started.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from pring_cycle import full_retrieval, worker
from pring_cycle.lookback import Lookback, Periods, Reading, own_reading, resolve
from pring_cycle.models import ModelRepository, model_v0014_manifest, model_v0015_manifest
from pring_cycle.runs import RetrievalScope, RunRepository, member_keys
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.search_evidence import ModelInputSelector
from pring_cycle.trading_calendar import TradingCalendar
from pring_cycle.tushare_context import TushareContextAdapter
from pring_cycle.worker import process_pending_run
from tests.integration.test_full_run_retrieval import prepare, seed_core_history
from tests.integration.test_official_gdp_fallback import admit_gdp_candidate, delivery
from tests.integration.test_trading_calendar import record_sse_calendar

WEEKDAYS = TradingCalendar()


@pytest.mark.parametrize(
    ("periods", "newest", "expected"),
    [
        (Periods.consecutive(1), "2026-08", ("2026-08",)),
        (Periods.consecutive(3), "2026-02", ("2025-12", "2026-01", "2026-02")),
        # Year-on-year of a month differenced from year-to-date figures: t-13 is the
        # farthest point, four periods in all.
        (
            Periods.explicit(0, 1, 12, 13),
            "2026-08",
            ("2025-07", "2025-08", "2026-07", "2026-08"),
        ),
        (Periods.quarters(4), "2026-Q2", ("2025-Q3", "2025-Q4", "2026-Q1", "2026-Q2")),
        (Periods.sessions(1), "2026-08-28", ("2026-08-28",)),
    ],
)
def test_a_reading_reads_its_periods_back_from_the_newest(
    periods: Periods, newest: str, expected: tuple[str, ...]
) -> None:
    assert periods.back_from(newest) == expected


def test_an_explicit_set_is_as_far_as_its_farthest_point_not_as_many() -> None:
    year_on_year = Periods.explicit(13, 12, 1, 0)

    assert year_on_year.farthest == 13
    assert len(year_on_year.offsets) == 4
    assert year_on_year.offsets == (0, 1, 12, 13)


def test_sessions_are_counted_on_the_calendar() -> None:
    sessions = ("2026-09-28", "2026-09-29", "2026-09-30", "2026-10-08", "2026-10-09")

    assert Periods.sessions(3).back_from("2026-10-08", sessions) == (
        "2026-09-29",
        "2026-09-30",
        "2026-10-08",
    )
    with pytest.raises(ValueError, match="lookback_sessions_short"):
        Periods.sessions(3).back_from("2026-09-29", sessions)


@pytest.mark.parametrize(
    "periods",
    [lambda: Periods.explicit(0, 0), lambda: Periods.explicit(-1), lambda: Periods.consecutive(0)],
)
def test_an_ill_formed_set_is_refused(periods: Any) -> None:
    with pytest.raises(ValueError, match="lookback_"):
        periods()


def _window_to(last: date) -> tuple[date, ...]:
    return tuple(
        date(2026, 4, 6) + timedelta(days=offset)
        for offset in range((last - date(2026, 4, 6)).days + 1)
        if (date(2026, 4, 6) + timedelta(days=offset)).weekday() < 5
    )


def _resolve(*readings: Reading) -> Lookback:
    # 2026-04-06 to 2026-06-30: CPI's newest out moves from February to May.
    window = _window_to(date(2026, 6, 30))
    return resolve(
        readings,
        formula_versions={},
        window=window,
        public_cutoff=datetime.combine(window[-1], time.max, tzinfo=ZoneInfo("Asia/Shanghai")),
        calendar=WEEKDAYS,
    )


def test_a_reading_read_every_day_is_required_and_covered_for_each_day_of_the_window() -> None:
    year_on_year = Reading(
        "CN_CPI_HEADLINE", "yoy_momentum", Periods.explicit(0, 12), every_day=True
    )
    read = _resolve(own_reading("CN_CPI_HEADLINE", "monthly"), year_on_year)

    # Each day's month and the same month a year before; the series' own reading adds the
    # month before the first day's newest, to compare with.
    assert read.coverage.periods["CN_CPI_HEADLINE"] == (
        *(f"2025-{m}" for m in ("02", "03", "04", "05")),
        *(f"2026-{m}" for m in ("01", "02", "03", "04", "05")),
    )
    assert read.resolved["yoy_momentum"].minimum.periods == {
        "CN_CPI_HEADLINE": ("2025-05", "2026-05")
    }
    # Held only to April, the plan requires what was out by then and looks for May.
    assert list(read.required("CN_CPI_HEADLINE", "2026-04")) == [
        "2025-02",
        "2025-03",
        "2025-04",
        "2025-05",
        "2026-02",
        "2026-03",
        "2026-04",
    ]


def test_the_fetch_covers_what_a_day_reads_not_only_what_it_must_hold() -> None:
    # Thirteen months read each day, the newest alone required.
    slope = Reading(
        "CN_PPI",
        "level_range",
        Periods.consecutive(13),
        required=Periods.consecutive(1),
        every_day=True,
    )
    read = _resolve(slope)

    assert read.coverage.start("CN_PPI") == "2025-02"
    assert list(read.required("CN_PPI", "2026-05")) == ["2026-02", "2026-03", "2026-04", "2026-05"]


def test_each_reading_keeps_its_own_members_on_its_own_periods() -> None:
    total = ({"aggregate": "total", "measure": "nominal_ytd_level"},)
    growth = ({"aggregate": "total", "measure": "real_quarter_yoy"},)
    read = _resolve(
        Reading("CN_GDP", "level", Periods.quarters(1), members=total, every_day=True),
        Reading("CN_GDP", "momentum", Periods.quarters(4), members=growth, every_day=True),
    )

    required = read.required("CN_GDP", "2026-Q1")

    # Q4 2025 was the newest out on the window's first days, Q1 2026 from mid-April.
    assert required == {
        "2025-Q1": growth,
        "2025-Q2": growth,
        "2025-Q3": growth,
        "2025-Q4": (*total, *growth),
        "2026-Q1": (*total, *growth),
    }


def test_a_daily_series_read_every_session_asks_others_members_of_the_target_day_alone() -> None:
    sessions = ("2026-08-26", "2026-08-27", "2026-08-28")
    rate = ({"tenor": "7d"},)
    volume = ({"measure": "volume"},)
    read = Lookback(
        (
            Reading("CN_DR007", "level", Periods.sessions(1), members=rate, every_day=True),
            Reading("CN_DR007", "turnover", Periods.sessions(1), members=volume),
        )
    )

    assert read.required("CN_DR007", "2026-08-28", sessions=sessions, whole_window=True) == {
        "2026-08-26": rate,
        "2026-08-27": rate,
        "2026-08-28": (*rate, *volume),
    }


def test_a_member_beyond_the_catalogs_is_named_beside_every_member_it_requires() -> None:
    # The series' own reading asks every member the catalog requires of the newest month;
    # a reading naming one the catalog does not require keeps it there (ticket 04). With
    # no member contract for a month, the members named are what is checked.
    growth = ({"measure": "stock_yoy"},)
    catalog = ({"measure": "ytd_increment"}, {"measure": "stock_end"})
    read = Lookback(
        (
            own_reading("CN_SF_TOTAL", "monthly"),
            Reading("CN_SF_TOTAL", "growth", Periods.consecutive(2), members=growth),
            Reading("CN_SF_TOTAL", "stock", Periods.consecutive(1), members=catalog[1:]),
        )
    )

    assert read.required("CN_SF_TOTAL", "2026-07", catalog_members=lambda _: catalog) == {
        "2026-06": growth,
        "2026-07": (*catalog, *growth),
    }
    assert read.required("CN_SF_TOTAL", "2026-07", catalog_members=lambda _: None) == {
        "2026-06": growth,
        "2026-07": (*growth, *catalog[1:]),
    }
    # Members the catalog requires anyway leave the month read whole, as before.
    plain = Lookback(
        (
            own_reading("CN_SF_TOTAL", "monthly"),
            Reading("CN_SF_TOTAL", "stock", Periods.consecutive(1), members=catalog[1:]),
        )
    )
    assert plain.required("CN_SF_TOTAL", "2026-07", catalog_members=lambda _: catalog) == {
        "2026-07": None
    }
    assert plain.required("CN_SF_TOTAL", "2026-07") == {"2026-07": None}


def test_a_reading_declared_twice_for_a_metric_is_refused() -> None:
    # Its periods would no longer be told apart by members.
    with pytest.raises(ValueError, match="lookback_reading_declared_twice"):
        _resolve(
            Reading("CN_GDP", "level", Periods.quarters(1), every_day=True),
            Reading("CN_GDP", "level", Periods.quarters(4), every_day=True),
        )


def test_a_daily_reading_of_many_sessions_is_covered_back_from_each_day_on_the_calendar() -> None:
    # Counted on the SSE calendar from the window's first day (2026-04-06): its holidays
    # are no sessions. A reading of the newest two keeps to the fetch's fixed lead.
    holidays = {date(2026, 1, 1), date(2026, 2, 17), date(2026, 2, 18)}
    stated = TradingCalendar(
        day
        for day in (date(2025, 9, 1) + timedelta(days=offset) for offset in range(400))
        if day.weekday() < 5 and day not in holidays
    )
    window = _window_to(date(2026, 6, 30))
    read = resolve(
        (
            Reading("CN_DR007", "range", Periods.sessions(100)),
            own_reading("CN_SHIBOR_ON_1W_3M", "daily"),
        ),
        formula_versions={},
        window=window,
        public_cutoff=datetime.combine(window[-1], time.max, tzinfo=ZoneInfo("Asia/Shanghai")),
        calendar=stated,
    )

    covered = read.coverage.periods["CN_DR007"]
    first = stated.sessions_back(window[0], 100)[0]
    assert covered[0] == first.isoformat() and covered[-1] == "2026-06-30"
    assert not {day.isoformat() for day in holidays} & set(covered)
    assert "CN_SHIBOR_ON_1W_3M" not in read.coverage.periods


def test_a_daily_reading_beyond_the_calendar_starts_a_holiday_margin_before_its_weekdays() -> None:
    read = _resolve(Reading("CN_DR007", "range", Periods.sessions(250)))

    # 249 weekdays before 2026-04-06 (2025-04-22), then 7 days and one for each 15 more.
    assert read.coverage.periods["CN_DR007"][0] == "2025-03-30"


def test_a_daily_reading_of_many_sessions_every_day_is_refused() -> None:
    # The plan would require each day's own sessions: not one it reads that way.
    with pytest.raises(ValueError, match="lookback_sessions_beyond_daily_lead"):
        _resolve(
            Reading(
                "CN_DR007",
                "range",
                Periods.sessions(250),
                required=Periods.sessions(2),
                every_day=True,
            )
        )


def test_a_plan_counts_a_daily_reading_s_sessions_past_the_window() -> None:
    window = tuple(f"2026-08-{day:02d}" for day in (24, 25, 26, 27, 28))
    history = ("2026-08-18", "2026-08-19", "2026-08-20", "2026-08-21", *window)
    read = Lookback(
        (
            own_reading("CN_DR007", "daily", every_session=True),
            Reading("CN_DR007", "range", Periods.sessions(7)),
        )
    )

    required = read.required(
        "CN_DR007", "2026-08-28", sessions=history, window=window, whole_window=True
    )

    assert list(required) == [*history[-7:]]
    # Sessions the calendar does not state are not named.
    assert list(read.required("CN_DR007", "2026-08-28", sessions=window, whole_window=True)) == [
        *window
    ]
    # Counted from the target day, whatever event was held last: the rate in force on the
    # session before a window of five, though the newest rate held is of 25 August.
    baseline = Lookback(
        (Reading("CN_OMO_7D_RATE", "baseline", Periods.explicit(5, unit="session")),)
    )
    assert list(
        baseline.required("CN_OMO_7D_RATE", "2026-08-25", sessions=history, window=window)
    ) == ["2026-08-21"]


def test_a_reading_read_on_the_target_day_alone_takes_its_set_at_the_anchor() -> None:
    read = Lookback(
        (
            own_reading("CN_LOAN_STRUCTURE", "monthly"),
            Reading("CN_LOAN_STRUCTURE", "yoy_flow", Periods.explicit(0, 1, 12, 13)),
        )
    )

    assert list(read.required("CN_LOAN_STRUCTURE", "2026-07")) == [
        "2025-06",
        "2025-07",
        "2026-06",
        "2026-07",
    ]


def test_members_a_reading_names_are_all_its_periods_ask_for() -> None:
    nominal = ({"aggregate": "total", "measure": "nominal_ytd_level"},)
    read = Lookback(
        (
            own_reading("CN_GDP", "quarterly"),
            Reading("CN_GDP", "level", Periods.quarters(4), members=nominal),
        )
    )

    required = read.required("CN_GDP", "2026-Q2")

    # The quarter the series' own reading needs asks for every member; the older ones
    # only for the nominal level.
    assert required == {
        "2025-Q3": nominal,
        "2025-Q4": nominal,
        "2026-Q1": nominal,
        "2026-Q2": None,
    }


class _RecordedFetch:
    """The TuShare context adapter, answering nothing: each family's request parameters."""

    def __init__(self) -> None:
        self.requests: dict[str, dict[str, str]] = {}

    def __getattr__(self, name: str) -> Any:
        def request(**parameters: Any) -> tuple[()]:
            self.requests[name] = {
                key: str(value) for key, value in parameters.items() if key != "held_levels"
            }
            return ()

        return request

    def acquire_scalars(self, paths: Any, retrieve: Any, *, details: Any, **_: Any) -> None:
        # Breadth asks the exchange calendar first; its range is the window, not a lookback.
        if details["family"] != "market_breadth":
            retrieve()


def _run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, model_id: str) -> tuple[Any, Any]:
    """The run's first plan and the direct fetch's requests, for 2026-08-28."""
    manifest = {"model-v0014": model_v0014_manifest, "model-v0015": model_v0015_manifest}
    plan, requests = _full_run(
        tmp_path, monkeypatch, manifest[model_id]() if model_id in manifest else None
    )
    return plan["initial"], requests


def _full_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    manifest: dict[str, Any] | None,
    hold: Callable[[RuntimePaths], None] | None = None,
) -> tuple[Any, Any]:
    """A full run for 2026-08-28 under ``manifest`` (v0001 without one), after ``hold``.

    Its whole plan, and the direct fetch's requests.
    """
    model_id = str(manifest["model_version_id"]) if manifest is not None else "model-v0001"
    fetch = _RecordedFetch()
    refresh = worker.refresh_context_sources

    def recorded(*args: Any, **kwargs: Any) -> None:
        with monkeypatch.context() as patch:
            patch.setattr(worker, "parse_data_source_secrets", lambda _: {"TUSHARE_TOKEN": "x"})
            patch.setattr(worker, "_context_adapter", lambda _: fetch)
            refresh(*args, **kwargs)

    monkeypatch.setattr(worker, "refresh_context_sources", recorded)
    paths, runs = prepare(tmp_path)
    seed_core_history(paths)
    if manifest is not None:
        models = ModelRepository(paths.database)
        models.register(manifest)
        models.activate(model_id, explicitly_approved=True)
    if hold is not None:
        hold(paths)
    run = runs.submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id=f"lookback-{model_id}",
        model_version_id=model_id,
        system_as_of=datetime.now(UTC),
    )
    process_pending_run(paths, report_adapters=())
    return runs.full_retrieval_plan(run.run_id), fetch.requests


def _periods(plan: dict[str, Any]) -> dict[str, list[str]]:
    periods: dict[str, list[str]] = {}
    for requirement in plan["requirements"]:
        if "period" in requirement:
            periods.setdefault(requirement["metric_id"], []).append(requirement["period"])
    return {metric_id: sorted(values) for metric_id, values in periods.items()}


def _span(periods: list[str]) -> tuple[str, str, int]:
    return periods[0], periods[-1], len(periods)


@pytest.mark.parametrize(
    ("model_id", "expected"),
    [
        # The two-year impulse: 24 months and 8 quarters to the target day, back to what
        # the window's first day (2026-03-16) read; loans are a daily series of v0001.
        (
            "model-v0001",
            {
                "CN_SF_TOTAL": ("2024-03", "2026-07", 29),
                "CN_GDP": ("2024-Q1", "2026-Q2", 10),
                "CN_LOAN_STRUCTURE": ("2026-03-16", "2026-08-28", 120),
                "derived": {"CN_CREDIT_IMPULSE": {"CN_SF_TOTAL": 24, "CN_GDP": 8}},
                "fetch": {
                    "social_financing": "202403",
                    "gdp": "2024Q1",
                    "prices": "202601",
                    "pmi": "202601",
                    "money": "202601",
                },
            },
        ),
        # The twelve-month impulse: 13 months and 4 quarters plus each base period; the
        # loan change reads two months.
        (
            "model-v0014",
            {
                "CN_SF_TOTAL": ("2025-01", "2026-07", 19),
                "CN_GDP": ("2025-Q1", "2026-Q2", 6),
                "CN_LOAN_STRUCTURE": ("2026-06", "2026-07", 2),
                "derived": {
                    "CN_CREDIT_IMPULSE": {"CN_SF_TOTAL": 14, "CN_GDP": 5},
                    "CN_LOAN_STRUCTURE": {"CN_LOAN_STRUCTURE": 2},
                    "CN_DR007_POLICY_SPREAD": {"CN_DR007": 1, "CN_OMO_7D_RATE": 1},
                    "CN_REAL_FINISHED_GOODS_INVENTORY_PROXY": {
                        "CN_FINISHED_GOODS_INVENTORY": 1,
                        "CN_PPI": 1,
                    },
                },
                "fetch": {
                    "social_financing_total": "202501",
                    "gdp": "2025Q1",
                    "prices": "202601",
                    "pmi": "202601",
                    "money": "202601",
                },
            },
        ),
    ],
)
def test_an_existing_model_plans_and_fetches_the_periods_it_did(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, model_id: str, expected: dict[str, Any]
) -> None:
    plan, requests = _run(tmp_path, monkeypatch, model_id)
    periods = _periods(plan)

    for metric_id in ("CN_SF_TOTAL", "CN_GDP", "CN_LOAN_STRUCTURE"):
        assert _span(periods[metric_id]) == expected[metric_id], metric_id
    # The others read their newest period alone: a month, a quarter, a day not out yet on
    # the target day, or every session of the window for a P0/P1 daily series.
    assert periods["CN_CPI_HEADLINE"] == ["2026-07"]
    assert periods["CN_PMI_ACTIVITY"] == ["2026-07"]
    assert periods["CN_CAPACITY_UTILIZATION"] == ["2026-Q2"]
    assert _span(periods["CN_DR007"]) == ("2026-03-16", "2026-08-28", 120)
    assert _span(periods["CN_EQUITY_CORE_000985"]) == ("2026-03-16", "2026-08-28", 120)
    derived = {
        item["metric_id"]: item["required_input_periods"] for item in plan["derived_requirements"]
    }
    for metric_id, counts in expected["derived"].items():
        assert derived[metric_id] == counts, metric_id
    impulse = next(
        item for item in plan["derived_requirements"] if item["metric_id"] == "CN_CREDIT_IMPULSE"
    )
    assert impulse["covered_input_periods"] == {
        "CN_SF_TOTAL": list(expected["CN_SF_TOTAL"][:2]),
        "CN_GDP": list(expected["CN_GDP"][:2]),
    }
    # The fetch starts each family before the window's first day; daily ones two weeks.
    starts = {
        family: parameters.get("start_month") or parameters.get("start_quarter")
        for family, parameters in requests.items()
        if family in expected["fetch"]
    }
    assert starts == expected["fetch"]
    assert requests["market_indices"]["start_date"] == "2026-03-02"
    assert requests["gdp"]["end_quarter"] == "2026Q3"
    assert requests["prices"]["end_month"] == "202608"
    if model_id == "model-v0014":
        _assert_the_fetch_covers_the_plan(periods, requests)
        # The impulse's quarters are the farthest any reading takes.
        assert periods["CN_GDP"][0].replace("-", "") == requests["gdp"]["start_quarter"]


def test_a_confirmation_model_plans_the_months_each_member_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Each key indicator's main member reads what its readings need (ADR-0037): the PMIs'
    # slope three months, the others' place in a year twelve; an auxiliary member three,
    # a flow derived from year-to-date totals its month and a year before. The main
    # members, and those a turn hint reads, read the two months before too, as grace reads
    # each month as it stood (ticket 05): five months, fourteen back to t-13. The other
    # series still read their newest period alone, and the fetch covers them all.
    plan, requests = _run(tmp_path, monkeypatch, "model-v0015")
    periods = _periods(plan)
    members = _members(plan)
    year = [f"{2025 + (5 + i) // 12}-{(5 + i) % 12 + 1:02d}" for i in range(14)]
    five = ["2026-03", "2026-04", "2026-05", "2026-06", "2026-07"]
    three = five[2:]

    assert year[0] == "2025-06" and year[-1] == "2026-07"
    assert periods["CN_PMI_ACTIVITY"] == five
    assert periods["CN_PMI_PRICES"] == five
    assert periods["CN_PMI_INVENTORY"] == ["2026-07"]
    assert periods["CN_CPI_HEADLINE"] == periods["CN_PPI"] == periods["CN_M1_M2"] == year
    assert periods["CN_CORE_CPI"] == three
    # PPI's month-on-month is read back for grace: stage II's hint reads it (F4).
    mom = member_keys("CN_PPI", ({"category": "headline", "measure": "mom"},))[0]
    assert mom in members["CN_PPI"]["2026-03"] and mom not in members["CN_PPI"]["2026-02"]
    pmi = member_keys(
        "CN_PMI_ACTIVITY",
        tuple(
            {"measure": "level", "series": series}
            for series in ("manufacturing", "new_orders", "production", "purchase_volume")
        ),
    )
    # The newest month is read whole by the series' own reading; the two before, for the
    # members the confirmation names.
    assert members["CN_PMI_ACTIVITY"]["2026-07"] is None
    assert sorted(members["CN_PMI_ACTIVITY"]["2026-05"]) == sorted(pmi)
    m1 = member_keys("CN_M1_M2", ({"aggregate": "m1", "measure": "yoy"},))
    m2 = member_keys("CN_M1_M2", ({"aggregate": "m2", "measure": "yoy"},))
    assert members["CN_M1_M2"]["2025-08"] == list(m1)
    assert sorted(members["CN_M1_M2"]["2026-06"]) == sorted(m1 + m2)
    # Industrial value added has no January; its February is the cumulative growth.
    assert periods["CN_INDUSTRIAL_VA"] == [month for month in year if month != "2026-01"]
    assert members["CN_INDUSTRIAL_VA"]["2026-02"] == list(
        member_keys("CN_INDUSTRIAL_VA", ({"measure": "ytd_real_yoy"},))
    )
    assert members["CN_INDUSTRIAL_VA"]["2026-03"] == list(
        member_keys("CN_INDUSTRIAL_VA", ({"measure": "current_month_real_yoy"},))
    )
    # Social financing's official stock growth is required beside what the catalog
    # requires, not lost where the series' own reading and the impulse read the month.
    stock_yoy = member_keys("CN_SF_TOTAL", ({"measure": "stock_yoy"},))[0]
    for month in year:
        assert stock_yoy in members["CN_SF_TOTAL"][month], month
    assert {
        member_keys("CN_SF_TOTAL", ({"measure": measure},))[0]
        for measure in ("ytd_increment", "stock_end")
    } <= set(members["CN_SF_TOTAL"]["2026-07"])
    # Government bonds and the seven other components, each by its official growth.
    components = member_keys(
        "CN_SF_COMPONENTS",
        tuple(
            {"component": component, "measure": "stock_yoy"}
            for component in (
                "government_bonds",
                "renminbi_loans",
                "foreign_currency_loans_rmb",
                "entrusted_loans",
                "trust_loans",
                "undiscounted_bank_acceptances",
                "corporate_bonds",
                "nonfinancial_enterprise_equity",
            )
        ),
    )
    assert periods["CN_SF_COMPONENTS"] == three
    assert sorted(members["CN_SF_COMPONENTS"]["2026-05"]) == sorted(components)
    # Loans: July's flow and July's a year before, from their totals and the months
    # before them, t-13 the farthest (ticket 07); the v0014 loan change reads two months.
    assert periods["CN_LOAN_STRUCTURE"] == ["2025-06", "2025-07", "2026-06", "2026-07"]
    pairs = (
        ("enterprise", "long_term"),
        ("household", "total"),
        ("household", "short_term"),
        ("household", "long_term"),
        ("enterprise", "total"),
        ("enterprise", "short_term"),
        ("enterprise", "bill_financing"),
        ("nonbank_financial", "total"),
        ("all_rmb_loans", "total"),
    )
    loans = member_keys(
        "CN_LOAN_STRUCTURE",
        tuple(
            {"borrower": borrower, "tenor": tenor, "measure": "ytd_increment"}
            for borrower, tenor in pairs
        ),
    )
    assert sorted(members["CN_LOAN_STRUCTURE"]["2025-06"]) == sorted(loans)
    # GDP and capacity utilisation: four quarters to the second of 2026 and the one before.
    quarters = ["2025-Q2", "2025-Q3", "2025-Q4", "2026-Q1", "2026-Q2"]
    assert periods["CN_CAPACITY_UTILIZATION"] == quarters
    assert sorted(members["CN_CAPACITY_UTILIZATION"]["2025-Q2"]) == sorted(
        member_keys(
            "CN_CAPACITY_UTILIZATION",
            tuple(
                {"industry": "all_industry", "measure": measure}
                for measure in ("quarter_rate", "yoy_change")
            ),
        )
    )
    assert set(quarters) <= set(periods["CN_GDP"])
    real = member_keys("CN_GDP", ({"aggregate": "total", "measure": "real_quarter_yoy"},))[0]
    assert all(
        members["CN_GDP"][quarter] is None or real in members["CN_GDP"][quarter]
        for quarter in quarters
    )
    # Industrial profits: July, out on the 27th, and the four months before it.
    assert periods["CN_INDUSTRIAL_FINANCE"] == five
    # The fetch reads the five quarters back from the window's first day's newest, the
    # fourth of 2025: no further.
    assert requests["gdp"]["start_quarter"] == "2024Q4"
    _assert_the_fetch_covers_the_plan(periods, requests)


def test_the_policy_readings_declare_their_windows_baselines_and_lead() -> None:
    from pring_cycle.context_projection import ContextProjectionRules
    from pring_cycle.lookback import declare

    readings = {
        item.reading: item
        for item in declare(ContextProjectionRules.from_manifest(model_v0015_manifest()))
        if item.reading.startswith("confirmation:")
        and item.reading.split(":")[1] in {"policy_rate", "lpr", "rrr", "liquidity", "dr007"}
    }

    assert {
        name: (item.metric_id, item.periods, item.members) for name, item in readings.items()
    } == {
        # The rate in force on the session before the 120-session window, and the
        # operation notice of that session and of each in the window.
        "confirmation:policy_rate": (
            "CN_OMO_7D_RATE",
            Periods.explicit(120, unit="session"),
            None,
        ),
        "confirmation:policy_rate:notices": (
            "CN_OMO_7D_AMOUNT",
            Periods.sessions(121),
            ({"measure": "injection"},),
        ),
        # The window's months and the fixing before them.
        "confirmation:lpr": ("CN_LPR_1Y_5Y", Periods.consecutive(8), ({"tenor": "1y"},)),
        "confirmation:lpr:5y_plus": (
            "CN_LPR_1Y_5Y",
            Periods.consecutive(8),
            ({"tenor": "5y_plus"},),
        ),
        # Fourteen five-session periods and the ten sessions before them, whose
        # injections mature in the first.
        "confirmation:liquidity": (
            "CN_OMO_7D_AMOUNT",
            Periods.sessions(80),
            ({"measure": "injection"},),
        ),
        "confirmation:liquidity:short_term_reverse_repo": (
            "CN_TOOL_LIQUIDITY_MONTHLY",
            Periods.consecutive(3),
            ({"tool": "短期逆回购", "measure": "net_injection"},),
        ),
        "confirmation:dr007": ("CN_DR007", Periods.sessions(260), None),
        "confirmation:dr007:shibor_1w": (
            "CN_SHIBOR_ON_1W_3M",
            Periods.sessions(15),
            ({"tenor": "1w"},),
        ),
    }


def test_loans_declare_t_13_and_the_quarterly_indicators_their_quarters() -> None:
    # Loans: each pair's totals at t, t-1, t-12 and t-13, nothing further (ADR-0035). GDP
    # and capacity utilisation: four quarters and the one before them, the quarter grace
    # reads back reading its own year; capacity's official change on a year before at the
    # same quarters. Industrial profits: three months and two for grace (ticket 07).
    from pring_cycle.context_projection import ContextProjectionRules
    from pring_cycle.lookback import declare

    readings = {
        item.reading: item
        for item in declare(ContextProjectionRules.from_manifest(model_v0015_manifest()))
        if item.reading.split(":")[0] == "confirmation"
        and item.reading.split(":")[1]
        in {"loans", "gdp", "capacity_utilization", "industrial_profit"}
    }

    def loan(borrower: str, tenor: str) -> dict[str, str]:
        return {"borrower": borrower, "tenor": tenor, "measure": "ytd_increment"}

    endpoints = Periods.explicit(0, 1, 12, 13)
    assert (
        readings["confirmation:loans:ytd"].periods,
        readings["confirmation:loans:ytd"].members,
    ) == (
        endpoints,
        (loan("enterprise", "long_term"),),
    )
    household = readings["confirmation:loans:household_total:ytd"]
    assert (household.metric_id, household.periods, household.members) == (
        "CN_LOAN_STRUCTURE",
        endpoints,
        (loan("household", "total"),),
    )
    assert sum(1 for name in readings if name.startswith("confirmation:loans")) == 9
    assert {
        name: (item.metric_id, item.periods, item.members)
        for name, item in readings.items()
        if not name.startswith("confirmation:loans")
    } == {
        "confirmation:gdp": (
            "CN_GDP",
            Periods.quarters(5),
            ({"aggregate": "total", "measure": "real_quarter_yoy"},),
        ),
        "confirmation:gdp:nominal_ytd_level": (
            "CN_GDP",
            Periods.quarters(3),
            ({"aggregate": "total", "measure": "nominal_ytd_level"},),
        ),
        "confirmation:capacity_utilization": (
            "CN_CAPACITY_UTILIZATION",
            Periods.quarters(5),
            ({"industry": "all_industry", "measure": "quarter_rate"},),
        ),
        "confirmation:capacity_utilization:change": (
            "CN_CAPACITY_UTILIZATION",
            Periods.quarters(5),
            ({"industry": "all_industry", "measure": "yoy_change"},),
        ),
        "confirmation:industrial_profit": (
            "CN_INDUSTRIAL_FINANCE",
            Periods.consecutive(5),
            ({"item": "profit", "measure": "official_yoy"},),
        ),
        "confirmation:industrial_profit:revenue": (
            "CN_INDUSTRIAL_FINANCE",
            Periods.consecutive(3),
            ({"item": "revenue", "measure": "official_yoy"},),
        ),
        "confirmation:industrial_profit:cost": (
            "CN_INDUSTRIAL_FINANCE",
            Periods.consecutive(3),
            ({"item": "cost", "measure": "official_yoy"},),
        ),
    }
    assert readings["confirmation:industrial_profit"].unreleased_months == frozenset({1})


def test_a_policy_model_counts_its_sessions_and_months_past_the_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The SSE calendar states 400 sessions to the target day. DR007 reads a year of
    # five-session periods and the two grace reads back before them: 260 sessions to the
    # target day, and back from the window's first day for the fetch. The policy rate
    # reads each session's notice in the window and the one before it for the rate in
    # force there, the LPR the window's months and the fixing before them (macro
    # semantics ticket 06).
    days = [
        day
        for day in (date(2026, 8, 28) - timedelta(days=offset) for offset in range(560))
        if day.weekday() < 5
    ][:400][::-1]
    plan, requests = _full_run(
        tmp_path,
        monkeypatch,
        model_v0015_manifest(),
        lambda paths: record_sse_calendar(paths, days),
    )
    periods = _periods(plan["initial"])
    members = _members(plan["initial"])
    sessions = [day.isoformat() for day in days]

    assert periods["CN_DR007"] == sessions[-260:]
    # A session before the window is read for DR007 alone, its one member.
    assert members["CN_DR007"][sessions[-121]] is None
    assert sessions[-121] in periods["CN_OMO_7D_RATE"]
    assert periods["CN_LPR_1Y_5Y"] == [f"2026-{month:02d}" for month in range(1, 9)]
    assert sorted(members["CN_LPR_1Y_5Y"]["2026-03"]) == sorted(
        member_keys("CN_LPR_1Y_5Y", ({"tenor": "1y"}, {"tenor": "5y_plus"}))
    )
    # The notices from the session before the window: the policy rate's history; net
    # injection's periods and the lead before them lie in the window.
    assert periods["CN_OMO_7D_AMOUNT"] == sessions[-121:]
    assert requests["transmission"]["start_date"] == sessions[-120 - 259]


def _members(plan: dict[str, Any]) -> dict[str, dict[str, list[str] | None]]:
    """The members each requirement names, by metric and period: None for every one."""
    members: dict[str, dict[str, list[str] | None]] = {}
    for requirement in plan["requirements"]:
        if "period" in requirement:
            members.setdefault(requirement["metric_id"], {})[requirement["period"]] = (
                requirement.get("members")
            )
    return members


def _manufacturing_pmi(payload: dict[str, Any]) -> bytes:
    """TuShare's PMI for May and July with the manufacturing index alone."""
    fields = str(payload["fields"]).split(",")
    values = {"202605": 49.5, "202607": 49.3}
    return json.dumps(
        {
            "code": 0,
            "data": {
                "fields": fields,
                "items": [
                    [
                        month if field == "month" else value if field == "pmi010000" else None
                        for field in fields
                    ]
                    for month, value in values.items()
                ],
            },
        }
    ).encode()


def _manufacturing_pmi_in_may(payload: dict[str, Any]) -> bytes:
    """TuShare's PMI for May alone, the manufacturing index alone."""
    fields = str(payload["fields"]).split(",")
    item = [
        "202605" if field == "month" else 49.5 if field == "pmi010000" else None for field in fields
    ]
    return json.dumps({"code": 0, "data": {"fields": fields, "items": [item]}}).encode()


@pytest.mark.usefixtures("runtime_clock")
def test_the_plan_reads_back_from_the_newest_month_due_not_an_older_one_held(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Only May's PMI held, July out and due by the release calendar on 2026-08-28: the
    # plan reads back from July, so June and July are asked for, not left out because
    # May is the newest held (ticket 05).
    manifest = model_v0015_manifest()

    def hold(paths: RuntimePaths) -> None:
        adapter = TushareContextAdapter("fixture-only", transport=_manufacturing_pmi_in_may)
        adapter.acquire_scalars(
            paths,
            lambda: adapter.pmi(start_month="202605", end_month="202605"),
            definition_version=str(manifest["metric_catalog_version"]),
        )

    plan, _requests = _full_run(tmp_path, monkeypatch, manifest, hold)

    periods = _periods(plan["initial"])
    assert periods["CN_PMI_ACTIVITY"] == ["2026-03", "2026-04", "2026-05", "2026-06", "2026-07"]
    asked = {
        document["period"]
        for document in plan["initial"]["scopes"]
        if "CN_PMI_ACTIVITY" in document["metric_ids"]
    }
    assert {"2026-06", "2026-07"} <= asked
    # A series read as itself alone is asked for its newest month due, too.
    assert _periods(plan["initial"])["CN_PMI_INVENTORY"] == ["2026-07"]


@pytest.mark.usefixtures("runtime_clock")
def test_the_members_a_reading_names_carry_from_the_plan_to_the_final_evaluation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A confirmation of the PMI alone naming its main member alone (ticket 02's members,
    # ticket 03's reading). May, holding that member only, is complete; June is planned
    # for it alone, its scope stored and restored with the member, and the final
    # evaluation finds that member missing, not the others. July, read whole by the
    # series' own reading, still lacks the members it does not hold.
    manifest = model_v0015_manifest()
    manifest["model_version_id"] = "model-v0015-main-member"
    pmi = manifest["confirmation_rules"]["key_indicators"][0]
    manifest["confirmation_rules"]["key_indicators"] = [pmi]
    pmi["auxiliary"] = []
    # Nor any note told of the members left out.
    pmi["expectations"]["stage_ii"]["cells"][1].pop("note")
    pmi["expectations"]["stage_vi"].pop("notes")

    def hold(paths: RuntimePaths) -> None:
        adapter = TushareContextAdapter("fixture-only", transport=_manufacturing_pmi)
        adapter.acquire_scalars(
            paths,
            lambda: adapter.pmi(start_month="202605", end_month="202607"),
            definition_version=str(manifest["metric_catalog_version"]),
        )

    plan, _requests = _full_run(tmp_path, monkeypatch, manifest, hold)

    named = list(member_keys("CN_PMI_ACTIVITY", ({"measure": "level", "series": "manufacturing"},)))
    june = next(
        document
        for document in plan["initial"]["scopes"]
        if document["metric_ids"] == ["CN_PMI_ACTIVITY"] and document["period"] == "2026-06"
    )
    assert not any(
        document["period"] == "2026-05" and "CN_PMI_ACTIVITY" in document["metric_ids"]
        for document in plan["initial"]["scopes"]
    )
    restored = full_retrieval._scope(june)
    assert restored.members == tuple(named)
    # As stored again, the document it was restored from.
    assert json.loads(json.dumps(restored.document())) == {
        key: value for key, value in june.items() if key != "release_status"
    }
    gaps = {
        gap["period"]: gap for gap in plan["final"]["gaps"] if gap["metric_id"] == "CN_PMI_ACTIVITY"
    }
    assert gaps["2026-05"]["complete"] is True
    assert gaps["2026-05"]["missing_members"] == []
    assert len(gaps["2026-05"]["selected_claim_ids"]) == 1
    assert gaps["2026-06"]["complete"] is False
    assert gaps["2026-06"]["missing_members"] == named
    assert gaps["2026-07"]["complete"] is False
    assert len(gaps["2026-07"]["missing_members"]) == 3
    final = {
        requirement["period"]: requirement.get("members")
        for requirement in plan["final"]["requirements"]
        if requirement["metric_id"] == "CN_PMI_ACTIVITY"
    }
    # March and April too, for grace (ticket 05).
    assert final == {
        "2026-03": named,
        "2026-04": named,
        "2026-05": named,
        "2026-06": named,
        "2026-07": None,
    }


def _assert_the_fetch_covers_the_plan(
    periods: dict[str, list[str]], requests: dict[str, dict[str, str]]
) -> None:
    """Both read one declaration: every period the plan requires of a fetched series lies in
    the fetch's range, the impulse's months start where the fetch starts, and its quarters
    start no earlier.

    Not of v0001, whose catalog declares the monthly series daily.
    """
    families = {
        "social_financing_total": ("CN_SF_TOTAL",),
        "gdp": ("CN_GDP",),
        "prices": ("CN_CPI_HEADLINE", "CN_PPI"),
        "pmi": ("CN_PMI_ACTIVITY", "CN_PMI_INVENTORY", "CN_PMI_PRICES"),
        "money": ("CN_M1_M2",),
    }
    for family, metric_ids in families.items():
        parameters = requests[family]
        start = parameters.get("start_month") or parameters["start_quarter"]
        end = parameters.get("end_month") or parameters["end_quarter"]
        for metric_id in metric_ids:
            for period in periods.get(metric_id, ()):
                assert start <= period.replace("-", "") <= end, (metric_id, period)
    assert (
        periods["CN_SF_TOTAL"][0].replace("-", "")
        == requests["social_financing_total"]["start_month"]
    )
    # A key indicator's quarters may reach before the impulse's: the fetch covers the five
    # quarters each day of the window reads, the plan the target day's (ticket 07).
    assert requests["gdp"]["start_quarter"] <= periods["CN_GDP"][0].replace("-", "")


@pytest.mark.usefixtures("runtime_clock")
def test_a_scope_naming_members_is_complete_without_the_others(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # TuShare delivers GDP's nominal levels, not its real growth: complete for a reading of
    # the levels alone, still missing for one of every member.
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    candidate, version = admit_gdp_candidate(paths, capsys)
    adapter = TushareContextAdapter("fixture-only", transport=delivery)
    adapter.acquire_scalars(
        paths,
        lambda: adapter.gdp(start_quarter="2026Q2", end_quarter="2026Q2"),
        definition_version=version,
    )
    run = RunRepository(paths.database).submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id="named-members",
        model_version_id=candidate,
        system_as_of=datetime.now(UTC),
    )
    levels = tuple(
        {"aggregate": aggregate, "measure": "nominal_ytd_level"}
        for aggregate in ("primary", "secondary", "tertiary", "total")
    )
    named = RetrievalScope(
        "gdp-levels", ("CN_GDP",), "2026-Q2", "P2", None, member_keys("CN_GDP", levels)
    )
    selector = ModelInputSelector(paths, run)

    every = selector.select(RetrievalScope("gdp-all", ("CN_GDP",), "2026-Q2", "P2", None))
    levels_only = selector.select(named)

    assert not every.complete
    assert all("real_quarter_yoy" in member for member in every.missing_members)
    assert levels_only.complete
    assert levels_only.missing_members == ()
    assert set(levels_only.held_members) == set(member_keys("CN_GDP", levels))
    # Warrants are whole by each symbol, as their family decides: not narrowed.
    with pytest.raises(ValueError, match="retrieval_scope_members_decided_by_family"):
        selector.select(
            RetrievalScope(
                "warrants",
                ("CN_FUTURES_WARRANTS",),
                "2026-08-28",
                "P2",
                None,
                member_keys("CN_FUTURES_WARRANTS", ({"symbol": "CU"},)),
            )
        )
    # A plan stores the members it named, and a scope naming none as it always did.
    assert named.document()["members"] == member_keys("CN_GDP", levels)
    assert "members" not in RetrievalScope("gdp-all", ("CN_GDP",), "2026-Q2", "P2", None).document()
