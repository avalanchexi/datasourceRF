"""A model is a version and an explicit pointer: switching needs no replay or acceptance."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from zoneinfo import ZoneInfo

import pytest

import pring_cycle.evidence as evidence_module
from pring_cycle import credit_impulse
from pring_cycle.catalog import metric_definition
from pring_cycle.cli import main
from pring_cycle.context_projection import ContextProjectionRules
from pring_cycle.core_history import refresh_core_history
from pring_cycle.dashboard import dashboard_page
from pring_cycle.day_summary import DaySummaries, ModelRules, RunMaterials
from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.models import (
    EFFECTIVE_CATALOG_VERSION,
    ModelRepository,
    certified_model_v0001_manifest,
    effective_model_manifest,
    model_v0013_manifest,
    model_v0014_manifest,
)
from pring_cycle.projections import ProjectionSet, ProjectionSetRepository
from pring_cycle.reports import report_input_from_projection
from pring_cycle.runtime import RuntimePaths
from pring_cycle.source_adapters import TushareCoreAdapter
from pring_cycle.trading_calendar import TradingCalendar, current_calendar
from pring_cycle.worker import process_pending_run
from tests.conftest import install_runtime_clock
from tests.integration import test_core_carry_forward as carry
from tests.integration.test_core_history_refresh import historical_response
from tests.integration.test_credit_impulse import AS_OF, EXPECTED, VERSION, gdp, social_financing
from tests.integration.test_decertified_main_chain import TARGET, seed_published_inputs
from tests.integration.test_worker_execution import runtime, seed_independent_calendar
from tests.web.test_dashboard_contract import _text


def cli(paths: RuntimePaths, capsys: pytest.CaptureFixture[str], *argv: str) -> dict[str, Any]:
    main([argv[0], "--runtime-root", str(paths.override_root), *argv[1:], "--json"])
    return dict(json.loads(capsys.readouterr().out))


def run_once(paths: RuntimePaths, capsys: pytest.CaptureFixture[str], request_id: str) -> str:
    submitted = cli(
        paths,
        capsys,
        "run-submit",
        "--target-date",
        TARGET.isoformat(),
        "--request-id",
        request_id,
        "--as-of",
        datetime(2026, 8, 28, 21).astimezone().isoformat(),
    )
    process_pending_run(paths, report_adapters=())
    return str(submitted["run_id"])


def summaries(paths: RuntimePaths) -> list[tuple[str, str]]:
    connection = sqlite3.connect(paths.database)
    try:
        return connection.execute(
            "SELECT projection_set_id, envelope_json FROM projection_set ORDER BY rowid"
        ).fetchall()
    finally:
        connection.close()


def batch_model(paths: RuntimePaths, run_id: str) -> str:
    connection = sqlite3.connect(paths.database)
    try:
        return str(
            connection.execute(
                "SELECT model_version_id FROM parent_run WHERE run_id=?", (run_id,)
            ).fetchone()[0]
        )
    finally:
        connection.close()


def test_activation_moves_the_pointer_for_later_runs_only(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = runtime(tmp_path)
    days = seed_published_inputs(paths)
    first = run_once(paths, capsys, "before-switch")
    published = summaries(paths)
    variant = certified_model_v0001_manifest()
    variant["model_version_id"] = "model-v0001-persistence-7"
    variant["trend_rules"]["persistence_days"] = 7
    manifest = tmp_path / "variant.json"
    manifest.write_text(json.dumps(variant), encoding="utf-8")

    registered = cli(paths, capsys, "model-register", "--manifest", str(manifest))
    activated = cli(
        paths, capsys, "model-activate", "--model", variant["model_version_id"], "--confirm"
    )
    # Each run fetches its calendar; the previous run's retention dropped the response.
    seed_independent_calendar(paths, days)
    second = run_once(paths, capsys, "after-switch")

    assert registered["status"] == "registered"
    assert activated["status"] == "active"
    assert batch_model(paths, first) == "model-v0001"
    assert batch_model(paths, second) == "model-v0001-persistence-7"
    assert summaries(paths)[: len(published)] == published
    assert len(summaries(paths)) == len(published) + 1

    cli(paths, capsys, "model-activate", "--model", "model-v0001", "--confirm")
    seed_independent_calendar(paths, days)
    third = run_once(paths, capsys, "rolled-back")

    assert batch_model(paths, third) == "model-v0001"
    assert ModelRepository(paths.database).active().model_version_id == "model-v0001"


def test_activation_still_needs_explicit_confirmation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = runtime(tmp_path)

    with pytest.raises(SystemExit):
        main(
            [
                "model-activate",
                "--runtime-root",
                str(paths.override_root),
                "--model",
                "model-v0003",
                "--json",
            ]
        )

    assert ModelRepository(paths.database).active().model_version_id == "model-v0001"
    assert "explicit_model_approval_required" in capsys.readouterr().err


def test_v0014_is_registered_by_the_user_s_commands_and_v0013_still_rolls_back(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """v0014 reads the twelve-month impulse without the proxy; v0013 keeps both (#25)."""
    paths = runtime(tmp_path)
    for manifest in (model_v0013_manifest(), model_v0014_manifest()):
        register(paths, capsys, tmp_path, manifest)
    models = ModelRepository(paths.database)

    def active_rules(model: str) -> tuple[ContextProjectionRules, dict[str, Any]]:
        assert cli(paths, capsys, "model-activate", "--model", model, "--confirm")["status"] == (
            "active"
        )
        manifest = models.manifest(models.active().model_version_id)
        return ContextProjectionRules.from_manifest(manifest), manifest

    rules, manifest = active_rules("model-v0014")
    credit = {item.metric_id: item for item in rules.metric_definitions}["CN_CREDIT_IMPULSE"]
    assert rules.formula_versions["credit_impulse"] == "credit-impulse-12m-flow-share-v0003"
    assert (rules.metric_catalog_version, credit.unit) == ("metric-catalog-v0006", "percent")
    assert manifest["trend_rules"]["proxy_12m_enabled"] is False

    rules, manifest = active_rules("model-v0013")
    version = rules.formula_versions["credit_impulse"]
    credit = {item.metric_id: item for item in rules.metric_definitions}["CN_CREDIT_IMPULSE"]
    assert version == "credit-impulse-ytd-flow-v0002"
    assert (rules.metric_catalog_version, credit.unit) == (
        "metric-catalog-v0005",
        "percentage_points",
    )
    assert "proxy_12m_enabled" not in manifest["trend_rules"]
    # Rolled back, the impulse reads two years again: their change of the share.
    cutoff = datetime(2026, 9, 18, 23, 59, tzinfo=ZoneInfo("Asia/Shanghai"))
    needs = credit_impulse.minimum_requirements(
        version, public_cutoff=cutoff, calendar=current_calendar()
    )
    assert needs.counts() == {"CN_SF_TOTAL": 25, "CN_GDP": 9}
    repository = certified_credit_inputs(paths, monkeypatch)
    result = credit_impulse.derive(
        repository, version, as_of=AS_OF, as_of_mode=AsOfMode.SYSTEM, definition_version=VERSION
    )
    assert (result.status, result.unit) == ("available", "percentage_points")
    assert result.value == pytest.approx(EXPECTED)


def register(
    paths: RuntimePaths,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    manifest: dict[str, Any],
) -> None:
    path = tmp_path / f"{manifest['model_version_id']}.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert cli(paths, capsys, "model-register", "--manifest", str(path))["status"] == "registered"


def activate(paths: RuntimePaths, capsys: pytest.CaptureFixture[str], model: str) -> None:
    assert cli(paths, capsys, "model-activate", "--model", model, "--confirm")["status"] == (
        "active"
    )


def test_v0015_is_the_newest_model_and_v0014_still_rolls_back(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """v0015 confirms the stage narrative by key indicators; v0014 keeps the four labels."""
    paths = runtime(tmp_path)
    for manifest in (model_v0014_manifest(), effective_model_manifest()):
        register(paths, capsys, tmp_path, manifest)
    models = ModelRepository(paths.database)

    activate(paths, capsys, "model-v0015")
    manifest = models.manifest(models.active().model_version_id)
    assert manifest["model_version_id"] == "model-v0015"
    assert manifest["projection_output_structure"] == "confirmation-v0001"
    assert manifest["metric_catalog_version"] == "metric-catalog-v0006"

    activate(paths, capsys, "model-v0014")
    manifest = models.manifest(models.active().model_version_id)
    assert "projection_output_structure" not in manifest
    assert "confirmation_rules" not in manifest


def publish_active(paths: RuntimePaths, window: tuple[str, ...]) -> ProjectionSet:
    """One day summarized by the active model, the days of ``window`` backfilled."""
    models = ModelRepository(paths.database)
    summaries = DaySummaries(
        EvidenceRepository(paths.database),
        ProjectionSetRepository(paths.database),
        ModelRules.of(models, models.active().model_version_id),
        calendar=TradingCalendar(carry.sessions()),
    )
    result = summaries.summarize_target(
        carry.TARGET.isoformat(),
        system_as_of=carry.CUTOFF,
        run_materials=RunMaterials(),
        backfill_window=window,
    ).result
    assert result.projection_set_id is not None
    return ProjectionSetRepository(paths.database).get(result.projection_set_id)


def test_switching_to_v0015_leaves_what_v0014_published_as_it_was(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
) -> None:
    """The new structure reaches later summaries only; old ones read and show as before."""
    paths = runtime(tmp_path)
    for manifest in (model_v0014_manifest(), effective_model_manifest()):
        register(paths, capsys, tmp_path, manifest)
    # Rising cores with their originals, which the registered catalog rechecks, taken
    # before the cutoff.
    install_runtime_clock(monkeypatch, request, carry.CUTOFF.astimezone(UTC).replace(hour=11))
    refresh_core_history(
        paths,
        TushareCoreAdapter("fixture-token", transport=historical_response),
        start=carry.sessions()[0],
        end=carry.TARGET,
        definition_version=EFFECTIVE_CATALOG_VERSION,
    )
    activate(paths, capsys, "model-v0014")
    window = tuple(day.isoformat() for day in carry.sessions()[-6:])
    old = publish_active(paths, window)
    published = summaries(paths)
    # Every day v0014 summarized, the backfilled ones too, as it published them.
    repository = ProjectionSetRepository(paths.database)
    datasets = {
        projection_id: repository.get(projection_id).datasets for projection_id, _ in published
    }
    assert {json.loads(envelope)["target_business_date"] for _, envelope in published} == set(
        window
    )
    history = repository.stage_history()
    old_report = report_input_from_projection(old)
    old_pages = {
        page: _text(dashboard_page(page, old, (), ())) for page in ("/", "/macro", "/inventory")
    }

    activate(paths, capsys, "model-v0015")
    new = publish_active(paths, window)

    assert summaries(paths)[: len(published)] == published
    assert {
        projection_id: repository.get(projection_id).datasets for projection_id in datasets
    } == datasets
    # The new day's assessments sit beside the old ones, which stay as assessed.
    assert all(repository.p0_assessment(str(item["assessment_id"])) == item for item in history)
    assert new.datasets["macro"]["output_structure"] == "confirmation-v0001"
    assert (
        new.datasets["cycle_overview"]["current_stage"]
        == old.datasets["cycle_overview"]["current_stage"]
    )
    # The history v0014 published leads the new one unchanged; the day summarized again is
    # listed once, at its new summary and the same stage (ticket 07).
    events = cast(list[dict[str, Any]], old.datasets["stage_history"]["events"])
    later = cast(list[dict[str, Any]], new.datasets["stage_history"]["events"])
    assert later[:-1] == events[:-1]
    assert [
        (item["business_date"], item["current_stage"], item["model_version_id"])
        for item in (events[-1], later[-1])
    ] == [
        (carry.TARGET.isoformat(), "stage_iii", "model-v0014"),
        (carry.TARGET.isoformat(), "stage_iii", "model-v0015"),
    ]
    # The old summary, read back after the switch, still shows the four labels and seven cards.
    reread = repository.get(old.envelope.projection_set_id)
    assert "output_structure" not in reread.datasets["macro"]
    assert len(cast(list[dict[str, Any]], reread.datasets["inventory"]["cards"])) == 7
    assert report_input_from_projection(reread) == old_report
    assert "confirmation" not in old_report.results
    assert "confirmation" in report_input_from_projection(new).results
    for page, text in old_pages.items():
        assert _text(dashboard_page(page, reread, (), ())) == text
    assert all(
        label in old_pages["/"] for label in ("政策方向", "信用响应", "过热程度", "物价压力")
    )
    assert "四象限解释" in old_pages["/inventory"]
    assert "四象限解释" not in _text(dashboard_page("/inventory", new, (), ()))


def certified_credit_inputs(
    paths: RuntimePaths, monkeypatch: pytest.MonkeyPatch
) -> EvidenceRepository:
    """Two years of year-to-date social financing and GDP, as the credit tests hold them."""

    def certified(  # type: ignore[no-untyped-def]
        metric_id: str, *, definition_version: str = VERSION, database_path: Path | None = None
    ):
        definition = metric_definition(
            metric_id, definition_version=definition_version, database_path=database_path
        )
        return replace(definition, certification_status="certified")

    monkeypatch.setattr(evidence_module, "metric_definition", certified)
    repository = EvidenceRepository(paths.database)
    social_financing(repository, "ytd_increment")
    gdp(repository, "nominal_ytd_level")
    return repository
