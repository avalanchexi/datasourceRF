"""Phase two #08: one TuShare news pull per full run, read locally by each gap."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.acquisition import AcquisitionRepository
from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.full_retrieval import FullRunRetrieval
from pring_cycle.models import ModelRepository
from pring_cycle.retention import prune_to_window
from pring_cycle.runs import RunRecord, RunRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.storage import database_connection
from pring_cycle.tushare_news import pull_news
from tests.conftest import install_runtime_clock
from tests.fixtures.model_registration import prepared_request, save, submit
from tests.retrieval.test_news_rules import SAMPLE

# Two days after the 8/2026 CPI release: August is the due period.
NOW = datetime(2026, 9, 11, 2, tzinfo=UTC)


def news_response(items: list[dict[str, str]]) -> bytes:
    fields = ["title", "content", "pub_time", "src"]
    return json.dumps(
        {"code": 0, "data": {"fields": fields, "items": [[i[f] for f in fields] for i in items]}}
    ).encode()


class Opener:
    """TuShare over HTTP: major_news answers from ``answer``; every other API is offline."""

    def __init__(self, answer: Callable[[dict[str, Any]], bytes]) -> None:
        self.answer = answer
        self.news_requests: list[dict[str, str]] = []

    def open(self, request: Any, *, timeout: float) -> BytesIO:
        payload = json.loads(request.data)
        if payload["api_name"] != "major_news":
            raise OSError("fixture_tushare_offline")
        self.news_requests.append(payload["params"])
        return BytesIO(self.answer(payload))


def register_at(
    now: datetime,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
    capsys: pytest.CaptureFixture[str],
) -> tuple[RuntimePaths, str, str]:
    install_runtime_clock(monkeypatch, request, now)
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifest_request, _ = prepared_request(paths)
    submit(paths, save(paths, manifest_request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    ModelRepository(paths.database).activate(model_id, explicitly_approved=True)
    paths.secrets.write_text("TUSHARE_TOKEN=fixture-token\nTAVILY_API_KEY=fixture-secret\n")
    return paths, model_id, manifest_request["manifest"]["metric_catalog_version"]


@pytest.fixture
def registered(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
    capsys: pytest.CaptureFixture[str],
) -> tuple[RuntimePaths, str, str]:
    return register_at(NOW, tmp_path, monkeypatch, request, capsys)


def full_run(
    paths: RuntimePaths,
    model_id: str,
    monkeypatch: pytest.MonkeyPatch,
    answer: Callable[[dict[str, Any]], bytes],
    *,
    target: str = "2026-09-10",
    now: datetime = NOW,
) -> tuple[RunRecord, Opener, list[str]]:
    opener = Opener(answer)
    monkeypatch.setattr("pring_cycle.tushare_context.build_opener", lambda *handlers: opener)
    elsewhere: list[str] = []

    def official(url: str) -> Any:
        elsewhere.append(url)
        raise OSError("fixture_official_offline")

    class Empty(BytesIO):
        status = 200
        headers: dict[str, str] = {}

    def search(request: Any, **kwargs: Any) -> Empty:
        elsewhere.append(json.loads(request.data)["query"])
        return Empty(b'{"results":[]}')

    monkeypatch.setattr("pring_cycle.official_context._fetch_official_context_document", official)
    monkeypatch.setattr("pring_cycle.search_discovery.urlopen", search)
    runs = RunRepository(paths.database)
    submitted = runs.submit_manual_full(
        target_business_date=target,
        client_request_id="tushare-news",
        model_version_id=model_id,
        system_as_of=now,
    )
    run = runs.advance(submitted.run_id, "refreshing_evidence")
    FullRunRetrieval(paths).retrieve(run)
    return runs.get(run.run_id), opener, elsewhere


def release_day_news(_payload: dict[str, Any]) -> bytes:
    return news_response(json.loads(SAMPLE.read_text())["items"])


def cpi(paths: RuntimePaths, version: str) -> dict[str, float | None]:
    return {
        p.dimensions["measure"]: p.selected_value
        for p in EvidenceRepository(paths.database).metric_series(
            "CN_CPI_HEADLINE",
            mode=AsOfMode.SYSTEM,
            as_of=NOW + timedelta(days=1),
            definition_version=version,
        )
    }


def test_cpi_is_filled_from_the_news_and_later_channels_are_not_called(
    registered: tuple[RuntimePaths, str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, model_id, version = registered

    run, opener, _elsewhere = full_run(paths, model_id, monkeypatch, release_day_news)

    # A first run pulls three days, once for the whole run, up to the target day's end.
    assert opener.news_requests == [
        {"start_date": "2026-09-07 23:59:59", "end_date": "2026-09-10 23:59:59"}
    ]
    assert cpi(paths, version) == {"yoy": 0.8, "mom": 0.4, "cumulative_average_yoy": 0.9}
    with database_connection(paths.database) as connection:
        attempts = connection.execute(
            "SELECT channel, outcome FROM run_retrieval_attempt "
            "WHERE run_id=? AND release_event_id='full:nbs_core_cpi:2026-08' "
            "ORDER BY sequence",
            (run.run_id,),
        ).fetchall()
        quotes = connection.execute(
            "SELECT q.route, q.source_name, q.published_at, q.url FROM claim_matched_quote q "
            "JOIN source_claim c USING(claim_id) WHERE c.metric_id='CN_CPI_HEADLINE'"
        ).fetchall()
    # Headline CPI's cascade stops at the news. (Core CPI is a separate gap of the same
    # release, with its own official page, and the news states only its year-on-year.)
    hit = attempts.index(("tushare_news", "verified"))
    assert attempts[hit - 2 : hit] == [("local", "not_found"), ("tushare", "failed")]
    assert hit + 1 == len(attempts) or attempts[hit + 1][0] == "local"
    assert len(quotes) == 3
    assert {row[0] for row in quotes} == {"tushare_news"}
    assert {row[3] for row in quotes} == {None}
    # The earliest release-day item states the headline first: Xinhua at 09:39.
    assert {(row[1], row[2]) for row in quotes} == {("新华网", "2026-09-09T09:39:18+08:00")}


def test_a_failed_pull_is_recorded_and_the_run_carries_on(
    registered: tuple[RuntimePaths, str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, model_id, version = registered

    def unauthorized(_payload: dict[str, Any]) -> bytes:
        return json.dumps({"code": 40203, "msg": "抱歉，您没有访问该接口的权限"}).encode()

    run, _opener, _elsewhere = full_run(paths, model_id, monkeypatch, unauthorized)

    assert run.status == "running"
    pulls = [
        a
        for a in RunRepository(paths.database).full_retrieval_plan(run.run_id)["acquisitions"]
        if a["api_name"] == "major_news"
    ]
    assert [(a["phase"], a["state"]) for a in pulls] == [("tushare_news", "failed")]
    assert cpi(paths, version) == {}


def test_the_pull_pages_back_until_the_window_is_covered(
    registered: tuple[RuntimePaths, str, str],
) -> None:
    paths, model_id, _version = registered
    runs = RunRepository(paths.database)
    run = runs.submit_manual_full(
        target_business_date="2026-09-10",
        client_request_id="paging",
        model_version_id=model_id,
        system_as_of=NOW,
        cutoff_mode="explicit",
    )
    requests: list[dict[str, str]] = []

    def transport(payload: dict[str, Any]) -> bytes:
        requests.append(payload["params"])
        end = datetime.fromisoformat(payload["params"]["end_date"])
        count = 400 if len(requests) == 1 else 3
        return news_response(
            [
                {
                    "title": f"t{len(requests)}-{n}",
                    "content": "",
                    "pub_time": (end - timedelta(minutes=n)).strftime("%Y-%m-%d %H:%M:%S"),
                    "src": "财联社",
                }
                for n in range(count)
            ]
        )

    outcome = pull_news(paths, run, "fixture-token", end=NOW, transport=transport)

    assert outcome == "verified_candidate"
    assert [r["end_date"] for r in requests] == ["2026-09-11 10:00:00", "2026-09-11 03:21:00"]
    assert {r["start_date"] for r in requests} == {"2026-09-08 10:00:00"}


def test_originals_go_after_three_days_and_the_quotes_stay(
    registered: tuple[RuntimePaths, str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, model_id, version = registered
    full_run(paths, model_id, monkeypatch, release_day_news)
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    [news] = [r for r in acquisitions.history() if r.api_name == "major_news"]
    assert news.raw_hash is not None
    original = paths.artifacts / news.raw_hash[:2] / news.raw_hash

    prune_to_window(paths, now=NOW + timedelta(days=2))
    assert original.is_file()

    prune_to_window(paths, now=NOW + timedelta(days=4))

    assert not original.is_file()
    with database_connection(paths.database) as connection:
        # CPI's three members, the seven PPI members and core CPI's year-on-year.
        assert connection.execute("SELECT count(*) FROM claim_matched_quote").fetchone() == (11,)
    assert cpi(paths, version) == {"yoy": 0.8, "mom": 0.4, "cumulative_average_yoy": 0.9}


def sample_news(name: str) -> Callable[[dict[str, Any]], bytes]:
    items = json.loads((SAMPLE.parent / name).read_text())["items"]
    return lambda _payload: news_response(items)


def selected(paths: RuntimePaths, metric_id: str, version: str, now: datetime) -> dict[str, Any]:
    return {
        "-".join(sorted(p.dimensions.values())): p.selected_value
        for p in EvidenceRepository(paths.database).metric_series(
            metric_id,
            mode=AsOfMode.SYSTEM,
            as_of=now + timedelta(days=1),
            definition_version=version,
        )
    }


def test_pmi_is_filled_from_the_release_day_news(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Phase two #09: the day after August's PMI release."""
    now = datetime(2026, 9, 1, 4, tzinfo=UTC)
    paths, model_id, version = register_at(now, tmp_path, monkeypatch, request, capsys)

    full_run(
        paths,
        model_id,
        monkeypatch,
        sample_news("nbs_20260831_pmi.json"),
        target="2026-09-01",
        now=now,
    )

    assert selected(paths, "CN_PMI_PRICES", version, now) == {
        "level-output_prices": 50.4,
        "level-purchase_prices": 56.6,
    }
    assert selected(paths, "CN_PMI_ACTIVITY", version, now)["level-manufacturing"] == 49.8


def test_lpr_is_filled_from_the_fixing_day_news(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Phase two #10: September's LPR, fixed on Sunday the 20th, read on Monday."""
    now = datetime(2026, 9, 21, 4, tzinfo=UTC)
    paths, model_id, version = register_at(now, tmp_path, monkeypatch, request, capsys)

    run, _opener, _elsewhere = full_run(
        paths,
        model_id,
        monkeypatch,
        sample_news("pbc_20260920_lpr.json"),
        target="2026-09-21",
        now=now,
    )

    assert selected(paths, "CN_LPR_1Y_5Y", version, now) == {"1y": 3.0, "5y_plus": 3.5}
    with database_connection(paths.database) as connection:
        attempts = connection.execute(
            "SELECT channel, outcome FROM run_retrieval_attempt WHERE run_id=? "
            "AND release_event_id LIKE 'full:chinamoney_lpr:%' ORDER BY sequence",
            (run.run_id,),
        ).fetchall()
    assert attempts[-1] == ("tushare_news", "verified")
