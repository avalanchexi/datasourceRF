"""Read-only candidate material diagnostics through the public CLI."""

import json
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from pring_cycle.acquisition import AcquisitionRepository
from pring_cycle.cli import main
from pring_cycle.evidence import AsOfMode, EvidenceRepository, EvidenceValueState, SourceClaimInput
from pring_cycle.models import ModelRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.source_adapters import CORE_API_IDENTITIES, TushareCoreAdapter
from pring_cycle.tushare_context import ContextScalar, TushareContextAdapter
from tests.conftest import install_runtime_clock
from tests.models.test_candidate_admission import prepare_credit_component_pair
from tests.models.test_isolated_lifecycle import (
    admit_complete_candidate,
    synthetic_public_scalars,
    trading_days,
)


def test_prepared_core_inputs_include_a_validated_independent_calendar(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from pring_cycle.full_run_requirements import required_calendar
    from pring_cycle.runs import RunRepository
    from pring_cycle.search_evidence import ModelInputSelector
    from tests.models.test_isolated_lifecycle import import_core_histories

    paths = RuntimePaths.discover(tmp_path)
    initialize_runtime(paths)
    candidate = admit_complete_candidate(paths, capsys)
    version = ModelRepository(paths.database).manifest(candidate)["metric_catalog_version"]
    import_core_histories(paths, version, lambda: datetime.now(UTC))
    run = RunRepository(paths.database).submit(
        command_type="manual_full",
        target_business_date="2026-08-28",
        client_request_id="preflight-material-calendar",
        model_version_id=candidate,
        system_as_of=datetime.now(UTC),
    )
    calendar = required_calendar(paths, run, ModelInputSelector(paths, run))
    assert calendar["status"] == "available"
    assert len(calendar["dates"]) == 120
    assert calendar["dates"][0] == "2026-03-09"
    assert calendar["dates"][-1] == "2026-08-28"
    assert calendar["provenance"]["acquisition_id"] is not None


@pytest.mark.parametrize("fault", [None, "missing", "late_public", "shared_history_hole"])
def test_preflight_checks_core_history_before_the_requested_window(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], fault: str | None
) -> None:
    paths = RuntimePaths.discover(tmp_path)
    initialize_runtime(paths)
    candidate = admit_complete_candidate(paths, capsys)
    version = ModelRepository(paths.database).manifest(candidate)["metric_catalog_version"]
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    evidence = EvidenceRepository(paths.database)
    bad_metric = "CN_BOND_CORE_000012"
    if fault == "shared_history_hole":
        calendar_days = trading_days()[-122:]
        calendar_raw = json.dumps(
            {
                "code": 0,
                "data": {
                    "fields": ["cal_date", "is_open"],
                    "items": [[day.strftime("%Y%m%d"), 1] for day in calendar_days],
                },
            }
        ).encode()
        TushareCoreAdapter("synthetic-token", transport=lambda _: calendar_raw).acquire_calendar(
            acquisitions, calendar_days[0], calendar_days[-1]
        )
    for metric, (api, code) in CORE_API_IDENTITIES.items():
        days = (date(2026, 8, 27), date(2026, 8, 28))
        if fault == "shared_history_hole":
            days = (date(2026, 3, 5), date(2026, 8, 28))
        if fault == "missing" and metric == bad_metric:
            days = days[1:]
        raw = json.dumps(
            {
                "code": 0,
                "data": {
                    "fields": ["ts_code", "trade_date", "close", "pre_close", "pct_chg"],
                    "items": [[code, day.strftime("%Y%m%d"), 100.0, 100.0, 0.0] for day in days],
                },
            }
        ).encode()
        receipt = (
            TushareCoreAdapter("synthetic-token", transport=lambda _, body=raw: body)
            .acquire_core_bars(
                acquisitions, metric, start=days[0], end=days[-1], expected_business_dates=days
            )
            .receipt
        )
        assert receipt.received_at is not None
        assert receipt.validated_at is not None
        claims = []
        for day in days:
            published = datetime(day.year, day.month, day.day, 8, tzinfo=UTC)
            if fault == "late_public" and metric == bad_metric and day.day == 27:
                published += timedelta(days=1)
            claims.append(
                SourceClaimInput(
                    metric_id=metric,
                    definition_version=version,
                    period_kind="business_day",
                    period_start=day.isoformat(),
                    period_end=day.isoformat(),
                    dimensions={},
                    value=100.0,
                    value_state=EvidenceValueState.REPORTED_VALUE,
                    unit="index_points",
                    provider="tushare",
                    source_reference=f"tushare:{api}:{code}:{day.isoformat()}",
                    release_event_id=f"synthetic:preflight-core:{metric}:{day}",
                    release_at=published,
                    public_available_at=published,
                    fetched_at=receipt.received_at,
                    available_at=receipt.validated_at,
                    certification_status="certified",
                    quality_status="validated",
                    acquisition_id=receipt.acquisition_id,
                )
            )
        evidence.append_source_claims(tuple(claims))
    main(
        [
            "model-input-preflight",
            "--runtime-root",
            str(tmp_path),
            "--model",
            candidate,
            "--start",
            "2026-08-28",
            "--end",
            "2026-08-28",
            "--json",
        ]
    )
    result = json.loads(capsys.readouterr().out)
    gaps = [gap for gap in result["gaps"] if gap["reason"] == "core_history_input_missing"]
    if fault == "shared_history_hole":
        assert result["calendar"]["status"] == "available"
        assert {gap["metric_id"] for gap in gaps if gap["period"] == "2026-03-06"} == set(
            CORE_API_IDENTITIES
        )
    elif fault is None:
        assert gaps == []
    else:
        assert any(
            gap["metric_id"] == bad_metric
            and gap["period"] == "2026-08-27"
            and gap["business_date"] == "2026-08-27"
            for gap in gaps
        )


@pytest.mark.parametrize("material_start,missing", [("2026-08-18", False), ("2026-08-28", True)])
def test_preflight_reports_missing_formula_input_warmup(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    material_start: str,
    missing: bool,
) -> None:
    paths = RuntimePaths.discover(tmp_path)
    initialize_runtime(paths)
    candidate = admit_complete_candidate(paths, capsys)
    version = ModelRepository(paths.database).manifest(candidate)["metric_catalog_version"]
    days = [day for day in trading_days() if material_start <= day.isoformat() <= "2026-08-28"]
    rows = {
        "repo_daily": {
            "fields": ["ts_code", "trade_date", "repo_maturity", "weight"],
            "items": [["DR007.IB", day.strftime("%Y%m%d"), "DR007", 1.4] for day in days],
        },
        "shibor": {
            "fields": ["date", "on", "1w", "3m"],
            "items": [[day.strftime("%Y%m%d"), 1.3, 1.38, 1.43] for day in days],
        },
    }
    adapter = TushareContextAdapter(
        "synthetic-token",
        transport=lambda payload: json.dumps(
            {"code": 0, "data": rows[payload["api_name"]]}
        ).encode(),
    )
    adapter.acquire_scalars(
        paths,
        lambda: synthetic_public_scalars(
            adapter.transmission(start_date=days[0], end_date=days[-1])
        ),
        definition_version=version,
    )
    main(
        [
            "model-input-preflight",
            "--runtime-root",
            str(tmp_path),
            "--model",
            candidate,
            "--start",
            "2026-08-28",
            "--end",
            "2026-08-28",
            "--json",
        ]
    )
    result = json.loads(capsys.readouterr().out)
    gaps = [
        gap
        for gap in result["gaps"]
        if gap["metric_id"] == "CN_DR007" and gap["reason"] == "input_warmup_missing"
    ]
    assert bool(gaps) is missing
    if missing:
        assert gaps[0]["required_start"] == "2026-08-18"


def test_preflight_lists_missing_material_without_changing_candidate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path)
    initialize_runtime(paths)
    candidate = admit_complete_candidate(paths, capsys)
    models = ModelRepository(paths.database)
    versions = models.list_versions()
    activations = models.activation_history()

    main(
        [
            "model-input-preflight",
            "--runtime-root",
            str(tmp_path),
            "--model",
            candidate,
            "--start",
            "2026-03-09",
            "--end",
            "2026-08-28",
            "--json",
        ]
    )
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "blocked"
    assert result["model_version_id"] == candidate
    assert result["manifest_hash"] == models.get(candidate).manifest_hash
    missing = {gap["metric_id"] for gap in result["gaps"]}
    assert {"CN_TRADE_CALENDAR", "CN_MARGIN_BALANCE", "CN_INDEX_VALUATION"} <= missing
    assert models.list_versions() == versions
    assert models.activation_history() == activations


@pytest.mark.parametrize(
    "damage_original,publication",
    [
        (False, "known"),
        (True, "known"),
        (False, "unknown"),
        (False, "future"),
        (False, "damage_after_read"),
    ],
)
def test_preflight_rechecks_originals_of_existing_claims(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], damage_original: bool, publication: str
) -> None:
    paths = RuntimePaths.discover(tmp_path)
    initialize_runtime(paths)
    candidate = admit_complete_candidate(paths, capsys)
    version = ModelRepository(paths.database).manifest(candidate)["metric_catalog_version"]
    raw = json.dumps(
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
    ).encode()
    adapter = TushareContextAdapter("synthetic-token", transport=lambda _: raw)

    def retrieve() -> tuple[ContextScalar, ...]:
        values = adapter.margin_financing(start_date=date(2026, 8, 28), end_date=date(2026, 8, 28))
        if publication == "unknown":
            return values
        if publication == "future":
            future = datetime(2026, 8, 29, 8, tzinfo=UTC)
            return tuple(
                replace(value, public_available_at=future, release_at=future) for value in values
            )
        return synthetic_public_scalars(values)

    adapter.acquire_scalars(paths, retrieve, definition_version=version)
    receipt = AcquisitionRepository(paths.database, paths.artifacts).history()[0]
    assert receipt.raw_hash is not None
    if damage_original:
        (paths.artifacts / receipt.raw_hash[:2] / receipt.raw_hash).write_bytes(b"damaged original")
    arguments = [
        "model-input-preflight",
        "--runtime-root",
        str(tmp_path),
        "--model",
        candidate,
        "--start",
        "2026-08-28",
        "--end",
        "2026-08-28",
        "--json",
    ]
    main(arguments)
    result = json.loads(capsys.readouterr().out)
    margin_gaps = [gap for gap in result["gaps"] if gap["metric_id"] == "CN_MARGIN_BALANCE"]
    if damage_original or publication in {"unknown", "future"}:
        assert any(gap["reason"] == "input_selection_missing" for gap in margin_gaps)
    else:
        assert margin_gaps == []

    if publication == "damage_after_read":
        (paths.artifacts / receipt.raw_hash[:2] / receipt.raw_hash).write_bytes(
            b"damaged after read"
        )
        main(arguments)
        second = json.loads(capsys.readouterr().out)
        assert any(
            gap["metric_id"] == "CN_MARGIN_BALANCE" and gap["reason"] == "input_selection_missing"
            for gap in second["gaps"]
        )


@pytest.mark.parametrize(
    "window_size,missing_count,blocked",
    [(3, 0, False), (3, 1, True), (20, 1, False), (20, 2, True)],
)
def test_preflight_checks_each_calendar_day_not_only_the_last(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
    window_size: int,
    missing_count: int,
    blocked: bool,
) -> None:
    paths = RuntimePaths.discover(tmp_path)
    initialize_runtime(paths)
    candidate = admit_complete_candidate(paths, capsys)
    version = ModelRepository(paths.database).manifest(candidate)["metric_catalog_version"]
    now = install_runtime_clock(monkeypatch, request, datetime(2026, 8, 28, 10, tzinfo=UTC))
    days = trading_days()
    window = days[-window_size:]
    omitted = set(window[1 : 1 + missing_count])
    calendar_raw = json.dumps(
        {
            "code": 0,
            "data": {
                "fields": ["cal_date", "is_open"],
                "items": [[day.strftime("%Y%m%d"), 1] for day in days],
            },
        }
    ).encode()
    TushareCoreAdapter(
        "synthetic-token", transport=lambda _: calendar_raw, clock=now
    ).acquire_calendar(AcquisitionRepository(paths.database, paths.artifacts), days[0], days[-1])
    raw = json.dumps(
        {
            "code": 0,
            "data": {
                "fields": ["trade_date", "exchange_id", "rzye", "rzmre"],
                "items": [
                    [day.strftime("%Y%m%d"), exchange, 100_000_000, 10_000_000]
                    for day in window
                    if day not in omitted
                    for exchange in ("SSE", "SZSE", "BSE")
                ],
            },
        }
    ).encode()
    adapter = TushareContextAdapter("synthetic-token", transport=lambda _: raw)
    adapter.acquire_scalars(
        paths,
        lambda: synthetic_public_scalars(
            adapter.margin_financing(start_date=window[0], end_date=window[-1])
        ),
        definition_version=version,
    )
    main(
        [
            "model-input-preflight",
            "--runtime-root",
            str(tmp_path),
            "--model",
            candidate,
            "--start",
            window[0].isoformat(),
            "--end",
            "2026-08-28",
            "--json",
        ]
    )
    result = json.loads(capsys.readouterr().out)
    assert result["calendar"]["status"] == "available"
    gaps = [gap for gap in result["gaps"] if gap["metric_id"] == "CN_MARGIN_BALANCE"]
    if blocked:
        assert any(gap.get("business_date") == window[1].isoformat() for gap in gaps)
    else:
        assert gaps == []


@pytest.mark.parametrize("fault", [None, "raw", "normalized", "range", "late_capture"])
def test_preflight_validates_calendar_artifacts_and_requested_range(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
    fault: str | None,
) -> None:
    paths = RuntimePaths.discover(tmp_path)
    initialize_runtime(paths)
    candidate = admit_complete_candidate(paths, capsys)
    now = install_runtime_clock(
        monkeypatch,
        request,
        datetime(2026, 8, 29 if fault == "late_capture" else 28, 10, tzinfo=UTC),
    )
    days = trading_days()[-120:]
    raw = json.dumps(
        {
            "code": 0,
            "data": {
                "fields": ["cal_date", "is_open"],
                "items": [[day.strftime("%Y%m%d"), 1] for day in days],
            },
        }
    ).encode()
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    TushareCoreAdapter("synthetic-token", transport=lambda _: raw, clock=now).acquire_calendar(
        acquisitions, days[0], days[-1]
    )
    receipt = acquisitions.history()[0]
    if fault in {"raw", "normalized"}:
        digest = receipt.raw_hash if fault == "raw" else receipt.normalized_hash
        assert digest is not None
        (paths.artifacts / digest[:2] / digest).write_bytes(b"damaged calendar")
    start = days[0] - timedelta(days=1) if fault == "range" else days[0]
    main(
        [
            "model-input-preflight",
            "--runtime-root",
            str(tmp_path),
            "--model",
            candidate,
            "--start",
            start.isoformat(),
            "--end",
            days[-1].isoformat(),
            "--json",
        ]
    )
    result = json.loads(capsys.readouterr().out)
    calendar_gaps = [gap for gap in result["gaps"] if gap["metric_id"] == "CN_TRADE_CALENDAR"]
    if fault in {None, "late_capture"}:
        assert calendar_gaps == []
    else:
        assert calendar_gaps
        assert result["calendar"]["status"] == "unavailable"


def test_preflight_rejects_missing_credit_difference_baseline(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path)
    initialize_runtime(paths)
    manifests, _ = prepare_credit_component_pair(
        paths, capsys, missing_candidate_social_baseline=True
    )
    for side, manifest in manifests.items():
        main(
            [
                "model-input-preflight",
                "--runtime-root",
                str(tmp_path),
                "--model",
                manifest["model_version_id"],
                "--start",
                "2026-08-28",
                "--end",
                "2026-08-28",
                "--json",
            ]
        )
        result = json.loads(capsys.readouterr().out)
        credit_gaps = [
            gap
            for gap in result["gaps"]
            if gap["metric_id"] == "CN_CREDIT_IMPULSE"
            and gap["reason"] == "formula_inputs_unavailable"
        ]
        if side == "candidate":
            assert credit_gaps
            assert credit_gaps[0]["business_date"] == "2026-08-28"
            assert credit_gaps[0]["formula_version"] == "credit-impulse-ytd-flow-v0002"
            assert credit_gaps[0]["missing_input_periods"] == {"CN_SF_TOTAL": ["2026-06"]}
        else:
            assert credit_gaps == []


@pytest.mark.parametrize("target", ["2026-08-28", "2026-08-31"])
def test_preflight_isolates_a_future_damaged_revision(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], target: str
) -> None:
    paths = RuntimePaths.discover(tmp_path)
    initialize_runtime(paths)
    candidate = admit_complete_candidate(paths, capsys)
    version = ModelRepository(paths.database).manifest(candidate)["metric_catalog_version"]
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    original_hashes = []
    for revised in (False, True):
        raw = json.dumps(
            {
                "code": 0,
                "data": {
                    "fields": ["trade_date", "exchange_id", "rzye", "rzmre"],
                    "items": [
                        ["20260828", exchange, 200_000_000 if revised else 100_000_000, 10_000_000]
                        for exchange in ("SSE", "SZSE", "BSE")
                    ],
                },
            }
        ).encode()
        adapter = TushareContextAdapter("synthetic-token", transport=lambda _, body=raw: body)

        def retrieve(
            source: TushareContextAdapter = adapter, is_revision: bool = revised
        ) -> tuple[ContextScalar, ...]:
            scalars = source.margin_financing(
                start_date=date(2026, 8, 28), end_date=date(2026, 8, 28)
            )
            published = datetime(2026, 8, 29 if is_revision else 28, 8, tzinfo=UTC)
            return tuple(
                replace(s, release_at=published, public_available_at=published) for s in scalars
            )

        adapter.acquire_scalars(paths, retrieve, definition_version=version)
        matching = [
            r
            for r in acquisitions.history()
            if r.raw_hash and acquisitions.read_content(r.acquisition_id, "raw") == raw
        ]
        assert len(matching) == 1
        original_hashes.append(matching[0].raw_hash)
    assert original_hashes[0] != original_hashes[1]
    bad = original_hashes[1]
    assert bad is not None
    (paths.artifacts / bad[:2] / bad).write_bytes(b"damaged future revision")
    main(
        [
            "model-input-preflight",
            "--runtime-root",
            str(tmp_path),
            "--model",
            candidate,
            "--start",
            target,
            "--end",
            target,
            "--json",
        ]
    )
    result = json.loads(capsys.readouterr().out)
    invalid = [
        gap
        for gap in result["gaps"]
        if gap["metric_id"] == "CN_MARGIN_BALANCE" and gap["reason"] == "input_selection_missing"
    ]
    assert bool(invalid) is (target == "2026-08-31")


@pytest.mark.parametrize("evidence_kind", ["unbound", "bound"])
def test_registered_calendar_claims_cannot_bypass_the_receipt_preflight(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], evidence_kind: str
) -> None:
    paths = RuntimePaths.discover(tmp_path)
    initialize_runtime(paths)
    candidate = admit_complete_candidate(paths, capsys)
    version = ModelRepository(paths.database).manifest(candidate)["metric_catalog_version"]
    days = trading_days()[-120:]
    receipt = None
    if evidence_kind != "unbound":
        raw = json.dumps(
            {
                "code": 0,
                "data": {
                    "fields": ["cal_date", "is_open"],
                    "items": [[day.strftime("%Y%m%d"), 1] for day in days],
                },
            }
        ).encode()
        receipt = (
            TushareCoreAdapter("synthetic-token", transport=lambda _: raw)
            .acquire_calendar(
                AcquisitionRepository(paths.database, paths.artifacts), days[0], days[-1]
            )
            .receipt
        )
    now = datetime.now(UTC)
    with pytest.raises(
        ValueError, match="registered_source_contract_not_implemented:CN_TRADE_CALENDAR"
    ):
        EvidenceRepository(paths.database).append_source_claims(
            tuple(
                SourceClaimInput(
                    metric_id="CN_TRADE_CALENDAR",
                    definition_version=version,
                    period_kind="business_day",
                    period_start=day.isoformat(),
                    period_end=day.isoformat(),
                    dimensions={},
                    value=1.0,
                    value_state=EvidenceValueState.REPORTED_VALUE,
                    unit="scalar",
                    provider="tushare",
                    source_reference=f"tushare:trade_cal:SSE:{day}",
                    release_event_id=f"synthetic:calendar:{day}",
                    release_at=None,
                    public_available_at=None,
                    fetched_at=receipt.received_at if receipt is not None else now,
                    available_at=now,
                    certification_status="certified",
                    quality_status="validated",
                    acquisition_id=receipt.acquisition_id if receipt is not None else None,
                )
                for day in days
            )
        )
    main(
        [
            "model-input-preflight",
            "--runtime-root",
            str(tmp_path),
            "--model",
            candidate,
            "--start",
            days[0].isoformat(),
            "--end",
            days[-1].isoformat(),
            "--json",
        ]
    )
    result = json.loads(capsys.readouterr().out)
    calendar_gaps = [gap for gap in result["gaps"] if gap["metric_id"] == "CN_TRADE_CALENDAR"]
    assert bool(calendar_gaps) is (evidence_kind != "bound")


def test_preflight_identifies_a_damaged_historical_formula_parent(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path)
    initialize_runtime(paths)
    manifests, parent_ids = prepare_credit_component_pair(paths, capsys)
    repository = EvidenceRepository(paths.database)
    (historical,) = [
        point
        for point in repository.metric_series(
            "CN_GDP",
            mode=AsOfMode.PUBLIC,
            as_of=datetime(2026, 8, 28, 15, 59, 59, tzinfo=UTC),
            definition_version=manifests["candidate"]["metric_catalog_version"],
        )
        if point.period_end == "2024-09-30"
        and point.dimensions == {"aggregate": "total", "measure": "nominal_ytd_level"}
    ]
    assert historical.selected_claim_id in parent_ids["candidate"]
    assert historical.selected_claim_id is not None
    ((receipt, _),) = repository.source_claim_originals(historical.selected_claim_id)
    assert receipt.raw_hash is not None
    (paths.artifacts / receipt.raw_hash[:2] / receipt.raw_hash).write_bytes(b"damaged old GDP")
    for side, manifest in manifests.items():
        main(
            [
                "model-input-preflight",
                "--runtime-root",
                str(tmp_path),
                "--model",
                manifest["model_version_id"],
                "--start",
                "2026-08-28",
                "--end",
                "2026-08-28",
                "--json",
            ]
        )
        result = json.loads(capsys.readouterr().out)
        credit = [gap for gap in result["gaps"] if gap["metric_id"] == "CN_CREDIT_IMPULSE"]
        if side == "candidate":
            assert credit
            assert {
                "metric_id": "CN_GDP",
                "period": "2024-Q3",
                "claim_id": historical.selected_claim_id,
            } in credit[0]["invalid_parent_claims"]
        else:
            assert credit == []


def test_density_counts_only_values_public_by_their_own_business_date(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
) -> None:
    """Coverage is a point-in-time question: a value published later was not there that day.

    Counting a row because it has *some* publication time lets a window look fully covered
    when every value only became public after the window closed.
    """
    paths = RuntimePaths.discover(tmp_path)
    initialize_runtime(paths)
    candidate = admit_complete_candidate(paths, capsys)
    version = ModelRepository(paths.database).manifest(candidate)["metric_catalog_version"]
    now = install_runtime_clock(monkeypatch, request, datetime(2026, 9, 15, 10, tzinfo=UTC))
    days = trading_days()
    window = days[-20:]
    calendar_raw = json.dumps(
        {
            "code": 0,
            "data": {
                "fields": ["cal_date", "is_open"],
                "items": [[day.strftime("%Y%m%d"), 1] for day in days],
            },
        }
    ).encode()
    TushareCoreAdapter(
        "synthetic-token", transport=lambda _: calendar_raw, clock=now
    ).acquire_calendar(AcquisitionRepository(paths.database, paths.artifacts), days[0], days[-1])
    raw = json.dumps(
        {
            "code": 0,
            "data": {
                "fields": ["trade_date", "exchange_id", "rzye", "rzmre"],
                "items": [
                    [day.strftime("%Y%m%d"), exchange, 100_000_000, 10_000_000]
                    for day in window
                    for exchange in ("SSE", "SZSE", "BSE")
                ],
            },
        }
    ).encode()

    # Every session's value only became public well after the window closed.
    published = datetime(2026, 9, 14, 8, tzinfo=UTC)

    def released_after_the_window(scalars: tuple[ContextScalar, ...]) -> tuple[ContextScalar, ...]:
        return tuple(
            replace(scalar, release_at=published, public_available_at=published)
            for scalar in scalars
        )

    adapter = TushareContextAdapter("synthetic-token", transport=lambda _: raw)
    adapter.acquire_scalars(
        paths,
        lambda: released_after_the_window(
            adapter.margin_financing(start_date=window[0], end_date=window[-1])
        ),
        definition_version=version,
    )
    main(
        [
            "model-input-preflight",
            "--runtime-root",
            str(tmp_path),
            "--model",
            candidate,
            "--start",
            window[0].isoformat(),
            "--end",
            window[-1].isoformat(),
            "--json",
        ]
    )

    result = json.loads(capsys.readouterr().out)
    assert result["calendar"]["status"] == "available"
    coverage = [
        gap
        for gap in result["gaps"]
        if gap["metric_id"] == "CN_MARGIN_BALANCE" and gap["reason"] == "daily_coverage_missing"
    ]
    assert coverage, "a window whose values were all published later is not covered"


def test_operational_evidence_stays_visible_instead_of_vanishing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A P0 the preflight does not score still has to appear, or the catalogue is short.

    Skipping these ids outright makes them indistinguishable from metrics that passed.
    The run planner they mirror keeps a row for each one.
    """
    paths = RuntimePaths.discover(tmp_path)
    initialize_runtime(paths)
    candidate = admit_complete_candidate(paths, capsys)
    manifest = ModelRepository(paths.database).manifest(candidate)
    operational = {
        definition["metric_id"]
        for definition in manifest["metric_definitions"]
        if definition["role"] == "operational_evidence"
        or definition["metric_id"]
        in {"CN_TRADE_CALENDAR", "CN_RELEASE_SCHEDULE", "SOURCE_OBSERVED_AVAILABILITY"}
    }
    assert operational, "the manifest must carry the operational evidence this pins"

    main(
        [
            "model-input-preflight",
            "--runtime-root",
            str(tmp_path),
            "--model",
            candidate,
            "--start",
            "2026-08-28",
            "--end",
            "2026-08-28",
            "--json",
        ]
    )

    result = json.loads(capsys.readouterr().out)
    listed = {entry["metric_id"]: entry for entry in result["operational_evidence"]}
    assert operational <= set(listed)
    assert all(entry["role"] == "operational_evidence" for entry in listed.values())
    # The status must not read as a verdict this command never reached.
    assert listed["CN_TRADE_CALENDAR"]["status"] == "checked_separately"
    assert listed["CN_RELEASE_SCHEDULE"]["status"] == "not_checked"
    assert listed["SOURCE_OBSERVED_AVAILABILITY"]["status"] == "not_checked"


def test_a_source_publishing_the_next_morning_still_counts_as_covered(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
) -> None:
    """Publication lag is normal, and this repository encodes a date as the next midnight.

    `publication_times` turns a date-only publication into 00:00 of the following day,
    so requiring a session's value to be public before that session ended would report
    every legitimate day of such a source as uncovered.
    """
    paths = RuntimePaths.discover(tmp_path)
    initialize_runtime(paths)
    candidate = admit_complete_candidate(paths, capsys)
    version = ModelRepository(paths.database).manifest(candidate)["metric_catalog_version"]
    now = install_runtime_clock(monkeypatch, request, datetime(2026, 8, 28, 10, tzinfo=UTC))
    days = trading_days()
    window = days[-20:]
    calendar_raw = json.dumps(
        {
            "code": 0,
            "data": {
                "fields": ["cal_date", "is_open"],
                "items": [[day.strftime("%Y%m%d"), 1] for day in days],
            },
        }
    ).encode()
    TushareCoreAdapter(
        "synthetic-token", transport=lambda _: calendar_raw, clock=now
    ).acquire_calendar(AcquisitionRepository(paths.database, paths.artifacts), days[0], days[-1])
    raw = json.dumps(
        {
            "code": 0,
            "data": {
                "fields": ["trade_date", "exchange_id", "rzye", "rzmre"],
                "items": [
                    [day.strftime("%Y%m%d"), exchange, 100_000_000, 10_000_000]
                    for day in window
                    for exchange in ("SSE", "SZSE", "BSE")
                ],
            },
        }
    ).encode()

    def published_next_midnight(scalars: tuple[ContextScalar, ...]) -> tuple[ContextScalar, ...]:
        """Exactly what publication_times produces for a date-only publication."""
        from zoneinfo import ZoneInfo

        def public_at(period_end: str) -> datetime:
            session = date.fromisoformat(period_end)
            return datetime.combine(
                session + timedelta(days=1), datetime.min.time(), ZoneInfo("Asia/Shanghai")
            ).astimezone(UTC)

        return tuple(
            replace(scalar, release_at=None, public_available_at=public_at(scalar.period_end))
            for scalar in scalars
        )

    adapter = TushareContextAdapter("synthetic-token", transport=lambda _: raw)
    adapter.acquire_scalars(
        paths,
        lambda: published_next_midnight(
            adapter.margin_financing(start_date=window[0], end_date=window[-1])
        ),
        definition_version=version,
    )
    main(
        [
            "model-input-preflight",
            "--runtime-root",
            str(tmp_path),
            "--model",
            candidate,
            "--start",
            window[0].isoformat(),
            "--end",
            window[-1].isoformat(),
            "--json",
        ]
    )

    result = json.loads(capsys.readouterr().out)
    coverage = [
        gap
        for gap in result["gaps"]
        if gap["metric_id"] == "CN_MARGIN_BALANCE" and gap["reason"] == "daily_coverage_missing"
    ]
    assert coverage == [], "a source that publishes the next morning is still covered"
