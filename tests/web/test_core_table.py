"""The 01 section's three-core table, read through the home page render function."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dash import html
from dash.development.base_component import Component

from pring_cycle.dashboard import dashboard_page
from pring_cycle.domain.trend import TrendRules
from pring_cycle.projections import ProjectionEnvelope, ProjectionSet
from tests.web.test_dashboard_contract import _hrefs, _text

NINE_COLUMNS = (
    "三核心",
    "状态",
    "最新",
    "距 MA120",
    "20 日斜率",
    "候选",
    "近 5 日",
    "近 120 日",
    "120 日走势",
)


def _asset(asset: str, metric_id: str, **fields: object) -> dict[str, object]:
    return {
        "asset": asset,
        "metric_id": metric_id,
        "state": "bull",
        "reason": "validated",
        "distance_pct": 1.25,
        "slope_pct": 0.5,
        "candidate_30d": "bull",
        "candidate_state": None,
        "candidate_days": 0,
        "persistence_required": 8,
        "latest_business_date": "2026-09-30",
        **fields,
    }


def _display(value: float, claim: str) -> dict[str, object]:
    return {
        "unit": "index_points",
        "latest_value": value,
        "latest_date": "2026-09-30",
        "points": [
            {
                "date": "2026-09-29",
                "value": value - 1,
                "ma120": value - 2,
                "selected_claim_id": None,
            },
            {"date": "2026-09-30", "value": value, "ma120": value - 1, "selected_claim_id": claim},
        ],
        "change_5": {"value": 0.5, "unit": "percent"},
        "change_120": {"value": 2.0, "unit": "percent"},
    }


def _projection(
    assets: list[dict[str, object]], displays: dict[str, object] | None = None
) -> ProjectionSet:
    return ProjectionSet(
        ProjectionEnvelope(
            projection_set_id="projection-cores",
            system_as_of=datetime(2026, 10, 10, 3, tzinfo=UTC),
            target_business_date="2026-09-30",
            evidence_snapshot_id="snapshot-cores",
            model_version_id="model-v0015",
            trend_rule_version="trend-v0001",
            evidence_window_start="2026-04-09",
            evidence_window_end="2026-09-30",
            generated_at=datetime(2026, 10, 10, 3, tzinfo=UTC),
            completeness="complete",
            refresh_status="completed",
            warnings=(),
        ),
        {
            "cycle_overview": {"current_stage": None, "stage_reason": "noncanonical_combination"},
            "core_assets": {
                "assets": assets,
                "display": displays
                if displays is not None
                else {
                    "bond": _display(230.95, "claim-bond"),
                    "stock": _display(5648.25, "claim-stock"),
                    "commodity": _display(4097.94, "claim-commodity"),
                },
            },
            "macro": {},
            "inventory": {},
            "release_calendar": {},
            "stage_history": {},
        },
    )


def _three_cores(**overrides: dict[str, object]) -> ProjectionSet:
    return _projection(
        [
            _asset("bond", "CN_BOND_CORE_000012", **overrides.get("bond", {})),
            _asset("stock", "CN_EQUITY_CORE_000985", state="bear", **overrides.get("stock", {})),
            _asset("commodity", "CN_COMMODITY_CORE_NHII", **overrides.get("commodity", {})),
        ]
    )


def _core_table(page: object) -> tuple[list[str], list[list[Any]]]:
    """The first table under 01 whose header names the three cores: headers and raw cells."""

    def walk(component: object) -> Any:
        if isinstance(component, (list, tuple)):
            for child in component:
                found = walk(child)
                if found is not None:
                    return found
            return None
        if not isinstance(component, Component):
            return None
        if isinstance(component, html.Table):
            head, body = component.children
            headers = [_text(cell) for cell in head.children.children]
            if headers and headers[0] == "三核心":
                return headers, [list(row.children) for row in body.children]
        return walk(getattr(component, "children", None))

    found: tuple[list[str], list[list[Any]]] | None = walk(page)
    assert found is not None, "no three-core table on the page"
    return found


def _cells(row: list[Any]) -> list[str]:
    return [" ".join(_text(cell).split()) for cell in row]


def test_core_table_has_nine_columns_named_from_the_frozen_trend_rules() -> None:
    headers, rows = _core_table(
        dashboard_page("/", _three_cores(), (), (), trend_rules=TrendRules())
    )

    assert tuple(headers) == NINE_COLUMNS
    assert all(len(row) == 9 for row in rows)
    assert [_cells(row)[0].split(" ")[0] for row in rows] == ["债券", "股票", "商品"]


def test_column_windows_follow_another_rule_set_and_fall_back_when_rules_are_missing() -> None:
    other = TrendRules(window_days=60, slope_days=10)
    headers, _rows = _core_table(dashboard_page("/", _three_cores(), (), (), trend_rules=other))
    assert headers[3:5] == ["距 MA60", "10 日斜率"]

    headers, rows = _core_table(dashboard_page("/", _three_cores(), (), ()))
    assert headers[3:5] == ["距均线", "斜率"]
    assert "MA120" not in " ".join(headers)
    assert all(len(row) == 9 for row in rows)


def test_candidate_column_keeps_the_30_day_direction_and_the_asset_candidate_apart() -> None:
    projection = _three_cores(
        # Same: a 30-day bear reading that has already become a 3-day asset candidate.
        bond={"candidate_30d": "bear", "candidate_state": "bear", "candidate_days": 3},
        # Different: the 30-day direction is back to bear while a bull candidate persists.
        stock={
            "candidate_30d": "bear",
            "candidate_state": "bull",
            "candidate_days": 5,
            "persistence_required": None,
        },
        # None: no 30-day direction and no asset candidate.
        commodity={"candidate_30d": None, "candidate_state": None, "candidate_days": 0},
    )
    _headers, rows = _core_table(dashboard_page("/", projection, (), (), trend_rules=TrendRules()))
    candidates = [_cells(row)[5] for row in rows]

    assert candidates == [
        "30 日候选方向 熊市 资产候选状态 熊市 · 持续 3 日 / 门槛 8 日",
        "30 日候选方向 熊市 资产候选状态 牛市 · 持续 5 日 / 门槛 未提供",
        "30 日候选方向 无 资产候选状态 无",
    ]
    assert all("0 天" not in cell and "持续 0 日" not in cell for cell in candidates)


def test_a_30_day_direction_without_an_asset_candidate_is_not_read_as_a_duration() -> None:
    _headers, rows = _core_table(
        dashboard_page("/", _three_cores(), (), (), trend_rules=TrendRules())
    )
    bond = _cells(rows[0])

    assert bond[5] == "30 日候选方向 牛市 资产候选状态 无"
    assert "牛市 · 0" not in " ".join(bond)


def test_core_cell_names_the_asset_and_its_core_metric() -> None:
    _headers, rows = _core_table(
        dashboard_page("/", _three_cores(), (), (), trend_rules=TrendRules())
    )

    assert [_cells(row)[0] for row in rows] == [
        "债券 · 上证国债指数 CN_BOND_CORE_000012",
        "股票 · 中证全指 CN_EQUITY_CORE_000985",
        "商品 · 南华工业品指数 CN_COMMODITY_CORE_NHII",
    ]


def test_state_and_latest_columns_read_as_glossary_states_and_frozen_evidence() -> None:
    _headers, rows = _core_table(
        dashboard_page("/", _three_cores(), (), (), trend_rules=TrendRules())
    )

    assert [_cells(row)[1] for row in rows] == ["牛市", "熊市", "牛市"]
    assert _cells(rows[0])[2] == "230.95 点 2026-09-30"
    assert _hrefs(rows[0][2]) == [
        "/data-chain?projection=projection-cores&version=claim-bond&return=conclusion#evidence"
    ]
    assert [_cells(row)[3:5] for row in rows][0] == ["1.25 %", "0.50 %"]
    assert [_cells(row)[6:8] for row in rows][0] == ["0.50 %", "2.00 %"]


def test_an_old_projection_without_display_points_keeps_a_readable_nine_column_table() -> None:
    projection = _projection(
        [
            {
                "asset": "bond",
                "metric_id": "CN_BOND_CORE_000012",
                "state": "bull",
                "candidate_30d": "bull",
                "candidate_days": 0,
            }
        ],
        displays={},
    )
    headers, rows = _core_table(dashboard_page("/", projection, (), ()))
    bond = _cells(rows[0])

    assert len(headers) == len(bond) == 9
    assert bond[1] == "牛市"
    assert bond[2] == "— 旧投影未提供"
    assert bond[5] == "30 日候选方向 牛市 资产候选状态 无"
    assert bond[8] == "旧投影未提供展示点列；新运行发布后可用。"
    assert _hrefs(rows[0][2]) == []


def test_web_reads_column_windows_from_the_projection_s_frozen_model(tmp_path: Path) -> None:
    from pring_cycle.models import ModelRepository, certified_model_v0001_manifest
    from pring_cycle.projections import ProjectionSetRepository
    from tests.integration.test_core_carry_forward import seed_cores
    from tests.integration.test_day_summary import target_projection
    from tests.integration.test_worker_execution import runtime
    from tests.web.test_cockpit_http import rendered_page, serving

    paths = runtime(tmp_path)
    seed_cores(paths)
    first = target_projection(paths)
    manifest = certified_model_v0001_manifest()
    manifest["model_version_id"] = "model-test-windows"
    manifest["trend_rules"] = {**manifest["trend_rules"], "window_days": 60, "slope_days": 10}
    ModelRepository(paths.database).register(manifest)

    def publish(projection_id: str, model_version_id: str) -> None:
        envelope = replace(
            first.envelope, projection_set_id=projection_id, model_version_id=model_version_id
        )
        ProjectionSetRepository(paths.database).publish(
            envelope,
            {
                name: {**data, "projection_set_id": projection_id}
                for name, data in first.datasets.items()
            },
        )

    publish("projection-other-windows", "model-test-windows")

    with serving(paths) as base:

        def page(projection_id: str) -> str:
            response = rendered_page(base, "/", "?projection=" + projection_id)
            return json.dumps(response["page-content"]["children"], ensure_ascii=False)

        frozen = page(first.envelope.projection_set_id)
        other = page("projection-other-windows")

    assert '"距 MA120"' in frozen and '"20 日斜率"' in frozen
    assert '"距 MA60"' in other and '"10 日斜率"' in other
    assert '"距 MA120"' not in other


def test_the_table_scrolls_inside_its_own_container_so_the_page_does_not_overflow() -> None:
    page = dashboard_page("/", _three_cores(), (), (), trend_rules=TrendRules())

    def scroll_containers(component: object) -> list[html.Div]:
        if isinstance(component, (list, tuple)):
            return [found for child in component for found in scroll_containers(child)]
        if not isinstance(component, Component):
            return []
        own = (
            [component]
            if isinstance(component, html.Div)
            and getattr(component, "className", None) == "table-scroll"
            and "core-table" in str(getattr(component.children, "className", ""))
            else []
        )
        return own + scroll_containers(getattr(component, "children", None))

    assert len(scroll_containers(page)) == 1
    stylesheet = (
        Path(__file__).parents[2] / "src" / "pring_cycle" / "assets" / "report.css"
    ).read_text(encoding="utf-8")
    assert ".table-scroll { overflow-x: auto; max-width: 100%;" in stylesheet
    assert ".core-table td { white-space: nowrap; }" in stylesheet
