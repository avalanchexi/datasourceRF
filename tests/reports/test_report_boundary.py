from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, tzinfo
from pathlib import Path
from typing import Any, Self

import pytest

from pring_cycle.domain import CoreAssetState
from pring_cycle.p0 import CoreAssetReadiness, P0ProjectionService
from pring_cycle.projections import ProjectionEnvelope, ProjectionSet, ProjectionSetRepository
from pring_cycle.reports import (
    AdapterResponse,
    CliReportAdapter,
    ReportInput,
    ReportRepository,
    ReportService,
    report_input_from_projection,
)


@dataclass
class FakeAdapter:
    name: str
    response: AdapterResponse
    calls: list[str] = field(default_factory=list)
    version: str = "fixture-cli-1"

    def generate(self, bundle: ReportInput) -> AdapterResponse:
        self.calls.append(bundle.bundle_id)
        return self.response


CONCLUSIONS = {
    "policy_direction": "easing",
    "credit_response": "expanding",
    "overheat_state": "insufficient_data",
    "price_pressure": "producer_diffusion",
    "inventory_quadrant": None,
}


def bundle() -> ReportInput:
    return ReportInput.create(
        projection_set_id="projection-1",
        target_business_date="2026-08-28",
        report_cutoff=datetime(2026, 8, 28, 10, tzinfo=UTC),
        system_as_of=datetime(2026, 8, 28, 9, 59, tzinfo=UTC),
        model_version_id="model-v0001",
        trend_rule_version="trend-v0001",
        current_stage="stage_ii",
        stage_reason="canonical_combination",
        core_states={"bond": "bull", "stock": "bull", "commodity": "bear"},
        conclusions=CONCLUSIONS,
        results={"policy_direction": {"value": "easing", "source": ["tushare"], "anomaly": []}},
    )


def valid_document(**changes: Any) -> dict[str, Any]:
    source = bundle()
    return {
        "bundle_id": source.bundle_id,
        "current_stage": "stage_ii",
        "report_cutoff": "2026-08-28T10:00:00+00:00",
        "core_states": {"bond": "bull", "stock": "bull", "commodity": "bear"},
        "conclusions": dict(CONCLUSIONS),
        "sections": [
            {
                "title": "政策传导",
                "explanation": "政策方向偏宽松（来源：TuShare），但不参与正式阶段分类。",
            }
        ],
        "proxy_used": False,
        **changes,
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


def test_clock_rollback_retains_timeout_audit_and_measured_duration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reports = ReportRepository.create(tmp_path / "reports.sqlite3")
    source = bundle()
    started = datetime(2026, 9, 9, 10, tzinfo=UTC)
    wall_now = started
    monotonic_ns = 7_000_000_000

    class WallClock(datetime):
        @classmethod
        def now(cls, tz: tzinfo | None = None) -> Self:
            return cls.fromtimestamp(wall_now.timestamp(), tz)

    class TimedOutTransport:
        name = "codex_cli"
        version = "fixture-timeout"

        def generate(self, evidence: ReportInput) -> AdapterResponse:
            nonlocal wall_now, monotonic_ns
            assert evidence.document() == source.document()
            wall_now = started - timedelta(minutes=1)
            monotonic_ns = 9_500_000_000
            return AdapterResponse("unavailable", None, "timed_out", 0, {"stdout_bytes": 7})

    monkeypatch.setattr("pring_cycle.reports.datetime", WallClock)
    monkeypatch.setattr("pring_cycle.reports.time.monotonic_ns", lambda: monotonic_ns)
    result = ReportService(reports, (TimedOutTransport(),)).generate(
        source, client_request_id="clock-rollback"
    )

    assert result.status == "completed_degraded"
    (attempt,) = reports.attempts(result.report_snapshot_id)
    assert attempt.outcome == "timed_out"
    assert attempt.started_at == started
    assert attempt.completed_at == datetime(2026, 9, 9, 9, 59, tzinfo=UTC)
    assert attempt.duration_ms == 2500
    assert attempt.process_audit["stdout_bytes"] == 7
    assert attempt.process_audit["timing"]["clock_went_backwards"] is True
    snapshot = reports.get(result.report_snapshot_id)
    assert snapshot.duration_ms == 2500
    assert snapshot.report_cutoff == source.report_cutoff
    assert snapshot.system_as_of == source.system_as_of
    assert snapshot.current_stage == "stage_ii"
    assert "ai_explanation" not in snapshot.body
    requested = reports.by_client_request("clock-rollback")
    assert requested is not None and requested.duration_ms == 2500
    assert reports.history()[0].duration_ms == 2500


def test_fallback_report_duration_spans_both_attempts_across_clock_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reports = ReportRepository.create(tmp_path / "reports.sqlite3")
    source = bundle()
    wall_now = datetime(2026, 9, 9, 10, tzinfo=UTC)
    monotonic_ns = 7_000_000_000

    class WallClock(datetime):
        @classmethod
        def now(cls, tz: tzinfo | None = None) -> Self:
            return cls.fromtimestamp(wall_now.timestamp(), tz)

    class ClockChangingTransport:
        version = "fixture-clock-change"

        def __init__(self, name: str) -> None:
            self.name = name

        def generate(self, evidence: ReportInput) -> AdapterResponse:
            nonlocal wall_now, monotonic_ns
            assert evidence.document() == source.document()
            if self.name == "codex_cli":
                wall_now = datetime(2026, 9, 9, 9, 59, tzinfo=UTC)
                monotonic_ns = 9_500_000_000
                return AdapterResponse.unavailable("timed_out")
            wall_now = datetime(2026, 9, 9, 11, tzinfo=UTC)
            monotonic_ns = 11_000_000_000
            return AdapterResponse.succeeded(valid_document())

    monkeypatch.setattr("pring_cycle.reports.datetime", WallClock)
    monkeypatch.setattr("pring_cycle.reports.time.monotonic_ns", lambda: monotonic_ns)
    service = ReportService(
        reports,
        (
            ClockChangingTransport("codex_cli"),
            ClockChangingTransport("claude_code_cli"),
        ),
    )
    result = service.generate(source, client_request_id="clock-fallback")
    assert result.status == "completed"
    assert result.adapter == "claude_code_cli"
    first, second = reports.attempts(result.report_snapshot_id)
    assert [first.duration_ms, second.duration_ms] == [2500, 1500]
    assert first.completed_at == second.started_at == datetime(2026, 9, 9, 9, 59, tzinfo=UTC)
    assert second.completed_at == datetime(2026, 9, 9, 11, tzinfo=UTC)
    assert first.process_audit["timing"]["clock_went_backwards"] is True
    assert second.process_audit["timing"]["clock_went_backwards"] is False
    assert reports.get(result.report_snapshot_id).duration_ms == 4000
    assert service.generate(source, client_request_id="clock-fallback") == result
    assert len(reports.attempts(result.report_snapshot_id)) == 2


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


@pytest.mark.parametrize(
    ("response", "outcome"),
    [
        pytest.param(
            AdapterResponse.succeeded(
                valid_document(core_states={"bond": "bear", "stock": "bull", "commodity": "bear"})
            ),
            "conclusion_mutation_rejected",
            id="core-state-rewritten",
        ),
        pytest.param(
            AdapterResponse.succeeded(
                valid_document(conclusions={**CONCLUSIONS, "inventory_quadrant": "主动补库存"})
            ),
            "conclusion_mutation_rejected",
            id="inventory-rewritten",
        ),
        pytest.param(
            AdapterResponse.succeeded(
                valid_document(
                    sections=[{"title": "引用", "explanation": "见证据。", "evidence_ids": []}]
                )
            ),
            "schema_validation_failed",
            id="evidence-reference-field",
        ),
        pytest.param(
            AdapterResponse.succeeded(valid_document(), tool_events=1),
            "tool_use_rejected",
            id="tool-event",
        ),
        pytest.param(
            AdapterResponse.succeeded(
                valid_document(
                    sections=[{"title": "建议", "explanation": "建议买入并设置目标价。"}]
                )
            ),
            "forbidden_content_rejected",
            id="trading-advice",
        ),
    ],
)
def test_rewritten_conclusions_structure_tools_and_advice_are_rejected(
    tmp_path: Path, response: AdapterResponse, outcome: str
) -> None:
    reports = ReportRepository.create(tmp_path / "reports.sqlite3")
    first = FakeAdapter("codex_cli", response)
    second = FakeAdapter("claude_code_cli", AdapterResponse.unavailable("fixture"))

    result = ReportService(reports, (first, second)).generate(bundle())

    assert result.status == "completed_degraded"
    assert result.adapter == "deterministic"
    assert reports.attempts(result.report_snapshot_id)[0].outcome == outcome


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
    assert stored.body["conclusions"] == CONCLUSIONS
    assert not {"support", "counterevidence", "governance_gaps", "evidence_references"} & set(
        stored.body
    )
    assert len(reports.attempts(result.report_snapshot_id)) == 2


def test_noncanonical_projection_generates_a_report_without_inventing_a_stage(
    tmp_path: Path,
) -> None:
    projections = ProjectionSetRepository.create(tmp_path / "projections.sqlite3")
    assets = tuple(
        CoreAssetReadiness(
            asset=asset,
            metric_id=metric_id,
            state=state,
            reason="validated",
            observation_count=120,
            latest_business_date="2026-08-28",
            observation_version_ids=(f"version-{asset}",),
        )
        for asset, metric_id, state in (
            ("bond", "CN_BOND_CORE_000012", CoreAssetState.BULL),
            ("stock", "CN_EQUITY_CORE_000985", CoreAssetState.BEAR),
            ("commodity", "CN_COMMODITY_CORE_NHII", CoreAssetState.BULL),
        )
    )
    result = P0ProjectionService(projections).publish(
        target_business_date="2026-08-28",
        system_as_of=datetime(2026, 8, 28, 13, tzinfo=UTC),
        assets=assets,  # type: ignore[arg-type]
        last_confirmed_stage=None,
    )
    assert result.status == "published"
    source = report_input_from_projection(projections.current())
    reports = ReportRepository.create(tmp_path / "reports.sqlite3")
    generated = ReportService(reports, ()).generate(source)
    stored = reports.get(generated.report_snapshot_id)
    assert stored.current_stage is None
    assert stored.body["formal_stage_basis"]["current_stage"] is None
    assert stored.body["formal_stage_basis"]["stage_reason"] == "noncanonical_combination"
    assert stored.body["core_states"] == {"bond": "bull", "stock": "bear", "commodity": "bull"}


def test_cli_process_start_failure_is_classified_as_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("pring_cycle.reports.shutil.which", lambda _name: "/bin/codex")

    def fail_to_start(*_args: object, **_kwargs: object) -> None:
        raise OSError("fixture process launch failure")

    monkeypatch.setattr("pring_cycle.reports.subprocess.Popen", fail_to_start)

    response = CliReportAdapter("codex_cli").generate(bundle())

    assert response.status == "unavailable"
    assert response.error_classification == "process_start_failed"
    assert response.process_audit["exit_code"] is None


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


@pytest.mark.parametrize("activity_provider", [None, "tushare", "国家统计局"])
def test_report_input_carries_results_and_sources_without_evidence_identifiers(
    tmp_path: Path,
    activity_provider: str | None,
) -> None:
    projections = ProjectionSetRepository.create(tmp_path / "projections.sqlite3")
    assets = tuple(
        CoreAssetReadiness(
            asset=asset,
            metric_id=metric_id,
            state=state,
            reason="validated",
            observation_count=120,
            latest_business_date="2026-08-28",
            observation_version_ids=(f"version-{asset}",),
        )
        for asset, metric_id, state in (
            ("bond", "CN_BOND_CORE_000012", CoreAssetState.BULL),
            ("stock", "CN_EQUITY_CORE_000985", CoreAssetState.BULL),
            ("commodity", "CN_COMMODITY_CORE_NHII", CoreAssetState.BEAR),
        )
    )
    activity = (
        {
            "state": "fixture_activity",
            "evidence": [
                {
                    "metric_id": "CN_PMI_ACTIVITY",
                    "status": "current",
                    "observation_version_ids": ["version-pmi"],
                    "claims": [{"provider": activity_provider, "selected": True}],
                },
                {"metric_id": "CN_INDUSTRIAL_VA", "status": "missing", "claims": []},
            ],
        }
        if activity_provider is not None
        else None
    )
    P0ProjectionService(projections).publish(
        target_business_date="2026-08-28",
        system_as_of=datetime(2026, 8, 28, 13, tzinfo=UTC),
        assets=assets,  # type: ignore[arg-type]
        last_confirmed_stage=None,
        macro_document={"overheat": activity, "overheat_state": "fixture_activity"}
        if activity
        else None,
    )

    report_input = report_input_from_projection(projections.current())
    text = json.dumps(report_input.document(), ensure_ascii=False)

    assert "version-" not in text
    assert "evidence" not in text
    assert [item["value"] for item in report_input.results["core_assets"]] == [
        "bull",
        "bull",
        "bear",
    ]
    assert report_input.results["core_assets"][0]["source"] == "tushare:index_daily"
    if activity:
        assert report_input.conclusions["overheat_state"] == "fixture_activity"
        assert report_input.results["overheat_state"] == {
            "value": "fixture_activity",
            "source": [activity_provider],
            "anomaly": ["gap:CN_INDUSTRIAL_VA"],
        }


def test_real_run_report_input_is_a_fraction_of_the_first_evidence_bundle() -> None:
    """The first real run's projection (2026-09-23) gave a 139,770-byte evidence bundle."""
    sample = json.loads(
        (Path(__file__).parents[1] / "fixtures/report_input/projection-20260923.json").read_text()
    )
    envelope = sample["envelope"]
    projection = ProjectionSet(
        ProjectionEnvelope(
            **{
                **envelope,
                "system_as_of": datetime.fromisoformat(envelope["system_as_of"]),
                "generated_at": datetime.fromisoformat(envelope["generated_at"]),
                "warnings": tuple(envelope["warnings"]),
            }
        ),
        sample["datasets"],
    )

    report_input = report_input_from_projection(projection)
    prompt = json.dumps(report_input.prompt_document(), ensure_ascii=False)

    assert len(prompt.encode()) < 139_770 // 10
    assert not re.search(r"[0-9a-f]{64}", prompt)
    assert report_input.current_stage is None
    assert report_input.results["formal_stage"]["reason"] == "noncanonical_combination"
    assert report_input.results["gap_summary"]["counts"]["missing"] >= 1
    assert report_input.gap_list == sample["datasets"]["cycle_overview"]["gap_list"]


def test_report_rejects_projection_that_exposes_preheat_history(tmp_path: Path) -> None:
    projections = ProjectionSetRepository.create(tmp_path / "projections.sqlite3")
    assets = tuple(
        CoreAssetReadiness(
            asset=asset,
            metric_id=metric_id,
            state=state,
            reason="validated",
            observation_count=121,
            latest_business_date="2026-08-28",
            observation_version_ids=tuple(f"version-{asset}-{index}" for index in range(121)),
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

    with pytest.raises(ValueError, match="report_evidence_window_exceeds_120_days"):
        report_input_from_projection(projections.current())


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


def test_a_snapshot_from_before_the_report_input_still_reads_and_renders(tmp_path: Path) -> None:
    from pring_cycle.dashboard import _report_reader
    from pring_cycle.storage import database_connection

    reports = ReportRepository.create(tmp_path / "reports.sqlite3")
    legacy_bundle = {
        "bundle_id": "bundle-legacy",
        "projection_set_id": "projection-legacy",
        "target_business_date": "2026-09-23",
        "report_cutoff": "2026-09-23T19:58:56+00:00",
        "system_as_of": "2026-09-23T19:58:56+00:00",
        "current_stage": None,
        "stage_reason": "noncanonical_combination",
        "core_states": {"bond": "bull", "stock": "bear", "commodity": "bull"},
        "allowed_evidence_ids": ["obs-bond"],
        "allowed_governance_refs": ["ADR-0003"],
        "support": ["三核心资产价格状态通过 P0 门禁。"],
        "counterevidence": [],
        "governance_gaps": [],
        "structured_context": {},
        "schema_version": "report-schema-v0003",
        "prompt_version": "report-prompt-v0003",
    }
    body = {
        "core_states": legacy_bundle["core_states"],
        "support": legacy_bundle["support"],
        "evidence_references": ["obs-bond"],
        "gap_list": [],
        "ai_explanation": [
            {
                "title": "阶段依据",
                "explanation": "组合不在六阶段内。",
                "evidence_ids": ["obs-bond"],
                "governance_refs": ["ADR-0003"],
            }
        ],
    }
    with database_connection(reports._database_path) as connection:
        connection.execute(
            "INSERT INTO evidence_bundle VALUES (?, 'hash', 'projection-legacy', ?, ?)",
            ("bundle-legacy", json.dumps(legacy_bundle), "2026-09-23T20:00:00+00:00"),
        )
        connection.execute(
            "INSERT INTO report_snapshot(report_snapshot_id, client_request_id, "
            "projection_set_id, target_business_date, version, status, adapter, current_stage, "
            "bundle_id, bundle_hash, model_version_id, schema_version, prompt_version, "
            "body_json, body_retained, created_at) VALUES ('report-legacy', 'legacy', "
            "'projection-legacy', '2026-09-23', 1, 'completed', 'codex_cli', NULL, "
            "'bundle-legacy', 'hash', 'model-v0012', 'report-schema-v0003', "
            "'report-prompt-v0003', ?, 1, '2026-09-23T20:00:00+00:00')",
            (json.dumps(body, ensure_ascii=False),),
        )

    snapshot = reports.get("report-legacy")
    page = str(_report_reader(snapshot))

    assert (snapshot.input_schema_version, snapshot.input_prompt_version) == (
        "report-schema-v0003",
        "report-prompt-v0003",
    )
    assert "组合不在六阶段内。" in page
    assert "证据 obs-bond" in page
