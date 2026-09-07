"""Read saved official RRR bytes through the installed public parser; never write a DB."""

from datetime import UTC, datetime
from pathlib import Path
import json

from pring_cycle.official_context import parse_official_context_document


root = Path(__file__).resolve().parent
raw = (root / "evidence-13/7c74949b8e34290d31b76c3fc11b70e783d8ccdd9c7fc321f6e38b4fd17285d5").read_bytes()
results = []
for period in ("2025-05", "2026-05"):
    try:
        parsed = parse_official_context_document(
            raw,
            family="pbc_rrr_notice",
            source_url="https://www.pbc.gov.cn/goutongjiaoliu/113456/113469/5896228/index.html",
            expected_period=period,
            fetched_at=datetime(2026, 9, 7, 14, tzinfo=UTC),
        )
        result = {
            "period": period,
            "status": "parsed",
            "release_at": str(parsed.release_at),
            "scalars": [
                {"period": item.period_end, "dimensions": item.dimensions, "value": item.value}
                for item in parsed.scalars
            ],
        }
    except ValueError as error:
        result = {"period": period, "status": "rejected", "error": str(error)}
    results.append(result)
print(json.dumps({"public_parser": True, "database_writes": 0, "results": results}, indent=2))
