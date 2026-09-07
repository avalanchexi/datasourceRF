from __future__ import annotations

import hashlib
import json
import re
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from contextvars import copy_context
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.request import Request
from zoneinfo import ZoneInfo

from pring_cycle.acquisition import AcquisitionRepository
from pring_cycle.artifacts import store_artifact
from pring_cycle.http_transport import open_no_redirects as urlopen
from pring_cycle.official_context import (
    _fetch_official_context_document,
    ingest_official_context_document,
    parse_official_context_document,
)
from pring_cycle.official_lpr import ingest_lpr_document, parse_lpr_announcement
from pring_cycle.runtime import RuntimePaths


@dataclass(frozen=True)
class HistoricalSourceRecord:
    source_url: str
    period: str
    families: tuple[str, ...] = ()
    lpr: bool = False


@dataclass(frozen=True)
class _FetchedRecord:
    record: HistoricalSourceRecord
    content: bytes
    media_type: str
    final_url: str
    http_status: int


class _AnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.anchors: list[tuple[str, str]] = []
        self._href: str | None = None
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a" or self._href is not None:
            return
        values = {key.lower(): value for key, value in attrs}
        self._href = values.get("href") or values.get("tagname")
        self._parts = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href is not None:
            self.anchors.append((self._href, " ".join(self._parts)))
            self._href = None
            self._parts = []


def smoke_source_history(
    paths: RuntimePaths,
    *,
    target_business_date: str,
    browser_capture_root: Path | None = None,
) -> dict[str, object]:
    target = date.fromisoformat(target_business_date)
    records, discovery_requests = _historical_records(paths, target)
    browser_capture_records = sum(
        1
        for record in records
        if browser_capture_root is not None
        and record.families
        and record.families[0].startswith("nbs_")
    )
    documents: list[dict[str, object]] = []
    max_workers = 8
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        remaining = iter(records)
        pending = {
            executor.submit(
                copy_context().run,
                _smoke_record,
                paths,
                record,
                target=target,
                browser_capture_root=browser_capture_root,
            )
            for record in (next(remaining, None) for _ in range(max_workers))
            if record is not None
        }
        while pending:
            done, pending = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                documents.append(future.result())
                record = next(remaining, None)
                if record is not None:
                    pending.add(
                        executor.submit(
                            copy_context().run,
                            _smoke_record,
                            paths,
                            record,
                            target=target,
                            browser_capture_root=browser_capture_root,
                        )
                    )
    documents.sort(key=lambda item: (str(item["period"]), str(item["source_url"])))
    coverage = _validate_coverage(tuple(documents), target=target)
    digest = hashlib.sha256(
        "\x1f".join(f"{item['source_url']}:{item['artifact_hash']}" for item in documents).encode()
    ).hexdigest()
    return {
        "browser_capture_records": browser_capture_records,
        "coverage": coverage,
        "families": sorted(
            {
                family
                for document in documents
                for family in _string_list(
                    document["families"],
                    "source_history_smoke_families_invalid",
                )
            }
        ),
        "network_requests": discovery_requests + len(records) - browser_capture_records,
        "normalized_hash": digest,
        "record_count": len(documents),
        "records": documents,
        "status": "validated_candidate",
        "target_business_date": target_business_date,
    }


def _smoke_record(
    paths: RuntimePaths,
    record: HistoricalSourceRecord,
    *,
    target: date,
    browser_capture_root: Path | None,
) -> dict[str, object]:
    repository = AcquisitionRepository(paths.database, paths.artifacts)
    fetched: _FetchedRecord | None = None
    acquisition_id = ""
    capture_path = (
        browser_capture_root / f"{record.families[0]}--{record.period}.eval.txt"
        if browser_capture_root is not None
        and record.families
        and record.families[0].startswith("nbs_")
        else None
    )

    def started(value: str) -> None:
        nonlocal acquisition_id
        acquisition_id = value

    def fetch() -> bytes:
        nonlocal fetched
        if capture_path is not None:
            _validate_official_url(record.source_url)
            return capture_path.read_bytes()
        fetched = _fetch_record(record)
        return fetched.content

    def parse(content: bytes) -> dict[str, object]:
        received_at = repository.get(acquisition_id).received_at
        if received_at is None:
            raise ValueError("source_history_acquisition_identity_invalid")
        if capture_path is not None:
            document = _FetchedRecord(
                record,
                _decode_browser_capture(content),
                "text/html; charset=utf-8",
                record.source_url,
                200,
            )
        elif fetched is not None and fetched.content == content:
            document = fetched
        else:
            raise ValueError("source_history_acquisition_identity_invalid")
        return _smoke_document_from_fetched(paths, document, target=target, fetched_at=received_at)

    parameters = {
        "source_url": record.source_url,
        "period": record.period,
        "families": ",".join(record.families),
        "target_business_date": target.isoformat(),
        "transport": "browser_capture_import" if capture_path is not None else "http_get",
    }
    if capture_path is not None:
        parameters["capture_path"] = str(capture_path)
    else:
        parameters["response_read_limit_bytes"] = "4000001"
    acquired = repository.capture(
        provider="official_history",
        api_name="history_document",
        parameters=parameters,
        fields="official_history_document",
        parser_version="source-history-document-v0001",
        fetch=fetch,
        parse=parse,
        normalize=lambda document: document,
        on_started=started,
        max_error_body_bytes=4_000_001,
    )
    receipt = acquired.receipt
    return {
        **acquired.value,
        "acquisition_id": receipt.acquisition_id,
        "started_at": receipt.started_at.isoformat(),
        "received_at": receipt.received_at.isoformat() if receipt.received_at else None,
        "validated_at": receipt.validated_at.isoformat() if receipt.validated_at else None,
    }


def _smoke_document_from_fetched(
    paths: RuntimePaths,
    item: _FetchedRecord,
    *,
    target: date,
    fetched_at: datetime,
) -> dict[str, object]:
    if item.final_url != item.record.source_url or item.http_status != 200:
        raise ValueError("source_history_fetch_identity_invalid")
    artifact = store_artifact(
        paths.database,
        paths.artifacts,
        item.content,
        "text/html",
        item.record.source_url,
    )
    release_at: datetime | None
    public_at: datetime | None
    if item.record.lpr:
        parsed = parse_lpr_announcement(
            item.content,
            source_url=item.record.source_url,
            expected_period=item.record.period,
            fetched_at=fetched_at,
        )
        metric_ids: tuple[str, ...] = ("CN_LPR_1Y_5Y",)
        release_at = parsed.release_at
        public_at = parsed.public_available_at
    else:
        parsed_families = tuple(
            parse_official_context_document(
                item.content,
                family=family,
                source_url=item.record.source_url,
                expected_period=item.record.period,
                fetched_at=fetched_at,
            )
            for family in item.record.families
        )
        metric_ids = tuple(
            sorted(
                {
                    scalar.metric_id
                    for parsed_family in parsed_families
                    for scalar in parsed_family.scalars
                }
            )
        )
        release_times = {parsed_family.release_at for parsed_family in parsed_families}
        if len(release_times) != 1:
            raise ValueError("source_history_release_identity_mismatch")
        release_at = next(iter(release_times))
        public_times = {parsed_family.public_available_at for parsed_family in parsed_families}
        if len(public_times) != 1:
            raise ValueError("source_history_release_identity_mismatch")
        public_at = next(iter(public_times))
    if public_at is None:
        raise ValueError("source_history_publication_time_unknown")
    if public_at.astimezone(ZoneInfo("Asia/Shanghai")).date() > target:
        raise ValueError("source_history_release_after_target")
    return {
        "artifact_hash": artifact.content_hash,
        "families": list(item.record.families),
        "lpr": item.record.lpr,
        "metric_ids": list(metric_ids),
        "period": item.record.period,
        "release_at": release_at.isoformat() if release_at is not None else None,
        "public_available_at": public_at.isoformat(),
        "source_url": item.record.source_url,
    }


def refresh_source_history(
    paths: RuntimePaths,
    *,
    smoke_document: dict[str, object],
    definition_version: str,
) -> dict[str, object]:
    records = smoke_document.get("records")
    if not isinstance(records, list) or not records:
        raise ValueError("source_history_smoke_records_missing")
    results: list[dict[str, object]] = []
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("source_history_smoke_record_invalid")
        content_hash = str(record.get("artifact_hash", ""))
        artifact_path = paths.artifacts / content_hash[:2] / content_hash
        content = artifact_path.read_bytes()
        if hashlib.sha256(content).hexdigest() != content_hash:
            raise ValueError("source_history_artifact_hash_mismatch")
        source_url = str(record.get("source_url", ""))
        period = str(record.get("period", ""))
        fetched_at = datetime.now(UTC)
        if record.get("lpr") is True:
            results.append(
                asdict(
                    ingest_lpr_document(
                        paths,
                        content,
                        source_url=source_url,
                        expected_period=period,
                        fetched_at=fetched_at,
                        definition_version=definition_version,
                    )
                )
            )
            continue
        families = record.get("families")
        if not isinstance(families, list) or not all(
            isinstance(family, str) for family in families
        ):
            raise ValueError("source_history_smoke_families_invalid")
        for family in families:
            results.append(
                asdict(
                    ingest_official_context_document(
                        paths,
                        content,
                        family=family,
                        source_url=source_url,
                        expected_period=period,
                        fetched_at=fetched_at,
                        definition_version=definition_version,
                    )
                )
            )
    return {
        "ingestion_count": len(results),
        "observation_count": sum(
            _integer(item["observation_count"], "source_history_observation_count_invalid")
            for item in results
        ),
        "results": results,
        "status": "source_history_refreshed",
    }


def _historical_records(
    paths: RuntimePaths, target: date
) -> tuple[tuple[HistoricalSourceRecord, ...], int]:
    records = [
        *_nbs_records(),
        *_tool_liquidity_records(),
        *_lpr_records(),
        *_pbc_migrated_january_2025_records(),
    ]
    financial, financial_requests = _discover_pbc_financial_reports(paths, target)
    omo, omo_requests = _discover_omo_notices(paths, target)
    records.extend(financial)
    records.extend(omo)
    unique = {
        (record.source_url, record.period, record.families, record.lpr): record
        for record in records
    }
    return tuple(sorted(unique.values(), key=lambda item: (item.period, item.source_url))), (
        financial_requests + omo_requests
    )


def _fetch_record(record: HistoricalSourceRecord) -> _FetchedRecord:
    _validate_official_url(record.source_url)
    if record.lpr:
        request = Request(
            record.source_url,
            headers={"Accept": "text/html", "User-Agent": "pring-cycle/1.0 history-check"},
            method="GET",
        )
        with urlopen(request, timeout=20) as response:  # noqa: S310 - fixed official URL
            content = response.read(4_000_001)
            return _FetchedRecord(
                record,
                content,
                str(response.headers.get("Content-Type", "")),
                response.geturl(),
                int(response.status),
            )
    response = _fetch_official_context_document(record.source_url)
    return _FetchedRecord(
        record,
        response.content,
        response.media_type,
        response.final_url,
        response.http_status,
    )


def _discover_pbc_financial_reports(
    paths: RuntimePaths,
    target: date,
) -> tuple[tuple[HistoricalSourceRecord, ...], int]:
    base = "https://www.pbc.gov.cn"
    records: dict[str, HistoricalSourceRecord] = {}
    requests = 0
    for page in range(1, 6):
        url = base + "/diaochatongjisi/116219/116225/" + f"11871-{page}.html"
        anchors = _fetch_anchors(paths, url, expected_host="www.pbc.gov.cn", target=target)
        requests += 1
        for href, title in anchors:
            report = _financial_report_identity(title)
            if report is None:
                continue
            period, report_kind = report
            if not "2024-01" <= period <= target.strftime("%Y-%m"):
                continue
            if report_kind == "social_financing":
                families: tuple[str, ...] = ("pbc_social_financing",)
            else:
                families = ("pbc_loan_structure",)
                if period >= "2025-09":
                    families = (
                        "pbc_social_financing",
                        *families,
                    )
                if period >= "2026-01":
                    families = (*families, "pbc_money")
            source_url = _validated_discovered_url(base, href, expected_host="www.pbc.gov.cn")
            records[source_url] = HistoricalSourceRecord(source_url, period, families)
    return tuple(records.values()), requests


def _pbc_migrated_january_2025_records() -> tuple[HistoricalSourceRecord, ...]:
    base = "https://www.pbc.gov.cn/goutongjiaoliu/113456/113469/"
    return (
        HistoricalSourceRecord(
            base + "2025092212554572702/index.html",
            "2025-01",
            ("pbc_loan_structure",),
        ),
        HistoricalSourceRecord(
            base + "2025092212554511660/index.html",
            "2025-01",
            ("pbc_social_financing",),
        ),
        HistoricalSourceRecord(
            base + "2025092212554594361/index.html",
            "2025-01",
            ("pbc_social_financing",),
        ),
    )


def _discover_omo_notices(
    paths: RuntimePaths,
    target: date,
) -> tuple[tuple[HistoricalSourceRecord, ...], int]:
    base = "https://www.pbc.gov.cn"
    start = date(2026, 2, 20)
    records: dict[str, HistoricalSourceRecord] = {}
    requests = 0
    for page in range(1, 10):
        url = base + "/zhengcehuobisi/125207/125213/125431/125475/" + f"17081-{page}.html"
        anchors = _fetch_anchors(paths, url, expected_host="www.pbc.gov.cn", target=target)
        requests += 1
        for href, title in anchors:
            if "公开市场业务交易公告" not in title:
                continue
            match = re.search(r"/(20\d{12})\d*/index\.html", href)
            if match is None:
                continue
            period = datetime.strptime(match.group(1)[:8], "%Y%m%d").date()
            if not start <= period <= target:
                continue
            source_url = _validated_discovered_url(base, href, expected_host="www.pbc.gov.cn")
            candidate = HistoricalSourceRecord(
                source_url,
                period.isoformat(),
                ("pbc_omo_notice",),
            )
            key = period.isoformat()
            previous = records.get(key)
            if previous is None or candidate.source_url < previous.source_url:
                records[key] = candidate
    return tuple(records.values()), requests


def _decode_browser_capture(raw: bytes) -> bytes:
    document = raw.decode("utf-8-sig").replace("\r\n", "\n")
    prefix = "### Result\n"
    suffix = "\n### Ran Playwright code"
    if not document.startswith(prefix) or suffix not in document:
        raise ValueError("source_history_browser_capture_invalid")
    serialized = document.removeprefix(prefix).split(suffix, 1)[0].strip()
    content = json.loads(serialized)
    if not isinstance(content, str) or "<html" not in content.lower():
        raise ValueError("source_history_browser_capture_invalid")
    return content.encode()


def _fetch_anchors(
    paths: RuntimePaths, url: str, *, expected_host: str, target: date
) -> tuple[tuple[str, str], ...]:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != expected_host:
        raise ValueError("source_history_listing_url_invalid")
    request = Request(
        url,
        headers={"Accept": "text/html", "User-Agent": "pring-cycle/1.0 history-index"},
        method="GET",
    )
    final_url = ""
    http_status = 0

    def fetch() -> bytes:
        nonlocal final_url, http_status
        with urlopen(request, timeout=20) as response:  # noqa: S310 - validated official URL
            content = response.read(1_000_001)
            final_url, http_status = response.geturl(), int(response.status)
        if not isinstance(content, bytes):
            raise ValueError("source_history_listing_response_bytes_required")
        return content

    def parse(content: bytes) -> tuple[tuple[str, str], ...]:
        if final_url != url or http_status != 200:
            raise ValueError("source_history_listing_fetch_invalid")
        if not content or len(content) > 1_000_000:
            raise ValueError("source_history_listing_size_invalid")
        parser = _AnchorParser()
        parser.feed(content.decode("utf-8", errors="replace"))
        return tuple((href, re.sub(r"\s+", "", title)) for href, title in parser.anchors)

    return (
        AcquisitionRepository(paths.database, paths.artifacts)
        .capture(
            provider="official_history",
            api_name="history_listing",
            parameters={
                "source_url": url,
                "transport": "http_get",
                "target_business_date": target.isoformat(),
                "response_read_limit_bytes": "1000001",
            },
            fields="href,title",
            parser_version="source-history-listing-v0001",
            fetch=fetch,
            parse=parse,
            normalize=lambda anchors: anchors,
            max_error_body_bytes=1_000_001,
        )
        .value
    )


def _validated_discovered_url(base: str, href: str, *, expected_host: str) -> str:
    source_url = urljoin(base, href)
    parsed = urlsplit(source_url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != expected_host
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port is not None
    ):
        raise ValueError("source_history_discovered_url_invalid")
    return source_url


def _validate_official_url(source_url: str) -> None:
    parsed = urlsplit(source_url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in {"www.pbc.gov.cn", "www.stats.gov.cn", "www.chinamoney.com.cn"}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port is not None
    ):
        raise ValueError("source_history_record_url_invalid")


def _financial_report_identity(title: str) -> tuple[str, str] | None:
    match = re.fullmatch(
        r"(?P<year>202[456])年(?P<label>.*?)(?P<kind>"
        r"金融统计数据报告|社会融资规模(?:存量|增量)统计数据报告)",
        title,
    )
    if match is None or "地区" in title:
        return None
    year = match.group("year")
    label = match.group("label")
    labels = {"": 12, "一季度": 3, "上半年": 6, "前三季度": 9}
    if label in labels:
        month = labels[label]
    else:
        month_match = re.fullmatch(r"(?P<month>\d{1,2})月", label)
        if month_match is None:
            return None
        month = int(month_match.group("month"))
    report_kind = (
        "social_financing" if match.group("kind").startswith("社会融资规模") else "financial"
    )
    return f"{year}-{month:02d}", report_kind


def _validate_coverage(
    records: tuple[dict[str, object], ...],
    *,
    target: date,
) -> dict[str, object]:
    periods: dict[str, set[str]] = {}
    for record in records:
        period = str(record["period"])
        if record.get("lpr") is True:
            periods.setdefault("lpr", set()).add(period)
        for family in _string_list(
            record["families"],
            "source_history_coverage_families_invalid",
        ):
            periods.setdefault(str(family), set()).add(period)
    required = {
        "nbs_pmi": ("2026-01", "2026-07", 7),
        "nbs_core_cpi": ("2025-12", "2026-07", 8),
        "nbs_ppi": ("2025-12", "2026-07", 8),
        "nbs_gdp": ("2023-Q4", "2026-Q2", 11),
        "nbs_industrial_value_added": ("2025-12", "2026-07", 7),
        "nbs_industrial_finance": ("2025-12", "2026-07", 7),
        "nbs_capacity_utilization": ("2025-Q4", "2026-Q2", 3),
        "pbc_social_financing": ("2024-01", "2026-07", 31),
        "pbc_loan_structure": ("2024-01", "2026-07", 31),
        "pbc_money": ("2026-01", "2026-07", 7),
        "pbc_tool_liquidity_monthly": ("2025-12", "2026-07", 8),
        "lpr": ("2025-12", "2026-08", 9),
    }
    summary: dict[str, object] = {}
    for family, (first, last, minimum_count) in required.items():
        observed = sorted(periods.get(family, set()))
        if (
            len(observed) < minimum_count
            or not observed
            or observed[0] > first
            or observed[-1] < last
        ):
            raise ValueError(f"source_history_coverage_incomplete:{family}")
        summary[family] = {
            "first_period": observed[0],
            "last_period": observed[-1],
            "period_count": len(observed),
        }
    omo = sorted(periods.get("pbc_omo_notice", set()))
    if not omo or omo[0] > "2026-02-27" or omo[-1] < target.isoformat():
        raise ValueError("source_history_coverage_incomplete:pbc_omo_notice")
    omo_dates = [date.fromisoformat(value) for value in omo]
    if any((right - left).days > 10 for left, right in zip(omo_dates, omo_dates[1:], strict=False)):
        raise ValueError("source_history_coverage_gap:pbc_omo_notice")
    summary["pbc_omo_notice"] = {
        "first_period": omo[0],
        "last_period": omo[-1],
        "period_count": len(omo),
    }
    return summary


def _nbs_records() -> tuple[HistoricalSourceRecord, ...]:
    base = "https://www.stats.gov.cn/sj/zxfb/"
    rows = (
        ("nbs_pmi", "2026-01", "202601/t20260131_1962416.html"),
        ("nbs_pmi", "2026-02", "202603/t20260304_1962699.html"),
        ("nbs_pmi", "2026-03", "202603/t20260331_1962889.html"),
        ("nbs_pmi", "2026-04", "202604/t20260430_1963473.html"),
        ("nbs_pmi", "2026-05", "202605/t20260531_1963824.html"),
        ("nbs_pmi", "2026-06", "202606/t20260630_1964032.html"),
        ("nbs_pmi", "2026-07", "202607/t20260731_1964253.html"),
        ("nbs_core_cpi", "2025-12", "202601/t20260109_1962273.html"),
        ("nbs_core_cpi", "2026-01", "202602/t20260211_1962588.html"),
        ("nbs_core_cpi", "2026-02", "202603/t20260309_1962732.html"),
        ("nbs_core_cpi", "2026-03", "202604/t20260410_1963264.html"),
        ("nbs_core_cpi", "2026-04", "202605/t20260511_1963659.html"),
        ("nbs_core_cpi", "2026-05", "202606/t20260610_1963923.html"),
        ("nbs_core_cpi", "2026-06", "202607/t20260709_1964084.html"),
        ("nbs_core_cpi", "2026-07", "202608/t20260809_1965008.html"),
        ("nbs_ppi", "2025-12", "202601/t20260109_1962272.html"),
        ("nbs_ppi", "2026-01", "202602/t20260211_1962587.html"),
        ("nbs_ppi", "2026-02", "202603/t20260309_1962729.html"),
        ("nbs_ppi", "2026-03", "202604/t20260410_1963263.html"),
        ("nbs_ppi", "2026-04", "202605/t20260511_1963658.html"),
        ("nbs_ppi", "2026-05", "202606/t20260610_1963922.html"),
        ("nbs_ppi", "2026-06", "202607/t20260709_1964083.html"),
        ("nbs_ppi", "2026-07", "202608/t20260809_1965007.html"),
        ("nbs_gdp", "2023-Q4", "202401/t20240118_1946691.html"),
        ("nbs_gdp", "2024-Q1", "202404/t20240429_1948771.html"),
        ("nbs_gdp", "2024-Q2", "202407/t20240716_1955649.html"),
        ("nbs_gdp", "2024-Q3", "202410/t20241019_1957083.html"),
        ("nbs_gdp", "2024-Q4", "202501/t20250118_1958363.html"),
        ("nbs_gdp", "2025-Q1", "202504/t20250417_1959334.html"),
        ("nbs_gdp", "2025-Q2", "202507/t20250716_1960426.html"),
        ("nbs_gdp", "2025-Q3", "202510/t20251021_1961646.html"),
        ("nbs_gdp", "2025-Q4", "202601/t20260120_1962349.html"),
        ("nbs_gdp", "2026-Q1", "202604/t20260417_1963336.html"),
        ("nbs_gdp", "2026-Q2", "202607/t20260716_1964142.html"),
        ("nbs_industrial_value_added", "2025-12", "202601/t20260119_1962329.html"),
        ("nbs_industrial_value_added", "2026-02", "202603/t20260316_1962782.html"),
        ("nbs_industrial_value_added", "2026-03", "202604/t20260416_1963329.html"),
        ("nbs_industrial_value_added", "2026-04", "202605/t20260518_1963731.html"),
        ("nbs_industrial_value_added", "2026-05", "202606/t20260616_1963953.html"),
        ("nbs_industrial_value_added", "2026-06", "202607/t20260715_1964123.html"),
        ("nbs_industrial_value_added", "2026-07", "202608/t20260817_1965055.html"),
        ("nbs_industrial_finance", "2025-12", "202601/t20260127_1962382.html"),
        ("nbs_industrial_finance", "2026-02", "202603/t20260327_1962868.html"),
        ("nbs_industrial_finance", "2026-03", "202604/t20260427_1963403.html"),
        ("nbs_industrial_finance", "2026-04", "202605/t20260527_1963808.html"),
        ("nbs_industrial_finance", "2026-05", "202606/t20260627_1964019.html"),
        ("nbs_industrial_finance", "2026-06", "202607/t20260727_1964194.html"),
        ("nbs_industrial_finance", "2026-07", "202608/t20260827_1965126.html"),
        ("nbs_capacity_utilization", "2025-Q4", "202601/t20260119_1962320.html"),
        ("nbs_capacity_utilization", "2026-Q1", "202604/t20260416_1963322.html"),
        ("nbs_capacity_utilization", "2026-Q2", "202607/t20260715_1964130.html"),
    )
    return tuple(
        HistoricalSourceRecord(base + path, period, (family,)) for family, period, path in rows
    )


def _tool_liquidity_records() -> tuple[HistoricalSourceRecord, ...]:
    base = "https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/5727710/"
    rows = (
        ("2025-12", "2026010517563068096/index.html"),
        ("2026-01", "2026020318084859404/index.html"),
        ("2026-02", "2026030316592793608/index.html"),
        ("2026-03", "2026040217142755538/index.html"),
        ("2026-04", "2026050716471136206/index.html"),
        ("2026-05", "2026060216561236851/index.html"),
        ("2026-06", "2026070216555861498/index.html"),
        ("2026-07", "2026080416515912098/index.html"),
    )
    return tuple(
        HistoricalSourceRecord(
            base + path,
            period,
            ("pbc_tool_liquidity_monthly",),
        )
        for period, path in rows
    )


def _lpr_records() -> tuple[HistoricalSourceRecord, ...]:
    base = "https://www.chinamoney.com.cn/chinese/rdgz/"
    rows = (
        ("2025-12", "20251222/3256124.html"),
        ("2026-01", "20260120/3271248.html"),
        ("2026-02", "20260224/3285699.html"),
        ("2026-03", "20260320/3301473.html"),
        ("2026-04", "20260420/3318431.html"),
        ("2026-05", "20260520/3343089.html"),
        ("2026-06", "20260622/3361525.html"),
        ("2026-07", "20260720/3379021.html"),
        ("2026-08", "20260820/3399885.html"),
    )
    return tuple(HistoricalSourceRecord(base + path, period, lpr=True) for period, path in rows)


def _string_list(value: object, error: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(error)
    return value


def _integer(value: object, error: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(error)
    return value
