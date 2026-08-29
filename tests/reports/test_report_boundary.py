from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.domain import CoreAssetState
from pring_cycle.p0 import CoreAssetReadiness, P0ProjectionService
from pring_cycle.projections import ProjectionSetRepository
from pring_cycle.reports import (
    AdapterResponse,
    CliReportAdapter,
    EvidenceBundle,
    ReportRepository,
    ReportService,
    evidence_bundle_from_projection,
)


@dataclass
class FakeAdapter:
    name: str
    response: AdapterResponse
    calls: list[str] = field(default_factory=list)
    version: str = "fixture-cli-1"

    def generate(self, bundle: EvidenceBundle) -> AdapterResponse:
        self.calls.append(bundle.bundle_id)
        return self.response


def bundle() -> EvidenceBundle:
    return EvidenceBundle.create(
        projection_set_id="projection-1",
        target_business_date="2026-08-28",
        report_cutoff=datetime(2026, 8, 28, 10, tzinfo=UTC),
        system_as_of=datetime(2026, 8, 28, 9, 59, tzinfo=UTC),
        model_version_id="model-v0001",
        trend_rule_version="trend-v0001",
        current_stage="stage_ii",
        core_states={"bond": "bull", "stock": "bull", "commodity": "bear"},
        allowed_evidence_ids=("obs-bond", "obs-stock", "obs-commodity", "obs-policy"),
        allowed_governance_refs=("gap-vix",),
        support=("obs-policy",),
        counterevidence=(),
        governance_gaps=("gap-vix",),
    )


def valid_document(evidence_id: str = "obs-policy") -> dict[str, Any]:
    source = bundle()
    return {
        "bundle_id": source.bundle_id,
        "current_stage": "stage_ii",
        "report_cutoff": "2026-08-28T10:00:00+00:00",
        "sections": [
            {
                "title": "政策传导",
                "explanation": "政策证据支持当前叙事，但不参与正式阶段分类。",
                "evidence_ids": [evidence_id],
                "governance_refs": [],
            }
        ],
        "proxy_used": False,
    }


def test_valid_primary_cli_writes_an_immutable_report_snapshot(tmp_path: Path) -> None:
    reports = ReportRepository.create(tmp_path / "reports.sqlite3")
    codex = FakeAdapter("codex_cli", AdapterResponse.succeeded(valid_document()))
    claude = FakeAdapter("claude_code_cli", AdapterResponse.unavailable("not_needed"))

    result = ReportService(reports, (codex, claude)).generate(bundle())

    assert result.status == "completed"
    assert result.adapter == "codex_cli"
    assert len(codex.calls) == 1
    assert claude.calls == []
    stored = reports.get(result.report_snapshot_id)
    assert stored.projection_set_id == "projection-1"
    assert stored.current_stage == "stage_ii"
    assert stored.body_retained is True


def test_stage_mutation_is_rejected_and_alternate_cli_is_tried_once(tmp_path: Path) -> None:
    reports = ReportRepository.create(tmp_path / "reports.sqlite3")
    mutated = valid_document()
    mutated["current_stage"] = "stage_vi"
    codex = FakeAdapter("codex_cli", AdapterResponse.succeeded(mutated))
    claude = FakeAdapter("claude_code_cli", AdapterResponse.succeeded(valid_document()))

    result = ReportService(reports, (codex, claude)).generate(bundle())

    assert result.status == "completed"
    assert result.adapter == "claude_code_cli"
    assert codex.calls == [bundle().bundle_id]
    assert claude.calls == [bundle().bundle_id]
    attempts = reports.attempts(result.report_snapshot_id)
    assert [item.outcome for item in attempts] == [
        "stage_mutation_rejected",
        "succeeded",
    ]
    assert reports.get(result.report_snapshot_id).current_stage == "stage_ii"


def test_illegal_reference_tool_event_and_trading_advice_are_rejected(tmp_path: Path) -> None:
    for response in (
        AdapterResponse.succeeded(valid_document("outside-bundle")),
        AdapterResponse.succeeded(valid_document(), tool_events=1),
        AdapterResponse.succeeded(
            {
                **valid_document(),
                "sections": [
                    {
                        "title": "建议",
                        "explanation": "建议买入并设置目标价。",
                        "evidence_ids": ["obs-policy"],
                        "governance_refs": [],
                    }
                ],
            }
        ),
    ):
        reports = ReportRepository.create(tmp_path / f"reports-{id(response)}.sqlite3")
        first = FakeAdapter("codex_cli", response)
        second = FakeAdapter("claude_code_cli", AdapterResponse.unavailable("fixture"))

        result = ReportService(reports, (first, second)).generate(bundle())

        assert result.status == "completed_degraded"
        assert result.adapter == "deterministic"


def test_two_cli_failures_publish_a_deterministic_fact_skeleton(tmp_path: Path) -> None:
    reports = ReportRepository.create(tmp_path / "reports.sqlite3")
    codex = FakeAdapter("codex_cli", AdapterResponse.unavailable("cli_not_authenticated"))
    claude = FakeAdapter("claude_code_cli", AdapterResponse.unavailable("cli_not_installed"))

    result = ReportService(reports, (codex, claude)).generate(bundle())

    assert result.status == "completed_degraded"
    assert result.adapter == "deterministic"
    assert len(codex.calls) == len(claude.calls) == 1
    stored = reports.get(result.report_snapshot_id)
    assert stored.body["formal_stage_basis"]["current_stage"] == "stage_ii"
    assert stored.body["core_states"] == {
        "bond": "bull",
        "stock": "bull",
        "commodity": "bear",
    }
    assert len(reports.attempts(result.report_snapshot_id)) == 2


def test_cli_process_start_failure_is_classified_as_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("pring_cycle.reports.shutil.which", lambda _name: "/bin/codex")

    def fail_to_start(*_args: object, **_kwargs: object) -> None:
        raise OSError("fixture process launch failure")

    monkeypatch.setattr("pring_cycle.reports.subprocess.Popen", fail_to_start)

    response = CliReportAdapter("codex_cli").generate(bundle())

    assert response == AdapterResponse.unavailable("process_start_failed")


def test_same_day_regeneration_creates_versions_without_overwriting(tmp_path: Path) -> None:
    reports = ReportRepository.create(tmp_path / "reports.sqlite3")
    adapter = FakeAdapter("codex_cli", AdapterResponse.succeeded(valid_document()))
    service = ReportService(reports, (adapter,))

    first = service.generate(bundle(), client_request_id="report-1")
    duplicate = service.generate(bundle(), client_request_id="report-1")
    second = service.generate(bundle(), client_request_id="report-2")

    assert duplicate.report_snapshot_id == first.report_snapshot_id
    assert second.report_snapshot_id != first.report_snapshot_id
    assert [item.version for item in reports.history()] == [2, 1]


def test_projection_observation_versions_are_preserved_in_the_report_bundle(
    tmp_path: Path,
) -> None:
    projections = ProjectionSetRepository.create(tmp_path / "projections.sqlite3")
    assets = tuple(
        CoreAssetReadiness(
            asset=asset,
            metric_id=metric_id,
            state=state,
            reason="validated",
            observation_count=160,
            latest_business_date="2026-08-28",
            observation_version_ids=(f"version-{asset}",),
        )
        for asset, metric_id, state in (
            ("bond", "CN_BOND_CORE_000012", CoreAssetState.BULL),
            ("stock", "CN_EQUITY_CORE_000985", CoreAssetState.BULL),
            ("commodity", "CN_COMMODITY_CORE_NHII", CoreAssetState.BEAR),
        )
    )
    P0ProjectionService(projections).publish(
        target_business_date="2026-08-28",
        system_as_of=datetime(2026, 8, 28, 13, tzinfo=UTC),
        assets=assets,  # type: ignore[arg-type]
        last_confirmed_stage=None,
    )

    report_bundle = evidence_bundle_from_projection(projections.current())
    evidence_ids = report_bundle.allowed_evidence_ids

    assert evidence_ids == ("version-bond", "version-commodity", "version-stock")
    assert set(report_bundle.structured_context) == {
        "transition_watch",
        "macro_confirmation",
        "policy_context",
        "inventory_context",
        "price_context",
        "change_reasons",
    }


def test_cancellation_after_an_adapter_returns_prevents_report_publication(
    tmp_path: Path,
) -> None:
    reports = ReportRepository.create(tmp_path / "reports.sqlite3")
    adapter = FakeAdapter("codex_cli", AdapterResponse.succeeded(valid_document()))
    cancellation_checks = 0

    def cancel_after_adapter() -> bool:
        nonlocal cancellation_checks
        cancellation_checks += 1
        return cancellation_checks >= 3

    with pytest.raises(ValueError, match="report_generation_cancelled"):
        ReportService(reports, (adapter,)).generate(
            bundle(),
            cancel_requested=cancel_after_adapter,
        )

    assert adapter.calls == [bundle().bundle_id]
    assert reports.history() == ()
