from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from dash import html

from pring_cycle.cockpit import identity_strip
from pring_cycle.dashboard import dashboard_page
from pring_cycle.projections import ProjectionSet
from pring_cycle.run_health import ProducerRun
from tests.integration.test_core_carry_forward import seed_cores
from tests.integration.test_day_summary import target_projection
from tests.integration.test_worker_execution import runtime
from tests.web.test_dashboard_contract import _hrefs, _text


def test_board_orders_seven_sections_and_links_values_to_frozen_evidence(tmp_path: Path) -> None:
    paths = runtime(tmp_path)
    seed_cores(paths)
    projection = target_projection(paths)
    board = dashboard_page("/", projection, (), ())
    text = _text(board)
    headings = [
        "01 周期识别结论",
        "02 三核心与同类资产",
        "03 海外与汇率",
        "04 宏观事后确认",
        "05 库存周期",
        "06 周期说明与阶段史",
        "07 数据说明与解读",
    ]
    assert all(heading in text for heading in headings)
    assert [text.index(heading) for heading in headings] == sorted(text.index(h) for h in headings)
    assert "MA120" in text
    assert "近 5 日" in text and "近 120 日" in text
    links = [href for href in _hrefs(board) if "version=" in href]
    assert links
    assert all(projection.envelope.projection_set_id in href for href in links)
    assert "旧投影未提供展示点列" not in text


IDENTITY_LABELS = ("目标交易日", "模型版本", "投影", "完整度", "分析截止", "运行", "页面生成")
RENDERED_AT = datetime(2026, 10, 16, 1, 2, 3, tzinfo=UTC)


def _identity(projection: ProjectionSet | None, producer: ProducerRun | None = None) -> str:
    strip = identity_strip(projection, producer=producer, rendered_at=RENDERED_AT)
    return " ".join(_text(html.Div(strip)).split())


def test_identity_bar_names_the_projection_its_producing_run_and_render_time(
    tmp_path: Path,
) -> None:
    paths = runtime(tmp_path)
    seed_cores(paths)
    projection = target_projection(paths)
    text = _identity(projection, ProducerRun("run-produced-it", None))
    assert [text.index(label) for label in IDENTITY_LABELS] == sorted(
        text.index(label) for label in IDENTITY_LABELS
    )
    assert "目标交易日 2026-08-28" in text
    assert "模型版本 model-v0001" in text
    assert f"投影 {projection.envelope.projection_set_id}" in text
    assert "分析截止 2026-08-28 21:00:00 北京时间" in text
    assert "运行 run-produced-it" in text
    assert "页面生成 2026-10-16 09:02:03 北京时间" in text
    degraded = replace(projection, envelope=replace(projection.envelope, completeness="degraded"))
    complete = replace(projection, envelope=replace(projection.envelope, completeness="complete"))
    assert "完整度 降级" in _identity(degraded)
    assert "完整度 完整" in _identity(complete)


def test_identity_bar_says_not_provided_when_no_producing_run_is_known(tmp_path: Path) -> None:
    paths = runtime(tmp_path)
    seed_cores(paths)
    projection = target_projection(paths)
    assert "运行 未提供" in _identity(projection)


def test_empty_library_identity_bar_is_readable_without_invented_identity() -> None:
    text = _identity(None)
    assert all(label in text for label in IDENTITY_LABELS)
    assert "等待首次完整运行" in text
    assert "运行 未提供" in text
    assert "model-v" not in text and "projection-" not in text
    assert "页面生成 2026-10-16 09:02:03 北京时间" in text


def test_empty_board_remains_readable_without_fabricated_prices() -> None:
    text = _text(dashboard_page("/", None, (), ()))
    assert "等待首次完整运行" in text
    assert "确认度" in text


def test_old_projection_calendar_keeps_its_frozen_events(tmp_path: Path) -> None:
    paths = runtime(tmp_path)
    seed_cores(paths)
    projection = target_projection(paths)
    projection = replace(
        projection,
        datasets={
            **projection.datasets,
            "release_calendar": {"events": [{"period": "frozen-August", "status": "current"}]},
        },
    )
    text = _text(
        dashboard_page(
            "/release-calendar",
            projection,
            (),
            (),
            (),
            ({"period": "live-October", "status": "current"},),
        )
    )
    assert "frozen-August" in text and "live-October" not in text
    assert projection.envelope.projection_set_id in text


def test_run_charts_keep_unknown_time_and_count_physical_requests_once() -> None:
    from pring_cycle.cockpit_operations import runs_workspace

    summary = {
        "run_id": "chart-run",
        "attempt": 1,
        "status": "completed",
        "duration_seconds": 61.25,
        "request_count": 3,
        "segments": [
            {
                "step": "refreshing_evidence",
                "started_at": "2026-10-15T13:00:00+00:00",
                "ended_at": "2026-10-15T13:01:00+00:00",
                "seconds": 60.0,
            },
            {
                "step": "validating_evidence",
                "started_at": "2026-10-15T13:01:00+00:00",
                "ended_at": None,
                "seconds": None,
            },
        ],
        "requests": [
            {"request_id": "a", "phase": "direct_core_refresh", "metric_ids": ["bond", "stock"]},
            {"request_id": "a", "phase": "direct_core_refresh", "metric_ids": ["commodity"]},
            {"request_id": "b", "phase": "direct_core_refresh", "metric_ids": ["bond"]},
            {"request_id": "c", "phase": "direct_context_refresh", "metric_ids": ["pmi"]},
        ],
    }
    text = " ".join(_text(runs_workspace((), summary, [], {})).split())
    assert "本次运行各环节" in text
    assert "获取证据 60.00 秒" in text
    assert "校验证据 未记录" in text
    assert "请求按环节" in text
    assert "三核心取数 2 次" in text
    assert "背景指标取数 1 次" in text
