from dataclasses import replace
from pathlib import Path

from pring_cycle.dashboard import dashboard_page
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
    assert "5 日变化" in text and "120 日变化" in text
    links = [href for href in _hrefs(board) if "version=" in href]
    assert links
    assert all(projection.envelope.projection_set_id in href for href in links)
    assert "旧投影未提供展示点列" not in text


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
