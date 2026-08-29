from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from pring_cycle.cli import main


def test_public_official_context_contract_is_offline_and_non_mutating(
    tmp_path: Path,
    capsys: object,
) -> None:
    runtime_root = tmp_path / "runtime"
    source = tmp_path / "core-cpi.html"
    source.write_text(
        """
        <html><body><h1>2026年6月份居民消费价格</h1>
        <p>发布时间：2026-07-09 09:30</p>
        <table>
          <tr><th>指标</th><th>环比（%）</th><th>同比（%）</th><th>累计平均同比（%）</th></tr>
          <tr><td>不包括食品和能源</td><td>-0.1</td><td>1.0</td><td>1.2</td></tr>
        </table></body></html>
        """,
        encoding="utf-8",
    )

    main(
        [
            "official-context-contract",
            "--runtime-root",
            str(runtime_root),
            "--input",
            str(source),
            "--family",
            "nbs_core_cpi",
            "--url",
            "https://www.stats.gov.cn/sj/zxfb/202607/t20260709_1.html",
            "--period",
            "2026-06",
            "--fetched-at",
            "2026-07-09T02:00:00+00:00",
            "--json",
        ]
    )
    document = cast(dict[str, Any], json.loads(cast(Any, capsys).readouterr().out))

    assert document["status"] == "validated_candidate"
    assert document["network_requests"] == 0
    assert document["observation_count"] == 3
    assert not runtime_root.exists()


def test_public_eia_contract_is_offline_and_non_mutating(
    tmp_path: Path,
    capsys: object,
) -> None:
    runtime_root = tmp_path / "runtime"
    source = tmp_path / "eia.json"
    source.write_text(
        json.dumps(
            {
                "response": {
                    "frequency": "daily",
                    "data": [
                        {
                            "period": "2026-08-27",
                            "series": "RBRTE",
                            "series-description": "Europe Brent Spot Price FOB",
                            "value": "71.25",
                            "units": "Dollars per Barrel",
                        },
                        {
                            "period": "2026-08-27",
                            "series": "RWTC",
                            "series-description": "Cushing, OK WTI Spot Price FOB",
                            "value": "66.50",
                            "units": "Dollars per Barrel",
                        },
                    ],
                }
            }
        ),
        encoding="utf-8",
    )

    main(
        [
            "eia-contract",
            "--runtime-root",
            str(runtime_root),
            "--input",
            str(source),
            "--start",
            "2026-08-27",
            "--end",
            "2026-08-27",
            "--json",
        ]
    )
    document = cast(dict[str, Any], json.loads(cast(Any, capsys).readouterr().out))

    assert document == {
        "metric_ids": ["EIA_BRENT_RBRTE", "EIA_WTI_RWTC"],
        "network_requests": 0,
        "observation_count": 2,
        "series_ids": ["RBRTE", "RWTC"],
        "status": "validated_candidate",
    }
    assert not runtime_root.exists()
