"""China trading sessions keep administrative working weekends closed."""

from datetime import date

import pytest

from pring_cycle.source_adapters import TushareCoreAdapter


def test_public_calendar_rejects_administrative_working_sunday():
    response = {
        "code": 0,
        "data": {
            "fields": ["cal_date", "is_open"],
            "items": [
                ["20260918", 1],
                ["20260920", 1],
                ["20260921", 1],
                ["20260922", 1],
            ],
        },
    }
    adapter = TushareCoreAdapter("synthetic-token", transport=lambda _: response)

    with pytest.raises(ValueError, match="china_trading_calendar_invalid"):
        adapter.trading_days(date(2026, 9, 18), date(2026, 9, 22))
