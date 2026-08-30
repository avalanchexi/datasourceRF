from __future__ import annotations

from datetime import date, timedelta

from pring_cycle.domain import CoreAssetState
from pring_cycle.domain.trend import (
    PricePoint,
    TrendRules,
    evaluate_trend,
    evaluate_trend_history,
)


def price_series(*, increasing: bool, count: int = 160) -> list[PricePoint]:
    start = date(2025, 1, 1)
    return [
        PricePoint(
            business_date=start + timedelta(days=index),
            value=100.0 + (index if increasing else -index * 0.3),
        )
        for index in range(count)
    ]


def test_stable_direction_uses_price_position_slope_noise_and_persistence() -> None:
    rules = TrendRules()

    bullish = evaluate_trend(price_series(increasing=True), rules)
    bearish = evaluate_trend(price_series(increasing=False), rules)

    assert bullish.stable_state is CoreAssetState.BULL
    assert bearish.stable_state is CoreAssetState.BEAR
    assert bullish.rule_version == "trend-v0001"
    assert bullish.persistence_days >= 8
    assert bullish.network_requests == 0


def test_insufficient_history_is_not_a_neutral_or_bear_state() -> None:
    result = evaluate_trend(price_series(increasing=True, count=119), TrendRules())

    assert result.stable_state is None
    assert result.reason == "insufficient_history"


def test_30_day_candidate_and_12_month_proxy_do_not_vote_in_formal_state() -> None:
    result = evaluate_trend(price_series(increasing=True), TrendRules())

    assert result.candidate_30d is CoreAssetState.BULL
    assert result.proxy_12m is None
    assert result.stable_state is CoreAssetState.BULL


def test_linear_trend_history_matches_every_prefix_evaluation() -> None:
    points = [
        PricePoint(
            date(2024, 1, 1) + timedelta(days=index),
            100.0 + index * 0.03 + ((index % 17) - 8) * 0.4,
        )
        for index in range(320)
    ]
    rules = TrendRules()

    history = evaluate_trend_history(points, rules)

    assert len(history) == len(points)
    for index, historical in enumerate(history):
        prefix = evaluate_trend(points[: index + 1], rules)
        assert historical.business_date == points[index].business_date
        assert historical.stable_state is prefix.stable_state
        assert historical.distance_pct == prefix.distance_pct
