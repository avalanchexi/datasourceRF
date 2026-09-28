"""CZCE's own daily warrant report for TA and CF (ADR-0032).

TuShare's ``fut_wsr`` rows for PTA came back malformed in a different way each day, and its
cotton totals miss lots. Zhengzhou publishes one plain-text file a trading day with every
symbol's warehouses and their subtotals; a member of ``CN_FUTURES_WARRANTS`` is a subtotal
("小计") of that file. It is a registered source: fetched in the Worker's acquisition stage,
never searched, and TuShare no longer delivers or backs up these two symbols.

The day's file is requested once. Each symbol gets its own receipt of it, so a symbol whose
block is missing or has changed shape is refused on its own, and so is only that day.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
from datetime import date, datetime
from http.client import HTTPException
from urllib.error import HTTPError
from urllib.request import Request

from pring_cycle.acquisition import AcquisitionReceipt, AcquisitionRepository, utc_now
from pring_cycle.catalog import MetricDefinition, metric_definition
from pring_cycle.evidence import AsOfMode, EvidenceRepository, EvidenceValueState, SourceClaimInput
from pring_cycle.http_transport import open_no_redirects
from pring_cycle.metric_contracts import (
    CZCE_PROVIDER,
    CZCE_WARRANT_SYMBOLS,
    czce_source_reference,
    czce_warrant_url,
)
from pring_cycle.runtime import RuntimePaths
from pring_cycle.storage import database_connection
from pring_cycle.tushare_context import ContextScalar, WarrantAcquisition

METRIC_ID = "CN_FUTURES_WARRANTS"
CHANNEL = "czce_official"
PARSER_VERSION = "czce-warehouse-receipts-parser-v0001"
API_NAME = "czce_warehouse_receipts"
# Serial, with about a second between two requests (user decision 2026-09-26).
REQUEST_INTERVAL_SECONDS = 1.0
WINDOW_TRADING_DAYS = 120
_MAX_BYTES = 2_000_000


@dataclass(frozen=True)
class _Block:
    title: str
    header: tuple[str, ...]
    quantity_columns: tuple[int, ...]
    change_column: int


# PTA's quantity is the duty-paid and the bonded receipts together (user decision 2026-09-26).
_BLOCKS = {
    "TA": _Block(
        "PTA",
        (
            "仓库编号",
            "仓库简称",
            "品牌",
            "仓单数量(完税)",
            "仓单数量(保税)",
            "当日增减",
            "有效预报",
            "升贴水",
        ),
        (3, 4),
        5,
    ),
    "CF": _Block(
        "棉花CF",
        ("仓库编号", "仓库简称", "年度", "等级", "产地", "仓单数量", "当日增减", "有效预报"),
        (5,),
        6,
    ),
}
_INTEGER = re.compile(r"-?\d+")
_WAREHOUSE_CODE = re.compile(r"\d+")
_ANSWERED = re.compile(r"czce_warrant_(?:http_\d{3}|response_invalid|response_oversize)")


@dataclass(frozen=True)
class CzceWarrantMember:
    """One warehouse's subtotal for a day, in receipts ("张")."""

    warehouse: str
    registered_receipts: int
    registered_receipts_change: int


def parse_czce_warrants(
    content: bytes, *, business_date: date, symbol: str
) -> tuple[CzceWarrantMember, ...]:
    """Each warehouse's subtotal in ``symbol``'s block of one day's report.

    The block's header must read as expected, every row must belong to a warehouse that a
    subtotal closes, and the subtotals must add up to the block's total; anything else is
    refused with a reason code rather than read.
    """
    block = _BLOCKS.get(symbol)
    if block is None:
        raise ValueError("czce_warrant_symbol_not_allowed")
    try:
        lines = content.decode("utf-8-sig").splitlines()
    except UnicodeDecodeError as error:
        raise ValueError("czce_warrant_document_invalid") from error
    title = next((line.strip() for line in lines if line.strip()), "")
    if not title.startswith("郑州商品交易所") or f"({business_date.isoformat()})" not in title:
        raise ValueError("czce_warrant_date_mismatch")
    starts = [
        index
        for index, line in enumerate(lines)
        if line.startswith("品种：") and line[3:].split()[:1] == [block.title]
    ]
    if not starts:
        raise ValueError("czce_warrant_symbol_block_missing")
    if len(starts) > 1:
        raise ValueError("czce_warrant_symbol_block_ambiguous")
    start = starts[0]
    if f"日期：{business_date.isoformat()}" not in lines[start].replace(" ", ""):
        raise ValueError("czce_warrant_date_mismatch")
    if start + 1 >= len(lines) or _cells(lines[start + 1]) != block.header:
        raise ValueError("czce_warrant_header_mismatch")
    members: list[CzceWarrantMember] = []
    warehouse: str | None = None
    for line in lines[start + 2 :]:
        cells = _cells(line)
        if len(cells) != len(block.header):
            raise ValueError("czce_warrant_row_invalid")
        # Brand rows leave empty what only their warehouse's subtotal states.
        quantity = sum(
            _integer(cells[column], required=cells[0] in {"小计", "总计"})
            for column in block.quantity_columns
        )
        if cells[0] == "总计":
            if warehouse is not None or not members:
                raise ValueError("czce_warrant_row_invalid")
            change = _integer(cells[block.change_column], required=True)
            if (
                sum(m.registered_receipts for m in members) != quantity
                or sum(m.registered_receipts_change for m in members) != change
            ):
                raise ValueError("czce_warrant_total_mismatch")
            return tuple(members)
        if cells[0] == "小计":
            if warehouse is None or cells[1]:
                raise ValueError("czce_warrant_row_invalid")
            if quantity < 0:
                raise ValueError("czce_warrant_quantity_negative")
            if any(m.warehouse == warehouse for m in members):
                raise ValueError("czce_warrant_warehouse_duplicate")
            members.append(
                CzceWarrantMember(
                    warehouse, quantity, _integer(cells[block.change_column], required=True)
                )
            )
            warehouse = None
        elif _WAREHOUSE_CODE.fullmatch(cells[0]) and cells[1]:
            if warehouse is not None:
                raise ValueError("czce_warrant_row_invalid")
            warehouse = cells[1]
        elif cells[0] or cells[1] or warehouse is None:
            raise ValueError("czce_warrant_row_invalid")
    raise ValueError("czce_warrant_total_missing")


def _cells(line: str) -> tuple[str, ...]:
    return tuple(cell.strip() for cell in line.split("|"))


def _integer(text: str, *, required: bool = False) -> int:
    if not text and not required:
        return 0
    if _INTEGER.fullmatch(text) is None:
        raise ValueError("czce_warrant_value_invalid")
    return int(text)


def warrant_scalars(
    members: Iterable[CzceWarrantMember], *, business_date: date, symbol: str
) -> tuple[ContextScalar, ...]:
    day = business_date.isoformat()
    return tuple(
        ContextScalar(
            metric_id=METRIC_ID,
            api_name=API_NAME,
            source_field=source_field,
            period_kind="business_day",
            period_start=day,
            period_end=day,
            dimensions={
                "symbol": symbol,
                "warehouse": member.warehouse,
                "exchange": "CZCE",
                "measure": measure,
            },
            value=float(getattr(member, measure)),
            unit="sheet",
        )
        for member in members
        for source_field, measure in (
            ("subtotal_receipts", "registered_receipts"),
            ("subtotal_change", "registered_receipts_change"),
        )
    )


def parse_czce_warrant_acquisition(
    receipt: AcquisitionReceipt, raw: bytes, normalized: bytes, *, period: str
) -> WarrantAcquisition:
    """Reparse one symbol-day receipt and check it against what was normalized from it."""
    parameters = receipt.parameters
    if (
        receipt.provider != CZCE_PROVIDER
        or receipt.api_name != "official_http_get"
        or receipt.parser_version != PARSER_VERSION
        or set(parameters) != {"source_url", "business_date", "symbol"}
        or parameters["symbol"] not in CZCE_WARRANT_SYMBOLS
    ):
        raise ValueError("czce_warrant_acquisition_contract_invalid")
    day = date.fromisoformat(parameters["business_date"])
    if parameters["source_url"] != czce_warrant_url(day):
        raise ValueError("czce_warrant_acquisition_contract_invalid")
    members = parse_czce_warrants(raw, business_date=day, symbol=parameters["symbol"])
    if json.loads(normalized) != [asdict(member) for member in members]:
        raise ValueError("czce_warrant_normalized_mismatch")
    scalars = warrant_scalars(members, business_date=day, symbol=parameters["symbol"])
    return WarrantAcquisition(
        parameters["symbol"],
        tuple(scalar for scalar in scalars if scalar.period_end == period),
        len(members) if day.isoformat() == period else 0,
    )


def _sleep(seconds: float) -> None:
    time.sleep(seconds)


def _fetch(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0 (pring-cycle/1.0)"})
    try:
        with open_no_redirects(request, timeout=20) as response:
            if int(response.status) != 200 or response.geturl() != url:
                raise OSError("czce_warrant_response_invalid")
            content = bytes(response.read(_MAX_BYTES + 1))
    except HTTPError as error:
        raise OSError(f"czce_warrant_http_{error.code}") from error
    except HTTPException as error:
        raise OSError("czce_warrant_http_protocol_failed") from error
    if len(content) > _MAX_BYTES:
        raise OSError("czce_warrant_response_oversize")
    return content


def window_trading_days(paths: RuntimePaths, target: date) -> tuple[date, ...]:
    """The last 120 sessions to ``target`` from the validated SSE calendar responses.

    CZCE keeps the SSE's sessions. Only days inside a range some response covered count; with
    no complete window on record, only the target day is known to be a session.
    """
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    with database_connection(paths.database) as connection:
        rows = connection.execute(
            "SELECT acquisition_id FROM acquisition_request WHERE provider='tushare' "
            "AND api_name='trade_cal' AND state='validated'"
        ).fetchall()
    sessions: set[date] = set()
    covered: list[tuple[date, date]] = []
    for (acquisition_id,) in rows:
        receipt = acquisitions.get(acquisition_id)
        try:
            start = datetime.strptime(receipt.parameters["start_date"], "%Y%m%d").date()
            end = datetime.strptime(receipt.parameters["end_date"], "%Y%m%d").date()
            document = json.loads(acquisitions.read_receipt_content(receipt, "normalized"))
        except (KeyError, ValueError, LookupError, OSError):
            continue
        if not isinstance(document, list) or not all(isinstance(day, str) for day in document):
            continue
        covered.append((start, end))
        sessions.update(date.fromisoformat(day) for day in document)
    window = sorted(day for day in sessions if day <= target)[-WINDOW_TRADING_DAYS:]
    complete = (
        len(window) == WINDOW_TRADING_DAYS
        and window[-1] == target
        and _covers(covered, window[0], target)
    )
    return tuple(window) if complete else (target,)


def _covers(ranges: list[tuple[date, date]], first: date, last: date) -> bool:
    reached = first
    for start, end in sorted(ranges):
        if start > reached:
            break
        if end >= reached:
            reached = date.fromordinal(end.toordinal() + 1)
        if reached > last:
            return True
    return reached > last


def refresh_czce_warrants(
    paths: RuntimePaths,
    *,
    days: tuple[date, ...],
    definition_version: str,
    fetch: Callable[[str], bytes] | None = None,
    sleep: Callable[[float], None] | None = None,
) -> dict[str, int]:
    """Take TA and CF for each of ``days`` neither holds yet, one serial request a day.

    Each symbol-day records its own outcome (with the reason code when it fails); a day the
    exchange answers without its file leaves only that day missing. A source that cannot be
    reached at all stops the run's requests: the days left are asked for next run. Returns
    how many days each symbol newly holds.
    """
    repository = EvidenceRepository(paths.database)
    definition = metric_definition(
        METRIC_ID, definition_version=definition_version, database_path=paths.database
    )
    totals = _held_totals(repository, definition_version)
    held = {
        symbol: {day for s, day, _w in totals if s == symbol} for symbol in CZCE_WARRANT_SYMBOLS
    }
    newly = dict.fromkeys(sorted(CZCE_WARRANT_SYMBOLS), 0)
    requested = False
    ordered = sorted(set(days))
    for index, day in enumerate(ordered):
        missing = [s for s in sorted(CZCE_WARRANT_SYMBOLS) if day.isoformat() not in held[s]]
        if not missing:
            continue
        if requested:
            (sleep or _sleep)(REQUEST_INTERVAL_SECONDS)
        requested = True
        response = _DayResponse(czce_warrant_url(day), fetch or _fetch)
        previous = ordered[index - 1].isoformat() if index else None
        for symbol in missing:
            if _take(
                paths,
                repository,
                definition,
                day=day,
                symbol=symbol,
                fetch=response.read,
                previous_totals={
                    warehouse: value
                    for (s, held_day, warehouse), value in totals.items()
                    if s == symbol and held_day == previous
                },
                totals=totals,
            ):
                newly[symbol] += 1
                held[symbol].add(day.isoformat())
        if response.unreachable:
            break
    return newly


class _DayResponse:
    """The day's file, requested once; each symbol's receipt holds that one response."""

    def __init__(self, url: str, fetch: Callable[[str], bytes]) -> None:
        self._url = url
        self._fetch = fetch
        self._outcome: bytes | OSError | None = None

    def read(self) -> bytes:
        if self._outcome is None:
            try:
                self._outcome = self._fetch(self._url)
            except OSError as error:
                self._outcome = error
        if isinstance(self._outcome, OSError):
            raise self._outcome
        return self._outcome

    @property
    def unreachable(self) -> bool:
        # An HTTP status is an answer (a day without its file); anything else is no answer.
        return (
            isinstance(self._outcome, OSError) and _ANSWERED.fullmatch(str(self._outcome)) is None
        )


def _held_totals(
    repository: EvidenceRepository, definition_version: str
) -> dict[tuple[str, str, str], float]:
    """Each CZCE warehouse total held, by symbol, day and warehouse."""
    totals = {}
    for point in repository.metric_series(
        METRIC_ID, mode=AsOfMode.SYSTEM, as_of=utc_now(), definition_version=definition_version
    ):
        claim = next((c for c in point.claims if c.claim_id == point.selected_claim_id), None)
        if (
            claim is not None
            and claim.provider == CZCE_PROVIDER
            and point.dimensions.get("symbol") in CZCE_WARRANT_SYMBOLS
            and point.dimensions.get("measure") == "registered_receipts"
            and point.selected_value is not None
        ):
            key = (point.dimensions["symbol"], point.period_end, point.dimensions["warehouse"])
            totals[key] = point.selected_value
    return totals


def _take(
    paths: RuntimePaths,
    repository: EvidenceRepository,
    definition: MetricDefinition,
    *,
    day: date,
    symbol: str,
    fetch: Callable[[], bytes],
    previous_totals: dict[str, float],
    totals: dict[tuple[str, str, str], float],
) -> bool:
    url = czce_warrant_url(day)
    metadata = {
        "source_url": url,
        "business_date": day.isoformat(),
        "period": day.isoformat(),
        "symbol": symbol,
    }
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    identities: list[str] = []
    try:
        acquired = acquisitions.capture(
            provider=CZCE_PROVIDER,
            api_name="official_http_get",
            parameters={"source_url": url, "business_date": day.isoformat(), "symbol": symbol},
            fields=API_NAME,
            parser_version=PARSER_VERSION,
            fetch=fetch,
            parse=lambda raw: parse_czce_warrants(raw, business_date=day, symbol=symbol),
            normalize=lambda members: [asdict(member) for member in members],
            on_started=identities.append,
        )
    except (OSError, ValueError) as error:
        repository.record_retrieval_attempt(
            metric_id=METRIC_ID,
            channel=CHANNEL,
            outcome="source_failed" if isinstance(error, OSError) else "validation_failed",
            fetched_at=utc_now(),
            acquisition_ids=tuple(identities),
            safe_metadata={**metadata, "error_type": type(error).__name__, "reason": str(error)},
        )
        return False
    receipt = acquired.receipt
    scalars = warrant_scalars(acquired.value, business_date=day, symbol=symbol)
    claims = tuple(
        SourceClaimInput(
            metric_id=METRIC_ID,
            definition_version=definition.definition_version,
            period_kind=scalar.period_kind,
            period_start=scalar.period_start,
            period_end=scalar.period_end,
            dimensions=scalar.dimensions,
            value=scalar.value,
            value_state=EvidenceValueState.REPORTED_VALUE,
            unit=scalar.unit,
            provider=CZCE_PROVIDER,
            source_reference=czce_source_reference(day, symbol),
            release_event_id=f"czce:warehouse_receipts:{day.isoformat()}",
            release_at=None,
            public_available_at=None,
            fetched_at=receipt.received_at or utc_now(),
            available_at=receipt.validated_at or utc_now(),
            certification_status=definition.certification_status,
            quality_status="validated",
            acquisition_id=receipt.acquisition_id,
        )
        for scalar in scalars
    )
    try:
        repository.append_source_claims(claims, availability_clock=utc_now)
    except ValueError as error:
        acquisitions.record_ingest_result(receipt.acquisition_id, error)
        repository.record_retrieval_attempt(
            metric_id=METRIC_ID,
            channel=CHANNEL,
            outcome="validation_failed",
            fetched_at=utc_now(),
            acquisition_ids=(receipt.acquisition_id,),
            safe_metadata={**metadata, "stage": "ingest", "reason": str(error)[:300]},
        )
        return False
    acquisitions.record_ingest_result(receipt.acquisition_id, None)
    for member in acquired.value:
        totals[(symbol, day.isoformat(), member.warehouse)] = float(member.registered_receipts)
    repository.record_retrieval_attempt(
        metric_id=METRIC_ID,
        channel=CHANNEL,
        outcome="verified_candidate",
        fetched_at=utc_now(),
        acquisition_ids=(receipt.acquisition_id,),
        safe_metadata={
            **metadata,
            "warehouses": str(len(acquired.value)),
            "reconciliation": json.dumps(
                _reconciliation(acquired.value, previous_totals), ensure_ascii=False
            ),
        },
    )
    return True


def _reconciliation(
    members: Iterable[CzceWarrantMember], previous_totals: dict[str, float]
) -> list[dict[str, object]]:
    """Where a warehouse's change disagrees with its totals on the previous session held.

    Noted only, never rejected (ADR-0029). A warehouse the previous session did not list, or a
    day whose previous session is not held, is left unchecked.
    """
    return [
        {
            "warehouse": member.warehouse,
            "total": member.registered_receipts,
            "previous_total": previous_totals[member.warehouse],
            "change": member.registered_receipts_change,
        }
        for member in members
        if member.warehouse in previous_totals
        and member.registered_receipts - previous_totals[member.warehouse]
        != member.registered_receipts_change
    ]
