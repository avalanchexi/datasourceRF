"""Every metric with an official family can name the page its values fall back to.

When TuShare has not published a period, the value becomes a gap and gap retrieval reaches for
the official page. That only happens when the gap carries a source URL, which comes from the
metric's source candidates. A metric in an official family without one cannot fall back at all,
however well the rest of the path works.
"""

from __future__ import annotations

from pring_cycle.catalog import metric_catalog
from pring_cycle.source_families import OFFICIAL_CONTEXT_FAMILIES

# These seven have no official page to fall back to, so a period TuShare has not published
# stays a gap. Five of them have a page that the 2026-09-17 probe confirmed carries their
# series; they are still listed here because adding it needs a new catalog version, the v0003
# catalog being pinned by canonical hash. Money supply and GDP are here for a different reason:
# no page reached carried either series at all.
WITHOUT_A_FALLBACK_PAGE = frozenset(
    {
        "CN_CPI_HEADLINE",
        "CN_PPI",
        "CN_PMI_ACTIVITY",
        "CN_PMI_INVENTORY",
        "CN_PMI_PRICES",
        "CN_M1_M2",
        "CN_GDP",
    }
)


def official_family_metrics() -> frozenset[str]:
    return frozenset(
        metric_id
        for family in OFFICIAL_CONTEXT_FAMILIES.values()
        for metric_id in family.metric_ids
    )


def test_the_metrics_that_cannot_fall_back_are_the_ones_on_record() -> None:
    """Pins which metrics have no official page, so the list cannot shrink unnoticed.

    Adding a page to any of these needs a new catalog version, because the v0003 catalog is
    pinned by canonical hash; see `verification-2527-probe-20260917.md` and ticket 25.
    """
    candidates = {
        definition.metric_id: tuple(
            candidate
            for candidate in definition.source_candidates
            if candidate.startswith("https://")
        )
        for definition in metric_catalog()
    }
    unreachable = {
        metric_id for metric_id in official_family_metrics() if not candidates.get(metric_id)
    }
    assert unreachable == WITHOUT_A_FALLBACK_PAGE


def test_a_metric_shares_the_official_page_of_the_family_it_belongs_to() -> None:
    """Two metrics parsed out of one document must point at that one document."""
    candidates = {
        definition.metric_id: tuple(
            candidate
            for candidate in definition.source_candidates
            if candidate.startswith("https://")
        )
        for definition in metric_catalog()
    }
    for family in OFFICIAL_CONTEXT_FAMILIES.values():
        pages = {
            candidates[metric_id] for metric_id in family.metric_ids if candidates.get(metric_id)
        }
        assert len(pages) <= 1, f"{family.provider} family disagrees on its page: {pages}"
