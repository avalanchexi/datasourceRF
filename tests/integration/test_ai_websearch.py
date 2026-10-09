"""Phase two #11: AI WebSearch through the installed CLIs, Codex first and Claude after."""

from __future__ import annotations

import json
import os
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

CLS = "https://www.cls.cn/detail/2140001"
SENTENCES = {
    "yoy": ("2026年8月份，全国居民消费价格同比上涨0.8%。", 0.8),
    "mom": ("8月份，全国居民消费价格环比上涨0.4%。", 0.4),
    "cumulative_average_yoy": ("1—8月平均，全国居民消费价格比上年同期上涨0.9%。", 0.9),
}

FAKE_CLI = """#!/usr/bin/python3
import json, os, sys, time
from pathlib import Path
here = Path(__file__).parent
name = Path(sys.argv[0]).name
if '--version' in sys.argv:
    print('fixture-' + name + ' 1.0'); raise SystemExit(0)
plan = json.loads((here / 'plan.json').read_text())[name]
with (here / 'calls.jsonl').open('a') as f:
    f.write(json.dumps({'name': name, 'args': sys.argv[1:],
        'key_visible': any(k in os.environ for k in ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY')),
        'prompt': json.load(sys.stdin)}) + '\\n')
if plan['mode'] == 'hang':
    time.sleep(60)
document = {'candidates': plan['candidates']}
if name == 'codex':
    out = sys.argv[sys.argv.index('--output-last-message') + 1]
    Path(out).write_text(json.dumps(document))
    print(json.dumps({'type': 'item.completed', 'item': {'type': 'web_search'}}))
    print(json.dumps({'type': 'turn.completed'}))
else:
    block = {'type': 'tool_use', 'name': 'WebSearch', 'input': {'query': 'cpi'}}
    print(json.dumps({'type': 'assistant', 'message': {'content': [block]}}))
    print(json.dumps({'type': 'result', 'subtype': 'success', 'is_error': False,
        'structured_output': document}))
"""


def candidate(measure: str, **changes: Any) -> dict[str, Any]:
    quote, value = SENTENCES[measure]
    return {
        "url": CLS,
        "quote": quote,
        "value": value,
        "period": "2026-08",
        "published_date": "2026-09-09",
        **changes,
    }


def install(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, plan: dict[str, Any]) -> Path:
    directory = tmp_path / "cli"
    directory.mkdir()
    for name in ("codex", "claude"):
        program = directory / name
        program.write_text(FAKE_CLI)
        program.chmod(0o700)
    (directory / "plan.json").write_text(json.dumps(plan))
    monkeypatch.setenv("PATH", str(directory) + os.pathsep + os.environ.get("PATH", ""))
    monkeypatch.setenv("OPENAI_API_KEY", "fixture-must-not-reach-cli")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fixture-must-not-reach-cli")
    return directory / "calls.jsonl"


def ai_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    plan: dict[str, Any],
    *,
    metric_ids: tuple[str, ...] = ("CN_CPI_HEADLINE",),
    release_event_id: str = "ai:cpi:2026-08",
    period: str = "2026-08",
) -> tuple[RunRecord, RuntimePaths, str, list[dict[str, Any]]]:
    calls = install(tmp_path, monkeypatch, plan)
    monkeypatch.delenv("PRING_CYCLE_AI_WEBSEARCH")
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    ModelRepository(paths.database).activate(model_id, explicitly_approved=True)
    paths.config_file.write_text(
        paths.config_file.read_text() + "\n[retrieval]\nai_websearch = true\n"
    )
    runs = RunRepository(paths.database)
    submitted = runs.submit(
        command_type="targeted_refresh",
        target_business_date="2026-09-10",
        client_request_id="ai-websearch",
        model_version_id=model_id,
        system_as_of=datetime.now(UTC) + timedelta(days=1),
        release_event_id=release_event_id,
        metric_ids=metric_ids,
        period=period,
    )
    process_pending_run(paths, report_adapters=())
    made = [json.loads(line) for line in calls.read_text().splitlines()] if calls.exists() else []
    return runs.get(submitted.run_id), paths, request["manifest"]["metric_catalog_version"], made


def cpi(paths: RuntimePaths, version: str) -> dict[str, float | None]:
    return {
        p.dimensions["measure"]: p.selected_value
        for p in EvidenceRepository(paths.database).metric_series(
            "CN_CPI_HEADLINE",
            mode=AsOfMode.SYSTEM,
            as_of=datetime.now(UTC) + timedelta(days=2),
            definition_version=version,
        )
    }


ALL_THREE = [candidate(measure) for measure in SENTENCES]


@pytest.mark.usefixtures("runtime_clock")
def test_codex_candidates_fill_the_p1_gap_with_their_quotes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    stored, paths, version, calls = ai_run(
        tmp_path,
        monkeypatch,
        capsys,
        {
            "codex": {"mode": "ok", "candidates": ALL_THREE},
            "claude": {"mode": "ok", "candidates": []},
        },
    )

    assert stored.status == "completed", stored.error_classification
    assert [call["name"] for call in calls] == ["codex"]
    assert calls[0]["args"][0] == "--search"
    assert not calls[0]["key_visible"]
    assert calls[0]["prompt"]["search_query"] == "2026年8月份居民消费价格"
    assert calls[0]["prompt"]["allowed_domains"][0] == "www.stats.gov.cn"
    assert cpi(paths, version) == {"yoy": 0.8, "mom": 0.4, "cumulative_average_yoy": 0.9}
    ledger = stored.retrieval_ledger
    [request] = [r for r in ledger["requests"] if r["channel"] == "ai_websearch"]
    assert (request["provider"], request["outcome"]) == ("codex_cli", "verified")
    assert request["started_at"] <= request["completed_at"]
    assert [v["outcome"] for v in ledger["candidate_validations"]] == ["model_usable"] * 3
    with database_connection(paths.database) as connection:
        routes = connection.execute("SELECT DISTINCT route, source_name FROM claim_matched_quote")
        assert routes.fetchall() == [("ai_websearch", "财联社")]


@pytest.mark.usefixtures("runtime_clock")
def test_claude_fills_the_gap_when_codex_times_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("pring_cycle.ai_websearch.AI_CALL_SECONDS", 2)

    stored, paths, version, calls = ai_run(
        tmp_path,
        monkeypatch,
        capsys,
        {
            "codex": {"mode": "hang", "candidates": []},
            "claude": {"mode": "ok", "candidates": ALL_THREE},
        },
    )

    assert stored.status == "completed", stored.error_classification
    assert [call["name"] for call in calls] == ["codex", "claude"]
    assert "WebSearch" in calls[1]["args"]
    assert cpi(paths, version) == {"yoy": 0.8, "mom": 0.4, "cumulative_average_yoy": 0.9}
    [request] = [r for r in stored.retrieval_ledger["requests"] if r["channel"] == "ai_websearch"]
    assert request["provider"] == "claude_code_cli"


@pytest.mark.usefixtures("runtime_clock")
def test_each_unusable_candidate_is_rejected_with_its_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    candidates = [
        candidate("yoy", url="https://finance.example.com/cpi"),
        candidate("yoy", value=0.9),
        candidate("yoy", period="2026-07"),
        candidate("yoy", published_date="2099-01-01"),
        candidate("yoy", quote="8月份CPI同比涨幅扩大至0.8%。"),
    ]

    stored, paths, version, _calls = ai_run(
        tmp_path,
        monkeypatch,
        capsys,
        {
            "codex": {"mode": "ok", "candidates": candidates},
            "claude": {"mode": "ok", "candidates": []},
        },
    )

    assert [
        (v["outcome"], v["reason"]) for v in stored.retrieval_ledger["candidate_validations"]
    ] == [
        ("not_model_usable", "not_whitelisted"),
        ("not_model_usable", "search_value_mismatch"),
        ("not_model_usable", "period_mismatch"),
        ("not_model_usable", "date_after_cutoff"),
        ("not_model_usable", "rule_not_matched"),
    ]
    assert cpi(paths, version) == {}


@pytest.mark.usefixtures("runtime_clock")
def test_the_run_stops_calling_once_its_ai_time_is_spent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("pring_cycle.ai_websearch.AI_RUN_BUDGET", timedelta(0))

    stored, _paths, _version, calls = ai_run(
        tmp_path,
        monkeypatch,
        capsys,
        {
            "codex": {"mode": "ok", "candidates": ALL_THREE},
            "claude": {"mode": "ok", "candidates": []},
        },
    )

    assert calls == []
    [attempt] = [a for a in stored.retrieval_attempts if a["channel"] == "ai_websearch"]
    assert (attempt["outcome"], attempt["classification"]) == (
        "not_attempted",
        "ai_time_exhausted",
    )


@pytest.mark.usefixtures("runtime_clock")
def test_a_figure_given_as_the_sentence_writes_it_is_the_same_figure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """ "下降0.4%" is -0.4 for the member; the CLI may report the 0.4 it reads."""
    falling = candidate("yoy", quote="2026年8月份，全国居民消费价格同比下降0.4%。", value=0.4)

    stored, paths, version, _calls = ai_run(
        tmp_path,
        monkeypatch,
        capsys,
        {
            "codex": {"mode": "ok", "candidates": [falling, *ALL_THREE[1:]]},
            "claude": {"mode": "ok", "candidates": []},
        },
    )

    assert stored.status == "completed", stored.error_classification
    assert cpi(paths, version)["yoy"] == -0.4


@pytest.mark.usefixtures("runtime_clock")
def test_a_gap_the_rules_cannot_complete_is_not_asked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """PPI's component year-to-date averages are only in the official table."""
    stored, _paths, _version, calls = ai_run(
        tmp_path,
        monkeypatch,
        capsys,
        {"codex": {"mode": "ok", "candidates": []}, "claude": {"mode": "ok", "candidates": []}},
        metric_ids=("CN_PPI",),
    )

    assert calls == []
    [attempt] = [a for a in stored.retrieval_attempts if a["channel"] == "ai_websearch"]
    assert attempt["outcome"] == "not_configured"


PARITY = "2026年9月9日银行间外汇市场人民币汇率中间价为1美元对人民币6.7351元，下调17个基点。"


def parity_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    quote: str,
    value: float,
) -> tuple[RunRecord, dict[tuple[str, tuple[tuple[str, str], ...]], float | None]]:
    found = {"url": CLS, "quote": quote, "value": value, "period": "2026-09-09"}
    stored, paths, version, _calls = ai_run(
        tmp_path,
        monkeypatch,
        capsys,
        {
            "codex": {"mode": "ok", "candidates": [{**found, "published_date": "2026-09-09"}]},
            "claude": {"mode": "ok", "candidates": []},
        },
        metric_ids=("CN_USDCNY_CENTRAL_PARITY",),
        release_event_id="ai:usdcny:2026-09-09",
        period="2026-09-09",
    )
    series = EvidenceRepository(paths.database).metric_series(
        "CN_USDCNY_CENTRAL_PARITY",
        mode=AsOfMode.SYSTEM,
        as_of=datetime.now(UTC) + timedelta(days=2),
        definition_version=version,
    )
    return stored, {
        (p.period_end, tuple(sorted(p.dimensions.items()))): p.selected_value for p in series
    }


@pytest.mark.usefixtures("runtime_clock")
def test_a_stored_central_parity_completes_its_gap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Lookback ticket 07: the one member the parity has is the contract it is selected by."""
    stored, parity = parity_run(tmp_path, monkeypatch, capsys, PARITY, 6.7351)

    member = (("currency_pair", "USD/CNY"), ("quote_direction", "CNY per USD"))
    assert parity == {("2026-09-09", member): 6.7351}
    ledger = stored.retrieval_ledger
    assert ledger is not None
    [request] = [r for r in ledger["requests"] if r["channel"] == "ai_websearch"]
    assert (request["outcome"], request["classification"]) == (
        "verified",
        "complete_model_input",
    )
    assert stored.status == "completed", stored.error_classification


@pytest.mark.usefixtures("runtime_clock")
def test_a_parity_quoted_the_other_way_round_is_not_taken(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Dollars per yuan is not the member: 0.1485 must not stand as the CNY-per-USD rate."""
    reversed_quote = "2026年9月9日银行间外汇市场人民币汇率中间价为1人民币对美元0.1485美元。"

    stored, parity = parity_run(tmp_path, monkeypatch, capsys, reversed_quote, 0.1485)

    assert parity == {}
    ledger = stored.retrieval_ledger
    assert ledger is not None
    assert [(v["outcome"], v["reason"]) for v in ledger["candidate_validations"]] == [
        ("not_model_usable", "rule_not_matched")
    ]
    [request] = [r for r in ledger["requests"] if r["channel"] == "ai_websearch"]
    assert request["classification"] == "candidate_validation_unresolved"
    assert stored.status != "completed"


def test_ai_websearch_is_on_unless_turned_off(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pring_cycle.ai_websearch import ai_websearch_enabled

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    monkeypatch.delenv("PRING_CYCLE_AI_WEBSEARCH")
    assert ai_websearch_enabled(paths)
    paths.config_file.write_text("[retrieval]\nai_websearch = false\n")
    assert not ai_websearch_enabled(paths)
    paths.config_file.write_text("[retrieval]\nai_websearch = true\n")
    monkeypatch.setenv("PRING_CYCLE_AI_WEBSEARCH", "off")
    assert not ai_websearch_enabled(paths)


GDP_TOTAL_GROWTH = 'CN_GDP:{"aggregate": "total", "measure": "real_quarter_yoy"}'
GDP_PRIMARY_GROWTH = 'CN_GDP:{"aggregate": "primary", "measure": "real_quarter_yoy"}'
SF_STOCK_GROWTH = 'CN_SF_TOTAL:{"measure": "stock_yoy"}'


@pytest.mark.parametrize(
    ("metric_id", "period", "members", "stock_growth_ruled", "asked"),
    [
        # A lookback reads the total's quarterly growth alone, which the news states.
        pytest.param("CN_GDP", "2026-Q2", (GDP_TOTAL_GROWTH,), True, True, id="gdp-total"),
        # Each industry's quarterly growth is not stated in the news.
        pytest.param(
            "CN_GDP",
            "2026-Q2",
            (GDP_TOTAL_GROWTH, GDP_PRIMARY_GROWTH),
            True,
            False,
            id="gdp-industry",
        ),
        pytest.param("CN_SF_TOTAL", "2026-07", (SF_STOCK_GROWTH,), True, True, id="sf-growth"),
        # Without a rule for the stock's growth, the flow and stock it states do not count.
        pytest.param(
            "CN_SF_TOTAL", "2026-07", (SF_STOCK_GROWTH,), False, False, id="sf-growth-unruled"
        ),
    ],
)
def test_ai_websearch_is_asked_only_for_members_its_rules_can_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    metric_id: str,
    period: str,
    members: tuple[str, ...],
    stock_growth_ruled: bool,
    asked: bool,
) -> None:
    """Lookback L03: what a scope's lookback names decides it, not the catalog's required
    members; otherwise the AI was asked eight times for a growth no rule could take."""
    from dataclasses import replace

    from pring_cycle import news_rules
    from pring_cycle.models import EFFECTIVE_CATALOG_VERSION, effective_model_manifest
    from pring_cycle.runs import RetrievalScope
    from pring_cycle.worker import _production_retrieval_adapters

    monkeypatch.delenv("PRING_CYCLE_AI_WEBSEARCH")
    if not stock_growth_ruled:
        monkeypatch.setitem(
            news_rules.NEWS_RULES,
            "pbc_social_financing",
            tuple(
                rule
                for rule in news_rules.NEWS_RULES["pbc_social_financing"]
                if (rule.metric_id, rule.dimensions) != ("CN_SF_TOTAL", (("measure", "stock_yoy"),))
            ),
        )
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifest = effective_model_manifest()
    models = ModelRepository(paths.database)
    models.register(manifest)
    models.activate(str(manifest["model_version_id"]), explicitly_approved=True)
    run = RunRepository(paths.database).submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id="ai-websearch-members",
        model_version_id=str(manifest["model_version_id"]),
        system_as_of=datetime.now(UTC),
    )
    scope = RetrievalScope(f"full:{metric_id}:{period}", (metric_id,), period, "P1", None, members)

    adapters = _production_retrieval_adapters(
        paths,
        scope,
        datetime.now(UTC),
        definition_version=EFFECTIVE_CATALOG_VERSION,
        run_id=run.run_id,
        scope_run=replace(run, retrieval_scope=scope),
    )

    assert ("ai_websearch" in adapters) is asked


# The candidate Codex gave in run-8a3779cff80f6bd586a0 for July 2025 (lookback 14): its
# value is the stock, its sentence states the growth too.
SF_JULY_2025 = {
    "url": "https://app.www.gov.cn/govdata/gov/202508/13/534662/article.html",
    "quote": "初步统计，2025年7月末社会融资规模存量为431.26万亿元，同比增长9%。",
    "value": 431.26,
    "period": "2025-07",
    "published_date": "2025-08-13",
}


SF_STOCK = 'CN_SF_TOTAL:{"measure": "stock_end"}'
SF_STOCK_REPORT = (
    Path(__file__).parents[1]
    / "fixtures"
    / "official_period_fallback"
    / "pbc_social_financing_stock_202507.html"
)
SF_STOCK_ONLY = {**SF_JULY_2025, "quote": "初步统计，2025年7月末社会融资规模存量为431.26万亿元。"}


def sf_lookback_answer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    members: tuple[str, ...],
    found: dict[str, Any] = SF_JULY_2025,
    *,
    stock_held: bool = False,
) -> tuple[RunRecord, RuntimePaths, list[dict[str, Any]]]:
    """The AI asked for July 2025's social financing on a full run whose lookback names
    ``members``, answering with ``found`` (the real candidate). ``stock_held``: the stock
    report already gave the stock (its growth left out, as if not read)."""
    from dataclasses import replace

    from pring_cycle.ai_websearch import ai_websearch_adapter
    from pring_cycle.models import EFFECTIVE_CATALOG_VERSION, effective_model_manifest
    from pring_cycle.official_context import (
        FetchedOfficialContextDocument,
        refresh_official_context_document,
    )
    from pring_cycle.retrieval_ledger import RetrievalLedger
    from pring_cycle.runs import RetrievalScope

    calls = install(tmp_path, monkeypatch, {})
    monkeypatch.delenv("PRING_CYCLE_AI_WEBSEARCH")
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifest = effective_model_manifest()
    models = ModelRepository(paths.database)
    models.register(manifest)
    models.activate(str(manifest["model_version_id"]), explicitly_approved=True)

    if stock_held:
        report = "https://www.pbc.gov.cn/diaochatongjisi/116219/116225/4405816f/index.html"
        refresh_official_context_document(
            paths,
            family="pbc_social_financing",
            source_url=report,
            expected_period="2025-07",
            fetched_at=datetime.now(UTC),
            fetcher=lambda url: FetchedOfficialContextDocument(
                content=SF_STOCK_REPORT.read_bytes(),
                media_type="text/html",
                final_url=url,
                http_status=200,
            ),
            definition_version=EFFECTIVE_CATALOG_VERSION,
            held_members=frozenset({SF_STOCK_GROWTH}),
        )
    calls.with_name("plan.json").write_text(
        json.dumps(
            {
                "codex": {"mode": "ok", "candidates": [found]},
                "claude": {"mode": "ok", "candidates": []},
            }
        )
    )
    run = RunRepository(paths.database).submit_manual_full(
        target_business_date="2026-09-30",
        client_request_id="ai-websearch-sf-lookback",
        model_version_id=str(manifest["model_version_id"]),
        system_as_of=datetime.now(UTC) + timedelta(minutes=1),
    )
    scope = RetrievalScope(
        "full:CN_SF_TOTAL:2025-07", ("CN_SF_TOTAL",), "2025-07", "P1", None, members
    )
    scope_run = replace(run, retrieval_scope=scope)
    RetrievalLedger(paths.database).bind_run(scope_run, EFFECTIVE_CATALOG_VERSION)

    ai_websearch_adapter(
        paths, run.run_id, scope_run, definition_version=EFFECTIVE_CATALOG_VERSION
    )(scope.release_event_id)

    made = [json.loads(line) for line in calls.read_text().splitlines()]
    return RunRepository(paths.database).get(run.run_id), paths, made


def sf_july_2025(paths: RuntimePaths) -> dict[str, float | None]:
    return {
        p.dimensions["measure"]: p.selected_value
        for p in EvidenceRepository(paths.database).metric_series(
            "CN_SF_TOTAL", mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC) + timedelta(days=1)
        )
        if p.period_end == "2025-07-31"
    }


@pytest.mark.usefixtures("runtime_clock")
def test_the_member_a_lookback_misses_is_taken_from_a_sentence_stating_others_too(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Lookback 14: the sentence states the stock and its growth, the CLI gave the stock,
    and only the stock was kept, while the gap was the growth."""
    _stored, paths, calls = sf_lookback_answer(tmp_path, monkeypatch, (SF_STOCK_GROWTH,))

    assert calls[0]["prompt"]["members"] == [
        {"metric_id": "CN_SF_TOTAL", "dimensions": {"measure": "stock_yoy"}}
    ]
    assert sf_july_2025(paths) == {"stock_yoy": 9.0}
    ledger = _stored.retrieval_ledger
    assert ledger is not None
    [request] = [r for r in ledger["requests"] if r["channel"] == "ai_websearch"]
    assert (request["outcome"], request["classification"]) == ("verified", "complete_model_input")
    [validation] = ledger["candidate_validations"]
    assert (validation["outcome"], validation["missing_members"]) == ("model_usable", [])
    assert validation["selected_claim_ids"] == validation["claim_ids"]


@pytest.mark.usefixtures("runtime_clock")
def test_a_candidate_that_leaves_the_gap_incomplete_is_recorded_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Lookback 14: the candidate was recorded model_usable while the gap it was asked for
    stayed unresolved. A gap naming no members misses the catalog's required ones, and the
    sentence does not state the year's increment."""
    stored, paths, _calls = sf_lookback_answer(tmp_path, monkeypatch, ())

    assert sf_july_2025(paths) == {"stock_end": 4312600.0}
    ledger = stored.retrieval_ledger
    assert ledger is not None
    [request] = [r for r in ledger["requests"] if r["channel"] == "ai_websearch"]
    assert request["classification"] == "candidate_validation_unresolved"
    [validation] = ledger["candidate_validations"]
    assert (validation["outcome"], validation["reason"]) == (
        "not_model_usable",
        "incomplete_model_input",
    )
    assert 'CN_SF_TOTAL:{"measure": "ytd_increment"}' in validation["missing_members"]
    assert validation["claim_ids"]


@pytest.mark.usefixtures("runtime_clock")
def test_a_sentence_stating_only_members_the_gap_holds_fills_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stored, paths, _calls = sf_lookback_answer(
        tmp_path, monkeypatch, (SF_STOCK_GROWTH,), SF_STOCK_ONLY
    )

    assert sf_july_2025(paths) == {}
    assert stored.retrieval_ledger is not None
    assert [
        (v["outcome"], v["reason"]) for v in stored.retrieval_ledger["candidate_validations"]
    ] == [("not_model_usable", "incomplete_model_input")]


@pytest.mark.usefixtures("runtime_clock")
def test_a_member_the_scope_reads_but_holds_is_neither_asked_for_nor_taken(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A scope reads every member of its period, the held ones too: the AI is asked for
    the growth alone, and the stock its sentence restates is not stored again."""
    stored, paths, calls = sf_lookback_answer(
        tmp_path, monkeypatch, (SF_STOCK, SF_STOCK_GROWTH), stock_held=True
    )

    assert calls[-1]["prompt"]["members"] == [
        {"metric_id": "CN_SF_TOTAL", "dimensions": {"measure": "stock_yoy"}}
    ]
    assert sf_july_2025(paths) == {"stock_end": 4312600.0, "stock_yoy": 9.0}
    assert stored.retrieval_ledger is not None
    [validation] = stored.retrieval_ledger["candidate_validations"]
    assert validation["outcome"] == "model_usable"
    # The growth alone: the stock is not restated.
    assert len(validation["claim_ids"]) == 1
