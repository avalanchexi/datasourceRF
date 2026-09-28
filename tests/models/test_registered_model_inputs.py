"""Inputs of families that a registered catalog brings: breadth, credit, valuation and more."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.acquisition import AcquisitionRepository
from pring_cycle.artifacts import store_artifact
from pring_cycle.cli import main
from pring_cycle.context_projection import build_context_projection
from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.models import (
    ModelRepository,
)
from pring_cycle.official_context import (
    ingest_official_context_document,
)
from pring_cycle.official_lpr import ingest_lpr_document
from pring_cycle.retrieval_ledger import RetrievalLedger
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.search_discovery import (
    SearchHttpResponse,
    build_search_query,
    search_discovery_adapter,
)
from pring_cycle.search_evidence import select_retrieval_input
from pring_cycle.tushare_context import ContextScalar, TushareContextAdapter, ingest_context_scalars
from tests.fixtures.model_registration import (
    bind_synthetic_review,
    encode,
    prepared_request,
    save,
    submit,
)


def admitted_gdp_manifest(
    paths: RuntimePaths, capsys: pytest.CaptureFixture[str], *, side: str = ""
) -> dict[str, Any]:
    # A full candidate with synthetic review bindings; no actual source is certified.
    request, _ = prepared_request(paths)
    definition = next(
        item for item in request["manifest"]["metric_definitions"] if item["metric_id"] == "CN_GDP"
    )
    definition["certification_status"] = "certified"
    if side:
        request["manifest"]["metric_catalog_version"] += "-" + side
        for item in request["manifest"]["metric_definitions"]:
            item["definition_version"] = request["manifest"]["metric_catalog_version"]
        if side == "candidate":
            definition["source_candidates"] = [
                *definition["source_candidates"],
                "https://www.stats.gov.cn/synthetic-review",
            ]
    package_hash = request["package_hashes"][0]
    package = json.loads((paths.artifacts / package_hash[:2] / package_hash).read_bytes())
    package["definition_bindings"]["CN_GDP"] = hashlib.sha256(encode(definition)).hexdigest()
    if side:
        package["definition_bindings"] = {
            item["metric_id"]: hashlib.sha256(encode(item)).hexdigest()
            for item in request["manifest"]["metric_definitions"]
            if item["metric_id"] in package["definition_bindings"]
        }
    bind_synthetic_review(paths, request, package)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    return ModelRepository(paths.database).manifest(model_id)


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize(
    "period,digest,url,levels,growth",
    [
        (
            "2025-Q3",
            "0f7c85e52242f3e1905d3313aa744028f51d48f60bcff899b712da400f135a5c",
            "https://www.stats.gov.cn/sj/zxfb/202510/t20251021_1961646.html",
            (1015036, 58061, 364020, 592955),
            (4.8, 4.0, 4.2, 5.4),
        ),
        (
            "2025-Q4",
            "9d9bc9ece5d52a9ba07d6d9ed01e0d865b4d72b385c1b2a9873501e2d5532765",
            "https://www.stats.gov.cn/sj/zxfb/202601/t20260120_1962349.html",
            (1401879, 93347, 499653, 808879),
            (4.5, 4.2, 3.4, 5.2),
        ),
    ],
)
def test_registered_gdp_preserves_q3_q4_official_table_layouts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    period: str,
    digest: str,
    url: str,
    levels: tuple[int, ...],
    growth: tuple[float, ...],
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifest = admitted_gdp_manifest(paths, capsys)
    version = manifest["metric_catalog_version"]
    raw = (
        Path(__file__).parents[2]
        / ".scratch/pring-data-acquisition-repair/evidence-macro-normalized"
        / digest
    ).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == digest
    imported = ingest_official_context_document(
        paths,
        raw,
        family="nbs_gdp",
        source_url=url,
        expected_period=period,
        fetched_at=datetime.now(UTC),
        definition_version=version,
    )
    repository = EvidenceRepository(paths.database)
    points = repository.metric_series(
        "CN_GDP", mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC), definition_version=version
    )
    assert len(points) == 8
    assert {point.selected_claim_id for point in points} == set(imported.claim_ids)
    # Independently read table literals: cumulative levels and current-quarter growth.
    for aggregate, level, yoy in zip(
        ("total", "primary", "secondary", "tertiary"), levels, growth, strict=True
    ):
        assert {
            point.dimensions["measure"]: point.selected_value
            for point in points
            if point.dimensions["aggregate"] == aggregate
        } == {
            "nominal_ytd_level": level,
            "real_quarter_yoy": yoy,
        }


def admitted_treasury_manifest(
    paths: RuntimePaths, capsys: pytest.CaptureFixture[str]
) -> dict[str, Any]:
    # Synthetic source review binds the official CSV identity, never the old TuShare fields.
    request, _ = prepared_request(paths)
    package_hash = request["package_hashes"][0]
    package = json.loads((paths.artifacts / package_hash[:2] / package_hash).read_bytes())
    columns = {"UST2Y_NOMINAL_YIELD": "2 Yr", "UST10Y_NOMINAL_YIELD": "10 Yr"}
    for definition in request["manifest"]["metric_definitions"]:
        metric = definition["metric_id"]
        if metric in columns:
            definition.update(
                certification_status="certified",
                source_codes=[f"treasury_nominal_yields_csv.{columns[metric]}"],
                source_candidates=["U.S. Department of the Treasury"],
                release_event_family="treasury_nominal_yields_csv",
                release_timezone="America/New_York",
            )
        elif metric == "UST_2S10S_SPREAD":
            definition["certification_status"] = "derived_from_certified_inputs"
        else:
            continue
        package["definition_bindings"][metric] = hashlib.sha256(encode(definition)).hexdigest()
    bind_synthetic_review(paths, request, package)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    return ModelRepository(paths.database).manifest(model_id)


# The archived Treasury CSV covers 2026-09-04; the daily freshness limit is 10 days, so these
# tests run on a pinned timeline instead of the wall clock, which would make them stale in time.
TREASURY_FIXTURE_DAY = date(2026, 9, 4)
TREASURY_FRESH_CLOCK = datetime(2026, 9, 5, 12, tzinfo=UTC)


def cpi_document() -> bytes:
    # Compact synthetic rendering of the six independently audited July literals.
    # Actual original: a4b8c84fa4b005807a9c30b4a41c06726f571bd203e753db81532be4dee54a49.
    return """
    <html><body><h1>2026年7月份居民消费价格</h1>
    <p>发布时间：2026-08-09 09:30</p><table>
    <tr><th>指标</th><th>环比（%）</th><th>同比（%）</th><th>累计平均同比（%）</th></tr>
    <tr><td>居民消费价格</td><td>-0.1</td><td>0.5</td><td>0.9</td></tr>
    <tr><td>不包括食品和能源</td><td>0.3</td><td>0.9</td><td>1.1</td></tr>
    </table></body></html>
    """.encode()


def admitted_source_variant(
    paths: RuntimePaths,
    capsys: pytest.CaptureFixture[str],
    side: str,
    *,
    metric_id: str = "CN_RRR_EVENT",
) -> dict[str, Any]:
    request, _ = prepared_request(paths)
    manifest = request["manifest"]
    manifest["metric_catalog_version"] += "-" + side
    for definition in manifest["metric_definitions"]:
        definition["definition_version"] = manifest["metric_catalog_version"]
        if side == "candidate" and definition["metric_id"] == metric_id:
            definition["source_candidates"] = [
                *definition["source_candidates"],
                "https://www.pbc.gov.cn/synthetic-review",
            ]
    package_hash = request["package_hashes"][0]
    package = json.loads((paths.artifacts / package_hash[:2] / package_hash).read_bytes())
    package["definition_bindings"] = {
        d["metric_id"]: hashlib.sha256(encode(d)).hexdigest()
        for d in manifest["metric_definitions"]
        if d["metric_id"] in package["definition_bindings"]
    }
    bind_synthetic_review(paths, request, package)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    return ModelRepository(paths.database).manifest(model_id)


@pytest.mark.usefixtures("runtime_clock")
def test_registered_warrant_acquisition_preserves_sample_units_and_unknown_public(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    version = request["manifest"]["metric_catalog_version"]
    # Synthetic TuShare delivery shape, anchored to independent SHFE literals.
    # These are not historical TuShare receipts or a new source certification.
    raw_by_symbol = {
        symbol: encode(
            {
                "code": 0,
                "data": {
                    "fields": [
                        "trade_date",
                        "symbol",
                        "warehouse",
                        "pre_vol",
                        "vol",
                        "vol_chg",
                        "unit",
                        "exchange",
                    ],
                    "items": [["20260828", symbol, warehouse, None, value, 0, unit, "SHFE"]],
                },
            }
        )
        for symbol, warehouse, value, unit in (
            ("CU", "国储天威", 225, "吨"),
            ("SC", "弘润油储", 1027000, "桶"),
        )
    }
    requests: list[str] = []

    def transport(payload: dict[str, Any]) -> bytes:
        assert payload["api_name"] == "fut_wsr"
        symbol = str(payload["params"]["symbol"])
        requests.append(symbol)
        return raw_by_symbol[symbol]

    adapter = TushareContextAdapter("synthetic-token", transport=transport)
    imported = adapter.acquire_scalars(
        paths,
        lambda: tuple(
            scalar
            for symbol in ("CU", "SC")
            for scalar in adapter.futures_warrants(
                start_date=date(2026, 8, 28),
                end_date=date(2026, 8, 28),
                symbol=symbol,
            )
        ),
        definition_version=version,
    )
    assert requests == ["CU", "SC"]
    assert len(imported.claim_ids) == 4
    evidence = EvidenceRepository(paths.database)
    now = datetime.now(UTC)
    points = evidence.metric_series(
        "CN_FUTURES_WARRANTS", mode=AsOfMode.SYSTEM, as_of=now, definition_version=version
    )
    assert {
        (p.dimensions["symbol"], p.selected_value, p.claims[0].unit)
        for p in points
        if p.dimensions["measure"] == "registered_receipts"
    } == {("CU", 225, "tonne"), ("SC", 1027000, "barrel")}
    assert all(p.dimensions["exchange"] == "SHFE" for p in points)
    for point in points:
        trace = evidence.trace(point.observation_id, mode=AsOfMode.SYSTEM, as_of=now)
        assert len(trace.acquisitions) == 1
        (linked_receipt,) = trace.acquisitions
        assert linked_receipt.parameters["symbol"] == point.dimensions["symbol"]
    assert all(p.claims[0].parsed_public_available_at is None for p in points)
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    assert len(acquisitions.history()) == 2
    assert {
        acquisitions.read_content(r.acquisition_id, "raw") for r in acquisitions.history()
    } == set(raw_by_symbol.values())
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="warrant-two-sample-members",
        model_version_id=model_id,
        system_as_of=now,
        release_event_id="synthetic:warrants",
        metric_ids=("CN_FUTURES_WARRANTS",),
        period="2026-08-28",
    )
    assert not select_retrieval_input(paths, run).complete


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("missing_current", [False, True])
@pytest.mark.parametrize("redeliver_old", [False, True])
def test_warrant_same_day_revision_preserves_public_history_and_replaces_members(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], missing_current: bool, redeliver_old: bool
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    version = request["manifest"]["metric_catalog_version"]
    old_public = datetime(2026, 8, 28, 9, tzinfo=UTC)
    new_public = datetime(2026, 8, 28, 10, tzinfo=UTC)

    def transport(payload: dict[str, Any]) -> bytes:
        symbol = payload["params"]["symbol"]
        return encode(
            {
                "code": 0,
                "data": {
                    "fields": [
                        "trade_date",
                        "symbol",
                        "warehouse",
                        "pre_vol",
                        "vol",
                        "vol_chg",
                        "unit",
                        "exchange",
                    ],
                    "items": [
                        ["20260828", symbol, "synthetic-old", 90, 100, 10, "吨", "synthetic"]
                    ],
                },
            }
        )

    adapter = TushareContextAdapter("synthetic-token", transport=transport)
    original = adapter.acquire_scalars(
        paths,
        lambda: tuple(
            replace(s, release_at=old_public, public_available_at=old_public)
            for symbol in ("CF", "CU", "PP", "RB", "RU", "SC", "SP", "TA")
            for s in adapter.futures_warrants(
                start_date=date(2026, 8, 28), end_date=date(2026, 8, 28), symbol=symbol
            )
        ),
        definition_version=version,
    )
    evidence = EvidenceRepository(paths.database)
    old_cu_ids = {
        p.selected_claim_id
        for p in evidence.metric_series(
            "CN_FUTURES_WARRANTS",
            mode=AsOfMode.PUBLIC,
            as_of=old_public,
            definition_version=version,
        )
        if p.dimensions["symbol"] == "CU"
    }
    revision_adapter = TushareContextAdapter(
        "synthetic-token",
        transport=lambda payload: encode(
            {
                "code": 0,
                "data": {
                    "fields": [
                        "trade_date",
                        "symbol",
                        "warehouse",
                        "pre_vol",
                        "vol",
                        "vol_chg",
                        "unit",
                        "exchange",
                    ],
                    "items": [
                        [
                            "20260828",
                            "CU",
                            "synthetic-new",
                            20,
                            None if missing_current else 25,
                            None,
                            "吨",
                            "synthetic",
                        ]
                    ],
                },
            }
        ),
    )
    revision = revision_adapter.acquire_scalars(
        paths,
        lambda: tuple(
            replace(s, release_at=new_public, public_available_at=new_public)
            for s in revision_adapter.futures_warrants(
                start_date=date(2026, 8, 28), end_date=date(2026, 8, 28), symbol="CU"
            )
        ),
        definition_version=version,
    )
    revision_acquired_at = datetime.now(UTC)
    if redeliver_old:
        original = adapter.acquire_scalars(
            paths,
            lambda: tuple(
                replace(s, release_at=old_public, public_available_at=old_public)
                for symbol in ("CF", "CU", "PP", "RB", "RU", "SC", "SP", "TA")
                for s in adapter.futures_warrants(
                    start_date=date(2026, 8, 28), end_date=date(2026, 8, 28), symbol=symbol
                )
            ),
            definition_version=version,
        )
        old_cu_ids = {
            p.selected_claim_id
            for p in evidence.metric_series(
                "CN_FUTURES_WARRANTS",
                mode=AsOfMode.PUBLIC,
                as_of=old_public,
                definition_version=version,
            )
            if p.dimensions["symbol"] == "CU"
        }
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="warrant-same-day-revision",
        model_version_id=model_id,
        system_as_of=datetime.now(UTC),
        release_event_id="synthetic:warrant-same-day-revision",
        metric_ids=("CN_FUTURES_WARRANTS",),
        period="2026-08-28",
    )
    for cutoff in (old_public, new_public):
        selection = select_retrieval_input(
            paths, replace(run, system_as_of=cutoff, cutoffs_frozen=True), mode=AsOfMode.PUBLIC
        )
        assert selection.complete is not (cutoff == new_public and missing_current)
        context = build_context_projection(
            evidence,
            as_of=cutoff,
            as_of_mode=AsOfMode.PUBLIC,
            model_manifest=ModelRepository(paths.database).manifest(model_id),
            target_business_date="2026-08-28",
        )
        inputs = context.macro["model_input_observation_version_ids"]
        assert isinstance(inputs, list)
        if cutoff == old_public:
            assert set(original.claim_ids) <= set(inputs)
            assert set(revision.claim_ids).isdisjoint(inputs)
        elif missing_current:
            assert set((*original.claim_ids, *revision.claim_ids)).isdisjoint(inputs)
        else:
            assert old_cu_ids.isdisjoint(inputs)
            assert (set(original.claim_ids) - old_cu_ids) | set(revision.claim_ids) <= set(inputs)
    if redeliver_old:
        before = select_retrieval_input(
            paths,
            replace(run, system_as_of=revision_acquired_at, cutoffs_frozen=True),
            mode=AsOfMode.SYSTEM,
        )
        assert before.complete is not missing_current
        if not missing_current:
            assert set(revision.claim_ids) <= set(before.selected_claim_ids)
        after = select_retrieval_input(paths, run, mode=AsOfMode.SYSTEM)
        assert after.complete
        assert set(after.selected_claim_ids) == set(original.claim_ids)


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("fault", ["api", "field", "unit_conflict", "partial"])
def test_registered_warrant_invalid_delivery_rejects_atomic_import(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], fault: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    capsys.readouterr()
    version = request["manifest"]["metric_catalog_version"]
    rows = [["20260828", "CU", "synthetic-warehouse", 225, 225, 0, "吨", "SHFE"]]
    if fault in {"unit_conflict", "partial"}:
        # Several rows of one warehouse are summed (ADR-0029), but only in one unit and only
        # for a field every row reports.
        rows.append(
            [
                "20260828",
                "CU",
                "synthetic-warehouse",
                225,
                None if fault == "partial" else 225,
                0,
                "千克" if fault == "unit_conflict" else "吨",
                "SHFE",
            ]
        )
    raw = encode(
        {
            "code": 0,
            "data": {
                "fields": [
                    "trade_date",
                    "symbol",
                    "warehouse",
                    "pre_vol",
                    "vol",
                    "vol_chg",
                    "unit",
                    "exchange",
                ],
                "items": rows,
            },
        }
    )
    adapter = TushareContextAdapter("synthetic-token", transport=lambda _: raw)

    def retrieve() -> tuple[ContextScalar, ...]:
        scalars = adapter.futures_warrants(
            start_date=date(2026, 8, 28), end_date=date(2026, 8, 28), symbol="CU"
        )
        if fault in {"unit_conflict", "partial"}:
            return scalars
        return tuple(
            (
                replace(s, api_name="synthetic_wrong_api")
                if fault == "api"
                else replace(s, source_field="pre_vol")
            )
            if s.source_field == "vol"
            else s
            for s in scalars
        )

    expected_error = {
        "unit_conflict": "tushare_warrant_unit_conflict",
        "partial": "tushare_warrant_member_field_partial",
    }.get(fault, "registered_warrant_source_field_mismatch")
    with pytest.raises(ValueError, match=expected_error):
        adapter.acquire_scalars(paths, retrieve, definition_version=version)
    assert not EvidenceRepository(paths.database).metric_series(
        "CN_FUTURES_WARRANTS",
        mode=AsOfMode.SYSTEM,
        as_of=datetime.now(UTC),
        definition_version=version,
    )
    if fault in {"unit_conflict", "partial"}:
        acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
        (receipt,) = acquisitions.history()
        assert receipt.state == "failed"
        assert acquisitions.read_content(receipt.acquisition_id, "raw") == raw


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("mixed_api", [False, True])
def test_registered_interbank_rejects_mixed_api_claim_links(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], mixed_api: bool
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    version = request["manifest"]["metric_catalog_version"]
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    receipt_ids = []
    # Adversarial associations through public receipt APIs: valid responses from
    # two APIs are given the same delivered DR scalar and mixed acquisition IDs.
    responses = {
        "repo_daily": (
            ["ts_code", "trade_date", "repo_maturity", "weight"],
            ["DR007.IB", "20260828", "DR007", 1.3859],
        ),
        "shibor": (["date", "on", "1w", "3m"], ["20260828", 1.339, 1.387, 1.43]),
    }
    for api_name in ("repo_daily", "shibor") if mixed_api else ("repo_daily",):
        columns, row = responses[api_name]
        raw = encode({"code": 0, "data": {"fields": columns, "items": [row]}})

        def fetch(content: bytes = raw) -> bytes:
            return content

        acquired = acquisitions.capture(
            provider="tushare",
            api_name=api_name,
            parameters={
                "start_date": "20260828",
                "end_date": "20260828",
                **({"ts_code": "DR007.IB"} if api_name == "repo_daily" else {}),
            },
            fields=",".join(columns),
            parser_version="tushare-context-parser-v0002",
            fetch=fetch,
            parse=json.loads,
            normalize=lambda value: value,
            defer_validation=True,
        )
        receipt_ids.append(acquired.receipt.acquisition_id)
    scalar = ContextScalar(
        metric_id="CN_DR007",
        api_name="repo_daily",
        source_field="weight",
        period_kind="business_day",
        period_start="2026-08-28",
        period_end="2026-08-28",
        dimensions={},
        value=1.3859,
        unit="percent",
        release_at=datetime(2026, 8, 28, 8, tzinfo=UTC),
        public_available_at=datetime(2026, 8, 28, 8, tzinfo=UTC),
        acquisition_ids=tuple(receipt_ids),
    )
    for receipt_id in receipt_ids:
        acquisitions.complete_validation(receipt_id, [asdict(scalar)])
    imported = ingest_context_scalars(
        paths, (scalar,), fetched_at=datetime.now(UTC), definition_version=version
    )
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="interbank-mixed-api",
        model_version_id=model_id,
        system_as_of=datetime.now(UTC),
        release_event_id="synthetic:interbank-mixed-api",
        metric_ids=("CN_DR007",),
        period="2026-08-28",
    )
    selection = select_retrieval_input(paths, run, mode=AsOfMode.PUBLIC)
    assert selection.complete is (not mixed_api)
    assert selection.selected_claim_ids == (() if mixed_api else imported.claim_ids)


@pytest.mark.parametrize("fault", ["dr_field", "dr_api", "shibor_field"])
def test_registered_interbank_rejects_wrong_delivery_field_atomically(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], fault: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    capsys.readouterr()
    now = datetime(2026, 8, 29, tzinfo=UTC)
    dr = ContextScalar(
        metric_id="CN_DR007",
        api_name="repo_daily",
        source_field="weight",
        period_kind="business_day",
        period_start="2026-08-28",
        period_end="2026-08-28",
        dimensions={},
        value=1.3859,
        unit="percent",
    )
    shibor = replace(
        dr,
        metric_id="CN_SHIBOR_ON_1W_3M",
        api_name="shibor",
        source_field="3m",
        dimensions={"tenor": "3m"},
        value=1.43,
    )
    if fault == "dr_field":
        dr = replace(dr, source_field="close")
    elif fault == "dr_api":
        dr = replace(dr, api_name="shibor")
    else:
        shibor = replace(shibor, source_field="1m")
    with pytest.raises(ValueError, match="registered_interbank_source_field_mismatch"):
        ingest_context_scalars(
            paths,
            (dr, shibor),
            fetched_at=now,
            definition_version=request["manifest"]["metric_catalog_version"],
        )
    repository = EvidenceRepository(paths.database)
    for metric in ("CN_DR007", "CN_SHIBOR_ON_1W_3M"):
        assert not repository.metric_series(
            metric,
            mode=AsOfMode.SYSTEM,
            as_of=now,
            definition_version=request["manifest"]["metric_catalog_version"],
        )


@pytest.mark.usefixtures("runtime_clock")
def test_registered_catalog_search_binds_shared_gaps_and_preserves_both_responses(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    with pytest.raises(LookupError, match="active_model_unavailable"):
        ModelRepository(paths.database).active()
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    version = request["manifest"]["metric_catalog_version"]
    metrics = ("CN_PMI_ACTIVITY", "CN_PMI_INVENTORY", "CN_PMI_PRICES")
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="registered-search-pair",
        model_version_id=model_id,
        system_as_of=datetime.now(UTC),
        release_event_id="synthetic:pmi-search",
        metric_ids=metrics,
        period="2026-07",
    )
    ledger = RetrievalLedger(paths.database)
    ledger.bind_run(run, version)
    query = build_search_query(metrics, period="2026-07")
    assert query == "2026年7月份中国采购经理指数运行情况"
    original = encode(
        {
            "results": [
                {
                    "url": "https://www.stats.gov.cn/synthetic/pmi.html",
                    "content": "synthetic unverified candidate",
                }
            ]
        }
    )

    def transport(
        _endpoint: str, _headers: dict[str, str], _payload: dict[str, object]
    ) -> SearchHttpResponse:
        return SearchHttpResponse(200, None, original)

    for provider in ("tavily", "exa"):
        response = search_discovery_adapter(
            provider,
            "synthetic-key",
            query,
            transport=transport,
            paths=paths,
            run_id=run.run_id,
            ledger=ledger,
        )("synthetic:pmi-search")
        assert response.status == "candidate_source"
        assert response.classification == "unverified_candidate"
    recorded = ledger.for_run(run.run_id)
    assert recorded is not None
    assert len(recorded["gaps"]) == 3
    assert {g["definition_version"] for g in recorded["gaps"]} == {version}
    assert {g["model_version_id"] for g in recorded["gaps"]} == {model_id}
    assert len(recorded["requests"]) == 2
    assert {r["channel"] for r in recorded["requests"]} == {"tavily", "exa"}
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    for physical in recorded["requests"]:
        assert acquisitions.read_content(physical["acquisition_id"], "raw") == original
    assert recorded["candidate_validations"] == []
    with pytest.raises(LookupError, match="active_model_unavailable"):
        ModelRepository(paths.database).active()


@pytest.mark.usefixtures("runtime_clock")
# Another run's old charge no longer limits this one (no daily cap, ticket 20); only an
# unexpired negative cache on the shared family still does.
@pytest.mark.parametrize("legacy_kind", ["cache"])
def test_registered_catalog_retains_shared_family_legacy_search_limits(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], legacy_kind: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    version = request["manifest"]["metric_catalog_version"]
    now = datetime.now(UTC)
    runs = RunRepository(paths.database)
    old = runs.submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="registered-search-old",
        model_version_id=model_id,
        system_as_of=now,
        release_event_id="synthetic:pmi-old",
        metric_ids=("CN_PMI_ACTIVITY",),
        period="2026-07",
    )
    if legacy_kind == "cache":
        runs.store_negative_cache(
            "synthetic:pmi-old",
            ("CN_PMI_ACTIVITY",),
            reason="unresolved",
            expires_at=now + timedelta(minutes=30),
            now=now,
        )
    else:
        runs.record_retrieval_attempt(
            old.run_id,
            release_event_id="synthetic:pmi-old",
            channel="tavily",
            outcome="failed",
            classification="transient_transport_error",
            latency_ms=1,
            remaining_run_budget=7,
            remaining_daily_budget=15,
            budget_charged=True,
            cache_hit=False,
            manual_budget_exemption=False,
            candidate_source=None,
            occurred_at=now,
        )
    runs.mark_action_required(old.run_id, "legacy-unresolved")
    run = runs.submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="registered-search-new",
        model_version_id=model_id,
        system_as_of=now,
        release_event_id="synthetic:pmi-new",
        metric_ids=("CN_PMI_INVENTORY",),
        period="2026-07",
    )
    ledger = RetrievalLedger(paths.database)
    ledger.bind_run(run, version)
    query = build_search_query(("CN_PMI_INVENTORY",), period="2026-07")

    def transport(
        _endpoint: str, _headers: dict[str, str], _payload: dict[str, object]
    ) -> SearchHttpResponse:
        pytest.fail("shared family limit must prevent an external request")

    response = search_discovery_adapter(
        "tavily",
        "synthetic-key",
        query,
        transport=transport,
        paths=paths,
        run_id=run.run_id,
    )("synthetic:pmi-new")
    assert response.status == "not_attempted"
    assert response.classification == "negative_cache_active"
    assert not AcquisitionRepository(paths.database, paths.artifacts).history()
    recorded = ledger.for_run(run.run_id)
    assert recorded is not None
    assert recorded["requests"] == []


def test_registered_search_gap_cannot_use_a_different_catalog_than_its_model(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="catalog-mismatch",
        model_version_id=model_id,
        system_as_of=datetime(2026, 9, 8, tzinfo=UTC),
        release_event_id="synthetic:mismatch",
        metric_ids=("CN_PMI_ACTIVITY",),
        period="2026-07",
    )
    ledger = RetrievalLedger(paths.database)
    with pytest.raises(ValueError, match="retrieval_catalog_model_mismatch"):
        ledger.bind_run(run, "metric-catalog-v0001")
    assert ledger.for_run(run.run_id) is None


def test_pmi_invalid_latest_period_does_not_restore_older_derived_values(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    manifest = ModelRepository(paths.database).manifest(model_id)
    evidence_root = Path(__file__).parents[2] / ".scratch/pring-data-acquisition-repair"
    claims = {}
    for period, folder, digest, url, acquired_at in (
        (
            "2026-06",
            "evidence-macro-normalized",
            "f0cc6558252e9d754645aaaedcd8bd5f20f04cc1de5765ba2c6761d4222e159c",
            "https://www.stats.gov.cn/sj/zxfb/202606/t20260630_1964032.html",
            datetime(2026, 7, 1, tzinfo=UTC),
        ),
        (
            "2026-07",
            "evidence-13",
            "fff072e83f897a0a9e981e147105ecb81535958dfeaeafcf7881c24ede2a10d6",
            "https://www.stats.gov.cn/sj/zxfb/202607/t20260731_1964253.html",
            datetime(2026, 8, 1, tzinfo=UTC),
        ),
    ):
        raw = (evidence_root / folder / digest).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == digest

        def clock(value: datetime = acquired_at) -> datetime:
            return value

        imported = ingest_official_context_document(
            paths,
            raw,
            family="nbs_pmi",
            source_url=url,
            expected_period=period,
            fetched_at=acquired_at,
            clock=clock,
            definition_version=manifest["metric_catalog_version"],
        )
        claims[period] = set(imported.claim_ids)

    def derived_rows(cutoff: datetime) -> tuple[dict[str, Any], list[str]]:
        context = build_context_projection(
            EvidenceRepository(paths.database),
            as_of=cutoff,
            model_manifest=manifest,
            as_of_mode=AsOfMode.PUBLIC,
        )
        cards = context.inventory["cards"]
        assert isinstance(cards, list)
        rows = {
            row["metric_id"]: row
            for card in cards
            for row in card["evidence"]
            if row["metric_id"] in {"CN_PRODUCTION_ORDER_SPREAD", "CN_ORDER_INVENTORY_SPREAD"}
        }
        inputs = context.macro["model_input_observation_version_ids"]
        assert isinstance(inputs, list)
        return rows, inputs

    now = datetime(2026, 8, 1, tzinfo=UTC)
    current, current_inputs = derived_rows(now)
    # Independent July table arithmetic: 49.9 - 48.5 and 48.5 - 48.6.
    assert current["CN_PRODUCTION_ORDER_SPREAD"]["value"] == pytest.approx(1.4)
    assert current["CN_ORDER_INVENTORY_SPREAD"]["value"] == pytest.approx(-0.1)
    assert {row["period"] for row in current.values()} == {"2026-07-31"}
    assert claims["2026-07"] <= set(current_inputs)
    july = next(
        receipt
        for receipt in AcquisitionRepository(paths.database, paths.artifacts).history()
        if receipt.parameters["period"] == "2026-07"
    )
    assert july.normalized_hash is not None
    (paths.artifacts / july.normalized_hash[:2] / july.normalized_hash).write_bytes(b"damaged")

    earlier, earlier_inputs = derived_rows(datetime(2026, 7, 30, tzinfo=UTC))
    # Independent June literals: 51.4 - 51.2 and 51.2 - 47.7.
    assert earlier["CN_PRODUCTION_ORDER_SPREAD"]["value"] == pytest.approx(0.2)
    assert earlier["CN_ORDER_INVENTORY_SPREAD"]["value"] == pytest.approx(3.5)
    assert {row["period"] for row in earlier.values()} == {"2026-06-30"}
    assert {row["status"] for row in earlier.values()} == {"current"}
    assert claims["2026-06"] <= set(earlier_inputs)
    assert not claims["2026-07"] & set(earlier_inputs)
    after, after_inputs = derived_rows(now)
    assert all(
        row["value"] is None or row["status"] not in {"current", "available"}
        for row in after.values()
    ), [(row["period"], row["status"], row["value"]) for row in after.values()]
    assert not (claims["2026-06"] | claims["2026-07"]) & set(after_inputs)


@pytest.mark.parametrize(
    ("family", "digest", "url", "period", "count", "anchors"),
    [
        (
            "nbs_ppi",
            "b323261248c08ecba00a96cf4401654896fd8a5709ce9bf81c2e38f7d5fbef09",
            "https://www.stats.gov.cn/sj/zxfb/202608/t20260809_1965007.html",
            "2026-07",
            9,
            {"CN_PPI": ({"category": "headline", "measure": "yoy"}, 3.5, "percent")},
        ),
        (
            "nbs_industrial_value_added",
            "d8a9cc4305ea657b6d9eeecc8633afcf6934bc05f7da72c9969c89e465833609",
            "https://www.stats.gov.cn/sj/zxfb/202608/t20260817_1965055.html",
            "2026-07",
            3,
            {"CN_INDUSTRIAL_VA": ({"measure": "current_month_real_yoy"}, 4.5, "percent")},
        ),
        (
            "nbs_industrial_finance",
            "28388ca9b78a83ea1fe39c0b3d943ad982d34c7dd4e26fee96d78a18b7a7f986",
            "https://www.stats.gov.cn/sj/zxfb/202608/t20260827_1965126.html",
            "2026-07",
            10,
            {
                "CN_INDUSTRIAL_FINANCE": (
                    {"item": "revenue", "measure": "ytd_level"},
                    809230.7,
                    "hundred_million_cny",
                ),
                "CN_FINISHED_GOODS_INVENTORY": (
                    {"measure": "nominal_end_level"},
                    72700,
                    "hundred_million_cny",
                ),
                "CN_INVENTORY_TURNOVER": ({"measure": "official_yoy_change"}, 0.6, "days"),
            },
        ),
        (
            "nbs_capacity_utilization",
            "8d1eadceb1259df2a86975d3565de90488c8d9b0f14992ec14fd7f8f49ab70e8",
            "https://www.stats.gov.cn/sj/zxfb/202607/t20260715_1964130.html",
            "2026-Q2",
            3,
            {
                "CN_CAPACITY_UTILIZATION": (
                    {"industry": "all_industry", "measure": "yoy_change"},
                    -1.0,
                    "percentage_points",
                )
            },
        ),
        (
            "pbc_money",
            "933f3546fc3f8232014dc9e2cab854a331ff5da5a9509d3063ada2d3678dfcef",
            "https://www.pbc.gov.cn/diaochatongjisi/116219/116225/2026081416320925645/index.html",
            "2026-07",
            4,
            {
                "CN_M1_M2": (
                    {"aggregate": "m1", "measure": "balance"},
                    1154600,
                    "hundred_million_cny",
                )
            },
        ),
        (
            "pbc_social_financing",
            "933f3546fc3f8232014dc9e2cab854a331ff5da5a9509d3063ada2d3678dfcef",
            "https://www.pbc.gov.cn/diaochatongjisi/116219/116225/2026081416320925645/index.html",
            "2026-07",
            27,
            {
                "CN_SF_TOTAL": ({"measure": "stock_end"}, 4632700, "hundred_million_cny"),
                "CN_SF_COMPONENTS": (
                    {"component": "government_bonds", "measure": "ytd_increment"},
                    77600,
                    "hundred_million_cny",
                ),
            },
        ),
        (
            "pbc_loan_structure",
            "933f3546fc3f8232014dc9e2cab854a331ff5da5a9509d3063ada2d3678dfcef",
            "https://www.pbc.gov.cn/diaochatongjisi/116219/116225/2026081416320925645/index.html",
            "2026-07",
            9,
            {
                "CN_LOAN_STRUCTURE": (
                    {"borrower": "enterprise", "tenor": "long_term", "measure": "ytd_increment"},
                    53200,
                    "hundred_million_cny",
                )
            },
        ),
        (
            "pbc_tool_liquidity_monthly",
            "10ed3fb5822bcc74dd429325d8196b7bbda9ed2e732eaa957914cbe95d2452f0",
            "https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/5727710/2026080416515912098/index.html",
            "2026-07",
            24,
            {
                "CN_TOOL_LIQUIDITY_MONTHLY": (
                    {"tool": "短期逆回购", "measure": "net_injection"},
                    -2495,
                    "hundred_million_cny",
                )
            },
        ),
        (
            "pbc_omo_notice",
            "ee19f9d0ca925b95875448bda4f354558ee7c6f06c36d9a3a62eafb9d59e4a1a",
            "https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/125431/125475/2026082808585347002/index.html",
            "2026-08-28",
            2,
            {
                "CN_OMO_7D_AMOUNT": ({"measure": "injection"}, 200, "hundred_million_cny"),
                "CN_OMO_7D_RATE": ({}, 1.4, "percent"),
            },
        ),
    ],
    ids=[
        "ppi",
        "industrial-va",
        "industrial-finance",
        "capacity-q2",
        "money",
        "social-financing",
        "loans",
        "tools",
        "omo",
    ],
)
@pytest.mark.parametrize("consumer", ["none", "selection", "context"])
def test_registered_official_original_reaches_selection_and_context(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    family: str,
    digest: str,
    url: str,
    period: str,
    count: int,
    anchors: dict[str, tuple[dict[str, str], float, str]],
    consumer: str,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    manifest = ModelRepository(paths.database).manifest(model_id)
    version = manifest["metric_catalog_version"]
    raw = (
        Path(__file__).parents[2] / ".scratch/pring-data-acquisition-repair/evidence-13" / digest
    ).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == digest
    now = datetime(2026, 8, 29, tzinfo=UTC)
    imported = ingest_official_context_document(
        paths,
        raw,
        family=family,
        source_url=url,
        expected_period=period,
        fetched_at=now,
        clock=lambda: now,
        definition_version=version,
    )
    assert len(imported.claim_ids) == count
    repository = EvidenceRepository(paths.database)
    for metric, (dimensions, value, unit) in anchors.items():
        for mode in (AsOfMode.PUBLIC, AsOfMode.SYSTEM):
            points = repository.metric_series(
                metric, mode=mode, as_of=now, definition_version=version
            )
            (point,) = (p for p in points if p.dimensions == dimensions)
            assert point.selected_value == value
            (claim,) = (c for c in point.claims if c.claim_id == point.selected_claim_id)
            assert claim.unit == unit
            assert claim.source_reference == f"{url}#sha256={digest}"
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="admitted-official",
        model_version_id=model_id,
        system_as_of=now,
        release_event_id=imported.release_event_id,
        metric_ids=tuple(anchors),
        period=period,
    )
    selection = select_retrieval_input(paths, run)
    assert selection.complete, selection.missing_members
    assert set(selection.selected_claim_ids) <= set(imported.claim_ids)
    context = build_context_projection(repository, as_of=now, model_manifest=manifest)
    assert set(imported.claim_ids) <= set(context.observation_version_ids)
    model_inputs = context.macro["model_input_observation_version_ids"]
    assert isinstance(model_inputs, list)
    assert set(imported.claim_ids) <= set(model_inputs)

    if consumer != "none":
        acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
        (receipt,) = acquisitions.history()
        assert receipt.raw_hash == digest
        assert receipt.normalized_hash is not None
        normalized_path = paths.artifacts / receipt.normalized_hash[:2] / receipt.normalized_hash
        normalized_path.write_bytes(b'{"damaged":true}\n')
        if consumer == "selection":
            invalid_selection = select_retrieval_input(paths, run)
            assert not invalid_selection.complete
            assert invalid_selection.selected_claim_ids == ()
        else:
            after_context = build_context_projection(repository, as_of=now, model_manifest=manifest)
            after_inputs = after_context.macro["model_input_observation_version_ids"]
            assert isinstance(after_inputs, list)
            assert set(imported.claim_ids).isdisjoint(after_inputs)
            assert set(imported.claim_ids) <= set(after_context.observation_version_ids)


def test_the_overnight_and_7_day_reverse_repo_row_continues_the_7_day_member(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Run findings 03: from August the PBC table reads "隔夜、7天期逆回购" where July read
    "7天期逆回购"; both are the one short reverse repo member, and all 24 values are held."""
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    version = ModelRepository(paths.database).manifest(model_id)["metric_catalog_version"]
    digest = "4d104698df655c19c27e4a697ef4bd55cc1c0b30ad9aae265e7db3c955bc90c2"
    raw = (
        Path(__file__).parents[2] / ".scratch/pring-data-acquisition-repair/evidence-13" / digest
    ).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == digest
    now = datetime(2026, 9, 3, tzinfo=UTC)

    imported = ingest_official_context_document(
        paths,
        raw,
        family="pbc_tool_liquidity_monthly",
        source_url=(
            "https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/5727710/"
            "2026090214213398506/index.html"
        ),
        expected_period="2026-08",
        fetched_at=now,
        clock=lambda: now,
        definition_version=version,
    )

    assert len(imported.claim_ids) == 24
    points = EvidenceRepository(paths.database).metric_series(
        "CN_TOOL_LIQUIDITY_MONTHLY", mode=AsOfMode.PUBLIC, as_of=now, definition_version=version
    )
    assert {p.period_end for p in points} == {"2026-08-31"}
    (short,) = (
        p for p in points if p.dimensions == {"tool": "短期逆回购", "measure": "net_injection"}
    )
    assert short.selected_value == -6415
    (claim,) = (c for c in short.claims if c.claim_id == short.selected_claim_id)
    assert claim.release_at == datetime(2026, 9, 2, 9, tzinfo=UTC)


def test_an_unknown_reverse_repo_row_is_refused_and_the_receipt_says_why(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Run findings 03: only the two known names of the short reverse repo row are one member;
    another name is refused, and the refusal code is kept, not only a ValueError."""
    from pring_cycle.official_context import (
        FetchedOfficialContextDocument,
        refresh_official_context_document,
    )

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    version = ModelRepository(paths.database).manifest(model_id)["metric_catalog_version"]
    digest = "4d104698df655c19c27e4a697ef4bd55cc1c0b30ad9aae265e7db3c955bc90c2"
    raw = (
        Path(__file__).parents[2] / ".scratch/pring-data-acquisition-repair/evidence-13" / digest
    ).read_bytes()
    assert "隔夜、7天期逆回购".encode() in raw
    renamed = raw.replace("隔夜、7天期逆回购".encode(), "14天期逆回购".encode())
    url = (
        "https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/5727710/2026090214213398506/index.html"
    )

    with pytest.raises(ValueError, match="registered_official_source_identity_mismatch"):
        refresh_official_context_document(
            paths,
            family="pbc_tool_liquidity_monthly",
            source_url=url,
            expected_period="2026-08",
            fetched_at=datetime.now(UTC),
            fetcher=lambda u: FetchedOfficialContextDocument(renamed, "text/html", u, 200),
            definition_version=version,
        )

    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    (receipt,) = acquisitions.history()
    assert receipt.state == "validated"
    assert acquisitions.ingest_result(receipt.acquisition_id) == (
        "rejected",
        "registered_official_source_identity_mismatch",
    )
    assert not EvidenceRepository(paths.database).metric_series(
        "CN_TOOL_LIQUIDITY_MONTHLY",
        mode=AsOfMode.SYSTEM,
        as_of=datetime.now(UTC),
        definition_version=version,
    )


@pytest.mark.parametrize(
    ("family", "digest", "url", "period", "metric", "values"),
    [
        (
            "nbs_ppi",
            "e7e65eb8ae0656afae92ab36bcb8a6c261be5af0422352fadbecf45c4a0e2943",
            "https://www.stats.gov.cn/sj/zxfb/202602/t20260211_1962587.html",
            "2026-01",
            "CN_PPI",
            {"mom", "yoy"},
        ),
        (
            "nbs_industrial_value_added",
            "2115d7cc67a22dd15a88c93101be752711a72e7f41534b01b1e8f7528f341f8e",
            "https://www.stats.gov.cn/sj/zxfb/202603/t20260316_1962782.html",
            "2026-02",
            "CN_INDUSTRIAL_VA",
            {"mom_seasonally_adjusted", "ytd_real_yoy"},
        ),
    ],
    ids=["january-ppi", "february-industrial-va"],
)
def test_registered_official_legitimate_missing_columns_are_complete(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    family: str,
    digest: str,
    url: str,
    period: str,
    metric: str,
    values: set[str],
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    version = request["manifest"]["metric_catalog_version"]
    raw = (
        Path(__file__).parents[2]
        / ".scratch/pring-data-acquisition-repair/evidence-official-consumer-edge"
        / digest
    ).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == digest
    now = datetime(2026, 8, 29, tzinfo=UTC)
    result = ingest_official_context_document(
        paths,
        raw,
        family=family,
        source_url=url,
        expected_period=period,
        fetched_at=now,
        clock=lambda: now,
        definition_version=version,
    )
    points = EvidenceRepository(paths.database).metric_series(
        metric,
        mode=AsOfMode.SYSTEM,
        as_of=now,
        definition_version=version,
    )
    assert {p.dimensions["measure"] for p in points} == values
    if metric == "CN_INDUSTRIAL_VA":
        assert {p.dimensions["measure"]: p.selected_value for p in points} == {
            "mom_seasonally_adjusted": 0.83,
            "ytd_real_yoy": 6.3,
        }
    else:
        assert len(points) == 6
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="missing-columns",
        model_version_id=model_id,
        system_as_of=now,
        release_event_id=result.release_event_id,
        metric_ids=(metric,),
        period=period,
    )
    assert select_retrieval_input(paths, run).complete


def synthetic_coherent_gdp_release(period: str, *, fractional: bool = False) -> tuple[bytes, str]:
    # Deliberately synthetic public transport data. This tests the full formula
    # without asserting that mixed historical GDP releases share a vintage.
    year, quarter = int(period[:4]), int(period[-1])
    label = ("一季度", "二季度", "三季度", "四季度")[quarter - 1]
    release_year = year + 1 if quarter == 4 else year
    release_month = 1 if quarter == 4 else quarter * 3 + 1
    header = "<tr><td></td><td>绝对额（亿元）</td><td>比上年同期增长（%）</td></tr>"
    if quarter != 1:
        cumulative = ("", "上半年", "前三季度", "全年")[quarter - 1]
        header += (
            f"<tr><td>{label}</td><td>{cumulative}</td><td>{label}</td><td>{cumulative}</td></tr>"
        )
    rows = []
    for name, value in (
        ("GDP", 350000),
        ("第一产业", 10000),
        ("第二产业", 140000),
        ("第三产业", 200000),
    ):
        quarter_value = Decimal(value)
        if fractional and name in ("GDP", "第一产业"):
            quarter_value += Decimal("0.1")
        cells = (
            (name, quarter_value, 5)
            if quarter == 1
            else (name, quarter_value, quarter_value * quarter, 5, 5)
        )
        rows.append("<tr>" + "".join(f"<td>{cell}</td>" for cell in cells) + "</tr>")
    document = (
        "<html><body><p>synthetic fixture; not official economic data</p>"
        f"<h1>{year}年{label}国内生产总值初步核算结果</h1>"
        f"<p>发布时间：{release_year}-{release_month:02d}-16 09:30</p>"
        f"<table>{header}{''.join(rows)}"
        "<tr><td>绝对额按现价计算，增长速度按不变价计算。</td></tr></table></body></html>"
    )
    return document.encode(), f"https://www.stats.gov.cn/sj/synthetic-credit-window-{period}.html"


def synthetic_prior_social_financing_release(month: int = 6) -> tuple[bytes, str]:
    # A deliberately synthetic extra month makes old-window fallback observable.
    months_label, total = {5: ("前五个月", 15), 6: ("前六个月", 18)}[month]
    document = f"""<html><body><p>synthetic fixture; not official economic data</p>
    <h1>2024年{month}月社会融资规模增量统计数据报告</h1>
    <p>发布时间：2024-{month + 1:02d}-13 17:00:00</p>
    <p>2024年{months_label}社会融资规模增量累计为{total}万亿元。
    其中，对实体经济发放的人民币贷款增加12.38万亿元；
    对实体经济发放的外币贷款折合人民币减少970亿元；委托贷款减少573亿元；
    信托贷款增加3072亿元；未贴现的银行承兑汇票减少3440亿元；
    企业债券净融资1.61万亿元；政府债券净融资4.03万亿元；
    非金融企业境内股票融资1445亿元。</p></body></html>"""
    return (
        document.encode(),
        f"https://www.pbc.gov.cn/synthetic-credit-window-2024-{month:02d}.html",
    )


def prepare_credit_component_pair(
    paths: RuntimePaths,
    capsys: pytest.CaptureFixture[str],
    *,
    missing_candidate_social_baseline: bool = False,
) -> tuple[dict[str, dict[str, Any]], dict[str, set[str | None]]]:
    repository = EvidenceRepository(paths.database)
    root = Path(__file__).parents[2]
    fixture = json.loads(
        (
            root / ".scratch/pring-data-acquisition-repair/credit-window-inputs-186/manifest.json"
        ).read_text()
    )
    fixture_time = datetime(2026, 8, 29, tzinfo=UTC)
    cutoff = datetime(2026, 8, 28, 15, 59, 59, 999999, tzinfo=UTC)
    manifests = {}
    parent_ids = {}
    for side in ("comparison", "candidate"):
        manifest = admitted_gdp_manifest(paths, capsys, side=side)
        manifests[side] = manifest
        version = manifest["metric_catalog_version"]
        for parent in fixture["parents"]:
            if (
                missing_candidate_social_baseline
                and side == "candidate"
                and parent["family"] == "pbc_social_financing"
                and parent["period"] == "2026-06"
            ):
                continue
            raw = (root / parent["raw_path"]).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == parent["raw_sha256"]
            url = parent["source_url"]
            if parent["family"] == "nbs_gdp":
                raw, url = synthetic_coherent_gdp_release(parent["period"])
            if side == "candidate":
                raw += b"<!-- synthetic candidate component retrieval -->"
            imported = ingest_official_context_document(
                paths,
                raw,
                family=parent["family"],
                source_url=url,
                expected_period=parent["period"],
                fetched_at=fixture_time,
                clock=lambda: fixture_time,
                definition_version=version,
            )
            assert imported.claim_ids
        if missing_candidate_social_baseline:
            # Both catalogs have an older complete 24-month flow window. Only
            # the candidate lacks the baseline needed for its latest July flow.
            for month in (5, 6):
                old_raw, old_url = synthetic_prior_social_financing_release(month)
                older = ingest_official_context_document(
                    paths,
                    old_raw,
                    family="pbc_social_financing",
                    source_url=old_url,
                    expected_period=f"2024-{month:02d}",
                    fetched_at=fixture_time,
                    clock=lambda: fixture_time,
                    definition_version=version,
                )
                assert older.claim_ids
        # Replay also checks the complete latest SF publication: stock and flow
        # are separate official documents. Neither substitutes for the other.
        stock_hash = "933f3546fc3f8232014dc9e2cab854a331ff5da5a9509d3063ada2d3678dfcef"
        stock = (
            root / ".scratch/pring-data-acquisition-repair/evidence-13" / stock_hash
        ).read_bytes()
        assert hashlib.sha256(stock).hexdigest() == stock_hash
        imported_stock = ingest_official_context_document(
            paths,
            stock,
            family="pbc_social_financing",
            source_url="https://www.pbc.gov.cn/diaochatongjisi/116219/116225/2026081416320925645/index.html",
            expected_period="2026-07",
            fetched_at=fixture_time,
            clock=lambda: fixture_time,
            definition_version=version,
        )
        assert imported_stock.claim_ids
        parent_ids[side] = {
            point.selected_claim_id
            for metric, dimensions in (
                ("CN_SF_TOTAL", {"measure": "ytd_increment"}),
                ("CN_GDP", {"aggregate": "total", "measure": "nominal_ytd_level"}),
            )
            for point in repository.metric_series(
                metric, mode=AsOfMode.PUBLIC, as_of=cutoff, definition_version=version
            )
            if point.dimensions == dimensions
        }
        expected_count = 36 - int(side == "candidate") if missing_candidate_social_baseline else 34
        assert len(parent_ids[side]) == expected_count and None not in parent_ids[side]
    return manifests, parent_ids


def test_registered_social_financing_completes_only_after_both_original_announcements(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    version = request["manifest"]["metric_catalog_version"]
    repository = EvidenceRepository(paths.database)
    selected_counts = []
    receipts = []
    for index, (digest, code) in enumerate(
        (
            (
                "42312d6054e2df029dfeeba68c7c60fc4bc45934cb72bdd739c143e1c9f02243",
                "29d3365dfab04cc0a1e50bf0df41bae4",
            ),
            (
                "d0ae83ced9ad510a057a853f51b185e729ed81c9cd5e958fa988c7b10a676d9d",
                "d3cea9a15135428c8ecb623c90117476",
            ),
        )
    ):
        now = datetime(2026, 8, 29, index, tzinfo=UTC)

        def fixed_clock(instant: datetime = now) -> datetime:
            return instant

        raw = (
            Path(__file__).parents[2]
            / ".scratch/pring-data-acquisition-repair/evidence-official-consumer-social"
            / digest
        ).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == digest
        url = f"https://www.pbc.gov.cn/diaochatongjisi/116219/116225/{code}/index.html"
        result = ingest_official_context_document(
            paths,
            raw,
            family="pbc_social_financing",
            source_url=url,
            expected_period="2024-01",
            fetched_at=now,
            clock=fixed_clock,
            definition_version=version,
        )
        receipts.append(result)
        assert len(result.claim_ids) == (18 if index == 0 else 9)
        run = RunRepository(paths.database).submit(
            command_type="targeted_refresh",
            target_business_date="2026-08-28",
            client_request_id=f"split-sf-{index}",
            model_version_id=model_id,
            system_as_of=now,
            release_event_id=result.release_event_id,
            metric_ids=("CN_SF_TOTAL", "CN_SF_COMPONENTS"),
            period="2024-01",
        )
        selection = select_retrieval_input(paths, run)
        selected_counts.append(len(selection.selected_claim_ids))
        assert selection.complete is (index == 1)
        if index == 0:
            assert len(selection.missing_members) == 9
            assert all("ytd_increment" in member for member in selection.missing_members)
    assert selected_counts == [17, 26]
    points = repository.metric_series(
        "CN_SF_TOTAL",
        mode=AsOfMode.SYSTEM,
        as_of=datetime(2026, 8, 29, 1, tzinfo=UTC),
        definition_version=version,
    )
    assert {p.dimensions["measure"]: p.selected_value for p in points} == {
        "stock_end": 3842900,
        "stock_yoy": 9.5,
        "ytd_increment": 65000,
    }
    claims = [c for p in points for c in p.claims]
    assert len({c.source_reference for c in claims}) == 2
    assert len({c.public_available_at for c in claims}) == 2
    assert {c.fetched_at.hour for c in claims} == {0, 1}
    assert not set(receipts[0].claim_ids) & set(receipts[1].claim_ids)
    earlier = repository.metric_series(
        "CN_SF_TOTAL",
        mode=AsOfMode.SYSTEM,
        as_of=datetime(2026, 8, 29, tzinfo=UTC),
        definition_version=version,
    )
    assert {p.dimensions["measure"] for p in earlier} == {"stock_end", "stock_yoy"}


def prepared_capacity_mapping_request(
    paths: RuntimePaths, *, side: str = ""
) -> tuple[dict[str, Any], str, bytes, str, str]:
    # Public candidate admission and document ingestion with a synthetic review.
    # This does not certify the real source, historical PUBLIC time, or a full replay.
    request, _ = prepared_request(paths)
    manifest = request["manifest"]
    if side:
        manifest["metric_catalog_version"] += "-" + side
        for item in manifest["metric_definitions"]:
            item["definition_version"] = manifest["metric_catalog_version"]
            if side == "candidate" and item["metric_id"] == "CN_CAPACITY_UTILIZATION":
                item["source_candidates"] = [
                    *item["source_candidates"],
                    "https://www.stats.gov.cn/synthetic-q1-review",
                ]
    version = manifest["metric_catalog_version"]
    definition = next(
        item
        for item in manifest["metric_definitions"]
        if item["metric_id"] == "CN_CAPACITY_UTILIZATION"
    )
    digest = "0c66284a8d0420a6168c432e87e7e4ee31bf4002896634e5253780d928cdb02a"
    evidence_root = Path(__file__).parents[2] / ".scratch/pring-data-acquisition-repair"
    raw = (evidence_root / "evidence-official-consumer-edge" / digest).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == digest
    url = "https://www.stats.gov.cn/sj/zxfb/202604/t20260416_1963322.html"
    store_artifact(paths.database, paths.artifacts, raw, "text/html", url)
    basis_path = evidence_root / "capacity-q1-source-mapping-decision.md"
    basis = store_artifact(
        paths.database,
        paths.artifacts,
        basis_path.read_bytes(),
        "text/markdown",
        "synthetic:q1-mapping-semantic-basis",
    )
    mapping_hash = save(
        paths,
        {
            "schema_version": "source-field-mapping-v0001",
            "rule_version": "capacity_q1_same_interval_alias_v0001",
            "metric_id": "CN_CAPACITY_UTILIZATION",
            "definition_version": version,
            "definition_hash": hashlib.sha256(encode(definition)).hexdigest(),
            "source_document": {
                "artifact_hash": digest,
                "source_reference": url,
                "bytes": 128195,
            },
            "parser": {
                "version": "official-context-parser-v0004",
                "family": "nbs_capacity_utilization",
                "period": "2026-Q1",
            },
            "source": {
                "source_field": "industrial_capacity_utilization_pct",
                "dimensions": {"industry": "all_industry", "measure": "quarter_rate"},
                "period_kind": "quarter",
                "period_start": "2026-01-01",
                "period_end": "2026-03-31",
                "unit": "percent",
                "value": 73.6,
            },
            "target": {
                "source_field": "industrial_capacity_utilization_ytd_pct",
                "dimensions": {"industry": "all_industry", "measure": "ytd_rate"},
                "period_kind": "year_to_quarter",
                "period_start": "2026-01-01",
                "period_end": "2026-03-31",
                "unit": "percent",
                "value": 73.6,
            },
            "basis": {
                "artifact_hash": basis.content_hash,
                "source_reference": "synthetic:q1-mapping-semantic-basis",
            },
        },
    )
    package_hash = request["package_hashes"][0]
    package = json.loads((paths.artifacts / package_hash[:2] / package_hash).read_bytes())
    review_hash = package["review_hash"]
    review = json.loads((paths.artifacts / review_hash[:2] / review_hash).read_bytes())
    for criterion in ("semantics", "fields"):
        review["assessments"][criterion]["evidence"].append(
            {
                "artifact_hash": mapping_hash,
                "source_reference": "synthetic:admission",
            }
        )
    package["review_hash"] = save(paths, review)
    package["definition_bindings"] = {
        item["metric_id"]: hashlib.sha256(encode(item)).hexdigest()
        for item in manifest["metric_definitions"]
        if item["metric_id"] in package["definition_bindings"]
    }
    bind_synthetic_review(paths, request, package)
    return request, mapping_hash, raw, digest, url


@pytest.mark.parametrize(
    ("document_kind", "consumer"),
    [
        ("compact", "none"),
        ("official_original", "none"),
        ("official_original", "selection"),
        ("official_original", "context"),
    ],
)
def test_admitted_catalog_consumes_cpi_with_separate_categories_and_public_system_times(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], document_kind: str, consumer: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    manifest = ModelRepository(paths.database).manifest(model_id)
    version = manifest["metric_catalog_version"]
    acquired_at = datetime(2026, 8, 9, 2, tzinfo=UTC)
    content = cpi_document()
    if document_kind == "official_original":
        digest = "a4b8c84fa4b005807a9c30b4a41c06726f571bd203e753db81532be4dee54a49"
        content = (
            Path(__file__).parents[2]
            / ".scratch/pring-data-acquisition-repair/evidence-13"
            / digest
        ).read_bytes()
        assert hashlib.sha256(content).hexdigest() == digest
    ingested = ingest_official_context_document(
        paths,
        content,
        family="nbs_core_cpi",
        source_url="https://www.stats.gov.cn/sj/zxfb/202608/t20260809_1965008.html",
        expected_period="2026-07",
        fetched_at=acquired_at,
        definition_version=version,
        clock=lambda: acquired_at,
    )
    repository = EvidenceRepository(paths.database)
    expected = {
        "CN_CPI_HEADLINE": ("headline", {"mom": -0.1, "yoy": 0.5, "cumulative_average_yoy": 0.9}),
        "CN_CORE_CPI": ("ex_food_energy", {"mom": 0.3, "yoy": 0.9, "cumulative_average_yoy": 1.1}),
    }
    selected: set[str | None] = set()
    for metric, (category, values) in expected.items():
        public = repository.metric_series(
            metric,
            mode=AsOfMode.PUBLIC,
            as_of=datetime(2026, 8, 9, 1, 45, tzinfo=UTC),
            definition_version=version,
        )
        assert {point.dimensions["measure"]: point.selected_value for point in public} == values
        assert {point.dimensions["category"] for point in public} == {category}
        selected.update(point.selected_claim_id for point in public)
        assert not repository.metric_series(
            metric,
            mode=AsOfMode.SYSTEM,
            as_of=datetime(2026, 8, 9, 1, 45, tzinfo=UTC),
            definition_version=version,
        )
        assert (
            len(
                repository.metric_series(
                    metric,
                    mode=AsOfMode.SYSTEM,
                    as_of=acquired_at,
                    definition_version=version,
                )
            )
            == 3
        )
    assert selected == set(ingested.claim_ids)
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="admitted-cpi",
        model_version_id=model_id,
        system_as_of=acquired_at,
        release_event_id=ingested.release_event_id,
        metric_ids=tuple(expected),
        period="2026-07",
    )
    selection = select_retrieval_input(paths, run)
    assert selection.complete
    assert set(selection.selected_claim_ids) == set(ingested.claim_ids)
    context = build_context_projection(repository, as_of=acquired_at, model_manifest=manifest)
    assert set(ingested.claim_ids) <= set(context.observation_version_ids)
    model_inputs = context.macro["model_input_observation_version_ids"]
    assert isinstance(model_inputs, list)
    assert set(ingested.claim_ids) <= set(model_inputs)
    with pytest.raises(LookupError, match="active_model_unavailable"):
        ModelRepository(paths.database).active()
    if consumer != "none":
        (receipt,) = AcquisitionRepository(paths.database, paths.artifacts).history()
        assert receipt.normalized_hash is not None
        (paths.artifacts / receipt.normalized_hash[:2] / receipt.normalized_hash).write_bytes(
            b"damaged CPI normalized"
        )
        if consumer == "selection":
            after = select_retrieval_input(paths, run, mode=AsOfMode.PUBLIC)
            assert not after.complete
            assert after.selected_claim_ids == ()
        else:
            after_context = build_context_projection(
                EvidenceRepository(paths.database),
                as_of=acquired_at,
                model_manifest=manifest,
                as_of_mode=AsOfMode.PUBLIC,
            )
            after_inputs = after_context.macro["model_input_observation_version_ids"]
            assert isinstance(after_inputs, list)
            assert set(ingested.claim_ids).isdisjoint(after_inputs)
            assert set(ingested.claim_ids) <= set(after_context.observation_version_ids)


@pytest.mark.parametrize("month", [1, 7])
def test_registered_cpi_requires_cumulative_only_outside_january(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], month: int
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    # Four January literals from the independently audited table. The July
    # variation is deliberately incomplete synthetic data, not an official page.
    release_day = 11 if month == 1 else 9
    period = f"2026-{month:02d}"
    content = f"""
    <h1>2026年{month}月份居民消费价格</h1>
    <p>发布时间：2026-{month + 1:02d}-{release_day:02d} 09:30</p>
    <table><tr><th></th><th>环比涨跌幅（%）</th><th>同比涨跌幅（%）</th></tr>
    <tr><td>居民消费价格</td><td>0.2</td><td>0.2</td></tr>
    <tr><td>不包括食品和能源</td><td>0.3</td><td>0.8</td></tr></table>
    """.encode()
    now = datetime(2026, month + 1, release_day, 2, tzinfo=UTC)
    ingested = ingest_official_context_document(
        paths,
        content,
        family="nbs_core_cpi",
        source_url=(
            "https://www.stats.gov.cn/sj/zxfb/202602/t20260211_1962588.html"
            if month == 1
            else "https://www.stats.gov.cn/sj/zxfb/202608/t20260809_1965008.html"
        ),
        expected_period=period,
        fetched_at=now,
        clock=lambda: now,
        definition_version=request["manifest"]["metric_catalog_version"],
    )
    assert len(ingested.claim_ids) == 4
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-03-09" if month == 1 else "2026-08-28",
        client_request_id="admitted-cpi-january",
        model_version_id=model_id,
        system_as_of=now,
        release_event_id=ingested.release_event_id,
        metric_ids=("CN_CPI_HEADLINE", "CN_CORE_CPI"),
        period=period,
    )
    selection = select_retrieval_input(paths, run)
    assert selection.complete is (month == 1)
    if month == 7:
        assert len(selection.missing_members) == 2
        assert all("cumulative_average_yoy" in member for member in selection.missing_members)
    assert set(selection.selected_claim_ids) == set(ingested.claim_ids)


@pytest.mark.parametrize("field", ["source_codes", "release_event_family", "allowed_units"])
def test_cpi_parser_rejects_an_incompatible_registered_contract(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], field: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    definition = next(
        item
        for item in request["manifest"]["metric_definitions"]
        if item["metric_id"] == "CN_CPI_HEADLINE"
    )
    definition[field] = {
        "source_codes": ["another-reviewed-source"],
        "release_event_family": "another-review-family",
        "allowed_units": ["percent", "index_points"],
    }[field]
    package_hash = request["package_hashes"][0]
    package = json.loads((paths.artifacts / package_hash[:2] / package_hash).read_bytes())
    package["definition_bindings"]["CN_CPI_HEADLINE"] = hashlib.sha256(
        encode(definition)
    ).hexdigest()
    bind_synthetic_review(paths, request, package)
    submit(paths, save(paths, request))
    capsys.readouterr()
    now = datetime(2026, 8, 9, 2, tzinfo=UTC)
    with pytest.raises(ValueError, match="registered_cpi_source_contract_unsupported"):
        ingest_official_context_document(
            paths,
            cpi_document(),
            family="nbs_core_cpi",
            source_url="https://www.stats.gov.cn/sj/zxfb/202608/t20260809_1965008.html",
            expected_period="2026-07",
            fetched_at=now,
            clock=lambda: now,
            definition_version=request["manifest"]["metric_catalog_version"],
        )


def test_same_catalog_version_cannot_name_different_reviewed_definitions(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    first, _ = prepared_request(paths)
    submit(paths, save(paths, first))
    admitted = json.loads(capsys.readouterr().out)
    versions_before = ModelRepository(paths.database).list_versions()
    manifest_before = ModelRepository(paths.database).manifest(admitted["model_version_id"])

    second, _ = prepared_request(paths)
    definition = next(
        item
        for item in second["manifest"]["metric_definitions"]
        if item["metric_id"] == "CN_LPR_1Y_5Y"
    )
    definition["name_cn"] = "a different, independently reviewed definition"
    package_hash = second["package_hashes"][0]
    package = json.loads((paths.artifacts / package_hash[:2] / package_hash).read_bytes())
    package["definition_bindings"]["CN_LPR_1Y_5Y"] = hashlib.sha256(encode(definition)).hexdigest()
    bind_synthetic_review(paths, second, package)

    with pytest.raises(SystemExit) as failure:
        submit(paths, save(paths, second))

    assert failure.value.code == 2
    assert "metric_catalog_version_is_immutable" in capsys.readouterr().err
    assert ModelRepository(paths.database).list_versions() == versions_before
    assert ModelRepository(paths.database).manifest(admitted["model_version_id"]) == manifest_before


@pytest.mark.parametrize("saved_official", [False, True])
def test_admitted_catalog_consumes_lpr_through_evidence_selection_and_context(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], saved_official: bool
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    manifest = ModelRepository(paths.database).manifest(model_id)
    version = manifest["metric_catalog_version"]
    acquired_at = datetime(2026, 8, 20, 2, tzinfo=UTC)
    content = (Path(__file__).parents[1] / "fixtures/chinamoney_lpr_20260820.html").read_bytes()
    if saved_official:
        # Real archived bytes and literal expected values; admission and clocks
        # remain synthetic, so this does not grant historical source certification.
        digest = "5b4ddec501ddfe52bfec15d471c8c6d4548b643da9a61f35f9a978825bc04bd5"
        content = (
            Path(__file__).parents[2]
            / ".scratch/pring-data-acquisition-repair/evidence-lpr-import-20260908"
            / digest
        ).read_bytes()
        assert hashlib.sha256(content).hexdigest() == digest
    ingested = ingest_lpr_document(
        paths,
        content,
        source_url="https://www.chinamoney.com.cn/chinese/rdgz/20260820/3399885.html",
        fetched_at=acquired_at,
        expected_period="2026-08",
        definition_version=version,
        clock=lambda: acquired_at,
    )
    repository = EvidenceRepository(paths.database)
    for mode in (AsOfMode.PUBLIC, AsOfMode.SYSTEM):
        points = repository.metric_series(
            "CN_LPR_1Y_5Y", mode=mode, as_of=acquired_at, definition_version=version
        )
        assert {p.dimensions["tenor"]: p.selected_value for p in points} == {
            "1y": 3.0,
            "5y_plus": 3.5,
        }
        assert {p.selected_claim_id for p in points} == set(ingested.claim_ids)
    before_acquisition = datetime(2026, 8, 20, 1, 30, tzinfo=UTC)
    assert not repository.metric_series(
        "CN_LPR_1Y_5Y", mode=AsOfMode.SYSTEM, as_of=before_acquisition, definition_version=version
    )
    assert (
        len(
            repository.metric_series(
                "CN_LPR_1Y_5Y",
                mode=AsOfMode.PUBLIC,
                as_of=before_acquisition,
                definition_version=version,
            )
        )
        == 2
    )
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="admitted-lpr",
        model_version_id=model_id,
        system_as_of=acquired_at,
        release_event_id=ingested.release_event_id,
        metric_ids=("CN_LPR_1Y_5Y",),
        period="2026-08",
    )
    selection = select_retrieval_input(paths, run)
    assert selection.complete
    assert set(selection.selected_claim_ids) == set(ingested.claim_ids)
    context = build_context_projection(repository, as_of=acquired_at, model_manifest=manifest)
    rows = [
        row
        for row in context.macro["credit"]["evidence"]  # type: ignore[index]
        if row["metric_id"] == "CN_LPR_1Y_5Y"
    ]
    assert {row["dimensions"]["tenor"]: row["value"] for row in rows} == {"1y": 3.0, "5y_plus": 3.5}
    assert all(row["status"] == "current" for row in rows)
    model_inputs = context.macro["model_input_observation_version_ids"]
    assert isinstance(model_inputs, list)
    assert set(model_inputs) == set(ingested.claim_ids)
    assert set(ingested.claim_ids) <= set(context.observation_version_ids)
    with pytest.raises(LookupError, match="active_model_unavailable"):
        ModelRepository(paths.database).active()


@pytest.mark.parametrize("consumer", ["selection", "context", "ledger"])
@pytest.mark.parametrize("fault", ["unregistered", "different_definitions"])
def test_generic_model_creation_cannot_borrow_or_register_catalog(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], consumer: str, fault: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    manifest = request["manifest"]
    if fault == "different_definitions":
        submit(paths, save(paths, request))
        capsys.readouterr()
        manifest["metric_definitions"][0]["name_cn"] = "unreviewed changed definition"
    manifest["model_version_id"] = "generic-unreviewed-model"
    ModelRepository(paths.database).create_candidate(manifest)
    expected = (
        "unknown_metric_definition_version"
        if fault == "unregistered"
        else "model_metric_catalog_binding_mismatch"
    )
    with pytest.raises((KeyError, ValueError), match=expected):
        if consumer == "context":
            build_context_projection(
                EvidenceRepository(paths.database),
                as_of=datetime(2026, 8, 28, tzinfo=UTC),
                model_manifest=manifest,
            )
        else:
            run = RunRepository(paths.database).submit(
                command_type="targeted_refresh",
                target_business_date="2026-08-28",
                client_request_id="unreviewed-lpr",
                model_version_id=manifest["model_version_id"],
                system_as_of=datetime(2026, 8, 28, tzinfo=UTC),
                release_event_id="synthetic:lpr",
                metric_ids=("CN_LPR_1Y_5Y",),
                period="2026-08",
            )
            if consumer == "ledger":
                RetrievalLedger(paths.database).bind_run(run, manifest["metric_catalog_version"])
            else:
                select_retrieval_input(paths, run)
    if consumer == "ledger":
        assert RetrievalLedger(paths.database).for_run(run.run_id) is None


def test_reviewed_models_can_share_identical_catalog_in_different_order(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    first_id = json.loads(capsys.readouterr().out)["model_version_id"]
    request["manifest"]["metric_definitions"].reverse()
    package_hash = request["package_hashes"][0]
    package = json.loads((paths.artifacts / package_hash[:2] / package_hash).read_bytes())
    bind_synthetic_review(paths, request, package)
    submit(paths, save(paths, request))
    second_id = json.loads(capsys.readouterr().out)["model_version_id"]
    assert first_id != second_id
    for model_id in (first_id, second_id):
        manifest = ModelRepository(paths.database).manifest(model_id)
        build_context_projection(
            EvidenceRepository(paths.database),
            as_of=datetime(2026, 8, 28, tzinfo=UTC),
            model_manifest=manifest,
        )


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize(("missing_days", "staggered"), [(6, False), (7, False), (6, True)])
def test_warrant_history_coverage_counts_only_complete_daily_warehouses(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    missing_days: int,
    staggered: bool,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    version = request["manifest"]["metric_catalog_version"]
    digest = "6e849804171177debebc666eabf63388c21066fe695a06f75f6c2cc47043f120"
    raw = (
        Path(__file__).parents[2]
        / ".scratch/pring-data-acquisition-repair/evidence-04"
        / f"{digest}.json"
    ).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == digest
    required = tuple(
        sorted(
            {date.fromisoformat(row["tradeDate"]).isoformat() for row in json.loads(raw)["data"]}
        )
    )
    assert len(required) == 120
    assert (required[0], required[-1]) == ("2026-03-09", "2026-08-28")
    # Only the date set comes from the saved official index response.
    # All warrant values, publication times, and source certification are synthetic.
    missing = set(required[40 : 40 + missing_days])
    pp_missing = set(required[60:66]) if staggered else set()
    symbols = ("CF", "CU", "PP", "RB", "RU", "SC", "SP", "TA")

    def transport(payload: dict[str, Any]) -> bytes:
        symbol = str(payload["params"]["symbol"])
        start = date.fromisoformat(payload["params"]["start_date"]).isoformat()
        end = date.fromisoformat(payload["params"]["end_date"]).isoformat()
        unit = "桶" if symbol == "SC" else "张" if symbol in {"CF", "PTA"} else "吨"
        rows = []
        for period in required:
            if start <= period <= end:
                day = period.replace("-", "")
                rows.append(
                    [
                        day,
                        symbol,
                        "synthetic-first",
                        None,
                        None if symbol == "PP" and period in pp_missing else 100,
                        None,
                        unit,
                        "synthetic",
                    ]
                )
                if symbol == "CU":
                    rows.append(
                        [
                            day,
                            symbol,
                            "synthetic-second",
                            None,
                            None if period in missing else 25,
                            None,
                            unit,
                            "synthetic",
                        ]
                    )
        return encode(
            {
                "code": 0,
                "data": {
                    "fields": [
                        "trade_date",
                        "symbol",
                        "warehouse",
                        "pre_vol",
                        "vol",
                        "vol_chg",
                        "unit",
                        "exchange",
                    ],
                    "items": rows,
                },
            }
        )

    adapter = TushareContextAdapter("synthetic-token", transport=transport)

    def retrieve() -> tuple[ContextScalar, ...]:
        return tuple(
            replace(
                scalar,
                release_at=datetime.fromisoformat(f"{scalar.period_end}T09:00:00+00:00"),
                public_available_at=datetime.fromisoformat(f"{scalar.period_end}T09:00:00+00:00"),
            )
            for symbol in symbols
            for scalar in adapter.futures_warrants(
                start_date=date(2026, 3, 9), end_date=date(2026, 8, 28), symbol=symbol
            )
        )

    adapter.acquire_scalars(paths, retrieve, definition_version=version)
    context = build_context_projection(
        EvidenceRepository(paths.database),
        as_of=datetime(2026, 8, 28, 9, tzinfo=UTC),
        as_of_mode=AsOfMode.PUBLIC,
        model_manifest=ModelRepository(paths.database).manifest(model_id),
        target_business_date="2026-08-28",
        visible_evidence_start="2026-03-09",
    )
    coverage = context.warrant_history
    assert coverage is not None
    assert len(coverage.complete_periods["CU"]) == (114 if missing_days == 6 else 113)
    assert len(coverage.complete_periods["PP"]) == (114 if staggered else 120)
    assert all(
        len(coverage.complete_periods[symbol]) == 120
        for symbol in symbols
        if symbol not in {"CU", "PP"}
    )
    if staggered:
        assert (
            len(set(coverage.complete_periods["CU"]) & set(coverage.complete_periods["PP"])) == 108
        )
    assert missing.isdisjoint(coverage.complete_periods["CU"])
    assert coverage.is_ready(required) is (missing_days == 6)
    assert not coverage.is_ready(required[:-1])
    assert not coverage.is_ready((*required[:-1], required[-2]))


@pytest.mark.parametrize(
    ("case", "exception_type", "message"),
    [
        ("missing_key", ValueError, "eia_api_key_required"),
        ("source_failed", OSError, "synthetic_eia_unavailable"),
        ("invalid_response", ValueError, "eia_response_json_invalid"),
    ],
)
@pytest.mark.usefixtures("runtime_clock")
def test_registered_catalog_eia_api_failure_keeps_receipt_without_claims(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    case: str,
    exception_type: type[Exception],
    message: str,
) -> None:
    from pring_cycle.eia_context import EiaPetroleumAdapter

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    version = ModelRepository(paths.database).manifest(model_id)["metric_catalog_version"]
    raw = b"not JSON"

    def transport(parameters: dict[str, object]) -> bytes:
        if case == "source_failed":
            raise OSError("synthetic_eia_unavailable")
        return raw

    with pytest.raises(exception_type, match=message):
        adapter = EiaPetroleumAdapter(
            "" if case == "missing_key" else "synthetic-api-key", transport=transport
        )
        adapter.acquire_spot_prices(
            paths,
            start_date=date(2026, 8, 27),
            end_date=date(2026, 8, 27),
            definition_version=version,
        )
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    if case == "missing_key":
        assert acquisitions.history() == ()
    else:
        (receipt,) = acquisitions.history()
        assert receipt.api_name == "eia_spot_prices"
        assert receipt.state == "failed" and receipt.error_type == exception_type.__name__
        assert receipt.normalized_hash is None and receipt.validated_at is None
        assert "api_key" not in receipt.parameters
        if case == "source_failed":
            assert receipt.raw_hash is None and receipt.received_at is None
        else:
            assert acquisitions.read_content(receipt.acquisition_id, "raw") == raw
            assert receipt.received_at is not None
    evidence = EvidenceRepository(paths.database)
    for metric in ("EIA_BRENT_RBRTE", "EIA_WTI_RWTC"):
        assert (
            evidence.metric_series(
                metric, mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC), definition_version=version
            )
            == ()
        )


@pytest.mark.parametrize("outcome", ["source_failed", "validation_failed"])
@pytest.mark.usefixtures("runtime_clock")
def test_registered_catalog_eia_html_cli_failure_keeps_classified_attempt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    outcome: str,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    version = ModelRepository(paths.database).manifest(model_id)["metric_catalog_version"]
    raw = b"<html><body>Synthetic malformed history</body></html>"

    class Response(BytesIO):
        status = 200
        headers = {"Content-Type": "text/html; charset=utf-8"}

        def geturl(self) -> str:
            return "https://www.eia.gov/dnav/pet/hist/RBRTED.htm"

    def fetch(request: Any, *, timeout: float) -> Response:
        assert request.full_url == "https://www.eia.gov/dnav/pet/hist/RBRTED.htm"
        if outcome == "source_failed":
            raise OSError("synthetic_eia_unavailable")
        return Response(raw)

    monkeypatch.setattr("pring_cycle.eia_html.open_no_redirects", fetch)
    with pytest.raises(OSError if outcome == "source_failed" else SystemExit) as failure:
        main(
            [
                "eia-html-refresh",
                "--runtime-root",
                str(paths.override_root),
                "--series",
                "RBRTE",
                "--start",
                "2026-08-31",
                "--end",
                "2026-09-04",
                "--definition-version",
                version,
                "--json",
            ]
        )
    if outcome == "source_failed":
        assert isinstance(failure.value, OSError)
        assert str(failure.value) == "synthetic_eia_unavailable"
    else:
        assert isinstance(failure.value, SystemExit)
        assert failure.value.code == 2
        assert "eia_history_" in capsys.readouterr().err
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    (receipt,) = acquisitions.history()
    assert receipt.api_name == "eia_history_html" and receipt.state == "failed"
    assert receipt.normalized_hash is None and receipt.validated_at is None
    assert receipt.parameters["definition_version"] == version
    if outcome == "source_failed":
        assert receipt.error_type == "OSError"
        assert receipt.raw_hash is None and receipt.received_at is None
    else:
        assert receipt.error_type == "ValueError"
        assert receipt.received_at is not None
        assert acquisitions.read_content(receipt.acquisition_id, "raw") == raw
    evidence = EvidenceRepository(paths.database)
    assert (
        evidence.metric_series(
            "EIA_BRENT_RBRTE",
            mode=AsOfMode.SYSTEM,
            as_of=datetime.now(UTC),
            definition_version=version,
        )
        == ()
    )
    attempt = evidence.latest_retrieval_attempt(
        "EIA_BRENT_RBRTE",
        period="2026-09-04",
        as_of=datetime.now(UTC),
        definition_version=version,
    )
    assert attempt is not None and attempt.outcome == outcome
    assert attempt.safe_metadata["acquisition_ids"] == receipt.acquisition_id
    assert attempt.safe_metadata["error_type"] == receipt.error_type


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize(
    "fault",
    [
        "missing_exchange",
        "duplicate_exchange",
        "wrong_unit",
        "wrong_value",
        "wrong_scope",
        "bad_response",
        "missing_value",
        "negative_value",
        "wrong_period",
        "wrong_exchange",
    ],
)
def test_registered_margin_rejects_invalid_delivery_with_failed_receipt(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], fault: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    version = ModelRepository(paths.database).manifest(model_id)["metric_catalog_version"]
    rows: list[list[Any]] = [
        ["20260828", "SSE", 100_000_000, 10_000_000],
        ["20260828", "SZSE", 200_000_000, 20_000_000],
        ["20260828", "BSE", 300_000_000, 30_000_000],
    ]
    if fault == "wrong_period":
        for row in rows:
            row[0] = "20260827"
    elif fault == "wrong_exchange":
        rows[-1][1] = "NYSE"
    elif fault == "missing_exchange":
        # Before the newest day: the newest day alone may still be waiting for an exchange.
        rows = [["20260827", "SSE", 90_000_000, 9_000_000], *rows]
    elif fault == "duplicate_exchange":
        rows.append(rows[-1].copy())
    elif fault == "missing_value":
        rows[-1][-1] = None
    elif fault == "negative_value":
        rows[-1][-1] = -30_000_000
    raw = (
        b"not JSON"
        if fault == "bad_response"
        else encode(
            {
                "code": 0,
                "data": {"fields": ["trade_date", "exchange_id", "rzye", "rzmre"], "items": rows},
            }
        )
    )
    adapter = TushareContextAdapter("synthetic-token", transport=lambda _: raw)

    def retrieve() -> tuple[ContextScalar, ...]:
        start = date(2026, 8, 27) if fault == "missing_exchange" else date(2026, 8, 28)
        scalars = adapter.margin_financing(start_date=start, end_date=date(2026, 8, 28))
        if fault == "wrong_unit":
            return tuple(replace(s, unit="cny") for s in scalars)
        if fault == "wrong_value":
            return (replace(scalars[0], value=60), *scalars[1:])
        if fault == "wrong_scope":
            return tuple(
                replace(s, dimensions={**s.dimensions, "scope": "SSE+SZSE"}) for s in scalars
            )
        return scalars

    with pytest.raises(ValueError):
        adapter.acquire_scalars(paths, retrieve, definition_version=version)
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    (receipt,) = acquisitions.history()
    assert receipt.state == "failed"
    assert receipt.error_type in {"ValueError", "JSONDecodeError"}
    assert receipt.validated_at is None
    assert acquisitions.read_content(receipt.acquisition_id, "raw") == raw
    assert (
        EvidenceRepository(paths.database).metric_series(
            "CN_MARGIN_BALANCE",
            mode=AsOfMode.SYSTEM,
            as_of=datetime.now(UTC),
            definition_version=version,
        )
        == ()
    )


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("artifact_kind", ["raw", "normalized"])
@pytest.mark.parametrize("damage", ["corrupt", "missing"])
def test_registered_margin_selection_requires_readable_originals(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], artifact_kind: str, damage: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    version = ModelRepository(paths.database).manifest(model_id)["metric_catalog_version"]
    raw = encode(
        {
            "code": 0,
            "data": {
                "fields": ["trade_date", "exchange_id", "rzye", "rzmre"],
                "items": [
                    ["20260828", "SSE", 100_000_000, 10_000_000],
                    ["20260828", "SZSE", 200_000_000, 20_000_000],
                    ["20260828", "BSE", 300_000_000, 30_000_000],
                ],
            },
        }
    )
    adapter = TushareContextAdapter("synthetic-token", transport=lambda _: raw)
    # Explicit synthetic publication assertion; not evidence of a real exchange release.
    published = datetime(2026, 8, 28, 8, tzinfo=UTC)
    result = adapter.acquire_scalars(
        paths,
        lambda: tuple(
            replace(s, release_at=published, public_available_at=published)
            for s in adapter.margin_financing(
                start_date=date(2026, 8, 28), end_date=date(2026, 8, 28)
            )
        ),
        definition_version=version,
    )
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="synthetic-margin-original-integrity",
        model_version_id=model_id,
        system_as_of=datetime.now(UTC),
        release_event_id="synthetic:margin",
        metric_ids=("CN_MARGIN_BALANCE",),
        period="2026-08-28",
    )
    selection = select_retrieval_input(paths, run)
    assert selection.complete
    assert set(selection.selected_claim_ids) == set(result.claim_ids)
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    (receipt,) = acquisitions.history()
    digest = receipt.raw_hash if artifact_kind == "raw" else receipt.normalized_hash
    assert digest is not None
    original = paths.artifacts / digest[:2] / digest
    if damage == "missing":
        original.unlink()
    else:
        original.write_bytes(b"damaged source delivery")
    rejected = select_retrieval_input(paths, run)
    assert not rejected.complete
    assert rejected.selected_claim_ids == ()


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("publication", ["known", "unknown", "future"])
def test_registered_margin_candidate_selection_respects_publication_cutoff(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], publication: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    version = ModelRepository(paths.database).manifest(model_id)["metric_catalog_version"]
    raw = encode(
        {
            "code": 0,
            "data": {
                "fields": ["trade_date", "exchange_id", "rzye", "rzmre"],
                "items": [
                    ["20260828", "SSE", 100_000_000, 10_000_000],
                    ["20260828", "SZSE", 200_000_000, 20_000_000],
                    ["20260828", "BSE", 300_000_000, 30_000_000],
                ],
            },
        }
    )
    # These are synthetic time assertions to exercise the two existing query modes.
    published = (
        None
        if publication == "unknown"
        else datetime(2026, 8, 31 if publication == "future" else 28, 8, tzinfo=UTC)
    )
    adapter = TushareContextAdapter("synthetic-token", transport=lambda _: raw)
    result = adapter.acquire_scalars(
        paths,
        lambda: tuple(
            replace(s, release_at=published, public_available_at=published)
            for s in adapter.margin_financing(
                start_date=date(2026, 8, 28), end_date=date(2026, 8, 28)
            )
        ),
        definition_version=version,
    )
    repository = EvidenceRepository(paths.database)
    visible = repository.metric_series(
        "CN_MARGIN_BALANCE",
        mode=AsOfMode.PUBLIC,
        as_of=datetime(2026, 8, 28, 8, tzinfo=UTC),
        definition_version=version,
    )
    assert len(visible) == (2 if publication == "known" else 0)
    assert (
        len(
            repository.metric_series(
                "CN_MARGIN_BALANCE",
                mode=AsOfMode.SYSTEM,
                as_of=datetime.now(UTC),
                definition_version=version,
            )
        )
        == 2
    )
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="synthetic-margin-publication",
        model_version_id=model_id,
        system_as_of=datetime.now(UTC),
        release_event_id="synthetic:margin-publication",
        metric_ids=("CN_MARGIN_BALANCE",),
        period="2026-08-28",
    )
    selection = select_retrieval_input(paths, run)
    assert selection.complete is (publication == "known")
    assert set(selection.selected_claim_ids) == (
        set(result.claim_ids) if publication == "known" else set()
    )


@pytest.mark.usefixtures("runtime_clock")
def test_registered_market_indices_keep_each_identity_value_and_original(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    models = ModelRepository(paths.database)
    manifest = models.manifest(model_id)
    assert len(manifest["metric_definitions"]) == 61
    version = manifest["metric_catalog_version"]
    # Independent synthetic identities and closing points, never real certification.
    expected = {
        "CN_EQ_CSI300": ("index_daily", "000300.SH", 3000.25),
        "CN_EQ_CSI500": ("index_daily", "000905.SH", 5000.5),
        "CN_EQ_CSI1000": ("index_daily", "000852.SH", 6000.75),
        "CN_BOND_FULL_PRICE_CNY030": ("index_daily", "000012CNY030.CSI", 123.45),
        "CN_BOND_10Y_930916": ("index_daily", "930916.CSI", 234.56),
        "CN_COMMODITY_BROAD_NHCI": ("fut_index_daily", "NHCI.NH", 2100.125),
    }
    originals = {}

    def transport(payload: dict[str, Any]) -> bytes:
        source_code = payload["params"]["ts_code"]
        api_name, _, value = next(row for row in expected.values() if row[1] == source_code)
        assert payload["api_name"] == api_name
        assert payload["fields"] == "ts_code,trade_date,close"
        assert payload["params"] == {
            "ts_code": source_code,
            "start_date": "20260828",
            "end_date": "20260828",
        }
        raw = encode(
            {
                "code": 0,
                "data": {
                    "fields": ["ts_code", "trade_date", "close"],
                    "items": [[source_code, "20260828", value]],
                },
            }
        )
        originals[source_code] = raw
        return raw

    adapter = TushareContextAdapter("synthetic-token", transport=transport)
    before = datetime.now(UTC)
    result = adapter.acquire_scalars(
        paths,
        lambda: adapter.market_indices(start_date=date(2026, 8, 28), end_date=date(2026, 8, 28)),
        definition_version=version,
    )
    after = datetime.now(UTC)
    assert result.observation_count == 6
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    assert len(acquisitions.history()) == 6
    evidence = EvidenceRepository(paths.database)
    for metric_id, (api_name, source_code, value) in expected.items():
        assert (
            evidence.metric_series(
                metric_id, mode=AsOfMode.SYSTEM, as_of=before, definition_version=version
            )
            == ()
        )
        (point,) = evidence.metric_series(
            metric_id, mode=AsOfMode.SYSTEM, as_of=after, definition_version=version
        )
        assert point.selected_value == value
        assert point.period_start == point.period_end == "2026-08-28"
        assert point.dimensions == {"source_code": source_code}
        (claim,) = point.claims
        assert claim.unit == "index_points"
        assert claim.source_reference == f"tushare:{api_name}:close:2026-08-28"
        assert claim.parsed_public_available_at is None and claim.release_at is None
        trace = evidence.trace(point.observation_id, mode=AsOfMode.SYSTEM, as_of=after)
        (receipt,) = trace.acquisitions
        assert receipt.state == "validated" and receipt.api_name == api_name
        assert receipt.parameters["ts_code"] == source_code
        assert acquisitions.read_content(receipt.acquisition_id, "raw") == originals[source_code]
    assert models.manifest(model_id) == manifest


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("source_code", ["000905.SH", "NHCI.NH"])
def test_registered_market_indices_reject_duplicate_day_before_validation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], source_code: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    version = ModelRepository(paths.database).manifest(model_id)["metric_catalog_version"]
    originals = {}

    def transport(payload: dict[str, Any]) -> bytes:
        code = payload["params"]["ts_code"]
        rows = [[code, "20260828", 123.5]]
        if code == source_code:
            rows.append(rows[0].copy())
        raw = encode(
            {"code": 0, "data": {"fields": ["ts_code", "trade_date", "close"], "items": rows}}
        )
        originals[code] = raw
        return raw

    adapter = TushareContextAdapter("synthetic-token", transport=transport)
    with pytest.raises(ValueError):
        adapter.acquire_scalars(
            paths,
            lambda: adapter.market_indices(
                start_date=date(2026, 8, 28), end_date=date(2026, 8, 28)
            ),
            definition_version=version,
        )
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    receipts = acquisitions.history()
    assert any(r.parameters["ts_code"] == source_code for r in receipts)
    for receipt in receipts:
        assert receipt.state == "failed" and receipt.validated_at is None
        assert (
            acquisitions.read_content(receipt.acquisition_id, "raw")
            == originals[receipt.parameters["ts_code"]]
        )
    evidence = EvidenceRepository(paths.database)
    for metric_id in (
        "CN_EQ_CSI300",
        "CN_EQ_CSI500",
        "CN_EQ_CSI1000",
        "CN_BOND_FULL_PRICE_CNY030",
        "CN_BOND_10Y_930916",
        "CN_COMMODITY_BROAD_NHCI",
    ):
        assert (
            evidence.metric_series(
                metric_id, mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC), definition_version=version
            )
            == ()
        )


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("source_code", ["000905.SH", "NHCI.NH"])
@pytest.mark.parametrize(
    "fault",
    [
        "wrong_unit",
        "wrong_value",
        "wrong_scope",
        "missing_member",
        "wrong_identity",
        "wrong_period",
        "missing_value",
        "bad_response",
    ],
)
def test_registered_market_indices_reject_invalid_delivery_before_validation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], source_code: str, fault: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    version = ModelRepository(paths.database).manifest(model_id)["metric_catalog_version"]
    originals = {}

    def transport(payload: dict[str, Any]) -> bytes:
        code = payload["params"]["ts_code"]
        row: list[Any] = [code, "20260828", 123.5]
        if code == source_code:
            if fault == "wrong_identity":
                row[0] = "unexpected-index"
            elif fault == "wrong_period":
                row[1] = "20260827"
            elif fault == "missing_value":
                row[2] = None
        raw = encode(
            {
                "code": 0,
                "data": {
                    "fields": ["ts_code", "trade_date", "close"],
                    "items": [row],
                },
            }
        )
        if code == source_code and fault == "bad_response":
            raw = b"not JSON"
        originals[code] = raw
        return raw

    adapter = TushareContextAdapter("synthetic-token", transport=transport)

    def retrieve() -> tuple[ContextScalar, ...]:
        scalars = adapter.market_indices(start_date=date(2026, 8, 28), end_date=date(2026, 8, 28))
        delivered = []
        for scalar in scalars:
            if scalar.dimensions["source_code"] == source_code:
                if fault == "missing_member":
                    continue
                if fault == "wrong_unit":
                    scalar = replace(scalar, unit="percent")
                elif fault == "wrong_value":
                    scalar = replace(scalar, value=1235.0)
                elif fault == "wrong_scope":
                    scalar = replace(scalar, dimensions={"source_code": "000300.SH"})
            delivered.append(scalar)
        return tuple(delivered)

    with pytest.raises(ValueError):
        adapter.acquire_scalars(paths, retrieve, definition_version=version)
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    assert any(r.parameters["ts_code"] == source_code for r in acquisitions.history())
    for receipt in acquisitions.history():
        assert receipt.state == "failed" and receipt.validated_at is None
        assert (
            acquisitions.read_content(receipt.acquisition_id, "raw")
            == originals[receipt.parameters["ts_code"]]
        )
    evidence = EvidenceRepository(paths.database)
    for metric_id in (
        "CN_EQ_CSI300",
        "CN_EQ_CSI500",
        "CN_EQ_CSI1000",
        "CN_BOND_FULL_PRICE_CNY030",
        "CN_BOND_10Y_930916",
        "CN_COMMODITY_BROAD_NHCI",
    ):
        assert (
            evidence.metric_series(
                metric_id, mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC), definition_version=version
            )
            == ()
        )


@pytest.mark.parametrize("damage", ["corrupt", "missing"])
@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize(
    "metric_id,source_code", [("CN_EQ_CSI500", "000905.SH"), ("CN_COMMODITY_BROAD_NHCI", "NHCI.NH")]
)
@pytest.mark.parametrize("artifact_kind", ["raw", "normalized"])
def test_registered_market_index_selection_requires_its_originals(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    metric_id: str,
    source_code: str,
    artifact_kind: str,
    damage: str,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    version = ModelRepository(paths.database).manifest(model_id)["metric_catalog_version"]

    def transport(payload: dict[str, Any]) -> bytes:
        return encode(
            {
                "code": 0,
                "data": {
                    "fields": ["ts_code", "trade_date", "close"],
                    "items": [[payload["params"]["ts_code"], "20260828", 123.5]],
                },
            }
        )

    adapter = TushareContextAdapter("synthetic-token", transport=transport)
    # Synthetic publication assertion, not historical official publication evidence.
    published = datetime(2026, 8, 28, 8, tzinfo=UTC)
    adapter.acquire_scalars(
        paths,
        lambda: tuple(
            replace(s, release_at=published, public_available_at=published)
            for s in adapter.market_indices(
                start_date=date(2026, 8, 28), end_date=date(2026, 8, 28)
            )
        ),
        definition_version=version,
    )
    runs = {}
    for selected in (metric_id, "CN_EQ_CSI300"):
        runs[selected] = RunRepository(paths.database).submit(
            command_type="targeted_refresh",
            target_business_date="2026-08-28",
            client_request_id="synthetic-index-original-" + selected,
            model_version_id=model_id,
            system_as_of=datetime.now(UTC),
            release_event_id="synthetic:index",
            metric_ids=(selected,),
            period="2026-08-28",
        )
        selection = select_retrieval_input(paths, runs[selected])
        assert selection.complete and len(selection.selected_claim_ids) == 1
    receipt = next(
        r
        for r in AcquisitionRepository(paths.database, paths.artifacts).history()
        if r.parameters["ts_code"] == source_code
    )
    digest = receipt.raw_hash if artifact_kind == "raw" else receipt.normalized_hash
    assert digest is not None
    original = paths.artifacts / digest[:2] / digest
    if damage == "missing":
        original.unlink()
    else:
        original.write_bytes(b"damaged index original")
    rejected = select_retrieval_input(paths, runs[metric_id])
    assert not rejected.complete and rejected.selected_claim_ids == ()
    assert select_retrieval_input(paths, runs["CN_EQ_CSI300"]).complete


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("publication", ["known", "unknown", "future"])
def test_registered_market_indices_respect_publication_cutoff(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], publication: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    version = ModelRepository(paths.database).manifest(model_id)["metric_catalog_version"]
    cutoff = datetime(2026, 8, 28, 8, tzinfo=UTC)
    public_at = (
        None
        if publication == "unknown"
        else cutoff
        if publication == "known"
        else datetime(2026, 8, 28, 9, tzinfo=UTC)
    )

    def transport(payload: dict[str, Any]) -> bytes:
        return encode(
            {
                "code": 0,
                "data": {
                    "fields": ["ts_code", "trade_date", "close"],
                    "items": [[payload["params"]["ts_code"], "20260828", 123.5]],
                },
            }
        )

    adapter = TushareContextAdapter("synthetic-token", transport=transport)
    # Explicitly synthetic publication metadata; official historical evidence remains open.
    adapter.acquire_scalars(
        paths,
        lambda: tuple(
            replace(s, release_at=public_at, public_available_at=public_at)
            for s in adapter.market_indices(
                start_date=date(2026, 8, 28), end_date=date(2026, 8, 28)
            )
        ),
        definition_version=version,
    )
    evidence = EvidenceRepository(paths.database)
    for metric_id in (
        "CN_EQ_CSI300",
        "CN_EQ_CSI500",
        "CN_EQ_CSI1000",
        "CN_BOND_FULL_PRICE_CNY030",
        "CN_BOND_10Y_930916",
        "CN_COMMODITY_BROAD_NHCI",
    ):
        visible = evidence.metric_series(
            metric_id, mode=AsOfMode.PUBLIC, as_of=cutoff, definition_version=version
        )
        assert len(visible) == (1 if publication == "known" else 0)
        assert (
            len(
                evidence.metric_series(
                    metric_id,
                    mode=AsOfMode.SYSTEM,
                    as_of=datetime.now(UTC),
                    definition_version=version,
                )
            )
            == 1
        )
        run = RunRepository(paths.database).submit(
            command_type="targeted_refresh",
            target_business_date="2026-08-28",
            client_request_id="synthetic-index-time-" + metric_id,
            model_version_id=model_id,
            system_as_of=cutoff,
            release_event_id="synthetic:index",
            metric_ids=(metric_id,),
            period="2026-08-28",
        )
        selection = select_retrieval_input(paths, run, mode=AsOfMode.PUBLIC)
        assert selection.complete is (publication == "known")
        assert len(selection.selected_claim_ids) == (1 if publication == "known" else 0)


@pytest.mark.usefixtures("runtime_clock")
def test_registered_valuation_keeps_all_nine_static_members_and_originals(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    models = ModelRepository(paths.database)
    manifest = models.manifest(model_id)
    assert len(manifest["metric_definitions"]) == 61
    version = manifest["metric_catalog_version"]
    expected = {
        "000300.SH": {"price_earnings": 12.0, "price_book": 1.2, "turnover_rate": 0.5},
        "000905.SH": {"price_earnings": 20.0, "price_book": 2.0, "turnover_rate": 0.8},
        "000852.SH": {"price_earnings": 30.0, "price_book": 3.0, "turnover_rate": 1.1},
    }
    originals = {}

    def transport(payload: dict[str, Any]) -> bytes:
        assert payload["api_name"] == "index_dailybasic"
        assert payload["fields"] == "ts_code,trade_date,pe,pb,turnover_rate"
        code = payload["params"]["ts_code"]
        assert payload["params"] == {
            "ts_code": code,
            "start_date": "20260828",
            "end_date": "20260828",
        }
        values = expected[code]
        raw = encode(
            {
                "code": 0,
                "data": {
                    "fields": ["ts_code", "trade_date", "pe", "pb", "turnover_rate"],
                    "items": [
                        [
                            code,
                            "20260828",
                            values["price_earnings"],
                            values["price_book"],
                            values["turnover_rate"],
                        ]
                    ],
                },
            }
        )
        originals[code] = raw
        return raw

    adapter = TushareContextAdapter("synthetic-token", transport=transport)
    # Synthetic publication assertion, not evidence of an official historical release.
    public_at = datetime(2026, 8, 28, 8, tzinfo=UTC)
    result = adapter.acquire_scalars(
        paths,
        lambda: tuple(
            replace(s, release_at=public_at, public_available_at=public_at)
            for s in adapter.index_valuation(
                start_date=date(2026, 8, 28), end_date=date(2026, 8, 28)
            )
        ),
        definition_version=version,
    )
    assert result.observation_count == 9
    evidence = EvidenceRepository(paths.database)
    points = evidence.metric_series(
        "CN_INDEX_VALUATION", mode=AsOfMode.PUBLIC, as_of=public_at, definition_version=version
    )
    assert len(points) == 9
    assert {(p.dimensions["index"], p.dimensions["measure"]) for p in points} == {
        (code, measure)
        for code in expected
        for measure in ("price_earnings", "price_book", "turnover_rate")
    }
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    assert len(acquisitions.history()) == 3
    for point in points:
        code, measure = point.dimensions["index"], point.dimensions["measure"]
        assert point.selected_value == expected[code][measure]
        assert point.period_start == point.period_end == "2026-08-28"
        (claim,) = point.claims
        assert claim.unit == ("percent" if measure == "turnover_rate" else "multiple")
        field = {"price_earnings": "pe", "price_book": "pb", "turnover_rate": "turnover_rate"}[
            measure
        ]
        assert claim.source_reference == f"tushare:index_dailybasic:{field}:2026-08-28"
        trace = evidence.trace(point.observation_id, mode=AsOfMode.PUBLIC, as_of=public_at)
        (receipt,) = trace.acquisitions
        assert receipt.state == "validated" and receipt.parameters["ts_code"] == code
        assert acquisitions.read_content(receipt.acquisition_id, "raw") == originals[code]
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="synthetic-valuation-nine-members",
        model_version_id=model_id,
        system_as_of=datetime.now(UTC),
        release_event_id="synthetic:valuation",
        metric_ids=("CN_INDEX_VALUATION",),
        period="2026-08-28",
    )
    selection = select_retrieval_input(paths, run)
    assert selection.complete and set(selection.selected_claim_ids) == set(result.claim_ids)
    assert models.manifest(model_id) == manifest


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize(
    "fault",
    [
        "ttm_measure",
        "duplicate_day",
        "ttm_column",
        "wrong_index",
        "wrong_period",
        "wrong_unit",
        "wrong_value",
        "bad_response",
    ],
)
def test_registered_valuation_rejects_invalid_delivery_before_validation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], fault: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    version = ModelRepository(paths.database).manifest(model_id)["metric_catalog_version"]
    originals = {}

    def transport(payload: dict[str, Any]) -> bytes:
        code = payload["params"]["ts_code"]
        fields = ["ts_code", "trade_date", "pe", "pb", "turnover_rate"]
        rows: list[list[Any]] = [[code, "20260828", 12.0, 1.2, 0.5]]
        if code == "000852.SH":
            if fault == "ttm_column":
                fields[2] = "pe_ttm"
            elif fault == "wrong_index":
                rows[0][0] = "000300.SH"
            elif fault == "wrong_period":
                rows[0][1] = "20260827"
        if code == "000852.SH" and fault == "duplicate_day":
            rows.append(rows[0].copy())
        raw = encode(
            {
                "code": 0,
                "data": {
                    "fields": fields,
                    "items": rows,
                },
            }
        )
        if code == "000852.SH" and fault == "bad_response":
            raw = b"not JSON"
        originals[code] = raw
        return raw

    adapter = TushareContextAdapter("synthetic-token", transport=transport)

    def retrieve() -> tuple[ContextScalar, ...]:
        scalars = adapter.index_valuation(start_date=date(2026, 8, 28), end_date=date(2026, 8, 28))
        delivered = []
        for scalar in scalars:
            if scalar.dimensions == {"index": "000852.SH", "measure": "price_earnings"}:
                if fault == "ttm_measure":
                    scalar = replace(scalar, source_field="pe_ttm")
                elif fault == "wrong_unit":
                    scalar = replace(scalar, unit="percent")
                elif fault == "wrong_value":
                    scalar = replace(scalar, value=120.0)
            delivered.append(scalar)
        return tuple(delivered)

    with pytest.raises(ValueError):
        adapter.acquire_scalars(paths, retrieve, definition_version=version)
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    assert len(acquisitions.history()) == 3
    for receipt in acquisitions.history():
        assert receipt.state == "failed" and receipt.validated_at is None
        assert (
            acquisitions.read_content(receipt.acquisition_id, "raw")
            == originals[receipt.parameters["ts_code"]]
        )
    assert (
        EvidenceRepository(paths.database).metric_series(
            "CN_INDEX_VALUATION",
            mode=AsOfMode.SYSTEM,
            as_of=datetime.now(UTC),
            definition_version=version,
        )
        == ()
    )


@pytest.mark.parametrize("damage", ["corrupt", "missing"])
@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("artifact_kind", ["raw", "normalized"])
def test_registered_valuation_selection_rejects_damaged_index_originals(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], artifact_kind: str, damage: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    version = ModelRepository(paths.database).manifest(model_id)["metric_catalog_version"]

    def transport(payload: dict[str, Any]) -> bytes:
        return encode(
            {
                "code": 0,
                "data": {
                    "fields": ["ts_code", "trade_date", "pe", "pb", "turnover_rate"],
                    "items": [[payload["params"]["ts_code"], "20260828", 12.0, 1.2, 0.5]],
                },
            }
        )

    adapter = TushareContextAdapter("synthetic-token", transport=transport)
    public_at = datetime(2026, 8, 28, 8, tzinfo=UTC)
    result = adapter.acquire_scalars(
        paths,
        lambda: tuple(
            replace(s, release_at=public_at, public_available_at=public_at)
            for s in adapter.index_valuation(
                start_date=date(2026, 8, 28), end_date=date(2026, 8, 28)
            )
        ),
        definition_version=version,
    )
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="synthetic-valuation-original",
        model_version_id=model_id,
        system_as_of=datetime.now(UTC),
        release_event_id="synthetic:valuation",
        metric_ids=("CN_INDEX_VALUATION",),
        period="2026-08-28",
    )
    before = select_retrieval_input(paths, run)
    assert before.complete and set(before.selected_claim_ids) == set(result.claim_ids)
    points = EvidenceRepository(paths.database).metric_series(
        "CN_INDEX_VALUATION", mode=AsOfMode.PUBLIC, as_of=public_at, definition_version=version
    )
    unaffected = {p.selected_claim_id for p in points if p.dimensions["index"] != "000852.SH"}
    receipt = next(
        r
        for r in AcquisitionRepository(paths.database, paths.artifacts).history()
        if r.parameters["ts_code"] == "000852.SH"
    )
    digest = receipt.raw_hash if artifact_kind == "raw" else receipt.normalized_hash
    assert digest is not None
    original = paths.artifacts / digest[:2] / digest
    if damage == "missing":
        original.unlink()
    else:
        original.write_bytes(b"damaged valuation original")
    after = select_retrieval_input(paths, run)
    assert not after.complete
    assert set(after.selected_claim_ids) == unaffected
    assert len(after.selected_claim_ids) == 6 and len(after.missing_members) == 3
    assert all("000852.SH" in missing for missing in after.missing_members)


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize(
    "fault,expected_count", [("missing_static_pe", 8), ("ttm_only", 8), ("empty_index", 6)]
)
def test_registered_valuation_keeps_missing_members_incomplete(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], fault: str, expected_count: int
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    version = ModelRepository(paths.database).manifest(model_id)["metric_catalog_version"]
    originals = {}

    def transport(payload: dict[str, Any]) -> bytes:
        code = payload["params"]["ts_code"]
        fields = ["ts_code", "trade_date", "pe", "pb", "turnover_rate"]
        row: list[Any] = [code, "20260828", 12.0, 1.2, 0.5]
        if code == "000852.SH":
            row[2] = None
            if fault == "ttm_only":
                fields.append("pe_ttm")
                row.append(40.0)
        rows = [] if code == "000852.SH" and fault == "empty_index" else [row]
        raw = encode({"code": 0, "data": {"fields": fields, "items": rows}})
        originals[code] = raw
        return raw

    adapter = TushareContextAdapter("synthetic-token", transport=transport)
    public_at = datetime(2026, 8, 28, 8, tzinfo=UTC)
    result = adapter.acquire_scalars(
        paths,
        lambda: tuple(
            replace(s, release_at=public_at, public_available_at=public_at)
            for s in adapter.index_valuation(
                start_date=date(2026, 8, 28), end_date=date(2026, 8, 28)
            )
        ),
        definition_version=version,
    )
    assert result.observation_count == expected_count
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="synthetic-valuation-missing-" + fault,
        model_version_id=model_id,
        system_as_of=datetime.now(UTC),
        release_event_id="synthetic:valuation",
        metric_ids=("CN_INDEX_VALUATION",),
        period="2026-08-28",
    )
    selection = select_retrieval_input(paths, run)
    assert not selection.complete and len(selection.selected_claim_ids) == expected_count
    assert len(selection.missing_members) == 9 - expected_count
    assert all("000852.SH" in member for member in selection.missing_members)
    if fault != "empty_index":
        assert "price_earnings" in selection.missing_members[0]
    points = EvidenceRepository(paths.database).metric_series(
        "CN_INDEX_VALUATION", mode=AsOfMode.PUBLIC, as_of=public_at, definition_version=version
    )
    assert not any(
        p.dimensions == {"index": "000852.SH", "measure": "price_earnings"} for p in points
    )
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    for receipt in acquisitions.history():
        assert (
            acquisitions.read_content(receipt.acquisition_id, "raw")
            == originals[receipt.parameters["ts_code"]]
        )


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("publication", ["known", "unknown", "future"])
def test_registered_valuation_respects_publication_cutoff(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], publication: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    version = ModelRepository(paths.database).manifest(model_id)["metric_catalog_version"]
    cutoff = datetime(2026, 8, 28, 8, tzinfo=UTC)
    public_at = (
        None
        if publication == "unknown"
        else cutoff
        if publication == "known"
        else datetime(2026, 8, 28, 9, tzinfo=UTC)
    )

    def transport(payload: dict[str, Any]) -> bytes:
        return encode(
            {
                "code": 0,
                "data": {
                    "fields": ["ts_code", "trade_date", "pe", "pb", "turnover_rate"],
                    "items": [[payload["params"]["ts_code"], "20260828", 12.0, 1.2, 0.5]],
                },
            }
        )

    adapter = TushareContextAdapter("synthetic-token", transport=transport)
    # Synthetic metadata verifies software boundaries, never historical source certification.
    adapter.acquire_scalars(
        paths,
        lambda: tuple(
            replace(s, release_at=public_at, public_available_at=public_at)
            for s in adapter.index_valuation(
                start_date=date(2026, 8, 28), end_date=date(2026, 8, 28)
            )
        ),
        definition_version=version,
    )
    evidence = EvidenceRepository(paths.database)
    assert len(
        evidence.metric_series(
            "CN_INDEX_VALUATION", mode=AsOfMode.PUBLIC, as_of=cutoff, definition_version=version
        )
    ) == (9 if publication == "known" else 0)
    assert (
        len(
            evidence.metric_series(
                "CN_INDEX_VALUATION",
                mode=AsOfMode.SYSTEM,
                as_of=datetime.now(UTC),
                definition_version=version,
            )
        )
        == 9
    )
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="synthetic-valuation-publication-" + publication,
        model_version_id=model_id,
        system_as_of=cutoff,
        release_event_id="synthetic:valuation",
        metric_ids=("CN_INDEX_VALUATION",),
        period="2026-08-28",
    )
    selection = select_retrieval_input(paths, run, mode=AsOfMode.PUBLIC)
    assert selection.complete is (publication == "known")
    assert len(selection.selected_claim_ids) == (9 if publication == "known" else 0)
