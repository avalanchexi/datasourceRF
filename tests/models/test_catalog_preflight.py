"""Catalog diagnostics via the public CLI; no complete lifecycle materials."""

import json
from pathlib import Path

import pytest

from pring_cycle.catalog_registry import registered_definitions
from pring_cycle.cli import main
from pring_cycle.models import ModelRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from tests.models.test_candidate_admission import save
from tests.models.test_cny030_optional_migration import optional_request, submit


@pytest.fixture
def catalog_runtime(tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch):
    from datetime import UTC, datetime

    from tests.conftest import _clock_datetime

    clock = _clock_datetime(lambda: datetime(2026, 9, 24, 9, tzinfo=UTC))
    monkeypatch.setattr("pring_cycle.acquisition.datetime", clock)
    monkeypatch.setattr("pring_cycle.material_preflight.datetime", clock)
    paths = RuntimePaths.discover(tmp_path)
    initialize_runtime(paths)
    # Reviewed synthetic contracts through admission; no activation or input histories.
    submit(paths, save(paths, optional_request(paths)))
    model = json.loads(capsys.readouterr().out)["model_version_id"]
    return paths, model


def inspect_catalog(paths, model, capsys, *extra):
    main(
        [
            "model-input-preflight",
            "--runtime-root",
            str(paths.override_root),
            "--model",
            model,
            "--start",
            "2026-04-01",
            "--end",
            "2026-09-22",
            "--json",
            *extra,
        ]
    )
    return json.loads(capsys.readouterr().out)


def test_preflight_lists_every_registered_metric_even_when_no_material_exists(
    catalog_runtime, capsys
):
    paths, model = catalog_runtime
    version = ModelRepository(paths.database).manifest(model)["metric_catalog_version"]
    definitions = registered_definitions(paths.database, version)

    result = inspect_catalog(paths, model, capsys)

    entries = {item["metric_id"]: item for item in result["catalog_checks"]}
    assert len(entries) == len(result["catalog_checks"]) == len(definitions)
    assert set(entries) == {item["metric_id"] for item in definitions}
    for definition in definitions:
        entry = entries[definition["metric_id"]]
        assert entry["priority"] == definition["priority"]
        assert entry["role"] == definition["role"]
        assert entry["certification_status"] == definition["certification_status"]
        assert entry["selection"]["status"] != "executed"
    assert entries["CN_BOND_FULL_PRICE_CNY030"]["required"] is False
    assert entries["CN_MARGIN_BALANCE_SSE_SZSE"]["required"] is True
    assert entries["CN_RELEASE_SCHEDULE"]["selection"]["status"] == "pending"
    assert entries["CN_INDEX_VALUATION"]["selection"] == {
        "status": "blocked",
        "reason": "source_material_missing",
    }
    assert result["checks_complete"] is False
    assert {"point_in_time", "parents", "originals", "dimensions"} <= set(result["pending_checks"])
    main(
        [
            "model-input-preflight-read",
            "--runtime-root",
            str(paths.override_root),
            "--receipt-hash",
            result["receipt_hash"],
            "--json",
        ]
    )
    assert json.loads(capsys.readouterr().out) == result


def capture_shibor(paths, model, *, missing_tenor=False, published=None, value=1.5):
    from dataclasses import replace
    from datetime import UTC, date, datetime

    from pring_cycle.tushare_context import TushareContextAdapter

    responses = {
        "repo_daily": {"fields": ["ts_code", "trade_date", "repo_maturity", "weight"], "items": []},
        "shibor": {
            "fields": ["date", "on", "1w", "3m"],
            "items": [["20260922", value, None if missing_tenor else 1.7, 1.8]],
        },
    }
    adapter = TushareContextAdapter(
        "synthetic-token",
        transport=lambda payload: json.dumps(
            {"code": 0, "data": responses[payload["api_name"]]}
        ).encode(),
    )
    published = published or datetime(2026, 9, 22, 3, tzinfo=UTC)
    # Synthetic explicit publication metadata allowed by the interbank contract;
    # no real historical publication or source certification is asserted.
    result = adapter.acquire_scalars(
        paths,
        lambda: tuple(
            replace(s, release_at=published, public_available_at=published)
            for s in adapter.transmission(start_date=date(2026, 9, 22), end_date=date(2026, 9, 22))
        ),
        definition_version=ModelRepository(paths.database).manifest(model)[
            "metric_catalog_version"
        ],
    )
    return result


def test_preflight_records_only_checks_that_ran_for_shibor(catalog_runtime, capsys):
    paths, model = catalog_runtime
    capture_shibor(paths, model)

    result = inspect_catalog(paths, model, capsys)

    entry = next(
        item for item in result["catalog_checks"] if item["metric_id"] == "CN_SHIBOR_ON_1W_3M"
    )
    assert entry["selection"]["status"] == "executed"
    assert entry["selection"]["complete"] is True
    assert entry["checks"] == [
        {
            "business_date": "2026-09-22",
            "period": "2026-09-22",
            "originals": "executed",
            "dimensions": "executed",
            "invalid_original_claim_ids": [],
        }
    ]
    gaps = [
        g
        for g in result["gaps"]
        if g["metric_id"] == "CN_SHIBOR_ON_1W_3M" and g["reason"] == "input_selection_missing"
    ]
    assert gaps == []
    assert result["checks_complete"] is False


def test_shibor_missing_tenor_is_rejected_before_claims_reach_preflight(catalog_runtime, capsys):
    from pring_cycle.evidence import EvidenceRepository

    paths, model = catalog_runtime
    with pytest.raises(ValueError, match="^tushare_context_value_missing$"):
        capture_shibor(paths, model, missing_tenor=True)
    version = ModelRepository(paths.database).manifest(model)["metric_catalog_version"]
    assert (
        EvidenceRepository(paths.database).source_claim_vintages(
            "CN_SHIBOR_ON_1W_3M", definition_version=version
        )
        == ()
    )
    result = inspect_catalog(paths, model, capsys)
    assert {"metric_id": "CN_SHIBOR_ON_1W_3M", "reason": "source_material_missing"} in result[
        "gaps"
    ]


@pytest.mark.parametrize("artifact_kind", ["raw", "normalized"])
@pytest.mark.parametrize("future_revision", [False, True])
def test_preflight_rechecks_shibor_damage_between_calls_without_poisoning_past(
    catalog_runtime, capsys, artifact_kind, future_revision
):
    from datetime import UTC, datetime

    from pring_cycle.acquisition import AcquisitionRepository

    paths, model = catalog_runtime
    capture_shibor(paths, model)
    before = inspect_catalog(paths, model, capsys)
    initial = next(
        item for item in before["catalog_checks"] if item["metric_id"] == "CN_SHIBOR_ON_1W_3M"
    )
    assert initial["selection"]["complete"] is True
    if future_revision:
        capture_shibor(paths, model, published=datetime(2026, 9, 23, 3, tzinfo=UTC), value=2.5)
    receipt = [
        r
        for r in AcquisitionRepository(paths.database, paths.artifacts).history()
        if r.api_name == "shibor"
    ][-1]
    digest = getattr(receipt, artifact_kind + "_hash")
    (paths.artifacts / digest[:2] / digest).write_bytes(b"damaged selected original")

    after = inspect_catalog(paths, model, capsys)
    selected = next(
        item for item in after["catalog_checks"] if item["metric_id"] == "CN_SHIBOR_ON_1W_3M"
    )
    assert selected["selection"]["complete"] is future_revision
    if future_revision:
        assert selected["checks"] == initial["checks"]
        later = inspect_catalog(
            paths,
            model,
            capsys,
            "--start",
            "2026-09-23",
            "--end",
            "2026-09-23",
            "--expected-trading-days",
            "1",
        )
        selected = next(
            item for item in later["catalog_checks"] if item["metric_id"] == "CN_SHIBOR_ON_1W_3M"
        )
        assert selected["selection"]["complete"] is False
    assert selected["checks"][0]["originals"] == "executed"
    assert selected["checks"][0]["dimensions"] == "executed"
    assert selected["checks"][0]["invalid_original_claim_ids"]
    main(
        [
            "model-input-preflight-read",
            "--runtime-root",
            str(paths.override_root),
            "--receipt-hash",
            before["receipt_hash"],
            "--json",
        ]
    )
    assert json.loads(capsys.readouterr().out) == before


def test_preflight_exposes_unavailable_dimension_contract_without_inventing_claims(
    catalog_runtime, capsys
):
    paths, model = catalog_runtime
    result = inspect_catalog(paths, model, capsys)
    assert {
        "metric_id": "CN_USDCNY_CENTRAL_PARITY",
        "reason": "dimension_contract_unavailable",
    } in result["optional_gaps"]
    entry = next(
        item for item in result["catalog_checks"] if item["metric_id"] == "CN_USDCNY_CENTRAL_PARITY"
    )
    assert entry["selection"] == {"status": "blocked", "reason": "dimension_contract_unavailable"}
    assert entry["checks"] == []


def capture_rrr(paths, model):
    from datetime import UTC, datetime

    from pring_cycle.official_context import ingest_official_context_document

    raw = (
        "<html><body><h1>2026年9月准备金公告</h1>"
        "<p>发布时间：2026-09-22 10:00:00</p><table>"
        "<tr><th>生效日期</th><th>调整（百分点）</th><th>机构范围</th>"
        "<th>调整后准备金率（%）</th><th>释放资金（亿元）</th></tr>"
        "<tr><td>2026-09-22</td><td>-0.25</td><td>all</td>"
        "<td>1.75</td><td>500</td></tr></table></body></html>"
    ).encode()
    now = datetime(2026, 9, 24, 9, tzinfo=UTC)
    return ingest_official_context_document(
        paths,
        raw,
        family="pbc_rrr_notice",
        source_url="https://www.pbc.gov.cn/synthetic-rrr",
        expected_period="2026-09",
        fetched_at=now,
        clock=lambda: now,
        definition_version=ModelRepository(paths.database).manifest(model)[
            "metric_catalog_version"
        ],
    )


def test_preflight_records_the_separate_rrr_publication_checks(catalog_runtime, capsys):
    paths, model = catalog_runtime
    capture_rrr(paths, model)
    result = inspect_catalog(paths, model, capsys)
    entry = next(item for item in result["catalog_checks"] if item["metric_id"] == "CN_RRR_EVENT")
    assert entry["selection"]["complete"] is True
    assert entry["checks"] == [
        {
            "business_date": "2026-09-22",
            "period": "2026-09-22",
            "originals": "executed",
            "dimensions": "executed",
            "invalid_original_claim_ids": [],
        }
    ]


def capture_warrants(paths, model, *, omit_symbol=None):
    from dataclasses import replace
    from datetime import UTC, date, datetime

    from pring_cycle.tushare_context import TushareContextAdapter

    symbols = ("CF", "CU", "PP", "RB", "RU", "SC", "SP", "TA")

    def transport(payload):
        symbol = payload["params"]["symbol"]
        unit = "桶" if symbol == "SC" else "张" if symbol in {"CF", "PTA"} else "吨"
        exchange = "CZCE" if symbol in {"CF", "PTA"} else "DCE" if symbol == "PP" else "SHFE"
        return json.dumps(
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
                        ["20260922", symbol, "synthetic-warehouse", None, 100, None, unit, exchange]
                    ],
                },
            }
        ).encode()

    adapter = TushareContextAdapter("synthetic-token", transport=transport)
    public_at = datetime(2026, 9, 22, 9, tzinfo=UTC)
    return adapter.acquire_scalars(
        paths,
        lambda: tuple(
            replace(s, release_at=public_at, public_available_at=public_at)
            for symbol in symbols
            if symbol != omit_symbol
            for s in adapter.futures_warrants(
                start_date=date(2026, 9, 22), end_date=date(2026, 9, 22), symbol=symbol
            )
        ),
        definition_version=ModelRepository(paths.database).manifest(model)[
            "metric_catalog_version"
        ],
    )


def test_preflight_records_warrant_checks_and_names_a_missing_symbol(catalog_runtime, capsys):
    paths, model = catalog_runtime
    capture_warrants(paths, model, omit_symbol="SP")
    result = inspect_catalog(paths, model, capsys)
    entry = next(
        item for item in result["catalog_checks"] if item["metric_id"] == "CN_FUTURES_WARRANTS"
    )
    assert entry["selection"]["complete"] is False
    assert entry["checks"] == [
        {
            "business_date": "2026-09-22",
            "period": "2026-09-22",
            "originals": "executed",
            "dimensions": "executed",
            "invalid_original_claim_ids": [],
        }
    ]
    gaps = [
        g
        for g in result["gaps"]
        if g["metric_id"] == "CN_FUTURES_WARRANTS" and g["reason"] == "input_selection_missing"
    ]
    assert len(gaps) == 1
    assert gaps[0]["missing_members"] == "CN_FUTURES_WARRANTS:symbol_missing:SP"


@pytest.mark.parametrize(
    "family,metric,missing_member",
    [
        ("pmi", "CN_PMI_ACTIVITY", 'CN_PMI_ACTIVITY:{"measure": "level", "series": "production"}'),
        ("sf_total", "CN_SF_TOTAL", 'CN_SF_TOTAL:{"measure": "ytd_increment"}'),
    ],
)
def test_partial_monthly_delivery_has_exact_system_gap_and_no_invented_public_time(
    catalog_runtime, capsys, monkeypatch, family, metric, missing_member
):
    from datetime import UTC, datetime

    from pring_cycle.evidence import AsOfMode
    from pring_cycle.runs import RunRepository
    from pring_cycle.search_evidence import select_retrieval_input
    from pring_cycle.tushare_context import TushareContextAdapter
    from tests.models.test_cny030_optional_migration import rebind

    paths, _ = catalog_runtime
    request = optional_request(paths)
    manifest = request["manifest"]
    manifest["metric_catalog_version"] += "-dual-" + family
    manifest["point_in_time_rule_version"] = "dual-cutoff-v0003"
    from tests.conftest import _clock_datetime

    monkeypatch.setattr(
        "pring_cycle.acquisition.datetime",
        _clock_datetime(lambda: datetime(2026, 9, 22, 9, tzinfo=UTC)),
    )
    for definition in manifest["metric_definitions"]:
        definition["definition_version"] = manifest["metric_catalog_version"]
        if (family == "pmi" and definition["metric_id"].startswith("CN_PMI_")) or definition[
            "metric_id"
        ] == metric:
            definition["source_codes"] = [
                *definition["source_codes"],
                "tushare:cn_pmi:official-sampled-v0001"
                if family == "pmi"
                else "tushare:sf_month:official-sampled-v0001",
            ]
    rebind(paths, request)
    submit(paths, save(paths, request))
    model = json.loads(capsys.readouterr().out)["model_version_id"]
    rows = {
        "pmi": {
            "fields": [
                "month",
                "pmi010000",
                "pmi010400",
                "pmi010500",
                "pmi010700",
                "pmi011100",
                "pmi011200",
                "pmi011300",
                "pmi011400",
            ],
            "items": [["202608", 49.2, None, 48.5, 48.3, 49.4, 53.2, 47.8, 48.6]],
        },
        "sf_total": {
            "fields": ["month", "inc_cumval", "stk_endval"],
            "items": [["202608", None, 420.0]],
        },
    }
    adapter = TushareContextAdapter(
        "synthetic-token",
        transport=lambda _: json.dumps({"code": 0, "data": rows[family]}).encode(),
    )
    collect = adapter.pmi if family == "pmi" else adapter.social_financing_total
    adapter.acquire_scalars(
        paths,
        lambda: collect(start_month="202608", end_month="202608"),
        definition_version=manifest["metric_catalog_version"],
    )
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-09-22",
        client_request_id="partial-" + family,
        model_version_id=model,
        system_as_of=datetime(2026, 9, 24, 10, tzinfo=UTC),
        release_event_id="synthetic:partial:" + family,
        metric_ids=(metric,),
        period="2026-08",
    )
    selection = select_retrieval_input(paths, run, mode=AsOfMode.SYSTEM)
    assert selection.complete is False
    assert selection.missing_members == (missing_member,)
    assert selection.selected_claim_ids
    assert select_retrieval_input(paths, run, mode=AsOfMode.PUBLIC).selected_claim_ids == ()
    # The same persisted claims cannot make a historical PUBLIC preflight executed-originals.
    preflight = inspect_catalog(paths, model, capsys)
    entry = next(item for item in preflight["catalog_checks"] if item["metric_id"] == metric)
    assert entry["checks"][0]["originals"] == "blocked"
    assert entry["checks"][0]["dimensions"] == "executed"


@pytest.mark.parametrize(
    "family,metric", [("rrr", "CN_RRR_EVENT"), ("warrants", "CN_FUTURES_WARRANTS")]
)
@pytest.mark.parametrize("artifact_kind", ["raw", "normalized"])
def test_preflight_special_family_checks_reject_damage_after_success(
    catalog_runtime, capsys, family, metric, artifact_kind
):
    from pring_cycle.acquisition import AcquisitionRepository

    paths, model = catalog_runtime
    (capture_rrr if family == "rrr" else capture_warrants)(paths, model)
    before = inspect_catalog(paths, model, capsys)
    entry = next(item for item in before["catalog_checks"] if item["metric_id"] == metric)
    assert entry["selection"]["complete"] is True
    receipts = AcquisitionRepository(paths.database, paths.artifacts).history()
    receipt = (
        receipts[0]
        if family == "rrr"
        else next(r for r in receipts if r.parameters.get("symbol") == "CU")
    )
    digest = getattr(receipt, artifact_kind + "_hash")
    (paths.artifacts / digest[:2] / digest).write_bytes(b"corrupted after first inspection")
    after = inspect_catalog(paths, model, capsys)
    entry = next(item for item in after["catalog_checks"] if item["metric_id"] == metric)
    assert entry["selection"]["complete"] is False
    assert entry["checks"][0]["originals"] == "executed"
    assert entry["checks"][0]["dimensions"] == ("blocked" if family == "rrr" else "executed")
    gaps = [
        g
        for g in after["gaps"]
        if g["metric_id"] == metric and g["reason"] == "input_selection_missing"
    ]
    assert len(gaps) == 1
    assert ("publication_contract_unavailable" if family == "rrr" else "symbol_missing:CU") in gaps[
        0
    ]["missing_members"]


def test_missing_lpr_tenor_is_rejected_at_public_document_ingestion(catalog_runtime, capsys):
    from datetime import UTC, datetime

    from pring_cycle.evidence import EvidenceRepository
    from pring_cycle.official_lpr import ingest_lpr_document

    paths, model = catalog_runtime
    version = ModelRepository(paths.database).manifest(model)["metric_catalog_version"]
    content = (Path(__file__).parents[1] / "fixtures/chinamoney_lpr_20260820.html").read_bytes()
    content = content.replace("，5年期以上LPR为3.5%".encode(), b"")
    at = datetime(2026, 9, 24, 9, tzinfo=UTC)
    with pytest.raises(ValueError, match="^lpr_5y_plus_value_missing$"):
        ingest_lpr_document(
            paths,
            content,
            source_url="https://www.chinamoney.com.cn/chinese/rdgz/20260820/3399885.html",
            fetched_at=at,
            expected_period="2026-08",
            definition_version=version,
            clock=lambda: at,
        )
    assert (
        EvidenceRepository(paths.database).source_claim_vintages(
            "CN_LPR_1Y_5Y", definition_version=version
        )
        == ()
    )
