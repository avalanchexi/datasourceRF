from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, tzinfo
from pathlib import Path
from types import SimpleNamespace
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


def test_the_report_input_carries_the_facts_without_their_evidence_identifiers() -> None:
    claims = [f"{index:064x}" for index in range(40)]
    traced = {
        "inventory": {
            "registered_warrants": {
                "median_change_rate": 0.2,
                "observation_version_ids": claims,
                "symbols": [
                    {
                        "symbol": "CF",
                        "first": 400.0,
                        "last": 480.0,
                        "change_rate": 0.2,
                        "first_claim_ids": claims[:20],
                        "last_claim_ids": claims[20:],
                    }
                ],
            },
        },
        "core_assets": [
            {
                "metric_id": "CN_BOND_CORE_000012",
                "state": "bull",
                "selected_claim_ids": claims[:3],
                "readings": [{"period": "2026-08", "value": 1.5, "observation_id": "obs-1"}],
            }
        ],
        "policy_direction": {
            "value": "easing",
            "source": ["tushare"],
            "derived_observation_id": "derived-1",
            "evidence_snapshot_id": "snapshot-1",
        },
    }
    shown = {
        "inventory": {
            "registered_warrants": {
                "median_change_rate": 0.2,
                "symbols": [{"symbol": "CF", "first": 400.0, "last": 480.0, "change_rate": 0.2}],
            },
        },
        "core_assets": [
            {
                "metric_id": "CN_BOND_CORE_000012",
                "state": "bull",
                "readings": [{"period": "2026-08", "value": 1.5}],
            }
        ],
        "policy_direction": {"value": "easing", "source": ["tushare"]},
    }

    def create(results: dict[str, Any]) -> ReportInput:
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
            results=results,
        )

    # Tracing is the projection's job: the AI is given the facts, never what they rest on.
    assert create(traced).prompt_document() == create(shown).prompt_document()
    assert claims[0] not in json.dumps(create(traced).deterministic_skeleton())


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
            AdapterResponse.succeeded(
                valid_document(
                    sections=[{"title": "阶段", "explanation": "当前阶段为阶段III，商品转牛。"}]
                )
            ),
            "stage_mutation_rejected",
            id="stage-rewritten-in-text",
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


@pytest.mark.parametrize(
    ("explanation", "outcome"),
    [
        ("当前处于第三阶段，债券转弱。", "stage_mutation_rejected"),
        ("目前阶段为第四阶段。", "stage_mutation_rejected"),
        ("当前处于第二阶段，债券与股票同为牛市。", "succeeded"),
    ],
)
def test_a_stage_stated_by_its_chinese_name_is_checked_like_its_numeral(
    tmp_path: Path, explanation: str, outcome: str
) -> None:
    reports = ReportRepository.create(tmp_path / "reports.sqlite3")
    document = valid_document(sections=[{"title": "阶段", "explanation": explanation}])
    codex = FakeAdapter("codex_cli", AdapterResponse.succeeded(document))

    result = ReportService(reports, (codex,)).generate(bundle())

    assert [item.outcome for item in reports.attempts(result.report_snapshot_id)] == [outcome]


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
    monkeypatch.setattr("pring_cycle.cli_process.shutil.which", lambda _name: "/bin/codex")

    def fail_to_start(*_args: object, **_kwargs: object) -> None:
        raise OSError("fixture process launch failure")

    monkeypatch.setattr("pring_cycle.cli_process.subprocess.Popen", fail_to_start)

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


def test_report_input_names_its_stages_metrics_and_sources_in_chinese(tmp_path: Path) -> None:
    """Machine fields stay for validation; the AI is also given each code's Chinese name."""
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
    P0ProjectionService(projections).publish(
        target_business_date="2026-08-28",
        system_as_of=datetime(2026, 8, 28, 13, tzinfo=UTC),
        assets=assets,  # type: ignore[arg-type]
        last_confirmed_stage=None,
        macro_document={
            "overheat": {
                "state": "fixture_activity",
                "evidence": [{"metric_id": "CN_INDUSTRIAL_VA", "status": "missing"}],
            },
            "overheat_state": "fixture_activity",
        },
    )

    report_input = report_input_from_projection(projections.current())
    prompt = report_input.prompt_document()

    assert report_input.current_stage == "stage_ii"
    assert report_input.results["core_assets"][0]["source"] == "tushare:index_daily"
    assert report_input.results["overheat_state"]["anomaly"] == ["gap:CN_INDUSTRIAL_VA"]
    assert prompt["display_names"] == {
        "stages": {"stage_ii": "第二阶段"},
        "metrics": {
            "CN_BOND_CORE_000012": "上证国债指数",
            "CN_COMMODITY_CORE_NHII": "南华工业品指数",
            "CN_EQUITY_CORE_000985": "中证全指",
            "CN_INDUSTRIAL_VA": "工业增加值",
        },
        "sources": {"tushare:fut_index_daily": "TuShare", "tushare:index_daily": "TuShare"},
    }


def test_cli_prompt_asks_for_the_chinese_names_of_the_codes_it_carries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = ReportInput.create(
        projection_set_id="projection-1",
        target_business_date="2026-08-28",
        report_cutoff=datetime(2026, 8, 28, 10, tzinfo=UTC),
        system_as_of=datetime(2026, 8, 28, 9, 59, tzinfo=UTC),
        model_version_id="model-v0001",
        trend_rule_version="trend-v0001",
        current_stage="stage_iii",
        stage_reason="canonical_combination",
        core_states={"bond": "bear", "stock": "bull", "commodity": "bull"},
        conclusions=CONCLUSIONS,
        results={
            "core_assets": [
                {
                    "asset": "stock",
                    "value": "bull",
                    "metric_id": "CN_EQUITY_CORE_000985",
                    "source": "tushare:index_daily",
                }
            ]
        },
    )
    prompts: list[dict[str, Any]] = []

    def run(name: str, prompt: str, schema: Any, **kwargs: Any) -> Any:
        prompts.append(json.loads(prompt))
        return SimpleNamespace(
            document=None, classification="fixture", audit={}, version="fixture", tool_events=0
        )

    monkeypatch.setattr("pring_cycle.reports.run_structured_cli", run)
    CliReportAdapter("codex_cli").generate(source)

    [prompt] = prompts
    assert prompt["report_input"]["results"]["core_assets"][0]["source"] == "tushare:index_daily"
    assert prompt["report_input"]["display_names"] == {
        "stages": {"stage_iii": "第三阶段"},
        "metrics": {"CN_EQUITY_CORE_000985": "中证全指"},
        "sources": {"tushare:index_daily": "TuShare"},
    }
    assert "display_names" in prompt["instruction"]
    assert "不写原始代号" in prompt["instruction"]
    assert prompt["execution_contract"]["prompt_version"] == "report-prompt-v0008"


def test_report_with_untranslated_codes_is_kept_and_marked(tmp_path: Path) -> None:
    source = ReportInput.create(
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
        results={
            "core_assets": [
                {
                    "asset": "stock",
                    "value": "bull",
                    "metric_id": "CN_EQUITY_CORE_000985",
                    "source": "tushare:index_daily",
                }
            ]
        },
    )

    def report(explanation: str) -> dict[str, Any]:
        reports = ReportRepository.create(tmp_path / f"{len(explanation)}.sqlite3")
        document = {
            **valid_document(),
            "bundle_id": source.bundle_id,
            "sections": [{"title": "三核心", "explanation": explanation}],
        }
        codex = FakeAdapter("codex_cli", AdapterResponse.succeeded(document))
        result = ReportService(reports, (codex,)).generate(source)
        assert (result.status, result.adapter) == ("completed", "codex_cli")
        return reports.get(result.report_snapshot_id).body

    coded = report("沿 stage_ii 解读，中证全指走强（来源：tushare:index_daily）。")
    named = report("沿第二阶段解读，中证全指走强（来源：TuShare）。")

    assert coded["ai_explanation"][0]["explanation"].startswith("沿 stage_ii")
    assert coded["untranslated_codes"] == ["stage_ii", "tushare:index_daily"]
    assert "untranslated_codes" not in named


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


@pytest.mark.parametrize("adapter_name", ["codex_cli", "claude_code_cli"])
def test_rejected_noncanonical_output_is_retained_with_first_difference(
    tmp_path: Path, adapter_name: str
) -> None:
    from dataclasses import replace
    from hashlib import sha256

    source = replace(
        bundle(),
        current_stage=None,
        stage_reason="noncanonical_combination",
        core_states={"bond": "bull", "stock": "bear", "commodity": "bull"},
    )
    document = valid_document(
        current_stage=None,
        core_states=source.core_states,
        conclusions={**source.conclusions, "credit_response": "changed"},
    )
    reports = ReportRepository.create(tmp_path / "reports.sqlite3")
    result = ReportService(
        reports, (FakeAdapter(adapter_name, AdapterResponse.succeeded(document)),)
    ).generate(source)
    assert result.status == "completed_degraded"
    (attempt,) = reports.attempts(result.report_snapshot_id)
    assert attempt.outcome == "conclusion_mutation_rejected"
    assert attempt.process_audit["rejection"] == {
        "check": "conclusions",
        "path": "conclusions.credit_response",
    }
    digest = attempt.output_hash
    assert digest is not None
    content = (tmp_path / "artifacts" / "sha256" / digest[:2] / digest).read_bytes()
    assert sha256(content).hexdigest() == digest
    assert json.loads(content) == document
    assert "ai_explanation" not in reports.get(result.report_snapshot_id).body


def test_rejection_points_to_section_and_success_has_no_rejection(tmp_path: Path) -> None:
    reports = ReportRepository.create(tmp_path / "reports.sqlite3")
    bad = valid_document(sections=[{"title": "错误阶段", "explanation": "当前阶段为 IV。"}])
    result = ReportService(
        reports,
        (
            FakeAdapter("codex_cli", AdapterResponse.succeeded(bad)),
            FakeAdapter("claude_code_cli", AdapterResponse.succeeded(valid_document())),
        ),
    ).generate(bundle())
    first, second = reports.attempts(result.report_snapshot_id)
    assert first.process_audit["rejection"] == {
        "check": "stated_stage",
        "path": "sections[0]",
        "section_index": 0,
        "section_title": "错误阶段",
    }
    assert "rejection" not in second.process_audit
    assert result.status == "completed"
    assert result.adapter == "claude_code_cli"


def test_output_storage_failure_does_not_suppress_cli_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reports = ReportRepository.create(tmp_path / "reports.sqlite3")

    def fail(*args: Any) -> str:
        raise OSError("fixture disk unavailable")

    monkeypatch.setattr(reports, "save_output", fail)
    result = ReportService(
        reports,
        (
            FakeAdapter(
                "codex_cli", AdapterResponse.succeeded(valid_document(current_stage="stage_i"))
            ),
            FakeAdapter("claude_code_cli", AdapterResponse.succeeded(valid_document())),
        ),
    ).generate(bundle())
    assert result.status == "completed"
    first, second = reports.attempts(result.report_snapshot_id)
    assert first.outcome == "stage_mutation_rejected"
    assert first.process_audit["rejection"]["check"] == "current_stage"
    assert second.outcome == "succeeded"
    assert all(
        attempt.process_audit["output_retention"]
        == {
            "status": "failed",
            "error_type": "OSError",
        }
        for attempt in (first, second)
    )
