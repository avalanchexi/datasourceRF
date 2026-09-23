from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import date, datetime
from html.parser import HTMLParser
from urllib.parse import urlsplit
from urllib.request import Request
from zoneinfo import ZoneInfo

from pring_cycle.acquisition import Acquired, AcquisitionReceipt, AcquisitionRepository, utc_now
from pring_cycle.catalog import METRIC_CATALOG_VERSION
from pring_cycle.evidence import EvidenceRepository, MetricSeriesPoint, publication_times
from pring_cycle.http_transport import open_no_redirects as urlopen
from pring_cycle.official_context import (
    ParsedOfficialContextRelease,
    ingest_acquired_official_release,
)
from pring_cycle.release_calendar import month_bounds
from pring_cycle.runtime import RuntimePaths
from pring_cycle.tushare_context import ContextScalar

CHINAMONEY_PROVIDER = "中国货币网"
CHINAMONEY_METRIC_ID = "CN_LPR_1Y_5Y"
MAX_ANNOUNCEMENT_BYTES = 1_000_000
_OFFICIAL_HOST = "www.chinamoney.com.cn"
_OFFICIAL_PATH = re.compile(r"/chinese/rdgz/(?P<date>\d{8})/(?P<content>\d+)\.html")


@dataclass(frozen=True)
class LprObservation:
    tenor: str
    value: float


@dataclass(frozen=True)
class ParsedLprRelease:
    release_event_id: str
    period: str
    release_at: datetime | None
    public_available_at: datetime | None
    source_url: str
    observations: tuple[LprObservation, ...]


@dataclass(frozen=True)
class FetchedOfficialDocument:
    content: bytes
    media_type: str
    final_url: str
    http_status: int


@dataclass(frozen=True)
class LprIngestionResult:
    status: str
    release_event_id: str
    period: str
    artifact_hash: str
    observation_ids: tuple[str, ...]
    claim_ids: tuple[str, ...]
    observation_count: int


@dataclass(frozen=True)
class LprSmokeResult:
    status: str
    source_identity: str
    final_url: str
    period: str
    release_at: datetime | None
    observation_count: int
    tenors: tuple[str, ...]
    content_hash: str
    byte_count: int
    http_status: int
    network_requests: int


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.publication_parts: list[str] = []
        self._inside_time = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "time":
            self._inside_time = True
        if tag == "meta":
            values = dict(attrs)
            if (values.get("name") or "").lower() == "pubdate":
                self.publication_parts.append(values.get("content") or "")

    def handle_endtag(self, tag: str) -> None:
        if tag == "time":
            self._inside_time = False

    def handle_data(self, data: str) -> None:
        self.parts.append(data)
        if self._inside_time:
            self.publication_parts.append(data)


def parse_lpr_announcement(
    content: bytes,
    *,
    source_url: str,
    fetched_at: datetime,
    expected_period: str,
    parser_text_limit: int | None = None,
) -> ParsedLprRelease:
    url_date = _validate_official_url(source_url)
    if fetched_at.tzinfo is None:
        raise ValueError("lpr_fetched_at_must_be_timezone_aware")
    if not content or len(content) > MAX_ANNOUNCEMENT_BYTES:
        raise ValueError("lpr_announcement_size_invalid")
    try:
        document = content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("lpr_announcement_must_be_utf8") from error
    extractor = _TextExtractor()
    extractor.feed(document)
    text = re.sub(r"\s+", "", " ".join(extractor.parts))
    if parser_text_limit is not None and len(text) > parser_text_limit:
        raise ValueError("official_parser_fragment_too_large")
    if "全国银行间同业拆借中心受权公布贷款市场报价利率" not in text:
        raise ValueError("lpr_announcement_identity_missing")
    if "中国人民银行授权全国银行间同业拆借中心公布" not in text:
        raise ValueError("lpr_authorization_identity_missing")
    date_match = re.search(r"(?P<year>\d{4})年(?P<month>\d{1,2})月(?P<day>\d{1,2})日", text)
    if date_match is None:
        raise ValueError("lpr_release_date_missing")
    release_date = (
        f"{int(date_match.group('year')):04d}-"
        f"{int(date_match.group('month')):02d}-"
        f"{int(date_match.group('day')):02d}"
    )
    if release_date.replace("-", "") != url_date:
        raise ValueError("lpr_release_date_mismatch")
    if release_date[:7] != expected_period:
        raise ValueError("lpr_release_period_mismatch")
    published = _publication_metadata(extractor)
    source_timezone = ZoneInfo("Asia/Shanghai")
    release_at, public_at = publication_times(published, source_timezone)
    if release_at is not None:
        release_at = release_at.astimezone(source_timezone)
        public_at = release_at
    if release_at is not None and fetched_at < release_at:
        raise ValueError("lpr_fetched_before_public_release")
    if (
        published is not None
        and not isinstance(published, datetime)
        and fetched_at.astimezone(source_timezone).date() < published
    ):
        raise ValueError("lpr_fetched_before_public_release")
    one_year = _extract_rate(text, r"1年期LPR为(?P<value>\d+(?:\.\d+)?)%", "lpr_1y_value_missing")
    five_year = _extract_rate(
        text,
        r"5年期以上LPR为(?P<value>\d+(?:\.\d+)?)%",
        "lpr_5y_plus_value_missing",
    )
    return ParsedLprRelease(
        release_event_id=f"chinamoney-lpr:{release_date}:{hashlib.sha256(content).hexdigest()}",
        period=expected_period,
        release_at=release_at,
        public_available_at=public_at,
        source_url=source_url,
        observations=(LprObservation("1y", one_year), LprObservation("5y_plus", five_year)),
    )


def parse_lpr_acquisition(receipt: AcquisitionReceipt, raw: bytes) -> ParsedLprRelease:
    """Rebuild the release recorded by one validated LPR acquisition."""
    if (
        receipt.state != "validated"
        or receipt.provider != CHINAMONEY_PROVIDER
        or receipt.api_name not in {"document_import", "official_http_get"}
        or receipt.parser_version != "chinamoney-lpr-parser-v0002"
        or receipt.fields != "1y,5y_plus"
        or receipt.received_at is None
    ):
        raise ValueError("lpr_acquisition_identity_mismatch")
    parsed = parse_lpr_announcement(
        raw,
        source_url=receipt.parameters["source_url"],
        fetched_at=receipt.received_at,
        expected_period=receipt.parameters["period"],
    )
    normalized = json.dumps(
        asdict(parsed),
        default=str,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    if hashlib.sha256(normalized).hexdigest() != receipt.normalized_hash:
        raise ValueError("lpr_acquisition_normalized_mismatch")
    return parsed


def lpr_claims_matching_acquisitions(
    repository: EvidenceRepository, points: tuple[MetricSeriesPoint, ...]
) -> set[str]:
    """Match selected values to every linked release within one evaluation."""
    selected_points = {
        point.selected_claim_id: point for point in points if point.selected_claim_id is not None
    }
    checked: dict[str, ParsedLprRelease | None] = {}
    valid_claim_ids: set[str] = set()
    for claim_id, acquisitions in repository.source_claim_acquisitions_many(
        tuple(selected_points)
    ).items():
        valid = bool(acquisitions)
        point = selected_points[claim_id]
        claim = next((item for item in point.claims if item.claim_id == claim_id), None)
        for acquisition in acquisitions:
            acquisition_id = acquisition.receipt.acquisition_id
            if acquisition_id not in checked:
                try:
                    checked[acquisition_id] = parse_lpr_acquisition(
                        acquisition.receipt, acquisition.raw
                    )
                except (ValueError, TypeError, KeyError):
                    checked[acquisition_id] = None
            parsed = checked[acquisition_id]
            if (
                parsed is None
                or claim is None
                or claim.provider != CHINAMONEY_PROVIDER
                or claim.unit != "percent"
                or claim.source_reference
                != f"{parsed.source_url}#sha256={acquisition.receipt.raw_hash}"
                or (
                    (claim.release_at is not None or claim.parsed_public_available_at is not None)
                    and (claim.release_at, claim.parsed_public_available_at)
                    != (parsed.release_at, parsed.public_available_at)
                )
                or (point.period_start, point.period_end) != month_bounds(parsed.period)
                or not any(
                    point.dimensions == {"tenor": observation.tenor}
                    and point.selected_value == observation.value
                    for observation in parsed.observations
                )
            ):
                valid = False
                break
        if valid:
            valid_claim_ids.add(claim_id)
    return valid_claim_ids


def _publication_metadata(extractor: _TextExtractor) -> datetime | date | None:
    metadata = list(extractor.publication_parts)
    # Existing official pages have a standalone timestamp; a bare date is
    # accepted only from explicit publication metadata, never the title or URL.
    for part in extractor.parts:
        normalized = part.strip()
        if re.fullmatch(r"\d{4}[-/]\d{2}[-/]\d{2}\s+\d{2}:\d{2}(?::\d{2})?", normalized):
            metadata.append(normalized)
        metadata.extend(
            re.findall(
                r"(?:发布时间|发布日期)[：:]\s*(\d{4}[-/]\d{2}[-/]\d{2}(?:\s+\d{2}:\d{2}(?::\d{2})?)?)",
                part,
            )
        )
    values = {
        re.sub(r"\s+", " ", value.strip()).replace("/", "-") for value in metadata if value.strip()
    }
    timestamps = set()
    for value in values:
        if " " in value or "T" in value:
            timestamp = datetime.fromisoformat(value)
            timestamps.add(
                timestamp.replace(tzinfo=ZoneInfo("Asia/Shanghai"))
                if timestamp.tzinfo is None
                else timestamp.astimezone(ZoneInfo("Asia/Shanghai"))
            )
    dates = {date.fromisoformat(value) for value in values if " " not in value and "T" not in value}
    if (
        len(timestamps) > 1
        or len(dates) > 1
        or (timestamps and dates and {value.date() for value in timestamps} != dates)
    ):
        raise ValueError("lpr_publication_metadata_conflict")
    return next(iter(timestamps)) if timestamps else next(iter(dates)) if dates else None


def ingest_lpr_document(
    paths: RuntimePaths,
    content: bytes,
    *,
    source_url: str,
    fetched_at: datetime,
    expected_period: str,
    media_type: str = "text/html",
    definition_version: str = METRIC_CATALOG_VERSION,
    clock: Callable[[], datetime] = utc_now,
) -> LprIngestionResult:
    def parse(raw: bytes) -> ParsedLprRelease:
        if media_type.split(";", maxsplit=1)[0].strip().lower() != "text/html":
            raise ValueError("lpr_response_media_type_invalid")
        return parse_lpr_announcement(
            raw,
            source_url=source_url,
            fetched_at=fetched_at,
            expected_period=expected_period,
        )

    acquired = AcquisitionRepository(paths.database, paths.artifacts).capture(
        provider=CHINAMONEY_PROVIDER,
        api_name="document_import",
        parameters={"source_url": source_url, "period": expected_period},
        fields="1y,5y_plus",
        parser_version="chinamoney-lpr-parser-v0002",
        fetch=lambda: content,
        parse=parse,
        normalize=asdict,
        clock=clock,
    )
    return _ingest_lpr_acquisition(
        paths, acquired, definition_version=definition_version, clock=clock
    )


def _ingest_lpr_acquisition(
    paths: RuntimePaths,
    acquired: Acquired[ParsedLprRelease],
    *,
    definition_version: str,
    clock: Callable[[], datetime] = utc_now,
) -> LprIngestionResult:
    parsed = acquired.value
    period_start, period_end = month_bounds(parsed.period)
    release = ParsedOfficialContextRelease(
        family="chinamoney_lpr",
        provider=CHINAMONEY_PROVIDER,
        release_event_id=parsed.release_event_id,
        period=parsed.period,
        release_at=parsed.release_at,
        public_available_at=parsed.public_available_at,
        source_url=parsed.source_url,
        scalars=tuple(
            ContextScalar(
                metric_id=CHINAMONEY_METRIC_ID,
                api_name="chinamoney_lpr",
                source_field=observation.tenor,
                period_kind="month",
                period_start=period_start,
                period_end=period_end,
                dimensions={"tenor": observation.tenor},
                value=observation.value,
                unit="percent",
            )
            for observation in parsed.observations
        ),
    )
    result = ingest_acquired_official_release(
        paths,
        Acquired(release, acquired.receipt),
        definition_version=definition_version,
        clock=clock,
    )
    return LprIngestionResult(
        status="stored",
        release_event_id=result.release_event_id,
        period=result.period,
        artifact_hash=result.artifact_hash,
        observation_ids=result.observation_ids,
        claim_ids=result.claim_ids,
        observation_count=result.observation_count,
    )


def refresh_lpr_release(
    paths: RuntimePaths,
    *,
    source_url: str,
    expected_period: str,
    fetched_at: datetime,
    fetcher: Callable[[str], FetchedOfficialDocument] | None = None,
    definition_version: str = METRIC_CATALOG_VERSION,
    on_acquisition_started: Callable[[str], None] | None = None,
    parser_text_limit: int | None = None,
    admit: Callable[[ParsedLprRelease], None] | None = None,
) -> LprIngestionResult:
    """Fetch and store one announcement; ``admit`` may reject the parsed release first."""
    _validate_official_url(source_url)
    fetch = fetcher or fetch_official_document
    try:
        responses: list[FetchedOfficialDocument] = []

        def fetch_bytes() -> bytes:
            response = fetch(source_url)
            responses.append(response)
            return response.content

        def parse(raw: bytes) -> ParsedLprRelease:
            response = responses[0]
            _validate_official_url(response.final_url)
            if response.final_url != source_url:
                raise ValueError("lpr_source_redirect_identity_changed")
            if response.http_status != 200:
                raise ValueError("lpr_source_http_status_invalid")
            if response.media_type.split(";", maxsplit=1)[0].strip().lower() != "text/html":
                raise ValueError("lpr_response_media_type_invalid")
            parsed = parse_lpr_announcement(
                raw,
                source_url=source_url,
                fetched_at=utc_now(),
                expected_period=expected_period,
                parser_text_limit=parser_text_limit,
            )
            if admit is not None:
                admit(parsed)
            return parsed

        acquired = AcquisitionRepository(paths.database, paths.artifacts).capture(
            provider=CHINAMONEY_PROVIDER,
            api_name="official_http_get",
            parameters={"source_url": source_url, "period": expected_period},
            fields="1y,5y_plus",
            parser_version="chinamoney-lpr-parser-v0002",
            fetch=fetch_bytes,
            parse=parse,
            normalize=asdict,
            on_started=on_acquisition_started,
        )
        return _ingest_lpr_acquisition(paths, acquired, definition_version=definition_version)
    except (OSError, ValueError) as error:
        EvidenceRepository(paths.database).record_retrieval_attempt(
            metric_id=CHINAMONEY_METRIC_ID,
            channel="certified_official_direct",
            outcome="source_failed" if isinstance(error, OSError) else "validation_failed",
            fetched_at=fetched_at,
            safe_metadata={"period": expected_period, "provider": CHINAMONEY_PROVIDER},
        )
        raise


def fetch_official_document(source_url: str) -> FetchedOfficialDocument:
    _validate_official_url(source_url)
    request = Request(
        source_url,
        headers={"Accept": "text/html", "User-Agent": "pring-cycle/1.0 official-source-check"},
        method="GET",
    )
    with urlopen(request, timeout=15) as response:  # noqa: S310 - strict host allowlist above
        content = response.read(MAX_ANNOUNCEMENT_BYTES + 1)
        final_url = response.geturl()
        status = int(response.status)
        media_type = str(response.headers.get("Content-Type", ""))
    return FetchedOfficialDocument(content, media_type, final_url, status)


def _validate_official_url(source_url: str) -> str:
    parsed = urlsplit(source_url)
    path_match = _OFFICIAL_PATH.fullmatch(parsed.path)
    if (
        parsed.scheme != "https"
        or parsed.hostname != _OFFICIAL_HOST
        or parsed.port not in {None, 443}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or path_match is None
    ):
        raise ValueError("lpr_source_url_not_official")
    return path_match.group("date")


def _extract_rate(text: str, pattern: str, error_message: str) -> float:
    matches = re.findall(pattern, text)
    if len(matches) != 1:
        raise ValueError(error_message)
    value = float(matches[0])
    if not 0 < value < 100:
        raise ValueError("lpr_value_out_of_range")
    return value
