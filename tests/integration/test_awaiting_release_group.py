"""Worker gaps ticket 03: a period its release has not reached is awaiting release, not missing.

EIA publishes its daily spot prices in weekly batches. The run for 10-15 frozen at 16:08 on
10-16 (Beijing) read pages released 10-15, the newest value 10-14, the next release 10-21
(the 10-15 originals of the real run). The 10-15 session is not owed yet: the gap list
groups it apart from what is missing, with the release date the page states, and the
coverage counts do not take it for a missing period.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.models import ModelRepository, effective_model_manifest
from pring_cycle.projections import ProjectionSetRepository
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.worker import process_pending_run
from tests.conftest import OfficialFile, install_runtime_clock
from tests.integration.test_core_history_refresh import historical_response

CURRENT_MODEL = str(effective_model_manifest()["model_version_id"])
EIA_PAGES = {
    "https://www.eia.gov/dnav/pet/hist/RBRTED.htm": "RBRTED_20261015.htm",
    "https://www.eia.gov/dnav/pet/hist/RWTCD.htm": "RWTCD_20261015.htm",
}


def serve_eia_pages_of_1015(monkeypatch: pytest.MonkeyPatch) -> None:
    fixtures = Path(__file__).resolve().parents[1] / "fixtures" / "eia"

    def open_page(request, *, timeout):
        name = EIA_PAGES.get(request.full_url)
        if name is None:
            raise OSError("official_page_offline_in_tests")
        page = OfficialFile(request.full_url, (fixtures / name).read_bytes())
        page.headers = {"Content-Type": "text/html"}  # type: ignore[attr-defined]
        return page

    monkeypatch.setattr("pring_cycle.eia_html.open_no_redirects", open_page)


def serve_cores_from_tushare(monkeypatch: pytest.MonkeyPatch, paths: RuntimePaths) -> None:
    """The three cores and the SSE calendar answer; every other TuShare call fails."""
    paths.secrets.write_text("TUSHARE_TOKEN=fixture-secret\n", encoding="utf-8")

    class FixtureOpener:
        def open(self, request: Any, *, timeout: int) -> BytesIO:
            payload = json.loads(request.data)
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


def test_eia_session_its_release_has_not_reached_is_awaiting_release(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    install_runtime_clock(monkeypatch, request, datetime(2026, 10, 16, 7, 52, tzinfo=UTC))
    serve_eia_pages_of_1015(monkeypatch)
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    models = ModelRepository(paths.database)
    models.register(effective_model_manifest())
    models.activate(CURRENT_MODEL, explicitly_approved=True)
    serve_cores_from_tushare(monkeypatch, paths)
    runs = RunRepository(paths.database)
    run = runs.submit_manual_full(
        target_business_date="2026-10-15",
        client_request_id="eia-awaiting-release",
        model_version_id=CURRENT_MODEL,
        system_as_of=datetime(2026, 10, 16, 8, 8, tzinfo=UTC),
        cutoff_mode="explicit",
    )

    process_pending_run(paths, report_adapters=())

    stored = runs.get(run.run_id)
    assert stored.status == "completed", stored.error_classification
    projection = ProjectionSetRepository(paths.database).current()
    listed = {
        str(gap["metric_id"]): gap for gap in projection.datasets["cycle_overview"]["gap_list"]
    }
    for metric_id in ("EIA_BRENT_RBRTE", "EIA_WTI_RWTC"):
        gap = listed[metric_id]
        assert gap["category"] == "awaiting_release", gap
        # The page's own next release, not the registered lag's estimate.
        assert gap["awaiting_release"] == [
            {
                "period": "2026-10-15",
                "next_release_date": "2026-10-21",
                "basis": "source_next_release_date",
            }
        ]
        assert "not_requested" not in gap
    # Not a missing period of either coverage measure: counted with the release gate.
    coverage = projection.datasets["macro"]["coverage"]["catalog"]
    awaiting = [
        row
        for row in coverage["periods"]
        if row["metric_id"] in {"EIA_BRENT_RBRTE", "EIA_WTI_RWTC"} and not row.get("complete")
    ]
    assert {row["release_gate"] for row in awaiting} == {"awaiting_release"}
    assert coverage["counts"]["release_gated"] >= len(awaiting) == 2
