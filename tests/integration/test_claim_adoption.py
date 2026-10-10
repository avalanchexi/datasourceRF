"""Claim adoption: whether each selected claim can be adopted, rechecked in one module.

The family rechecks each have their own tests with their sources; these cover what the
module decides -- which family a metric answers to, and what a built-in catalog skips.
The other families are exercised where their originals are built (registered model
inputs, ECB, LPR news, RRR backtrack, warrants, treasury).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from pring_cycle.acquisition import AcquisitionRepository
from pring_cycle.claim_adoption import ClaimAdoption, MetricAdoption
from pring_cycle.core_history import refresh_core_history
from pring_cycle.evidence import (
    AsOfMode,
    EvidenceRepository,
    EvidenceValueState,
    MetricSeriesPoint,
    SourceClaimInput,
)
from pring_cycle.models import (
    EFFECTIVE_CATALOG_VERSION,
    ModelRepository,
    effective_model_manifest,
)
from pring_cycle.news_rules import (
    AI_WEBSEARCH,
    MEDIA_PAGE,
    TUSHARE_NEWS,
    MatchedQuote,
    add_subject_column,
    matched_quotes,
    member_period,
    member_unit,
    news_claims_no_longer_stated,
    record_matched_quotes,
    restore_suspect_subjects,
    suspect_news_claims,
    text_hash,
)
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.source_adapters import CoreInputValidator, TushareCoreAdapter
from pring_cycle.storage import SCHEMA_HEAD, database_connection, migrate_database
from pring_cycle.treasury_context import treasury_claims_matching_acquisitions
from pring_cycle.tushare_context import TushareContextAdapter
from tests.fixtures.model_registration import prepared_request, save, submit
from tests.integration.test_core_history_refresh import core_response
from tests.integration.test_gap_source_repairs import treasury_response
from tests.integration.test_receipt_counts import _upgrade


def adoption_of(
    paths: RuntimePaths,
    metric_id: str,
    definition_version: str,
    *,
    as_of: datetime,
    mode: AsOfMode = AsOfMode.SYSTEM,
    period: str | None = None,
) -> MetricAdoption:
    """What the module makes of the metric's selected series at ``as_of``."""
    evidence = EvidenceRepository(paths.database)
    points = evidence.metric_series(
        metric_id, mode=mode, as_of=as_of, definition_version=definition_version
    )
    return ClaimAdoption(evidence, definition_version=definition_version, mode=mode).check(
        {metric_id: points}, period=period
    )[metric_id]


def damage_original(paths: RuntimePaths, claim_id: str) -> None:
    """Overwrite the raw original of every receipt the claim was taken from."""
    links = EvidenceRepository(paths.database).source_claim_acquisitions_many((claim_id,))
    assert links[claim_id]
    for link in links[claim_id]:
        digest = link.receipt.raw_hash
        assert digest is not None
        (paths.artifacts / digest[:2] / digest).write_bytes(b"damaged original")


def registered_version(paths: RuntimePaths, capsys: pytest.CaptureFixture[str]) -> str:
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    return str(ModelRepository(paths.database).manifest(model_id)["metric_catalog_version"])


@pytest.fixture
def paths(tmp_path: Path) -> RuntimePaths:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    return paths


@pytest.mark.usefixtures("runtime_clock")
def test_a_registered_core_close_is_adoptable_only_while_its_original_agrees(
    paths: RuntimePaths, capsys: pytest.CaptureFixture[str]
) -> None:
    version = registered_version(paths, capsys)
    refresh_core_history(
        paths,
        TushareCoreAdapter("fixture-secret", transport=core_response),
        start=date(2026, 8, 3),
        end=date(2026, 8, 3),
        definition_version=version,
    )
    evidence = EvidenceRepository(paths.database)
    now = datetime.now(UTC)
    (point,) = evidence.metric_series(
        "CN_EQUITY_CORE_000985", mode=AsOfMode.SYSTEM, as_of=now, definition_version=version
    )
    assert point.selected_claim_id is not None

    kept = adoption_of(paths, "CN_EQUITY_CORE_000985", version, as_of=now)
    assert kept.rechecked
    assert kept.adoptable == {point.selected_claim_id}
    assert CoreInputValidator(evidence, (point.selected_claim_id,)).is_valid(
        "CN_EQUITY_CORE_000985", point
    )

    (receipt,) = (
        receipt
        for receipt in AcquisitionRepository(paths.database, paths.artifacts).history()
        if receipt.parameters.get("ts_code") == "000985.CSI"
    )
    assert receipt.raw_hash is not None
    (paths.artifacts / receipt.raw_hash[:2] / receipt.raw_hash).write_bytes(b"damaged")

    damaged = adoption_of(paths, "CN_EQUITY_CORE_000985", version, as_of=now)
    assert damaged.adoptable == frozenset()
    assert damaged.not_adoptable == {point.selected_claim_id}
    assert not CoreInputValidator(evidence, (point.selected_claim_id,)).is_valid(
        "CN_EQUITY_CORE_000985", point
    )
    # Only the damaged core's original was touched.
    assert adoption_of(paths, "CN_BOND_CORE_000012", version, as_of=now).adoptable


def core_claim(day: date, source_reference: str) -> SourceClaimInput:
    known = datetime.combine(day, datetime.min.time(), tzinfo=UTC)
    return SourceClaimInput(
        metric_id="CN_EQUITY_CORE_000985",
        definition_version="metric-catalog-v0001",
        period_kind="business_day",
        period_start=day.isoformat(),
        period_end=day.isoformat(),
        dimensions={},
        value=1000.0,
        value_state=EvidenceValueState.REPORTED_VALUE,
        unit="index_points",
        provider="tushare",
        source_reference=source_reference,
        release_event_id=f"fixture:core:{day}",
        release_at=known,
        public_available_at=known,
        fetched_at=known,
        available_at=known,
        certification_status="certified",
        quality_status="validated",
    )


def test_a_builtin_catalog_is_not_rechecked_but_a_core_still_names_its_source(
    paths: RuntimePaths,
) -> None:
    named, misnamed = date(2026, 8, 27), date(2026, 8, 28)
    stored = EvidenceRepository(paths.database).append_source_claims(
        (
            core_claim(named, f"tushare:index_daily:000985.CSI:{named}"),
            # A reference naming another day is not this close's source.
            core_claim(misnamed, f"tushare:index_daily:000985.CSI:{named}"),
        )
    )

    adoption = adoption_of(
        paths,
        "CN_EQUITY_CORE_000985",
        "metric-catalog-v0001",
        as_of=datetime(2026, 8, 28, 13, tzinfo=UTC),
    )

    assert not adoption.rechecked
    assert adoption.adoptable == {stored[0].claim_id}
    assert adoption.not_adoptable == {stored[1].claim_id}


def test_a_metric_no_family_owns_keeps_every_selected_claim(paths: RuntimePaths) -> None:
    adoption = ClaimAdoption(
        EvidenceRepository(paths.database), definition_version="synthetic-registered"
    ).check({"UNOWNED_METRIC": ()})

    assert adoption["UNOWNED_METRIC"] == MetricAdoption(frozenset(), frozenset())
    assert not adoption["UNOWNED_METRIC"].rechecked


@pytest.mark.usefixtures("runtime_clock")
def test_treasury_yields_from_us_tycr_are_adoptable_while_their_delivery_agrees(
    paths: RuntimePaths,
) -> None:
    # The yields' values here moved from test_gap_source_repairs, which keeps the gap list.
    ModelRepository(paths.database).register(effective_model_manifest())
    adapter = TushareContextAdapter("fixture-secret", transport=treasury_response)
    adapter.acquire_scalars(
        paths,
        lambda: adapter.treasury_yields(start_date=date(2026, 8, 24), end_date=date(2026, 8, 28)),
        definition_version=EFFECTIVE_CATALOG_VERSION,
    )
    evidence = EvidenceRepository(paths.database)
    now = datetime.now(UTC)
    series = {
        metric_id: evidence.metric_series(
            metric_id,
            mode=AsOfMode.SYSTEM,
            as_of=now,
            definition_version=EFFECTIVE_CATALOG_VERSION,
        )
        for metric_id in ("UST2Y_NOMINAL_YIELD", "UST10Y_NOMINAL_YIELD")
    }
    assert {p.selected_value for p in series["UST2Y_NOMINAL_YIELD"]} == {3.5}
    assert {p.selected_value for p in series["UST10Y_NOMINAL_YIELD"]} == {4.25}
    for metric_id, points in series.items():
        adoption = adoption_of(paths, metric_id, EFFECTIVE_CATALOG_VERSION, as_of=now)
        assert adoption.rechecked
        assert adoption.adoptable == {p.selected_claim_id for p in points}
        assert (
            treasury_claims_matching_acquisitions(
                evidence, {metric_id: points}, definition_version=EFFECTIVE_CATALOG_VERSION
            )
            == adoption.adoptable
        )

    (receipt,) = AcquisitionRepository(paths.database, paths.artifacts).history()
    assert receipt.raw_hash is not None
    (paths.artifacts / receipt.raw_hash[:2] / receipt.raw_hash).write_bytes(b"damaged")

    for metric_id, points in series.items():
        damaged = adoption_of(paths, metric_id, EFFECTIVE_CATALOG_VERSION, as_of=now)
        assert damaged.adoptable == frozenset()
        assert damaged.not_adoptable == {p.selected_claim_id for p in points}
        assert not treasury_claims_matching_acquisitions(
            evidence, {metric_id: points}, definition_version=EFFECTIVE_CATALOG_VERSION
        )


def news_claim(
    paths: RuntimePaths,
    version: str,
    provider: str,
    value: float,
    quote: str,
    known: datetime,
    *,
    measure: str = "ytd_real_yoy",
    title: str = "标题",
    subject: str | None = None,
    url: str | None = None,
    body_hash: str | None = None,
) -> str:
    """A 2026-08 industrial value claim kept with its matched quote, as stored whatever rules
    took it then; year to date unless ``measure`` says otherwise. Its page is ``url``, else
    its body's hash, by default its quote's own."""
    dimensions = {"measure": measure}
    kind, start, end = member_period("CN_INDUSTRIAL_VA", dimensions, "2026-08")
    [claim] = EvidenceRepository(paths.database).append_source_claims(
        (
            SourceClaimInput(
                metric_id="CN_INDUSTRIAL_VA",
                definition_version=version,
                period_kind=kind,
                period_start=start,
                period_end=end,
                dimensions=dimensions,
                value=value,
                value_state=EvidenceValueState.REPORTED_VALUE,
                unit=member_unit("CN_INDUSTRIAL_VA", dimensions, "2026-08", "%"),
                provider=provider,
                source_reference=f"{provider}:{quote}",
                release_event_id=f"fixture:news:{provider}:{value}:{known}",
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
                    {"tushare_news": TUSHARE_NEWS, "ai_websearch": AI_WEBSEARCH}.get(
                        provider, MEDIA_PAGE
                    ),
                    quote,
                    title,
                    provider,
                    None,
                    body_hash or text_hash(quote),
                    url,
                    subject,
                ),
            ),
        )
    return claim.claim_id


@pytest.mark.usefixtures("runtime_clock")
def test_a_kept_news_claim_the_current_rules_no_longer_state_is_no_candidate(
    paths: RuntimePaths, capsys: pytest.CaptureFixture[str]
) -> None:
    """Lookback 20: a news claim is read again under the rules of the day, not those that
    took it. Guangdong's "全省" 6.1, stored before the rules knew a province, is neither
    listed nor selected, even for a period with no national value; it does not hide an
    older national claim of its provider or outrank another provider's either."""
    version = registered_version(paths, capsys)
    evidence = EvidenceRepository(paths.database)
    first = datetime(2026, 9, 16, 2, tzinfo=UTC)
    local = (
        # 9850d479 (TuShare news) and 8dc3a4b8 (CLS) as the real run kept them.
        news_claim(
            paths,
            version,
            "tushare_news",
            6.1,
            "1—8月，全省规模以上工业增加值同比增长6.1%。",
            first + timedelta(days=5),
        ),
        news_claim(
            paths,
            version,
            "cls",
            6.1,
            "广东：1—8月份全省规模以上工业增加值同比增长6.1%很抱歉，当前没有启用javascript，网站无法正常访问。",
            first + timedelta(days=5),
        ),
    )
    as_of = first + timedelta(days=10)

    def series(preloaded: bool = False) -> tuple[MetricSeriesPoint, ...]:
        # A fresh repository each time: one preloads only what it held when asked.
        repository = EvidenceRepository(paths.database)
        if preloaded:
            repository.preload_metric_series({("CN_INDUSTRIAL_VA", version)})
        return repository.metric_series(
            "CN_INDUSTRIAL_VA", mode=AsOfMode.SYSTEM, as_of=as_of, definition_version=version
        )

    assert series() == series(preloaded=True) == ()
    observation = str(
        query_one(paths, "SELECT observation_id FROM source_claim WHERE claim_id=?", local[0])
    )
    assert evidence.query(observation, mode=AsOfMode.SYSTEM, as_of=as_of).claims == ()

    national = news_claim(
        paths, version, "tushare_news", 5.3, "1—8月份，规模以上工业增加值同比增长5.3%。", first
    )
    (point,) = series()
    assert [claim.claim_id for claim in point.claims] == [national]
    assert (point.selected_claim_id, point.selected_value) == (national, 5.3)
    assert [
        c.claim_id for c in evidence.query(observation, mode=AsOfMode.SYSTEM, as_of=as_of).claims
    ] == [national]
    assert series(preloaded=True) == (point,)
    adoption = ClaimAdoption(evidence, definition_version=version).check(
        {"CN_INDUSTRIAL_VA": (point,)}
    )["CN_INDUSTRIAL_VA"]
    assert adoption.adoptable == {national}
    # The claims themselves are kept as stored.
    assert (
        query_one(
            paths,
            "SELECT count(*) FROM source_claim WHERE quality_status='validated' AND claim_id IN "
            "(SELECT value FROM json_each(?))",
            json.dumps(local),
        )
        == 2
    )


@pytest.mark.usefixtures("runtime_clock")
def test_a_kept_news_claim_whose_title_or_subject_names_a_place_is_no_candidate(
    paths: RuntimePaths, capsys: pytest.CaptureFixture[str]
) -> None:
    """Lookback 22: Guangdong's month 6.9 (c8dcb77e) names no subject in its quote; its page
    is titled Guangdong's and its paragraph's subject clause is "全省". Kept with either, it
    is neither listed nor selected, even for a period with no national value. A quote kept
    before either was recorded is read as lookback 20 reads it, unless AI WebSearch kept it:
    that was never read on its page (lookback 26)."""
    version = registered_version(paths, capsys)
    evidence = EvidenceRepository(paths.database)
    first = datetime(2026, 9, 16, 2, tzinfo=UTC)
    month = "8月份，规模以上工业增加值同比增长6.9%，比上月加快1.0个百分点。"
    local = (
        news_claim(
            paths,
            version,
            "cls",
            6.9,
            month,
            first + timedelta(days=5),
            measure="current_month_real_yoy",
            title="广东：1—8月份全省规模以上工业增加值同比增长6.1%",
            subject="",
        ),
        news_claim(
            paths,
            version,
            "tushare_news",
            6.9,
            month,
            first + timedelta(days=5),
            measure="current_month_real_yoy",
            title="8月经济数据",
            subject="1—8月份全省规模以上工业增加值同比增长6.1%",
        ),
    )
    with database_connection(paths.database) as connection:
        kept = {
            str(row["claim_id"]): (row["title"], row["subject"])
            for row in matched_quotes(connection, local)
        }
    assert kept == {
        local[0]: ("广东：1—8月份全省规模以上工业增加值同比增长6.1%", ""),
        local[1]: ("8月经济数据", "1—8月份全省规模以上工业增加值同比增长6.1%"),
    }
    as_of = first + timedelta(days=10)

    def series(preloaded: bool = False) -> tuple[MetricSeriesPoint, ...]:
        repository = EvidenceRepository(paths.database)
        if preloaded:
            repository.preload_metric_series({("CN_INDUSTRIAL_VA", version)})
        return repository.metric_series(
            "CN_INDUSTRIAL_VA", mode=AsOfMode.SYSTEM, as_of=as_of, definition_version=version
        )

    assert series() == series(preloaded=True) == ()

    # Kept before lookback 22 by AI WebSearch: no subject clause and no title. Its sentence
    # was never read on its page, so it waits for it (lookback 26).
    unread = news_claim(
        paths,
        version,
        "ai_websearch",
        5.2,
        "8月份，规模以上工业增加值同比增长5.2%。",
        first,
        measure="current_month_real_yoy",
        title="",
    )
    assert series() == series(preloaded=True) == ()
    with database_connection(paths.database) as connection:
        assert suspect_news_claims(connection) == (unread,)

    # Kept before lookback 22 from TuShare news: no subject clause, read on its quote and title.
    legacy = news_claim(
        paths,
        version,
        "tushare_news",
        5.2,
        "8月份，规模以上工业增加值同比增长5.2%。",
        first,
        measure="current_month_real_yoy",
        title="8月份国民经济运行",
    )
    (point,) = (p for p in series() if p.dimensions == {"measure": "current_month_real_yoy"})
    assert [claim.claim_id for claim in point.claims] == [legacy]
    assert (point.selected_claim_id, point.selected_value) == (legacy, 5.2)
    adoption = ClaimAdoption(evidence, definition_version=version).check(
        {"CN_INDUSTRIAL_VA": (point,)}
    )["CN_INDUSTRIAL_VA"]
    assert adoption.adoptable == {legacy}


# Kept before lookback 22, as AI WebSearch, a media page and TuShare news kept them: Guangdong's
# month 6.9 (c8dcb77e) names no place in its quote.
MONTH = "8月份，规模以上工业增加值同比增长6.9%，比上月加快1.0个百分点。"
PROVINCE = "1—8月，全省规模以上工业增加值同比增长6.1%。"


@pytest.mark.usefixtures("runtime_clock")
def test_a_kept_news_claim_whose_page_names_a_place_elsewhere_waits_for_its_subject(
    paths: RuntimePaths, capsys: pytest.CaptureFixture[str]
) -> None:
    """Lookback 23: a claim kept before subject clauses were recorded is a suspect when
    another claim of its page (its address, else its body's hash) is read as a place's:
    its quote and title pass, but the clause its figure was read under is unknown. It is
    neither listed nor selected, nor adoptable once selected. A page whose other claims fail
    for another reason, or a claim kept with its clause, makes no suspect."""
    version = registered_version(paths, capsys)
    evidence = EvidenceRepository(paths.database)
    first = datetime(2026, 9, 16, 2, tzinfo=UTC)
    cls = "https://www.cls.cn/detail/2140000"
    suspect = news_claim(
        paths, version, "cls", 6.9, MONTH, first, measure="current_month_real_yoy", url=cls
    )
    as_of = first + timedelta(days=10)

    def series(preloaded: bool = False) -> tuple[MetricSeriesPoint, ...]:
        repository = EvidenceRepository(paths.database)
        if preloaded:
            repository.preload_metric_series({("CN_INDUSTRIAL_VA", version)})
        return repository.metric_series(
            "CN_INDUSTRIAL_VA", mode=AsOfMode.SYSTEM, as_of=as_of, definition_version=version
        )

    def adoptable(point: MetricSeriesPoint) -> frozenset[str]:
        return (
            ClaimAdoption(evidence, definition_version=version)
            .check({"CN_INDUSTRIAL_VA": (point,)})["CN_INDUSTRIAL_VA"]
            .adoptable
        )

    # Its page's other claims are no longer stated, but neither is a place's: one states
    # July's, not August's; one states two values of its member, contradicting itself.
    news_claim(
        paths, version, "cls", 5.8, "1—7月份，规模以上工业增加值同比增长5.8%。", first, url=cls
    )
    news_claim(
        paths,
        version,
        "cls",
        5.2,
        "1—8月份，规模以上工业增加值同比增长5.2%；1—8月份，规模以上工业增加值同比增长5.3%。",
        first,
        url=cls,
    )
    (point,) = series()
    assert (point.selected_claim_id, point.selected_value) == (suspect, 6.9)
    assert adoptable(point) == {suspect}
    with database_connection(paths.database) as connection:
        assert suspect_news_claims(connection) == ()

    news_claim(paths, version, "cls", 6.1, PROVINCE, first, url=cls)
    with database_connection(paths.database) as connection:
        assert suspect_news_claims(connection) == (suspect,)
    assert series() == series(preloaded=True) == ()
    observation = str(
        query_one(paths, "SELECT observation_id FROM source_claim WHERE claim_id=?", suspect)
    )
    assert evidence.query(observation, mode=AsOfMode.SYSTEM, as_of=as_of).claims == ()
    assert adoptable(point) == frozenset()

    # Taken since, its page's month figure keeps the clause it was read under: none.
    kept = news_claim(
        paths,
        version,
        "cls",
        6.9,
        MONTH,
        first + timedelta(days=1),
        measure="current_month_real_yoy",
        url=cls,
        subject="",
    )
    (point,) = series()
    assert [claim.claim_id for claim in point.claims] == [kept]
    assert adoptable(point) == {kept}


@pytest.mark.usefixtures("runtime_clock")
def test_a_suspect_news_claim_is_read_again_with_the_subject_its_page_gives(
    paths: RuntimePaths, capsys: pytest.CaptureFixture[str]
) -> None:
    """Lookback 23: each suspect's page is fetched again, one at a time. The clause the page
    gives its figure is kept, with the page's title where the quote had none, and the claim
    is read with them: a place's is no candidate, the country's is. A page that cannot be
    had or no longer gives the figure, or a claim with no address, leaves the suspect as it
    was, not taken; only a claim with no clause is written, so a second pass fetches only
    the pages left."""
    version = registered_version(paths, capsys)
    first = datetime(2026, 9, 16, 2, tzinfo=UTC)
    guangdong, country, gone, moved = (f"https://www.cls.cn/detail/214000{n}" for n in range(4))
    fetch_pages: list[str | None] = []

    def suspect_of(page: str | None, provider: str, title: str, body: str | None = None) -> str:
        # Each page its own release: a claim is one per provider, value and release.
        known = first + timedelta(hours=len(fetch_pages))
        fetch_pages.append(page)
        news_claim(paths, version, provider, 6.1, PROVINCE, known, url=page, body_hash=body)
        return news_claim(
            paths,
            version,
            provider,
            6.9,
            MONTH,
            known,
            measure="current_month_real_yoy",
            title=title,
            url=page,
            body_hash=body,
        )

    local = suspect_of(guangdong, "ai_websearch", "")
    national = suspect_of(country, "cls", "8月份国民经济运行")
    unavailable = suspect_of(gone, "cls", "标题")
    unstated = suspect_of(moved, "cls", "标题")
    unaddressed = suspect_of(None, "tushare_news", "资讯", "1" * 64)
    pages = {
        # A mixed page: the country's 6.9 first, then Guangdong's, which the quote is.
        guangdong: (
            "<html><head><title>8月份各地经济数据</title></head><body>"
            "<p>8月份，全国规模以上工业增加值同比增长6.9%。</p>"
            f"<p>1—8月份，全省规模以上工业增加值同比增长6.1%；{MONTH}</p></body></html>"
        ),
        # The quote's own paragraph names the country before it.
        country: (
            "<html><head><title>8月份国民经济运行</title></head><body><p>统计局发布。</p>"
            f"<p>全国规模以上工业生产加快，{MONTH}</p></body></html>"
        ),
        moved: "<html><head><title>页面已更新</title></head><body><p>已更新。</p></body></html>",
    }
    fetched: list[str] = []

    def fetch(url: str) -> str | None:
        fetched.append(url)
        return pages.get(url)

    restored = restore_suspect_subjects(paths.database, fetch)
    assert sorted(fetched) == sorted((guangdong, country, gone, moved))
    assert {r.claim_id: r.outcome for r in restored} == {
        local: "local",
        national: "national",
        unavailable: "unavailable",
        unstated: "unavailable",
        unaddressed: "unavailable",
    }
    # The original of each page had, recorded whatever it gave.
    assert {r.claim_id: r.content_sha256 for r in restored} == {
        local: text_hash(pages[guangdong]),
        national: text_hash(pages[country]),
        unavailable: None,
        unstated: text_hash(pages[moved]),
        unaddressed: None,
    }
    with database_connection(paths.database) as connection:
        kept = {
            str(row["claim_id"]): (row["title"], row["subject"])
            for row in matched_quotes(
                connection, (local, national, unavailable, unstated, unaddressed)
            )
        }
        assert news_claims_no_longer_stated(connection, ("CN_INDUSTRIAL_VA",)) >= {
            local,
            unavailable,
            unstated,
            unaddressed,
        }
        assert national not in news_claims_no_longer_stated(connection, ("CN_INDUSTRIAL_VA",))
        assert suspect_news_claims(connection) == tuple(
            sorted((unavailable, unstated, unaddressed))
        )
    assert kept == {
        local: ("8月份各地经济数据", "全省规模以上工业增加值同比增长6.1%"),
        national: ("8月份国民经济运行", "全国规模以上工业生产加快"),
        unavailable: ("标题", None),
        unstated: ("标题", None),
        unaddressed: ("资讯", None),
    }
    (point,) = EvidenceRepository(paths.database).metric_series(
        "CN_INDUSTRIAL_VA",
        mode=AsOfMode.SYSTEM,
        as_of=first + timedelta(days=10),
        definition_version=version,
    )
    assert [claim.claim_id for claim in point.claims] == [national]

    fetched.clear()
    again = restore_suspect_subjects(paths.database, fetch)
    assert sorted(fetched) == sorted((gone, moved))
    assert {r.claim_id: r.outcome for r in again} == {
        unavailable: "unavailable",
        unstated: "unavailable",
        unaddressed: "unavailable",
    }


@pytest.mark.usefixtures("runtime_clock")
def test_ai_websearch_quotes_kept_before_their_pages_were_read_wait_for_them(
    paths: RuntimePaths, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Lookback 26: the 35 AI WebSearch quotes kept before were the CLI's sentences alone.
    Each is a suspect, neither listed nor selected, until its page is read once more as a
    media page is, its original kept: the country's page restores it, a place's page or one
    not had leaves it out. A page with two of them is fetched once."""
    from pring_cycle.search_evidence import restore_suspect_pages
    from tests.integration.test_ai_websearch import page_of, serve

    version = registered_version(paths, capsys)
    first = datetime(2026, 9, 16, 2, tzinfo=UTC)
    country, guangdong, gone = (f"https://finance.sina.com.cn/doc-{n}.shtml" for n in range(3))
    elsewhere = "https://finance.example.com/va"

    def kept(url: str, value: float, hours: int) -> str:
        """The month's figure as the CLI gave it, alone: no title, no subject clause."""
        return news_claim(
            paths,
            version,
            "ai_websearch",
            value,
            MONTH.replace("6.9", str(value)),
            first + timedelta(hours=hours),
            measure="current_month_real_yoy",
            title="",
            url=url,
        )

    month = kept(country, 6.9, 0)
    # The same page's year to date, by its own sentence: the country's 5.3.
    year = news_claim(
        paths,
        version,
        "ai_websearch",
        5.3,
        "1—8月份，规模以上工业增加值同比增长5.3%。",
        first,
        title="",
        url=country,
    )
    local = kept(guangdong, 6.8, 1)
    missing = kept(gone, 6.7, 2)
    foreign = kept(elsewhere, 6.6, 3)
    as_of = first + timedelta(days=10)

    def series() -> dict[str, list[str]]:
        return {
            point.dimensions["measure"]: [claim.claim_id for claim in point.claims]
            for point in EvidenceRepository(paths.database).metric_series(
                "CN_INDUSTRIAL_VA", mode=AsOfMode.SYSTEM, as_of=as_of, definition_version=version
            )
        }

    assert series() == {}
    with database_connection(paths.database) as connection:
        assert set(suspect_news_claims(connection)) == {month, year, local, missing, foreign}

    pages = {
        country: page_of(
            "国家统计局：8月份规模以上工业增加值增长6.9%",
            f"全国规模以上工业生产加快，{MONTH}",
            "1—8月份，规模以上工业增加值同比增长5.3%。",
        ),
        guangdong: page_of(
            "广东：1—8月份全省规模以上工业增加值同比增长6.1%", MONTH.replace("6.9", "6.8")
        ),
    }
    fetched = serve(monkeypatch, pages)
    restored = {item.restored.claim_id: item for item in restore_suspect_pages(paths)}

    # One request per page, none for a host neither official nor whitelisted.
    assert sorted(fetched) == sorted((country, guangdong, gone))
    assert {claim: item.restored.outcome for claim, item in restored.items()} == {
        month: "national",
        year: "national",
        local: "local",
        missing: "unavailable",
        foreign: "unavailable",
    }
    receipts = {
        r.acquisition_id: r
        for r in AcquisitionRepository(paths.database, paths.artifacts).history()
    }
    for claim in (month, year, local):
        item = restored[claim]
        assert item.acquisition_id is not None
        receipt = receipts[item.acquisition_id]
        assert (receipt.api_name, receipt.raw_hash) == ("media_page_get", item.raw_hash)
        assert item.restored.content_sha256 == text_hash(pages[str(item.restored.url)].decode())
    assert (restored[missing].raw_hash, restored[foreign].raw_hash) == (None, None)
    with database_connection(paths.database) as connection:
        stored = {
            str(row["claim_id"]): (row["title"], row["subject"])
            for row in matched_quotes(connection, (month, year, local, missing, foreign))
        }
        assert set(suspect_news_claims(connection)) == {missing, foreign}
    assert stored[month] == (
        "国家统计局：8月份规模以上工业增加值增长6.9%",
        "全国规模以上工业生产加快",
    )
    assert stored[local][0] == "广东：1—8月份全省规模以上工业增加值同比增长6.1%"
    assert stored[missing] == stored[foreign] == ("", None)
    assert series() == {"current_month_real_yoy": [month], "ytd_real_yoy": [year]}


def query_one(paths: RuntimePaths, sql: str, *parameters: object) -> object:
    with database_connection(paths.database) as connection:
        return connection.execute(sql, parameters).fetchone()[0]


def test_a_quote_kept_before_subject_clauses_were_recorded_upgrades_without_one(
    tmp_path: Path,
) -> None:
    """Lookback 22 adds the subject clause to the matched quote table; a quote kept before
    has none, and its other columns stay as they were."""
    database = tmp_path / "runtime.sqlite3"
    _upgrade(database, "0032_receipt_counts")
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO claim_matched_quote VALUES ('claim-old', 'media_page', '原话', '标题', "
            "'财联社', NULL, ?, NULL, 'news-rules-v0001')",
            ("0" * 64,),
        )
    connection.close()

    migrate_database(database)
    with sqlite3.connect(database) as connection:
        add_subject_column(connection)  # safe to repeat
        assert connection.execute(
            "SELECT claim_id, quote, title, subject FROM claim_matched_quote"
        ).fetchall() == [("claim-old", "原话", "标题", None)]
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            SCHEMA_HEAD,
        )
        upgraded = connection.execute("PRAGMA table_info(claim_matched_quote)").fetchall()
    connection.close()
    fresh = tmp_path / "fresh.sqlite3"
    migrate_database(fresh)
    with sqlite3.connect(fresh) as connection:
        assert connection.execute("PRAGMA table_info(claim_matched_quote)").fetchall() == upgraded
    connection.close()
