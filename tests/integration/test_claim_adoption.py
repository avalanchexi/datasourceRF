"""Claim adoption: whether each selected claim can be adopted, rechecked in one module.

The family rechecks each have their own tests with their sources; these cover what the
module decides -- which family a metric answers to, and what a built-in catalog skips.
The other families are exercised where their originals are built (registered model
inputs, ECB, LPR news, RRR backtrack, warrants, treasury).
"""

from __future__ import annotations

import json
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
    MEDIA_PAGE,
    TUSHARE_NEWS,
    MatchedQuote,
    member_period,
    member_unit,
    record_matched_quotes,
)
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.source_adapters import CoreInputValidator, TushareCoreAdapter
from pring_cycle.storage import database_connection
from pring_cycle.treasury_context import treasury_claims_matching_acquisitions
from pring_cycle.tushare_context import TushareContextAdapter
from tests.fixtures.model_registration import prepared_request, save, submit
from tests.integration.test_core_history_refresh import core_response
from tests.integration.test_gap_source_repairs import treasury_response


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
    paths: RuntimePaths, version: str, provider: str, value: float, quote: str, known: datetime
) -> str:
    """A 2026-08 year-to-date industrial value claim kept with its matched quote, as stored
    whatever rules took it then."""
    dimensions = {"measure": "ytd_real_yoy"}
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
                    TUSHARE_NEWS if provider == "tushare_news" else MEDIA_PAGE,
                    quote,
                    "标题",
                    provider,
                    None,
                    "0" * 64,
                    None,
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


def query_one(paths: RuntimePaths, sql: str, *parameters: object) -> object:
    with database_connection(paths.database) as connection:
        return connection.execute(sql, parameters).fetchone()[0]
