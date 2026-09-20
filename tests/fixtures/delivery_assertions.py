"""Assertions for selected delivery identity at public evidence/output boundaries."""

from collections.abc import Mapping, Sequence
from typing import Any

from pring_cycle.evidence import MetricSeriesPoint


def assert_certified_points(points: Sequence[MetricSeriesPoint], provider: str) -> None:
    assert points
    for point in points:
        (selected,) = [c for c in point.claims if c.claim_id == point.selected_claim_id]
        assert (selected.provider, selected.certification_status) == (provider, "certified")


def assert_certified_rows(rows: Sequence[Mapping[str, Any]], provider: str) -> None:
    assert rows
    for row in rows:
        (selected,) = [claim for claim in row["claims"] if claim["selected"]]
        assert (selected["provider"], selected["certification_status"]) == (provider, "certified")
        assert row["certification_status"] == "certified"
