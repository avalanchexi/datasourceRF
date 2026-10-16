"""The 02 section's three asset cards, read through the home page render function (ticket 04).

Each card heads with what one row of the former 01 three-core table said; its observations,
daily values and noise band open in the shared right drawer.
"""

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
from tests.web.test_overseas_cards import _by_id, _find, _words


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


def _card(projection: ProjectionSet, asset: str, **kwargs: Any) -> Component:
    return _by_id(dashboard_page("/", projection, (), (), **kwargs), "asset-" + asset)


def _panel(page: object, trigger: Component) -> Component:
    return _by_id(page, str(getattr(trigger, "href", "")).removeprefix("#"))


def _triggers(component: object) -> list[Component]:
    return _find(component, lambda item: str(getattr(item, "href", "")).startswith("#drawer-"))


def test_a_card_heads_with_the_former_core_row_in_reading_order() -> None:
    card = _card(_three_cores(), "bond", trend_rules=TrendRules())

    assert _words(card).startswith(
        "债券 · 上证国债指数 CN_BOND_CORE_000012 牛市 230.95 点 2026-09-30 "
        "距 MA120 1.25 % 20 日斜率 0.50 % "
        "30 日候选方向 牛市 资产候选状态 无 "
        "近 5 日 0.50 % 近 120 日 2.00 % 逐日数值与证据"
    )
    assert _hrefs(card)[0] == (
        "/data-chain?projection=projection-cores&version=claim-bond&return=assets#evidence"
    )


def test_the_conclusion_drops_the_core_table_and_points_to_the_cards() -> None:
    page = dashboard_page("/", _three_cores(), (), (), trend_rules=TrendRules())
    conclusion = _by_id(page, "conclusion")

    assert not _find(conclusion, lambda item: isinstance(item, html.Table))
    assert "距 MA120" not in _words(conclusion)
    link = _find(
        conclusion, lambda item: isinstance(item, html.A) and _text(item) == "三核心详见 ② →"
    )
    assert [getattr(item, "href", None) for item in link] == ["?projection=projection-cores#assets"]
    assert [
        _words(_by_id(page, "asset-" + asset)).split(" ")[0]
        for asset in ("bond", "stock", "commodity")
    ] == ["债券", "股票", "商品"]


def test_header_windows_follow_another_rule_set_and_fall_back_when_rules_are_missing() -> None:
    other = _words(_card(_three_cores(), "bond", trend_rules=TrendRules(60, 10)))
    assert "距 MA60 1.25 % 10 日斜率 0.50 %" in other
    assert "MA120 1.25" not in other

    missing = _words(_card(_three_cores(), "bond"))
    assert "距均线 1.25 % 斜率 0.50 %" in missing


def test_the_candidate_lines_keep_the_30_day_direction_and_the_asset_candidate_apart() -> None:
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
    cards = [_words(_card(projection, asset)) for asset in ("bond", "stock", "commodity")]

    assert "30 日候选方向 熊市 资产候选状态 熊市 · 持续 3 日 / 门槛 8 日 近 5 日" in cards[0]
    assert "30 日候选方向 熊市 资产候选状态 牛市 · 持续 5 日 / 门槛 未提供 近 5 日" in cards[1]
    assert "30 日候选方向 无 资产候选状态 无 近 5 日" in cards[2]
    assert all("持续 0 日" not in card and "牛市 · 0" not in card for card in cards)


def test_an_old_projection_without_display_points_keeps_a_readable_card() -> None:
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
    page = dashboard_page("/", projection, (), ())
    card = _by_id(page, "asset-bond")
    (daily,) = [item for item in _triggers(card) if _text(item) == "逐日数值与证据"]

    assert _words(card).startswith("债券 · 上证国债指数 CN_BOND_CORE_000012 牛市 — 旧投影未提供 ")
    assert "30 日候选方向 牛市 资产候选状态 无" in _words(card)
    assert "旧投影未提供展示点列；新运行发布后可用。" in _words(card)
    assert "旧投影未提供展示点列" in _words(_panel(page, daily))
    assert [href for href in _hrefs(card) if not href.startswith("#")] == []


def test_daily_values_and_the_noise_band_open_in_the_drawer_with_frozen_evidence() -> None:
    projection = _three_cores(bond={"noise_band_pct": 0.42})
    page = dashboard_page("/", projection, (), ())
    card = _by_id(page, "asset-bond")
    (daily,) = [item for item in _triggers(card) if _text(item) == "逐日数值与证据"]
    panel = _panel(page, daily)

    assert "噪声带" not in _words(card)
    assert _words(panel).startswith(
        "债券 · 上证国债指数 · 逐日数值与证据 CN_BOND_CORE_000012 关闭 "
        "噪声带：0.42 %；MA120 仅在完整 120 个实际交易日价格齐备时显示。 "
        "交易日 实际价格 MA120 不可得原因 "
        "2026-09-29 229.95 点 228.95 — 2026-09-30 230.95 点 229.95 —"
    )
    assert _hrefs(panel)[1:] == [
        "/data-chain?projection=projection-cores&version=claim-bond&return=assets#evidence"
    ]


ADVANCES = {
    "metric_id": "CN_EQ_ADV_DEC",
    "name_cn": "CN_EQ_ADV_DEC",
    "dimensions": {"measure": "advances", "universe": "point_in_time_traded_a_shares"},
    "value": 978.0,
    "unit": "count",
    "period": "2026-09-30",
    "frequency": "daily",
    "direction": "down",
    "status": "current",
    "selected_claim_id": "claim-advances",
    "observation_id": "observation-advances",
    "display": {
        "points": [
            {"date": "2026-09-29", "value": 1200.0, "selected_claim_id": "claim-advances-29"},
            {"date": "2026-09-30", "value": 978.0, "selected_claim_id": "claim-advances"},
        ],
        "change_5": {
            "value": -222.0,
            "unit": "count",
            "start_date": "2026-09-23",
            "end_date": "2026-09-30",
        },
        "change_120": {"value": None, "reason": "insufficient_history"},
    },
}


def _with_observations(members: list[dict[str, object]]) -> ProjectionSet:
    projection = _three_cores()
    macro: dict[str, object] = {
        "observation_interfaces": {"cores": [{"core": "stock", "members": members}]}
    }
    return replace(projection, datasets={**projection.datasets, "macro": macro})


def test_observations_show_four_columns_and_each_row_opens_every_field() -> None:
    page = dashboard_page(
        "/",
        _with_observations([{"label": "市场广度：涨跌家数", "evidence": [ADVANCES]}]),
        (),
        (),
    )
    card = _by_id(page, "asset-stock")
    (row,) = [item for item in _triggers(card) if _text(item) == "上涨家数"]
    panel = _words(_panel(page, row))

    assert "同类观察 名称 值 近 5 日 方向 上涨家数 978.00 家 -222.00 家 ↓ 下降" in _words(card)
    assert "2026-09-30" not in _words(card).split("同类观察", 1)[1]
    assert panel.startswith(
        "上涨家数 CN_EQ_ADV_DEC · advances 关闭 "
        "最新值 978.00 家 统计期 / 频率 2026-09-30 / 日频 方向 ↓ 下降 "
        "近 5 日 -222.00 家（2026-09-23 → 2026-09-30） "
        "近 120 日 —（不足完整 120 交易日回看） 时效 当前有效 用途 仅观察，不计数 "
        "证据 查看固定版本证据 → 观测 observation-advances 走势与比较端点"
    )
    assert (
        "/data-chain?projection=projection-cores&version=claim-advances&return=assets#evidence"
        in _hrefs(_panel(page, row))
    )


def test_unregistered_observations_and_a_bond_price_reading_say_what_they_are() -> None:
    page = dashboard_page(
        "/",
        _with_observations(
            [{"label": "市场广度：涨跌家数", "reads_as": "bond_price", "evidence": [ADVANCES]}]
        ),
        (),
        (),
    )
    (row,) = [item for item in _triggers(_by_id(page, "asset-stock")) if _text(item) == "上涨家数"]

    assert "用途 债券价格观察" in _words(_panel(page, row))
    assert "当前模型未登记同类观察接口。" in _words(_by_id(page, "asset-bond"))


def test_count_multiple_and_ratio_units_read_in_chinese() -> None:
    rows = [
        {
            **ADVANCES,
            "metric_id": "CN_INDEX_VALUATION",
            "unit": unit,
            "value": value,
            "dimensions": {"index": "000300.SH", "measure": measure},
            "display": {},
        }
        for unit, value, measure in (("multiple", 1.39, "price_book"), ("ratio", 0.22, "x"))
    ]
    card = _words(_card(_with_observations([{"label": "估值", "evidence": rows}]), "stock")).split(
        "同类观察", 1
    )[1]

    assert "沪深 300 市净率 1.39 倍" in card
    assert "0.22 比值" in card
    assert not any(code in card for code in (" multiple", " ratio", " count"))


def test_price_consistency_sits_below_the_cards_with_its_details_in_the_drawer() -> None:
    from tests.web.test_conclusion_board_right import PRICE_CONSISTENCY

    projection = _three_cores()
    projection = replace(
        projection,
        datasets={**projection.datasets, "macro": {"price_consistency": PRICE_CONSISTENCY}},
    )
    page = dashboard_page("/", projection, (), ())
    section = _by_id(page, "assets")
    (consistency,) = _find(section, lambda item: getattr(item, "id", None) == "asset-consistency")
    (details,) = _triggers(consistency)
    panel = _words(_panel(page, details))
    text = _words(section)

    assert text.index("商品 · 南华工业品指数") < text.index("价格内部一致性（不计数）")
    assert _words(consistency) == (
        "价格内部一致性（不计数） 商品对债 +1.23 个百分点 · 股票对债 -0.50 个百分点 · "
        "股票对商品 未确认；股市广度（站上 90 日均线个股占比） 40.0%（上涨集中于较少个股）；"
        "商品篮子分项广度 3/7 个分项同向（上涨集中于少数分项） 查看明细 →"
    )
    assert panel.startswith(
        "价格内部一致性（不计数） 关闭 "
        "相对动量：120 个交易日收益差，需对齐的实际价格点（2026-04-09～2026-09-30） "
        "商品对债：+1.23 个百分点，"
    )
    assert "股票对商品：未确认，缺：CN_EQUITY_CORE_000985" in panel


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
    # A pinned projection's cards and drawers link only to that projection's evidence.
    assert "projection=projection-other-windows&version=" in other
    assert "projection=" + first.envelope.projection_set_id + "&version=" not in other
