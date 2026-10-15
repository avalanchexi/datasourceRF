from __future__ import annotations

import calendar
import hashlib
import json
import re
from collections.abc import Callable, Iterable, Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request
from zoneinfo import ZoneInfo

from pring_cycle.acquisition import (
    Acquired,
    AcquisitionReceipt,
    AcquisitionRepository,
    CandidateSkipped,
    SourceFailed,
    failed_step,
    owning_run,
    receipt_key,
    utc_now,
)
from pring_cycle.acquisition_outcome import (
    NOT_ATTEMPTED,
    SUCCEEDED,
    attempt_details,
    capture_failure,
    ingest_failure,
)
from pring_cycle.artifacts import store_artifact
from pring_cycle.catalog import METRIC_CATALOG_VERSION, metric_definition
from pring_cycle.catalog_registry import BUILTIN_CATALOG_VERSIONS
from pring_cycle.evidence import (
    AsOfMode,
    EvidenceRepository,
    EvidenceValueState,
    MetricSeriesPoint,
    SourceClaimInput,
    publication_times,
)
from pring_cycle.http_transport import open_no_redirects as urlopen
from pring_cycle.official_listing import (
    RRR_CHRONICLE_LISTING,
    ChronicleEntry,
    ListingNotCovered,
    chronicle_entries,
    chronicle_next_page,
    entry_days,
    listing_entries,
    next_listing_page,
    reaches_back,
    release_listing,
    release_titles,
    release_urls,
)
from pring_cycle.release_calendar import month_bounds
from pring_cycle.runtime import RuntimePaths
from pring_cycle.source_families import OFFICIAL_CONTEXT_FAMILIES
from pring_cycle.storage import database_connection
from pring_cycle.summary_cutoff import SummaryCutoff, day_end
from pring_cycle.tushare_context import (
    ContextScalar,
    parse_cpi_acquisition,
    parse_gdp_acquisition,
    parse_money_acquisition,
    parse_pmi_acquisition,
    parse_ppi_acquisition,
    parse_social_financing_total_acquisition,
    tushare_claims_matching_acquisitions,
)

MAX_OFFICIAL_CONTEXT_BYTES = 4_000_000

_PROVIDERS = {
    family: (descriptor.provider, descriptor.host)
    for family, descriptor in OFFICIAL_CONTEXT_FAMILIES.items()
}
# The path prefixes each family's releases and listings are registered under.
_PATHS = {
    family: tuple(prefix for _host, prefix in descriptor.hosts)
    for family, descriptor in OFFICIAL_CONTEXT_FAMILIES.items()
}

_SOCIAL_FINANCING_COMPONENTS = {
    "社会融资规模": "total",
    "人民币贷款": "renminbi_loans",
    "外币贷款（折合人民币）": "foreign_currency_loans_rmb",
    "委托贷款": "entrusted_loans",
    "信托贷款": "trust_loans",
    "未贴现银行承兑汇票": "undiscounted_bank_acceptances",
    "企业债券": "corporate_bonds",
    "政府债券": "government_bonds",
    "非金融企业境内股票融资": "nonfinancial_enterprise_equity",
    "存款类金融机构资产支持证券": "depository_abs",
    "贷款核销": "loan_writeoffs",
}

_LOAN_STRUCTURE_ROWS = {
    ("住户", "合计"): ("household", "total"),
    ("住户", "短期"): ("household", "short_term"),
    ("住户", "中长期"): ("household", "long_term"),
    ("企（事）业单位", "合计"): ("enterprise", "total"),
    ("企（事）业单位", "短期"): ("enterprise", "short_term"),
    ("企（事）业单位", "中长期"): ("enterprise", "long_term"),
    ("企（事）业单位", "票据融资"): ("enterprise", "bill_financing"),
    ("非银行业金融机构", "合计"): ("nonbank_financial", "total"),
    ("人民币各项贷款", "合计"): ("all_rmb_loans", "total"),
}

_LIVE_SOCIAL_FINANCING_COMPONENTS = {
    "renminbi_loans": (
        "对实体经济发放的人民币贷款余额",
        "对实体经济发放的人民币贷款",
    ),
    "foreign_currency_loans_rmb": (
        "对实体经济发放的外币贷款折合人民币余额",
        "对实体经济发放的外币贷款折合人民币",
    ),
    "entrusted_loans": ("委托贷款余额", "委托贷款"),
    "trust_loans": ("信托贷款余额", "信托贷款"),
    "undiscounted_bank_acceptances": (
        "未贴现的银行承兑汇票余额",
        "未贴现的银行承兑汇票",
    ),
    "corporate_bonds": ("企业债券余额", "企业债券"),
    "government_bonds": ("政府债券余额", "政府债券"),
    "nonfinancial_enterprise_equity": (
        "非金融企业境内股票余额",
        "非金融企业境内股票融资",
    ),
}

_FAMILY_METRICS = {
    family: frozenset(descriptor.metric_ids)
    for family, descriptor in OFFICIAL_CONTEXT_FAMILIES.items()
}

OFFICIAL_CONTEXT_INTEGRITY_METRICS = frozenset(
    metric_id
    for family in (
        "nbs_gdp",
        "nbs_pmi",
        "nbs_core_cpi",
        "nbs_ppi",
        "nbs_industrial_value_added",
        "nbs_industrial_finance",
        "nbs_capacity_utilization",
        "pbc_money",
        "pbc_social_financing",
        "pbc_loan_structure",
        "pbc_tool_liquidity_monthly",
        "pbc_omo_notice",
    )
    for metric_id in OFFICIAL_CONTEXT_FAMILIES[family].metric_ids
)


@dataclass(frozen=True)
class ParsedOfficialContextRelease:
    family: str
    provider: str
    release_event_id: str
    period: str
    release_at: datetime | None
    public_available_at: datetime | None
    source_url: str
    scalars: tuple[ContextScalar, ...]


@dataclass(frozen=True)
class FetchedOfficialContextDocument:
    content: bytes
    media_type: str
    final_url: str
    http_status: int


@dataclass(frozen=True)
class OfficialContextIngestionResult:
    status: str
    family: str
    release_event_id: str
    period: str
    artifact_hash: str
    observation_ids: tuple[str, ...]
    claim_ids: tuple[str, ...]
    metric_ids: tuple[str, ...]
    observation_count: int


@dataclass(frozen=True)
class OfficialContextSmokeResult:
    status: str
    family: str
    provider: str
    final_url: str
    period: str
    release_at: datetime | None
    metric_ids: tuple[str, ...]
    first_period: str
    last_period: str
    observation_count: int
    content_hash: str
    byte_count: int
    http_status: int
    network_requests: int


class _OfficialHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.tables: list[list[tuple[str, ...]]] = []
        self._table: list[tuple[str, ...]] | None = None
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag == "table" and self._table is None:
            self._table = []
        elif tag == "tr" and self._table is not None and self._row is None:
            self._row = []
        elif tag in {"th", "td"} and self._row is not None and self._cell is None:
            self._cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag in {"th", "td"} and self._cell is not None and self._row is not None:
            self._row.append(_normalized_text(" ".join(self._cell)))
            self._cell = None
        elif tag == "tr" and self._row is not None and self._table is not None:
            if self._row:
                self._table.append(tuple(self._row))
            self._row = None
        elif tag == "table" and self._table is not None:
            if self._table:
                self.tables.append(self._table)
            self._table = None

    def handle_data(self, data: str) -> None:
        self.parts.append(data)
        if self._cell is not None:
            self._cell.append(data)


def parse_official_context_document(
    content: bytes,
    *,
    family: str,
    source_url: str,
    expected_period: str,
    fetched_at: datetime,
) -> ParsedOfficialContextRelease:
    provider = _validate_source_identity(family, source_url)
    if fetched_at.tzinfo is None:
        raise ValueError("official_context_fetched_at_must_be_timezone_aware")
    if not content or len(content) > MAX_OFFICIAL_CONTEXT_BYTES:
        raise ValueError("official_context_document_size_invalid")
    document = _decode_document(content)
    parser = _OfficialHtmlParser()
    parser.feed(document)
    text = _normalized_text(" ".join(parser.parts))
    source_timezone = ZoneInfo("Asia/Shanghai")
    published = _release_timestamp(text)
    release_at, public_at = publication_times(published, source_timezone)
    if release_at is not None:
        release_at = release_at.astimezone(ZoneInfo("Asia/Shanghai"))
        public_at = release_at
    if release_at is not None and fetched_at < release_at:
        raise ValueError("official_context_fetched_before_release")
    if (
        published is not None
        and not isinstance(published, datetime)
        and fetched_at.astimezone(source_timezone).date() < published
    ):
        raise ValueError("official_context_fetched_before_release")
    if not _period_is_identified(text, expected_period):
        raise ValueError("official_context_period_identity_mismatch")
    scalars = _parse_family(family, parser.tables, text, expected_period, release_at)
    return ParsedOfficialContextRelease(
        family=family,
        provider=provider,
        release_event_id=f"official:{family}:{expected_period}:{hashlib.sha256(content).hexdigest()}",
        period=expected_period,
        release_at=release_at,
        public_available_at=public_at,
        source_url=source_url,
        scalars=scalars,
    )


def official_family_for_metrics(metric_ids: tuple[str, ...]) -> str:
    requested = frozenset(metric_ids)
    if not requested:
        raise ValueError("official_context_metrics_required")
    matches = [family for family, metrics in _FAMILY_METRICS.items() if requested <= metrics]
    if len(matches) != 1:
        raise ValueError("official_context_metric_family_unknown")
    return matches[0]


def official_family_metrics(
    family: str, *, definition_version: str, database_path: Path | None = None
) -> tuple[str, ...]:
    """The official family's metrics this catalog defines (lookback fetch gaps 02)."""
    defined = []
    for metric_id in OFFICIAL_CONTEXT_FAMILIES[family].metric_ids:
        try:
            metric_definition(
                metric_id, definition_version=definition_version, database_path=database_path
            )
        except KeyError as error:
            if error.args != ("unknown_metric_id",):
                raise
            continue
        defined.append(metric_id)
    return tuple(defined)


def parse_official_acquisition(
    receipt: AcquisitionReceipt, raw: bytes
) -> ParsedOfficialContextRelease:
    """Rebuild the complete official release recorded by an acquisition."""
    if (
        receipt.state != "validated"
        or receipt.api_name not in {"document_import", "official_http_get"}
        or receipt.parser_version != "official-context-parser-v0004"
        or receipt.fields != ""
        or receipt.received_at is None
    ):
        raise ValueError("official_acquisition_identity_mismatch")
    parsed = parse_official_context_document(
        raw,
        family=receipt.parameters["family"],
        source_url=receipt.parameters["source_url"],
        expected_period=receipt.parameters["period"],
        fetched_at=receipt.received_at,
    )
    if receipt.provider != parsed.provider:
        raise ValueError("official_acquisition_provider_mismatch")
    normalized = json.dumps(
        asdict(parsed),
        default=str,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    if hashlib.sha256(normalized).hexdigest() != receipt.normalized_hash:
        raise ValueError("official_acquisition_normalized_mismatch")
    return parsed


# Rebuilding an announcement is a pure function of its receipt and the bytes just read,
# so repeated consumers (each replay cutoff) reuse it. The key includes the SHA-256 of
# those bytes: damaged or replaced originals never match an earlier rebuild.
_OFFICIAL_REBUILDS: dict[tuple[object, ...], ParsedOfficialContextRelease | None] = {}
_OFFICIAL_REBUILD_LIMIT = 4096


def _rebuilt_official_acquisition(
    receipt: AcquisitionReceipt, raw: bytes
) -> ParsedOfficialContextRelease | None:
    key = (receipt_key(receipt), hashlib.sha256(raw).hexdigest())
    if key in _OFFICIAL_REBUILDS:
        return _OFFICIAL_REBUILDS[key]
    rebuilt: ParsedOfficialContextRelease | None
    try:
        rebuilt = parse_official_acquisition(receipt, raw)
        if rebuilt.family == "nbs_gdp":
            _validate_registered_gdp_table(raw, rebuilt.period)
    except (LookupError, TypeError, ValueError):
        rebuilt = None
    if len(_OFFICIAL_REBUILDS) >= _OFFICIAL_REBUILD_LIMIT:
        _OFFICIAL_REBUILDS.pop(next(iter(_OFFICIAL_REBUILDS)))
    _OFFICIAL_REBUILDS[key] = rebuilt
    return rebuilt


def official_claims_matching_acquisitions(
    repository: EvidenceRepository,
    points_by_metric: Mapping[str, tuple[MetricSeriesPoint, ...]],
    *,
    definition_version: str,
) -> set[str]:
    """Match selected macro values to every linked official announcement."""
    selected_points = {
        point.selected_claim_id: (metric_id, point)
        for metric_id, points in points_by_metric.items()
        for point in points
        if point.selected_claim_id is not None
    }
    checked: dict[str, ParsedOfficialContextRelease | None] = {}
    valid_claim_ids: set[str] = set()
    for claim_id, acquisitions in repository.source_claim_acquisitions_many(
        tuple(selected_points)
    ).items():
        valid = bool(acquisitions)
        metric_id, point = selected_points[claim_id]
        claim = next((item for item in point.claims if item.claim_id == claim_id), None)
        for acquisition in acquisitions:
            acquisition_id = acquisition.receipt.acquisition_id
            if acquisition_id not in checked:
                checked[acquisition_id] = _rebuilt_official_acquisition(
                    acquisition.receipt, acquisition.raw
                )
            parsed = checked[acquisition_id]
            if (
                parsed is None
                or claim is None
                or claim.source_reference
                != f"{parsed.source_url}#sha256={acquisition.receipt.raw_hash}"
                or (
                    (claim.release_at is not None or claim.parsed_public_available_at is not None)
                    and (claim.release_at, claim.parsed_public_available_at)
                    != (parsed.release_at, parsed.public_available_at)
                )
                or not any(
                    scalar.metric_id == metric_id
                    and scalar.dimensions == point.dimensions
                    and scalar.value == point.selected_value
                    and scalar.period_start == point.period_start
                    and scalar.period_end == point.period_end
                    for scalar in parsed.scalars
                )
            ):
                valid = False
                break
        if valid:
            valid_claim_ids.add(claim_id)
    if definition_version not in BUILTIN_CATALOG_VERSIONS:
        for metric_id, parse_delivery in (
            ("CN_PPI", parse_ppi_acquisition),
            ("CN_CPI_HEADLINE", parse_cpi_acquisition),
            ("CN_PMI_ACTIVITY", parse_pmi_acquisition),
            ("CN_PMI_INVENTORY", parse_pmi_acquisition),
            ("CN_PMI_PRICES", parse_pmi_acquisition),
            ("CN_M1_M2", parse_money_acquisition),
            ("CN_SF_TOTAL", parse_social_financing_total_acquisition),
            ("CN_GDP", parse_gdp_acquisition),
        ):
            points = points_by_metric.get(metric_id, ())
            if not points:
                continue
            delivered = tushare_claims_matching_acquisitions(
                repository,
                points,
                definition_version=definition_version,
                parse=parse_delivery,
            )
            valid_claim_ids.update(
                repository.source_claims_matching_registered_contract(
                    tuple(delivered), definition_version=definition_version
                )
            )
        mapped_claim_ids = tuple(
            claim_id
            for claim_id, (metric_id, point) in selected_points.items()
            if metric_id == "CN_CAPACITY_UTILIZATION"
            and point.period_end.endswith("-03-31")
            and point.dimensions.get("measure") == "ytd_rate"
        )
        valid_mappings = repository.source_claims_matching_registered_contract(
            mapped_claim_ids, definition_version=definition_version
        )
        valid_claim_ids.difference_update(set(mapped_claim_ids) - valid_mappings)
    return valid_claim_ids


def official_gdp_quarters_matching_baselines(
    repository: EvidenceRepository,
    quarter_values: Mapping[str, float],
) -> set[str]:
    """Validate YTD differences against each selected release's nominal quarter.

    This is a constraint on cross-release arithmetic, not a new observed metric.
    Callers must also validate every selected YTD parent, including the baseline.
    """
    comparable: set[str] = set()
    for claim_id, acquisitions in repository.source_claim_acquisitions_many(
        tuple(quarter_values)
    ).items():
        if not acquisitions:
            continue
        for acquisition in acquisitions:
            try:
                parsed = parse_official_acquisition(acquisition.receipt, acquisition.raw)
                if parsed.family != "nbs_gdp":
                    break
                _validate_registered_gdp_table(acquisition.raw, parsed.period)
                parser = _OfficialHtmlParser()
                parser.feed(_decode_document(acquisition.raw))
                table = _table_with_first_column_members(
                    parser.tables, {"GDP", "第一产业", "第二产业", "第三产业"}
                )
                row = _unique_first_cell_row(table, "GDP")
                announced_quarter = _bounded_number(row[1], minimum=0)
            except (LookupError, TypeError, ValueError):
                break
            if announced_quarter != quarter_values[claim_id]:
                break
        else:
            comparable.add(claim_id)
    return comparable


def ingest_official_context_document(
    paths: RuntimePaths,
    content: bytes,
    *,
    family: str,
    source_url: str,
    expected_period: str,
    fetched_at: datetime,
    media_type: str = "text/html",
    definition_version: str = METRIC_CATALOG_VERSION,
    clock: Callable[[], datetime] = utc_now,
) -> OfficialContextIngestionResult:
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)

    def parse(raw: bytes) -> ParsedOfficialContextRelease:
        _validate_html_media_type(media_type)
        return parse_official_context_document(
            raw,
            family=family,
            source_url=source_url,
            expected_period=expected_period,
            fetched_at=fetched_at,
        )

    acquired = acquisitions.capture(
        provider=_validate_source_identity(family, source_url),
        api_name="document_import",
        parameters={"source_url": source_url, "period": expected_period, "family": family},
        fields="",
        parser_version="official-context-parser-v0004",
        fetch=lambda: content,
        parse=parse,
        normalize=asdict,
        clock=clock,
        count_scalars=lambda release: len(release.scalars),
    )
    return ingest_acquired_official_release(
        paths, acquired, definition_version=definition_version, clock=clock
    )


def ingest_acquired_official_release(
    paths: RuntimePaths,
    acquired: Acquired[ParsedOfficialContextRelease],
    *,
    definition_version: str,
    clock: Callable[[], datetime] = utc_now,
    metric_ids: tuple[str, ...] | None = None,
    held_members: frozenset[str] = frozenset(),
) -> OfficialContextIngestionResult:
    """Store a validated release's claims; its receipt says whether they entered, and if not
    why (run findings 03: a contract refusal used to leave only a ValueError behind).

    ``held_members`` (``METRIC:{dimensions}``) are left out: another source delivered them.
    A page fetched for GDP's real growth also states nominal levels in their first release,
    which would contest the revised levels already held (run findings 2026-09-28, #12)."""
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    try:
        result = _ingest_acquired_official_release(
            paths,
            acquired,
            definition_version=definition_version,
            clock=clock,
            metric_ids=metric_ids,
            held_members=held_members,
        )
    except ValueError as error:
        # The contract refusing the values; a failure of this system storing them is no
        # refusal, and leaves the receipt without an ingest result (ticket 18).
        acquisitions.record_ingest_result(acquired.receipt.acquisition_id, error)
        raise
    acquisitions.record_ingest_result(acquired.receipt.acquisition_id, None)
    return result


def _ingest_acquired_official_release(
    paths: RuntimePaths,
    acquired: Acquired[ParsedOfficialContextRelease],
    *,
    definition_version: str,
    clock: Callable[[], datetime],
    metric_ids: tuple[str, ...] | None,
    held_members: frozenset[str] = frozenset(),
    record_attempt: bool = True,
) -> OfficialContextIngestionResult:
    parsed, receipt = acquired.value, acquired.receipt
    # Keep the original and its normalized full announcement intact for revalidation.
    # A retrieval scope asks for some of the release; the others of its family it states
    # that this catalog defines are stored with them, a rate beside its notice's amount,
    # components beside their total (lookback fetch gaps 02; run findings 10).
    if metric_ids is None:
        requested = admitted = frozenset(scalar.metric_id for scalar in parsed.scalars)
    else:
        requested = _official_metric_scope(parsed.family, metric_ids)
        admitted = requested | frozenset(
            official_family_metrics(
                parsed.family, definition_version=definition_version, database_path=paths.database
            )
        )
    scalars = tuple(
        scalar
        for scalar in parsed.scalars
        if scalar.metric_id in admitted
        and official_member(scalar.metric_id, scalar.dimensions) not in held_members
    )
    if not any(scalar.metric_id in requested for scalar in scalars):
        raise ValueError("official_context_requested_metrics_missing")
    if receipt.received_at is None or receipt.validated_at is None or receipt.raw_hash is None:
        raise ValueError("official_acquisition_incomplete")
    content = AcquisitionRepository(paths.database, paths.artifacts).read_content(
        receipt.acquisition_id, "raw"
    )
    if parsed.family == "nbs_gdp" and definition_version not in BUILTIN_CATALOG_VERSIONS:
        _validate_registered_gdp_table(content, parsed.period)
    artifact = store_artifact(
        paths.database, paths.artifacts, content, "text/html", parsed.source_url
    )
    source_reference = f"{parsed.source_url}#sha256={artifact.content_hash}"
    repository = EvidenceRepository(paths.database)
    # Publication uncertainty belongs to the whole revised announcement, including
    # revisions learned through a previously requested sibling metric.
    previous = [
        repository.latest_provider_claim(
            metric_id=scalar.metric_id,
            period_kind=scalar.period_kind,
            period_start=scalar.period_start,
            period_end=scalar.period_end,
            dimensions=scalar.dimensions,
            provider=parsed.provider,
        )
        for scalar in parsed.scalars
    ]
    same_document_previous = [
        repository.latest_provider_claim(
            metric_id=scalar.metric_id,
            period_kind=scalar.period_kind,
            period_start=scalar.period_start,
            period_end=scalar.period_end,
            dimensions=scalar.dimensions,
            provider=parsed.provider,
            source_reference=source_reference,
        )
        for scalar in parsed.scalars
    ]
    revision_without_new_time = any(
        prior is not None and prior.public_available_at is None for prior in same_document_previous
    ) or any(
        prior is not None
        and (
            prior.public_available_at is None
            or prior.value != scalar.value
            or prior.unit != scalar.unit
        )
        and (
            parsed.public_available_at is None
            or (
                prior.public_available_at is None and parsed.public_available_at <= prior.fetched_at
            )
            or (
                prior.public_available_at is not None
                and parsed.public_available_at <= prior.public_available_at
            )
        )
        for prior, scalar in zip(previous, parsed.scalars, strict=True)
    )
    public_at = None if revision_without_new_time else parsed.public_available_at
    release_at = None if revision_without_new_time else parsed.release_at
    release_event_id = parsed.release_event_id
    if public_at is None:
        release_event_id = f"unresolved-publication:{receipt.acquisition_id}"
    claims = tuple(
        SourceClaimInput(
            metric_id=scalar.metric_id,
            definition_version=definition_version,
            period_kind=scalar.period_kind,
            period_start=scalar.period_start,
            period_end=scalar.period_end,
            dimensions=scalar.dimensions,
            value=scalar.value,
            value_state=EvidenceValueState.REPORTED_VALUE,
            unit=scalar.unit,
            provider=parsed.provider,
            source_reference=source_reference,
            release_event_id=release_event_id,
            release_at=release_at,
            public_available_at=public_at,
            fetched_at=receipt.received_at,
            available_at=receipt.validated_at,
            certification_status=metric_definition(
                scalar.metric_id,
                definition_version=definition_version,
                database_path=paths.database,
            ).certification_status,
            quality_status="validated",
            acquisition_id=receipt.acquisition_id,
        )
        for scalar in scalars
    )
    stored = repository.append_source_claims(claims, availability_clock=clock)
    family = parsed.family
    expected_period = parsed.period
    metric_ids = tuple(sorted({scalar.metric_id for scalar in scalars}))
    for metric_id in metric_ids if record_attempt else ():
        repository.record_retrieval_attempt(
            metric_id=metric_id,
            channel="official_direct_candidate",
            outcome=SUCCEEDED,
            fetched_at=clock(),
            acquisition_ids=(receipt.acquisition_id,),
            safe_metadata=attempt_details(
                step="ingest",
                completeness="complete",
                artifact_hash=artifact.content_hash,
                family=family,
                period=expected_period,
                provider=parsed.provider,
                definition_version=definition_version,
            ),
        )
    return OfficialContextIngestionResult(
        status="stored_candidate",
        family=family,
        release_event_id=release_event_id,
        period=expected_period,
        artifact_hash=artifact.content_hash,
        observation_ids=tuple(item.observation_id for item in stored),
        claim_ids=tuple(item.claim_id for item in stored),
        metric_ids=metric_ids,
        observation_count=len(stored),
    )


def official_member(metric_id: str, dimensions: Mapping[str, str]) -> str:
    """A member's key as a run plan lists it among ``missing_members``."""
    return f"{metric_id}:{json.dumps(dict(dimensions), sort_keys=True)}"


def _official_metric_scope(family: str, metric_ids: tuple[str, ...] | None) -> frozenset[str]:
    requested = _FAMILY_METRICS[family] if metric_ids is None else frozenset(metric_ids)
    if not requested or not requested.issubset(_FAMILY_METRICS[family]):
        raise ValueError("official_context_metric_scope_invalid")
    return requested


@dataclass(frozen=True)
class RestoredOfficialRelease:
    acquisition_id: str
    period: str
    release_event_id: str
    metric_ids: tuple[str, ...]
    claim_ids: tuple[str, ...]


@dataclass(frozen=True)
class SkippedOfficialRelease:
    acquisition_id: str
    period: str
    reason: str


@dataclass(frozen=True)
class OfficialReprocessResult:
    status: str
    family: str
    definition_version: str
    metric_ids: tuple[str, ...]
    start: str
    end: str
    # Validated originals of the family read; those with nothing to restore are not listed.
    examined: int
    restored: tuple[RestoredOfficialRelease, ...]
    restored_claim_count: int
    skipped: tuple[SkippedOfficialRelease, ...]
    network_requests: int = 0


def reprocess_stored_official_releases(
    paths: RuntimePaths,
    *,
    metric_ids: tuple[str, ...],
    start: str,
    end: str,
    definition_version: str,
    clock: Callable[[], datetime] = utc_now,
) -> OfficialReprocessResult:
    """Store what stored official originals state of ``metric_ids`` and their ingest left out.

    An older ingest kept only the metrics a retrieval named, leaving the rest of the page
    out: an OMO notice's rate beside the amount asked for (audit ticket 09; fixed by
    lookback fetch gaps 02). Each validated original of the family is rebuilt and checked
    against its receipt as a run reads it, and today's ingest stores the members it states
    for periods ending within ``start``..``end`` that nothing holds. Nothing is requested.

    Only what cannot change a selection is restored, the rest is left to a run. A member is
    restored only when no claim of its source holds it, and only from an original that is
    the one source of everything its source states of the release: a claim stored now is
    the newest of its source, so restoring an older notice beside a revision already held
    would turn the selection back to it, and a revision held would make the ingest take the
    original for a revision itself. Such an original is skipped as
    ``revised_by_another_original``. A member another source delivered (of a like
    definition, ADR-0036) is not restated either, as the ingest never contests one; whether
    it can be adopted is a run's to judge, which fetches the page itself if not. A member
    restored is held by its source, so running it again stores nothing more.

    The claims tell the truth about their time: published when the source published it,
    fetched when the original was, and available to this system only from now (``clock``),
    so a SYSTEM cutoff before the reprocessing never sees them. Nothing is retrieved, so no
    retrieval attempt is recorded, and the original's receipt keeps the ingest result it
    said once. The range keeps values retention removed before it out.
    """
    family = official_family_for_metrics(metric_ids)
    requested = frozenset(metric_ids)
    if not requested <= frozenset(
        official_family_metrics(
            family, definition_version=definition_version, database_path=paths.database
        )
    ):
        raise ValueError("official_reprocess_metric_undefined")
    start = _required_iso_date(start, "official_reprocess_range_invalid")
    end = _required_iso_date(end, "official_reprocess_range_invalid")
    if start > end:
        raise ValueError("official_reprocess_range_invalid")

    # The sources each member is delivered by; reprocessing adds none but the official one.
    evidence = EvidenceRepository(paths.database)
    providers: dict[tuple[str, str, str, str], set[str]] = {}
    for metric_id in sorted(requested):
        for point in evidence.metric_series(
            metric_id,
            mode=AsOfMode.SYSTEM,
            as_of=max(clock(), utc_now()),
            definition_version=definition_version,
        ):
            member = official_member(metric_id, point.dimensions)
            providers.setdefault(
                (member, point.period_start, point.period_end, metric_id), set()
            ).update(claim.provider for claim in point.claims)

    def delivered_elsewhere(scalar: ContextScalar, provider: str) -> bool:
        member = official_member(scalar.metric_id, scalar.dimensions)
        key = (member, scalar.period_start, scalar.period_end, scalar.metric_id)
        return bool(providers.get(key, set()) - {provider})

    receipts = AcquisitionRepository(paths.database, paths.artifacts)
    stored = receipts.validated_receipts(
        api_names=("document_import", "official_http_get"),
        parser_version="official-context-parser-v0004",
        parameters={"family": family},
    )
    restored: list[RestoredOfficialRelease] = []
    skipped: list[SkippedOfficialRelease] = []
    for receipt in stored:
        period = receipt.parameters.get("period", "")
        try:
            raw = receipts.read_receipt_content(receipt, "raw")
        except (LookupError, OSError, ValueError):
            skipped.append(SkippedOfficialRelease(receipt.acquisition_id, period, "raw_missing"))
            continue
        parsed = _rebuilt_official_acquisition(receipt, raw)
        if parsed is None:
            skipped.append(SkippedOfficialRelease(receipt.acquisition_id, period, "rebuild_failed"))
            continue
        # The reference the ingest gives the claims of this original.
        reference = f"{parsed.source_url}#sha256={receipt.raw_hash}"
        # Every original of its source each member stated is held by, in any version, as the
        # ingest reads them to tell a revision.
        held_by = {
            id(scalar): _provider_references(paths.database, scalar, parsed.provider)
            for scalar in parsed.scalars
        }
        missing = tuple(
            scalar
            for scalar in parsed.scalars
            if scalar.metric_id in requested
            and start <= scalar.period_end <= end
            and not held_by[id(scalar)]
            and not delivered_elsewhere(scalar, parsed.provider)
        )
        if not missing:
            continue
        if any(references - {reference} for references in held_by.values()):
            skipped.append(
                SkippedOfficialRelease(
                    receipt.acquisition_id, period, "revised_by_another_original"
                )
            )
            continue
        restoring = {official_member(s.metric_id, s.dimensions) for s in missing}
        others = [scalar for scalar in parsed.scalars if scalar not in missing]
        # The ingest leaves members out, not periods: one also stated for another period
        # would be stored beside the missing one.
        if any(official_member(s.metric_id, s.dimensions) in restoring for s in others):
            skipped.append(
                SkippedOfficialRelease(receipt.acquisition_id, period, "member_periods_mixed")
            )
            continue
        try:
            result = _ingest_acquired_official_release(
                paths,
                Acquired(parsed, receipt),
                definition_version=definition_version,
                clock=clock,
                metric_ids=tuple(sorted({scalar.metric_id for scalar in missing})),
                held_members=frozenset(official_member(s.metric_id, s.dimensions) for s in others),
                record_attempt=False,
            )
        except ValueError as error:
            skipped.append(
                SkippedOfficialRelease(
                    receipt.acquisition_id, period, f"ingest_refused:{str(error)[:200]}"
                )
            )
            continue
        restored.append(
            RestoredOfficialRelease(
                acquisition_id=receipt.acquisition_id,
                period=parsed.period,
                release_event_id=result.release_event_id,
                metric_ids=result.metric_ids,
                claim_ids=result.claim_ids,
            )
        )
    return OfficialReprocessResult(
        status="completed",
        family=family,
        definition_version=definition_version,
        metric_ids=tuple(sorted(requested)),
        start=start,
        end=end,
        examined=len(stored),
        restored=tuple(restored),
        restored_claim_count=sum(len(item.claim_ids) for item in restored),
        skipped=tuple(skipped),
    )


def _provider_references(database: Path, scalar: ContextScalar, provider: str) -> set[str]:
    """The originals of ``provider`` holding a claim of the scalar's member and period, in
    any catalog version: those the ingest reads as earlier statements of it."""
    with database_connection(database) as connection:
        rows = connection.execute(
            """
            SELECT DISTINCT source_reference FROM source_claim
            WHERE metric_id=? AND period_kind=? AND period_start=? AND period_end=?
              AND dimensions_json=? AND provider=?
            """,
            (
                scalar.metric_id,
                scalar.period_kind,
                scalar.period_start,
                scalar.period_end,
                json.dumps(scalar.dimensions, ensure_ascii=False, sort_keys=True),
                provider,
            ),
        ).fetchall()
    return {str(row[0]) for row in rows}


# Listing pages one run reads from a site, all its listings together (lookback L05).
LISTING_PAGES_PER_SITE = 50
# Reads of one listing page a run makes before taking it as unreadable: a retrieval's own
# retries of a transient failure, not one more for each period still to look up.
_LISTING_PAGE_TRIES = 3
_LISTING_PARSER = "official-release-listing-v0003"


@dataclass(frozen=True)
class _ListingPage:
    url: str
    content: bytes
    days: list[str]
    following: str | None


def _listing_page(url: str, content: bytes) -> _ListingPage:
    return _ListingPage(url, content, entry_days(content), next_listing_page(content, url))


@dataclass
class ListingScan:
    """The listing pages one run has read, shared by every period looked up on them.

    A listing is read newest first, page by page, only as far back as the periods asked
    for so far need: a later, older period reads on from the last page read. A site's
    listings read at most ``LISTING_PAGES_PER_SITE`` pages together. A listing ends at its
    last page, at a page listing what the one before did (the site serves no older one),
    or at a page that failed each of its reads.
    """

    pages: dict[str, list[_ListingPage]] = field(default_factory=dict)
    ended: dict[str, str] = field(default_factory=dict)
    sites: dict[str, int] = field(default_factory=dict)
    reads: dict[str, int] = field(default_factory=dict)
    failures: dict[str, int] = field(default_factory=dict)

    def days(self, listing_url: str) -> list[str]:
        """The days of the dated entries on the listing's pages read so far."""
        return [day for page in self.pages.get(listing_url, []) for day in page.days]

    def count_site(self, url: str) -> None:
        site = urlsplit(url).netloc
        self.sites[site] = self.sites.get(site, 0) + 1

    def count_read(self, listing_url: str) -> None:
        self.count_site(listing_url)
        self.reads[listing_url] = self.reads.get(listing_url, 0) + 1

    def keep(self, listing_url: str, page: _ListingPage) -> bool:
        """Keep a page read of the listing; False when it lists what the one before did."""
        pages = self.pages.setdefault(listing_url, [])
        if pages and listing_entries(page.content) == listing_entries(pages[-1].content):
            self.ended[listing_url] = "repeated_page"
            return False
        pages.append(page)
        return True


# The run whose listing pages were last read in this process, and its scan.
_RUN_LISTINGS: list[tuple[tuple[Path, str], ListingScan]] = []
# The scan the lookups made inside ``listing_scan`` share.
_SHARED_LISTINGS: ContextVar[ListingScan | None] = ContextVar("listing_scan", default=None)


@contextmanager
def listing_scan() -> Iterator[None]:
    """Share one scan of the listings among the lookups made inside: a targeted run's
    official channel and the search candidates it checks (lookback L05)."""
    token = _SHARED_LISTINGS.set(ListingScan())
    try:
        yield
    finally:
        _SHARED_LISTINGS.reset(token)


def _run_listings(paths: RuntimePaths) -> ListingScan:
    """The listing pages read so far by the run now acquiring, a fresh scan outside a run;
    a targeted run's are shared within ``listing_scan``."""
    if (shared := _SHARED_LISTINGS.get()) is not None:
        return shared
    run_id = owning_run(paths.database)
    return ListingScan() if run_id is None else run_listings(paths, run_id)


def run_listings(paths: RuntimePaths, run_id: str) -> ListingScan:
    """The listing pages a full run has read so far.

    Rebuilt from its receipts when this process has not read them, so a run resumed reads
    on from where it stopped and keeps counting its pages; a failed page is tried afresh.
    The chronicle's pages the RRR backtrack read count to their site too; a request the
    retrieval ledger held back was never sent and counts to none.
    """
    key = (paths.database.resolve(), run_id)
    if _RUN_LISTINGS and _RUN_LISTINGS[0][0] == key:
        return _RUN_LISTINGS[0][1]
    scan = ListingScan()
    receipts = AcquisitionRepository(paths.database, paths.artifacts)
    with database_connection(paths.database) as connection:
        rows = connection.execute(
            "SELECT a.acquisition_id, a.parameters_json, a.state, a.parser_version "
            "FROM full_run_acquisition f JOIN acquisition_request a USING(acquisition_id) "
            "WHERE f.run_id=? AND a.api_name='official_listing_get' "
            "AND coalesce(a.error_type, '') <> 'RetrievalBudgetBlocked' ORDER BY a.rowid",
            (run_id,),
        ).fetchall()
    for acquisition_id, parameters_json, state, parser_version in rows:
        parameters = json.loads(parameters_json)
        if parser_version != _LISTING_PARSER:
            scan.count_site(parameters["source_url"])
            continue
        listing_url = parameters["listing"]
        scan.count_read(listing_url)
        if state == "validated" and listing_url not in scan.ended:
            content = receipts.read_content(acquisition_id, "raw")
            scan.keep(listing_url, _listing_page(parameters["source_url"], content))
    _RUN_LISTINGS[:] = [(key, scan)]
    return scan


def read_listing_page(
    paths: RuntimePaths,
    *,
    family: str,
    listing_url: str,
    period: str,
    listings: ListingScan,
    on_acquisition_started: Callable[[str], None] | None = None,
    fetcher: Callable[[str], FetchedOfficialContextDocument] | None = None,
) -> str | None:
    """Read the listing's next older page into ``listings``, for ``period``; when there is
    none to read, where the listing stopped. A failed read is raised (lookback L05)."""
    listings.pages.setdefault(listing_url, [])
    started = on_acquisition_started or (lambda _acquisition_id: None)
    if _read_older_page(paths, family, listing_url, period, fetcher, started, listings):
        return None
    return listings.ended[listing_url]


def _release_from_listing(
    paths: RuntimePaths,
    family: str,
    listing_url: str,
    expected_period: str,
    fetcher: Callable[[str], FetchedOfficialContextDocument] | None,
    started: Callable[[str], None],
    scan: ListingScan,
) -> tuple[str, ...]:
    """The period's release, looked up on the listing's pages the run has read and, while
    they do not reach back to the period, on the older pages read next.

    A listing read back past the period without the release does not list it (not found,
    which is not ambiguous); so does one read to its end with no dated entry. One that
    stopped short of the period has not covered it. An OMO day may list several notices,
    on to the next page: all are returned, and parsing tells them apart; once that next
    page failed a read, those found are.
    """
    pages = scan.pages.setdefault(listing_url, [])
    found: list[str] = []
    index = 0
    while True:
        if index == len(pages):
            # The page after the day's notices found failed already: read those found, in a
            # retrieval of their own (a failed read ends the one it is part of).
            if found and scan.failures.get(pages[-1].following or "", 0):
                return tuple(dict.fromkeys(found))
            if not _read_older_page(
                paths, family, listing_url, expected_period, fetcher, started, scan
            ):
                break
        page = pages[index]
        resolved = release_urls(
            page.content, family=family, listing_url=page.url, period=expected_period
        )
        for url in resolved:
            _validate_source_identity(family, url)
        found += resolved
        index += 1
        reached = reaches_back(
            [day for read in pages[:index] for day in read.days], expected_period
        )
        if found and (reached or family != "pbc_omo_notice"):
            return tuple(dict.fromkeys(found))
        if reached:
            raise ValueError("official_context_release_link_not_found")
    if found:
        return tuple(dict.fromkeys(found))
    days = [day for read in pages for day in read.days]
    stopped = scan.ended[listing_url]
    if stopped == "last_page" and not days:
        raise ValueError("official_context_release_link_not_found")
    raise ListingNotCovered(stopped, scan.reads.get(listing_url, 0), min(days, default=None))


def _read_older_page(
    paths: RuntimePaths,
    family: str,
    listing_url: str,
    period: str,
    fetcher: Callable[[str], FetchedOfficialContextDocument] | None,
    started: Callable[[str], None],
    scan: ListingScan,
) -> bool:
    """Read the listing's next older page into the scan, for ``period``; False once there is
    none to read. A failed read is raised, and counted against the page's tries."""
    pages = scan.pages[listing_url]
    if listing_url in scan.ended:
        return False
    page_url = pages[-1].following if pages else listing_url
    if page_url is None:
        scan.ended[listing_url] = "last_page"
        return False
    if scan.sites.get(urlsplit(listing_url).netloc, 0) >= LISTING_PAGES_PER_SITE:
        scan.ended[listing_url] = "page_limit"
        return False
    if scan.failures.get(page_url, 0) >= _LISTING_PAGE_TRIES:
        scan.ended[listing_url] = "unreadable_page"
        return False
    try:
        page = _read_listing_page(paths, family, listing_url, page_url, period, fetcher, started)
    except (LookupError, OSError, TypeError, ValueError) as error:
        # One held back before it was sent (the retrieval ledger's cache) is no read.
        if failed_step(error) != "start":
            scan.count_read(listing_url)
            scan.failures[page_url] = scan.failures.get(page_url, 0) + 1
        raise
    scan.count_read(listing_url)
    return scan.keep(listing_url, page)


def _read_listing_page(
    paths: RuntimePaths,
    family: str,
    listing_url: str,
    page_url: str,
    period: str,
    fetcher: Callable[[str], FetchedOfficialContextDocument] | None,
    started: Callable[[str], None],
) -> _ListingPage:
    responses: list[FetchedOfficialContextDocument] = []

    def fetch_listing() -> bytes:
        response = (fetcher or _fetch_official_context_document)(page_url)
        responses.append(response)
        return response.content

    def parse_listing(content: bytes) -> _ListingPage:
        _validate_fetched_document(family, page_url, responses[0])
        if not content or len(content) > MAX_OFFICIAL_CONTEXT_BYTES:
            raise ValueError("official_context_document_size_invalid")
        # A period no release is titled for is refused with the page read for it.
        release_titles(family, period)
        page = _listing_page(page_url, content)
        if page.following is not None:
            _validate_source_identity(family, page.following)
        return page

    discovered = AcquisitionRepository(paths.database, paths.artifacts).capture(
        provider=_validate_source_identity(family, page_url),
        api_name="official_listing_get",
        # The period it was read for; later ones of the run read it from the scan, which a
        # resumed run rebuilds by the listing each page belongs to.
        parameters={
            "source_url": page_url,
            "listing": listing_url,
            "period": period,
            "family": family,
        },
        fields="href,title",
        parser_version=_LISTING_PARSER,
        fetch=fetch_listing,
        parse=parse_listing,
        normalize=lambda page: {"entry_days": page.days, "next_page": page.following},
        on_started=started,
        # The list's dated entries; an HTML page holds no values (lookback L06).
        count_records=lambda page: len(page.days),
    )
    return discovered.value


def refresh_official_context_document(
    paths: RuntimePaths,
    *,
    family: str,
    source_url: str,
    expected_period: str,
    fetched_at: datetime,
    fetcher: Callable[[str], FetchedOfficialContextDocument] | None = None,
    definition_version: str = METRIC_CATALOG_VERSION,
    on_acquisition_started: Callable[[str], None] | None = None,
    metric_ids: tuple[str, ...] | None = None,
    admit: Callable[[ParsedOfficialContextRelease], None] | None = None,
    held_members: frozenset[str] = frozenset(),
    listings: ListingScan | None = None,
) -> OfficialContextIngestionResult:
    """Fetch and store one release; ``admit`` may reject the parsed release first, and
    ``held_members`` another source delivered are left out. A release looked up on a listing
    reads the pages the run acquiring has read (``listings``, when given) before any older
    one."""
    _validate_source_identity(family, source_url)
    requested = _official_metric_scope(family, metric_ids)
    if fetched_at.tzinfo is None:
        raise ValueError("official_context_fetched_at_must_be_timezone_aware")
    acquisition_ids: list[str] = []

    def started(acquisition_id: str) -> None:
        acquisition_ids.append(acquisition_id)
        if on_acquisition_started is not None:
            on_acquisition_started(acquisition_id)

    stage = ["acquire"]

    def ingest(source_url: str, *, last: bool = True) -> OfficialContextIngestionResult:
        response_holder: list[FetchedOfficialContextDocument] = []
        stage[0] = "acquire"

        def fetch() -> bytes:
            response = (fetcher or _fetch_official_context_document)(source_url)
            response_holder.append(response)
            return response.content

        def parse(raw: bytes) -> ParsedOfficialContextRelease:
            _validate_fetched_document(family, source_url, response_holder[0])
            try:
                parsed = parse_official_context_document(
                    raw,
                    family=family,
                    source_url=source_url,
                    expected_period=expected_period,
                    fetched_at=utc_now(),
                )
            except ValueError as error:
                # Another of the day's notices, passed over for the next: skipped, not refused.
                if not last and str(error) == "official_context_table_schema_mismatch":
                    raise CandidateSkipped(str(error)) from error
                raise
            if admit is not None:
                admit(parsed)
            return parsed

        acquired = AcquisitionRepository(paths.database, paths.artifacts).capture(
            provider=_validate_source_identity(family, source_url),
            api_name="official_http_get",
            parameters={"source_url": source_url, "period": expected_period, "family": family},
            fields="",
            parser_version="official-context-parser-v0004",
            fetch=fetch,
            parse=parse,
            normalize=asdict,
            on_started=started,
            count_scalars=lambda release: len(release.scalars),
        )
        stage[0] = "ingest"
        return ingest_acquired_official_release(
            paths,
            acquired,
            definition_version=definition_version,
            metric_ids=metric_ids,
            held_members=held_members,
        )

    try:
        listing = release_listing(family, source_url)
        candidates = (
            _release_from_listing(
                paths,
                family,
                listing,
                expected_period,
                fetcher,
                started,
                listings if listings is not None else _run_listings(paths),
            )
            if listing is not None
            else (source_url,)
        )
        # Another of the day's notices (central bank bills) has another table: try the next.
        for candidate in candidates[:-1]:
            try:
                return ingest(candidate, last=False)
            except CandidateSkipped:
                pass
        return ingest(candidates[-1])
    except (LookupError, OSError, TypeError, ValueError) as error:
        # Where it ended says how: at the call (the source, or its response's check), or
        # storing the checked values (the contract, or this system).
        outcome, recorded = (
            ingest_failure(error) if stage[0] == "ingest" else capture_failure(error)
        )
        if isinstance(error, ListingNotCovered):
            # No request for the release: the listing read did not reach back to it.
            outcome, recorded = (
                NOT_ATTEMPTED,
                attempt_details(
                    step="request",
                    condition=str(error),
                    listing_stopped=error.stopped,
                    listing_pages=str(error.pages),
                ),
            )
            if error.oldest is not None:
                recorded["listing_oldest_entry"] = error.oldest
        repository = EvidenceRepository(paths.database)
        for metric_id in sorted(requested):
            repository.record_retrieval_attempt(
                metric_id=metric_id,
                channel="official_direct_candidate",
                outcome=outcome,
                fetched_at=utc_now(),
                acquisition_ids=tuple(acquisition_ids),
                safe_metadata={
                    "family": family,
                    "period": expected_period,
                    "definition_version": definition_version,
                    **recorded,
                },
            )
        raise


# A chronicle entry opens with its day ("5月15日，"); a change of the RRR in it is written
# with its direction near the rate ("下调金融机构存款准备金率", "定向下调存款准备金率").
_ENTRY_DAY = re.compile(r"(\d{1,2})月(\d{1,2})日")
_RRR_CHANGE_MENTION = re.compile(r"(?:下调|上调|降低|提高)[^。；，]{0,30}?(?<!外汇)存款准备金率")


@dataclass(frozen=True)
class RrrBacktrack:
    """What the chronicles gave: the latest cut's claims (none when no issue up to the
    column's last page states one), and the last day the newest issue read covers."""

    claim_ids: tuple[str, ...]
    covered_through: date | None


def backtrack_rrr_chronicle(
    paths: RuntimePaths,
    *,
    until: date,
    fetched_at: datetime,
    public_as_of: datetime | None = None,
    fetcher: Callable[[str], FetchedOfficialContextDocument] | None = None,
    definition_version: str = METRIC_CATALOG_VERSION,
    on_acquisition_started: Callable[[str], None] | None = None,
) -> RrrBacktrack:
    """The latest RRR change effective by ``until``, traced back through the chronicles.

    The PBC's own RRR column stopped in 2020; its monetary policy chronicle states each
    change by the day it took effect (ADR-0028). Issues out by ``public_as_of`` (the run's
    cutoff; ``until``'s end when not given) are read newest first, each from its last month
    back, and the first cut found is the latest: an issue goes no later than the ones
    published after it. An issue is listed by its day alone, so it is public from the next
    day (ticket 06). That issue is then read again as the month's release and kept. A cut the
    parser cannot read stops the search (an older one must not stand in for it), and so
    does any page that cannot be read.
    """
    family = "pbc_rrr_notice"
    known_at = public_as_of if public_as_of is not None else day_end(until)
    covered_through = None
    page_url: str | None = RRR_CHRONICLE_LISTING
    while page_url is not None:
        entries, page_url = _read_chronicle_page(paths, page_url, fetcher, on_acquisition_started)
        for entry in entries:
            # Listed by its day alone, an issue is public as a page showing only its day is.
            _release, public_at = publication_times(
                date.fromisoformat(entry.published), ZoneInfo("Asia/Shanghai")
            )
            if public_at is None or public_at > known_at or entry.year > until.year:
                continue
            first = covered_through is None
            if first:
                last = calendar.monthrange(entry.year, entry.through_month)[1]
                covered_through = date(entry.year, entry.through_month, last)
            period = _scan_chronicle(paths, entry, until, fetcher, on_acquisition_started)
            if period is not None:
                result = refresh_official_context_document(
                    paths,
                    family=family,
                    source_url=entry.url,
                    expected_period=period,
                    fetched_at=fetched_at,
                    fetcher=fetcher,
                    definition_version=definition_version,
                    on_acquisition_started=on_acquisition_started,
                )
                if _claims_known(
                    paths, result.claim_ids, SummaryCutoff(until, known_at), definition_version
                ):
                    return RrrBacktrack(result.claim_ids, covered_through)
                # Its own page went out after the cutoff (ticket 11): the issue was not yet
                # read then, so neither its cut nor its months count; an older one is next.
                if first:
                    covered_through = None
    return RrrBacktrack((), covered_through)


def _claims_known(
    paths: RuntimePaths,
    claim_ids: tuple[str, ...],
    cutoff: SummaryCutoff,
    definition_version: str,
) -> bool:
    """Whether the target day's summary knows each of these RRR claims by their stored
    public time, the page's own when it gives one (ticket 11)."""
    wanted = set(claim_ids)
    vintages = [
        vintage
        for vintage in EvidenceRepository(paths.database).source_claim_vintages(
            "CN_RRR_EVENT", definition_version=definition_version
        )
        if vintage.claim_id in wanted
    ]
    return len(vintages) == len(wanted) and all(
        cutoff.knows(date.fromisoformat(vintage.period_end), vintage.public_available_at)
        for vintage in vintages
    )


def _read_chronicle_page(
    paths: RuntimePaths,
    page_url: str,
    fetcher: Callable[[str], FetchedOfficialContextDocument] | None,
    started: Callable[[str], None] | None,
) -> tuple[tuple[ChronicleEntry, ...], str | None]:
    family = "pbc_rrr_notice"
    responses: list[FetchedOfficialContextDocument] = []

    def fetch() -> bytes:
        response = (fetcher or _fetch_official_context_document)(page_url)
        responses.append(response)
        return response.content

    def parse(content: bytes) -> tuple[tuple[ChronicleEntry, ...], str | None]:
        _validate_fetched_document(family, page_url, responses[0])
        if not content or len(content) > MAX_OFFICIAL_CONTEXT_BYTES:
            raise ValueError("official_context_document_size_invalid")
        entries = chronicle_entries(content, page_url)
        if not entries:
            # A changed or replaced page is not the column's end.
            raise ValueError("official_context_release_link_not_found")
        following = chronicle_next_page(content, page_url)
        for url in (*(entry.url for entry in entries), *((following,) if following else ())):
            _validate_source_identity(family, url)
        return entries, following

    discovered = AcquisitionRepository(paths.database, paths.artifacts).capture(
        provider=_validate_source_identity(family, page_url),
        api_name="official_listing_get",
        parameters={"source_url": page_url, "family": family},
        fields="href,title,date",
        parser_version="official-chronicle-listing-v0001",
        fetch=fetch,
        parse=parse,
        normalize=lambda value: {
            "entries": [asdict(entry) for entry in value[0]],
            "next_page": value[1],
        },
        on_started=started,
    )
    return discovered.value


def _scan_chronicle(
    paths: RuntimePaths,
    entry: ChronicleEntry,
    until: date,
    fetcher: Callable[[str], FetchedOfficialContextDocument] | None,
    started: Callable[[str], None] | None,
) -> str | None:
    """The month of the latest cut in force by ``until`` that this issue states, if any."""
    family = "pbc_rrr_notice"
    responses: list[FetchedOfficialContextDocument] = []

    def fetch() -> bytes:
        response = (fetcher or _fetch_official_context_document)(entry.url)
        responses.append(response)
        return response.content

    def parse(content: bytes) -> str | None:
        _validate_fetched_document(family, entry.url, responses[0])
        parser = _OfficialHtmlParser()
        parser.feed(_decode_document(content))
        text = _normalized_text(" ".join(parser.parts))
        # The months whose entries change the RRR, read or not (the FX RRR is another).
        changed = {
            int(dated[-1][0])
            for mention in _RRR_CHANGE_MENTION.finditer(text)
            if (dated := _ENTRY_DAY.findall(text, 0, mention.start()))
        }
        last = entry.through_month if entry.year < until.year else until.month
        for month in range(min(entry.through_month, last), 0, -1):
            if month not in changed:
                continue
            period = f"{entry.year:04d}-{month:02d}"
            try:
                parsed = parse_official_context_document(
                    content,
                    family=family,
                    source_url=entry.url,
                    expected_period=period,
                    fetched_at=utc_now(),
                )
            except ValueError as error:
                if str(error) == "official_context_table_schema_mismatch":
                    raise ValueError("official_context_rrr_change_unreadable") from error
                raise
            if all(item.period_end <= until.isoformat() for item in parsed.scalars):
                return period
        return None

    scanned = AcquisitionRepository(paths.database, paths.artifacts).capture(
        provider=_validate_source_identity(family, entry.url),
        api_name="official_listing_get",
        parameters={"source_url": entry.url, "until": until.isoformat(), "family": family},
        fields="rrr_change_month",
        parser_version="official-rrr-chronicle-scan-v0001",
        fetch=fetch,
        parse=parse,
        normalize=lambda period: {"period": period},
        on_started=started,
    )
    return scanned.value


def _fetch_official_context_document(source_url: str) -> FetchedOfficialContextDocument:
    request = Request(
        source_url,
        headers={"Accept": "text/html", "User-Agent": "pring-cycle/1.0 official-source-check"},
        method="GET",
    )
    with urlopen(request, timeout=15) as response:  # noqa: S310 - validated by caller
        content = response.read(MAX_OFFICIAL_CONTEXT_BYTES + 1)
        final_url = response.geturl()
        status = int(response.status)
        media_type = str(response.headers.get("Content-Type", ""))
    return FetchedOfficialContextDocument(content, media_type, final_url, status)


def _parse_family(
    family: str,
    tables: list[list[tuple[str, ...]]],
    text: str,
    period: str,
    release_at: datetime | None,
) -> tuple[ContextScalar, ...]:
    if family == "nbs_core_cpi":
        return _parse_core_cpi(tables, period, release_at)
    if family == "nbs_pmi":
        return _parse_pmi(tables, period, release_at)
    if family == "nbs_ppi":
        return _parse_ppi(tables, period, release_at)
    if family == "nbs_gdp":
        return _parse_gdp(tables, period, release_at)
    if family == "nbs_industrial_value_added":
        return _parse_industrial_value_added(tables, period, release_at)
    if family == "nbs_industrial_finance":
        return _parse_industrial_finance(tables, text, period, release_at)
    if family == "nbs_capacity_utilization":
        return _parse_capacity_utilization(tables, period, release_at)
    if family == "pbc_omo_notice":
        return _parse_omo_notice(tables, period, release_at)
    if family == "pbc_rrr_notice":
        return _parse_rrr_notice(tables, text, period, release_at)
    if family == "pbc_tool_liquidity_monthly":
        return _parse_tool_liquidity(tables, period, release_at)
    if family == "pbc_social_financing":
        return _parse_social_financing(tables, text, period, release_at)
    if family == "pbc_loan_structure":
        return _parse_loan_structure(tables, text, period, release_at)
    if family == "pbc_money":
        return _parse_money(text, period, release_at)
    if family == "pbc_usdcny_central_parity":
        return _parse_usdcny_central_parity(text, period, release_at)
    raise ValueError("official_context_family_unsupported")


def _parse_core_cpi(
    tables: list[list[tuple[str, ...]]],
    period: str,
    release_at: datetime | None,
) -> tuple[ContextScalar, ...]:
    header = ("指标", "环比（%）", "同比（%）", "累计平均同比（%）")
    try:
        rows = _table_with_header(tables, header)
    except ValueError as error:
        live_tables = _unique_tables(
            table
            for table in tables
            if table
            and len(table[0]) in {3, 4}
            and tuple(_compact_text(cell) for cell in table[0][:3])
            == ("", "环比涨跌幅（%）", "同比涨跌幅（%）")
        )
        if len(live_tables) != 1:
            raise error
        rows = live_tables[0]
    matching = [
        row for row in rows[1:] if row and row[0].removeprefix("其中：") == "不包括食品和能源"
    ]
    column_count = len(rows[0])
    if len(matching) != 1 or len(matching[0]) != column_count:
        raise ValueError("official_context_row_identity_mismatch")
    headline = [row for row in rows[1:] if row and row[0] == "居民消费价格"]
    if len(headline) > 1 or (headline and len(headline[0]) != column_count):
        raise ValueError("official_context_row_identity_mismatch")
    period_start, period_end = month_bounds(period)
    groups = [("CN_CORE_CPI", "ex_food_energy", matching[0], "core_cpi")]
    if headline:
        groups.insert(0, ("CN_CPI_HEADLINE", "headline", headline[0], "headline_cpi"))
    measure_columns = [
        ("mom_pct", "mom", 1),
        ("yoy_pct", "yoy", 2),
    ]
    if column_count == 4:
        measure_columns.append(("ytd_avg_yoy_pct", "cumulative_average_yoy", 3))
    return tuple(
        ContextScalar(
            metric_id=metric_id,
            api_name="nbs_core_cpi",
            source_field=f"{prefix}_{source_field}",
            period_kind="month",
            period_start=period_start,
            period_end=period_end,
            dimensions={"measure": measure, "category": category},
            value=_percent(values[index]),
            unit="percent",
            release_at=release_at,
            public_available_at=release_at,
        )
        for metric_id, category, values, prefix in groups
        for source_field, measure, index in measure_columns
    )


def _parse_pmi(
    tables: list[list[tuple[str, ...]]],
    period: str,
    release_at: datetime | None,
) -> tuple[ContextScalar, ...]:
    period_start, period_end = month_bounds(period)
    year, month = (int(item) for item in period.split("-"))
    target = f"{year}年{month}月"
    primary = _pmi_period_row(
        tables,
        target,
        required_headers=("生产", "新订单", "原材料库存"),
    )
    secondary = _pmi_period_row(
        tables,
        target,
        required_headers=("采购量", "主要原材料购进价格", "产成品库存"),
    )
    fields = (
        ("CN_PMI_ACTIVITY", "manufacturing_pmi", "manufacturing", primary, 1),
        ("CN_PMI_ACTIVITY", "production", "production", primary, 2),
        ("CN_PMI_ACTIVITY", "new_orders", "new_orders", primary, 3),
        ("CN_PMI_INVENTORY", "raw_materials", "raw_materials", primary, 4),
        ("CN_PMI_ACTIVITY", "purchase_volume", "purchase_volume", secondary, 3),
        ("CN_PMI_PRICES", "purchase_prices", "purchase_prices", secondary, 4),
        ("CN_PMI_PRICES", "output_prices", "output_prices", secondary, 5),
        ("CN_PMI_INVENTORY", "finished_goods", "finished_goods", secondary, 6),
    )
    return tuple(
        _official_scalar(
            metric_id,
            "nbs_pmi",
            source_field,
            "month",
            period_start,
            period_end,
            {"series": series, "measure": "level"},
            _bounded_number(row[index], minimum=0, maximum=100),
            "diffusion_index_points",
            release_at,
        )
        for metric_id, source_field, series, row, index in fields
    )


def _parse_ppi(
    tables: list[list[tuple[str, ...]]],
    period: str,
    release_at: datetime | None,
) -> tuple[ContextScalar, ...]:
    labels = ("一、工业生产者出厂价格", "生产资料", "生活资料")
    selected_rows = _consistent_first_column_rows(tables, labels)
    period_start, period_end = month_bounds(period)
    measure_columns = [("mom", "mom", 1), ("yoy", "yoy", 2)]
    if all(len(row) >= 4 for row in selected_rows.values()):
        measure_columns.append(("accu", "cumulative_average_yoy", 3))
    return tuple(
        _official_scalar(
            "CN_PPI",
            "nbs_ppi",
            f"{prefix}_{source_suffix}",
            "month",
            period_start,
            period_end,
            {"measure": measure, "category": category},
            _percent(row[index]),
            "percent",
            release_at,
        )
        for label, category, prefix in (
            ("一、工业生产者出厂价格", "headline", "ppi"),
            ("生产资料", "means_of_production", "ppi_mp"),
            ("生活资料", "consumer_goods", "ppi_cg"),
        )
        for row in (selected_rows[label],)
        for source_suffix, measure, index in measure_columns
    )


def _validate_registered_gdp_table(content: bytes, period: str) -> None:
    """Check new-catalog source semantics without rewriting the v4 parser contract."""
    parser = _OfficialHtmlParser()
    parser.feed(_decode_document(content))
    members = {"GDP", "第一产业", "第二产业", "第三产业"}
    table = _table_with_first_column_members(parser.tables, members)
    header = tuple(_compact_text(cell) for cell in table[0])
    if header != ("", "绝对额（亿元）", "比上年同期增长（%）"):
        raise ValueError("registered_gdp_table_contract_mismatch")
    quarter = int(period[-1])
    if quarter != 1:
        current, cumulative = {
            2: ("二季度", "上半年"),
            3: ("三季度", "前三季度"),
            4: ("四季度", "全年"),
        }[quarter]
        if tuple(_compact_text(cell) for cell in table[1]) != (
            current,
            cumulative,
            current,
            cumulative,
        ):
            raise ValueError("registered_gdp_table_contract_mismatch")
    if any(
        len(_unique_first_cell_row(table, member)) != (3 if quarter == 1 else 5)
        for member in members
    ):
        raise ValueError("registered_gdp_table_contract_mismatch")
    table_text = "".join(_compact_text(cell) for row in table for cell in row)
    bases = re.findall(r"绝对额按([^，,；;。]+)[，,]增长速度按([^，,；;。]+)", table_text)
    if bases != [("现价计算", "不变价计算")]:
        raise ValueError("registered_gdp_table_contract_mismatch")


def _parse_gdp(
    tables: list[list[tuple[str, ...]]],
    period: str,
    release_at: datetime | None,
) -> tuple[ContextScalar, ...]:
    year, quarter_text = period.split("-Q")
    quarter = int(quarter_text)
    quarter_start = f"{year}-{(quarter - 1) * 3 + 1:02d}-01"
    quarter_end = month_bounds(f"{year}-{quarter * 3:02d}")[1]
    level_index = 1 if quarter == 1 else 2
    yoy_index = 2 if quarter == 1 else 3
    rows = _table_with_first_column_members(
        tables,
        {"GDP", "第一产业", "第二产业", "第三产业"},
    )
    return tuple(
        scalar
        for label, aggregate, prefix in (
            ("GDP", "total", "gdp"),
            ("第一产业", "primary", "pi"),
            ("第二产业", "secondary", "si"),
            ("第三产业", "tertiary", "ti"),
        )
        for row in (_unique_first_cell_row(rows, label),)
        for scalar in (
            _official_scalar(
                "CN_GDP",
                "nbs_gdp",
                prefix,
                "year_to_quarter",
                f"{year}-01-01",
                quarter_end,
                {"aggregate": aggregate, "measure": "nominal_ytd_level"},
                _bounded_number(row[level_index], minimum=0),
                "hundred_million_cny",
                release_at,
            ),
            _official_scalar(
                "CN_GDP",
                "nbs_gdp",
                f"{prefix}_yoy",
                "quarter",
                quarter_start,
                quarter_end,
                {"aggregate": aggregate, "measure": "real_quarter_yoy"},
                _percent(row[yoy_index]),
                "percent",
                release_at,
            ),
        )
    )


def _parse_industrial_value_added(
    tables: list[list[tuple[str, ...]]],
    period: str,
    release_at: datetime | None,
) -> tuple[ContextScalar, ...]:
    period_start, period_end = month_bounds(period)
    if period.endswith("-01"):
        raise ValueError("official_context_january_monthly_value_not_reported")
    header = ("指标", "当月实际同比（%）", "累计实际同比（%）", "季调环比（%）")
    current_yoy: str | None
    try:
        rows = _table_with_header(tables, header)
        matching = [row for row in rows[1:] if row and row[0] == "规模以上工业增加值"]
        if len(matching) != 1 or len(matching[0]) != len(header):
            raise ValueError("official_context_row_identity_mismatch")
        current_yoy, ytd_yoy, mom_sa = matching[0][1:]
    except ValueError as error:
        year, month = (int(item) for item in period.split("-"))
        main_tables = _unique_tables(
            table
            for table in tables
            if len(table) >= 3
            and len(table[0]) == 3
            and _compact_text(table[0][0]) == "指标"
            and _compact_text(table[0][1]) == f"{month}月"
            and _compact_text(table[0][2]) == f"1—{month}月"
            and tuple(_compact_text(cell) for cell in table[1])
            == ("绝对量", "同比增长（%）", "绝对量", "同比增长（%）")
        )
        if month == 2:
            main_tables = _unique_tables(
                table
                for table in tables
                if len(table) >= 3
                and tuple(_compact_text(cell) for cell in table[0]) == ("指标", "1—2月")
                and tuple(_compact_text(cell) for cell in table[1]) == ("绝对量", "同比增长（%）")
            )
        sa_tables = _unique_tables(
            table
            for table in tables
            if table
            and tuple(_compact_text(cell) for cell in table[0]) == ("年份", "月份", "环比增速（%）")
        )
        if len(main_tables) != 1 or len(sa_tables) != 1:
            raise error
        expected_columns = 3 if month == 2 else 5
        main_rows = [
            row
            for row in main_tables[0][2:]
            if row and row[0] == "规模以上工业增加值" and len(row) == expected_columns
        ]
        if len(main_rows) != 1:
            raise ValueError("official_context_row_identity_mismatch") from error
        mom_values: list[str] = []
        observed_year: int | None = None
        for row in sa_tables[0][1:]:
            if len(row) == 3:
                year_match = re.fullmatch(r"(\d{4})年", _compact_text(row[0]))
                if year_match is None:
                    raise ValueError("official_context_row_identity_mismatch") from error
                observed_year = int(year_match.group(1))
                month_cell, value_cell = row[1], row[2]
            elif len(row) == 2 and observed_year is not None:
                month_cell, value_cell = row
            else:
                raise ValueError("official_context_row_identity_mismatch") from error
            if observed_year == year and _compact_text(month_cell) == f"{month}月":
                mom_values.append(value_cell)
        if len(mom_values) != 1:
            raise ValueError("official_context_row_identity_mismatch") from error
        current_yoy = None if month == 2 else main_rows[0][2]
        ytd_yoy = main_rows[0][2] if month == 2 else main_rows[0][4]
        mom_sa = mom_values[0]
    year_start = f"{period[:4]}-01-01"
    values = [
        (
            "industrial_va_ytd_yoy_real_pct",
            "ytd_real_yoy",
            ytd_yoy,
            "year_to_month",
            year_start,
        ),
        (
            "industrial_va_mom_sa_pct",
            "mom_seasonally_adjusted",
            mom_sa,
            "month",
            period_start,
        ),
    ]
    if current_yoy is not None:
        values.insert(
            0,
            (
                "industrial_va_yoy_real_pct",
                "current_month_real_yoy",
                current_yoy,
                "month",
                period_start,
            ),
        )
    return tuple(
        _official_scalar(
            "CN_INDUSTRIAL_VA",
            "nbs_industrial_value_added",
            source_field,
            period_kind,
            start,
            period_end,
            {"measure": measure},
            _percent(raw_value),
            "percent",
            release_at,
        )
        for source_field, measure, raw_value, period_kind, start in values
    )


def _parse_industrial_finance(
    tables: list[list[tuple[str, ...]]],
    text: str,
    period: str,
    release_at: datetime | None,
) -> tuple[ContextScalar, ...]:
    period_start, period_end = month_bounds(period)
    year_start = f"{period[:4]}-01-01"
    header = ("指标", "数值", "同比或变化", "数值单位", "同比或变化单位")
    try:
        rows = _rows_by_first_cell(_table_with_header(tables, header))
    except ValueError:
        return _parse_industrial_finance_live(tables, text, period, release_at)
    required = {"利润总额", "营业收入", "营业成本", "产成品存货", "产成品周转天数"}
    if set(rows) != required or any(len(row) != len(header) for row in rows.values()):
        raise ValueError("official_context_industrial_finance_rows_mismatch")
    scalars: list[ContextScalar] = []
    for label, item in (("利润总额", "profit"), ("营业收入", "revenue"), ("营业成本", "cost")):
        row = rows[label]
        if (row[3], row[4]) != ("亿元", "%"):
            raise ValueError("official_context_industrial_finance_unit_mismatch")
        for source_field, measure, value, unit in (
            (
                f"industrial_{item}_ytd_100m",
                "ytd_level",
                _bounded_number(row[1]),
                "hundred_million_cny",
            ),
            (f"industrial_{item}_ytd_yoy_pct", "official_yoy", _percent(row[2]), "percent"),
        ):
            scalars.append(
                _official_scalar(
                    "CN_INDUSTRIAL_FINANCE",
                    "nbs_industrial_finance",
                    source_field,
                    "year_to_month",
                    year_start,
                    period_end,
                    {"item": item, "measure": measure},
                    value,
                    unit,
                    release_at,
                )
            )
    inventory = rows["产成品存货"]
    if (inventory[3], inventory[4]) != ("亿元", "%"):
        raise ValueError("official_context_industrial_finance_unit_mismatch")
    for source_field, measure, value, unit in (
        (
            "finished_goods_inventory_100m",
            "nominal_end_level",
            _bounded_number(inventory[1], minimum=0),
            "hundred_million_cny",
        ),
        (
            "finished_goods_inventory_yoy_pct",
            "official_yoy",
            _percent(inventory[2]),
            "percent",
        ),
    ):
        scalars.append(
            _official_scalar(
                "CN_FINISHED_GOODS_INVENTORY",
                "nbs_industrial_finance",
                source_field,
                "month",
                period_start,
                period_end,
                {"measure": measure},
                value,
                unit,
                release_at,
            )
        )
    turnover = rows["产成品周转天数"]
    if (turnover[3], turnover[4]) != ("天", "天"):
        raise ValueError("official_context_industrial_finance_unit_mismatch")
    for source_field, measure, value in (
        ("finished_goods_turnover_days", "days", _bounded_number(turnover[1], minimum=0)),
        (
            "finished_goods_turnover_days_yoy_change",
            "official_yoy_change",
            _bounded_number(turnover[2]),
        ),
    ):
        scalars.append(
            _official_scalar(
                "CN_INVENTORY_TURNOVER",
                "nbs_industrial_finance",
                source_field,
                "year_to_month",
                year_start,
                period_end,
                {"measure": measure},
                value,
                "days",
                release_at,
            )
        )
    return tuple(scalars)


def _parse_industrial_finance_live(
    tables: list[list[tuple[str, ...]]],
    text: str,
    period: str,
    release_at: datetime | None,
) -> tuple[ContextScalar, ...]:
    period_start, period_end = month_bounds(period)
    year_start = f"{period[:4]}-01-01"
    finance_tables = _unique_tables(
        table
        for table in tables
        if len(table) >= 3
        and tuple(_compact_text(cell) for cell in table[0])
        == ("分组", "营业收入", "营业成本", "利润总额")
        and tuple(_compact_text(cell).replace("(", "（").replace(")", "）") for cell in table[1])
        == (
            "金额（亿元）",
            "同比增长（%）",
            "金额（亿元）",
            "同比增长（%）",
            "金额（亿元）",
            "同比增长（%）",
        )
    )
    turnover_tables = _unique_tables(
        table
        for table in tables
        if table
        and len(table[0]) == 9
        and _compact_text(table[0][0]) == "分组"
        and _compact_text(table[0][7]) == "产成品存货周转天数"
    )
    if len(finance_tables) != 1 or len(turnover_tables) != 1:
        raise ValueError("official_context_table_schema_mismatch")
    totals = [row for row in finance_tables[0][2:] if row and row[0] == "总计"]
    turnover_totals = [row for row in turnover_tables[0][1:] if row and row[0] == "总计"]
    if len(totals) != 1 or len(totals[0]) != 7:
        raise ValueError("official_context_industrial_finance_rows_mismatch")
    if len(turnover_totals) != 1 or len(turnover_totals[0]) != 9:
        raise ValueError("official_context_industrial_finance_rows_mismatch")

    compact = _compact_text(text)
    inventory_match = re.search(
        r"产成品存货(?P<level>\d+(?:\.\d+)?)万亿元[，,]"
        r"(?:同比)?(?P<direction>增长|下降)(?P<change>\d+(?:\.\d+)?)%",
        compact,
    )
    turnover_match = re.search(
        r"产成品存货周转天数为(?P<level>\d+(?:\.\d+)?)天[，,]"
        r"(?:同比|比上年末)(?P<direction>增加|减少)(?P<change>\d+(?:\.\d+)?)天",
        compact,
    )
    if inventory_match is None or turnover_match is None:
        raise ValueError("official_context_industrial_finance_text_mismatch")
    turnover_level = _bounded_number(turnover_match.group("level"), minimum=0)
    if abs(turnover_level - _bounded_number(turnover_totals[0][7], minimum=0)) > 1e-6:
        raise ValueError("official_context_industrial_finance_text_mismatch")

    total = totals[0]
    scalars: list[ContextScalar] = []
    item_columns = {"revenue": (1, 2), "cost": (3, 4), "profit": (5, 6)}
    for item, (level_index, yoy_index) in item_columns.items():
        for source_field, measure, value, unit in (
            (
                f"industrial_{item}_ytd_100m",
                "ytd_level",
                _bounded_number(total[level_index], minimum=0),
                "hundred_million_cny",
            ),
            (
                f"industrial_{item}_ytd_yoy_pct",
                "official_yoy",
                _percent(total[yoy_index]),
                "percent",
            ),
        ):
            scalars.append(
                _official_scalar(
                    "CN_INDUSTRIAL_FINANCE",
                    "nbs_industrial_finance",
                    source_field,
                    "year_to_month",
                    year_start,
                    period_end,
                    {"item": item, "measure": measure},
                    value,
                    unit,
                    release_at,
                )
            )

    inventory_yoy = _bounded_number(inventory_match.group("change"))
    if inventory_match.group("direction") == "下降":
        inventory_yoy = -inventory_yoy
    for source_field, measure, value, unit in (
        (
            "finished_goods_inventory_100m",
            "nominal_end_level",
            _bounded_number(inventory_match.group("level"), minimum=0) * 10_000,
            "hundred_million_cny",
        ),
        ("finished_goods_inventory_yoy_pct", "official_yoy", inventory_yoy, "percent"),
    ):
        scalars.append(
            _official_scalar(
                "CN_FINISHED_GOODS_INVENTORY",
                "nbs_industrial_finance",
                source_field,
                "month",
                period_start,
                period_end,
                {"measure": measure},
                value,
                unit,
                release_at,
            )
        )

    turnover_change = _bounded_number(turnover_match.group("change"))
    if turnover_match.group("direction") == "减少":
        turnover_change = -turnover_change
    for source_field, measure, value in (
        ("finished_goods_turnover_days", "days", turnover_level),
        ("finished_goods_turnover_days_yoy_change", "official_yoy_change", turnover_change),
    ):
        scalars.append(
            _official_scalar(
                "CN_INVENTORY_TURNOVER",
                "nbs_industrial_finance",
                source_field,
                "year_to_month",
                year_start,
                period_end,
                {"measure": measure},
                value,
                "days",
                release_at,
            )
        )
    return tuple(scalars)


def capacity_q1_alias_value(content: bytes, period: str) -> float:
    """Qualify the single Q1 cell without changing the frozen v0004 parser."""
    if re.fullmatch(r"[0-9]{4}-Q1", period) is None:
        raise ValueError("capacity_mapping_requires_q1")
    parser = _OfficialHtmlParser()
    parser.feed(_decode_document(content))
    tables = _unique_tables(parser.tables)
    # An independent cumulative column must retain its own value and review.
    if any(
        table
        and (
            tuple(_compact_text(cell) for cell in table[0])
            == ("行业", "当季（%）", "同比变化（百分点）", "累计（%）")
            or (
                len(table[0]) == 3
                and _compact_text(table[0][0]) == "行业"
                and _compact_text(table[0][1]) == "一季度"
            )
        )
        for table in tables
    ):
        raise ValueError("capacity_mapping_independent_ytd_column")
    matching = [
        table
        for table in tables
        if len(table) >= 3
        and tuple(_compact_text(cell) for cell in table[0]) == ("行业", "一季度")
        and tuple(_compact_text(cell) for cell in table[1])
        == ("产能利用率（%）", "比上年同期增减（百分点）")
    ]
    if len(matching) != 1:
        raise ValueError("capacity_mapping_table_identity_mismatch")
    rows = [row for row in matching[0][2:] if row and row[0] == "工业"]
    if len(rows) != 1 or len(rows[0]) != 3:
        raise ValueError("capacity_mapping_row_identity_mismatch")
    return _percent(rows[0][1])


def _parse_capacity_utilization(
    tables: list[list[tuple[str, ...]]],
    period: str,
    release_at: datetime | None,
) -> tuple[ContextScalar, ...]:
    year_start, quarter_start, quarter_end = _quarter_bounds(period)
    header = ("行业", "当季（%）", "同比变化（百分点）", "累计（%）")
    try:
        rows = _table_with_header(tables, header)
        matching = [row for row in rows[1:] if row and row[0] == "全国规模以上工业"]
        if len(matching) != 1 or len(matching[0]) != len(header):
            raise ValueError("official_context_row_identity_mismatch")
        quarter_rate, yoy_change, ytd_rate = matching[0][1:]
    except ValueError as error:
        quarter = int(period[-1])
        quarter_name = {1: "一季度", 2: "二季度", 3: "三季度", 4: "四季度"}[quarter]
        live_tables = _unique_tables(
            table
            for table in tables
            if len(table) >= 3
            and len(table[0]) == 3
            and _compact_text(table[0][0]) == "行业"
            and _compact_text(table[0][1]) == quarter_name
            and tuple(_compact_text(cell) for cell in table[1])
            == (
                "产能利用率（%）",
                "比上年同期增减（百分点）",
                "产能利用率（%）",
                "比上年同期增减（百分点）",
            )
        )
        if len(live_tables) != 1 and quarter == 1:
            live_tables = _unique_tables(
                table
                for table in tables
                if len(table) >= 3
                and tuple(_compact_text(cell) for cell in table[0]) == ("行业", "一季度")
                and tuple(_compact_text(cell) for cell in table[1])
                == ("产能利用率（%）", "比上年同期增减（百分点）")
            )
        if len(live_tables) != 1:
            raise error
        expected_row_width = len(live_tables[0][1]) + 1
        matching = [row for row in live_tables[0][2:] if row and row[0] == "工业"]
        if len(matching) != 1 or len(matching[0]) != expected_row_width:
            raise ValueError("official_context_row_identity_mismatch") from error
        quarter_rate, yoy_change = matching[0][1:3]
        ytd_rate = matching[0][3] if len(matching[0]) == 5 else quarter_rate
    return tuple(
        _official_scalar(
            "CN_CAPACITY_UTILIZATION",
            "nbs_capacity_utilization",
            source_field,
            period_kind,
            start,
            quarter_end,
            {"industry": "all_industry", "measure": measure},
            _percent(raw_value),
            unit,
            release_at,
        )
        for source_field, measure, raw_value, unit, period_kind, start in (
            (
                "industrial_capacity_utilization_pct",
                "quarter_rate",
                quarter_rate,
                "percent",
                "quarter",
                quarter_start,
            ),
            (
                "industrial_capacity_utilization_yoy_change_pp",
                "yoy_change",
                yoy_change,
                "percentage_points",
                "quarter",
                quarter_start,
            ),
            (
                "industrial_capacity_utilization_ytd_pct",
                "ytd_rate",
                ytd_rate,
                "percent",
                "year_to_quarter",
                year_start,
            ),
        )
    )


def _parse_omo_notice(
    tables: list[list[tuple[str, ...]]],
    period: str,
    release_at: datetime | None,
) -> tuple[ContextScalar, ...]:
    _required_iso_date(period, "official_context_period_invalid")
    header = (
        "操作日",
        "品种",
        "期限",
        "中标利率（%）",
        "投放量（亿元）",
        "到期量（亿元）",
    )
    try:
        rows = _table_with_header(tables, header)
    except ValueError as error:
        live_tables = _unique_tables(
            table
            for table in tables
            if table
            and len(table[0]) in {3, 4}
            and "逆回购操作情况期限" in _compact_text(table[0][0])
            and tuple(_compact_text(cell) for cell in table[0][-2:]) == ("投标量", "中标量")
        )
        if len(live_tables) != 1:
            raise error
        live_rows = [
            row
            for row in live_tables[0][1:]
            if len(row) == len(live_tables[0][0]) and _compact_text(row[0]) == "7天"
        ]
        if len(live_rows) != 1:
            raise ValueError("official_context_row_identity_mismatch") from error
        injection = _pbc_amount(live_rows[0][-1])
        scalars = [
            _official_scalar(
                "CN_OMO_7D_AMOUNT",
                "pbc_omo_notice",
                "injection_100m",
                "business_day",
                period,
                period,
                {"measure": "injection"},
                injection,
                "hundred_million_cny",
                release_at,
            )
        ]
        if len(live_rows[0]) == 4:
            scalars.insert(
                0,
                _official_scalar(
                    "CN_OMO_7D_RATE",
                    "pbc_omo_notice",
                    "operation_rate_pct",
                    "business_day",
                    period,
                    period,
                    {},
                    _percent(_compact_text(live_rows[0][1])),
                    "percent",
                    release_at,
                ),
            )
        return tuple(scalars)
    matching = [
        row
        for row in rows[1:]
        if len(row) == len(header) and row[1] == "逆回购" and row[2] == "7天"
    ]
    if len(matching) != 1 or matching[0][0] != period:
        raise ValueError("official_context_row_identity_mismatch")
    row = matching[0]
    rate = _bounded_number(row[3], minimum=0, maximum=100)
    injection = _bounded_number(row[4], minimum=0)
    maturity = _bounded_number(row[5], minimum=0)
    return (
        _official_scalar(
            "CN_OMO_7D_RATE",
            "pbc_omo_notice",
            "operation_rate_pct",
            "business_day",
            period,
            period,
            {},
            rate,
            "percent",
            release_at,
        ),
        _official_scalar(
            "CN_OMO_7D_AMOUNT",
            "pbc_omo_notice",
            "injection_100m",
            "business_day",
            period,
            period,
            {"measure": "injection"},
            injection,
            "hundred_million_cny",
            release_at,
        ),
        _official_scalar(
            "CN_OMO_7D_AMOUNT",
            "pbc_omo_notice",
            "maturity_100m",
            "business_day",
            period,
            period,
            {"measure": "maturity"},
            maturity,
            "hundred_million_cny",
            release_at,
        ),
    )


def _parse_rrr_notice(
    tables: list[list[tuple[str, ...]]],
    text: str,
    period: str,
    release_at: datetime | None,
) -> tuple[ContextScalar, ...]:
    period_start, period_end = month_bounds(period)
    header = (
        "生效日期",
        "调整（百分点）",
        "机构范围",
        "调整后准备金率（%）",
        "释放资金（亿元）",
    )
    try:
        rows = _table_with_header(tables, header)
    except ValueError as error:
        year, month = (int(item) for item in period.split("-"))
        matches = re.findall(
            r"(?P<month>\d{1,2})月(?P<day>\d{1,2})日[^。；]{0,80}"
            r"下调金融机构存款准备金率\s*(?P<change>\d+(?:\.\d+)?)\s*个百分点"
            r"(?P<scope>[^。]*)",
            text,
        )
        matching = [item for item in matches if int(item[0]) == month]
        if len(matching) != 1:
            raise error
        matched_month, day, change, scope_text = matching[0]
        effective_date = date(year, int(matched_month), int(day)).isoformat()
        scope_details = re.fullmatch(
            r"\s*(?P<exclusion>[（(]不含已执行\s*5\s*%\s*存款准备金率的金融机构[）)])?\s*"
            r"(?:[，,；;]\s*下调汽车金融公司和金融租赁公司存款准备金率"
            r"\s*(?P<targeted_change>\d+(?:\.\d+)?)\s*个百分点)?\s*",
            scope_text,
        )
        if scope_details is None:
            raise ValueError("official_context_rrr_scope_incomplete") from None
        scope = (
            "excluding_5_percent_institutions"
            if scope_details.group("exclusion") is not None
            else "all_eligible_financial_institutions"
        )
        scope_changes = [(scope, change)]
        targeted_change = scope_details.group("targeted_change")
        if targeted_change is not None:
            scope_changes.append(("auto_finance_and_financial_leasing_companies", targeted_change))
        return tuple(
            _official_scalar(
                "CN_RRR_EVENT",
                "pbc_rrr_notice",
                "rrr_change_pp",
                "event",
                effective_date,
                effective_date,
                {"scope": event_scope, "measure": "rrr_change"},
                -_bounded_number(event_change, minimum=0, maximum=100),
                "percentage_points",
                release_at,
            )
            for event_scope, event_change in scope_changes
        )
    matching = [row for row in rows[1:] if len(row) == len(header)]
    if len(matching) != 1:
        raise ValueError("official_context_row_identity_mismatch")
    effective_date = _required_iso_date(
        matching[0][0],
        "official_context_effective_date_invalid",
    )
    if not period_start <= effective_date <= period_end:
        raise ValueError("official_context_effective_period_mismatch")
    scope = matching[0][2].strip()
    if not scope:
        raise ValueError("official_context_scope_missing")
    values = (
        ("rrr_change", "rrr_change_pp", matching[0][1], "percentage_points"),
        ("post_change_rrr", "post_change_rrr_pct", matching[0][3], "percent"),
        ("released_funds", "released_funds_100m", matching[0][4], "hundred_million_cny"),
    )
    return tuple(
        _official_scalar(
            "CN_RRR_EVENT",
            "pbc_rrr_notice",
            source_field,
            "event",
            effective_date,
            effective_date,
            {"scope": scope, "measure": measure},
            _bounded_number(raw_value),
            unit,
            release_at,
        )
        for measure, source_field, raw_value, unit in values
    )


# The PBC's row names for one member. From August 2026 the table reads "隔夜、7天期逆回购"
# where it read "7天期逆回购": the one short reverse repo series, continued (run findings
# 03). The original keeps the row name; any other name is left as written and refused.
_TOOL_LIQUIDITY_ROW_MEMBERS = {
    "7天期逆回购": "短期逆回购",
    "隔夜、7天期逆回购": "短期逆回购",
}


def _parse_tool_liquidity(
    tables: list[list[tuple[str, ...]]],
    period: str,
    release_at: datetime | None,
) -> tuple[ContextScalar, ...]:
    period_start, period_end = month_bounds(period)
    header = ("工具", "投放（亿元）", "回笼（亿元）", "净投放（亿元）")
    live_shape = False
    try:
        rows = _table_with_header(tables, header)
    except ValueError as error:
        live_tables = _unique_tables(
            table
            for table in tables
            if table
            and len(table[0]) == 5
            and _compact_text(table[0][0]).endswith("工具类型")
            and tuple(_compact_text(cell) for cell in table[0][1:])
            == ("工具名称", "投放", "回笼", "净投放")
        )
        if len(live_tables) != 1:
            raise error
        rows = live_tables[0]
        live_shape = True
    scalars: list[ContextScalar] = []
    for row in rows[1:]:
        if live_shape:
            if len(row) == 5:
                tool, values = row[1], (row[2], row[3], row[4])
            elif len(row) == 4:
                tool, values = row[0], (row[1], row[2], row[3])
            else:
                raise ValueError("official_context_row_identity_mismatch")
            if values == ("-", "-", "-"):
                continue
        else:
            if len(row) != len(header) or not row[0].strip():
                raise ValueError("official_context_row_identity_mismatch")
            tool, values = row[0], (row[1], row[2], row[3])
        if not tool.strip():
            raise ValueError("official_context_row_identity_mismatch")
        tool = _TOOL_LIQUIDITY_ROW_MEMBERS.get(_compact_text(tool), tool.strip())
        injection = _bounded_number(values[0], minimum=0)
        withdrawal = _bounded_number(values[1], minimum=0)
        net = _bounded_number(values[2])
        if abs(injection - withdrawal - net) > 1e-6:
            raise ValueError("official_context_liquidity_identity_mismatch")
        for source_field, measure, value in (
            ("injection_100m", "injection", injection),
            ("withdrawal_100m", "withdrawal", withdrawal),
            ("net_injection_100m", "net_injection", net),
        ):
            scalars.append(
                _official_scalar(
                    "CN_TOOL_LIQUIDITY_MONTHLY",
                    "pbc_tool_liquidity_monthly",
                    source_field,
                    "month",
                    period_start,
                    period_end,
                    {"tool": tool, "measure": measure},
                    value,
                    "hundred_million_cny",
                    release_at,
                )
            )
    if not scalars:
        raise ValueError("official_context_observations_missing")
    return tuple(scalars)


def _parse_social_financing(
    tables: list[list[tuple[str, ...]]],
    text: str,
    period: str,
    release_at: datetime | None,
) -> tuple[ContextScalar, ...]:
    period_start, period_end = month_bounds(period)
    try:
        increment_rows = _rows_by_first_cell(
            _table_with_header(tables, ("分项", "当月增量（亿元）"))
        )
        stock_rows = _rows_by_first_cell(
            _table_with_header(tables, ("分项", "期末存量（万亿元）", "同比（%）"))
        )
    except ValueError:
        return _parse_social_financing_live(text, period, release_at)
    required = set(_SOCIAL_FINANCING_COMPONENTS)
    if set(increment_rows) != required or set(stock_rows) != required:
        raise ValueError("official_context_social_financing_components_mismatch")
    scalars: list[ContextScalar] = []
    for label, component in _SOCIAL_FINANCING_COMPONENTS.items():
        increment = increment_rows[label]
        stock = stock_rows[label]
        metric_id = "CN_SF_TOTAL" if component == "total" else "CN_SF_COMPONENTS"
        for source_field, measure, value, unit in (
            (
                "monthly_increment_100m",
                "monthly_increment",
                _bounded_number(increment[1]),
                "hundred_million_cny",
            ),
            (
                "stock_end_trillion",
                "stock_end",
                _bounded_number(stock[1], minimum=0) * 10_000,
                "hundred_million_cny",
            ),
            ("stock_yoy_pct", "stock_yoy", _percent(stock[2]), "percent"),
        ):
            dimensions = {"measure": measure}
            if component != "total":
                dimensions = {"component": component, "measure": measure}
            scalars.append(
                _official_scalar(
                    metric_id,
                    "pbc_social_financing",
                    source_field,
                    "month",
                    period_start,
                    period_end,
                    dimensions,
                    value,
                    unit,
                    release_at,
                )
            )
    return tuple(scalars)


def _parse_social_financing_live(
    text: str,
    period: str,
    release_at: datetime | None,
) -> tuple[ContextScalar, ...]:
    period_start, period_end = month_bounds(period)
    year_start = f"{period[:4]}-01-01"
    compact = _compact_text(text)
    has_stock = "社会融资规模存量为" in compact
    has_increment = any(
        label in compact for label in ("社会融资规模增量累计为", "社会融资规模增量为")
    )
    if not has_stock and not has_increment:
        raise ValueError("official_context_social_financing_components_mismatch")
    scalars: list[ContextScalar] = []
    if has_stock:
        total_stock, total_yoy = _stock_level_and_yoy(
            compact,
            "社会融资规模存量为",
        )
        scalars.extend(
            (
                _official_scalar(
                    "CN_SF_TOTAL",
                    "pbc_social_financing",
                    "stock_end_trillion",
                    "month",
                    period_start,
                    period_end,
                    {"measure": "stock_end"},
                    total_stock,
                    "hundred_million_cny",
                    release_at,
                ),
                _official_scalar(
                    "CN_SF_TOTAL",
                    "pbc_social_financing",
                    "stock_yoy_pct",
                    "month",
                    period_start,
                    period_end,
                    {"measure": "stock_yoy"},
                    total_yoy,
                    "percent",
                    release_at,
                ),
            )
        )
    if has_increment:
        total_increment = _signed_amount_after_first_label(
            compact,
            ("社会融资规模增量累计为", "社会融资规模增量为"),
        )
        scalars.append(
            _official_scalar(
                "CN_SF_TOTAL",
                "pbc_social_financing",
                "ytd_increment_100m",
                "year_to_month",
                year_start,
                period_end,
                {"measure": "ytd_increment"},
                total_increment,
                "hundred_million_cny",
                release_at,
            )
        )
    for component, (stock_label, increment_label) in _LIVE_SOCIAL_FINANCING_COMPONENTS.items():
        component_values: list[tuple[str, str, str, str, float, str]] = []
        if has_stock:
            stock, yoy = _stock_level_and_yoy(compact, stock_label)
            component_values.extend(
                (
                    (
                        "stock_end_trillion",
                        "month",
                        period_start,
                        "stock_end",
                        stock,
                        "hundred_million_cny",
                    ),
                    (
                        "stock_yoy_pct",
                        "month",
                        period_start,
                        "stock_yoy",
                        yoy,
                        "percent",
                    ),
                )
            )
        if has_increment:
            component_values.append(
                (
                    "ytd_increment_100m",
                    "year_to_month",
                    year_start,
                    "ytd_increment",
                    _signed_amount_after_label(compact, increment_label),
                    "hundred_million_cny",
                )
            )
        for source_field, period_kind, start, measure, value, unit in component_values:
            scalars.append(
                _official_scalar(
                    "CN_SF_COMPONENTS",
                    "pbc_social_financing",
                    source_field,
                    period_kind,
                    start,
                    period_end,
                    {"component": component, "measure": measure},
                    value,
                    unit,
                    release_at,
                )
            )
    return tuple(scalars)


def _parse_loan_structure(
    tables: list[list[tuple[str, ...]]],
    text: str,
    period: str,
    release_at: datetime | None,
) -> tuple[ContextScalar, ...]:
    period_start, period_end = month_bounds(period)
    try:
        rows = _table_with_header(tables, ("借款人", "期限", "月末存量（亿元）"))
    except ValueError:
        return _parse_loan_structure_live(text, period, release_at)
    observed: dict[tuple[str, str], tuple[str, ...]] = {}
    for row in rows[1:]:
        if len(row) != 3:
            raise ValueError("official_context_row_identity_mismatch")
        key = (row[0], row[1])
        if key in observed:
            raise ValueError("official_context_duplicate_row_identity")
        observed[key] = row
    if set(observed) != set(_LOAN_STRUCTURE_ROWS):
        raise ValueError("official_context_loan_structure_rows_mismatch")
    return tuple(
        _official_scalar(
            "CN_LOAN_STRUCTURE",
            "pbc_loan_structure",
            "stock_end_100m",
            "month",
            period_start,
            period_end,
            {"borrower": borrower, "tenor": tenor, "measure": "stock_end"},
            _bounded_number(observed[source_key][2], minimum=0),
            "hundred_million_cny",
            release_at,
        )
        for source_key, (borrower, tenor) in _LOAN_STRUCTURE_ROWS.items()
    )


def _parse_loan_structure_live(
    text: str,
    period: str,
    release_at: datetime | None,
) -> tuple[ContextScalar, ...]:
    _, period_end = month_bounds(period)
    year_start = f"{period[:4]}-01-01"
    compact = _compact_text(text)
    household_match = re.search(
        r"(?P<section>住户贷款(?:增加|减少)\d+(?:\.\d+)?(?:万亿元|亿元)，"
        r"其中，短期贷款(?:增加|减少)\d+(?:\.\d+)?(?:万亿元|亿元)，"
        r"中长期贷款(?:增加|减少)\d+(?:\.\d+)?(?:万亿元|亿元))；"
        r"(?P<enterprise>企（事）业单位贷款(?:增加|减少)\d+(?:\.\d+)?(?:万亿元|亿元)，"
        r"其中，短期贷款(?:增加|减少)\d+(?:\.\d+)?(?:万亿元|亿元)，"
        r"中长期贷款(?:增加|减少)\d+(?:\.\d+)?(?:万亿元|亿元)，"
        r"票据融资(?:增加|减少)\d+(?:\.\d+)?(?:万亿元|亿元))；"
        r"(?P<nonbank>非银行业金融机构贷款(?:增加|减少)\d+(?:\.\d+)?(?:万亿元|亿元))",
        compact,
    )
    if household_match is None:
        raise ValueError("official_context_loan_structure_rows_mismatch")
    household = household_match.group("section")
    enterprise = household_match.group("enterprise")
    nonbank = household_match.group("nonbank")
    values = {
        ("household", "total"): _signed_amount_after_label(household, "住户贷款"),
        ("household", "short_term"): _signed_amount_after_label(household, "短期贷款"),
        ("household", "long_term"): _signed_amount_after_label(household, "中长期贷款"),
        ("enterprise", "total"): _signed_amount_after_label(enterprise, "企（事）业单位贷款"),
        ("enterprise", "short_term"): _signed_amount_after_label(enterprise, "短期贷款"),
        ("enterprise", "long_term"): _signed_amount_after_label(enterprise, "中长期贷款"),
        ("enterprise", "bill_financing"): _signed_amount_after_label(enterprise, "票据融资"),
        ("nonbank_financial", "total"): _signed_amount_after_label(nonbank, "非银行业金融机构贷款"),
        ("all_rmb_loans", "total"): _signed_amount_after_label(
            compact, _year_to_date_label(period, "人民币贷款")
        ),
    }
    return tuple(
        _official_scalar(
            "CN_LOAN_STRUCTURE",
            "pbc_loan_structure",
            "ytd_increment_100m",
            "year_to_month",
            year_start,
            period_end,
            {"borrower": borrower, "tenor": tenor, "measure": "ytd_increment"},
            value,
            "hundred_million_cny",
            release_at,
        )
        for (borrower, tenor), value in values.items()
    )


def _parse_money(
    text: str,
    period: str,
    release_at: datetime | None,
) -> tuple[ContextScalar, ...]:
    period_start, period_end = month_bounds(period)
    compact = _compact_text(text)
    values: list[tuple[str, float, float]] = []
    for aggregate, chinese in (("m1", "狭义货币"), ("m2", "广义货币")):
        match = re.search(
            rf"{re.escape(chinese)}[（(]{aggregate.upper()}[）)]余额"
            rf"(?P<balance>\d+(?:\.\d+)?)万亿元[，,]"
            rf"同比(?P<direction>增长|下降)(?P<yoy>\d+(?:\.\d+)?)%",
            compact,
        )
        if match is None:
            raise ValueError("official_context_money_values_missing")
        yoy = _bounded_number(match.group("yoy"), minimum=0)
        if match.group("direction") == "下降":
            yoy = -yoy
        values.append(
            (
                aggregate,
                float(Decimal(match.group("balance")) * 10_000),
                yoy,
            )
        )
    return tuple(
        _official_scalar(
            "CN_M1_M2",
            "pbc_money",
            source_field,
            "month",
            period_start,
            period_end,
            {"aggregate": aggregate, "measure": measure},
            value,
            unit,
            release_at,
        )
        for aggregate, balance_100m, yoy in values
        for source_field, measure, value, unit in (
            (aggregate, "balance", balance_100m, "hundred_million_cny"),
            (f"{aggregate}_yoy", "yoy", yoy, "percent"),
        )
    )


def _year_to_date_label(period: str, subject: str) -> str:
    month = int(period[5:])
    names = {
        1: "1月份",
        2: "前两个月",
        3: "一季度",
        4: "前四个月",
        5: "前五个月",
        6: "上半年",
        7: "前七个月",
        8: "前八个月",
        9: "前三季度",
        10: "前十个月",
        11: "前十一个月",
        12: "全年",
    }
    return f"{names[month]}{subject}"


def _parse_usdcny_central_parity(
    text: str,
    period: str,
    release_at: datetime | None,
) -> tuple[ContextScalar, ...]:
    business_date = _required_iso_date(period, "official_context_period_invalid")
    year, month, day = (int(part) for part in business_date.split("-"))
    if f"{year}年{month}月{day}日" not in text:
        raise ValueError("official_context_period_identity_mismatch")
    values = re.findall(r"1美元对人民币\s*([0-9]+(?:\.[0-9]+)?)\s*元", text)
    if len(values) != 1:
        raise ValueError("official_context_usdcny_quote_missing")
    return (
        _official_scalar(
            "CN_USDCNY_CENTRAL_PARITY",
            "pbc_usdcny_central_parity",
            "usd_cny_central_parity",
            "business_day",
            business_date,
            business_date,
            {
                "currency_pair": "USD/CNY",
                "quote_direction": "CNY per USD",
            },
            _bounded_number(values[0], minimum=1, maximum=20),
            "cny_per_usd",
            release_at,
        ),
    )


def _table_with_header(
    tables: list[list[tuple[str, ...]]],
    header: tuple[str, ...],
) -> list[tuple[str, ...]]:
    matching = [table for table in tables if table and table[0] == header]
    if len(matching) != 1:
        raise ValueError("official_context_table_schema_mismatch")
    return matching[0]


def _pmi_period_row(
    tables: list[list[tuple[str, ...]]],
    target_period: str,
    *,
    required_headers: tuple[str, ...],
) -> tuple[str, ...]:
    normalized_target = _compact_text(target_period)
    matching: set[tuple[str, ...]] = set()
    for table in tables:
        header_text = "".join(_compact_text(cell) for row in table[:3] for cell in row)
        if not all(_compact_text(header) in header_text for header in required_headers):
            continue
        matching.update(row for row in table if row and _compact_text(row[0]) == normalized_target)
    if len(matching) != 1:
        raise ValueError("official_context_row_identity_mismatch")
    return next(iter(matching))


def _table_with_first_column_members(
    tables: list[list[tuple[str, ...]]],
    required: set[str],
) -> list[tuple[str, ...]]:
    matching = _unique_tables(
        table for table in tables if required <= {row[0] for row in table if row}
    )
    if len(matching) != 1:
        raise ValueError("official_context_table_schema_mismatch")
    return matching[0]


def _unique_first_cell_row(
    table: list[tuple[str, ...]],
    label: str,
) -> tuple[str, ...]:
    matching = [row for row in table if row and row[0] == label]
    if len(matching) != 1:
        raise ValueError("official_context_row_identity_mismatch")
    return matching[0]


def _consistent_first_column_rows(
    tables: list[list[tuple[str, ...]]],
    labels: tuple[str, ...],
) -> dict[str, tuple[str, ...]]:
    candidates: list[tuple[tuple[str, ...], ...]] = []
    for table in tables:
        observed = {row[0]: row for row in table if row and row[0] in labels}
        if set(observed) == set(labels):
            candidates.append(tuple(observed[label] for label in labels))
    unique = set(candidates)
    if len(unique) != 1:
        raise ValueError("official_context_table_schema_mismatch")
    return dict(zip(labels, next(iter(unique)), strict=True))


def _rows_by_first_cell(table: list[tuple[str, ...]]) -> dict[str, tuple[str, ...]]:
    rows: dict[str, tuple[str, ...]] = {}
    for row in table[1:]:
        if not row or not row[0]:
            raise ValueError("official_context_row_identity_mismatch")
        if row[0] in rows:
            raise ValueError("official_context_duplicate_row_identity")
        rows[row[0]] = row
    return rows


def _validate_fetched_document(
    family: str,
    source_url: str,
    response: FetchedOfficialContextDocument,
) -> None:
    if response.http_status != 200:
        # An answer that is itself a failure, not a response to check (ticket 18).
        raise SourceFailed(
            "official_context_source_http_status_invalid", external_code=response.http_status
        )
    _validate_source_identity(family, response.final_url)
    if response.final_url != source_url:
        raise ValueError("official_context_source_redirect_identity_changed")
    _validate_html_media_type(response.media_type)


def _validate_html_media_type(media_type: str) -> None:
    if media_type.split(";", maxsplit=1)[0].strip().lower() != "text/html":
        raise ValueError("official_context_response_media_type_invalid")


def _validate_source_identity(family: str, source_url: str) -> str:
    try:
        provider, host = _PROVIDERS[family]
    except KeyError as error:
        raise ValueError("official_context_family_unsupported") from error
    parsed = urlsplit(source_url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != host
        or parsed.port not in {None, 443}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or not parsed.path.startswith(_PATHS[family])
    ):
        raise ValueError("official_context_source_url_not_official")
    return provider


def _release_timestamp(text: str) -> datetime | date | None:
    matches = re.findall(
        r"(?:发布时间|文章来源)[：:]\s*(\d{4}-\d{2}-\d{2})\s+"
        r"(\d{2}:\d{2}(?::\d{2})?)",
        text,
    )
    if not matches:
        slash_matches = {
            (f"{year}-{month}-{day}", timestamp)
            for year, month, day, timestamp in re.findall(
                r"(?<!\d)(\d{4})/(\d{2})/(\d{2})\s+"
                r"(\d{2}:\d{2}(?::\d{2})?)",
                text,
            )
        }
        matches = sorted(slash_matches)
    if not matches:
        dates = set(
            re.findall(r"(?:发布时间|发布日期|文章来源)[：:]\s*(\d{4}-\d{2}-\d{2})(?![\d-])", text)
        )
        if len(dates) > 1:
            raise ValueError("official_context_release_timestamp_conflict")
        return date.fromisoformat(next(iter(dates))) if dates else None
    if len(set(matches)) != 1:
        raise ValueError("official_context_release_timestamp_conflict")
    timestamp = matches[0][1]
    if timestamp.count(":") == 1:
        timestamp += ":00"
    return datetime.fromisoformat(f"{matches[0][0]}T{timestamp}").replace(
        tzinfo=ZoneInfo("Asia/Shanghai")
    )


def _period_is_identified(text: str, period: str) -> bool:
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", period):
        return period in text
    if re.fullmatch(r"\d{4}-\d{2}", period):
        year, month = period.split("-")
        month_number = int(month)
        aggregate_label = {
            3: "一季度",
            6: "上半年",
            9: "前三季度",
            12: "全年",
        }.get(month_number)
        return (
            re.search(rf"{year}年(?:1[—-])?0?{month_number}月份?", text) is not None
            or re.search(rf"{year}年.*?0?{month_number}月", text) is not None
            or (
                aggregate_label is not None
                and re.search(rf"{year}年{aggregate_label}", text) is not None
            )
            or (
                month_number == 12
                and re.search(rf"{year}年(?:社会融资规模|金融统计)", text) is not None
            )
        )
    if re.fullmatch(r"\d{4}-Q[1-4]", period):
        year, quarter = period.split("-Q")
        names = {"1": "(?:一|1)", "2": "(?:二|2)", "3": "(?:三|3)", "4": "(?:四|4)"}
        return re.search(rf"{year}年第?{names[quarter]}季度", text) is not None
    raise ValueError("official_context_period_invalid")


def _percent(value: str) -> float:
    normalized = value.removesuffix("%").strip()
    try:
        parsed = float(normalized)
    except ValueError as error:
        raise ValueError("official_context_numeric_value_invalid") from error
    if not -100 < parsed < 100:
        raise ValueError("official_context_percent_out_of_range")
    return parsed


def _bounded_number(
    value: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    normalized = value.replace(",", "").strip()
    try:
        parsed = float(normalized)
    except ValueError as error:
        raise ValueError("official_context_numeric_value_invalid") from error
    if minimum is not None and parsed < minimum:
        raise ValueError("official_context_numeric_value_out_of_range")
    if maximum is not None and parsed > maximum:
        raise ValueError("official_context_numeric_value_out_of_range")
    return parsed


def _pbc_amount(value: str) -> float:
    normalized = _compact_text(value)
    match = re.fullmatch(r"([+-]?\d+(?:\.\d+)?)亿元", normalized)
    if match is None:
        raise ValueError("official_context_numeric_value_invalid")
    return _bounded_number(match.group(1), minimum=0)


def _stock_level_and_yoy(text: str, label: str) -> tuple[float, float]:
    match = re.search(
        re.escape(label) + r"为?(?P<level>\d+(?:\.\d+)?)万亿元[，,]同比"
        r"(?:(?P<direction>增长|下降)(?P<yoy>\d+(?:\.\d+)?)%|(?P<flat>持平))",
        text,
    )
    if match is None:
        raise ValueError("official_context_social_financing_components_mismatch")
    yoy = 0.0 if match.group("flat") is not None else _bounded_number(match.group("yoy"))
    if match.group("direction") == "下降":
        yoy = -yoy
    return round(_bounded_number(match.group("level"), minimum=0) * 10_000, 6), yoy


def _signed_amount_after_label(text: str, label: str) -> float:
    match = re.search(
        re.escape(label) + r"(?P<direction>增加|减少|净融资)?(?P<value>\d+(?:\.\d+)?)"
        r"(?P<unit>万亿元|亿元)",
        text,
    )
    if match is None:
        raise ValueError("official_context_numeric_value_invalid")
    value = _bounded_number(match.group("value"), minimum=0)
    if match.group("unit") == "万亿元":
        value = round(value * 10_000, 6)
    return -value if match.group("direction") == "减少" else value


def _signed_amount_after_first_label(text: str, labels: tuple[str, ...]) -> float:
    for label in labels:
        if label in text:
            return _signed_amount_after_label(text, label)
    raise ValueError("official_context_numeric_value_invalid")


def _compact_text(value: str) -> str:
    return re.sub(r"\s+", "", value)


def _unique_tables(
    tables: Iterable[list[tuple[str, ...]]],
) -> list[list[tuple[str, ...]]]:
    unique: list[list[tuple[str, ...]]] = []
    for table in tables:
        if table not in unique:
            unique.append(table)
    return unique


def _required_iso_date(value: str, error_code: str) -> str:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as error:
        raise ValueError(error_code) from error
    return parsed.isoformat()


def _quarter_bounds(value: str) -> tuple[str, str, str]:
    match = re.fullmatch(r"(?P<year>\d{4})-Q(?P<quarter>[1-4])", value)
    if match is None:
        raise ValueError("official_context_period_invalid")
    year = int(match.group("year"))
    quarter = int(match.group("quarter"))
    first_month = (quarter - 1) * 3 + 1
    final_month = quarter * 3
    final_day = calendar.monthrange(year, final_month)[1]
    return (
        f"{year:04d}-01-01",
        f"{year:04d}-{first_month:02d}-01",
        f"{year:04d}-{final_month:02d}-{final_day:02d}",
    )


def _official_scalar(
    metric_id: str,
    api_name: str,
    source_field: str,
    period_kind: str,
    period_start: str,
    period_end: str,
    dimensions: dict[str, str],
    value: float,
    unit: str,
    release_at: datetime | None,
) -> ContextScalar:
    return ContextScalar(
        metric_id=metric_id,
        api_name=api_name,
        source_field=source_field,
        period_kind=period_kind,
        period_start=period_start,
        period_end=period_end,
        dimensions=dimensions,
        value=value,
        unit=unit,
        release_at=release_at,
        public_available_at=release_at,
    )


def _normalized_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _decode_document(content: bytes) -> str:
    for encoding in ("utf-8", "gb18030"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("official_context_document_encoding_invalid")
