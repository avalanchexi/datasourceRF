"""Ticket 31: TuShare's call quotas, a minute's rate and a day's total, kept before a call."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from email.message import Message
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from zoneinfo import ZoneInfo

import pytest

from pring_cycle import tushare_quota
from pring_cycle.acquisition import AcquisitionRepository, own_acquisitions
from pring_cycle.acquisition_outcome import (
    NOT_ATTEMPTED,
    AcquisitionOutcomes,
    capture_failure,
)
from pring_cycle.batches import processing_batch
from pring_cycle.evidence import EvidenceRepository
from pring_cycle.models import ModelRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.source_adapters import TushareRefused
from pring_cycle.storage import database_connection
from pring_cycle.tushare_context import ContextRequestFailed, TushareContextAdapter
from pring_cycle.tushare_quota import InterfaceGrant, TushareCallNotAttempted
from tests.conftest import _clock_datetime
from tests.integration.test_acquisition_outcome import submit

_SHANGHAI = ZoneInfo("Asia/Shanghai")
DAILY_REFUSAL = (
    "抱歉，您访问接口(major_news)频率超限(40次/天)，"
    "具体频次详情：https://tushare.pro/document/1?doc_id=108。"
)
MINUTE_REFUSAL = "抱歉，您每分钟最多访问该接口200次"
PERMISSION_REFUSAL = "抱歉，您没有访问该接口的权限"


class Timeline:
    """The receipts' clock, moved on only by the quota's own waiting."""

    def __init__(self) -> None:
        self.shift = timedelta()
        self.waits: list[float] = []

    def now(self) -> datetime:
        return datetime.now(UTC) + self.shift

    def wait(self, seconds: float) -> None:
        self.waits.append(seconds)
        self.shift += timedelta(seconds=seconds)


@pytest.fixture
def paths(tmp_path: Path) -> RuntimePaths:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    ModelRepository(paths.database).activate("model-v0001", explicitly_approved=True)
    return paths


@pytest.fixture
def timeline(monkeypatch: pytest.MonkeyPatch) -> Iterator[Timeline]:
    timeline = Timeline()
    monkeypatch.setattr("pring_cycle.acquisition.datetime", _clock_datetime(timeline.now))
    monkeypatch.setattr(tushare_quota.PACING, "sleep", timeline.wait)
    yield timeline


def call(
    paths: RuntimePaths,
    api_name: str,
    *,
    refusal: str | None = None,
    sent: list[str] | None = None,
    timeout: bool = False,
    http_status: int | None = None,
    on_started: Callable[[str], None] | None = None,
) -> str:
    """One TuShare call through the receipt store; its receipt's id."""

    def fetch() -> bytes:
        if sent is not None:
            sent.append(api_name)
        if timeout:
            raise TimeoutError("timed out")
        if http_status is not None:
            raise HTTPError("https://api.tushare.pro", http_status, "unavailable", Message(), None)
        if refusal is not None:
            return json.dumps({"code": 40203, "msg": refusal}).encode()
        return json.dumps({"code": 0, "data": {"fields": [], "items": []}}).encode()

    def parse(raw: bytes) -> dict[str, Any]:
        document = json.loads(raw)
        if document["code"] != 0:
            raise TushareRefused(document["code"], document["msg"])
        return dict(document)

    acquired = AcquisitionRepository(paths.database, paths.artifacts).capture(
        provider="tushare",
        api_name=api_name,
        parameters={"page": str(len(sent or ()))},
        fields="value",
        parser_version="fixture-parser",
        fetch=fetch,
        parse=parse,
        normalize=lambda document: document,
        on_started=on_started,
    )
    return acquired.receipt.acquisition_id


def calls(paths: RuntimePaths, count: int, api_name: str) -> None:
    for _ in range(count):
        call(paths, api_name)


def receipts(paths: RuntimePaths, api_name: str) -> int:
    with database_connection(paths.database) as connection:
        return int(
            connection.execute(
                "SELECT count(*) FROM acquisition_request WHERE api_name=?", (api_name,)
            ).fetchone()[0]
        )


def test_the_registry_holds_the_120_point_tier_and_major_news(monkeypatch: Any) -> None:
    assert tushare_quota.quota("fut_wsr") == tushare_quota.CallQuota(per_minute=50, daily=None)
    assert tushare_quota.quota("major_news").daily == 40
    assert tushare_quota.quota("unregistered_api").per_minute == 50
    assert tushare_quota.ACCOUNT_TIER.daily_total == 8000
    # What is kept: 80% of a minute's rate, and a stop at 90% of a day's total.
    assert tushare_quota.minute_allowance("fut_wsr") == 40
    assert tushare_quota.daily_allowance("major_news") == 36
    assert tushare_quota.account_daily_allowance() == 7200


def test_a_call_over_the_minute_waits_for_the_oldest_to_age_out(
    paths: RuntimePaths, timeline: Timeline
) -> None:
    calls(paths, 40, "fut_wsr")
    assert timeline.waits == []

    call(paths, "fut_wsr")

    # The forty-first waits until the first leaves the minute; none is dropped.
    assert timeline.waits and 0 < sum(timeline.waits) <= 60.01
    with database_connection(paths.database) as connection:
        started = [
            datetime.fromisoformat(row[0])
            for row in connection.execute(
                "SELECT started_at FROM acquisition_request WHERE api_name='fut_wsr' "
                "ORDER BY started_at"
            )
        ]
    assert len(started) == 41 and started[40] - started[0] > timedelta(minutes=1)


def test_another_interface_keeps_its_own_minute(paths: RuntimePaths, timeline: Timeline) -> None:
    calls(paths, 40, "fut_wsr")

    call(paths, "cn_cpi")

    assert timeline.waits == []


def test_a_spent_daily_quota_sends_nothing_and_is_not_a_failure(
    paths: RuntimePaths, timeline: Timeline
) -> None:
    calls(paths, 36, "major_news")
    sent: list[str] = []

    with pytest.raises(TushareCallNotAttempted) as stopped:
        call(paths, "major_news", sent=sent)

    assert sent == [] and receipts(paths, "major_news") == 36
    outcome, details = capture_failure(stopped.value)
    assert outcome == NOT_ATTEMPTED
    assert details["condition"] == "tushare_daily_quota_exhausted"
    assert details["request_sent"] == "false"
    run, accepted = submit(paths, "run")
    with processing_batch(run):
        EvidenceRepository(paths.database).record_retrieval_attempt(
            metric_id="CN_RRR_EVENT",
            channel="tushare_news",
            outcome=outcome,
            fetched_at=accepted + timedelta(seconds=1),
            safe_metadata=details,
        )
    assert AcquisitionOutcomes(paths.database).for_batch(run).failures() == {}
    # Another interface still goes out, and the next Beijing day the quota is whole again.
    call(paths, "cn_cpi")
    beijing = timeline.now().astimezone(_SHANGHAI)
    midnight = datetime.combine(beijing.date() + timedelta(days=1), datetime.min.time(), _SHANGHAI)
    timeline.shift += midnight - beijing + timedelta(seconds=1)
    call(paths, "major_news")


def test_the_account_s_daily_total_stops_every_interface(
    paths: RuntimePaths, timeline: Timeline, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        tushare_quota,
        "ACCOUNT_TIER",
        tushare_quota.AccountTier(points=0, per_minute=50, daily_total=10),
    )
    calls(paths, 5, "fut_wsr")
    calls(paths, 4, "cn_cpi")

    with pytest.raises(TushareCallNotAttempted):
        call(paths, "cn_ppi")


@contextmanager
def in_run(paths: RuntimePaths, run_id: str) -> Iterator[None]:
    """Calls made in a run, as the Worker makes them: its batch, its calls."""
    with processing_batch(run_id), own_acquisitions(paths.database, run_id, "fixture_phase"):
        yield


def test_a_daily_refusal_stops_the_interface_for_the_run_and_the_next_run_probes_once(
    paths: RuntimePaths, timeline: Timeline
) -> None:
    first, _ = submit(paths, "first")
    with in_run(paths, first):
        with pytest.raises(TushareRefused):
            call(paths, "major_news", refusal=DAILY_REFUSAL)
        sent: list[str] = []
        with pytest.raises(TushareCallNotAttempted) as stopped:
            call(paths, "major_news", sent=sent)
        assert sent == []
        assert capture_failure(stopped.value)[1]["condition"] == "tushare_daily_quota_refused"
        call(paths, "cn_cpi")

    # The next run tries once; refused again, it stops there too.
    second, _ = submit(paths, "second")
    with in_run(paths, second):
        sent = []
        with pytest.raises(TushareRefused):
            call(paths, "major_news", refusal=DAILY_REFUSAL, sent=sent)
        with pytest.raises(TushareCallNotAttempted):
            call(paths, "major_news", sent=sent)
        assert sent == ["major_news"]

    # Answered, the run after it goes on as usual.
    third, _ = submit(paths, "third")
    with in_run(paths, third):
        sent = []
        call(paths, "major_news", sent=sent)
        call(paths, "major_news", sent=sent)
        assert sent == ["major_news", "major_news"]


def test_a_probe_that_gets_no_answer_is_the_run_s_one(
    paths: RuntimePaths, timeline: Timeline
) -> None:
    first, _ = submit(paths, "first")
    with in_run(paths, first), pytest.raises(TushareRefused):
        call(paths, "major_news", refusal=DAILY_REFUSAL)
    second, _ = submit(paths, "second")
    with in_run(paths, second):
        with pytest.raises(OSError, match="timed out"):
            call(paths, "major_news", timeout=True)
        sent: list[str] = []
        with pytest.raises(TushareCallNotAttempted):
            call(paths, "major_news", sent=sent)

    assert sent == []


def test_a_targeted_run_s_probe_is_known_by_its_retrieval_request(
    paths: RuntimePaths, timeline: Timeline
) -> None:
    """A run without acquisition owners: its calls are its retrieval requests'."""
    first, _ = submit(paths, "first")
    with in_run(paths, first), pytest.raises(TushareRefused):
        call(paths, "major_news", refusal=DAILY_REFUSAL)
    targeted, _ = submit(paths, "targeted")
    sent: list[str] = []

    def requested(acquisition_id: str) -> None:
        with database_connection(paths.database) as connection:
            connection.execute(
                "INSERT INTO retrieval_physical_request(request_id, run_id, channel, "
                "provider_key, release_event_id, state, started_at, run_attempt, "
                "acquisition_id) VALUES (?, ?, 'tushare', 'major_news', 'fixture', "
                "'started', ?, 1, ?)",
                (f"request-{acquisition_id}", targeted, timeline.now().isoformat(), acquisition_id),
            )

    with processing_batch(targeted):
        with pytest.raises(OSError, match="timed out"):
            call(paths, "major_news", timeout=True, sent=sent, on_started=requested)
        with pytest.raises(TushareCallNotAttempted):
            call(paths, "major_news", sent=sent)

    assert sent == ["major_news"]


def test_a_retry_held_back_for_the_day_leaves_the_request_that_failed(
    paths: RuntimePaths, timeline: Timeline, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The day's last call timed out; its retry is held back: what failed was the request."""
    monkeypatch.setitem(tushare_quota.INTERFACE_GRANTS, "us_tycr", InterfaceGrant(daily=2))

    def timing_out(payload: dict[str, Any]) -> bytes:
        raise TimeoutError("timed out")

    adapter = TushareContextAdapter("fixture-token", transport=timing_out)

    def retrying(api: str, params: Any, fields: Any, acquire: Any) -> Any:
        for _ in range(3):
            try:
                return acquire(None)
            except OSError:
                continue
        raise ContextRequestFailed("retries_exhausted")

    run, _ = submit(paths, "run")
    with in_run(paths, run), pytest.raises(ContextRequestFailed):
        adapter.acquire_scalars(
            paths,
            lambda: adapter.treasury_yields(
                start_date=date(2026, 8, 3), end_date=date(2026, 8, 28)
            ),
            request_wrapper=retrying,
            metric_ids=("UST10Y_NOMINAL_YIELD",),
        )

    with database_connection(paths.database) as connection:
        outcomes = {
            json.loads(row[1])["step"]: row[0]
            for row in connection.execute(
                "SELECT outcome, safe_metadata_json FROM retrieval_attempt "
                "WHERE metric_id='UST10Y_NOMINAL_YIELD'"
            )
        }
    assert outcomes == {"request": "source_failed"}


def test_an_http_error_is_no_answer_to_a_probe(paths: RuntimePaths, timeline: Timeline) -> None:
    first, _ = submit(paths, "first")
    with in_run(paths, first), pytest.raises(TushareRefused):
        call(paths, "major_news", refusal=DAILY_REFUSAL)
    second, _ = submit(paths, "second")
    sent: list[str] = []
    with in_run(paths, second):
        with pytest.raises(HTTPError):
            call(paths, "major_news", http_status=503, sent=sent)
        with pytest.raises(TushareCallNotAttempted):
            call(paths, "major_news", sent=sent)

    assert sent == ["major_news"]


def test_a_run_queued_before_the_refusal_still_probes(
    paths: RuntimePaths, timeline: Timeline
) -> None:
    first, _ = submit(paths, "first")
    queued, _ = submit(paths, "queued")
    with in_run(paths, first), pytest.raises(TushareRefused):
        call(paths, "major_news", refusal=DAILY_REFUSAL)

    with in_run(paths, queued):
        sent: list[str] = []
        call(paths, "major_news", sent=sent)

    assert sent == ["major_news"]


def test_the_refusal_s_words_are_kept_on_its_call_and_attempt(
    paths: RuntimePaths, timeline: Timeline
) -> None:
    run, _ = submit(paths, "run")
    with in_run(paths, run), pytest.raises(TushareRefused) as refused:
        call(paths, "major_news", refusal=DAILY_REFUSAL)

    outcome, details = capture_failure(refused.value)
    assert (outcome, details["classification"], details["quota"]) == (
        "source_failed",
        "rate_limited",
        "daily",
    )
    assert details["source_message"] == DAILY_REFUSAL
    with database_connection(paths.database) as connection:
        [(reason,)] = connection.execute(
            "SELECT rejection_reason FROM acquisition_request WHERE api_name='major_news'"
        ).fetchall()
    assert reason == f"tushare_daily_quota_refused: {DAILY_REFUSAL}"


@pytest.mark.parametrize("refusal", [MINUTE_REFUSAL, PERMISSION_REFUSAL])
def test_a_minute_refusal_or_a_missing_permission_does_not_stop_the_interface(
    paths: RuntimePaths, timeline: Timeline, refusal: str
) -> None:
    run, _ = submit(paths, "run")
    with in_run(paths, run):
        with pytest.raises(TushareRefused) as refused:
            call(paths, "fut_wsr", refusal=refusal)
        sent: list[str] = []
        call(paths, "fut_wsr", sent=sent)

    assert sent == ["fut_wsr"]
    assert "quota" not in capture_failure(refused.value)[1]


def test_a_stop_for_the_quota_does_not_hide_the_refusal_before_it(paths: RuntimePaths) -> None:
    run, accepted = submit(paths, "run")

    def at(seconds: int) -> datetime:
        return accepted + timedelta(seconds=seconds)

    repository = EvidenceRepository(paths.database)
    with processing_batch(run):
        repository.record_retrieval_attempt(
            metric_id="CN_FUTURES_WARRANTS",
            channel="tushare",
            outcome="source_failed",
            fetched_at=at(1),
            safe_metadata={"step": "response", "classification": "rate_limited"},
        )
        repository.record_retrieval_attempt(
            metric_id="CN_FUTURES_WARRANTS",
            channel="tushare",
            outcome=NOT_ATTEMPTED,
            fetched_at=at(2),
            safe_metadata={
                "step": "request",
                "condition": "tushare_daily_quota_refused",
                "request_sent": "false",
            },
        )

    failures = AcquisitionOutcomes(paths.database).for_batch(run).failures()

    assert [a.outcome for a in failures["CN_FUTURES_WARRANTS"]] == ["source_failed"]


def test_a_stop_for_the_quota_does_not_undo_the_success_before_it(paths: RuntimePaths) -> None:
    """A window's failure, then a day's refetch that succeeded, then a day held back."""
    run, accepted = submit(paths, "run")
    repository = EvidenceRepository(paths.database)

    def record(seconds: int, outcome: str, **metadata: str) -> None:
        repository.record_retrieval_attempt(
            metric_id="CN_FUTURES_WARRANTS",
            channel="tushare",
            outcome=outcome,
            fetched_at=accepted + timedelta(seconds=seconds),
            safe_metadata={"symbol": "CU", **metadata},
        )

    with processing_batch(run):
        record(1, "source_failed", step="response")
        record(2, "succeeded", step="structure", business_date="2026-08-28")
        record(
            3,
            NOT_ATTEMPTED,
            step="request",
            condition="tushare_daily_quota_exhausted",
            request_sent="false",
            business_date="2026-08-28",
        )

    assert AcquisitionOutcomes(paths.database).for_batch(run).failures() == {}
