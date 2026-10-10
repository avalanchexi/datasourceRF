"""Audit 06 slice 2 (ADR-0039): media values of one member that disagree are a source conflict
until an AI WebSearch recheck settles them on one side."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.ai_websearch import MEDIA_CONFLICT_UNSETTLED, ai_websearch_adapter
from pring_cycle.evidence import (
    AsOfMode,
    ClaimView,
    EvidenceRepository,
    EvidenceValueState,
    MetricSeriesPoint,
    SourceClaimInput,
    select_among,
)
from pring_cycle.media_recheck import SETTLED, UNSETTLED, decide
from pring_cycle.models import EFFECTIVE_CATALOG_VERSION, ModelRepository, effective_model_manifest
from pring_cycle.news_rules import (
    MEDIA_PAGE,
    MatchedQuote,
    member_period,
    member_unit,
    record_matched_quotes,
    text_hash,
)
from pring_cycle.retrieval_ledger import RetrievalLedger
from pring_cycle.runs import RetrievalScope, RunRecord, RunRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.storage import database_connection
from tests.integration.test_ai_websearch import SF_STOCK, SF_STOCK_ONLY, install, page_of, serve

STOCK = {"measure": "stock_end"}
KNOWN = datetime(2025, 8, 14, 2, tzinfo=UTC)
GOV = str(SF_STOCK_ONLY["url"])
SINA = "https://finance.sina.com.cn/roll/2025-08-13/doc-sf202507.shtml"
EASTMONEY = "https://finance.eastmoney.com/a/202508133500000001.html"
SF_GAP = "full:CN_SF_TOTAL:2025-07"


@pytest.fixture
def paths(tmp_path: Path) -> RuntimePaths:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifest = effective_model_manifest()
    models = ModelRepository(paths.database)
    models.register(manifest)
    models.activate(str(manifest["model_version_id"]), explicitly_approved=True)
    return paths


def stock_claim(
    paths: RuntimePaths, provider: str, value: float, url: str, known: datetime = KNOWN
) -> str:
    """July 2025's social financing stock, as a media page states it."""
    kind, start, end = member_period("CN_SF_TOTAL", STOCK, "2025-07")
    quote = f"初步统计，2025年7月末社会融资规模存量为{value / 10_000:g}万亿元。"
    [claim] = EvidenceRepository(paths.database).append_source_claims(
        (
            SourceClaimInput(
                metric_id="CN_SF_TOTAL",
                definition_version=EFFECTIVE_CATALOG_VERSION,
                period_kind=kind,
                period_start=start,
                period_end=end,
                dimensions=STOCK,
                value=value,
                value_state=EvidenceValueState.REPORTED_VALUE,
                unit=member_unit("CN_SF_TOTAL", STOCK, "2025-07", "亿元"),
                provider=provider,
                source_reference=f"{MEDIA_PAGE}:{url}#sha256={text_hash(quote)}",
                release_event_id=f"fixture:{provider}:{url}:{value}:{known}",
                release_at=known,
                public_available_at=known,
                fetched_at=known,
                available_at=known,
                quality_status="validated",
            ),
        )
    )
    with database_connection(paths.database) as connection:
        record_matched_quotes(
            connection,
            (
                MatchedQuote(
                    claim.claim_id,
                    MEDIA_PAGE,
                    quote,
                    "2025年7月金融统计数据报告",
                    provider,
                    None,
                    text_hash(quote),
                    url,
                    "",
                ),
            ),
        )
    return claim.claim_id


def stock(paths: RuntimePaths) -> MetricSeriesPoint:
    [point] = [
        p
        for p in EvidenceRepository(paths.database).metric_series(
            "CN_SF_TOTAL",
            mode=AsOfMode.SYSTEM,
            as_of=datetime.now(UTC) + timedelta(days=1),
            definition_version=EFFECTIVE_CATALOG_VERSION,
        )
        if p.period_end == "2025-07-31" and p.dimensions == STOCK
    ]
    return point


@pytest.mark.usefixtures("runtime_clock")
def test_media_values_of_one_member_that_disagree_are_a_source_conflict(
    paths: RuntimePaths,
) -> None:
    right = stock_claim(paths, "中国政府网", 4_312_600, GOV)
    stock_claim(paths, "东方财富", 4_512_600, EASTMONEY)

    point = stock(paths)
    assert (point.selection_status, point.conflict_reason) == ("conflicted", "value_disagreement")
    assert right in {claim.claim_id for claim in point.claims}


def test_a_certified_registered_value_decides_whatever_the_media_say() -> None:
    official = replace(
        view("official", 4_312_600),
        provider="人民银行",
        source_reference="pbc:sf",
        certification_status="certified",
    )
    media = (view("a", 4_312_600), view("b", 4_512_600))

    assert select_among((*media, official), tolerance=None) == (official, None)
    assert select_among(media, tolerance=None)[1] == "value_disagreement"
    # A provider's pages: its newest first.
    newer = replace(view("c", 4_512_600), available_at=KNOWN + timedelta(hours=1))
    assert select_among((view("a", 4_312_600), newer), tolerance=None)[0] == newer


@pytest.mark.usefixtures("runtime_clock")
def test_media_values_within_half_a_percent_agree(paths: RuntimePaths) -> None:
    stock_claim(paths, "中国政府网", 4_312_600, GOV)
    stock_claim(paths, "东方财富", 4_313_000, EASTMONEY)

    assert stock(paths).selection_status == "selected"


@pytest.mark.usefixtures("runtime_clock")
def test_one_provider_s_pages_that_disagree_are_a_conflict_its_page_read_again_is_not(
    paths: RuntimePaths,
) -> None:
    stock_claim(paths, "新浪财经", 4_512_600, SINA)
    newer = stock_claim(paths, "新浪财经", 4_312_600, SINA, KNOWN + timedelta(hours=1))

    point = stock(paths)
    # The page read again gives its newest value only.
    assert (point.selection_status, point.selected_claim_id) == ("selected", newer)

    stock_claim(paths, "新浪财经", 4_512_600, SINA.replace("sf202507", "sf202507b"))
    assert stock(paths).selection_status == "conflicted"


def view(claim_id: str, value: float) -> ClaimView:
    return ClaimView(
        claim_id,
        "媒体",
        value,
        EvidenceValueState.REPORTED_VALUE,
        "亿元",
        f"{MEDIA_PAGE}:https://example.cn/{claim_id}#sha256=0",
        KNOWN,
        KNOWN,
        KNOWN,
        KNOWN,
        "not_applicable",
        "validated",
        None,
    )


@pytest.mark.parametrize(
    ("rechecked", "outcome", "losing"),
    [
        ((4_312_600.0,), SETTLED, ("b",)),
        # Within ADR-0033's tolerance of one side.
        ((4_313_000.0,), SETTLED, ("b",)),
        ((), UNSETTLED, ()),
        # Agreeing with neither side, or the recheck's own values disagreeing.
        ((4_412_600.0,), UNSETTLED, ()),
        ((4_312_600.0, 4_512_600.0), UNSETTLED, ()),
    ],
)
def test_a_recheck_settles_a_conflict_only_on_one_side(
    rechecked: tuple[float, ...], outcome: str, losing: tuple[str, ...]
) -> None:
    contested = (view("a", 4_312_600), view("b", 4_512_600))

    decided = decide(contested, rechecked)
    assert (decided[0], decided[3]) == (outcome, losing)


def test_a_recheck_agreeing_with_both_sides_does_not_settle() -> None:
    # 100.4 is within half a percent of both 100.0 and 100.8, which are not of each other.
    contested = (view("a", 100.0), view("b", 100.8), view("c", 110.0))

    assert decide(contested, (100.4,))[0] == UNSETTLED
    # Two values that agree with each other but each with another side: not settled,
    # whichever is read first.
    contested = (view("a", 100.0), view("b", 101.0))
    assert decide(contested, (100.4, 100.6))[0] == UNSETTLED
    assert decide(contested, (100.6, 100.4))[0] == UNSETTLED
    # Pages within the tolerance of each other are one side.
    contested = (view("a", 100.0), view("b", 100.1), view("c", 200.0))
    assert decide(contested, (100.0,))[2:] == (("a", "b"), ("c",))


def recheck_run(
    paths: RuntimePaths,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    candidates: list[dict[str, Any]],
    request_id: str,
) -> tuple[Any, RunRecord, Path]:
    """A full run's AI WebSearch adapter for July 2025's social financing stock, its CLI
    answering ``candidates``; the adapter, its run and the CLI's call log."""
    (tmp_path / request_id).mkdir()
    calls = install(tmp_path / request_id, monkeypatch, {})
    calls.with_name("plan.json").write_text(
        json.dumps(
            {
                "codex": {"mode": "ok", "candidates": candidates},
                "claude": {"mode": "ok", "candidates": []},
            }
        )
    )
    run = RunRepository(paths.database).submit_manual_full(
        target_business_date="2026-09-30",
        client_request_id=request_id,
        model_version_id=str(effective_model_manifest()["model_version_id"]),
        system_as_of=datetime.now(UTC) + timedelta(minutes=1),
    )
    scope = RetrievalScope(SF_GAP, ("CN_SF_TOTAL",), "2025-07", "P1", None, (SF_STOCK,))
    scope_run = replace(run, retrieval_scope=scope)
    RetrievalLedger(paths.database).bind_run(scope_run, EFFECTIVE_CATALOG_VERSION)
    adapter = ai_websearch_adapter(
        paths, run.run_id, scope_run, definition_version=EFFECTIVE_CATALOG_VERSION
    )
    return adapter, scope_run, calls


def made(calls: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in calls.read_text().splitlines()] if calls.exists() else []


@pytest.mark.usefixtures("runtime_clock")
def test_a_recheck_that_agrees_with_one_side_settles_the_conflict(
    paths: RuntimePaths, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    serve(monkeypatch, {GOV: page_of("2025年7月金融统计数据报告", str(SF_STOCK_ONLY["quote"]))})
    monkeypatch.delenv("PRING_CYCLE_AI_WEBSEARCH")
    right = stock_claim(paths, "新浪财经", 4_312_600, SINA)
    wrong = stock_claim(paths, "东方财富", 4_512_600, EASTMONEY)
    adapter, _run, calls = recheck_run(
        paths, tmp_path, monkeypatch, [SF_STOCK_ONLY], "recheck-settled"
    )

    assert adapter.rechecks_first()
    response = adapter(SF_GAP)

    # The disagreeing member was asked, once.
    [call] = made(calls)
    assert call["prompt"]["members"] == [{"metric_id": "CN_SF_TOTAL", "dimensions": STOCK}]
    assert (response.status, response.classification) == ("verified", "complete_model_input")
    point = stock(paths)
    assert (point.selection_status, point.selected_claim_id) == ("selected", right)
    # The other side stays listed and stored, never selected while these claims stand.
    assert wrong in {claim.claim_id for claim in point.claims}
    with database_connection(paths.database) as connection:
        [(outcome, value, winning, losing, contested, recheck)] = connection.execute(
            "SELECT outcome, settled_value, winning_claim_ids_json, losing_claim_ids_json, "
            "contested_claim_ids_json, recheck_claim_ids_json FROM media_conflict_recheck"
        ).fetchall()
    assert (outcome, value) == (SETTLED, 4_312_600)
    assert (json.loads(winning), json.loads(losing)) == ([right], [wrong])
    assert json.loads(contested) == sorted([right, wrong])
    # The recheck's own claim is its evidence: listed, not a side, not selected over a
    # source's own.
    [evidence] = json.loads(recheck)
    assert evidence in {claim.claim_id for claim in point.claims}
    assert not adapter.rechecks_first()

    # A new page sides with the other: the claims are no longer those judged.
    stock_claim(paths, "第一财经", 4_512_600, "https://www.yicai.com/news/2025081300.html")
    assert stock(paths).selection_status == "conflicted"
    adapter, _run, _calls = recheck_run(paths, tmp_path, monkeypatch, [], "recheck-changed")
    assert adapter.rechecks_first()


@pytest.mark.usefixtures("runtime_clock")
def test_a_settled_side_holds_over_the_other_page_s_older_value(
    paths: RuntimePaths, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The other side's page read twice: its older value is not what the recheck judged,
    but no side of the claims selected from either."""
    serve(monkeypatch, {GOV: page_of("2025年7月金融统计数据报告", str(SF_STOCK_ONLY["quote"]))})
    monkeypatch.delenv("PRING_CYCLE_AI_WEBSEARCH")
    right = stock_claim(paths, "新浪财经", 4_312_600, SINA)
    stock_claim(paths, "东方财富", 4_512_600, EASTMONEY)
    stock_claim(paths, "东方财富", 4_512_600, EASTMONEY, KNOWN + timedelta(hours=1))
    adapter, _run, _calls = recheck_run(
        paths, tmp_path, monkeypatch, [SF_STOCK_ONLY], "recheck-older"
    )

    adapter(SF_GAP)

    point = stock(paths)
    assert (point.selection_status, point.selected_claim_id) == ("selected", right)


@pytest.mark.usefixtures("runtime_clock")
def test_a_recheck_that_settles_nothing_keeps_the_conflict_until_a_new_claim_comes(
    paths: RuntimePaths, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    serve(monkeypatch, {})
    monkeypatch.delenv("PRING_CYCLE_AI_WEBSEARCH")
    stock_claim(paths, "新浪财经", 4_312_600, SINA)
    stock_claim(paths, "东方财富", 4_512_600, EASTMONEY)
    adapter, _run, calls = recheck_run(paths, tmp_path, monkeypatch, [], "recheck-none")

    adapter(SF_GAP)

    assert len(made(calls)) == 1
    assert stock(paths).selection_status == "conflicted"
    with database_connection(paths.database) as connection:
        assert connection.execute("SELECT outcome FROM media_conflict_recheck").fetchall() == [
            (UNSETTLED,)
        ]

    # The next run holds the same claims: the verdict stands and nothing is asked.
    adapter, _run, calls = recheck_run(paths, tmp_path, monkeypatch, [], "recheck-again")
    assert not adapter.rechecks_first()
    response = adapter(SF_GAP)
    assert (response.status, response.classification) == (
        "not_attempted",
        MEDIA_CONFLICT_UNSETTLED,
    )
    assert made(calls) == []
    assert stock(paths).selection_status == "conflicted"

    # A new page's value makes the claims another conflict: it is rechecked.
    stock_claim(paths, "第一财经", 4_312_600, "https://www.yicai.com/news/2025081300.html")
    adapter, _run, _calls = recheck_run(paths, tmp_path, monkeypatch, [], "recheck-new")
    assert adapter.rechecks_first()
