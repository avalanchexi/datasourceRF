"""A metric keeps one definition across catalog versions that did not change it (ADR-0036)."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.cli import main
from pring_cycle.evidence import (
    AsOfMode,
    EvidenceRepository,
    EvidenceValueState,
    SourceClaimInput,
    StoredSourceClaim,
    _append_source_claim,
)
from pring_cycle.models import (
    MODEL_V0012_CATALOG_VERSION,
    MODEL_V0013_CATALOG_VERSION,
    MODEL_V0014_CATALOG_VERSION,
    model_v0012_manifest,
    model_v0013_manifest,
    model_v0014_manifest,
)
from pring_cycle.runtime import RuntimePaths
from pring_cycle.same_definition import _same
from tests.integration.test_worker_execution import runtime

V0012, V0013, V0014 = (
    MODEL_V0012_CATALOG_VERSION,
    MODEL_V0013_CATALOG_VERSION,
    MODEL_V0014_CATALOG_VERSION,
)
AS_OF = datetime(2026, 10, 2, tzinfo=UTC)


def register(paths: RuntimePaths, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    for manifest in (model_v0012_manifest(), model_v0013_manifest(), model_v0014_manifest()):
        path = tmp_path / f"{manifest['model_version_id']}.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        main(
            [
                "model-register",
                "--runtime-root",
                str(paths.override_root),
                "--manifest",
                str(path),
                "--json",
            ]
        )
        assert json.loads(capsys.readouterr().out)["status"] == "registered"


@pytest.fixture
def registered(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> RuntimePaths:
    paths = runtime(tmp_path)
    register(paths, tmp_path, capsys)
    return paths


def claim(
    version: str,
    value: float,
    *,
    day: str = "2026-09-29",
    provider: str = "tushare",
    available: datetime = datetime(2026, 9, 30, tzinfo=UTC),
    metric_id: str = "CN_DR007",
    unit: str = "percent",
) -> SourceClaimInput:
    return SourceClaimInput(
        metric_id=metric_id,
        definition_version=version,
        period_kind="day",
        period_start=day,
        period_end=day,
        dimensions={},
        value=value,
        value_state=EvidenceValueState.REPORTED_VALUE,
        unit=unit,
        provider=provider,
        source_reference=f"fixture:{provider}:{metric_id}:{day}",
        release_event_id=f"release:{metric_id}:{day}:{provider}:{available.isoformat()}",
        release_at=available,
        public_available_at=available,
        fetched_at=available,
        available_at=available,
        quality_status="validated",
        certification_status="certified",
    )


def stored(repository: EvidenceRepository, item: SourceClaimInput) -> StoredSourceClaim:
    """A claim taken earlier; its delivery contract was checked when it was fetched."""
    with repository._connect() as connection:
        return _append_source_claim(connection, item)


def series(paths: RuntimePaths, version: str, metric_id: str = "CN_DR007") -> tuple[Any, ...]:
    return EvidenceRepository(paths.database).metric_series(
        metric_id, mode=AsOfMode.SYSTEM, as_of=AS_OF, definition_version=version
    )


def test_unchanged_metrics_share_their_definition_and_changed_ones_do_not(
    registered: RuntimePaths,
) -> None:
    """v0014 changed only the credit impulse; v0013 changed breadth's source codes."""
    versions = EvidenceRepository(registered.database).same_definition_versions
    assert {V0012, V0013, V0014} <= set(versions("CN_DR007", V0014))
    assert versions("CN_CREDIT_IMPULSE", V0014) == (V0014,)
    assert {V0012, V0013} <= set(versions("CN_CREDIT_IMPULSE", V0013))
    assert V0014 not in versions("CN_CREDIT_IMPULSE", V0013)
    assert set(versions("CN_EQ_ADV_DEC", V0014)) == {V0013, V0014}
    assert V0013 not in versions("CN_EQ_ADV_DEC", V0012)


def test_a_builtin_catalog_shares_an_unchanged_definition_both_ways(
    registered: RuntimePaths,
) -> None:
    versions = EvidenceRepository(registered.database).same_definition_versions
    assert "metric-catalog-v0003" in versions("CN_DR007", V0014)
    assert V0014 in versions("CN_DR007", "metric-catalog-v0003")


def test_a_derived_metric_needs_the_same_known_formula() -> None:
    definition = {
        "metric_id": "CN_CREDIT_IMPULSE",
        "unit": "percent",
        "allowed_units": ["percent"],
        "frequency": "monthly",
        "dimensions": [],
        "source_codes": ["CN_CREDIT_IMPULSE"],
    }
    known = ({"CN_CREDIT_IMPULSE": definition}, {"credit_impulse": "f-v1"})
    assert _same("CN_CREDIT_IMPULSE", known, known)
    assert not _same(
        "CN_CREDIT_IMPULSE", known, ({"CN_CREDIT_IMPULSE": definition}, {"credit_impulse": "f-v2"})
    )
    unknown = ({"CN_CREDIT_IMPULSE": definition}, {"credit_impulse": None})
    assert not _same("CN_CREDIT_IMPULSE", unknown, ({"CN_CREDIT_IMPULSE": definition}, {}))
    assert not _same("CN_CREDIT_IMPULSE", known, unknown)
    # A metric no formula computes compares its fields only.
    plain = {**definition, "metric_id": "CN_DR007"}
    assert _same("CN_DR007", ({"CN_DR007": plain}, {}), ({"CN_DR007": plain}, {}))


def register_manifest(
    paths: RuntimePaths,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    manifest: dict[str, Any],
) -> None:
    path = tmp_path / f"{manifest['model_version_id']}.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    main(
        [
            "model-register",
            "--runtime-root",
            str(paths.override_root),
            "--manifest",
            str(path),
            "--json",
        ]
    )
    assert json.loads(capsys.readouterr().out)["status"] == "registered"


def test_a_catalog_two_models_compute_differently_shares_no_derived_definition(
    registered: RuntimePaths, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """v0013's catalog reused by a model with another credit formula: the formula is unknown."""
    other = model_v0013_manifest()
    other["model_version_id"] = "model-v0013-other-formula"
    other["derived_formula_versions"]["credit_impulse"] = "credit-impulse-rolling-share-v0001"
    register_manifest(registered, tmp_path, capsys, other)

    versions = EvidenceRepository(registered.database).same_definition_versions
    assert V0012 not in versions("CN_CREDIT_IMPULSE", V0013)
    assert V0012 in versions("CN_DR007", V0013)


def test_a_catalog_whose_model_lacks_the_formula_shares_no_derived_definition(
    registered: RuntimePaths, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    lacking = model_v0013_manifest()
    lacking["model_version_id"] = "model-without-credit-formula"
    lacking["metric_catalog_version"] = "metric-catalog-without-credit-formula"
    for definition in lacking["metric_definitions"]:
        definition["definition_version"] = lacking["metric_catalog_version"]
    del lacking["derived_formula_versions"]["credit_impulse"]
    register_manifest(registered, tmp_path, capsys, lacking)

    versions = EvidenceRepository(registered.database).same_definition_versions
    assert versions("CN_CREDIT_IMPULSE", lacking["metric_catalog_version"]) == (
        lacking["metric_catalog_version"],
    )
    assert lacking["metric_catalog_version"] in versions("CN_DR007", V0013)


def test_a_catalog_changed_behind_its_hash_is_refused(registered: RuntimePaths) -> None:
    with sqlite3.connect(registered.database) as connection:
        connection.execute(
            "UPDATE registered_metric_catalog SET definitions_json=replace(definitions_json, "
            "'\"percent\"', '\"basis_points\"') WHERE catalog_version=?",
            (V0013,),
        )
    with pytest.raises(ValueError, match="registered_metric_catalog_hash_mismatch"):
        EvidenceRepository(registered.database).same_definition_versions("CN_DR007", V0014)


def test_a_builtin_catalog_shares_no_derived_definition(registered: RuntimePaths) -> None:
    versions = EvidenceRepository(registered.database).same_definition_versions
    assert versions("CN_CREDIT_IMPULSE", "metric-catalog-v0002") == ("metric-catalog-v0002",)
    assert "metric-catalog-v0002" not in versions("CN_CREDIT_IMPULSE", V0013)


def test_a_catalog_registered_later_is_seen_by_an_open_repository(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = runtime(tmp_path)
    repository = EvidenceRepository(paths.database)
    assert repository.same_definition_versions("CN_DR007", V0014) == (V0014,)
    register(paths, tmp_path, capsys)
    assert V0013 in repository.same_definition_versions("CN_DR007", V0014)


def test_without_a_version_different_definitions_stay_apart(registered: RuntimePaths) -> None:
    repository = EvidenceRepository(registered.database)
    for version, value, unit in ((V0013, 0.5, "percentage_points"), (V0014, 20.0, "percent")):
        stored(
            repository,
            replace(
                claim(version, value, metric_id="CN_CREDIT_IMPULSE", unit=unit),
                period_kind="month",
                period_start="2026-08-01",
                period_end="2026-08-31",
            ),
        )

    points = repository.metric_series("CN_CREDIT_IMPULSE", mode=AsOfMode.SYSTEM, as_of=AS_OF)
    assert sorted(p.selected_value for p in points) == [0.5, 20.0]


def test_a_claim_taken_under_the_old_catalog_is_read_by_the_new_model_and_back(
    registered: RuntimePaths,
) -> None:
    repository = EvidenceRepository(registered.database)
    stored(repository, claim(V0013, 1.38, day="2026-09-28"))
    stored(repository, claim(V0014, 1.39, day="2026-09-29"))

    for version in (V0013, V0014):
        points = series(registered, version)
        assert [(p.period_end, p.selected_value) for p in points] == [
            ("2026-09-28", 1.38),
            ("2026-09-29", 1.39),
        ]


def test_one_period_across_versions_is_one_observation_and_the_newest_revision_wins(
    registered: RuntimePaths,
) -> None:
    repository = EvidenceRepository(registered.database)
    stored(repository, claim(V0013, 1.38))
    newer = stored(repository, claim(V0014, 1.40, available=datetime(2026, 10, 1, tzinfo=UTC)))

    (point,) = series(registered, V0014)
    assert point.selected_value == 1.40
    assert point.selected_claim_id == newer.claim_id
    assert point.selection_status != "conflicted"


def test_two_sources_across_versions_still_conflict_beyond_half_a_percent(
    registered: RuntimePaths,
) -> None:
    repository = EvidenceRepository(registered.database)
    stored(repository, claim(V0013, 1.38, provider="tushare"))
    stored(repository, claim(V0014, 1.50, provider="pbc-official"))

    (point,) = series(registered, V0014)
    assert point.selection_status == "conflicted"


def test_a_changed_definition_keeps_its_old_claims_apart(registered: RuntimePaths) -> None:
    repository = EvidenceRepository(registered.database)
    old = replace(
        claim(V0013, 0.5, metric_id="CN_CREDIT_IMPULSE", unit="percentage_points"),
        period_kind="month",
        period_start="2026-08-01",
        period_end="2026-08-31",
    )
    stored(repository, old)

    assert series(registered, V0014, "CN_CREDIT_IMPULSE") == ()
    assert len(series(registered, V0013, "CN_CREDIT_IMPULSE")) == 1


def test_tracing_a_merged_observation_shows_every_version_s_claims(
    registered: RuntimePaths,
) -> None:
    repository = EvidenceRepository(registered.database)
    old = stored(repository, claim(V0013, 1.38))
    new = stored(repository, claim(V0014, 1.40, available=datetime(2026, 10, 1, tzinfo=UTC)))

    (point,) = series(registered, V0014)
    assert point.observation_id == new.observation_id
    from_old = repository.query(old.observation_id, mode=AsOfMode.SYSTEM, as_of=AS_OF)
    assert from_old.selected_claim_id == new.claim_id
    trace = repository.trace(old.observation_id, mode=AsOfMode.SYSTEM, as_of=AS_OF)
    assert trace.selected_claim_id == new.claim_id


def test_preloaded_series_merge_the_same_way(registered: RuntimePaths) -> None:
    repository = EvidenceRepository(registered.database)
    stored(repository, claim(V0013, 1.38, day="2026-09-28"))
    stored(repository, claim(V0013, 1.38))
    stored(repository, claim(V0014, 1.40, available=datetime(2026, 10, 1, tzinfo=UTC)))

    repository.preload_metric_series({("CN_DR007", V0014)})
    points = repository.metric_series(
        "CN_DR007", mode=AsOfMode.SYSTEM, as_of=AS_OF, definition_version=V0014
    )
    assert [(p.period_end, p.selected_value) for p in points] == [
        ("2026-09-28", 1.38),
        ("2026-09-29", 1.40),
    ]
