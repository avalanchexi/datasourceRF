from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.evidence import AsOfMode, EvidenceRepository, SourceClaimInput
from pring_cycle.model_evaluation import evaluate_context_replay
from pring_cycle.models import ModelRepository
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.search_evidence import select_retrieval_input
from tests.adapters.test_commodity_basket import (
    capture_reviewed_basket_inputs,
    fixed_weight_basket_transport,
)
from tests.models.test_candidate_admission import (
    bind_synthetic_review,
    encode,
    prepared_request,
    save,
    submit,
)


def admitted_commodity_manifest(
    paths: RuntimePaths, capsys: pytest.CaptureFixture[str], *, side: str = "default"
) -> dict[str, Any]:
    request, _ = prepared_request(paths)
    manifest = request["manifest"]
    manifest["metric_catalog_version"] += "-calendar-commodity-v2-" + side
    for definition in manifest["metric_definitions"]:
        definition["definition_version"] = manifest["metric_catalog_version"]
        if definition["metric_id"] in {
            "CN_COMMODITY_EX_HOG_BASKET",
            "CN_COMMODITY_SLEEVE_CONTRIBUTION",
        }:
            definition["source_codes"] = ["tushare:fut_daily:ex-hog-calendar-settlement-v0002"]
            if side == "candidate":
                definition["source_candidates"] = [
                    *definition["source_candidates"],
                    "synthetic:calendar-basket-contract-review",
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
    identity = json.loads(capsys.readouterr().out)["model_version_id"]
    return ModelRepository(paths.database).manifest(identity)


@pytest.mark.usefixtures("acquisition_clock")
def test_registered_basket_is_readable_with_all_seven_contributions(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifest = admitted_commodity_manifest(paths, capsys)
    capture_reviewed_basket_inputs(paths)
    from pring_cycle.commodity_basket import persist_commodity_basket

    result = persist_commodity_basket(
        paths,
        business_date=date(2026, 3, 10),
        mode=AsOfMode.PUBLIC,
        as_of=datetime(2026, 3, 10, 9, tzinfo=UTC),
        definition_version=manifest["metric_catalog_version"],
    )
    assert result["missing"] == []
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-03-10",
        client_request_id="synthetic-calendar-basket",
        model_version_id=manifest["model_version_id"],
        system_as_of=datetime(2026, 3, 10, 9, tzinfo=UTC),
        release_event_id="synthetic:calendar-basket",
        metric_ids=("CN_COMMODITY_EX_HOG_BASKET", "CN_COMMODITY_SLEEVE_CONTRIBUTION"),
        period="2026-03-10",
    )
    selection = select_retrieval_input(paths, run, mode=AsOfMode.PUBLIC)
    assert selection.complete, selection.missing_members
    assert set(selection.selected_claim_ids) == set(result["claim_ids"])
    evidence = EvidenceRepository(paths.database)
    basket = evidence.metric_series(
        "CN_COMMODITY_EX_HOG_BASKET",
        mode=AsOfMode.PUBLIC,
        as_of=datetime(2026, 3, 10, 9, tzinfo=UTC),
        definition_version=manifest["metric_catalog_version"],
    )
    assert len(basket) == 1
    assert basket[0].selected_value == pytest.approx(1012.6666666666666)
    sleeves = evidence.metric_series(
        "CN_COMMODITY_SLEEVE_CONTRIBUTION",
        mode=AsOfMode.PUBLIC,
        as_of=datetime(2026, 3, 10, 9, tzinfo=UTC),
        definition_version=manifest["metric_catalog_version"],
    )
    assert {p.dimensions["sleeve"]: p.selected_value for p in sleeves} == {
        "copper": 0,
        "rebar": 0,
        "polypropylene": 0,
        "textiles": 0,
        "rubber": 0,
        "pulp": 0,
        "crude_oil": -2,
    }


@pytest.mark.usefixtures("acquisition_clock")
def test_candidate_rechecks_settlement_original_and_recovers_after_restoration(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifest = admitted_commodity_manifest(paths, capsys)
    capture_reviewed_basket_inputs(paths)
    from pring_cycle.commodity_basket import persist_commodity_basket

    result = persist_commodity_basket(
        paths,
        business_date=date(2026, 3, 10),
        mode=AsOfMode.PUBLIC,
        as_of=datetime(2026, 3, 10, 9, tzinfo=UTC),
        definition_version=manifest["metric_catalog_version"],
    )
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-03-10",
        client_request_id="synthetic-basket-original-integrity",
        model_version_id=manifest["model_version_id"],
        system_as_of=datetime(2026, 3, 10, 9, tzinfo=UTC),
        release_event_id="synthetic:calendar-basket",
        period="2026-03-10",
        metric_ids=("CN_COMMODITY_EX_HOG_BASKET", "CN_COMMODITY_SLEEVE_CONTRIBUTION"),
    )
    assert select_retrieval_input(paths, run, mode=AsOfMode.PUBLIC).complete

    inputs = EvidenceRepository(paths.database).source_claim_acquisitions_many(result["claim_ids"])
    parent = next(p for p in inputs[result["claim_ids"][0]] if p.receipt.api_name == "fut_daily")
    digest = parent.receipt.raw_hash
    assert digest is not None
    original = paths.artifacts / digest[:2] / digest
    saved = original.read_bytes()
    original.write_bytes(b"corrupted settlement")
    rejected = select_retrieval_input(paths, run, mode=AsOfMode.PUBLIC)
    assert not rejected.complete and rejected.selected_claim_ids == ()
    original.write_bytes(saved)
    assert select_retrieval_input(paths, run, mode=AsOfMode.PUBLIC).complete


@pytest.mark.usefixtures("acquisition_clock")
def test_registered_basket_rejects_changed_value_attached_to_valid_inputs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifest = admitted_commodity_manifest(paths, capsys)
    capture_reviewed_basket_inputs(paths)
    from pring_cycle.commodity_basket import persist_commodity_basket

    result = persist_commodity_basket(
        paths,
        business_date=date(2026, 3, 10),
        mode=AsOfMode.PUBLIC,
        as_of=datetime(2026, 3, 10, 9, tzinfo=UTC),
        definition_version=manifest["metric_catalog_version"],
    )
    evidence = EvidenceRepository(paths.database)
    point = evidence.metric_series(
        "CN_COMMODITY_EX_HOG_BASKET",
        mode=AsOfMode.PUBLIC,
        as_of=datetime(2026, 3, 10, 9, tzinfo=UTC),
        definition_version=manifest["metric_catalog_version"],
    )[0]
    claim = point.claims[0]
    parents = evidence.source_claim_acquisitions_many(result["claim_ids"])[claim.claim_id]
    with pytest.raises(ValueError, match="commodity.*(original|result|value)"):
        evidence.append_source_claim(
            SourceClaimInput(
                metric_id="CN_COMMODITY_EX_HOG_BASKET",
                definition_version=manifest["metric_catalog_version"],
                period_kind="business_day",
                period_start="2026-03-10",
                period_end="2026-03-10",
                dimensions=point.dimensions,
                value=777,
                value_state=claim.value_state,
                unit=claim.unit,
                provider=claim.provider,
                source_reference=claim.source_reference,
                release_event_id="synthetic:wrong-basket-value",
                release_at=claim.release_at,
                public_available_at=claim.public_available_at,
                fetched_at=claim.fetched_at,
                available_at=claim.available_at,
                certification_status="certified",
                quality_status="validated",
                acquisition_ids=tuple(p.receipt.acquisition_id for p in parents),
            )
        )


@pytest.mark.usefixtures("acquisition_clock")
def test_registered_basket_rejects_previous_output_relabelled_as_closed_day(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from pring_cycle.acquisition import AcquisitionRepository
    from pring_cycle.commodity_basket import COMMODITY_FORMULA_VERSION, persist_commodity_basket

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifest = admitted_commodity_manifest(paths, capsys)

    def closed_day(payload: dict[str, Any]) -> bytes:
        document = json.loads(fixed_weight_basket_transport(payload))
        if payload["api_name"] == "fut_trade_cal":
            fields = document["data"]["fields"]
            for row in document["data"]["items"]:
                if row[fields.index("cal_date")] == "2026-03-11":
                    row[fields.index("is_open")] = 0
        return encode(document)

    capture_reviewed_basket_inputs(paths, transport=closed_day)
    cutoff = datetime(2026, 3, 11, 9, tzinfo=UTC)
    result = persist_commodity_basket(
        paths,
        business_date=date(2026, 3, 10),
        mode=AsOfMode.PUBLIC,
        as_of=cutoff,
        definition_version=manifest["metric_catalog_version"],
    )
    assert result["missing"] == []
    closed = persist_commodity_basket(
        paths,
        business_date=date(2026, 3, 11),
        mode=AsOfMode.PUBLIC,
        as_of=cutoff,
        definition_version=manifest["metric_catalog_version"],
    )
    assert closed["missing"] == ["commodity_target_output_missing"]
    assert closed["claim_ids"] == []
    evidence = EvidenceRepository(paths.database)
    point = evidence.metric_series(
        "CN_COMMODITY_EX_HOG_BASKET",
        mode=AsOfMode.PUBLIC,
        as_of=cutoff,
        definition_version=manifest["metric_catalog_version"],
    )[0]
    claim = point.claims[0]
    parents = evidence.source_claim_acquisitions_many(result["claim_ids"])[claim.claim_id]
    snapshot = next(p for p in parents if p.receipt.api_name == "commodity_basket")
    document = json.loads(snapshot.raw)
    document["business_date"] = "2026-03-11"
    raw = encode(document)
    digest = hashlib.sha256(raw).hexdigest()
    output = AcquisitionRepository(paths.database, paths.artifacts).capture(
        provider="derived",
        api_name="commodity_basket",
        parameters={"result_hash": digest},
        fields="level,seven_sleeve_contributions",
        parser_version=COMMODITY_FORMULA_VERSION,
        fetch=lambda: raw,
        parse=json.loads,
        normalize=lambda value: value,
    )
    with pytest.raises(ValueError, match="commodity.*(original|result|value)"):
        evidence.append_source_claim(
            SourceClaimInput(
                metric_id="CN_COMMODITY_EX_HOG_BASKET",
                definition_version=manifest["metric_catalog_version"],
                period_kind="business_day",
                period_start="2026-03-11",
                period_end="2026-03-11",
                dimensions=point.dimensions,
                value=point.selected_value,
                value_state=claim.value_state,
                unit=claim.unit,
                provider=claim.provider,
                source_reference="tushare:commodity_basket:level:2026-03-11",
                release_event_id="commodity:" + digest,
                release_at=claim.release_at,
                public_available_at=claim.public_available_at,
                fetched_at=output.receipt.received_at,
                available_at=output.receipt.validated_at,
                certification_status="certified",
                quality_status="validated",
                acquisition_ids=(
                    *(p.receipt.acquisition_id for p in parents if p is not snapshot),
                    output.receipt.acquisition_id,
                ),
            )
        )


def test_registered_revision_preserves_old_public_system_results_and_parent_artifacts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], acquisition_clock: Callable[[], datetime]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifest = admitted_commodity_manifest(paths, capsys)
    capture_reviewed_basket_inputs(paths)
    from pring_cycle.commodity_basket import persist_commodity_basket

    old_public = datetime(2026, 3, 10, 9, tzinfo=UTC)
    first = persist_commodity_basket(
        paths,
        business_date=date(2026, 3, 10),
        mode=AsOfMode.PUBLIC,
        as_of=old_public,
        definition_version=manifest["metric_catalog_version"],
    )
    old_system = acquisition_clock()
    digest = first["result_hash"]
    immutable = paths.artifacts / digest[:2] / digest
    original = immutable.read_bytes()

    def select(mode: AsOfMode, cutoff: datetime, label: str):
        run = RunRepository(paths.database).submit(
            command_type="targeted_refresh",
            target_business_date="2026-03-10",
            client_request_id=label,
            model_version_id=manifest["model_version_id"],
            system_as_of=cutoff,
            release_event_id="synthetic:commodity-revision",
            metric_ids=("CN_COMMODITY_EX_HOG_BASKET", "CN_COMMODITY_SLEEVE_CONTRIBUTION"),
            period="2026-03-10",
        )
        return select_retrieval_input(paths, run, mode=mode)

    before_public = select(AsOfMode.PUBLIC, old_public, "before-public")
    before_system = select(AsOfMode.SYSTEM, old_system, "before-system")
    assert before_public.complete and before_system.complete

    def revised_prices(payload: dict[str, Any]) -> bytes:
        raw = fixed_weight_basket_transport(payload)
        if payload["api_name"] == "fut_daily" and payload["params"]["ts_code"] == "SC2604.INE":
            document = json.loads(raw)
            fields = document["data"]["fields"]
            document["data"]["items"][2][fields.index("settle")] = "88"
            return encode(document)
        return raw

    capture_reviewed_basket_inputs(
        paths, transport=revised_prices, settlement_revision_at="2026-03-10T10:00:00+00:00"
    )
    second = persist_commodity_basket(
        paths,
        business_date=date(2026, 3, 10),
        mode=AsOfMode.PUBLIC,
        as_of=datetime(2026, 3, 10, 11, tzinfo=UTC),
        definition_version=manifest["metric_catalog_version"],
    )
    assert second["missing"] == [] and second["result_hash"] != digest
    assert immutable.read_bytes() == original
    assert select(AsOfMode.PUBLIC, old_public, "after-old-public") == before_public
    assert select(AsOfMode.SYSTEM, old_system, "after-old-system") == before_system
    latest = select(AsOfMode.PUBLIC, datetime(2026, 3, 10, 11, tzinfo=UTC), "after-new-public")
    assert latest.complete and set(latest.selected_claim_ids) == set(second["claim_ids"])
    current = select(AsOfMode.SYSTEM, acquisition_clock(), "after-new-system")
    assert current.complete and set(current.selected_claim_ids) == set(second["claim_ids"])
    evidence = EvidenceRepository(paths.database)
    values = evidence.metric_series(
        "CN_COMMODITY_EX_HOG_BASKET",
        mode=AsOfMode.PUBLIC,
        as_of=datetime(2026, 3, 10, 11, tzinfo=UTC),
        definition_version=manifest["metric_catalog_version"],
    )
    assert values[0].selected_value == pytest.approx(992)
    parents = evidence.source_claim_acquisitions_many(first["claim_ids"])
    assert all(parents[identity] for identity in first["claim_ids"])


@pytest.mark.usefixtures("acquisition_clock")
def test_public_replay_rechecks_registered_commodity_originals(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from pring_cycle.commodity_basket import persist_commodity_basket

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    capture_reviewed_basket_inputs(paths)
    manifests = {}
    output = None
    for side in ("comparison", "candidate"):
        manifest = admitted_commodity_manifest(paths, capsys, side=side)
        manifest.pop("source_certification_packages")
        manifests[side] = manifest
        output = persist_commodity_basket(
            paths,
            business_date=date(2026, 3, 10),
            mode=AsOfMode.PUBLIC,
            as_of=datetime(2026, 3, 10, 9, tzinfo=UTC),
            definition_version=manifest["metric_catalog_version"],
        )
    assert output is not None

    def replay():
        return evaluate_context_replay(
            paths.database,
            manifests["candidate"],
            manifests["comparison"],
            requested_start="2026-03-10",
            requested_end="2026-03-10",
        )

    before = replay()
    assert before.evaluated_cutoffs == 1 and not before.gaps, before.gaps
    digest = output["result_hash"]
    artifact = paths.artifacts / digest[:2] / digest
    raw = artifact.read_bytes()
    try:
        artifact.write_bytes(b"damaged candidate result")
        after = replay()
        assert "candidate_context_selection_invalid:CN_COMMODITY_EX_HOG_BASKET" in after.gaps
        assert not any(gap.startswith("comparison_") for gap in after.gaps)
    finally:
        artifact.write_bytes(raw)
    restored = replay()
    assert restored.evaluated_cutoffs == 1 and not restored.gaps, restored.gaps


@pytest.mark.usefixtures("acquisition_clock")
@pytest.mark.parametrize("representation", ["prices", "czce_symbol"])
def test_equivalent_price_redelivery_keeps_saved_candidate_and_original_parents(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], representation: str
) -> None:
    from pring_cycle.commodity_basket import persist_commodity_basket

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifest = admitted_commodity_manifest(paths, capsys)
    capture_reviewed_basket_inputs(paths)
    output = persist_commodity_basket(
        paths,
        business_date=date(2026, 3, 10),
        mode=AsOfMode.PUBLIC,
        as_of=datetime(2026, 3, 10, 9, tzinfo=UTC),
        definition_version=manifest["metric_catalog_version"],
    )
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-03-10",
        client_request_id="synthetic-equivalent-basket",
        model_version_id=manifest["model_version_id"],
        system_as_of=datetime(2026, 3, 10, 9, tzinfo=UTC),
        release_event_id="synthetic:basket",
        metric_ids=("CN_COMMODITY_EX_HOG_BASKET", "CN_COMMODITY_SLEEVE_CONTRIBUTION"),
        period="2026-03-10",
    )
    before = select_retrieval_input(paths, run, mode=AsOfMode.PUBLIC)
    assert before.complete

    def equivalent_prices(payload: dict[str, Any]) -> bytes:
        document = json.loads(fixed_weight_basket_transport(payload))
        if representation == "prices" and payload["api_name"] == "fut_daily":
            fields = document["data"]["fields"]
            for row in document["data"]["items"]:
                for field in ("settle", "pre_settle"):
                    row[fields.index(field)] += ".0"
        if representation == "czce_symbol" and payload["api_name"] == "fut_basic":
            fields = document["data"]["fields"]
            for row in document["data"]["items"]:
                if row[fields.index("exchange")] == "CZCE":
                    symbol = row[fields.index("symbol")]
                    row[fields.index("symbol")] = symbol[:2] + symbol[3:]
        return encode(document)

    capture_reviewed_basket_inputs(paths, transport=equivalent_prices)
    assert select_retrieval_input(paths, run, mode=AsOfMode.PUBLIC) == before
    assert set(before.selected_claim_ids) == set(output["claim_ids"])


def test_system_result_with_unknown_publication_is_not_public_evidence(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], acquisition_clock: Callable[[], datetime]
) -> None:
    from pring_cycle.commodity_basket import persist_commodity_basket

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifest = admitted_commodity_manifest(paths, capsys)
    capture_reviewed_basket_inputs(paths, unknown_settlement_public=True)
    result = persist_commodity_basket(
        paths,
        business_date=date(2026, 3, 10),
        mode=AsOfMode.SYSTEM,
        as_of=acquisition_clock(),
        definition_version=manifest["metric_catalog_version"],
    )
    assert not result["missing"] and len(result["claim_ids"]) == 8
    evidence = EvidenceRepository(paths.database)
    system = evidence.metric_series(
        "CN_COMMODITY_EX_HOG_BASKET",
        mode=AsOfMode.SYSTEM,
        as_of=acquisition_clock(),
        definition_version=manifest["metric_catalog_version"],
    )
    assert len(system) == 1 and system[0].selected_value == pytest.approx(1012.6666666666666)
    assert all(c.public_available_at is None for c in system[0].claims)
    assert (
        evidence.metric_series(
            "CN_COMMODITY_EX_HOG_BASKET",
            mode=AsOfMode.PUBLIC,
            as_of=acquisition_clock(),
            definition_version=manifest["metric_catalog_version"],
        )
        == ()
    )
