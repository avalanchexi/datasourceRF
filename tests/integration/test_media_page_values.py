"""Phase two #07: a P1 gap filled from a whitelisted media page by the family's news rules."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.models import ModelRepository
from pring_cycle.runs import RunRecord, RunRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.storage import database_connection
from pring_cycle.worker import process_pending_run
from tests.fixtures.model_registration import prepared_request, save, submit
from tests.integration.test_retrieval_strict_path import Page
from tests.retrieval.test_news_rules import item

CLS = "https://www.cls.cn/detail/2140001"


def page(content: str, published: str = "2026-09-09T09:41:00+08:00") -> bytes:
    return (
        "<html><head><title>国家统计局：8月份CPI同比上涨0.8% PPI同比上涨3.8%</title>"
        f'<meta property="article:published_time" content="{published}"></head>'
        f"<body>{content}</body></html>"
    ).encode()


def media_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    *,
    body: bytes,
    metric_ids: tuple[str, ...] = ("CN_CPI_HEADLINE",),
    period: str = "2026-08",
    url: str = CLS,
) -> tuple[RunRecord, RuntimePaths, str, list[str]]:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    ModelRepository(paths.database).activate(model_id, explicitly_approved=True)
    paths.secrets.write_text("TAVILY_API_KEY=fixture-secret\n")
    calls: list[str] = []

    def search(request: Any, **kwargs: Any) -> Page:
        calls.append(request.full_url)
        return Page(json.dumps({"results": [{"url": url, "content": "8月CPI"}]}).encode(), url)

    def fetch(request: Any, **kwargs: Any) -> Page:
        calls.append(request.full_url)
        return Page(body, request.full_url)

    monkeypatch.setattr("pring_cycle.search_discovery.urlopen", search)
    monkeypatch.setattr("pring_cycle.http_transport.open_no_redirects", fetch)
    runs = RunRepository(paths.database)
    submitted = runs.submit(
        command_type="targeted_refresh",
        target_business_date="2026-09-10",
        client_request_id="media-page",
        model_version_id=model_id,
        # The run's cutoff lies after the values it stores, as for any refresh.
        system_as_of=datetime.now(UTC) + timedelta(days=1),
        release_event_id=f"media:{period}",
        metric_ids=metric_ids,
        period=period,
    )
    process_pending_run(paths, report_adapters=())
    return runs.get(submitted.run_id), paths, request["manifest"]["metric_catalog_version"], calls


def cpi_values(paths: RuntimePaths, version: str) -> dict[tuple[str, str], float | None]:
    return {
        (p.dimensions["category"], p.dimensions["measure"]): p.selected_value
        for p in EvidenceRepository(paths.database).metric_series(
            "CN_CPI_HEADLINE",
            mode=AsOfMode.SYSTEM,
            as_of=datetime.now(UTC) + timedelta(days=2),
            definition_version=version,
        )
    }


@pytest.mark.usefixtures("runtime_clock")
def test_cpi_gap_is_filled_from_a_media_page_and_keeps_its_matched_quotes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    body = page(item("财联社", "国家统计局")["content"])

    stored, paths, version, calls = media_run(tmp_path, monkeypatch, capsys, body=body)

    assert stored.status == "completed", stored.error_classification
    assert calls == ["https://api.tavily.com/search", CLS]
    assert cpi_values(paths, version) == {
        ("headline", "yoy"): 0.8,
        ("headline", "mom"): 0.4,
        ("headline", "cumulative_average_yoy"): 0.9,
    }
    [validation] = stored.retrieval_ledger["candidate_validations"]
    assert validation["outcome"] == "model_usable"
    with database_connection(paths.database) as connection:
        quotes = connection.execute(
            "SELECT q.route, q.quote, q.title, q.source_name, q.published_at, q.url, "
            "length(q.body_hash), c.provider FROM claim_matched_quote q "
            "JOIN source_claim c USING(claim_id) ORDER BY q.quote"
        ).fetchall()
    assert len(quotes) == 3
    assert {row[0] for row in quotes} == {"media_page"}
    assert {row[3] for row in quotes} == {row[7] for row in quotes} == {"财联社"}
    assert {row[4] for row in quotes} == {"2026-09-09T09:41:00+08:00"}
    assert {row[5] for row in quotes} == {CLS}
    assert {row[6] for row in quotes} == {64}
    assert "8月份CPI同比上涨0.8%" in quotes[0][2]
    assert any("全国居民消费价格同比上涨0.8%" in row[1] for row in quotes)


@pytest.mark.parametrize(
    ("body", "period", "reason"),
    [
        pytest.param(
            lambda: page(item("新华网", "解读")["content"]),
            "2026-08",
            "rule_not_matched",
            id="rule",
        ),
        pytest.param(
            lambda: page(item("财联社", "国家统计局")["content"]),
            "2026-07",
            "period_mismatch",
            id="period",
        ),
        pytest.param(
            lambda: page(item("财联社", "国家统计局")["content"], "2099-01-01T00:00:00+08:00"),
            "2026-08",
            "date_after_cutoff",
            id="published-after-cutoff",
        ),
    ],
)
@pytest.mark.usefixtures("runtime_clock")
def test_a_media_page_without_a_usable_rule_sentence_gives_nothing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    body: Any,
    period: str,
    reason: str,
) -> None:
    stored, paths, version, _calls = media_run(
        tmp_path, monkeypatch, capsys, body=body(), period=period
    )

    [validation] = stored.retrieval_ledger["candidate_validations"]
    assert (validation["outcome"], validation["reason"]) == ("not_model_usable", reason)
    if reason != "date_after_cutoff":
        assert cpi_values(paths, version) == {}


@pytest.mark.usefixtures("runtime_clock")
def test_a_p0_core_never_takes_a_media_value(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    stored, _paths, _version, calls = media_run(
        tmp_path,
        monkeypatch,
        capsys,
        body=page("中证全指2026年9月9日收盘5321.20点。"),
        metric_ids=("CN_EQUITY_CORE_000985",),
        period="2026-09-09",
    )

    [validation] = stored.retrieval_ledger["candidate_validations"]
    assert (validation["outcome"], validation["reason"]) == ("not_model_usable", "not_whitelisted")
    assert CLS not in calls


@pytest.mark.usefixtures("runtime_clock")
def test_a_media_page_for_a_family_without_news_rules_names_the_rule(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The monthly tool liquidity table is never stated in the news: no rule reads it."""
    stored, _paths, _version, calls = media_run(
        tmp_path,
        monkeypatch,
        capsys,
        body=page("8月央行各项工具流动性投放情况。"),
        metric_ids=("CN_TOOL_LIQUIDITY_MONTHLY",),
    )

    [validation] = stored.retrieval_ledger["candidate_validations"]
    assert (validation["outcome"], validation["reason"]) == ("not_model_usable", "rule_not_matched")
    assert CLS not in calls
