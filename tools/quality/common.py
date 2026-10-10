"""Shared read-only access for the quality audit: the run, its frozen model, window and calendars.

Every layer module takes a ``Run`` and reads through it. Nothing here imports ``pring_cycle``:
the audit has to stay an independent second reading of the same database, so the rules it
needs (window length, calendars, which metrics the model uses) come from stored data, the
frozen manifest, or the documented tables below.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from functools import cached_property
from pathlib import Path

DEFAULT_DATABASE = Path.home() / ".local/share/pring-cycle/pring-cycle.sqlite3"


def connect(database: Path) -> sqlite3.Connection:
    """Open the runtime database read-only; the audit must never write to it.

    Sorting spills to memory, not temporary files, so a read-only sandbox can run it too.
    """
    if not database.exists():
        raise SystemExit(f"database not found: {database}")
    db = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    db.execute("PRAGMA temp_store = MEMORY")
    return db


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def iso_day(value: str) -> str:
    """``20260930`` or ``2026-09-30`` to ``2026-09-30``."""
    value = value.strip()
    if len(value) == 8 and value.isdigit():
        return f"{value[:4]}-{value[4:6]}-{value[6:]}"
    return value[:10]


# --- calendars ----------------------------------------------------------------------------


@dataclass(frozen=True)
class Calendar:
    """Open days of one market, and the span of days the calendar actually speaks for."""

    name: str
    source: str
    open_days: frozenset[str]
    covered: frozenset[str]

    def classify(self, day: str) -> str:
        if day not in self.covered:
            return "uncovered"
        return "open" if day in self.open_days else "closed"


def _easter(year: int) -> date:
    """Gregorian Easter Sunday (anonymous algorithm)."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    g = (8 * b + 13) // 25
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    m = (32 + 2 * e + 2 * i - h - k) % 7
    n = (h + m + 114 - 7 * ((a + 11 * h + 19 * m) // 433)) // 31
    p = (h + m + 114 - 7 * ((a + 11 * h + 19 * m) // 433)) % 31
    return date(year, n, p + 1)


# Built-in holiday tables. Both must be extended every year; years outside them are reported
# as "calendar uncovered" rather than guessed.
NYSE_HOLIDAYS = {
    2025: [
        "2025-01-01", "2025-01-09", "2025-01-20", "2025-02-17", "2025-04-18", "2025-05-26",
        "2025-06-19", "2025-07-04", "2025-09-01", "2025-11-27", "2025-12-25",
    ],
    2026: [
        "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25", "2026-06-19",
        "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25",
    ],
    2027: [
        "2027-01-01", "2027-01-18", "2027-02-15", "2027-03-26", "2027-05-31", "2027-06-18",
        "2027-07-05", "2027-09-06", "2027-11-25", "2027-12-24",
    ],
}  # fmt: skip
# The Treasury market (SIFMA) also closes on Columbus Day and Veterans Day.
US_BOND_EXTRA_HOLIDAYS = {
    2025: ["2025-10-13", "2025-11-11"],
    2026: ["2026-10-12", "2026-11-11"],
    2027: ["2027-10-11", "2027-11-11"],
}
TARGET_YEARS = range(2025, 2028)

# Catalog fields that do not change what a series is: a claim stored under an older catalog
# version whose definition differs only in these still counts as the same series.
IDENTITY_NEUTRAL = {"definition_version", "priority", "certification_status", "name_cn"}


def _weekday_calendar(name: str, source: str, years, holidays: set[str]) -> Calendar:
    covered, open_days = set(), set()
    for year in years:
        day = date(year, 1, 1)
        while day.year == year:
            text = day.isoformat()
            covered.add(text)
            if day.weekday() < 5 and text not in holidays:
                open_days.add(text)
            day += timedelta(days=1)
    return Calendar(name, source, frozenset(open_days), frozenset(covered))


def us_equity_calendar() -> Calendar:
    holidays = {d for days in NYSE_HOLIDAYS.values() for d in days}
    return _weekday_calendar("US_EQUITY", "built-in NYSE holidays", NYSE_HOLIDAYS, holidays)


def us_treasury_calendar() -> Calendar:
    holidays = {d for days in NYSE_HOLIDAYS.values() for d in days}
    holidays |= {d for days in US_BOND_EXTRA_HOLIDAYS.values() for d in days}
    return _weekday_calendar(
        "US_TREASURY", "built-in NYSE + SIFMA holidays", NYSE_HOLIDAYS, holidays
    )


def target_calendar() -> Calendar:
    """ECB reference rates follow TARGET closing days."""
    holidays: set[str] = set()
    for year in TARGET_YEARS:
        easter = _easter(year)
        holidays |= {
            f"{year}-01-01",
            (easter - timedelta(days=2)).isoformat(),
            (easter + timedelta(days=1)).isoformat(),
            f"{year}-05-01",
            f"{year}-12-25",
            f"{year}-12-26",
        }
    return _weekday_calendar("TARGET", "built-in TARGET holidays", TARGET_YEARS, holidays)


# --- the audited run ----------------------------------------------------------------------


@dataclass
class Receipt:
    acquisition_id: str
    provider: str
    api_name: str
    parameters: dict
    state: str
    started_at: str
    received_at: str | None
    validated_at: str | None
    raw_hash: str | None
    source_record_count: int | None
    error_type: str | None
    rejection_reason: str | None


@dataclass
class Run:
    """One completed run, read once; layers share it instead of re-querying the basics."""

    db: sqlite3.Connection
    run_id: str
    artifacts: Path
    target_date: str = ""
    cutoff: str = ""
    model_version_id: str = ""
    manifest: dict = field(default_factory=dict)

    @classmethod
    def load(cls, db: sqlite3.Connection, run_id: str, database: Path) -> Run:
        row = db.execute(
            "SELECT target_business_date, system_as_of, model_version_id, status"
            " FROM parent_run WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        if row is None:
            raise SystemExit(f"run not found: {run_id}")
        target, cutoff, model_version_id, status = row
        if status != "completed":
            raise SystemExit(f"run {run_id} is {status}; the audit reads completed runs only")
        frozen = db.execute(
            "SELECT system_as_of FROM run_cutoff_freeze WHERE run_id = ?", (run_id,)
        ).fetchone()
        manifest = json.loads(
            db.execute(
                "SELECT manifest_json FROM model_version WHERE model_version_id = ?",
                (model_version_id,),
            ).fetchone()[0]
        )
        return cls(
            db=db,
            run_id=run_id,
            artifacts=database.parent / "artifacts",
            target_date=target,
            cutoff=frozen[0] if frozen else cutoff,
            model_version_id=model_version_id,
            manifest=manifest,
        )

    # -- frozen model ---------------------------------------------------------------------

    @cached_property
    def catalog(self) -> dict[str, dict]:
        """The frozen metric catalog, keyed by metric id, in manifest order."""
        return {d["metric_id"]: d for d in self.manifest["metric_definitions"]}

    @property
    def catalog_version(self) -> str:
        return self.manifest["metric_catalog_version"]

    @cached_property
    def model_used(self) -> frozenset[str]:
        """Metrics the frozen rules reference: core metrics, every catalog id named anywhere
        in ``confirmation_rules``, and the warrants behind ``warrant_conversions``."""
        found: set[str] = set(self.manifest["core_metrics"].values())

        def walk(node) -> None:
            if isinstance(node, dict):
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)
            elif isinstance(node, str) and node in self.catalog:
                found.add(node)

        rules = self.manifest["confirmation_rules"]
        walk(rules)
        if rules.get("warrant_conversions"):
            found.add("CN_FUTURES_WARRANTS")
        return frozenset(found & set(self.catalog))

    @cached_property
    def derived_only(self) -> frozenset[str]:
        """Catalog metrics that, by the cutoff, exist only as derived observations (ticket 02)."""
        rows = self.db.execute(
            "SELECT DISTINCT d.metric_id FROM derived_observation d WHERE d.computed_at <= ?"
            " AND NOT EXISTS (SELECT 1 FROM source_claim s"
            " WHERE s.metric_id = d.metric_id AND s.available_at <= ?)",
            (self.cutoff, self.cutoff),
        )
        return frozenset({r[0] for r in rows} & set(self.catalog))

    @cached_property
    def same_definition(self) -> dict[str, frozenset[str]]:
        """Per metric, the catalog versions whose definition matches the frozen one. Claims
        stored under those versions describe the same series (only identity-neutral fields,
        ``IDENTITY_NEUTRAL``, may differ)."""

        def identity(definition: dict) -> dict:
            return {k: v for k, v in definition.items() if k not in IDENTITY_NEUTRAL}

        frozen = {m: identity(d) for m, d in self.catalog.items()}
        found: dict[str, set[str]] = {m: {self.catalog_version} for m in self.catalog}
        for version, definitions in self.db.execute(
            "SELECT catalog_version, definitions_json FROM registered_metric_catalog"
        ):
            for definition in json.loads(definitions):
                metric = definition.get("metric_id")
                if metric in frozen and identity(definition) == frozen[metric]:
                    found[metric].add(version)
        return {m: frozenset(v) for m, v in found.items()}

    # -- receipts and raw artifacts -------------------------------------------------------

    def artifact(self, content_hash: str) -> bytes:
        return (self.artifacts / "sha256" / content_hash[:2] / content_hash).read_bytes()

    def receipts(self, where: str, params: tuple = ()) -> list[Receipt]:
        """Receipts started by the cutoff, newest first; ``where`` filters ``a``. Whether the
        answer itself arrived by the cutoff is ``reached_source``'s question."""
        rows = self.db.execute(
            "SELECT a.acquisition_id, a.provider, a.api_name, a.parameters_json, a.state,"
            " a.started_at, a.received_at, a.validated_at, a.raw_hash, a.source_record_count,"
            " a.error_type, a.rejection_reason FROM acquisition_request a"
            f" WHERE a.started_at <= ? AND ({where}) ORDER BY a.started_at DESC",
            (self.cutoff, *params),
        ).fetchall()
        return [Receipt(r[0], r[1], r[2], json.loads(r[3]), *r[4:]) for r in rows]

    def reached_source(self, receipt: Receipt) -> bool:
        """The receipt holds an upstream answer received by the cutoff."""
        return bool(receipt.raw_hash and receipt.received_at and receipt.received_at <= self.cutoff)

    def validated_by_cutoff(self, receipt: Receipt) -> bool:
        return receipt.state == "validated" and bool(
            receipt.validated_at and receipt.validated_at <= self.cutoff
        )

    def run_receipts(self, api_name: str) -> list[Receipt]:
        return self.receipts(
            "a.api_name = ? AND a.acquisition_id IN"
            " (SELECT acquisition_id FROM full_run_acquisition WHERE run_id = ?)",
            (api_name, self.run_id),
        )

    # -- calendars and window -------------------------------------------------------------

    def _tushare_calendar(self, name: str, api_name: str, exchange: str) -> Calendar | None:
        """Open days from the stored raw response: the run's own receipt first, else the
        newest earlier one. A receipt failed downstream still carries the upstream answer."""
        candidates = self.run_receipts(api_name)
        candidates += [
            r for r in self.receipts("a.api_name = ?", (api_name,)) if r not in candidates
        ]
        for receipt in candidates:
            if receipt.parameters.get("exchange", "SSE") != exchange:
                continue
            if not self.reached_source(receipt):
                continue
            try:
                payload = json.loads(self.artifact(receipt.raw_hash))
                fields, items = payload["data"]["fields"], payload["data"]["items"]
                day_at, open_at = fields.index("cal_date"), fields.index("is_open")
                covered = {iso_day(str(item[day_at])) for item in items}
                open_days = {
                    iso_day(str(item[day_at])) for item in items if int(item[open_at]) == 1
                }
            except (OSError, ValueError, KeyError, TypeError, IndexError):
                continue  # an error payload or another shape: try the next receipt
            if not covered:
                continue
            source = f"{api_name} {receipt.acquisition_id} ({receipt.state})"
            return Calendar(name, source, frozenset(open_days), frozenset(covered))
        return None

    @cached_property
    def calendars(self) -> dict[str, Calendar]:
        found = {"US_EQUITY": us_equity_calendar(), "US_TREASURY": us_treasury_calendar()}
        found["TARGET"] = target_calendar()
        sse = self._tushare_calendar("SSE", "trade_cal", "SSE")
        if sse is None:
            raise SystemExit("no stored SSE trade_cal response by the cutoff")
        found["SSE"] = sse
        for exchange in ("SHFE", "DCE", "CZCE", "INE"):
            calendar = self._tushare_calendar(exchange, "fut_trade_cal", exchange)
            if calendar is not None:
                found[exchange] = calendar
        return found

    @cached_property
    def window(self) -> list[str]:
        """The last N SSE open days up to the target date, N from the frozen manifest."""
        size = int(self.manifest["visible_evidence_window_trading_days"])
        days = sorted(d for d in self.calendars["SSE"].open_days if d <= self.target_date)
        if len(days) < size:
            raise SystemExit(f"SSE calendar has only {len(days)} open days up to the target")
        return days[-size:]

    @cached_property
    def system_start(self) -> str:
        """The first receipt in the database: periods published before it were backfilled."""
        return self.db.execute("SELECT MIN(started_at) FROM acquisition_request").fetchone()[0]


# --- markdown -----------------------------------------------------------------------------


def table(headers: list[str], rows: list[list]) -> str:
    def cell(value) -> str:
        return str(value).replace("|", "\\|").replace("\n", " ")

    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(cell(v) for v in row) + " |" for row in rows]
    return "\n".join(lines)


def compress_days(days: list[str], calendar_days: list[str]) -> str:
    """Join runs of consecutive calendar days: ``04-09～04-30（16 日）, 07-21``."""
    if not days:
        return ""
    position = {d: i for i, d in enumerate(calendar_days)}
    days = sorted(days, key=lambda d: position.get(d, -1))
    runs: list[list[str]] = [[days[0]]]
    for day in days[1:]:
        if position.get(day, -2) == position.get(runs[-1][-1], -9) + 1:
            runs[-1].append(day)
        else:
            runs.append([day])
    parts = []
    for run in runs:
        if len(run) == 1:
            parts.append(run[0])
        else:
            parts.append(f"{run[0]}～{run[-1]}（{len(run)} 日）")
    return ", ".join(parts)
