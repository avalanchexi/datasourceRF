from __future__ import annotations

import calendar
import hashlib
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date, datetime
from html.parser import HTMLParser
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from pring_cycle.artifacts import store_artifact
from pring_cycle.catalog import METRIC_CATALOG_VERSION, metric_definition
from pring_cycle.evidence import (
    EvidenceRepository,
    EvidenceValueState,
    SourceClaimInput,
    StoredSourceClaim,
)
from pring_cycle.release_calendar import month_bounds
from pring_cycle.runtime import RuntimePaths
from pring_cycle.source_families import OFFICIAL_CONTEXT_FAMILIES
from pring_cycle.tushare_context import ContextScalar

MAX_OFFICIAL_CONTEXT_BYTES = 4_000_000

_PROVIDERS = {
    family: (descriptor.provider, descriptor.host)
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


@dataclass(frozen=True)
class ParsedOfficialContextRelease:
    family: str
    provider: str
    release_event_id: str
    period: str
    release_at: datetime
    public_available_at: datetime
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
    release_at: datetime
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
    release_at = _release_timestamp(text)
    if fetched_at < release_at:
        raise ValueError("official_context_fetched_before_release")
    if not _period_is_identified(text, expected_period):
        raise ValueError("official_context_period_identity_mismatch")
    scalars = _parse_family(family, parser.tables, text, expected_period, release_at)
    return ParsedOfficialContextRelease(
        family=family,
        provider=provider,
        release_event_id=f"official:{family}:{expected_period}:{release_at.isoformat()}",
        period=expected_period,
        release_at=release_at,
        public_available_at=release_at,
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
) -> OfficialContextIngestionResult:
    _validate_html_media_type(media_type)
    parsed = parse_official_context_document(
        content,
        family=family,
        source_url=source_url,
        expected_period=expected_period,
        fetched_at=fetched_at,
    )
    artifact = store_artifact(
        paths.database,
        paths.artifacts,
        content,
        "text/html",
        source_url,
    )
    source_reference = f"{source_url}#sha256={artifact.content_hash}"
    definitions = {
        scalar.metric_id: metric_definition(
            scalar.metric_id,
            definition_version=definition_version,
        )
        for scalar in parsed.scalars
    }
    repository = EvidenceRepository(paths.database)
    existing = repository.claims_for_release_source(
        parsed.release_event_id,
        source_reference,
        definition_version=definition_version,
    )
    if existing and len(existing) != len(parsed.scalars):
        raise ValueError("official_context_release_claim_set_incomplete")
    release_event_id = parsed.release_event_id
    if existing:
        stored = existing
    else:
        exact_previous = tuple(
            repository.latest_provider_claim(
                metric_id=scalar.metric_id,
                definition_version=definitions[scalar.metric_id].definition_version,
                period_kind=scalar.period_kind,
                period_start=scalar.period_start,
                period_end=scalar.period_end,
                dimensions=scalar.dimensions,
                provider=parsed.provider,
            )
            for scalar in parsed.scalars
        )
        physical_previous = tuple(
            repository.latest_provider_claim(
                metric_id=scalar.metric_id,
                period_kind=scalar.period_kind,
                period_start=scalar.period_start,
                period_end=scalar.period_end,
                dimensions=scalar.dimensions,
                provider=parsed.provider,
            )
            for scalar in parsed.scalars
        )
        exact_same = all(
            previous is not None
            and previous.value_state is EvidenceValueState.REPORTED_VALUE
            and previous.value == scalar.value
            and previous.unit == scalar.unit
            for previous, scalar in zip(exact_previous, parsed.scalars, strict=True)
        )
        cross_version_same = all(previous is None for previous in exact_previous) and all(
            previous is not None
            and previous.value_state is EvidenceValueState.REPORTED_VALUE
            and previous.value == scalar.value
            and previous.unit == scalar.unit
            for previous, scalar in zip(
                physical_previous,
                parsed.scalars,
                strict=True,
            )
        )
        if exact_same:
            stored = tuple(
                StoredSourceClaim(
                    previous.claim_id,
                    previous.observation_id,
                    previous.supersedes_claim_id,
                )
                for previous in exact_previous
                if previous is not None
            )
            release_event_id = exact_previous[0].release_event_id  # type: ignore[union-attr]
        else:
            if cross_version_same:
                prior = physical_previous[0]
                assert prior is not None
                release_event_id = prior.release_event_id
                release_at = prior.release_at
                public_available_at = prior.public_available_at
            elif any(previous is not None for previous in physical_previous):
                release_event_id = _revision_event_id(parsed.release_event_id, fetched_at)
                release_at = parsed.release_at
                public_available_at = fetched_at
            else:
                release_at = parsed.release_at
                public_available_at = parsed.public_available_at
            claims = tuple(
                SourceClaimInput(
                    metric_id=scalar.metric_id,
                    definition_version=definitions[scalar.metric_id].definition_version,
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
                    public_available_at=public_available_at,
                    fetched_at=fetched_at,
                    available_at=fetched_at,
                    certification_status=(
                        definitions[scalar.metric_id].certification_status
                    ),
                    quality_status="validated",
                )
                for scalar in parsed.scalars
            )
            stored = repository.append_source_claims(claims)
    metric_ids = tuple(sorted({scalar.metric_id for scalar in parsed.scalars}))
    for metric_id in metric_ids:
        repository.record_retrieval_attempt(
            metric_id=metric_id,
            channel="official_direct_candidate",
            outcome="verified_candidate",
            fetched_at=fetched_at,
            safe_metadata={
                "artifact_hash": artifact.content_hash,
                "family": family,
                "period": expected_period,
                "provider": parsed.provider,
            },
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


def _revision_event_id(base_event_id: str, fetched_at: datetime) -> str:
    suffix = hashlib.sha256(fetched_at.isoformat().encode()).hexdigest()[:16]
    return f"{base_event_id}:revision:{suffix}"


def refresh_official_context_document(
    paths: RuntimePaths,
    *,
    family: str,
    source_url: str,
    expected_period: str,
    fetched_at: datetime,
    fetcher: Callable[[str], FetchedOfficialContextDocument] | None = None,
    definition_version: str = METRIC_CATALOG_VERSION,
) -> OfficialContextIngestionResult:
    _validate_source_identity(family, source_url)
    if fetched_at.tzinfo is None:
        raise ValueError("official_context_fetched_at_must_be_timezone_aware")
    try:
        response = (fetcher or _fetch_official_context_document)(source_url)
        _validate_fetched_document(family, source_url, response)
        return ingest_official_context_document(
            paths,
            response.content,
            family=family,
            source_url=source_url,
            expected_period=expected_period,
            fetched_at=fetched_at,
            media_type=response.media_type,
            definition_version=definition_version,
        )
    except (OSError, TypeError, ValueError) as error:
        repository = EvidenceRepository(paths.database)
        for metric_id in sorted(_FAMILY_METRICS[family]):
            repository.record_retrieval_attempt(
                metric_id=metric_id,
                channel="official_direct_candidate",
                outcome="source_failed",
                fetched_at=fetched_at,
                safe_metadata={
                    "error_type": type(error).__name__,
                    "family": family,
                    "period": expected_period,
                },
            )
        raise


def smoke_official_context_document(
    *,
    family: str,
    source_url: str,
    expected_period: str,
    fetched_at: datetime,
    fetcher: Callable[[str], FetchedOfficialContextDocument] | None = None,
) -> OfficialContextSmokeResult:
    _validate_source_identity(family, source_url)
    response = (fetcher or _fetch_official_context_document)(source_url)
    _validate_fetched_document(family, source_url, response)
    parsed = parse_official_context_document(
        response.content,
        family=family,
        source_url=source_url,
        expected_period=expected_period,
        fetched_at=fetched_at,
    )
    return OfficialContextSmokeResult(
        status="validated_candidate",
        family=family,
        provider=parsed.provider,
        final_url=response.final_url,
        period=parsed.period,
        release_at=parsed.release_at,
        metric_ids=tuple(sorted({scalar.metric_id for scalar in parsed.scalars})),
        first_period=min(scalar.period_end for scalar in parsed.scalars),
        last_period=max(scalar.period_end for scalar in parsed.scalars),
        observation_count=len(parsed.scalars),
        content_hash=hashlib.sha256(response.content).hexdigest(),
        byte_count=len(response.content),
        http_status=response.http_status,
        network_requests=1,
    )


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
    if len(content) > MAX_OFFICIAL_CONTEXT_BYTES:
        raise ValueError("official_context_document_size_invalid")
    return FetchedOfficialContextDocument(content, media_type, final_url, status)


def _parse_family(
    family: str,
    tables: list[list[tuple[str, ...]]],
    text: str,
    period: str,
    release_at: datetime,
) -> tuple[ContextScalar, ...]:
    if family == "nbs_core_cpi":
        return _parse_core_cpi(tables, period, release_at)
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
    if family == "pbc_usdcny_central_parity":
        return _parse_usdcny_central_parity(text, period, release_at)
    raise ValueError("official_context_family_unsupported")


def _parse_core_cpi(
    tables: list[list[tuple[str, ...]]],
    period: str,
    release_at: datetime,
) -> tuple[ContextScalar, ...]:
    header = ("指标", "环比（%）", "同比（%）", "累计平均同比（%）")
    try:
        rows = _table_with_header(tables, header)
    except ValueError as error:
        live_tables = _unique_tables(
            table
            for table in tables
            if table
            and tuple(_compact_text(cell) for cell in table[0])
            == ("", "环比涨跌幅（%）", "同比涨跌幅（%）", "1—7月同比涨跌幅（%）")
        )
        if len(live_tables) != 1:
            raise error
        rows = live_tables[0]
    matching = [
        row
        for row in rows[1:]
        if row and row[0].removeprefix("其中：") == "不包括食品和能源"
    ]
    if len(matching) != 1 or len(matching[0]) != len(header):
        raise ValueError("official_context_row_identity_mismatch")
    period_start, period_end = month_bounds(period)
    values = tuple(_percent(cell) for cell in matching[0][1:])
    return tuple(
        ContextScalar(
            metric_id="CN_CORE_CPI",
            api_name="nbs_core_cpi",
            source_field=source_field,
            period_kind="month",
            period_start=period_start,
            period_end=period_end,
            dimensions={"measure": measure, "category": "ex_food_energy"},
            value=value,
            unit="percent",
            release_at=release_at,
            public_available_at=release_at,
        )
        for source_field, measure, value in zip(
            ("core_cpi_mom_pct", "core_cpi_yoy_pct", "core_cpi_ytd_avg_yoy_pct"),
            ("mom", "yoy", "cumulative_average_yoy"),
            values,
            strict=True,
        )
    )


def _parse_industrial_value_added(
    tables: list[list[tuple[str, ...]]],
    period: str,
    release_at: datetime,
) -> tuple[ContextScalar, ...]:
    period_start, period_end = month_bounds(period)
    if period.endswith("-01"):
        raise ValueError("official_context_january_monthly_value_not_reported")
    header = ("指标", "当月实际同比（%）", "累计实际同比（%）", "季调环比（%）")
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
        sa_tables = _unique_tables(
            table
            for table in tables
            if table
            and tuple(_compact_text(cell) for cell in table[0])
            == ("年份", "月份", "环比增速（%）")
        )
        if len(main_tables) != 1 or len(sa_tables) != 1:
            raise error
        main_rows = [
            row
            for row in main_tables[0][2:]
            if row and row[0] == "规模以上工业增加值" and len(row) == 5
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
        current_yoy, ytd_yoy, mom_sa = main_rows[0][2], main_rows[0][4], mom_values[0]
    year_start = f"{period[:4]}-01-01"
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
        for source_field, measure, raw_value, period_kind, start in (
            (
                "industrial_va_yoy_real_pct",
                "current_month_real_yoy",
                current_yoy,
                "month",
                period_start,
            ),
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
        )
    )


def _parse_industrial_finance(
    tables: list[list[tuple[str, ...]]],
    text: str,
    period: str,
    release_at: datetime,
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
    release_at: datetime,
) -> tuple[ContextScalar, ...]:
    period_start, period_end = month_bounds(period)
    year_start = f"{period[:4]}-01-01"
    finance_tables = _unique_tables(
        table
        for table in tables
        if len(table) >= 3
        and tuple(_compact_text(cell) for cell in table[0])
        == ("分组", "营业收入", "营业成本", "利润总额")
        and tuple(_compact_text(cell) for cell in table[1])
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
        r"同比(?P<direction>增加|减少)(?P<change>\d+(?:\.\d+)?)天",
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


def _parse_capacity_utilization(
    tables: list[list[tuple[str, ...]]],
    period: str,
    release_at: datetime,
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
        if len(live_tables) != 1:
            raise error
        matching = [
            row
            for row in live_tables[0][2:]
            if row and row[0] == "工业" and len(row) == 5
        ]
        if len(matching) != 1:
            raise ValueError("official_context_row_identity_mismatch") from error
        quarter_rate, yoy_change, ytd_rate = matching[0][1:4]
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
    release_at: datetime,
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
            and len(table[0]) == 4
            and "逆回购操作情况期限" in _compact_text(table[0][0])
            and tuple(_compact_text(cell) for cell in table[0][1:])
            == ("操作利率", "投标量", "中标量")
        )
        if len(live_tables) != 1:
            raise error
        live_rows = [
            row
            for row in live_tables[0][1:]
            if len(row) == 4 and _compact_text(row[0]) == "7天"
        ]
        if len(live_rows) != 1:
            raise ValueError("official_context_row_identity_mismatch") from error
        rate = _percent(_compact_text(live_rows[0][1]))
        injection = _pbc_amount(live_rows[0][3])
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
        )
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
    release_at: datetime,
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
            r"(?P<scope>[^。；]*)",
            text,
        )
        matching = [item for item in matches if int(item[0]) == month]
        if len(matching) != 1:
            raise error
        matched_month, day, change, scope_text = matching[0]
        effective_date = date(year, int(matched_month), int(day)).isoformat()
        scope = (
            "excluding_5_percent_institutions"
            if re.search(r"不含已执行\s*5\s*%", scope_text)
            else "all_eligible_financial_institutions"
        )
        return (
            _official_scalar(
                "CN_RRR_EVENT",
                "pbc_rrr_notice",
                "rrr_change_pp",
                "event",
                effective_date,
                effective_date,
                {"scope": scope, "measure": "rrr_change"},
                -_bounded_number(change, minimum=0, maximum=100),
                "percentage_points",
                release_at,
            ),
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


def _parse_tool_liquidity(
    tables: list[list[tuple[str, ...]]],
    period: str,
    release_at: datetime,
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
                    {"tool": tool.strip(), "measure": measure},
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
    release_at: datetime,
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
    release_at: datetime,
) -> tuple[ContextScalar, ...]:
    period_start, period_end = month_bounds(period)
    year_start = f"{period[:4]}-01-01"
    compact = _compact_text(text)
    total_stock, total_yoy = _stock_level_and_yoy(compact, "社会融资规模存量为")
    total_increment = _signed_amount_after_label(compact, "社会融资规模增量累计为")
    scalars = [
        _official_scalar(
            "CN_SF_TOTAL",
            "pbc_social_financing",
            source_field,
            period_kind,
            start,
            period_end,
            {"measure": measure},
            value,
            unit,
            release_at,
        )
        for source_field, period_kind, start, measure, value, unit in (
            (
                "stock_end_trillion",
                "month",
                period_start,
                "stock_end",
                total_stock,
                "hundred_million_cny",
            ),
            ("stock_yoy_pct", "month", period_start, "stock_yoy", total_yoy, "percent"),
            (
                "ytd_increment_100m",
                "year_to_month",
                year_start,
                "ytd_increment",
                total_increment,
                "hundred_million_cny",
            ),
        )
    ]
    for component, (stock_label, increment_label) in _LIVE_SOCIAL_FINANCING_COMPONENTS.items():
        stock, yoy = _stock_level_and_yoy(compact, stock_label)
        increment = _signed_amount_after_label(compact, increment_label)
        for source_field, period_kind, start, measure, value, unit in (
            (
                "stock_end_trillion",
                "month",
                period_start,
                "stock_end",
                stock,
                "hundred_million_cny",
            ),
            ("stock_yoy_pct", "month", period_start, "stock_yoy", yoy, "percent"),
            (
                "ytd_increment_100m",
                "year_to_month",
                year_start,
                "ytd_increment",
                increment,
                "hundred_million_cny",
            ),
        ):
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
    release_at: datetime,
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
    release_at: datetime,
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
        ("enterprise", "total"): _signed_amount_after_label(
            enterprise, "企（事）业单位贷款"
        ),
        ("enterprise", "short_term"): _signed_amount_after_label(
            enterprise, "短期贷款"
        ),
        ("enterprise", "long_term"): _signed_amount_after_label(
            enterprise, "中长期贷款"
        ),
        ("enterprise", "bill_financing"): _signed_amount_after_label(
            enterprise, "票据融资"
        ),
        ("nonbank_financial", "total"): _signed_amount_after_label(
            nonbank, "非银行业金融机构贷款"
        ),
        ("all_rmb_loans", "total"): _signed_amount_after_label(
            compact, "前七个月人民币贷款"
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


def _parse_usdcny_central_parity(
    text: str,
    period: str,
    release_at: datetime,
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
    _validate_source_identity(family, response.final_url)
    if response.final_url != source_url:
        raise ValueError("official_context_source_redirect_identity_changed")
    if response.http_status != 200:
        raise ValueError("official_context_source_http_status_invalid")
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
        or (host == "www.stats.gov.cn" and not parsed.path.startswith("/sj/"))
        or (host == "www.pbc.gov.cn" and not parsed.path.startswith("/"))
    ):
        raise ValueError("official_context_source_url_not_official")
    return provider


def _release_timestamp(text: str) -> datetime:
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
    if len(matches) != 1:
        raise ValueError("official_context_release_timestamp_missing")
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
        return (
            re.search(rf"{year}年(?:1[—-])?0?{int(month)}月份?", text) is not None
            or re.search(rf"{year}年.*?0?{int(month)}月", text) is not None
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
        re.escape(label)
        + r"(?P<level>\d+(?:\.\d+)?)万亿元[，,]同比(?P<direction>增长|下降)"
        r"(?P<yoy>\d+(?:\.\d+)?)%",
        text,
    )
    if match is None:
        raise ValueError("official_context_social_financing_components_mismatch")
    yoy = _bounded_number(match.group("yoy"))
    if match.group("direction") == "下降":
        yoy = -yoy
    return round(_bounded_number(match.group("level"), minimum=0) * 10_000, 6), yoy


def _signed_amount_after_label(text: str, label: str) -> float:
    match = re.search(
        re.escape(label)
        + r"(?P<direction>增加|减少|净融资)?(?P<value>\d+(?:\.\d+)?)"
        r"(?P<unit>万亿元|亿元)",
        text,
    )
    if match is None:
        raise ValueError("official_context_numeric_value_invalid")
    value = _bounded_number(match.group("value"), minimum=0)
    if match.group("unit") == "万亿元":
        value = round(value * 10_000, 6)
    return -value if match.group("direction") == "减少" else value


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
    release_at: datetime,
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
