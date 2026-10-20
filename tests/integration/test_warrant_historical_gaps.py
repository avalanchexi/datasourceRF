"""Historical warrant days the final plan could not complete are in the gap list.

Worker gaps 2026-10-17, ticket 04: the 10-15 run's final plan still lacked five symbols on
07-21 and polypropylene on 09-09, yet section 07 listed none of it, and coverage's "other
missing" named nothing a reader could find. One manual full run on the effective model with
offline doubles whose warrant deliveries skip three symbol-days.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from io import BytesIO
from typing import Any

import pytest

from pring_cycle.models import ModelRepository, effective_model_manifest
from pring_cycle.projections import ProjectionSet, ProjectionSetRepository
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.worker import process_pending_run
from tests.conftest import install_runtime_clock
from tests.fixtures.czce_report import czce_exchange
from tests.integration.test_gap_source_repairs import (
    CLOCK,
    TARGET,
    FixtureOpener,
    official_quote,
    warrant_response,
)

CURRENT_MODEL = str(effective_model_manifest()["model_version_id"])

# Symbol-days TuShare never delivers, however often asked.
SKIPPED = {("CU", "20260728"), ("RB", "20260728"), ("PP", "20260730")}


class SkippingWarrants(FixtureOpener):
    def open(self, request: Any, *, timeout: int) -> BytesIO:
        payload = json.loads(request.data)
        if payload["api_name"] != "fut_wsr":
            return super().open(request, timeout=timeout)
        answer = json.loads(warrant_response(payload))
        symbol = payload["params"]["symbol"]
        answer["data"]["items"] = [
            row for row in answer["data"]["items"] if (symbol, row[0]) not in SKIPPED
        ]
        return BytesIO(json.dumps(answer).encode())


@pytest.fixture(scope="module")
def published(
    tmp_path_factory: pytest.TempPathFactory, request: pytest.FixtureRequest
) -> Iterator[tuple[ProjectionSet, dict[str, Any]]]:
    with pytest.MonkeyPatch.context() as monkeypatch:
        install_runtime_clock(monkeypatch, request, CLOCK)
        monkeypatch.setattr(
            "pring_cycle.eia_html.open_no_redirects",
            lambda *args, **kwargs: (_ for _ in ()).throw(OSError("offline")),
        )
        monkeypatch.setattr("pring_cycle.quote_sources.open_no_redirects", official_quote)
        monkeypatch.setattr(
            "pring_cycle.czce_warrants._fetch", czce_exchange(lambda day: day.weekday() < 5)
        )
        paths = RuntimePaths.discover(tmp_path_factory.mktemp("warrant-history") / "runtime")
        initialize_runtime(paths)
        paths.secrets.write_text("TUSHARE_TOKEN=fixture-secret\n", encoding="utf-8")
        models = ModelRepository(paths.database)
        models.register(effective_model_manifest())
        models.activate(CURRENT_MODEL, explicitly_approved=True)
        monkeypatch.setattr("pring_cycle.source_adapters.build_opener", SkippingWarrants)
        monkeypatch.setattr(
            "pring_cycle.tushare_context.build_opener", lambda *handlers: SkippingWarrants()
        )
        runs = RunRepository(paths.database)
        run = runs.submit_manual_full(
            target_business_date=TARGET.isoformat(),
            client_request_id="warrant-historical-gaps",
            model_version_id=CURRENT_MODEL,
            system_as_of=datetime.now(UTC),
        )
        process_pending_run(paths, report_adapters=())
        projection = ProjectionSetRepository(paths.database).current()
        assert projection is not None
        yield projection, runs.full_retrieval_plan(run.run_id)["final"]


def test_historical_warrant_days_are_one_gap_with_each_period_and_its_symbols(
    published: tuple[ProjectionSet, dict[str, Any]],
) -> None:
    projection, _final = published

    (warrants,) = (
        gap
        for gap in projection.datasets["cycle_overview"]["gap_list"]
        if gap["metric_id"] == "CN_FUTURES_WARRANTS"
    )

    assert warrants["missing_periods"] == [
        {
            "period": "2026-07-28",
            "missing_members": [
                "CN_FUTURES_WARRANTS:symbol_missing:CU",
                "CN_FUTURES_WARRANTS:symbol_missing:RB",
            ],
        },
        {"period": "2026-07-30", "missing_members": ["CN_FUTURES_WARRANTS:symbol_missing:PP"]},
    ]


def test_every_other_missing_period_of_coverage_is_found_in_the_gap_list(
    published: tuple[ProjectionSet, dict[str, Any]],
) -> None:
    projection, final = published
    coverage = projection.datasets["macro"]["coverage"]["catalog"]
    listed = {
        str(gap["metric_id"]): gap for gap in projection.datasets["cycle_overview"]["gap_list"]
    }

    def found(row: dict[str, Any]) -> bool:
        gap = listed.get(str(row["metric_id"]))
        if gap is None:
            return False
        period = str(row["required_period"])
        held = str(gap.get("held_period") or "")
        return (
            any(item["period"] == period for item in gap.get("missing_periods", ()))
            or any(item["period"] == period for item in gap.get("not_covered", ()))
            # The metric's own timeliness row speaks for every period after the one it holds.
            or gap.get("due_period") is not None
            and held[: len(period)] < period
        )

    missing = [
        row
        for row in coverage["periods"]
        if not row.get("complete")
        and not row.get("release_gate")
        # Awaiting release, or out and not due yet: counted with the gated (macro stage 15).
        and not row.get("awaiting_release")
        and not row.get("not_due")
    ]
    assert len(missing) == coverage["counts"]["missing"]
    assert {(row["metric_id"], row["required_period"]) for row in missing} >= {
        ("CN_FUTURES_WARRANTS", "2026-07-28"),
        ("CN_FUTURES_WARRANTS", "2026-07-30"),
    }
    assert [row for row in missing if not found(row)] == []
    assert len(final["gaps"]) == coverage["total"]
