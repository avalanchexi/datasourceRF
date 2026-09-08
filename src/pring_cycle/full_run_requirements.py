from __future__ import annotations

import json
from datetime import UTC, date, datetime
from typing import Any

from pring_cycle.acquisition import AcquisitionRepository
from pring_cycle.context_projection import ContextProjectionRules
from pring_cycle.evidence import EvidenceValueState
from pring_cycle.runs import RunRecord
from pring_cycle.runtime import RuntimePaths
from pring_cycle.search_evidence import ModelInputSelector
from pring_cycle.storage import database_connection


def required_calendar(
    paths: RuntimePaths, run: RunRecord, selector: ModelInputSelector
) -> dict[str, Any]:
    """Use independent calendar evidence, never the price series being checked."""
    points = selector.series("CN_TRADE_CALENDAR")
    days, claim_ids = [], []
    for point in points:
        claim = next((c for c in point.claims if c.claim_id == point.selected_claim_id), None)
        if (
            point.period_end <= run.target_business_date
            and point.selection_status == "selected"
            and point.value_state is EvidenceValueState.REPORTED_VALUE
            and point.selected_value == 1
            and claim is not None
            and claim.certification_status == "certified"
            and claim.quality_status == "validated"
        ):
            days.append(point.period_end)
            claim_ids.append(claim.claim_id)
    dates = sorted(set(days))[-120:]
    proof: dict[str, Any] = {"claim_ids": claim_ids, "acquisition_id": None}
    basis = "certified_trade_calendar_claims"
    if len(dates) < 120 or not dates or dates[-1] != run.target_business_date:
        dates = []
        with database_connection(paths.database) as connection:
            receipts = connection.execute(
                "SELECT acquisition_id, validated_at FROM acquisition_request "
                "WHERE provider='tushare' "
                "AND api_name='trade_cal' AND state='validated' "
                "AND parser_version='tushare-core-parser-v0002' "
                "AND julianday(validated_at)<=julianday(?) ORDER BY julianday(validated_at) DESC",
                (selector.as_of.astimezone(UTC).isoformat(),),
            ).fetchall()
        acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
        for acquisition_id, validated_at in sorted(
            receipts, key=lambda row: datetime.fromisoformat(row[1]), reverse=True
        ):
            if datetime.fromisoformat(validated_at) > selector.as_of:
                continue
            document = json.loads(acquisitions.read_content(acquisition_id, "normalized"))
            if not isinstance(document, list) or not all(isinstance(day, str) for day in document):
                continue
            candidates = sorted(
                {
                    date.fromisoformat(day).isoformat()
                    for day in document
                    if day <= run.target_business_date
                }
            )[-120:]
            if len(candidates) == 120 and candidates[-1] == run.target_business_date:
                dates = candidates
                proof = {"claim_ids": [], "acquisition_id": acquisition_id}
                basis = "validated_independent_calendar_response"
                break
    if any(
        point.selection_status == "conflicted"
        and (dates[0] if dates else run.target_business_date)
        <= point.period_end
        <= run.target_business_date
        for point in points
    ):
        return {
            "dates": [],
            "basis": "calendar_source_conflict",
            "status": "unavailable",
            "provenance": proof,
        }
    return {
        "dates": dates,
        "basis": basis if dates else "independent_calendar_unavailable",
        "status": "available" if len(dates) == 120 else "unavailable",
        "provenance": proof,
    }


def formula_requirements(
    rules: ContextProjectionRules,
    selector: ModelInputSelector,
    periods: dict[str, str | None],
) -> tuple[dict[str, int], list[dict[str, Any]]]:
    counts: dict[str, int] = {}
    derived = []
    mappings = {
        "credit_impulse": ("CN_CREDIT_IMPULSE", {"CN_SF_TOTAL": 24, "CN_GDP": 8}),
        "dr007_policy_spread": ("CN_DR007_POLICY_SPREAD", {"CN_DR007": 1, "CN_OMO_7D_RATE": 1}),
        "loan_monthly_change": ("CN_LOAN_STRUCTURE", {"CN_LOAN_STRUCTURE": 2}),
        "omo_net_injection": ("CN_OMO_7D_AMOUNT", {"CN_OMO_7D_AMOUNT": 1}),
        "order_inventory_spread": (
            "CN_ORDER_INVENTORY_SPREAD",
            {"CN_PMI_ACTIVITY": 1, "CN_PMI_INVENTORY": 1},
        ),
        "production_order_spread": ("CN_PRODUCTION_ORDER_SPREAD", {"CN_PMI_ACTIVITY": 1}),
        "real_inventory_approximation": (
            "CN_REAL_FINISHED_GOODS_INVENTORY_PROXY",
            {"CN_FINISHED_GOODS_INVENTORY": 1, "CN_PPI": 1},
        ),
        "ust_2s10s_spread": (
            "UST_2S10S_SPREAD",
            {"UST2Y_NOMINAL_YIELD": 1, "UST10Y_NOMINAL_YIELD": 1},
        ),
    }
    for name, version in rules.formula_versions.items():
        metric, needs = mappings[name]
        needs = dict(needs)
        if name == "credit_impulse":
            gdp_end = periods.get("CN_GDP")
            if (
                version in {"credit-impulse-rolling-share-v0001", "credit-impulse-ytd-flow-v0002"}
                and _reported_count(
                    selector, "CN_GDP", {"aggregate": "total", "measure": "nominal_quarterly_level"}
                )
                < 8
                and gdp_end is not None
                and not preceding_periods(gdp_end, 8)[0].endswith("Q1")
            ):
                needs["CN_GDP"] += 1
            sf_end = periods.get("CN_SF_TOTAL")
            if (
                version == "credit-impulse-ytd-flow-v0002"
                and _reported_count(selector, "CN_SF_TOTAL", {"measure": "monthly_increment"}) < 24
                and sf_end is not None
                and not preceding_periods(sf_end, 24)[0].endswith("-01")
            ):
                needs["CN_SF_TOTAL"] += 1
        for source, count in needs.items():
            counts[source] = max(counts.get(source, 1), count)
        derived.append(
            {"metric_id": metric, "formula_version": version, "required_input_periods": needs}
        )
    return counts, derived


def _reported_count(selector: ModelInputSelector, metric: str, dimensions: dict[str, str]) -> int:
    return sum(
        point.dimensions == dimensions
        and point.selection_status == "selected"
        and point.value_state is EvidenceValueState.REPORTED_VALUE
        and point.selected_value is not None
        and any(
            claim.claim_id == point.selected_claim_id
            and claim.certification_status == "certified"
            and claim.quality_status == "validated"
            for claim in point.claims
        )
        for point in selector.series(metric)
    )


def preceding_periods(period: str, count: int) -> tuple[str, ...]:
    if count == 1:
        return (period,)
    if "-Q" in period:
        year, quarter = period.split("-Q")
        last = int(year) * 4 + int(quarter) - 1
        return tuple(
            f"{ordinal // 4:04d}-Q{ordinal % 4 + 1}"
            for ordinal in range(last - count + 1, last + 1)
        )
    year, month = period[:7].split("-")
    last = int(year) * 12 + int(month) - 1
    return tuple(
        f"{ordinal // 12:04d}-{ordinal % 12 + 1:02d}"
        for ordinal in range(last - count + 1, last + 1)
    )
