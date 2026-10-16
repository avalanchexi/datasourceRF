"""The two fact lines under the conclusion board: the reading and the run that produced it."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from dash.development.base_component import Component

from pring_cycle.dashboard import dashboard_page
from pring_cycle.projections import ProjectionSet
from pring_cycle.reports import (
    AdapterResponse,
    ReportRepository,
    ReportService,
    ReportSnapshot,
    report_input_from_projection,
)
from pring_cycle.run_health import ProducerRun
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths
from tests.integration.test_core_carry_forward import seed_cores
from tests.integration.test_day_summary import target_projection
from tests.integration.test_worker_execution import runtime
from tests.reports.test_report_boundary import FakeAdapter
from tests.web.test_dashboard_contract import _hrefs, _text

CUTOFF = datetime(2026, 8, 28, 13, tzinfo=UTC)


@pytest.fixture(scope="module")
def published(tmp_path_factory: pytest.TempPathFactory) -> tuple[RuntimePaths, ProjectionSet]:
    paths = runtime(tmp_path_factory.mktemp("board-footer"))
    seed_cores(paths)
    return paths, target_projection(paths)


def _section(component: object, identity: str) -> Component:
    if isinstance(component, (list, tuple)):
        found = [_section(child, identity) for child in component]
        return next(item for item in found if item is not None)
    if isinstance(component, Component):
        if getattr(component, "id", None) == identity:
            return component
        children = getattr(component, "children", None)
        if isinstance(children, (list, tuple, Component)):
            try:
                return _section(children, identity)
            except StopIteration:
                return None  # type: ignore[return-value]
    return None  # type: ignore[return-value]


def _board(projection: ProjectionSet | None, **kwargs: Any) -> tuple[str, list[str]]:
    runs = kwargs.pop("runs", ())
    reports = kwargs.pop("reports", ())
    section = _section(dashboard_page("/", projection, runs, reports, **kwargs), "conclusion")
    return " ".join(_text(section).split()), _hrefs(section)


def _report(projection_set_id: str, *, version: int = 1, **changes: Any) -> ReportSnapshot:
    return replace(
        ReportSnapshot(
            report_snapshot_id=f"report-{projection_set_id}-{version}",
            projection_set_id=projection_set_id,
            target_business_date="2026-08-28",
            version=version,
            status="completed",
            adapter="codex_cli",
            current_stage=None,
            bundle_id="bundle-fixture",
            bundle_hash="abc123",
            model_version_id="model-v0001",
            schema_version="report-schema-v0001",
            prompt_version="report-prompt-v0001",
            report_cutoff=CUTOFF,
            system_as_of=CUTOFF,
            created_at=CUTOFF,
            duration_ms=1250,
            body_retained=True,
            body={"ai_explanation": [{"title": "解读", "explanation": "未提供。"}]},
        ),
        **changes,
    )


def _reading(*paragraphs: str) -> dict[str, Any]:
    return {
        "ai_explanation": [
            {"title": f"第 {index} 节", "explanation": text}
            for index, text in enumerate(paragraphs, 1)
        ],
        "explanation_source": "ai",
    }


def test_ai_reading_shows_the_first_sentence_of_the_latest_same_projection_report(
    published: tuple[RuntimePaths, ProjectionSet],
) -> None:
    _paths, projection = published
    identity = projection.envelope.projection_set_id
    reports = (
        _report(identity, version=1, body=_reading("旧版首句。旧版次句。")),
        _report(
            identity,
            version=2,
            body=_reading("债券牛市而股票熊市，组合不在六个典型组合内。商品仍为牛市。", "第二段。"),
        ),
        _report("projection-other", version=3, body=_reading("别的投影的首句。")),
    )

    text, hrefs = _board(projection, reports=reports)

    assert "解读： 债券牛市而股票熊市，组合不在六个典型组合内。 全文" in text
    assert "商品仍为牛市" not in text and "第二段" not in text
    assert "旧版首句" not in text and "别的投影的首句" not in text
    assert f"?projection={identity}#reading" in hrefs


def test_template_report_says_there_is_no_ai_reading_and_why_the_adapters_failed(
    published: tuple[RuntimePaths, ProjectionSet],
) -> None:
    _paths, projection = published
    template = _report(
        projection.envelope.projection_set_id,
        status="completed_degraded",
        adapter="deterministic",
        body={
            "ai_explanation": [{"title": "非典型组合", "explanation": "模板事实句。"}],
            "explanation_source": "deterministic_template",
        },
        adapter_outcomes=(
            ("codex_cli", "timed_out"),
            ("claude_code_cli", "stage_mutation_rejected"),
        ),
    )

    text, _hrefs = _board(projection, reports=(template,))

    assert (
        "解读： 本次报告为确定性模板，无 AI 解读（适配器失败原因：codex_cli 超时；"
        "claude_code_cli 输出改写正式阶段被拒）"
    ) in text
    assert "模板事实句" not in text


def test_template_report_without_recorded_attempts_does_not_invent_a_reason(
    published: tuple[RuntimePaths, ProjectionSet],
) -> None:
    _paths, projection = published
    template = _report(projection.envelope.projection_set_id, adapter="deterministic")

    text, _hrefs = _board(projection, reports=(template,))

    assert "本次报告为确定性模板，无 AI 解读（未记录适配器尝试）" in text


def test_template_reason_is_the_attempt_the_report_service_recorded(tmp_path: Path) -> None:
    paths = runtime(tmp_path)
    seed_cores(paths)
    projection = target_projection(paths)
    repository = ReportRepository(paths.database)
    ReportService(
        repository,
        (FakeAdapter("claude_code_cli", AdapterResponse.unavailable("authentication_required")),),
    ).generate(report_input_from_projection(projection))

    text, _hrefs = _board(projection, reports=repository.history())

    assert "本次报告为确定性模板，无 AI 解读（适配器失败原因：claude_code_cli 未登录）" in text


def test_queued_report_task_says_the_report_is_being_generated(tmp_path: Path) -> None:
    paths = runtime(tmp_path)
    seed_cores(paths)
    projection = target_projection(paths)
    runs = RunRepository(paths.database)
    runs.submit(
        command_type="report_generation",
        target_business_date="2026-08-28",
        client_request_id="board-footer-report",
        model_version_id=projection.envelope.model_version_id,
        system_as_of=CUTOFF,
        projection_set_id=projection.envelope.projection_set_id,
    )

    text, _hrefs = _board(projection, runs=runs.list_runs(limit=-1, include_details=False))

    assert "解读： 报告生成中" in text
    assert "报告尚未生成" not in text


def test_without_a_same_projection_report_the_board_links_to_the_generate_button(
    published: tuple[RuntimePaths, ProjectionSet],
) -> None:
    _paths, projection = published
    identity = projection.envelope.projection_set_id
    stale = _report("projection-older", version=9, body=_reading("旧投影的报告首句。"))

    text, hrefs = _board(projection, reports=(stale,))

    assert "解读： 报告尚未生成 生成报告" in text
    assert "旧投影的报告首句" not in text
    assert f"?projection={identity}#generate-report-command" in hrefs


SUMMARY = {
    "run_id": "run-produced-it",
    "target_business_date": "2026-08-27",
    "model_version_id": "model-v0009",
    "request_count": 7,
    "request_outcomes": {"verified": 4, "failed": 1, "timeout": 1, "not_found": 1},
    "budget": {"tavily": 3, "exa": 1, "ai_websearch": 2},
    "duration_seconds": 125.4,
}


def test_run_facts_come_from_the_producing_runs_persisted_summary(
    published: tuple[RuntimePaths, ProjectionSet],
) -> None:
    _paths, projection = published

    text, _hrefs = _board(projection, producer_run=ProducerRun("run-produced-it", SUMMARY))

    assert (
        "运行事实：目标交易日 2026-08-27 · 模型版本 model-v0009 · 外部请求 7 次，失败 2 次 · "
        "检索预算 Tavily 3/16、Exa 1/8、AI 2 · 耗时 125.40 秒"
    ) in text


@pytest.mark.parametrize("producer", [None, ProducerRun("run-before-summaries", None)])
def test_run_facts_say_unavailable_rather_than_zero_without_a_summary(
    published: tuple[RuntimePaths, ProjectionSet], producer: ProducerRun | None
) -> None:
    _paths, projection = published

    text, _hrefs = _board(projection, producer_run=producer)

    assert (
        "运行事实：目标交易日 口径不可用 · 模型版本 口径不可用 · 外部请求 口径不可用 · "
        "检索预算 口径不可用 · 耗时 口径不可用"
    ) in text
    assert "0 次" not in text


def test_a_summary_without_a_duration_leaves_only_that_fact_unavailable(
    published: tuple[RuntimePaths, ProjectionSet],
) -> None:
    _paths, projection = published
    unfinished = {**SUMMARY, "duration_seconds": None}

    text, _hrefs = _board(projection, producer_run=ProducerRun("run-produced-it", unfinished))

    assert "外部请求 7 次，失败 2 次" in text
    assert "耗时 口径不可用" in text


def test_empty_library_reads_without_a_report_link_or_invented_run_facts() -> None:
    text, hrefs = _board(None)

    assert "解读：报告尚未生成" in text
    assert "运行事实：目标交易日 口径不可用" in text
    assert not any("generate-report-command" in href for href in hrefs)
