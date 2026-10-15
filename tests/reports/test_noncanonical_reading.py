from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.dashboard import dashboard_page
from pring_cycle.domain import CoreAssetState, FormalStage
from pring_cycle.noncanonical import TITLE, fact_sentences, observation_sentences
from pring_cycle.p0 import P0ProjectionService
from pring_cycle.projections import ProjectionSet, ProjectionSetRepository
from pring_cycle.reports import (
    AdapterResponse,
    CliReportAdapter,
    ReportInput,
    ReportRepository,
    ReportService,
    report_input_from_projection,
)
from tests.integration.test_p0_gate import readiness
from tests.reports.test_report_boundary import FakeAdapter
from tests.web.test_dashboard_contract import _text


def projection(tmp_path: Path, states: tuple[str | None, ...]) -> ProjectionSet:
    repository = ProjectionSetRepository.create(tmp_path / "projection.sqlite3")
    P0ProjectionService(repository).publish(
        target_business_date="2026-10-14",
        system_as_of=datetime(2026, 10, 15, 2, tzinfo=UTC),
        assets=tuple(
            replace(
                readiness(asset, CoreAssetState(state) if state else None),
                candidate_30d=CoreAssetState.BEAR,
                candidate_state=None,
                candidate_days=0,
                persistence_required=8,
            )
            for asset, state in zip(("bond", "stock", "commodity"), states, strict=True)
        ),
        last_confirmed_stage=FormalStage.STAGE_III,
    )
    return repository.current()


def document(source: ReportInput) -> dict[str, Any]:
    basis = source.results["noncanonical_basis"]
    return {
        "bundle_id": source.bundle_id,
        "current_stage": None,
        "report_cutoff": source.report_cutoff.isoformat(),
        "core_states": source.core_states,
        "conclusions": source.conclusions,
        "proxy_used": False,
        "sections": [
            {
                "title": TITLE,
                "explanation": "".join([*fact_sentences(basis), *observation_sentences(basis)]),
            }
        ],
    }


@pytest.mark.parametrize(
    "states,expected",
    [
        (
            ("bull", "bear", "bull"),
            [("stage_i", "commodity"), ("stage_iii", "stock"), ("stage_v", "bond")],
        ),
        (
            ("bear", "bull", "bear"),
            [("stage_ii", "bond"), ("stage_iv", "commodity"), ("stage_vi", "stock")],
        ),
    ],
)
def test_worker_lists_every_single_asset_difference_without_classifying(
    tmp_path: Path, states: tuple[str, ...], expected: list[tuple[str, str]]
) -> None:
    published = projection(tmp_path, states)
    overview = published.datasets["cycle_overview"]
    assert overview["current_stage"] is None
    basis = overview["noncanonical_basis"]
    assert [(row["stage"], row["asset"]) for row in basis["comparisons"]] == expected
    assert all(row["candidate_30d"] == "bear" for row in basis["comparisons"])
    assert all(row["candidate_state"] is None for row in basis["comparisons"])
    source = report_input_from_projection(published)
    assert source.results["noncanonical_basis"] == basis
    assert source.prompt_version == "report-prompt-v0006"
    assert "候选熊市 0 天" not in "".join(fact_sentences(basis))


def test_canonical_projection_does_not_add_noncanonical_reading(tmp_path: Path) -> None:
    published = projection(tmp_path, ("bull", "bull", "bull"))
    assert "noncanonical_basis" not in published.datasets["cycle_overview"]
    assert "ai_explanation" not in report_input_from_projection(published).deterministic_skeleton()


@pytest.mark.parametrize("ai_available", [True, False])
def test_new_report_and_home_show_reading_with_honest_source(
    tmp_path: Path, ai_available: bool
) -> None:
    published = projection(tmp_path, ("bull", "bear", "bull"))
    source = report_input_from_projection(published)
    repository = ReportRepository.create(tmp_path / "reports.sqlite3")
    first = FakeAdapter(
        "codex_cli",
        AdapterResponse.succeeded(document(source))
        if ai_available
        else AdapterResponse.unavailable("quota_exhausted"),
    )
    second = FakeAdapter("claude_code_cli", AdapterResponse.unavailable("quota_exhausted"))
    result = ReportService(repository, (first, second)).generate(source)
    assert result.status == ("completed" if ai_available else "completed_degraded")
    assert len(second.calls) == (0 if ai_available else 1)
    snapshot = repository.get(result.report_snapshot_id)
    assert snapshot.body["ai_explanation"][0]["title"] == TITLE
    home = _text(dashboard_page("/", published, (), (snapshot,)))
    assert TITLE in home
    assert ("AI 解读" if ai_available else "确定性模板") in home
    assert "与阶段 V只差债券一项" in home
    assert "暂无正式阶段" in home
    assert snapshot.current_stage is None
    # A report from another immutable projection must never appear on today's home.
    assert TITLE not in _text(
        dashboard_page(
            "/", published, (), (replace(snapshot, projection_set_id="other-projection"),)
        )
    )
    if not ai_available:
        assert "观察债券：" not in home
        reader = _text(dashboard_page("/reports", published, (), (snapshot,)))
        assert "确定性模板" in reader and "已验证结果" in reader


@pytest.mark.parametrize(
    "change",
    [
        "wrong_asset",
        "wrong_candidate",
        "wrong_days",
        "missing_section",
        "duplicate_section",
        "inclined_stage",
        "nearest_stage",
        "extra_false_fact",
        "no_observation",
        "negated_facts",
    ],
)
def test_invalid_reading_is_rejected_and_falls_back(tmp_path: Path, change: str) -> None:
    source = report_input_from_projection(projection(tmp_path, ("bull", "bear", "bull")))
    output = document(source)
    section = output["sections"][0]
    if change == "wrong_asset":
        section["explanation"] = section["explanation"].replace("只差商品", "只差股票")
    elif change == "wrong_candidate":
        section["explanation"] = section["explanation"].replace("候选方向：熊市", "候选方向：牛市")
    elif change == "wrong_days":
        section["explanation"] = section["explanation"].replace("要求 8 日", "要求 3 日")
    elif change == "missing_section":
        section["title"] = "通用解读"
    elif change == "duplicate_section":
        output["sections"].append(dict(section))
    elif change == "inclined_stage":
        section["explanation"] += "目前倾向处于阶段 III。"
    elif change == "nearest_stage":
        section["explanation"] += "最接近阶段 III。"
    elif change == "extra_false_fact":
        section["explanation"] += "股票候选已持续 9 日。"
    elif change == "negated_facts":
        section["explanation"] = "并非" + section["explanation"]
    elif change == "no_observation":
        section["explanation"] = "".join(fact_sentences(source.results["noncanonical_basis"]))
    repository = ReportRepository.create(tmp_path / "reports.sqlite3")
    result = ReportService(
        repository,
        (
            FakeAdapter("codex_cli", AdapterResponse.succeeded(output)),
            FakeAdapter("claude_code_cli", AdapterResponse.succeeded(output)),
        ),
    ).generate(source)
    assert result.status == "completed_degraded"
    assert all(
        attempt.process_audit.get("rejection")
        for attempt in repository.attempts(result.report_snapshot_id)
    )
    snapshot = repository.get(result.report_snapshot_id)
    assert snapshot.body["explanation_source"] == "deterministic_template"
    assert snapshot.body["ai_explanation"][0]["explanation"] == "".join(
        fact_sentences(source.results["noncanonical_basis"])
    )


@pytest.mark.parametrize("adapter", ["codex_cli", "claude_code_cli"])
def test_cli_prompt_contains_frozen_reading_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, adapter: str
) -> None:
    import json
    from types import SimpleNamespace

    source = report_input_from_projection(projection(tmp_path, ("bull", "bear", "bull")))

    def generate(name: str, prompt: str, schema: Any, **kwargs: Any) -> Any:
        data = json.loads(prompt)
        assert name == adapter
        assert data["execution_contract"]["prompt_version"] == "report-prompt-v0006"
        contract = data["noncanonical_reading_contract"]
        assert contract["title"] == TITLE
        assert len(contract["required_fact_sentences"]) == 5
        assert len(contract["observation_sentences"]) == 3
        return SimpleNamespace(
            document=document(source),
            error_classification=None,
            tool_events=0,
            audit={},
            version="fixture",
        )

    monkeypatch.setattr("pring_cycle.reports.run_structured_cli", generate)
    assert CliReportAdapter(adapter).generate(source).document == document(source)


def test_noncanonical_reading_preserves_not_applicable_confirmation(tmp_path: Path) -> None:
    original = report_input_from_projection(projection(tmp_path, ("bull", "bear", "bull")))
    source = replace(
        original,
        conclusions={
            "confirmation_applicable": False,
            "key_indicator:pmi": "not_applicable",
            "dimension:overheat": {
                "support": 0,
                "counterevidence": 0,
                "observation_only": 0,
                "unconfirmed": 0,
                "not_applicable": 1,
            },
        },
    )
    repository = ReportRepository.create(tmp_path / "reports.sqlite3")
    result = ReportService(
        repository, (FakeAdapter("codex_cli", AdapterResponse.succeeded(document(source))),)
    ).generate(source)
    assert result.status == "completed"
    snapshot = repository.get(result.report_snapshot_id)
    assert snapshot.schema_version == "report-schema-v0005"
    assert snapshot.prompt_version == "report-prompt-v0006"
    assert snapshot.body["conclusions"] == source.conclusions


def test_old_noncanonical_input_keeps_its_old_snapshot_and_contract(tmp_path: Path) -> None:
    source = report_input_from_projection(projection(tmp_path, ("bull", "bear", "bull")))
    old = ReportInput.create(
        projection_set_id="historical",
        target_business_date=source.target_business_date,
        report_cutoff=source.report_cutoff,
        system_as_of=source.system_as_of,
        model_version_id=source.model_version_id,
        trend_rule_version=source.trend_rule_version,
        current_stage=None,
        stage_reason=source.stage_reason,
        core_states=source.core_states,
        conclusions=source.conclusions,
        results={
            key: value for key, value in source.results.items() if key != "noncanonical_basis"
        },
    )
    repository = ReportRepository.create(tmp_path / "reports.sqlite3")
    service = ReportService(repository, ())
    historical = service.generate(old, client_request_id="old")
    before = repository.get(historical.report_snapshot_id)
    assert before.prompt_version == "report-prompt-v0004"
    assert "ai_explanation" not in before.body
    service.generate(source, client_request_id="new")
    assert repository.get(historical.report_snapshot_id).body == before.body
    assert service.generate(old, client_request_id="old") == historical


def test_extra_section_cannot_override_noncanonical_facts(tmp_path: Path) -> None:
    source = report_input_from_projection(projection(tmp_path, ("bull", "bear", "bull")))
    output = document(source)
    output["sections"].append(
        {"title": "总结", "explanation": "本轮正式阶段为 III。债券稳定状态为熊市。"}
    )
    repository = ReportRepository.create(tmp_path / "reports.sqlite3")
    result = ReportService(
        repository, (FakeAdapter("codex_cli", AdapterResponse.succeeded(output)),)
    ).generate(source)
    assert result.status == "completed_degraded"
    assert (
        repository.attempts(result.report_snapshot_id)[0].process_audit["rejection"][
            "section_index"
        ]
        == 1
    )


@pytest.mark.parametrize("pending", [False, True])
def test_noncanonical_section_requires_worker_basis(tmp_path: Path, pending: bool) -> None:
    published = projection(tmp_path, ("bull", "bull", "bull"))
    source = report_input_from_projection(published)
    if pending:
        source = replace(
            source,
            current_stage=None,
            stage_reason="core_data_pending",
            core_states={"bond": "bull", "stock": "bull", "commodity": "None"},
        )
    output = {
        "bundle_id": source.bundle_id,
        "current_stage": source.current_stage,
        "report_cutoff": source.report_cutoff.isoformat(),
        "core_states": source.core_states,
        "conclusions": source.conclusions,
        "proxy_used": False,
        "sections": [{"title": TITLE, "explanation": "三核心为非典型组合。"}],
    }
    repository = ReportRepository.create(tmp_path / "reports.sqlite3")
    result = ReportService(
        repository, (FakeAdapter("codex_cli", AdapterResponse.succeeded(output)),)
    ).generate(source)
    assert result.status == "completed_degraded"
    assert "ai_explanation" not in repository.get(result.report_snapshot_id).body
    (attempt,) = repository.attempts(result.report_snapshot_id)
    assert attempt.process_audit["rejection"]["check"] == "noncanonical_basis_missing"
