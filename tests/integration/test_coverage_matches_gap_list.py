"""Every period section 07's completeness counts as other missing is found in the gap list.

Macro stage 15: the first v0016 projection (target 10-19) counted four catalog periods
missing and its gap list explained three. VIX 10-19 was out and requested, the run held
10-16 and its timeliness was current: the 19th was no due period yet (decided 2026-10-13:
a newer period out and not held only notes, it never makes a gap), so no row named it, and
the coverage counted it missing all the same. The v0015 projection before it left both
bond observation indices out the same way (worker gaps 07, check 6). Such a period is
counted with the gated ones, the run carrying the one before.

The second review (2026-10-20) found the check let a period through that no row showed:
DR007, behind, due 08-27, and 08-28 taken as said for by its timeliness row. A period is
explained only where a row shows it by name. One later than the period due is not due
yet, behind or not; one between the period held and the one due is listed by its row.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pring_cycle.day_summary import RunMaterials
from pring_cycle.freshness import MetricFreshness
from tests.integration.test_core_carry_forward import seed_cores
from tests.integration.test_day_summary import target_projection
from tests.integration.test_worker_execution import runtime

# The final plan of a target day (08-28 here) as v0016 published one, cut to the metrics
# that matter.
PLAN = (
    {"complete": True, "metric_id": "CBOE_VIX_INDEX", "period": "2026-08-27"},
    {
        "complete": False,
        "metric_id": "CBOE_VIX_INDEX",
        "period": "2026-08-28",
        "missing_members": ["CBOE_VIX_INDEX:{}"],
    },
    # Requested on the target day alone, held for none of it.
    {
        "complete": False,
        "metric_id": "CN_BOND_FULL_PRICE_CNY030",
        "period": "2026-08-28",
        "missing_members": ["CN_BOND_FULL_PRICE_CNY030:{}"],
    },
    # An earlier day not had while a later one is: history, the gap list's to name.
    {
        "complete": False,
        "metric_id": "CN_USDCNY_CLOSE_1630",
        "period": "2026-08-27",
        "missing_members": ["CN_USDCNY_CLOSE_1630:{}"],
    },
    {
        "complete": False,
        "metric_id": "EIA_BRENT_RBRTE",
        "period": "2026-08-28",
        "missing_members": ["EIA_BRENT_RBRTE:{}"],
        "release_gate": "awaiting_release",
    },
    # Behind its due period: its timeliness row names the period due.
    {
        "complete": False,
        "metric_id": "CN_DR007",
        "period": "2026-08-27",
        "missing_members": ["CN_DR007:{}"],
    },
    # Past it: not due yet, though the metric is behind (review 2026-10-20 r2).
    {
        "complete": False,
        "metric_id": "CN_DR007",
        "period": "2026-08-28",
        "missing_members": ["CN_DR007:{}"],
    },
    # Two behind: the row states the period due, not the one between held and due.
    *(
        {
            "complete": False,
            "metric_id": "CN_USDCNY_CENTRAL_PARITY",
            "period": period,
            "missing_members": ["CN_USDCNY_CENTRAL_PARITY:{}"],
        }
        for period in ("2026-08-26", "2026-08-27")
    ),
)
# What the run's timeliness recorded: VIX states no due period, the bond's is the day held.
FRESHNESS = {
    "CBOE_VIX_INDEX": MetricFreshness("current", "2026-08-27", None),
    "CN_BOND_FULL_PRICE_CNY030": MetricFreshness("current", "2026-08-27", "2026-08-27"),
    "CN_USDCNY_CLOSE_1630": MetricFreshness("current", "2026-08-28", "2026-08-28"),
    "EIA_BRENT_RBRTE": MetricFreshness("current", "2026-08-27", "2026-08-27"),
    "CN_DR007": MetricFreshness("stale", "2026-08-26", "2026-08-27"),
    "CN_USDCNY_CENTRAL_PARITY": MetricFreshness("stale", "2026-08-25", "2026-08-27"),
}
DR007_ROW = {
    "metric_id": "CN_DR007",
    "priority": "P1",
    "category": "freshness_gap",
    "reason": "one_period_behind_carried",
    "due_period": "2026-08-27",
    "held_period": "2026-08-26",
    "periods_behind": 1,
    "no_web_fallback": True,
}
PARITY_ROW = DR007_ROW | {
    "metric_id": "CN_USDCNY_CENTRAL_PARITY",
    "category": "missing",
    "reason": "two_or_more_periods_behind",
    "held_period": "2026-08-25",
    "periods_behind": 2,
}


def _published(tmp_path: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    paths = runtime(tmp_path)
    seed_cores(paths)
    projection = target_projection(
        paths,
        RunMaterials(
            freshness_gaps=(DR007_ROW, PARITY_ROW),
            freshness=FRESHNESS,
            plan_gaps=PLAN,
        ),
    )
    gaps = {str(gap["metric_id"]): gap for gap in projection.datasets["cycle_overview"]["gap_list"]}
    return projection.datasets["macro"]["coverage"]["catalog"], gaps


# A row's details, each listing periods by name.
_PERIOD_DETAILS = (
    "missing_periods",
    "not_requested",
    "not_covered",
    "members_missing",
    "awaiting_release",
)


def _names(gap: Mapping[str, Any], period: str) -> bool:
    """Whether the row shows ``period`` itself: the due period a timeliness row states, or
    one its details list. A period merely past the one held is not named."""
    due = str(gap.get("due_period") or "")
    return due[: len(period)] == period or any(
        str(item["period"]) == period for key in _PERIOD_DETAILS for item in gap.get(key) or ()
    )


def test_a_period_out_but_not_yet_due_is_counted_with_the_gated_and_carried(
    tmp_path: Path,
) -> None:
    catalog, gaps = _published(tmp_path)

    rows = {(row["metric_id"], row["required_period"]): row for row in catalog["periods"]}
    assert catalog["counts"] == {"held": 1, "release_gated": 4, "missing": 4}
    assert rows[("CBOE_VIX_INDEX", "2026-08-28")]["not_due"] == {"carried_period": "2026-08-27"}
    assert "not_due" in rows[("CN_BOND_FULL_PRICE_CNY030", "2026-08-28")]
    # Later than the period due, whatever the metric holds: behind, it carries 08-26.
    assert rows[("CN_DR007", "2026-08-28")]["not_due"] == {"carried_period": "2026-08-26"}
    # No gap: the run's timeliness holds the due period (decided 2026-10-13).
    assert "CBOE_VIX_INDEX" not in gaps and "CN_BOND_FULL_PRICE_CNY030" not in gaps


def test_each_other_missing_period_is_one_the_gap_list_names(tmp_path: Path) -> None:
    catalog, gaps = _published(tmp_path)

    missing = [
        (row["metric_id"], row["required_period"])
        for row in catalog["periods"]
        if not row.get("complete")
        and not row.get("release_gate")
        and not row.get("awaiting_release")
        and not row.get("not_due")
    ]

    assert len(missing) == catalog["counts"]["missing"]
    assert [
        (metric_id, period)
        for metric_id, period in missing
        if metric_id not in gaps or not _names(gaps[metric_id], period)
    ] == []
    assert sorted(missing) == [
        ("CN_DR007", "2026-08-27"),
        ("CN_USDCNY_CENTRAL_PARITY", "2026-08-26"),
        ("CN_USDCNY_CENTRAL_PARITY", "2026-08-27"),
        ("CN_USDCNY_CLOSE_1630", "2026-08-27"),
    ]
    # Named is shown: a period the row does not show is no period it explains.
    assert not _names(gaps["CN_DR007"], "2099-01-01")
