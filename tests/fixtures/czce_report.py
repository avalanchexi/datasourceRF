"""Synthetic CZCE daily warrant reports in the exchange's plain-text layout (ADR-0032).

The real samples are in ``tests/fixtures/czce_warrants``; full-run fixtures need one report
for every session of their window.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from datetime import date

_PTA_HEADER = (
    "仓库编号  |仓库简称          |品牌            |仓单数量(完税)  |仓单数量(保税)  "
    "|当日增减  |有效预报  |升贴水"
)
_COTTON_HEADER = (
    "仓库编号  |仓库简称    |年度  |等级      |产地      |仓单数量  |当日增减  |有效预报"
)

# Warehouse, receipts, change of the day.
Members = Sequence[tuple[str, int, int]]


def czce_report(day: date, *, pta: Members, cotton: Members) -> bytes:
    lines = [f"\t\t\t\t\t郑州商品交易所期货仓单日报表({day.isoformat()})", "", "\t\t\t\t\t农产品"]
    lines.append(f"品种：棉花CF   单位：张          日期：{day.isoformat()}     每张仓单=40吨")
    lines.append(_COTTON_HEADER)
    for code, (warehouse, receipts, change) in enumerate(cotton, start=301):
        lines.append(f"0{code}|{warehouse}|2526|3129|新疆|{receipts}|{change}|")
        lines.append(f"小计|||||{receipts}|{change}|0")
    total = (sum(m[1] for m in cotton), sum(m[2] for m in cotton))
    lines += [f"总计|||||{total[0]}|{total[1]}|0", ""]
    lines.append(f"品种：PTA   单位：张          日期：{day.isoformat()}     每张仓单=5吨")
    lines.append(_PTA_HEADER)
    for code, (warehouse, receipts, change) in enumerate(pta, start=501):
        lines.append(f"0{code}|{warehouse}|合成品牌|{receipts}|0|{change}||0")
        lines.append(f"小计|||{receipts}|0|{change}|0|")
    total = (sum(m[1] for m in pta), sum(m[2] for m in pta))
    lines += [f"总计|||{total[0]}|0|{total[1]}|0|", ""]
    return "\n".join(lines).encode()


def czce_exchange(
    sessions: Callable[[date], bool],
    *,
    pta: Members = (("合成仓库", 100, 0),),
    cotton: Members = (("合成仓库", 25, 0),),
    overrides: Mapping[date, bytes] | None = None,
) -> Callable[[str], bytes]:
    """A fetch serving a report for each session, and 404 for any other day."""

    def fetch(url: str) -> bytes:
        found = re.search(r"/(\d{8})/FutureDataWhsheet\.txt$", url)
        if found is None:
            raise OSError("czce_warrant_http_404")
        text = found.group(1)
        day = date(int(text[:4]), int(text[4:6]), int(text[6:]))
        if overrides and day in overrides:
            return overrides[day]
        if not sessions(day):
            raise OSError("czce_warrant_http_404")
        return czce_report(day, pta=pta, cotton=cotton)

    return fetch
