"""How a metric's acquisition attempts turned out: read and explained in one place.

Two views over the recorded attempts. ``latest`` is the attempt a target day's cutoff
sees: the newest recorded at or before it, optionally for a period, target day or catalog.
``for_batch`` is what one processing batch acquired: the attempts it made and the
responses it had rejected by their structure check.

Only what was recorded is read; no stage an attempt did not record is inferred. What an
outcome means to a consumer -- a gap category, a release state, a P2 label -- stays with
that consumer.

Kept as they are, and so documented here: ``latest`` orders by exact time and then
attempt id, and may return the same target day's attempt from an earlier batch (it shows
the latest acquisition honestly, with its recorded time); the batch view attributes an
attempt by time (from the run's acceptance to the next run's), orders by recorded time and
insertion, and does not filter by catalog, nor does the LPR release calendar's ``latest``;
warrant symbols are grouped without their day, and several failing symbols of one metric
collapse to one reason; a rejection a later delivery of the batch resolved is still listed.

The target-day view reads each recorded detail as text; the batch view reads them as
recorded, so a detail recorded as null is absent there.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from pring_cycle.storage import database_connection

# A registered source that did not answer, and one whose answer was refused.
SOURCE_FAILED_OUTCOMES = frozenset({"source_failed", "adapter_failed", "missing_credentials"})
VALIDATION_FAILED_OUTCOMES = frozenset({"validation_failed"})
# The outcomes a registered source's acquisition records: the last one a batch recorded for
# a metric says whether that source failed it (gap sources #04).
_ACQUISITION_OUTCOMES = (
    SOURCE_FAILED_OUTCOMES
    | VALIDATION_FAILED_OUTCOMES
    | {"verified_candidate", "partial_validation", "missing_fields", "missing_values"}
)


@dataclass(frozen=True)
class AttemptView:
    """One recorded acquisition attempt, its recorded details typed.

    ``metadata`` keeps the details as recorded; each property reads one as text.
    """

    attempt_id: str
    metric_id: str
    channel: str
    outcome: str
    recorded_at: datetime
    metadata: Mapping[str, object] = field(default_factory=dict)

    def _get(self, key: str) -> str | None:
        return str(self.metadata[key]) if key in self.metadata else None

    @property
    def definition_version(self) -> str | None:
        return self._get("definition_version")

    @property
    def period(self) -> str | None:
        return self._get("period")

    @property
    def target_business_date(self) -> str | None:
        return self._get("target_business_date")

    @property
    def symbol(self) -> str | None:
        return self._get("symbol")

    @property
    def condition(self) -> str | None:
        return self._get("condition")

    @property
    def reason(self) -> str | None:
        return self._get("reason")

    @property
    def error_type(self) -> str | None:
        return self._get("error_type")

    @property
    def stage(self) -> str | None:
        return self._get("stage")

    @property
    def request_sent(self) -> bool | None:
        """Whether a request went out, as recorded ("true" or "false"); else unknown."""
        value = self._get("request_sent")
        return False if value == "false" else True if value == "true" else None

    @property
    def rejected_fields(self) -> str | None:
        return self._get("rejected_fields")

    @property
    def acquisition_ids(self) -> tuple[str, ...]:
        value = self._get("acquisition_ids")
        return tuple(value.split(",")) if value is not None else ()

    @property
    def latest_source_period(self) -> str | None:
        return self._get("latest_source_period")

    @property
    def source_timezone(self) -> str | None:
        return self._get("source_timezone")

    @property
    def release_date(self) -> str | None:
        return self._get("release_date")

    @property
    def next_release_date(self) -> str | None:
        return self._get("next_release_date")

    @property
    def release_timezone(self) -> str | None:
        return self._get("release_timezone")

    @property
    def detail(self) -> str:
        """Why it turned out so: the recorded reason, condition or error, else the outcome.

        Read as recorded: an empty or null detail gives way to the next.
        """
        recorded = self.metadata
        return str(
            recorded.get("reason")
            or recorded.get("condition")
            or recorded.get("error_type")
            or self.outcome
        )


@dataclass(frozen=True)
class StructureRejection:
    """A response of the batch its structure check refused (gate ③)."""

    metric_ids: tuple[str, ...]
    api_name: str
    reason: str | None


class BatchAcquisition:
    """What one processing batch acquired, by the attempts and receipts it recorded."""

    def __init__(self, database: Path, run_id: str) -> None:
        self._database = database
        self._run_id = run_id

    def failures(self) -> dict[str, AttemptView]:
        """Per metric, the batch's last attempt of a registered source, when it failed.

        Each warrant symbol is acquired on its own, so one symbol's failure stands though
        another succeeded after it; alternative families (an API, then its page) still let
        a later success clear an earlier failure. One failing symbol stands for the metric.
        """
        with database_connection(self._database) as connection:
            if not connection.execute(
                "SELECT 1 FROM sqlite_master WHERE name='retrieval_attempt'"
            ).fetchone():
                return {}
            run = connection.execute(
                "SELECT accepted_at, target_business_date FROM parent_run WHERE run_id=?",
                (self._run_id,),
            ).fetchone()
            if run is None:
                return {}
            # One Worker runs one batch at a time: this run's attempts fall between its
            # acceptance and the next run's.
            following = connection.execute(
                "SELECT min(accepted_at) FROM parent_run WHERE accepted_at > ?", (run[0],)
            ).fetchone()[0]
            rows = connection.execute(
                "SELECT retrieval_attempt_id, metric_id, channel, outcome, fetched_at, "
                "safe_metadata_json FROM retrieval_attempt "
                "WHERE fetched_at >= ? AND (? IS NULL OR fetched_at < ?) "
                "AND outcome IN (SELECT value FROM json_each(?)) ORDER BY fetched_at, rowid",
                (run[0], following, following, json.dumps(sorted(_ACQUISITION_OUTCOMES))),
            ).fetchall()
        latest: dict[tuple[str, object], AttemptView] = {}
        for row in rows:
            attempt = _view(row)
            if attempt.metadata.get("target_business_date", run[1]) == run[1]:
                latest[(attempt.metric_id, attempt.metadata.get("symbol"))] = attempt
        return {
            metric_id: attempt
            for (metric_id, _symbol), attempt in latest.items()
            if attempt.outcome in SOURCE_FAILED_OUTCOMES | VALIDATION_FAILED_OUTCOMES
        }

    def structure_rejections(self) -> tuple[StructureRejection, ...]:
        """The batch's responses refused by their structure check; a skipped one is not."""
        with database_connection(self._database) as connection:
            rows = connection.execute(
                """
                SELECT a.metric_ids_json, r.api_name, r.rejection_reason
                FROM full_run_acquisition a JOIN acquisition_request r USING (acquisition_id)
                WHERE a.run_id=? AND r.structure_check='rejected'
                """,
                (self._run_id,),
            ).fetchall()
        return tuple(
            StructureRejection(
                tuple(json.loads(metric_ids_json or "[]")),
                str(api_name),
                None if reason is None else str(reason),
            )
            for metric_ids_json, api_name, reason in rows
        )


class AcquisitionOutcomes:
    def __init__(self, database: Path) -> None:
        self._database = database

    def latest(
        self,
        metric_id: str,
        *,
        as_of: datetime,
        definition_version: str | None = None,
        target_business_date: str | None = None,
        period: str | None = None,
    ) -> AttemptView | None:
        """The newest attempt recorded at or before ``as_of``, matching what is given."""
        if as_of.tzinfo is None:
            raise ValueError("retrieval_attempt_as_of_must_be_timezone_aware")
        with database_connection(self._database) as connection:
            rows = connection.execute(
                """
                SELECT retrieval_attempt_id, metric_id, channel, outcome, fetched_at,
                    safe_metadata_json
                FROM retrieval_attempt
                WHERE metric_id=? AND julianday(fetched_at) <= julianday(?)
                """,
                (metric_id, as_of.astimezone(UTC).isoformat()),
            ).fetchall()
        # julianday rounds to the millisecond; the exact time decides. A candidate's details
        # are read only once it is reached.
        ordered = sorted(
            rows,
            key=lambda row: (_recorded_at(row[4]), str(row[0])),
            reverse=True,
        )
        for row in ordered:
            if _recorded_at(row[4]) > as_of:
                continue
            attempt = _view(row)
            if period is not None and attempt.period != period:
                continue
            if target_business_date is not None and (
                attempt.target_business_date != target_business_date
            ):
                continue
            if definition_version is not None and attempt.definition_version != definition_version:
                continue
            return attempt
        return None

    def for_batch(self, run_id: str) -> BatchAcquisition:
        return BatchAcquisition(self._database, run_id)


def _recorded_at(value: object) -> datetime:
    return datetime.fromisoformat(str(value)).astimezone(UTC)


def _view(row: tuple[object, ...]) -> AttemptView:
    attempt_id, metric_id, channel, outcome, fetched_at, metadata_json = row
    return AttemptView(
        attempt_id=str(attempt_id),
        metric_id=str(metric_id),
        channel=str(channel),
        outcome=str(outcome),
        recorded_at=_recorded_at(fetched_at),
        metadata={str(key): value for key, value in json.loads(str(metadata_json)).items()},
    )
