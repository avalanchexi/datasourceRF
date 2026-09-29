"""Whether each selected source claim can be adopted: the family rechecks in one place.

A claim is adoptable when what it states still agrees with its original, a news rule's
matched quote, or its registered contract, and the delivery or announcement it belongs to
kept all its members. This module only rechecks: the points come already selected (by the
evidence repository, or re-selected at a target day by the projection), and which points
to recheck is the caller's choice -- retrieval passes the periods it can adopt, the
projection the whole visible series.

Built-in catalogs predate the registered originals and are not rechecked, except that a
core close must still name its source. The family functions themselves live with their
sources; this module only decides which one a metric answers to.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from pring_cycle.catalog_registry import BUILTIN_CATALOG_VERSIONS
from pring_cycle.evidence import AsOfMode, EvidenceRepository, MetricSeriesPoint
from pring_cycle.interbank_evidence import INTERBANK_METRICS, interbank_claims_matching_acquisitions
from pring_cycle.news_rules import news_claims_matching_quotes
from pring_cycle.official_context import (
    OFFICIAL_CONTEXT_INTEGRITY_METRICS,
    official_claims_matching_acquisitions,
)
from pring_cycle.official_lpr import lpr_claims_matching_acquisitions
from pring_cycle.published_events import select_published_rrr_events
from pring_cycle.source_adapters import (
    CORE_API_IDENTITIES,
    CoreInputValidator,
    selected_core_claim_is_valid,
)
from pring_cycle.treasury_context import TREASURY_METRICS, treasury_claims_matching_acquisitions
from pring_cycle.tushare_context import (
    MARKET_INDEX_IDENTITIES,
    parse_market_index_acquisition,
    parse_valuation_acquisition,
    tushare_claims_matching_acquisitions,
)
from pring_cycle.warrant_inputs import select_warrant_inputs

Points = Mapping[str, tuple[MetricSeriesPoint, ...]]


def core_identity_holds(metric_id: str, point: MetricSeriesPoint) -> bool:
    """A core close names its registered source and unit; checked for every catalog."""
    return selected_core_claim_is_valid(metric_id, point)


@dataclass(frozen=True)
class MetricAdoption:
    """One metric's selected claims after the recheck.

    ``rechecked`` says a family recheck ran; without one every selected claim is
    adoptable (a core close still has to name its source). ``decides_members`` says the
    family chose the members itself -- the latest complete warrant delivery, the whole RRR
    announcement -- so ``missing_members`` is its answer and no member rule applies on top.
    ``selected_members`` are the claims it chose, in its order, and ``missing_by_period``
    what each warrant day lacks (symbol by symbol).
    """

    adoptable: frozenset[str]
    not_adoptable: frozenset[str]
    rechecked: bool = False
    decides_members: bool = False
    selected_members: tuple[str, ...] = ()
    missing_members: tuple[str, ...] = ()
    missing_by_period: Mapping[str, tuple[str, ...]] = field(default_factory=dict)


_UNCHECKED = MetricAdoption(frozenset(), frozenset())


@dataclass(frozen=True)
class AdoptionResult:
    by_metric: Mapping[str, MetricAdoption] = field(default_factory=dict)

    def __getitem__(self, metric_id: str) -> MetricAdoption:
        return self.by_metric.get(metric_id, _UNCHECKED)

    def adoptable(self, metric_id: str) -> frozenset[str]:
        return self[metric_id].adoptable


@dataclass(frozen=True)
class _Family:
    """A family's metrics and its recheck.

    ``valid`` rechecks the claims of all the family's metrics together and returns those
    that hold; ``members`` instead chooses each metric's members itself and answers whole.
    """

    owns: Callable[[str], bool]
    valid: Callable[[Points], set[str]] | None = None
    members: Callable[[tuple[MetricSeriesPoint, ...], str | None], MetricAdoption] | None = None


class ClaimAdoption:
    """Recheck selected claims for one definition version at one evaluation instant.

    ``mode`` is the as-of mode the points were selected under; it orders warrant
    deliveries.
    """

    def __init__(
        self,
        repository: EvidenceRepository,
        *,
        definition_version: str,
        mode: AsOfMode = AsOfMode.SYSTEM,
    ) -> None:
        self._repository = repository
        self._version = definition_version
        self._mode = mode
        self._registered = definition_version not in BUILTIN_CATALOG_VERSIONS

    def check(self, points_by_metric: Points, *, period: str | None = None) -> AdoptionResult:
        """Recheck each metric's selected claims; metrics of one family are checked together.

        ``period`` is the one day warrants are selected for, even with no points on it;
        without it each day the points hold is selected on its own.
        """
        results: dict[str, MetricAdoption] = {}
        valid: dict[str, set[str]] = {}
        owned: set[str] = set()
        for family in self._families():
            metrics = {m: points for m, points in points_by_metric.items() if family.owns(m)}
            if not metrics:
                continue
            owned.update(metrics)
            if family.members is not None:
                for metric_id, points in metrics.items():
                    results[metric_id] = family.members(points, period)
                continue
            assert family.valid is not None
            claims = family.valid(metrics)
            for metric_id in metrics:
                # A metric two families own must pass both.
                valid[metric_id] = valid[metric_id] & claims if metric_id in valid else claims
        for metric_id, points in points_by_metric.items():
            if metric_id in results:
                continue
            selected = frozenset(_selected(points))
            if metric_id in CORE_API_IDENTITIES:
                identity = {
                    point.selected_claim_id
                    for point in points
                    if point.selected_claim_id is not None and core_identity_holds(metric_id, point)
                }
                valid[metric_id] = valid.get(metric_id, identity) & identity
            adoptable = selected & valid[metric_id] if metric_id in valid else selected
            results[metric_id] = MetricAdoption(
                adoptable,
                selected - adoptable,
                rechecked=metric_id in owned,
            )
        return AdoptionResult(results)

    def _families(self) -> tuple[_Family, ...]:
        if not self._registered:
            return ()
        repository, version = self._repository, self._version

        def core(points_by_metric: Points) -> set[str]:
            validator = CoreInputValidator(repository, tuple(_selected(_all(points_by_metric))))
            return {
                point.selected_claim_id
                for metric_id, points in points_by_metric.items()
                for point in points
                if point.selected_claim_id is not None and validator.is_valid(metric_id, point)
            }

        def tushare(
            parse: Callable[..., Any] | None = None,
        ) -> Callable[[Points], set[str]]:
            def check(points_by_metric: Points) -> set[str]:
                points = tuple(_all(points_by_metric))
                if parse is None:
                    return tushare_claims_matching_acquisitions(
                        repository, points, definition_version=version
                    )
                return tushare_claims_matching_acquisitions(
                    repository, points, definition_version=version, parse=parse
                )

            return check

        def quoted(points_by_metric: Points) -> set[str]:
            return news_claims_matching_quotes(repository.database_path, points_by_metric)

        return (
            _Family(lambda m: m in CORE_API_IDENTITIES, core),
            _Family(
                lambda m: m == "CN_USDCNY_ECB_REFERENCE_CROSS",
                lambda points_by_metric: repository.source_claims_matching_registered_contract(
                    tuple(_selected(_all(points_by_metric))), definition_version=version
                ),
            ),
            _Family(
                lambda m: m == "CN_LPR_1Y_5Y",
                # The announcement's original, or a news rule's matched quote.
                lambda points_by_metric: (
                    lpr_claims_matching_acquisitions(
                        repository,
                        tuple(p for p in _all(points_by_metric) if p.selected_claim_id is not None),
                    )
                    | quoted(points_by_metric)
                ),
            ),
            _Family(
                lambda m: m in OFFICIAL_CONTEXT_INTEGRITY_METRICS,
                # An official original, a TuShare delivery, or a news rule's matched quote.
                lambda points_by_metric: (
                    official_claims_matching_acquisitions(
                        repository, points_by_metric, definition_version=version
                    )
                    | quoted(points_by_metric)
                ),
            ),
            _Family(
                lambda m: m in INTERBANK_METRICS,
                lambda points_by_metric: interbank_claims_matching_acquisitions(
                    repository, points_by_metric, definition_version=version
                ),
            ),
            _Family(
                lambda m: m in TREASURY_METRICS,
                lambda points_by_metric: treasury_claims_matching_acquisitions(
                    repository, points_by_metric, definition_version=version
                ),
            ),
            _Family(lambda m: m == "CN_MARGIN_BALANCE", tushare()),
            _Family(
                lambda m: m in MARKET_INDEX_IDENTITIES, tushare(parse_market_index_acquisition)
            ),
            _Family(lambda m: m == "CN_INDEX_VALUATION", tushare(parse_valuation_acquisition)),
            _Family(
                lambda m: m == "CN_RRR_EVENT", members=lambda points, _period: self._rrr(points)
            ),
            _Family(lambda m: m == "CN_FUTURES_WARRANTS", members=self._warrants),
        )

    def _warrants(
        self, points: tuple[MetricSeriesPoint, ...], period: str | None
    ) -> MetricAdoption:
        """Each symbol's latest visible delivery, whole or not at all, day by day."""
        adoptable: list[str] = []
        not_adoptable: set[str] = set()
        missing: dict[str, tuple[str, ...]] = {}
        periods = (period,) if period is not None else sorted({p.period_end for p in points})
        for day in periods:
            selection = select_warrant_inputs(
                self._repository,
                points,
                period=day,
                mode=self._mode,
                definition_version=self._version,
            )
            adoptable.extend(selection.selected_claim_ids)
            not_adoptable.update(selection.incomplete_claim_ids)
            if selection.missing_members:
                missing[day] = selection.missing_members
        return MetricAdoption(
            frozenset(adoptable),
            frozenset(not_adoptable),
            rechecked=True,
            decides_members=True,
            selected_members=tuple(adoptable),
            missing_members=tuple(member for members in missing.values() for member in members),
            missing_by_period=missing,
        )

    def _rrr(self, points: tuple[MetricSeriesPoint, ...]) -> MetricAdoption:
        """Every member of an official announcement, or each news member's own quote."""
        selection = select_published_rrr_events(self._repository, points)
        return MetricAdoption(
            frozenset(selection.selected_claim_ids),
            frozenset(selection.incomplete_claim_ids),
            rechecked=True,
            decides_members=True,
            selected_members=selection.selected_claim_ids,
            missing_members=selection.missing_members,
        )


def _all(points_by_metric: Points) -> Iterable[MetricSeriesPoint]:
    return (point for points in points_by_metric.values() for point in points)


def _selected(points: Iterable[MetricSeriesPoint]) -> Iterable[str]:
    return (point.selected_claim_id for point in points if point.selected_claim_id is not None)
