"""A model with confirmation rules, from the day summary to the pages and the report."""

from __future__ import annotations

import copy
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import pring_cycle.reports as reports_module
from pring_cycle.dashboard import dashboard_page
from pring_cycle.day_summary import DaySummaries, ModelRules, RunMaterials
from pring_cycle.domain import FormalStage
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
from tests.integration.test_confirmation_monthly_indicators import (
    BEFORE,
    YEAR,
    append,
    indicator,
    project,
    seed,
    year,
)
from tests.integration.test_confirmation_projection import append_pmi, confirmation_manifest
from tests.integration.test_core_carry_forward import CUTOFF, TARGET, seed_cores, sessions
from tests.integration.test_worker_execution import runtime
from tests.reports.test_report_boundary import FakeAdapter
from tests.web.test_dashboard_contract import _text

MODEL = "model-confirmation-fixture"
MONTHS = ("2026-05", "2026-06", "2026-07")
# The year to July, the newest month out on the target day.
TO_JULY = (BEFORE[-1], *YEAR[:-1])


def register_confirmation_model(
    paths: RuntimePaths, certified: tuple[str, ...] = ("CN_PMI_ACTIVITY",)
) -> None:
    base = certified_model_v0001_manifest()
    base["metric_definitions"] = [
        {**item, "certification_status": "certified"} if item["metric_id"] in certified else item
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


def pmi_of(projection: ProjectionSet) -> dict[str, Any]:
    return next(item for item in overheat(projection)["key_indicators"] if item["key"] == "pmi")  # type: ignore[no-any-return]


def test_the_stage_decided_first_is_the_one_confirmed_and_published(tmp_path: Path) -> None:
    projection = confirmed(tmp_path)

    overview = projection.datasets["cycle_overview"]
    confirmation = projection.datasets["macro"]["confirmation"]
    assert overview["current_stage"] == confirmation["stage"] == "stage_iii"
    pmi = pmi_of(projection)
    assert pmi["relation"] == "support"
    assert pmi["proposition"] == "经济自底部恢复，需求与生产扩张"
    assert overheat(projection)["counts"]["support"] == 1
    # Nothing of inventory held: its quadrant unconfirmed, no card's data there.
    inventory = projection.datasets["inventory"]
    assert inventory["status"] == "connected" and inventory["relation"] == "unconfirmed"
    cards = {card["name"]: card for card in inventory["cards"]}
    assert cards["new_orders"]["availability"] == "available"
    assert cards["finished_goods"]["availability"] == "unavailable"


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

    pmi = pmi_of(new)
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

    home = " ".join(_text(dashboard_page("/", projection, (), ())).split())
    macro = _text(dashboard_page("/macro", projection, (), ()))
    inventory = " ".join(_text(dashboard_page("/inventory", projection, (), ())).split())

    # Every dimension is read now, inventory by its quadrant; each card counts its rows.
    assert "过热 支持 1 · 反证 0 · 仅观察 0 · 未确认 4" in home and "尚未接入" not in home
    assert "库存 支持 0 · 反证 0 · 仅观察 0 · 未确认 1 库存象限 未确认" in home
    # The PMI row reads its relation; its drawer, the level and momentum.
    assert "PMI 支持 读取期 2026-07-31" in home and "高于 50" in home and "较上期上升" in home
    assert "政策方向" not in home and "数据不足" not in home
    assert "制造业 PMI" in macro and "新订单" in macro and "斜率变陡" in macro
    assert "命题：经济自底部恢复，需求与生产扩张" in macro
    # The policy dimension reads its five indicators, none held here.
    assert "政策利率" in macro and "DR007" in macro and "未确认 5" in macro
    assert "库存象限" in inventory and "七张阶段特征卡" not in inventory
    # The lines held nothing, and the quadrant is counted once as unconfirmed.
    assert "数据 不可用（缺失）" in inventory and "确认关系：未确认（象限仅计一项）" in inventory
    assert "实际库存近似（粗略价格调整代理）" in inventory and "不参与库存象限" in inventory


def test_the_pages_and_the_report_tell_the_turn_its_maturity_and_grace(tmp_path: Path) -> None:
    # Stage III: the PMI below 50 in July alone, a sprout within two months' grace.
    projection = confirmed(tmp_path, (50.5, 50.4, 49.6))

    pmi = pmi_of(projection)
    assert pmi["relation"] == "observation_only"
    macro = _text(dashboard_page("/macro", projection, (), ()))
    assert "时序：同步" in macro
    assert "转折观察：萌芽（已持续 1 期，自 2026-07-31）" in macro
    assert "宽限：反证条件已持续 1 期，自 2026-07-31，宽限 2 个月，未过宽限" in macro
    bundle = report_input_from_projection(projection)
    reading = bundle.results["confirmation"]["key_indicators"]["pmi"]
    assert reading["timing"] == "coincident"
    assert reading["statistical_period"] == "2026-07-31"
    assert reading["turn"]["maturity"] == "sprout"
    assert reading["grace"]["past"] is False and reading["grace"]["limit"] == 2
    assert bundle.conclusions["key_indicator:pmi"] == "observation_only"


def test_a_signal_held_past_what_was_read_is_told_as_at_least(tmp_path: Path) -> None:
    # Below 50 in every month read: past grace, from a month before those read.
    projection = confirmed(tmp_path, (49.8, 49.5, 49.2))

    assert pmi_of(projection)["relation"] == "counterevidence"
    macro = _text(dashboard_page("/macro", projection, (), ()))
    assert "转折观察：确认（至少已持续 3 期，起点早于所读历史）" in macro
    assert "宽限：反证条件至少已持续 3 期，起点早于所读历史，宽限 2 个月，已过宽限" in macro


def test_a_counterevidence_within_grace_is_not_published(tmp_path: Path) -> None:
    # Counted as counterevidence, its signal still within grace: a sprout counted.
    projection = confirmed(tmp_path, (50.5, 50.4, 49.6))
    datasets = copy.deepcopy(projection.datasets)
    dimension = datasets["macro"]["confirmation"]["dimensions"][2]
    dimension["key_indicators"][0]["relation"] = "counterevidence"
    dimension["counts"].update(observation_only=0, counterevidence=1)

    with pytest.raises(ValueError, match="projection_confirmation_invalid"):
        validate_analytical_projection(projection.envelope, datasets)


def test_the_report_carries_the_counts_and_relations_as_conclusions(tmp_path: Path) -> None:
    bundle = report_input_from_projection(confirmed(tmp_path))

    assert bundle.schema_version == "report-schema-v0005"
    # The PMI supports; the monthly indicators with nothing held are unconfirmed.
    assert bundle.conclusions == {
        "confirmation_applicable": True,
        "dimension:policy": {**_NONE, "unconfirmed": 5},
        "dimension:credit": {**_NONE, "unconfirmed": 3},
        "dimension:overheat": {**_NONE, "support": 1, "unconfirmed": 4},
        "dimension:price": {**_NONE, "unconfirmed": 3},
        "dimension:inventory": {**_NONE, "unconfirmed": 1},
        "key_indicator:pmi": "support",
        "key_indicator:industrial_va": "unconfirmed",
        "key_indicator:gdp": "unconfirmed",
        "key_indicator:capacity_utilization": "unconfirmed",
        "key_indicator:industrial_profit": "unconfirmed",
        "key_indicator:ppi": "unconfirmed",
        "key_indicator:cpi": "unconfirmed",
        "key_indicator:pmi_prices": "unconfirmed",
        "key_indicator:social_financing": "unconfirmed",
        "key_indicator:loans": "unconfirmed",
        "key_indicator:money": "unconfirmed",
        "key_indicator:policy_rate": "unconfirmed",
        "key_indicator:lpr": "unconfirmed",
        "key_indicator:rrr": "unconfirmed",
        "key_indicator:liquidity": "unconfirmed",
        "key_indicator:dr007": "unconfirmed",
        "key_indicator:inventory_quadrant": "unconfirmed",
    }
    pmi = bundle.results["confirmation"]["key_indicators"]["pmi"]
    assert pmi["relation"] == "support" and pmi["members"][0]["momentum"] == "up"
    assert pmi["members"][0]["label"] == "制造业 PMI"
    money = bundle.results["confirmation"]["key_indicators"]["money"]
    assert money["derived"][0]["label"] == "M1−M2"
    assert "observation_version_ids" not in json.dumps(bundle.prompt_document())


def test_the_price_and_credit_counts_reach_the_pages_and_the_report(tmp_path: Path) -> None:
    paths = runtime(tmp_path)
    seed_cores(paths)
    register_confirmation_model(paths, certified=("CN_PMI_ACTIVITY", "CN_PPI", "CN_SF_TOTAL"))
    seed_pmi(paths, (50.2, 50.5, 51.0))
    repository = EvidenceRepository(paths.database)
    # Stage III: the PPI rising, social financing's stock growth quickening on both sides.
    append(
        repository,
        "CN_PPI",
        {"category": "headline", "measure": "yoy"},
        year(-1.0, -0.4, 0.3, fill=-1.5),
        months=TO_JULY,
        definition_version="metric-catalog-v0001",
    )
    append(
        repository,
        "CN_SF_TOTAL",
        {"measure": "stock_yoy"},
        year(8.0, 8.2, 8.5, fill=8.0),
        months=TO_JULY,
        definition_version="metric-catalog-v0001",
    )

    projection = publish(paths, MODEL)

    bundle = report_input_from_projection(projection)
    assert bundle.conclusions["key_indicator:ppi"] == "support"
    assert bundle.conclusions["dimension:price"] == {**_NONE, "support": 1, "unconfirmed": 2}
    assert bundle.conclusions["key_indicator:social_financing"] == "support"
    assert bundle.conclusions["dimension:credit"] == {**_NONE, "support": 1, "unconfirmed": 2}
    home = " ".join(_text(dashboard_page("/", projection, (), ())).split())
    macro = _text(dashboard_page("/macro", projection, (), ()))
    assert "物价 支持 1 · 反证 0 · 仅观察 0 · 未确认 2 PPI 支持" in home
    assert "信用 支持 1 · 反证 0 · 仅观察 0 · 未确认 2 社融 支持" in home
    assert "M1/M2 未确认" in home
    assert "PPI 同比" in macro and "高于 0" in macro and "一年区间高位" in macro
    assert "存量同比" in macro and "命题：融资条件仍支持扩张" in macro
    # A member with nothing held says so.
    assert "PPI 环比 · 方向未知 · 无可用读数（缺失）" in macro


def test_a_cumulative_february_is_said_on_the_page_and_in_the_report(tmp_path: Path) -> None:
    # Industrial value added read through a February: its point is the January-February
    # cumulative growth, and both consumers say so (user, 2026-10-07).
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed(repository, "industrial_va", year(5.0, 5.2, 5.5, fill=5.0))
    read = indicator(project(repository, FormalStage.STAGE_III), "industrial_va")
    projection = confirmed(tmp_path / "published")
    datasets = copy.deepcopy(projection.datasets)
    overheat_document = next(
        item
        for item in datasets["macro"]["confirmation"]["dimensions"]
        if item["dimension"] == "overheat"
    )
    overheat_document["key_indicators"] = [
        read if item["key"] == "industrial_va" else item
        for item in overheat_document["key_indicators"]
    ]
    shown = replace(projection, datasets=datasets)

    macro = _text(dashboard_page("/macro", shown, (), ()))
    bundle = report_input_from_projection(shown)

    assert "2026-02-28 为1—2 月累计同比（累计口径）" in macro
    main = bundle.results["confirmation"]["key_indicators"]["industrial_va"]["members"][0]
    assert main["stand_ins"] == [{"period": "2026-02-28", "label": "1—2 月累计同比（累计口径）"}]


_NONE = {
    "support": 0,
    "counterevidence": 0,
    "observation_only": 0,
    "unconfirmed": 0,
    "not_applicable": 0,
}


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
        # The PMI's prices are their own indicator, not the PMI's.
        ("PMI 价格：未确认。PMI：支持。", {}, "succeeded"),
        ("PMI 价格记为支持。", {}, "conclusion_mutation_rejected"),
        ("社融：未确认。M1/M2 未确认。", {}, "succeeded"),
        ("M1/M2 记为支持。", {}, "conclusion_mutation_rejected"),
        # The inventory quadrant is its own indicator; inventory, its dimension (ticket 08).
        ("库存象限：未确认。库存维度未确认：1。", {}, "succeeded"),
        ("库存象限记为支持。", {}, "conclusion_mutation_rejected"),
        ("库存维度支持 1。", {}, "conclusion_mutation_rejected"),
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
    pmi = pmi_of(held)
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
