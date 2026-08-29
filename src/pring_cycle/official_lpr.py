from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from pring_cycle.artifacts import store_artifact
from pring_cycle.catalog import METRIC_CATALOG_VERSION
from pring_cycle.evidence import (
    EvidenceRepository,
    EvidenceValueState,
    SourceClaimInput,
    StoredSourceClaim,
)
from pring_cycle.release_calendar import month_bounds
from pring_cycle.runtime import RuntimePaths

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
    release_at: datetime
    public_available_at: datetime
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
    release_at: datetime
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

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def parse_lpr_announcement(
    content: bytes,
    *,
    source_url: str,
    fetched_at: datetime,
    expected_period: str,
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
    timestamp_match = re.search(
        r"(?P<date>\d{4}-\d{2}-\d{2})(?P<hour>\d{2}):(?P<minute>\d{2})",
        text,
    )
    if timestamp_match is None:
        raise ValueError("lpr_release_timestamp_missing")
    if timestamp_match.group("date") != release_date:
        raise ValueError("lpr_release_date_mismatch")
    release_at = datetime.fromisoformat(
        f"{release_date}T{timestamp_match.group('hour')}:{timestamp_match.group('minute')}:00"
    ).replace(tzinfo=ZoneInfo("Asia/Shanghai"))
    if (release_at.hour, release_at.minute) != (9, 0):
        raise ValueError("lpr_release_time_mismatch")
    if fetched_at < release_at:
        raise ValueError("lpr_fetched_before_public_release")
    one_year = _extract_rate(text, r"1年期LPR为(?P<value>\d+(?:\.\d+)?)%", "lpr_1y_value_missing")
    five_year = _extract_rate(
        text,
        r"5年期以上LPR为(?P<value>\d+(?:\.\d+)?)%",
        "lpr_5y_plus_value_missing",
    )
    return ParsedLprRelease(
        release_event_id=f"chinamoney-lpr:{release_date}",
        period=expected_period,
        release_at=release_at,
        public_available_at=release_at,
        source_url=source_url,
        observations=(LprObservation("1y", one_year), LprObservation("5y_plus", five_year)),
    )


def ingest_lpr_document(
    paths: RuntimePaths,
    content: bytes,
    *,
    source_url: str,
    fetched_at: datetime,
    expected_period: str,
    media_type: str = "text/html",
    definition_version: str = METRIC_CATALOG_VERSION,
) -> LprIngestionResult:
    parsed = parse_lpr_announcement(
        content,
        source_url=source_url,
        fetched_at=fetched_at,
        expected_period=expected_period,
    )
    if media_type.split(";", maxsplit=1)[0].strip().lower() != "text/html":
        raise ValueError("lpr_response_media_type_invalid")
    artifact = store_artifact(
        paths.database,
        paths.artifacts,
        content,
        "text/html",
        source_url,
    )
    period_start, period_end = month_bounds(parsed.period)
    source_reference = f"{source_url}#sha256={artifact.content_hash}"
    repository = EvidenceRepository(paths.database)
    existing = repository.claims_for_release_source(
        parsed.release_event_id,
        source_reference,
        definition_version=definition_version,
    )
    if existing and len(existing) != len(parsed.observations):
        raise ValueError("lpr_release_claim_set_incomplete")
    release_event_id = parsed.release_event_id
    if existing:
        stored = existing
    else:
        exact_previous = tuple(
            repository.latest_provider_claim(
                metric_id=CHINAMONEY_METRIC_ID,
                definition_version=definition_version,
                period_kind="month",
                period_start=period_start,
                period_end=period_end,
                dimensions={"tenor": observation.tenor},
                provider=CHINAMONEY_PROVIDER,
            )
            for observation in parsed.observations
        )
        physical_previous = tuple(
            repository.latest_provider_claim(
                metric_id=CHINAMONEY_METRIC_ID,
                period_kind="month",
                period_start=period_start,
                period_end=period_end,
                dimensions={"tenor": observation.tenor},
                provider=CHINAMONEY_PROVIDER,
            )
            for observation in parsed.observations
        )
        exact_same = all(
            previous is not None
            and previous.value_state is EvidenceValueState.REPORTED_VALUE
            and previous.value == observation.value
            and previous.unit == "percent"
            for previous, observation in zip(
                exact_previous,
                parsed.observations,
                strict=True,
            )
        )
        cross_version_same = all(previous is None for previous in exact_previous) and all(
            previous is not None
            and previous.value_state is EvidenceValueState.REPORTED_VALUE
            and previous.value == observation.value
            and previous.unit == "percent"
            for previous, observation in zip(
                physical_previous,
                parsed.observations,
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
                    metric_id=CHINAMONEY_METRIC_ID,
                    definition_version=definition_version,
                    period_kind="month",
                    period_start=period_start,
                    period_end=period_end,
                    dimensions={"tenor": observation.tenor},
                    value=observation.value,
                    value_state=EvidenceValueState.REPORTED_VALUE,
                    unit="percent",
                    provider=CHINAMONEY_PROVIDER,
                    source_reference=source_reference,
                    release_event_id=release_event_id,
                    release_at=release_at,
                    public_available_at=public_available_at,
                    fetched_at=fetched_at,
                    available_at=fetched_at,
                    certification_status="certified",
                    quality_status="validated",
                )
                for observation in parsed.observations
            )
            stored = repository.append_source_claims(claims)
    repository.record_retrieval_attempt(
        metric_id=CHINAMONEY_METRIC_ID,
        channel="certified_official_direct",
        outcome="verified",
        fetched_at=fetched_at,
        safe_metadata={
            "artifact_hash": artifact.content_hash,
            "http_status": "200",
            "period": parsed.period,
            "provider": CHINAMONEY_PROVIDER,
        },
    )
    return LprIngestionResult(
        status="stored",
        release_event_id=release_event_id,
        period=parsed.period,
        artifact_hash=artifact.content_hash,
        observation_ids=tuple(item.observation_id for item in stored),
        claim_ids=tuple(item.claim_id for item in stored),
        observation_count=len(stored),
    )


def _revision_event_id(base_event_id: str, fetched_at: datetime) -> str:
    suffix = hashlib.sha256(fetched_at.isoformat().encode()).hexdigest()[:16]
    return f"{base_event_id}:revision:{suffix}"


def refresh_lpr_release(
    paths: RuntimePaths,
    *,
    source_url: str,
    expected_period: str,
    fetched_at: datetime,
    fetcher: Callable[[str], FetchedOfficialDocument] | None = None,
    definition_version: str = METRIC_CATALOG_VERSION,
) -> LprIngestionResult:
    _validate_official_url(source_url)
    fetch = fetcher or fetch_official_document
    try:
        response = fetch(source_url)
        _validate_official_url(response.final_url)
        if response.final_url != source_url:
            raise ValueError("lpr_source_redirect_identity_changed")
        if response.http_status != 200:
            raise ValueError("lpr_source_http_status_invalid")
        return ingest_lpr_document(
            paths,
            response.content,
            source_url=response.final_url,
            fetched_at=fetched_at,
            expected_period=expected_period,
            media_type=response.media_type,
            definition_version=definition_version,
        )
    except (OSError, ValueError):
        EvidenceRepository(paths.database).record_retrieval_attempt(
            metric_id=CHINAMONEY_METRIC_ID,
            channel="certified_official_direct",
            outcome="source_failed",
            fetched_at=fetched_at,
            safe_metadata={"period": expected_period, "provider": CHINAMONEY_PROVIDER},
        )
        raise


def smoke_lpr_release(
    *,
    source_url: str,
    expected_period: str,
    fetched_at: datetime,
    fetcher: Callable[[str], FetchedOfficialDocument] | None = None,
) -> LprSmokeResult:
    _validate_official_url(source_url)
    response = (fetcher or fetch_official_document)(source_url)
    _validate_official_url(response.final_url)
    if response.final_url != source_url:
        raise ValueError("lpr_source_redirect_identity_changed")
    if response.http_status != 200:
        raise ValueError("lpr_source_http_status_invalid")
    if response.media_type.split(";", maxsplit=1)[0].strip().lower() != "text/html":
        raise ValueError("lpr_response_media_type_invalid")
    parsed = parse_lpr_announcement(
        response.content,
        source_url=response.final_url,
        fetched_at=fetched_at,
        expected_period=expected_period,
    )
    return LprSmokeResult(
        status="validated",
        source_identity="CHINAMONEY_LPR",
        final_url=response.final_url,
        period=parsed.period,
        release_at=parsed.release_at,
        observation_count=len(parsed.observations),
        tenors=tuple(item.tenor for item in parsed.observations),
        content_hash=hashlib.sha256(response.content).hexdigest(),
        byte_count=len(response.content),
        http_status=response.http_status,
        network_requests=1,
    )


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
    if len(content) > MAX_ANNOUNCEMENT_BYTES:
        raise ValueError("lpr_announcement_size_invalid")
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
