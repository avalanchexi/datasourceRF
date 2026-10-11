from __future__ import annotations

import statistics
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

from pring_cycle.domain.types import CoreAssetState


@dataclass(frozen=True)
class PricePoint:
    business_date: date
    value: float


@dataclass(frozen=True)
class TrendRules:
    window_days: int = 120
    slope_days: int = 20
    volatility_days: int = 20
    noise_multiplier: float = 1.5
    persistence_days: int = 8
    candidate_window_days: int = 30
    rule_version: str = "trend-v0001"
    candidate_duration_rule_version: str = "candidate-duration-v0001"
    # The public Pring 12-month proxy, off from model v0014 on (ADR-0035, ticket 25).
    proxy_12m_enabled: bool = True

    @property
    def history_required(self) -> int:
        """Closes a day's reading needs: the moving average and the one it slopes from."""
        return self.window_days + self.slope_days

    def candidate_days_for_output(self, result: TrendResult | TrendHistoryPoint) -> int:
        # Historical manifests retain their published duration semantics.
        if self.candidate_duration_rule_version == "candidate-duration-v0001":
            return result.persistence_days
        if self.candidate_duration_rule_version == "candidate-duration-v0002":
            return result.candidate_days
        raise ValueError("candidate_duration_rule_version_unsupported")


def proxy_12m_enabled(document: Mapping[str, object]) -> bool:
    """Whether a model's trend rules keep the 12-month proxy; rules before the switch do."""
    enabled = document.get("proxy_12m_enabled", True)
    if not isinstance(enabled, bool):
        raise ValueError("model_trend_rules_invalid")
    return enabled


@dataclass(frozen=True)
class TrendResult:
    stable_state: CoreAssetState | None
    candidate_state: CoreAssetState | None
    candidate_30d: CoreAssetState | None
    proxy_12m: CoreAssetState | None
    reason: str
    persistence_days: int
    distance_pct: float | None
    slope_pct: float | None
    noise_band_pct: float | None
    rule_version: str
    network_requests: int = 0
    candidate_days: int = 0


@dataclass(frozen=True)
class TrendHistoryPoint:
    business_date: date
    stable_state: CoreAssetState | None
    distance_pct: float | None
    candidate_state: CoreAssetState | None = None
    candidate_days: int = 0
    persistence_days: int = 0


def evaluate_trend(points: list[PricePoint], rules: TrendRules) -> TrendResult:
    ordered = sorted(points, key=lambda point: point.business_date)
    required = rules.history_required
    if len(ordered) < required or any(point.value <= 0 for point in ordered):
        return TrendResult(
            stable_state=None,
            candidate_state=None,
            candidate_30d=None,
            proxy_12m=None,
            reason="insufficient_history",
            persistence_days=0,
            distance_pct=None,
            slope_pct=None,
            noise_band_pct=None,
            rule_version=rules.rule_version,
        )

    values = [point.value for point in ordered]
    stable_state: CoreAssetState | None = None
    candidate_state: CoreAssetState | None = None
    candidate_days = 0
    latest_measurement: tuple[float, float, float] | None = None
    for index in range(required - 1, len(values)):
        current_ma = statistics.fmean(values[index - rules.window_days + 1 : index + 1])
        prior_end = index - rules.slope_days
        prior_ma = statistics.fmean(values[prior_end - rules.window_days + 1 : prior_end + 1])
        distance_pct = (values[index] / current_ma - 1.0) * 100.0
        slope_pct = (current_ma / prior_ma - 1.0) * 100.0
        recent = values[index - rules.volatility_days : index + 1]
        returns = [
            (current / previous - 1.0) * 100.0
            for previous, current in zip(recent, recent[1:], strict=False)
        ]
        volatility_pct = statistics.pstdev(returns)
        noise_band_pct = rules.noise_multiplier * abs(volatility_pct)
        signal = _directional_signal(distance_pct, slope_pct, noise_band_pct)
        latest_measurement = (distance_pct, slope_pct, noise_band_pct)
        if signal is None:
            candidate_state = None
            candidate_days = 0
            continue
        if signal is stable_state:
            candidate_state = None
            candidate_days = 0
            continue
        if signal is candidate_state:
            candidate_days += 1
        else:
            candidate_state = signal
            candidate_days = 1
        if candidate_days >= rules.persistence_days:
            stable_state = signal
            candidate_state = None
            candidate_days = 0

    if latest_measurement is None:
        raise AssertionError("trend_measurement_missing")
    distance_pct, slope_pct, noise_band_pct = latest_measurement
    return TrendResult(
        stable_state=stable_state,
        candidate_state=candidate_state,
        candidate_30d=_simple_track(values, rules.candidate_window_days),
        proxy_12m=_monthly_proxy(ordered) if rules.proxy_12m_enabled else None,
        reason="stable" if stable_state is not None else "transition_pending",
        persistence_days=rules.persistence_days if stable_state is not None else candidate_days,
        distance_pct=distance_pct,
        slope_pct=slope_pct,
        noise_band_pct=noise_band_pct,
        rule_version=rules.rule_version,
        candidate_days=candidate_days,
    )


def evaluate_trend_history(
    points: list[PricePoint],
    rules: TrendRules,
) -> tuple[TrendHistoryPoint, ...]:
    ordered = sorted(points, key=lambda point: point.business_date)
    if any(point.value <= 0 for point in ordered):
        return tuple(TrendHistoryPoint(point.business_date, None, None) for point in ordered)
    required = rules.history_required
    values = [point.value for point in ordered]
    stable_state: CoreAssetState | None = None
    candidate_state: CoreAssetState | None = None
    candidate_days = 0
    history: list[TrendHistoryPoint] = []
    for index, point in enumerate(ordered):
        if index < required - 1:
            history.append(TrendHistoryPoint(point.business_date, None, None))
            continue
        current_ma = statistics.fmean(values[index - rules.window_days + 1 : index + 1])
        prior_end = index - rules.slope_days
        prior_ma = statistics.fmean(values[prior_end - rules.window_days + 1 : prior_end + 1])
        distance_pct = (values[index] / current_ma - 1.0) * 100.0
        slope_pct = (current_ma / prior_ma - 1.0) * 100.0
        recent = values[index - rules.volatility_days : index + 1]
        returns = [
            (current / previous - 1.0) * 100.0
            for previous, current in zip(recent, recent[1:], strict=False)
        ]
        noise_band_pct = rules.noise_multiplier * abs(statistics.pstdev(returns))
        signal = _directional_signal(distance_pct, slope_pct, noise_band_pct)
        if signal is None or signal is stable_state:
            candidate_state = None
            candidate_days = 0
        elif signal is candidate_state:
            candidate_days += 1
        else:
            candidate_state = signal
            candidate_days = 1
        if candidate_days >= rules.persistence_days:
            stable_state = signal
            candidate_state = None
            candidate_days = 0
        history.append(
            TrendHistoryPoint(
                point.business_date,
                stable_state,
                distance_pct,
                candidate_state,
                candidate_days,
                rules.persistence_days if stable_state is not None else candidate_days,
            )
        )
    return tuple(history)


def _directional_signal(
    distance_pct: float, slope_pct: float, noise_band_pct: float
) -> CoreAssetState | None:
    if distance_pct >= noise_band_pct and slope_pct > 0:
        return CoreAssetState.BULL
    if distance_pct <= -noise_band_pct and slope_pct < 0:
        return CoreAssetState.BEAR
    return None


def _simple_track(values: list[float], window: int) -> CoreAssetState | None:
    if len(values) < window + 1:
        return None
    average = statistics.fmean(values[-window:])
    prior_average = statistics.fmean(values[-window - 1 : -1])
    if values[-1] > average and average > prior_average:
        return CoreAssetState.BULL
    if values[-1] < average and average < prior_average:
        return CoreAssetState.BEAR
    return None


def _monthly_proxy(points: list[PricePoint]) -> CoreAssetState | None:
    month_ends: dict[tuple[int, int], PricePoint] = {}
    for point in points:
        month_ends[(point.business_date.year, point.business_date.month)] = point
    monthly = [
        point.value for point in sorted(month_ends.values(), key=lambda item: item.business_date)
    ]
    if len(monthly) < 13:
        return None
    average = statistics.fmean(monthly[-12:])
    if monthly[-1] > average:
        return CoreAssetState.BULL
    if monthly[-1] < average:
        return CoreAssetState.BEAR
    return None
