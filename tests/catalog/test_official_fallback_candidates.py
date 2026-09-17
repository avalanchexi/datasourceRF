"""Metrics parsed out of one official document point at that one document.

When TuShare has not published a period, the value becomes a gap and gap retrieval reaches for
the official page named by the metric's source candidates. Two metrics read from the same
document disagreeing about its address would send one of them somewhere its value is not.

Which metrics currently have no official page at all is recorded in ticket 25, not asserted
here: a test that recomputes today's catalogue and compares it to a hand-copied list of the
same constants only proves the constants are unchanged.
"""

from __future__ import annotations

from pring_cycle.catalog import metric_catalog
from pring_cycle.source_families import OFFICIAL_CONTEXT_FAMILIES


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
