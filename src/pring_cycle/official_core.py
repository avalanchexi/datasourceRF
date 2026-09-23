"""The CSI official source for two of the three cores (ticket 22).

www.csindex.com.cn publishes each index's daily bars as JSON at one registered path. The
parser reads the close, change and percentage change of the requested index for each
trading day in the requested range; the page has no publication field, so publication is
the registered release time of the trading day (freshness registry). The Nanhua commodity
core has no stable official page to parse: its official site now serves quotes only
through a script application, so NHII is filled by TuShare alone.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, date, datetime
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import Request

from pring_cycle.acquisition import AcquisitionReceipt, AcquisitionRepository
from pring_cycle.adapters import MarketBar
from pring_cycle.catalog import metric_definition
from pring_cycle.evidence import EvidenceRepository, EvidenceValueState, SourceClaimInput
from pring_cycle.runtime import RuntimePaths

CSINDEX_HOST = "www.csindex.com.cn"
CSINDEX_PERF_PATH = "/csindex-home/perf/index-perf"
CSINDEX_PARSER_VERSION = "csindex-perf-parser-v0001"
CSINDEX_PROVIDER = "csindex"
CSINDEX_API = "index_perf"
# Core metric → CSI index code.
CSINDEX_CORES = {"CN_EQUITY_CORE_000985": "000985", "CN_BOND_CORE_000012": "000012"}
_MAX_BYTES = 2_000_000


def csindex_url(index_code: str, start: date, end: date) -> str:
    query = urlencode(
        {
            "indexCode": index_code,
            "startDate": start.strftime("%Y%m%d"),
            "endDate": end.strftime("%Y%m%d"),
        }
    )
    return f"https://{CSINDEX_HOST}{CSINDEX_PERF_PATH}?{query}"


def csindex_source_reference(metric_id: str, day: date) -> str:
    return f"{CSINDEX_PROVIDER}:{CSINDEX_API}:{CSINDEX_CORES[metric_id]}:{day.isoformat()}"


def is_csindex_page(metric_id: str, url: str) -> bool:
    """Whether a search candidate is a CSI page about this core's index."""
    parsed = urlsplit(url)
    return (
        metric_id in CSINDEX_CORES
        and parsed.scheme == "https"
        and parsed.hostname == CSINDEX_HOST
        and CSINDEX_CORES[metric_id] in url
    )


def parse_csindex_perf(
    raw: bytes, *, metric_id: str, start: date, end: date
) -> tuple[MarketBar, ...]:
    """The index's daily bars between ``start`` and ``end`` as the CSI page reports them."""
    code = CSINDEX_CORES[metric_id]
    if not raw or len(raw) > _MAX_BYTES:
        raise ValueError("csindex_response_size_invalid")
    try:
        document = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("csindex_response_invalid_json") from error
    if not isinstance(document, dict):
        raise ValueError("csindex_response_not_object")
    rows = document.get("data")
    if document.get("code") != "200" or not isinstance(rows, list):
        raise ValueError("csindex_response_not_success")
    bars: list[MarketBar] = []
    for row in rows:
        if not isinstance(row, dict) or row.get("indexCode") != code:
            raise ValueError("csindex_row_identity_mismatch")
        day = datetime.strptime(str(row.get("tradeDate")), "%Y%m%d").date()
        if not start <= day <= end:
            raise ValueError("csindex_period_mismatch")
        close, change, pct = (row.get(field) for field in ("close", "change", "changePct"))
        if not all(isinstance(value, int | float) for value in (close, change, pct)):
            raise ValueError("csindex_value_missing")
        assert isinstance(close, int | float) and isinstance(change, int | float)
        assert isinstance(pct, int | float)
        if close <= 0:
            raise ValueError("csindex_value_out_of_range")
        bars.append(
            MarketBar(
                metric_id=metric_id,
                source_code=code,
                business_date=day,
                close=float(close),
                pre_close=round(float(close) - float(change), 6),
                official_return=float(pct),
                unit="index_points",
                certification_status="not_applicable",
            )
        )
    if len({bar.business_date for bar in bars}) != len(bars):
        raise ValueError("csindex_duplicate_trade_date")
    return tuple(sorted(bars, key=lambda bar: bar.business_date))


def parse_csindex_acquisition(
    receipt: AcquisitionReceipt, raw: bytes, *, metric_id: str
) -> tuple[MarketBar, ...]:
    """Rebuild the bars a validated CSI call recorded, for rechecking a selected claim."""
    code = CSINDEX_CORES.get(metric_id)
    parameters = receipt.parameters
    if (
        code is None
        or receipt.state != "validated"
        or receipt.provider != CSINDEX_PROVIDER
        or receipt.api_name != CSINDEX_API
        or receipt.parser_version != CSINDEX_PARSER_VERSION
        or parameters.get("index_code") != code
    ):
        raise ValueError("core_acquisition_identity_mismatch")
    return parse_csindex_perf(
        raw,
        metric_id=metric_id,
        start=date.fromisoformat(parameters["start_date"]),
        end=date.fromisoformat(parameters["end_date"]),
    )


def _fetch(url: str) -> bytes:
    from pring_cycle.http_transport import open_no_redirects

    request = Request(url, headers={"Accept": "application/json", "User-Agent": "pring-cycle/1.0"})
    with open_no_redirects(request, timeout=15) as response:
        if int(response.status) != 200 or response.geturl() != url:
            raise OSError("csindex_response_status_or_redirect")
        return bytes(response.read(_MAX_BYTES + 1))


def refresh_csindex_core(
    paths: RuntimePaths,
    metric_id: str,
    *,
    start: date,
    end: date,
    definition_version: str,
    on_acquisition_started: Callable[[str], None] | None = None,
    admit: Callable[[tuple[MarketBar, ...]], None] | None = None,
) -> tuple[str, ...]:
    """Fetch the CSI page for ``start``..``end`` and store one claim per trading day."""
    url = csindex_url(CSINDEX_CORES[metric_id], start, end)

    def parse(raw: bytes) -> tuple[MarketBar, ...]:
        bars = parse_csindex_perf(raw, metric_id=metric_id, start=start, end=end)
        if admit is not None:
            admit(bars)
        return bars

    acquired = AcquisitionRepository(paths.database, paths.artifacts).capture(
        provider=CSINDEX_PROVIDER,
        api_name=CSINDEX_API,
        parameters={
            "index_code": CSINDEX_CORES[metric_id],
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "source_url": url,
        },
        fields="tradeDate,close,change,changePct",
        parser_version=CSINDEX_PARSER_VERSION,
        fetch=lambda: _fetch(url),
        parse=parse,
        normalize=lambda bars: [asdict(bar) for bar in bars],
        on_started=on_acquisition_started,
    )
    if not acquired.value:
        return ()
    receipt = acquired.receipt
    assert receipt.received_at is not None and receipt.validated_at is not None
    unit = metric_definition(
        metric_id, definition_version=definition_version, database_path=paths.database
    ).unit
    stored = EvidenceRepository(paths.database).append_source_claims(
        tuple(
            SourceClaimInput(
                metric_id=metric_id,
                definition_version=definition_version,
                period_kind="business_day",
                period_start=bar.business_date.isoformat(),
                period_end=bar.business_date.isoformat(),
                dimensions={},
                value=bar.close,
                value_state=EvidenceValueState.REPORTED_VALUE,
                unit=unit,
                provider=CSINDEX_PROVIDER,
                source_reference=csindex_source_reference(metric_id, bar.business_date),
                release_event_id=(
                    f"{CSINDEX_PROVIDER}:{receipt.acquisition_id}:{bar.business_date.isoformat()}"
                ),
                release_at=None,
                public_available_at=None,
                fetched_at=receipt.received_at.astimezone(UTC),
                available_at=receipt.validated_at.astimezone(UTC),
                quality_status="validated",
                acquisition_id=receipt.acquisition_id,
            )
            for bar in acquired.value
        )
    )
    return tuple(item.claim_id for item in stored)


def csindex_period_from_url(url: str) -> str | None:
    """The single trading day a CSI page URL names, if it names one."""
    values = parse_qs(urlsplit(url).query)
    start, end = values.get("startDate", [None])[0], values.get("endDate", [None])[0]
    return start if start is not None and start == end else None
