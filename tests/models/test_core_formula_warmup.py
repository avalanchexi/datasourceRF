"""Bounded synthetic core inputs through acquisition and the public preflight CLI.

No complete lifecycle/material builder, calibration or external network is used.
"""

import json
from datetime import date, timedelta

import pytest

from pring_cycle.acquisition import AcquisitionRepository
from pring_cycle.source_adapters import TushareCoreAdapter
from tests.models.test_fixed_window_preflight import (
    PLAN,
    preflight,
    read_preflight_receipt,
)
from tests.models.test_fixed_window_preflight import (
    calendar_runtime as calendar_runtime,
)


def calendar_response(days, *, omitted_dates=(), open_subset=False):
    # This synthetic source explicitly reports both open and closed natural dates.
    start, end = date.fromisoformat(days[0]), date.fromisoformat(days[-1])
    natural_dates = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    rows = [
        [day.strftime("%Y%m%d"), int(day.isoformat() in days)]
        for day in natural_dates
        if day.isoformat() not in omitted_dates and (not open_subset or day.isoformat() in days)
    ]
    return json.dumps(
        {
            "code": 0,
            "data": {
                "fields": ["cal_date", "is_open"],
                "items": rows,
            },
        }
    ).encode()


def capture_calendar(paths, days, *, omitted_dates=(), open_subset=False):
    raw = calendar_response(days, omitted_dates=omitted_dates, open_subset=open_subset)
    return TushareCoreAdapter("synthetic-token", transport=lambda _: raw).acquire_calendar(
        AcquisitionRepository(paths.database, paths.artifacts),
        date.fromisoformat(days[0]),
        date.fromisoformat(days[-1]),
    )


def test_preflight_derives_core_formula_consumers_from_frozen_rules(calendar_runtime, capsys):
    paths, candidate = calendar_runtime
    plan = json.loads(PLAN.read_text())
    capture_calendar(paths, plan["default_core_formula_input"]["dates"])
    result = preflight(paths, candidate, capsys)
    requirements = result["core_formula_inputs"]
    assert requirements["required_observations_per_result"] == 140
    assert requirements["input_start"] == "2025-08-29"
    assert requirements["input_end"] == "2026-09-22"
    assert requirements["input_observations"] == 259
    assert requirements["pre_window_observations"] == 139
    assert requirements["lookback_unit"] == "china_trading_sessions"
    assert requirements["rule_version"] == "trend-v0001"
    first, last = requirements["consumers"][0], requirements["consumers"][-1]
    assert first["business_date"] == "2026-04-01"
    assert first["input_dates"][0] == "2025-08-29"
    assert first["input_dates"][-1] == "2026-04-01"
    assert len(first["input_dates"]) == 140
    assert first["public_cutoff"] == "2026-04-01T15:59:59.999999+00:00"
    assert last["business_date"] == "2026-09-22"
    assert len(last["input_dates"]) == 140
    assert requirements["state_initialization"]["status"] == "not_evaluated"
    assert result["checks_complete"] is False
    assert read_preflight_receipt(paths, result["receipt_hash"], capsys) == result


def capture_core(
    paths,
    version,
    metric,
    days,
    *,
    published=None,
    certification="certified",
    quality="validated",
    value=100.0,
):
    from datetime import UTC, datetime
    from zoneinfo import ZoneInfo

    from pring_cycle.evidence import (
        EvidenceRepository,
        EvidenceValueState,
        SourceClaimInput,
        publication_times,
    )
    from pring_cycle.source_adapters import CORE_API_IDENTITIES

    api, code = CORE_API_IDENTITIES[metric]
    raw = json.dumps(
        {
            "code": 0,
            "data": {
                "fields": ["ts_code", "trade_date", "close", "pre_close", "pct_chg"],
                "items": [[code, day.replace("-", ""), value, value, 0.0] for day in days],
            },
        }
    ).encode()
    acquired = TushareCoreAdapter("synthetic-token", transport=lambda _: raw).acquire_core_bars(
        AcquisitionRepository(paths.database, paths.artifacts),
        metric,
        start=date.fromisoformat(days[0]),
        end=date.fromisoformat(days[-1]),
        expected_business_dates=tuple(date.fromisoformat(day) for day in days),
    )
    receipt = acquired.receipt
    claims = []
    for day in days:
        release = (
            datetime.fromisoformat(day).replace(hour=8, tzinfo=UTC)
            if published is None
            else published(day)
        )
        release, public_at = publication_times(release, ZoneInfo("Asia/Shanghai"))
        claims.append(
            SourceClaimInput(
                metric_id=metric,
                definition_version=version,
                period_kind="business_day",
                period_start=day,
                period_end=day,
                dimensions={},
                value=value,
                value_state=EvidenceValueState.REPORTED_VALUE,
                unit="index_points",
                provider="tushare",
                source_reference=f"tushare:{api}:{code}:{day}",
                release_event_id=f"synthetic:core:{metric}:{day}:{release}",
                release_at=release,
                public_available_at=public_at,
                fetched_at=receipt.received_at,
                available_at=receipt.validated_at,
                certification_status=certification,
                quality_status=quality,
                acquisition_id=receipt.acquisition_id,
            )
        )
    stored = EvidenceRepository(paths.database).append_source_claims(tuple(claims))
    return receipt, stored


def admit_core_candidate(paths, capsys, *, certified_from):
    import hashlib

    from tests.models.test_candidate_admission import encode, prepared_request, save, submit

    request, _ = prepared_request(paths)
    package_hash = request["package_hashes"][0]
    package = json.loads((paths.artifacts / package_hash[:2] / package_hash).read_bytes())
    review_hash = package["review_hash"]
    review = json.loads((paths.artifacts / review_hash[:2] / review_hash).read_bytes())
    package["certified_from"] = certified_from
    subject = {
        key: package[key] for key in ("definition_bindings", "manifest_hash", "certified_from")
    }
    review["subject_hash"] = hashlib.sha256(encode(subject)).hexdigest()
    package["review_hash"] = save(paths, review)
    request["package_hashes"] = [save(paths, package)]
    submit(paths, save(paths, request))
    candidate = json.loads(capsys.readouterr().out)["model_version_id"]
    version = request["manifest"]["metric_catalog_version"]
    return candidate, version


def prepare_core_runtime(
    paths,
    capsys,
    *,
    certified_from="2025-08-29",
    calendar_days=None,
    omitted_calendar_dates=(),
    open_subset=False,
):
    from pring_cycle.source_adapters import CORE_API_IDENTITIES

    candidate, version = admit_core_candidate(paths, capsys, certified_from=certified_from)
    days = json.loads(PLAN.read_text())["default_core_formula_input"]["dates"]
    capture_calendar(
        paths, calendar_days or days, omitted_dates=omitted_calendar_dates, open_subset=open_subset
    )
    # Keep a single pre-window point physically separate for integrity counterexamples.
    bad_day = "2025-09-05"
    for metric in CORE_API_IDENTITIES:
        capture_core(
            paths,
            version,
            metric,
            [day for day in days if day != bad_day or metric != "CN_BOND_CORE_000012"],
        )
    return candidate, version, bad_day


def test_preflight_checks_warmup_at_its_formal_consumer_cutoff(calendar_runtime, capsys):
    from datetime import UTC, datetime

    paths, _ = calendar_runtime
    candidate, version, day = prepare_core_runtime(paths, capsys)
    receipt, stored = capture_core(
        paths,
        version,
        "CN_BOND_CORE_000012",
        [day],
        published=lambda _: datetime(2026, 4, 1, 8, tzinfo=UTC),
    )
    result = preflight(paths, candidate, capsys)
    assert not [
        gap
        for gap in result["gaps"]
        if gap["metric_id"] in result["core_formula_inputs"]["metrics"].values()
    ]
    core = result["core_formula_inputs"]
    assert core["status"] == "available"
    assert len(core["consumers"]) == 120
    assert len(core["versions"]) == 777
    assert all(
        len(points) == 140
        for consumer in core["consumers"]
        for points in consumer["inputs"].values()
    )
    assert all(
        version["originals"] and version["certification_packages"]
        for version in core["versions"].values()
    )
    first = core["consumers"][0]
    point = next(p for p in first["inputs"]["CN_BOND_CORE_000012"] if p["period"] == day)
    assert point["claim_id"] == stored[0].claim_id
    lineage = core["versions"][point["claim_id"]]
    assert lineage["public_available_at"] == "2026-04-01T08:00:00+00:00"
    assert point["purpose"] == "formula_warmup"
    assert lineage["originals"] == [
        {
            "acquisition_id": receipt.acquisition_id,
            "raw_hash": receipt.raw_hash,
            "normalized_hash": receipt.normalized_hash,
        }
    ]
    assert core["state_initialization"]["status"] == "not_evaluated"
    assert result["checks_complete"] is False
    assert read_preflight_receipt(paths, result["receipt_hash"], capsys) == result


@pytest.mark.parametrize(
    "fault", ["unknown", "future", "uncertified", "quality", "raw", "normalized", "missing"]
)
def test_one_bad_warmup_blocks_then_qualified_vintage_restores_same_entry(
    calendar_runtime, capsys, fault
):
    from datetime import UTC, datetime

    paths, _ = calendar_runtime
    candidate, version, day = prepare_core_runtime(paths, capsys)
    metric = "CN_BOND_CORE_000012"
    if fault != "missing":
        receipt, rejected_claims = capture_core(
            paths,
            version,
            metric,
            [day],
            published=lambda _: (
                None
                if fault == "unknown"
                else datetime(2026, 4, 2 if fault == "future" else 1, 8, tzinfo=UTC)
            ),
            certification="awaiting_source_certification"
            if fault == "uncertified"
            else "certified",
            quality="invalid" if fault == "quality" else "validated",
        )
        if fault in {"raw", "normalized"}:
            digest = getattr(receipt, f"{fault}_hash")
            (paths.artifacts / digest[:2] / digest).write_bytes(b"damaged synthetic original")
    rejected = preflight(paths, candidate, capsys)
    gaps = [
        gap for gap in rejected["gaps"] if gap["metric_id"] == metric and gap.get("period") == day
    ]
    assert gaps
    expected_cause = {
        "missing": "value_missing",
        "unknown": "public_time_unknown",
        "future": "public_time_after_cutoff",
        "uncertified": "source_uncertified",
        "quality": "quality_invalid",
        "raw": "original_invalid",
        "normalized": "original_invalid",
    }[fault]
    assert gaps[0]["causes"] == [expected_cause]
    if fault != "missing":
        diagnostic = gaps[0]["diagnostic_candidates"][0]
        assert diagnostic["claim_id"] == rejected_claims[0].claim_id
        assert diagnostic["originals"][0]["acquisition_id"] == receipt.acquisition_id
        assert diagnostic["originals"][0]["raw_hash"] == receipt.raw_hash
        if fault in {"unknown", "future"}:
            assert gaps[0]["claim_id"] is None
            if fault == "unknown":
                assert (
                    rejected_claims[0].claim_id not in rejected["core_formula_inputs"]["versions"]
                )
            else:
                # Apr 2 publication is usable by later consumers, never by Apr 1.
                assert any(
                    p["claim_id"] == rejected_claims[0].claim_id
                    for p in rejected["core_formula_inputs"]["consumers"][1]["inputs"][metric]
                )
            assert all(
                p["claim_id"] != rejected_claims[0].claim_id
                for p in rejected["core_formula_inputs"]["consumers"][0]["inputs"][metric]
            )
    else:
        assert gaps[0]["diagnostic_candidates"] == []
    assert gaps[0]["business_date"] == "2026-04-01"
    assert gaps[0]["public_cutoff"] == "2026-04-01T15:59:59.999999+00:00"
    assert rejected["core_formula_inputs"]["status"] == "blocked"
    assert not [
        gap
        for gap in rejected["gaps"]
        if gap["metric_id"] == metric and gap.get("period", "") >= "2026-04-01"
    ]
    receipt, restored = capture_core(
        paths,
        version,
        metric,
        [day],
        value=101.0,
        published=lambda _: datetime(2026, 4, 1, 9, tzinfo=UTC),
    )
    recovered = preflight(paths, candidate, capsys)
    assert recovered["core_formula_inputs"]["status"] == "available"
    selected = next(
        p
        for p in recovered["core_formula_inputs"]["consumers"][0]["inputs"][metric]
        if p["period"] == day
    )
    assert selected["claim_id"] == restored[0].claim_id
    assert (
        recovered["core_formula_inputs"]["versions"][restored[0].claim_id]["originals"][0][
            "raw_hash"
        ]
        == receipt.raw_hash
    )
    assert read_preflight_receipt(paths, rejected["receipt_hash"], capsys) == rejected


def test_formula_warmup_must_be_covered_by_reviewed_source_certification(calendar_runtime, capsys):
    paths, _ = calendar_runtime
    candidate, version, day = prepare_core_runtime(paths, capsys, certified_from="2026-03-09")
    capture_core(paths, version, "CN_BOND_CORE_000012", [day])
    result = preflight(paths, candidate, capsys)
    gaps = [
        gap
        for gap in result["gaps"]
        if gap["reason"] == "core_formula_certification_not_covering_period"
    ]
    assert any(
        gap["period"] == "2025-08-29" and gap["business_date"] == "2026-04-01" for gap in gaps
    )
    assert result["core_formula_inputs"]["status"] == "blocked"


def test_friday_date_precision_becomes_public_on_saturday_but_system_waits_for_capture(
    calendar_runtime, capsys
):
    from datetime import UTC, datetime, timedelta

    from pring_cycle.evidence import AsOfMode, EvidenceRepository

    paths, _ = calendar_runtime
    candidate, version, day = prepare_core_runtime(paths, capsys)
    receipt, stored = capture_core(
        paths, version, "CN_BOND_CORE_000012", [day], published=lambda _: date(2025, 9, 5)
    )
    evidence = EvidenceRepository(paths.database)
    public_at = datetime(2025, 9, 5, 16, tzinfo=UTC)  # Saturday midnight in Shanghai.
    observation = stored[0].observation_id
    assert (
        evidence.query(
            observation, mode=AsOfMode.PUBLIC, as_of=public_at - timedelta(microseconds=1)
        ).selected_value
        is None
    )
    public = evidence.query(observation, mode=AsOfMode.PUBLIC, as_of=public_at)
    assert public.selected_claim_id == stored[0].claim_id
    assert public.claims[0].release_at is None
    assert public.claims[0].public_available_at == public_at
    assert evidence.query(observation, mode=AsOfMode.SYSTEM, as_of=public_at).selected_value is None
    assert (
        evidence.query(
            observation,
            mode=AsOfMode.SYSTEM,
            as_of=receipt.validated_at - timedelta(microseconds=1),
        ).selected_value
        is None
    )
    assert (
        evidence.query(
            observation, mode=AsOfMode.SYSTEM, as_of=receipt.validated_at
        ).selected_claim_id
        == stored[0].claim_id
    )
    result = preflight(paths, candidate, capsys)
    assert result["core_formula_inputs"]["status"] == "available"


def test_an_earlier_extra_row_cannot_hide_an_internal_warmup_hole(calendar_runtime, capsys):
    paths, _ = calendar_runtime
    candidate, version, day = prepare_core_runtime(paths, capsys)
    # The bond has 259 rows and starts earlier than required, but one required date is absent.
    capture_core(paths, version, "CN_BOND_CORE_000012", ["2025-08-28"])
    result = preflight(paths, candidate, capsys)
    assert result["core_formula_inputs"]["status"] == "blocked"
    assert any(
        gap["metric_id"] == "CN_BOND_CORE_000012"
        and gap.get("period") == day
        and gap["business_date"] == "2026-04-01"
        for gap in result["gaps"]
    )


def test_complete_report_calendar_does_not_prove_formula_history(calendar_runtime, capsys):
    paths, candidate = calendar_runtime
    capture_calendar(paths, json.loads(PLAN.read_text())["window"]["dates"])
    result = preflight(paths, candidate, capsys)
    assert result["calendar"]["status"] == "available"
    assert result["core_formula_inputs"]["status"] == "blocked"
    assert any(
        gap["reason"] == "core_formula_calendar_history_missing"
        and gap["business_date"] == "2026-04-01"
        and gap["missing_observations"] == 139
        for gap in result["gaps"]
    )


def test_base_formula_availability_does_not_confirm_persistent_state():
    from datetime import timedelta

    from pring_cycle.domain.stage import derive_formal_stage
    from pring_cycle.domain.trend import PricePoint, TrendRules, evaluate_trend

    points = [PricePoint(date(2025, 1, 1) + timedelta(days=i), 100.0 + i) for i in range(147)]
    first = evaluate_trend(points[:140], TrendRules())
    confirmed = evaluate_trend(points, TrendRules())
    assert first.distance_pct is not None and first.slope_pct is not None
    assert first.stable_state is None and first.candidate_state.value == "bull"
    assert first.candidate_days == 1
    assert (
        derive_formal_stage(
            bond=first.stable_state,
            stock=first.stable_state,
            commodity=first.stable_state,
            last_confirmed_stage=None,
        ).current_stage
        is None
    )
    assert confirmed.stable_state.value == "bull"
    assert confirmed.persistence_days == 8


def test_calendar_warmup_hole_cannot_be_filled_by_an_earlier_session(calendar_runtime, capsys):
    from pring_cycle.source_adapters import CORE_API_IDENTITIES

    paths, _ = calendar_runtime
    missing = "2025-09-05"
    days = json.loads(PLAN.read_text())["default_core_formula_input"]["dates"]
    altered = ["2025-08-28", *[day for day in days if day != missing]]
    candidate, version, _ = prepare_core_runtime(
        paths,
        capsys,
        certified_from="2025-08-28",
        calendar_days=altered,
        omitted_calendar_dates=(missing,),
    )
    for metric in CORE_API_IDENTITIES:
        capture_core(paths, version, metric, ["2025-08-28"])
    receipt = next(
        r
        for r in AcquisitionRepository(paths.database, paths.artifacts).history()
        if r.api_name == "trade_cal"
    )
    result = preflight(paths, candidate, capsys)
    assert result["calendar"]["dates"] == json.loads(PLAN.read_text())["window"]["dates"]
    assert result["core_formula_inputs"]["status"] == "blocked"
    gap = next(
        g for g in result["gaps"] if g["reason"] == "core_formula_calendar_coverage_unproven"
    )
    assert gap["missing_dates"] == ["2025-09-05"]
    assert gap["acquisition_id"] == receipt.acquisition_id
    assert gap["raw_hash"] == receipt.raw_hash
    assert result["core_formula_inputs"]["versions"] == {}
    assert read_preflight_receipt(paths, result["receipt_hash"], capsys) == result


@pytest.mark.parametrize("publication", ["unknown", "future"])
def test_unavailable_revision_cannot_replace_legal_formula_input(
    calendar_runtime, capsys, publication
):
    from datetime import UTC, datetime

    paths, _ = calendar_runtime
    candidate, version, day = prepare_core_runtime(paths, capsys)
    metric = "CN_BOND_CORE_000012"
    _, legal = capture_core(paths, version, metric, [day])
    receipt, revision = capture_core(
        paths,
        version,
        metric,
        [day],
        value=102.0,
        published=lambda _: (
            None if publication == "unknown" else datetime(2026, 9, 23, 8, tzinfo=UTC)
        ),
    )
    (paths.artifacts / receipt.raw_hash[:2] / receipt.raw_hash).write_bytes(
        b"damaged unseen revision"
    )
    result = preflight(paths, candidate, capsys)
    core = result["core_formula_inputs"]
    assert core["status"] == "available"
    assert legal[0].claim_id in core["versions"]
    assert revision[0].claim_id not in core["versions"]
    assert all(
        p["claim_id"] == legal[0].claim_id
        for consumer in core["consumers"]
        for p in consumer["inputs"][metric]
        if p["period"] == day
    )


def test_open_session_subset_does_not_prove_complete_formula_calendar(calendar_runtime, capsys):
    paths, _ = calendar_runtime
    candidate, version, day = prepare_core_runtime(paths, capsys, open_subset=True)
    capture_core(paths, version, "CN_BOND_CORE_000012", [day])
    result = preflight(paths, candidate, capsys)
    assert result["calendar"]["status"] == "available"
    assert result["core_formula_inputs"]["status"] == "blocked"
    coverage = result["calendar"]["history_coverage"]
    assert coverage["status"] == "unproven"
    assert "2025-08-30" in coverage["missing_dates"]
    assert result["core_formula_inputs"]["versions"] == {}
