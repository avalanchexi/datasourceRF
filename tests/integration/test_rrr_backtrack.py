"""Event #03: an RRR never held is traced back through the PBC's policy chronicles."""

from __future__ import annotations

import json
import re
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.official_context import FetchedOfficialContextDocument
from pring_cycle.runtime import RuntimePaths, initialize_runtime

FIXTURES = Path(__file__).parents[1] / "fixtures"
COLUMN = "https://www.pbc.gov.cn/zhengcehuobisi/125207/125227/125963/"
NOW = datetime(2026, 9, 24, 7, 11, tzinfo=UTC)
PAGES = {
    COLUMN + "index.html": "official_listing/pbc_125963_index_20260925.html",
    COLUMN + "17134-2.html": "official_listing/pbc_125963_17134-2_20260925.html",
    COLUMN + "2026081218415997958/index.html": "pbc_rrr_chronicle/2026081218415997958.html",
    COLUMN + "2026081218411076109/index.html": "pbc_rrr_chronicle/2026081218411076109.html",
    COLUMN + "2026052009181730749/index.html": "pbc_rrr_chronicle/2026052009181730749.html",
}


class Site:
    """The PBC column and chronicles as saved on 2026-09-25; anything else is offline."""

    def __init__(self, pages: dict[str, bytes] | None = None) -> None:
        self.pages = (
            pages
            if pages is not None
            else {url: (FIXTURES / name).read_bytes() for url, name in PAGES.items()}
        )
        self.fetched: list[str] = []

    def __call__(self, url: str) -> FetchedOfficialContextDocument:
        self.fetched.append(url)
        if url not in self.pages:
            raise OSError("fixture_official_offline")
        return FetchedOfficialContextDocument(self.pages[url], "text/html", url, 200)


@pytest.fixture
def paths(tmp_path: Path) -> RuntimePaths:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    return paths


def rrr(paths: RuntimePaths) -> dict[str, tuple[str, float | None]]:
    return {
        point.dimensions["scope"]: (point.period_end, point.selected_value)
        for point in EvidenceRepository(paths.database).metric_series(
            "CN_RRR_EVENT", mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC)
        )
    }


def test_the_latest_cut_is_found_in_the_newest_chronicle_that_states_one(
    paths: RuntimePaths,
) -> None:
    from pring_cycle.official_context import backtrack_rrr_chronicle

    site = Site()
    found = backtrack_rrr_chronicle(paths, until=date(2026, 9, 23), fetched_at=NOW, fetcher=site)

    assert rrr(paths) == {
        "excluding_5_percent_institutions": ("2025-05-15", -0.5),
        "auto_finance_and_financial_leasing_companies": ("2025-05-15", -5.0),
    }
    assert len(found.claim_ids) == 2
    # The newest issue goes to June: later days are for the tail check.
    assert found.covered_through == date(2026, 6, 30)
    # The column, the two 2026 issues (no cut), then 2025's, read again to be kept.
    assert site.fetched == [
        COLUMN + "index.html",
        COLUMN + "2026081218415997958/index.html",
        COLUMN + "2026081218411076109/index.html",
        COLUMN + "2026052009181730749/index.html",
        COLUMN + "2026052009181730749/index.html",
    ]


def test_an_issue_published_after_the_target_day_is_not_read(paths: RuntimePaths) -> None:
    from pring_cycle.official_context import backtrack_rrr_chronicle

    site = Site()
    found = backtrack_rrr_chronicle(paths, until=date(2026, 8, 11), fetched_at=NOW, fetcher=site)

    assert COLUMN + "2026081218415997958/index.html" not in site.fetched
    assert found.covered_through == date(2026, 3, 31)
    assert {end for end, _value in rrr(paths).values()} == {"2025-05-15"}


def test_a_column_with_no_cut_to_its_last_page_finds_none(paths: RuntimePaths) -> None:
    """A synthetic column: the real first page with only its 2026 issues and no pager."""
    from pring_cycle.official_context import backtrack_rrr_chronicle

    site = Site()
    older = re.compile(
        r'<table[^>]*>(?:(?!</table>).)*?title="20(?:1\d|2[0-5])年[^"]*"(?:(?!</table>).)*?</table>',
        re.S,
    )
    listing = site.pages[COLUMN + "index.html"].decode()
    site.pages[COLUMN + "index.html"] = older.sub("", listing).replace("下一页", "").encode()

    found = backtrack_rrr_chronicle(paths, until=date(2026, 9, 23), fetched_at=NOW, fetcher=site)

    assert found.claim_ids == ()
    assert found.covered_through == date(2026, 6, 30)
    assert rrr(paths) == {}


@pytest.mark.parametrize(
    ("sentence", "error"),
    [
        (
            "2月5日，中国人民银行下调金融机构存款准备金率0.5个百分点（不含财务公司）。",
            "official_context_rrr_scope_incomplete",
        ),
        # Worded as no rule reads it: still a change, so not "none that month".
        (
            "2月5日，中国人民银行对中小银行定向下调存款准备金率1个百分点。",
            "official_context_rrr_change_unreadable",
        ),
    ],
)
def test_a_cut_the_parser_cannot_read_stops_the_search(
    paths: RuntimePaths, sentence: str, error: str
) -> None:
    """An older cut must not stand in for a newer one that was not read."""
    from pring_cycle.official_context import backtrack_rrr_chronicle

    site = Site()
    key = COLUMN + "2026081218411076109/index.html"
    site.pages[key] = site.pages[key].replace(
        "1月15日，".encode(), (sentence + "1月15日，").encode(), 1
    )

    with pytest.raises(ValueError, match=f"^{error}$"):
        backtrack_rrr_chronicle(paths, until=date(2026, 9, 23), fetched_at=NOW, fetcher=site)
    assert COLUMN + "2026052009181730749/index.html" not in site.fetched


def test_a_foreign_currency_rrr_change_is_not_the_rrr(paths: RuntimePaths) -> None:
    from pring_cycle.official_context import backtrack_rrr_chronicle

    site = Site()
    key = COLUMN + "2026081218411076109/index.html"
    site.pages[key] = site.pages[key].replace(
        "1月15日，".encode(),
        "2月5日，中国人民银行下调金融机构外汇存款准备金率2个百分点。1月15日，".encode(),
        1,
    )

    found = backtrack_rrr_chronicle(paths, until=date(2026, 9, 23), fetched_at=NOW, fetcher=site)

    assert {end for end, _value in rrr(paths).values()} == {"2025-05-15"}
    assert len(found.claim_ids) == 2


def test_a_column_page_listing_no_chronicle_is_not_the_column_s_end(paths: RuntimePaths) -> None:
    """A page changed or replaced (a maintenance notice) does not say there is no cut."""
    from pring_cycle.official_context import backtrack_rrr_chronicle

    site = Site()
    site.pages[COLUMN + "index.html"] = "<html><body>系统维护中</body></html>".encode()

    with pytest.raises(ValueError, match="^official_context_release_link_not_found$"):
        backtrack_rrr_chronicle(paths, until=date(2026, 9, 23), fetched_at=NOW, fetcher=site)


# The public entry: a full run's retrieval, then its gap list and the policy action card.

TARGET = "2026-09-23"
TAIL_CUT = (
    "中国人民银行决定于2026年8月15日下调金融机构存款准备金率0.25个百分点"
    "（不含已执行5%存款准备金率的金融机构）。"
)


def backtrack_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
    capsys: pytest.CaptureFixture[str],
    site: Site,
    *,
    ai: list[dict[str, Any]] | None = None,
) -> tuple[RuntimePaths, str, dict[str, Any], list[dict[str, Any]]]:
    """A first full run for ``TARGET``: no RRR held and no news of one."""
    from pring_cycle.full_retrieval import FullRunRetrieval
    from pring_cycle.runs import RunRepository
    from tests.integration.test_ai_websearch import install
    from tests.integration.test_tushare_news import Opener, news_response, register_at

    calls = None
    if ai is not None:
        calls = install(tmp_path, monkeypatch, {"codex": {"mode": "answer", "candidates": ai}})
        monkeypatch.delenv("PRING_CYCLE_AI_WEBSEARCH")
    paths, model_id, _version = register_at(NOW, tmp_path, monkeypatch, request, capsys)
    opener = Opener(lambda _payload: news_response([]))
    monkeypatch.setattr("pring_cycle.tushare_context.build_opener", lambda *handlers: opener)
    monkeypatch.setattr("pring_cycle.official_context._fetch_official_context_document", site)
    runs = RunRepository(paths.database)
    submitted = runs.submit_manual_full(
        target_business_date=TARGET,
        client_request_id="rrr-backtrack",
        model_version_id=model_id,
        system_as_of=NOW,
    )
    run = runs.advance(submitted.run_id, "refreshing_evidence")
    FullRunRetrieval(paths).retrieve(run)
    plan = runs.full_retrieval_plan(run.run_id)
    made = (
        [json.loads(line) for line in calls.read_text().splitlines()]
        if calls and calls.exists()
        else []
    )
    # Other gaps of the run ask too; the backtrack's question names its window.
    return paths, model_id, plan, [call for call in made if "effective_by" in call["prompt"]]


def rrr_gaps(paths: RuntimePaths, model_id: str, run_id: str) -> list[dict[str, object]]:
    from pring_cycle.context_projection import ContextProjectionRules
    from pring_cycle.freshness import gap_list, record_run_freshness
    from pring_cycle.models import ModelRepository
    from pring_cycle.trading_calendar import TradingCalendar

    definitions = ContextProjectionRules.from_manifest(
        ModelRepository(paths.database).manifest(model_id)
    ).metric_definitions
    from pring_cycle.retrieval_ledger import utc_now

    # As the worker does, at the cutoff frozen after retrieval.
    record_run_freshness(paths.database, run_id, definitions, utc_now(), TradingCalendar())
    return [
        g for g in gap_list(paths.database, run_id, definitions) if g["metric_id"] == "CN_RRR_EVENT"
    ]


def card(paths: RuntimePaths, model_id: str) -> list[tuple[str, float | None]]:
    from tests.integration.test_tushare_news import rrr_rows

    return sorted(rrr_rows(paths, model_id, NOW, TARGET))


def run_id_of(paths: RuntimePaths) -> str:
    from pring_cycle.storage import database_connection

    with database_connection(paths.database) as connection:
        return str(connection.execute("SELECT run_id FROM parent_run").fetchone()[0])


def test_an_rrr_never_held_is_traced_back_to_the_latest_chronicled_cut(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
    capsys: pytest.CaptureFixture[str],
) -> None:
    paths, model_id, plan, _made = backtrack_run(tmp_path, monkeypatch, request, capsys, Site())

    backtrack = plan["event_backtrack"]
    assert backtrack["metrics"] == {"CN_RRR_EVENT": "found"}
    assert backtrack["official"] == "found"
    assert backtrack["covered_through"] == "2026-06-30"
    # AI WebSearch is off: the tail after June is recorded as not checked, not as missing.
    assert backtrack["tail"] == "unchecked"
    assert len(backtrack["claim_ids"]) == 2
    assert card(paths, model_id) == [("current", -5.0), ("current", -0.5)]
    assert rrr_gaps(paths, model_id, run_id_of(paths)) == []


def test_a_cut_after_the_newest_chronicle_is_asked_of_ai_websearch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
    capsys: pytest.CaptureFixture[str],
) -> None:
    tail = {
        "url": "https://www.pbc.gov.cn/goutongjiaoliu/113456/113469/2026081417000000000/index.html",
        "quote": TAIL_CUT,
        "value": 0.25,
        "period": "2026-08-15",
        "published_date": "2026-08-14",
    }
    paths, model_id, plan, made = backtrack_run(
        tmp_path, monkeypatch, request, capsys, Site(), ai=[tail]
    )

    backtrack = plan["event_backtrack"]
    assert backtrack["metrics"] == {"CN_RRR_EVENT": "found"}
    assert backtrack["tail"] == "new_event"
    (call,) = made
    assert (call["prompt"]["effective_after"], call["prompt"]["effective_by"]) == (
        "2026-06-30",
        TARGET,
    )
    assert selected_rrr(paths)["excluding_5_percent_institutions"] == ("2026-08-15", -0.25)


def test_the_official_column_failing_is_made_up_by_ai_websearch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fallback = {
        "url": "https://www.pbc.gov.cn/goutongjiaoliu/113456/113469/2025050709000000000/index.html",
        "quote": "中国人民银行决定于2025年5月15日下调金融机构存款准备金率0.5个百分点"
        "（不含已执行5%存款准备金率的金融机构）。",
        "value": 0.5,
        "period": "2025-05-15",
        "published_date": "2025-05-07",
    }
    paths, model_id, plan, made = backtrack_run(
        tmp_path, monkeypatch, request, capsys, Site({}), ai=[fallback]
    )

    backtrack = plan["event_backtrack"]
    assert backtrack["official"] == "source_failed"
    assert backtrack["metrics"] == {"CN_RRR_EVENT": "found"}
    (call,) = made
    assert (call["prompt"]["effective_after"], call["prompt"]["effective_by"]) == (None, TARGET)
    assert card(paths, model_id) == [("current", -0.5)]
    assert rrr_gaps(paths, model_id, run_id_of(paths)) == []


def test_an_ai_candidate_the_rrr_rule_does_not_read_is_not_adopted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
    capsys: pytest.CaptureFixture[str],
) -> None:
    undated = {
        "url": "https://www.pbc.gov.cn/goutongjiaoliu/113456/113469/2025050709000000000/index.html",
        # No effective day in the sentence: the rule does not take it.
        "quote": "中国人民银行下调金融机构存款准备金率0.5个百分点"
        "（不含已执行5%存款准备金率的金融机构）。",
        "value": 0.5,
        "period": "2025-05-15",
        "published_date": "2025-05-07",
    }
    paths, model_id, plan, _made = backtrack_run(
        tmp_path, monkeypatch, request, capsys, Site({}), ai=[undated]
    )

    assert plan["event_backtrack"]["metrics"] == {"CN_RRR_EVENT": "source_failed"}
    assert selected_rrr(paths) == {}
    (gap,) = rrr_gaps(paths, model_id, run_id_of(paths))
    assert gap["category"] == "retrieval_failed"


def test_a_column_searched_to_its_end_without_a_cut_is_not_a_gap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
    capsys: pytest.CaptureFixture[str],
) -> None:
    site = Site()
    listing = site.pages[COLUMN + "index.html"].decode()
    site.pages[COLUMN + "index.html"] = (
        re.sub(
            r'<table[^>]*>(?:(?!</table>).)*?title="20(?:1\d|2[0-5])年[^"]*"(?:(?!</table>).)*?</table>',
            "",
            listing,
            flags=re.S,
        )
        .replace("下一页", "")
        .encode()
    )
    paths, model_id, plan, _made = backtrack_run(tmp_path, monkeypatch, request, capsys, site)

    assert plan["event_backtrack"]["metrics"] == {"CN_RRR_EVENT": "none_found"}
    assert rrr_gaps(paths, model_id, run_id_of(paths)) == []


def selected_rrr(paths: RuntimePaths) -> dict[str, tuple[str, float | None]]:
    """Each scope's latest change, as the system holds it."""
    latest: dict[str, tuple[str, float | None]] = {}
    for scope, (end, value) in sorted(
        ((p.dimensions["scope"], (p.period_end, p.selected_value)) for p in _points(paths)),
        key=lambda item: item[1][0],
    ):
        latest[scope] = (end, value)
    return latest


def _points(paths: RuntimePaths) -> tuple[Any, ...]:
    return EvidenceRepository(paths.database).metric_series(
        "CN_RRR_EVENT", mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC)
    )


def test_on_a_day_the_official_notice_states_its_members_are_all_read_from_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Ticket 02's hand-over: news states only one member of the day the chronicle states.

    Selection by provider alone would read that member from the news and the other from
    the notice, and the notice would then look incomplete.
    """
    from tests.integration.test_tushare_news import full_run, news_response, rrr_rows

    paths, model_id, _plan, _made = backtrack_run(tmp_path, monkeypatch, request, capsys, Site())
    # The next day's news recalls the May cut, for its general scope only.
    recalled = {
        "title": "回顾：央行年内降准",
        "content": "<p>中国人民银行决定于2025年5月15日下调金融机构存款准备金率0.5个百分点"
        "（不含已执行5%存款准备金率的金融机构）。</p>",
        "pub_time": "2026-09-24 09:00:00",
        "src": "新华网",
    }
    later = datetime(2026, 9, 25, 7, 11, tzinfo=UTC)
    full_run(
        paths,
        model_id,
        monkeypatch,
        lambda _payload: news_response([recalled]),
        target="2026-09-24",
        now=later,
    )
    general = next(
        p for p in _points(paths) if p.dimensions["scope"] == "excluding_5_percent_institutions"
    )
    assert {claim.provider for claim in general.claims} == {"tushare_news", "中国人民银行"}

    assert sorted(rrr_rows(paths, model_id, later, "2026-09-24")) == [
        ("current", -5.0),
        ("current", -0.5),
    ]


def test_a_tail_candidate_published_after_the_target_day_leaves_the_search_unfinished(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The column has no cut; the tail's one candidate came out after the target day.

    It would not be visible on the target day, so it is not adopted; and a candidate turned
    down is not "none found": the search did not settle.
    """
    site = Site()
    listing = site.pages[COLUMN + "index.html"].decode()
    site.pages[COLUMN + "index.html"] = (
        re.sub(
            r'<table[^>]*>(?:(?!</table>).)*?title="20(?:1\d|2[0-5])年[^"]*"(?:(?!</table>).)*?</table>',
            "",
            listing,
            flags=re.S,
        )
        .replace("下一页", "")
        .encode()
    )
    late = {
        "url": "https://www.pbc.gov.cn/goutongjiaoliu/113456/113469/2026092409000000000/index.html",
        "quote": TAIL_CUT,
        "value": 0.25,
        "period": "2026-08-15",
        "published_date": "2026-09-24",
    }
    paths, model_id, plan, _made = backtrack_run(
        tmp_path, monkeypatch, request, capsys, site, ai=[late]
    )

    backtrack = plan["event_backtrack"]
    assert (backtrack["official"], backtrack["tail"]) == ("none_found", "rejected")
    assert backtrack["metrics"] == {"CN_RRR_EVENT": "source_failed"}
    assert selected_rrr(paths) == {}
    (gap,) = rrr_gaps(paths, model_id, run_id_of(paths))
    assert gap["category"] == "retrieval_failed"
