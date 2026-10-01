"""How a metric's acquisition attempts turned out: read and explained in one place.

Two views over the recorded attempts. ``latest`` is the attempt a target day's cutoff
sees: the newest recorded at or before it, optionally for a period, target day or catalog.
``for_batch`` is what one processing batch acquired: the attempts it made and the
responses it had rejected by their structure check.

Only what was recorded is read; no stage an attempt did not record is inferred. What an
outcome means to a consumer -- a gap category, a release state, a P2 label -- stays with
that consumer.

Both views order attempts by their exact recorded time, then by writing order, and keep
to a catalog: ``latest`` to the one asked for, the batch view to its run's model's, though
it keeps an attempt that names no catalog and reads them all when the model is not on
record (ticket 19). The
batch view takes an attempt by the run it names, and one that names none (recorded before
ticket 17) by time, from the run's acceptance to the next run's. Kept as they are, and so
documented here: ``latest`` may return the same target day's attempt from an earlier batch
(it shows the latest acquisition honestly, with its recorded time); warrant symbols are
grouped without their day, and several failing symbols of one metric collapse to one
reason; a rejection a later delivery of the batch resolved is still listed.

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

# How an acquisition turned out, as its adapter records it where each step ends (ticket 18).
# The outcome is the result; the details say at which step, why, and how much was delivered.
SUCCEEDED = "succeeded"
SOURCE_FAILED = "source_failed"  # the source did not answer, or answered with a failure
STRUCTURE_REJECTED = "structure_rejected"  # the response failed its structure check
INGEST_REJECTED = "ingest_rejected"  # the registered contract refused the checked values
LOCAL_FAILED = "local_failed"  # this system failed handling it
NOT_ATTEMPTED = "not_attempted"  # no request went out (a credential not configured)
STEPS = frozenset({"request", "response", "structure", "ingest", "local"})
# What a successful delivery held of what was asked: all of it, some members missing (named
# in ``missing_members``), nothing new to add since all was held, or nothing at all.
COMPLETENESS = frozenset({"complete", "partial_members_missing", "nothing_new", "source_empty"})

# A registered source that did not answer, and one whose answer was refused. The outcomes
# written before ticket 18 are still read as they were. A request not attempted is a
# failure only for want of a credential (``failed_to_acquire``); one a budget held back,
# or a release not yet due, is not.
SOURCE_FAILED_OUTCOMES = frozenset(
    {SOURCE_FAILED, LOCAL_FAILED, "adapter_failed", "missing_credentials"}
)
VALIDATION_FAILED_OUTCOMES = frozenset({STRUCTURE_REJECTED, INGEST_REJECTED, "validation_failed"})
# The outcomes a registered source's acquisition records: the last one a batch recorded for
# a metric says whether that source failed it (gap sources #04).
_ACQUISITION_OUTCOMES = (
    SOURCE_FAILED_OUTCOMES
    | VALIDATION_FAILED_OUTCOMES
    | {
        SUCCEEDED,
        NOT_ATTEMPTED,
        "verified_candidate",
        "partial_validation",
        "missing_fields",
        "missing_values",
    }
)


def failed_to_acquire(attempt: AttemptView) -> bool:
    """Whether the attempt is a registered source failing to deliver: no answer, a refused
    one, this system's failure, or no request for want of a credential."""
    if attempt.outcome == NOT_ATTEMPTED:
        return (attempt.condition or "").endswith("_not_configured")
    return attempt.outcome in SOURCE_FAILED_OUTCOMES | VALIDATION_FAILED_OUTCOMES


def attempt_details(
    *,
    step: str,
    completeness: str | None = None,
    external_code: str | None = None,
    rule_reason: str | None = None,
    error_type: str | None = None,
    missing_members: tuple[str, ...] = (),
    **details: str,
) -> dict[str, str]:
    """The details an attempt records of how it turned out, in this module's words.

    ``external_code`` is the source's own (an HTTP status, a TuShare code); ``rule_reason``
    the local rule that refused it; ``error_type`` the exception that ended it.
    """
    if step not in STEPS:
        raise ValueError("acquisition_step_unknown")
    if completeness is not None and completeness not in COMPLETENESS:
        raise ValueError("acquisition_completeness_unknown")
    recorded = {
        "step": step,
        "completeness": completeness,
        "external_code": external_code,
        "rule_reason": rule_reason,
        "error_type": error_type,
        "missing_members": (
            json.dumps(sorted(set(missing_members)), ensure_ascii=False)
            if missing_members
            else None
        ),
    }
    return {**details, **{key: value for key, value in recorded.items() if value is not None}}


def capture_failure(error: Exception) -> tuple[str, dict[str, str]]:
    """How a call through the receipt store ended, from where in it the error arose.

    The receipt store marks the step (``acquisition.failed_step``); an adapter's rules on
    the answered rows, after the call, have none. Before a request went out, it was not
    attempted; an answer that was itself a failure, or no answer, is the source's; the
    answer's check refusing it is a structure rejection; anything else, storing it included,
    this system's own failure.
    """
    from urllib.error import HTTPError

    from pring_cycle.acquisition import SourceFailed, failed_step, refused_by_parse

    step = failed_step(error)
    reason = str(error)[:300]
    error_type = type(error).__name__
    if isinstance(error, HTTPError):
        return SOURCE_FAILED, attempt_details(
            step="response", external_code=str(error.code), error_type=error_type, reason=reason
        )
    if isinstance(error, SourceFailed):
        return SOURCE_FAILED, attempt_details(
            step="response",
            external_code=error.external_code,
            error_type=error_type,
            reason=reason,
        )
    if step == "start":
        return NOT_ATTEMPTED, attempt_details(
            step="request", condition=reason, error_type=error_type, request_sent="false"
        )
    if step in {"store", "normalize"}:
        return LOCAL_FAILED, attempt_details(step="local", error_type=error_type, reason=reason)
    if isinstance(error, OSError) and step in {None, "request"}:
        return SOURCE_FAILED, attempt_details(step="request", error_type=error_type, reason=reason)
    if refused_by_parse(error, step) or (step is None and isinstance(error, ValueError)):
        return STRUCTURE_REJECTED, attempt_details(
            step="structure", rule_reason=reason, error_type=error_type
        )
    return LOCAL_FAILED, attempt_details(step="local", error_type=error_type, reason=reason)


def ingest_failure(error: Exception) -> tuple[str, dict[str, str]]:
    """How storing checked values ended: the contract refusing them, or this system failing."""
    if isinstance(error, ValueError):
        return INGEST_REJECTED, attempt_details(
            step="ingest", rule_reason=str(error)[:300], error_type=type(error).__name__
        )
    return LOCAL_FAILED, attempt_details(
        step="ingest", error_type=type(error).__name__, reason=str(error)[:300]
    )


@dataclass(frozen=True)
class AttemptView:
    """One recorded acquisition attempt, its recorded details typed.

    ``metadata`` keeps the details as recorded; each property reads one as text, but
    ``missing_members`` (a tuple), ``acquisition_ids`` (a tuple) and ``request_sent``.
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
    def step(self) -> str | None:
        return self._get("step")

    @property
    def completeness(self) -> str | None:
        return self._get("completeness")

    @property
    def external_code(self) -> str | None:
        return self._get("external_code")

    @property
    def rule_reason(self) -> str | None:
        return self._get("rule_reason")

    @property
    def missing_members(self) -> tuple[str, ...]:
        value = self._get("missing_members")
        return tuple(json.loads(value)) if value is not None else ()

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
            or recorded.get("rule_reason")
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
                "SELECT accepted_at, target_business_date, model_version_id FROM parent_run "
                "WHERE run_id=?",
                (self._run_id,),
            ).fetchone()
            if run is None:
                return {}
            catalog = _catalog_version(self._database, str(run[2]))
            # One Worker runs one batch at a time: an attempt that names no run (recorded
            # before ticket 17, or outside any batch) falls between its run's acceptance and
            # the next run's.
            following = connection.execute(
                "SELECT min(accepted_at) FROM parent_run WHERE accepted_at > ?", (run[0],)
            ).fetchone()[0]
            # An attempt names its run (ticket 17); one recorded before that is the batch's by
            # time. Either way the SQL only narrows what Python decides.
            rows = connection.execute(
                "SELECT rowid, retrieval_attempt_id, metric_id, channel, outcome, fetched_at, "
                "safe_metadata_json FROM retrieval_attempt "
                "WHERE (json_extract(safe_metadata_json, '$.run_id') = ? "
                "OR (fetched_at >= ? AND (? IS NULL OR fetched_at < ?))) "
                "AND outcome IN (SELECT value FROM json_each(?))",
                (
                    self._run_id,
                    run[0],
                    following,
                    following,
                    json.dumps(sorted(_ACQUISITION_OUTCOMES)),
                ),
            ).fetchall()
        latest: dict[tuple[str, object], AttemptView] = {}
        for row in sorted(rows, key=_recorded_order):
            attempt = _view(row[1:])
            owner = attempt.metadata.get("run_id")
            if owner is not None and owner != self._run_id:
                continue
            # The run's own catalog only; an attempt that names none predates the field.
            if catalog is not None and attempt.definition_version not in {None, catalog}:
                continue
            if attempt.metadata.get("target_business_date", run[1]) == run[1]:
                latest[(attempt.metric_id, attempt.metadata.get("symbol"))] = attempt
        return {
            metric_id: attempt
            for (metric_id, _symbol), attempt in latest.items()
            if failed_to_acquire(attempt)
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
                SELECT rowid, retrieval_attempt_id, metric_id, channel, outcome, fetched_at,
                    safe_metadata_json
                FROM retrieval_attempt
                WHERE metric_id=? AND julianday(fetched_at) <= julianday(?)
                """,
                (metric_id, as_of.astimezone(UTC).isoformat()),
            ).fetchall()
        # julianday rounds to the millisecond; the exact time decides, then writing order. A
        # candidate's details are read only once it is reached.
        for row in sorted(rows, key=_recorded_order, reverse=True):
            if _recorded_at(row[5]) > as_of:
                continue
            attempt = _view(row[1:])
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


def _recorded_order(row: tuple[object, ...]) -> tuple[datetime, int]:
    """A row (rowid first, recorded time sixth) by its exact time, then by writing order."""
    return _recorded_at(row[5]), int(str(row[0]))


def _catalog_version(database: Path, model_version_id: str) -> str | None:
    """The metric catalog a run's model reads, when the model is on record."""
    from pring_cycle.models import ModelRepository

    try:
        manifest = ModelRepository(database).manifest(model_version_id)
    except (LookupError, ValueError):
        return None
    version = manifest.get("metric_catalog_version")
    return str(version) if version is not None else None


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
