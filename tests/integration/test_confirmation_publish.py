"""A model with confirmation rules, from the day summary to the pages and the report."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import pring_cycle.reports as reports_module
from pring_cycle.dashboard import dashboard_page
from pring_cycle.day_summary import DaySummaries, ModelRules, RunMaterials
from pring_cycle.evidence import EvidenceRepository
from pring_cycle.models import ModelRepository, certified_model_v0001_manifest
from pring_cycle.projections import (
    ProjectionSet,
    ProjectionSetRepository,
    validate_analytical_projection,
)
from pring_cycle.reports import (
    AdapterResponse,
    CliReportAdapter,
    ReportRepository,
    ReportService,
    report_input_from_projection,
)
from pring_cycle.runtime import RuntimePaths
from pring_cycle.trading_calendar import TradingCalendar
from tests.integration.test_backfill import summary
from tests.integration.test_confirmation_projection import append_pmi, confirmation_manifest
from tests.integration.test_core_carry_forward import CUTOFF, TARGET, seed_cores, sessions
from tests.integration.test_worker_execution import runtime
from tests.reports.test_report_boundary import FakeAdapter
from tests.web.test_dashboard_contract import _text

MODEL = "model-confirmation-fixture"
MONTHS = ("2026-05", "2026-06", "2026-07")


def register_confirmation_model(paths: RuntimePaths) -> None:
    base = certified_model_v0001_manifest()
    base["metric_definitions"] = [
        {**item, "certification_status": "certified"}
        if item["metric_id"] == "CN_PMI_ACTIVITY"
        else item
        for item in base["metric_definitions"]
    ]
    ModelRepository(paths.database).register(confirmation_manifest(base))


def seed_pmi(paths: RuntimePaths, values: tuple[float, ...]) -> None:
    repository = EvidenceRepository(paths.database)
    for series in ("manufacturing", "new_orders", "production", "purchase_volume"):
        append_pmi(
            repository, series, values, months=MONTHS, definition_version="metric-catalog-v0001"
        )


def publish(paths: RuntimePaths, model: str, window: tuple[str, ...] = ()) -> ProjectionSet:
    summaries = DaySummaries(
        EvidenceRepository(paths.database),
        ProjectionSetRepository(paths.database),
        ModelRules.of(ModelRepository(paths.database), model),
        calendar=TradingCalendar(sessions()),
    )
    result = summaries.summarize_target(
        TARGET.isoformat(),
        system_as_of=CUTOFF,
        run_materials=RunMaterials(),
        backfill_window=window,
    ).result
    assert result.projection_set_id is not None
    return ProjectionSetRepository(paths.database).get(result.projection_set_id)


def confirmed(
    tmp_path: Path, values: tuple[float, ...] | None = (50.2, 50.5, 51.0)
) -> ProjectionSet:
    paths = runtime(tmp_path)
    seed_cores(paths)
    register_confirmation_model(paths)
    if values is not None:
        seed_pmi(paths, values)
    return publish(paths, MODEL)


def overheat(projection: ProjectionSet) -> dict[str, Any]:
    dimensions = projection.datasets["macro"]["confirmation"]["dimensions"]
    return next(item for item in dimensions if item["dimension"] == "overheat")  # type: ignore[no-any-return]


def test_the_stage_decided_first_is_the_one_confirmed_and_published(tmp_path: Path) -> None:
    projection = confirmed(tmp_path)

    overview = projection.datasets["cycle_overview"]
    confirmation = projection.datasets["macro"]["confirmation"]
    assert overview["current_stage"] == confirmation["stage"] == "stage_iii"
    [pmi] = overheat(projection)["key_indicators"]
    assert pmi["relation"] == "support"
    assert pmi["proposition"] == "经济自底部恢复，需求与生产扩张"
    assert overheat(projection)["counts"]["support"] == 1
    assert projection.datasets["inventory"]["status"] == "not_connected"
    assert "cards" not in projection.datasets["inventory"]


def test_a_confirmation_gap_neither_holds_the_stage_nor_rewrites_its_history(
    tmp_path: Path,
) -> None:
    window = tuple(day.isoformat() for day in sessions()[-6:])
    old_paths = runtime(tmp_path / "old")
    seed_cores(old_paths)
    old = publish(old_paths, "model-v0001", window)
    new_paths = runtime(tmp_path / "new")
    seed_cores(new_paths)
    register_confirmation_model(new_paths)

    new = publish(new_paths, MODEL, window)

    [pmi] = overheat(new)["key_indicators"]
    assert pmi["relation"] == "unconfirmed" and pmi["missing"]
    assert new.datasets["cycle_overview"]["current_stage"] == "stage_iii"

    def history(projection: ProjectionSet) -> list[tuple[str, str | None, str]]:
        return [
            (item["business_date"], item["current_stage"], item["event_kind"])
            for item in projection.datasets["stage_history"]["events"]
        ]

    assert history(new) == history(old)
    # Every backfilled day was published in the new structure too.
    for day in window[:-1]:
        assert summary(new_paths, day).datasets["macro"]["output_structure"] == (
            "confirmation-v0001"
        )


def test_the_old_model_still_publishes_the_four_labels_and_seven_cards(tmp_path: Path) -> None:
    paths = runtime(tmp_path)
    seed_cores(paths)
    register_confirmation_model(paths)
    seed_pmi(paths, (50.2, 50.5, 51.0))

    old = publish(paths, "model-v0001")

    assert "output_structure" not in old.datasets["macro"]
    assert old.datasets["macro"]["overheat_state"]
    assert len(old.datasets["inventory"]["cards"]) == 7
    home = _text(dashboard_page("/", old, (), ()))
    assert all(label in home for label in ("政策方向", "信用响应", "过热程度", "物价压力"))
    assert "四象限解释" in _text(dashboard_page("/inventory", old, (), ()))


def test_the_pages_list_the_dimension_summary_and_the_pmi_reading(tmp_path: Path) -> None:
    projection = confirmed(tmp_path)

    home = _text(dashboard_page("/", projection, (), ()))
    macro = _text(dashboard_page("/macro", projection, (), ()))
    inventory = _text(dashboard_page("/inventory", projection, (), ()))

    assert "过热" in home and "支持 1" in home and "尚未接入" in home
    assert "PMI：支持" in home and "高于 50" in home and "较上期上升" in home
    assert "政策方向" not in home and "数据不足" not in home
    assert "制造业 PMI" in macro and "新订单" in macro and "斜率变陡" in macro
    assert "命题：经济自底部恢复，需求与生产扩张" in macro
    assert "政策维度尚未接入" in macro
    assert "库存维度尚未接入" in inventory and "七张阶段特征卡" not in inventory


def test_the_report_carries_the_counts_and_relations_as_conclusions(tmp_path: Path) -> None:
    bundle = report_input_from_projection(confirmed(tmp_path))

    assert bundle.schema_version == "report-schema-v0005"
    assert bundle.conclusions == {
        "confirmation_applicable": True,
        "dimension:policy": "not_connected",
        "dimension:credit": "not_connected",
        "dimension:overheat": {
            "support": 1,
            "counterevidence": 0,
            "observation_only": 0,
            "unconfirmed": 0,
            "not_applicable": 0,
        },
        "dimension:price": "not_connected",
        "dimension:inventory": "not_connected",
        "key_indicator:pmi": "support",
    }
    pmi = bundle.results["confirmation"]["key_indicators"]["pmi"]
    assert pmi["relation"] == "support" and pmi["members"][0]["momentum"] == "up"
    assert "observation_version_ids" not in json.dumps(bundle.prompt_document())


def test_the_cli_is_held_to_the_counts_as_integers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = report_input_from_projection(confirmed(tmp_path))
    sent: dict[str, Any] = {}

    def structured_cli(name: str, prompt: str, schema: dict[str, Any], **kwargs: Any) -> Any:
        sent.update(prompt=json.loads(prompt), schema=schema)
        return SimpleNamespace(
            document=None, classification="fixture", audit={}, version="fixture", tool_events=0
        )

    monkeypatch.setattr(reports_module, "run_structured_cli", structured_cli)

    CliReportAdapter("codex_cli").generate(bundle)

    conclusions = sent["schema"]["properties"]["conclusions"]["properties"]
    assert conclusions["dimension:overheat"]["properties"]["support"] == {
        "type": "integer",
        "const": 1,
    }
    assert conclusions["key_indicator:pmi"] == {"type": "string", "const": "support"}
    assert sent["prompt"]["execution_contract"]["schema_version"] == "report-schema-v0005"


def test_the_old_projection_reports_under_its_old_contract(tmp_path: Path) -> None:
    paths = runtime(tmp_path)
    seed_cores(paths)

    bundle = report_input_from_projection(publish(paths, "model-v0001"))

    assert bundle.schema_version == "report-schema-v0004"
    assert set(bundle.conclusions) == {
        "policy_direction",
        "credit_response",
        "overheat_state",
        "price_pressure",
        "inventory_quadrant",
    }


_OVERHEAT = {
    "support": 1,
    "counterevidence": 0,
    "observation_only": 0,
    "unconfirmed": 0,
    "not_applicable": 0,
}


def _document(bundle: Any, text: str, title: str = "过热", **conclusions: Any) -> dict[str, Any]:
    return {
        "bundle_id": bundle.bundle_id,
        "current_stage": bundle.current_stage,
        "report_cutoff": bundle.report_cutoff.isoformat(),
        "core_states": dict(bundle.core_states),
        "conclusions": {**bundle.conclusions, **conclusions},
        "sections": [{"title": title, "explanation": text}],
        "proxy_used": False,
    }


_KEPT = "PMI 高于 50 且回升，记为支持；过热维度支持 1、反证 0，其余维度尚未接入。"


@pytest.mark.parametrize(
    ("text", "change", "outcome"),
    [
        (_KEPT, {}, "succeeded"),
        ("PMI 并不是反证，而是回升。", {}, "succeeded"),
        ("PMI 不记为反证。", {}, "succeeded"),
        (_KEPT, {"key_indicator:pmi": "counterevidence"}, "conclusion_mutation_rejected"),
        (
            _KEPT,
            {"dimension:overheat": {**_OVERHEAT, "support": 0, "counterevidence": 1}},
            "conclusion_mutation_rejected",
        ),
        # A count of 1 rewritten as true is no count.
        (
            _KEPT,
            {"dimension:overheat": {**_OVERHEAT, "support": True}},
            "conclusion_mutation_rejected",
        ),
        (_KEPT, {"dimension:policy": {"support": 1}}, "conclusion_mutation_rejected"),
        # The conclusions echoed, the paragraph saying otherwise.
        ("PMI 虽高于 50，但构成反证。", {}, "conclusion_mutation_rejected"),
        ("过热维度支持 0、反证 1。", {}, "conclusion_mutation_rejected"),
        ("PMI 记为支持，但最终判为反证。", {}, "conclusion_mutation_rejected"),
        # The title names the dimension the paragraph's counts are given, sentence after
        # sentence.
        ("支持 0、反证 1。", {}, "conclusion_mutation_rejected"),
        ("支持 1。反证 1。", {}, "conclusion_mutation_rejected"),
        ("PMI 高于 50。后续记为反证。", {}, "conclusion_mutation_rejected"),
        # Denying the input's own relation is saying another.
        ("PMI 不记为支持。", {}, "conclusion_mutation_rejected"),
        # As the pages put it, a colon for the verb.
        ("PMI：反证。", {}, "conclusion_mutation_rejected"),
        ("过热维度：支持：0、反证：1。", {}, "conclusion_mutation_rejected"),
        ("PMI：支持。过热维度：支持：1、反证：0。", {}, "succeeded"),
        # A sentence about another subject is not said of the one before; a dimension
        # qualifying the indicator named is no other subject.
        ("PMI 记为支持。政策维度尚未接入，不记为支持。", {}, "succeeded"),
        ("PMI 在过热维度中记为反证。", {}, "conclusion_mutation_rejected"),
        # Negations however worded, of relations and of counts.
        ("PMI 没有被判为支持。", {}, "conclusion_mutation_rejected"),
        ("PMI 没有被判为反证。", {}, "succeeded"),
        ("PMI 并非支持。", {}, "conclusion_mutation_rejected"),
        ("PMI 并非反证，而是回升。", {}, "succeeded"),
        ("PMI 并非不支持。", {}, "succeeded"),
        ("过热维度支持不是 1，反证为 0。", {}, "conclusion_mutation_rejected"),
        ("过热维度并非支持 1。", {}, "conclusion_mutation_rejected"),
        ("过热维度不是支持 0，而是支持 1。", {}, "succeeded"),
        ("政策维度支持 2。", {}, "conclusion_mutation_rejected"),
    ],
)
def test_a_report_rewriting_the_relations_or_counts_is_rejected(
    tmp_path: Path, text: str, change: dict[str, Any], outcome: str
) -> None:
    bundle = report_input_from_projection(confirmed(tmp_path))
    reports = ReportRepository.create(tmp_path / "reports.sqlite3")
    first = FakeAdapter("codex_cli", AdapterResponse.succeeded(_document(bundle, text, **change)))
    second = FakeAdapter("claude_code_cli", AdapterResponse.unavailable("fixture"))

    result = ReportService(reports, (first, second)).generate(bundle)

    assert reports.attempts(result.report_snapshot_id)[0].outcome == outcome
    assert result.adapter == ("codex_cli" if outcome == "succeeded" else "deterministic")
    stored = reports.get(result.report_snapshot_id)
    assert stored.schema_version == "report-schema-v0005"


@pytest.mark.parametrize(
    ("title", "text", "outcome"),
    [
        ("PMI：", "反证。", "conclusion_mutation_rejected"),
        ("PMI：", "支持。", "succeeded"),
    ],
)
def test_a_title_runs_into_its_paragraph(
    tmp_path: Path, title: str, text: str, outcome: str
) -> None:
    bundle = report_input_from_projection(confirmed(tmp_path))
    reports = ReportRepository.create(tmp_path / "reports.sqlite3")
    first = FakeAdapter(
        "codex_cli", AdapterResponse.succeeded(_document(bundle, text, title=title))
    )
    second = FakeAdapter("claude_code_cli", AdapterResponse.unavailable("fixture"))

    result = ReportService(reports, (first, second)).generate(bundle)

    assert reports.attempts(result.report_snapshot_id)[0].outcome == outcome


def test_a_day_without_a_formal_stage_publishes_and_reports_confirmation_not_applicable(
    tmp_path: Path,
) -> None:
    paths = runtime(tmp_path)
    seed_cores(paths, commodity_missing=2)
    register_confirmation_model(paths)
    seed_pmi(paths, (50.2, 50.5, 51.0))

    held = publish(paths, MODEL)

    assert held.datasets["cycle_overview"]["current_stage"] is None
    confirmation = held.datasets["macro"]["confirmation"]
    assert confirmation["stage_reason"] == "core_data_pending"
    [pmi] = overheat(held)["key_indicators"]
    assert pmi["relation"] == "not_applicable" and pmi["members"][0]["momentum"] == "up"
    bundle = report_input_from_projection(held)
    assert bundle.conclusions["confirmation_applicable"] is False
    assert bundle.conclusions["key_indicator:pmi"] == "not_applicable"
    assert "不适用" in _text(dashboard_page("/", held, (), ()))


@pytest.mark.parametrize(
    ("edit", "error"),
    [
        (lambda macro: macro["confirmation"]["dimensions"].append(None), "invalid"),
        (lambda macro: macro["confirmation"].update(stage="stage_ii"), "stage_mismatch"),
        (
            lambda macro: macro["confirmation"]["dimensions"][2]["counts"].update(support=2),
            "invalid",
        ),
        (
            lambda macro: macro["confirmation"]["dimensions"][2]["counts"].update(support=True),
            "invalid",
        ),
        (lambda macro: macro.update(overheat_state="warming"), "retired_label_present"),
    ],
)
def test_a_dimension_summary_disagreeing_with_the_set_is_not_published(
    tmp_path: Path, edit: Any, error: str
) -> None:
    projection = confirmed(tmp_path)
    datasets = copy.deepcopy(projection.datasets)
    edit(datasets["macro"])

    with pytest.raises(ValueError, match=f"projection_confirmation_{error}"):
        validate_analytical_projection(projection.envelope, datasets)
