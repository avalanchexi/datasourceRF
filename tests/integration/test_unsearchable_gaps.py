"""Phase two #05: a gap no web page can fill is retried through TuShare, never searched."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.projections import ProjectionSetRepository
from pring_cycle.storage import database_connection
from pring_cycle.worker import process_pending_run
from tests.integration.test_full_run_retrieval import prepare, seed_core_history

LPR_URL = "https://www.chinamoney.com.cn/chinese/rdgz/20260820/3399885.html"


@pytest.mark.usefixtures("runtime_clock")
def test_unsearchable_gaps_are_not_searched_and_are_listed_apart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, runs = prepare(tmp_path)
    seed_core_history(paths)
    paths.secrets.write_text("TAVILY_API_KEY=fixture-secret\n")
    original = (Path(__file__).parents[1] / "fixtures/chinamoney_lpr_20260820.html").read_bytes()
    queries: list[str] = []

    class Response(BytesIO):
        status = 200
        headers = {"Content-Type": "text/html"}

        def geturl(self) -> str:
            return LPR_URL

    def search(request: Any, *, timeout: float) -> Response:
        query = json.loads(request.data)["query"]
        queries.append(query)
        found = [{"url": LPR_URL}] if "LPR" in query or "贷款市场报价利率" in query else []
        return Response(json.dumps({"results": found}).encode())

    monkeypatch.setattr("pring_cycle.search_discovery.urlopen", search)
    monkeypatch.setattr(
        "pring_cycle.official_lpr.urlopen", lambda request, *, timeout: Response(original)
    )
    run = runs.submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id="unsearchable",
        model_version_id="model-v0001",
        system_as_of=datetime.now(UTC),
    )

    process_pending_run(paths, report_adapters=())

    assert runs.get(run.run_id).status == "completed"
    with database_connection(paths.database) as connection:
        attempts = connection.execute(
            "SELECT release_event_id, channel, outcome, classification "
            "FROM run_retrieval_attempt WHERE run_id=? AND channel='tavily'",
            (run.run_id,),
        ).fetchall()
    dr007 = [row for row in attempts if row[0].startswith("full:cn_dr007:")]
    assert dr007
    assert {(row[2], row[3]) for row in dr007} == {("not_attempted", "no_searchable_source")}
    # A searchable gap is still searched and filled from the page it finds.
    assert any(
        row[0].startswith("full:chinamoney_lpr:") and row[2] != "not_attempted" for row in attempts
    )
    assert queries
    projection = ProjectionSetRepository(paths.database).current()
    gaps = {g["metric_id"]: g for g in projection.datasets["cycle_overview"]["gap_list"]}
    assert gaps["CN_DR007"]["category"] == "no_searchable_source"
    assert gaps["CN_SHIBOR_ON_1W_3M"]["category"] == "no_searchable_source"
    assert "CN_LPR_1Y_5Y" not in gaps
    from pring_cycle.dashboard import _home_page

    assert "无可检索来源" in str(_home_page(projection))
