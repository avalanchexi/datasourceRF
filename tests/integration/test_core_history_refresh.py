from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from pring_cycle.adapters import MarketBar
from pring_cycle.core_history import CORE_HISTORY_SCHEMA_VERSION, refresh_core_history
from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.source_adapters import CORE_API_IDENTITIES
from pring_cycle.storage import artifact_is_registered


class FakeCoreAdapter:
    def trading_days(self, start: date, end: date) -> tuple[date, ...]:
        return tuple(
            start + timedelta(days=offset)
            for offset in range((end - start).days + 1)
            if (start + timedelta(days=offset)).weekday() < 5
        )

    def core_bars(
        self,
        metric_id: str,
        *,
        start: date,
        end: date,
        expected_business_dates: tuple[date, ...] | None = None,
    ) -> tuple[MarketBar, ...]:
        del start, end
        assert expected_business_dates is not None
        source_code = CORE_API_IDENTITIES[metric_id][1]
        return tuple(
            MarketBar(
                metric_id=metric_id,
                source_code=source_code,
                business_date=business_date,
                close=100.0 + index,
                pre_close=99.0 + index,
                official_return=0.01,
                unit="index_points",
                certification_status="certified",
            )
            for index, business_date in enumerate(expected_business_dates)
        )


def test_core_history_refresh_is_atomic_content_addressed_and_queryable(
    tmp_path: Path,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)

    result = refresh_core_history(
        paths,
        FakeCoreAdapter(),
        start=date(2025, 12, 30),
        end=date(2026, 1, 2),
        definition_version="metric-catalog-v0001",
    )

    assert result.status == "validated"
    assert result.observations_per_metric == 4
    assert result.network_requests == 8
    assert artifact_is_registered(
        paths.database,
        result.artifact_hash,
        f"{CORE_HISTORY_SCHEMA_VERSION}:2025-12-30:2026-01-02",
    )
    series = EvidenceRepository(paths.database).metric_series(
        "CN_COMMODITY_CORE_NHII",
        mode=AsOfMode.PUBLIC,
        as_of=datetime(2026, 1, 2, 23, 59, tzinfo=UTC),
        definition_version="metric-catalog-v0001",
    )
    assert [point.selected_value for point in series] == [100.0, 101.0, 100.0, 101.0]
