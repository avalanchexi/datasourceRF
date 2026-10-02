"""TuShare's call quotas, kept before each call (ticket 31, CONTEXT.md「调用限额」).

A quota is per interface and per account: a minute's rate and a day's total, by the account's
point tier or an interface's own grant. Every TuShare call through the receipt store passes
here before its receipt is written, so the receipts are the count, and a call held back
sent nothing and counts nothing:

- over 80% of an interface's minute rate, the call waits for the oldest to leave the minute;
- at 90% of a day's total (the interface's own, or the account's), it is not made: not
  attempted, the day's quota spent, no failure of the source;
- an interface the source refused for the day is asked once a run, the run it was refused
  in included, until the source answers it otherwise. When a refused quota renews is the
  source's to say, so no hour is presumed.

The day is Beijing's calendar day, the source's own. Calls made elsewhere (tests, probes by
hand) are not seen. A refusal for want of permission, or for the minute, stops nothing here:
the retrieval ledger backs off on those (ticket 22).
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from pring_cycle.acquisition import DAILY_QUOTA_REFUSED as DAILY_REFUSED
from pring_cycle.storage import database_connection

_SHANGHAI = ZoneInfo("Asia/Shanghai")
_MINUTE = timedelta(minutes=1)
# What is kept of a quota: a margin under the minute's rate, a stop before the day's end.
MINUTE_SHARE_PERCENT = 80
DAILY_SHARE_PERCENT = 90
# An interface no grant names is taken at this rate a minute, whatever the tier.
UNREGISTERED_PER_MINUTE = 50
# The mark a call held back for a spent day carries (a refused one's is ``DAILY_REFUSED``).
DAILY_EXHAUSTED = "tushare_daily_quota_exhausted"


@dataclass(frozen=True)
class AccountTier:
    """What a point tier allows: a rate per interface, and a day's total for the account
    or for each interface."""

    points: int
    per_minute: int
    daily_total: int | None = None
    daily_per_interface: int | None = None


@dataclass(frozen=True)
class InterfaceGrant:
    """An interface's own quota where the source states one apart from the tier."""

    per_minute: int | None = None
    daily: int | None = None


@dataclass(frozen=True)
class CallQuota:
    per_minute: int
    daily: int | None


# TuShare's tiers (https://tushare.pro/document/1?doc_id=290).
TIERS = {
    120: AccountTier(points=120, per_minute=50, daily_total=8000),
    200: AccountTier(points=200, per_minute=100, daily_per_interface=100_000),
    500: AccountTier(points=500, per_minute=500),
}
# The account's tier: the conservative 120 points until the user names theirs (2026-10-02).
# A change of tier is made here and nowhere else.
ACCOUNT_TIER = TIERS[120]
INTERFACE_GRANTS = {
    "major_news": InterfaceGrant(daily=40),
    "stock_basic": InterfaceGrant(per_minute=50),
    "daily": InterfaceGrant(per_minute=500),
}


def quota(api_name: str) -> CallQuota:
    """An interface's quota: its own grant, within the tier's rate; else the conservative one."""
    grant = INTERFACE_GRANTS.get(api_name, InterfaceGrant())
    return CallQuota(
        per_minute=min(grant.per_minute or UNREGISTERED_PER_MINUTE, ACCOUNT_TIER.per_minute),
        daily=grant.daily or ACCOUNT_TIER.daily_per_interface,
    )


def minute_allowance(api_name: str) -> int:
    return quota(api_name).per_minute * MINUTE_SHARE_PERCENT // 100


def daily_allowance(api_name: str) -> int | None:
    daily = quota(api_name).daily
    return None if daily is None else daily * DAILY_SHARE_PERCENT // 100


def account_daily_allowance() -> int | None:
    total = ACCOUNT_TIER.daily_total
    return None if total is None else total * DAILY_SHARE_PERCENT // 100


class TushareCallNotAttempted(OSError):
    """A TuShare call held back before it was sent: not attempted, no failure of the source.

    Raised where a call through the receipt store starts, so it is read as not attempted
    (``acquisition_step`` ``start``), its message the condition.
    """

    def __init__(self, condition: str, api_name: str) -> None:
        super().__init__(condition)
        self.condition = condition
        self.api_name = api_name
        self.acquisition_step = "start"


class Pacing:
    """The time a quota is kept by: the receipts' clock, and how a call waits."""

    def __init__(self) -> None:
        self.skipped = timedelta()

    def now(self) -> datetime:
        from pring_cycle import acquisition

        return acquisition.utc_now()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)

    def skip(self, seconds: float) -> None:
        """Wait without waiting, for tests: their clocks add what was skipped."""
        self.skipped += timedelta(seconds=seconds)


PACING = Pacing()


def admit(database: Path, api_name: str) -> None:
    """Hold a TuShare call to its quotas: wait out the minute, or refuse it for the day."""
    while True:
        now = PACING.now()
        with database_connection(database) as connection:
            _require_day(connection, api_name, now)
            wait = _minute_wait(connection, api_name, now)
        if wait <= 0:
            return
        PACING.sleep(wait)


def _require_day(connection: sqlite3.Connection, api_name: str, now: datetime) -> None:
    from pring_cycle.batches import current_batch_id

    day = now.astimezone(_SHANGHAI).date()
    start = datetime.combine(day, datetime.min.time(), _SHANGHAI)
    bounds = (start.isoformat(), (start + timedelta(days=1)).isoformat())
    query = connection.execute
    spent = query(
        "SELECT count(*), coalesce(sum(api_name=?), 0) FROM acquisition_request "
        "WHERE provider='tushare' AND julianday(started_at) >= julianday(?) "
        "AND julianday(started_at) < julianday(?)",
        (api_name, *bounds),
    ).fetchone()
    account, own = account_daily_allowance(), daily_allowance(api_name)
    if (account is not None and spent[0] >= account) or (own is not None and spent[1] >= own):
        raise TushareCallNotAttempted(DAILY_EXHAUSTED, api_name)
    # Refused for the day: until the source answers this interface with a response (not an
    # HTTP error, not another refusal), a run asks it once at most, the run it was refused
    # in included (a call that got no answer is that once). A call is the run's that
    # acquired it, or whose retrieval request it was.
    refused = query(
        "SELECT started_at FROM acquisition_request WHERE provider='tushare' AND api_name=? "
        "AND rejection_reason LIKE ? ORDER BY julianday(started_at) DESC LIMIT 1",
        (api_name, f"{DAILY_REFUSED}%"),
    ).fetchone()
    if (
        refused is None
        or query(
            "SELECT 1 FROM acquisition_request WHERE provider='tushare' AND api_name=? "
            "AND (state IN ('received', 'validated') OR structure_check IS NOT NULL) "
            "AND julianday(started_at) > julianday(?) LIMIT 1",
            (api_name, refused[0]),
        ).fetchone()
    ):
        return
    run_id = current_batch_id()
    if (
        run_id is not None
        and query(
            "SELECT count(*) FROM sqlite_master WHERE type='table' "
            "AND name IN ('full_run_acquisition', 'retrieval_physical_request')"
        ).fetchone()[0]
        == 2
        and query(
            "SELECT 1 FROM acquisition_request AS call WHERE call.provider='tushare' "
            "AND call.api_name=? AND julianday(call.started_at) >= julianday(?) "
            "AND (call.acquisition_id IN (SELECT acquisition_id FROM full_run_acquisition "
            "WHERE run_id=?) OR call.acquisition_id IN (SELECT acquisition_id "
            "FROM retrieval_physical_request WHERE run_id=? AND acquisition_id IS NOT NULL)) "
            "LIMIT 1",
            (api_name, refused[0], run_id, run_id),
        ).fetchone()
    ):
        raise TushareCallNotAttempted(DAILY_REFUSED, api_name)


def _minute_wait(connection: sqlite3.Connection, api_name: str, now: datetime) -> float:
    """How long until fewer than the allowance of this interface's calls are in the minute."""
    allowance = minute_allowance(api_name)
    since = now - _MINUTE
    started = sorted(
        moment
        for (value,) in connection.execute(
            "SELECT started_at FROM acquisition_request WHERE provider='tushare' "
            "AND api_name=? AND julianday(started_at) >= julianday(?)",
            (api_name, (since - timedelta(seconds=1)).isoformat()),
        )
        if since < (moment := datetime.fromisoformat(str(value))) <= now
    )
    if len(started) < allowance:
        return 0.0
    # The call that must leave the minute for this one to be within the allowance.
    leaving = started[len(started) - allowance]
    return (leaving + _MINUTE - now).total_seconds() + 0.001
