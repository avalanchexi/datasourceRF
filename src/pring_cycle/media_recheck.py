"""Media values of one member that disagree, and the AI WebSearch recheck that settles them.

With no certified registered value, a member's news, media and AI values (each by its
page: its address, else its text's hash) that disagree beyond ADR-0033's tolerance are a
source conflict, kept out of the model input (``evidence.select_among``). The run asks AI
WebSearch first, once per family and period, sharing the gap's ledger key and time budget
(``retrieval.run_retrieval_cascade``). Its page-read values settle the conflict when all
agree with one side only, values within the tolerance of each other being one side: that
side is then selected. Else the member stays a conflict. Either verdict is kept with the
claims it judged and holds while they are exactly the member's contested claims: a new
claim asks again. The recheck's own claims are its evidence, never a side (ADR-0039).
Rows are only appended; they go once none of the claims they judged is kept.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from pring_cycle.batches import current_batch_id
from pring_cycle.evidence import (
    ClaimView,
    EvidenceValueState,
    MediaVerdict,
    news_page,
    value_conflict_reason,
)

if TYPE_CHECKING:
    from pring_cycle.runs import RunRecord
    from pring_cycle.runtime import RuntimePaths

Outcome = Literal["settled", "unsettled"]
SETTLED: Outcome = "settled"
UNSETTLED: Outcome = "unsettled"

MEDIA_RECHECK_SCHEMA = """
CREATE TABLE IF NOT EXISTS media_conflict_recheck (
    contested_hash TEXT PRIMARY KEY,
    metric_id TEXT NOT NULL,
    period_end TEXT NOT NULL,
    dimensions_json TEXT NOT NULL,
    contested_claim_ids_json TEXT NOT NULL,
    recheck_claim_ids_json TEXT NOT NULL,
    outcome TEXT NOT NULL CHECK (outcome IN ('settled', 'unsettled')),
    settled_value REAL,
    winning_claim_ids_json TEXT NOT NULL,
    losing_claim_ids_json TEXT NOT NULL,
    run_id TEXT NOT NULL,
    search_request_id TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    batch_id TEXT
);
CREATE TRIGGER IF NOT EXISTS media_conflict_recheck_no_update
BEFORE UPDATE ON media_conflict_recheck
BEGIN SELECT RAISE(ABORT, 'media_conflict_recheck_is_append_only'); END;
CREATE TRIGGER IF NOT EXISTS media_conflict_recheck_no_delete
BEFORE DELETE ON media_conflict_recheck
BEGIN SELECT RAISE(ABORT, 'media_conflict_recheck_is_append_only'); END;
"""


@dataclass(frozen=True)
class MediaConflict:
    """A member whose media values disagree, with the claims that do."""

    metric_id: str
    member: str
    dimensions: dict[str, str]
    period_end: str
    contested: tuple[ClaimView, ...]


@dataclass(frozen=True)
class MediaConflicts:
    """A gap's media conflicts: those to recheck, and the members a recheck left unsettled
    for the same claims, not asked again."""

    pending: tuple[MediaConflict, ...]
    unsettled: frozenset[str]


def contested_claims(
    claims: Sequence[ClaimView], verdicts: Sequence[MediaVerdict] = ()
) -> tuple[ClaimView, ...]:
    """The media claims of a point that disagree, when no certified value decides it, as
    ``evidence.select_among`` compares them: a recheck's own claims are evidence, not a
    side. Empty when they agree."""
    if any(
        claim.certification_status == "certified"
        and claim.quality_status == "validated"
        and claim.value_state is EvidenceValueState.REPORTED_VALUE
        and claim.value is not None
        for claim in claims
    ):
        return ()
    evidence = frozenset().union(*(verdict.evidence for verdict in verdicts))
    media = tuple(
        claim
        for claim in claims
        if news_page(claim.source_reference) is not None
        and claim.claim_id not in evidence
        and claim.quality_status == "validated"
        and claim.value_state is EvidenceValueState.REPORTED_VALUE
        and claim.value is not None
    )
    values = [claim.value for claim in media if claim.value is not None]
    return media if value_conflict_reason(values) is not None else ()


def decide(
    contested: Sequence[ClaimView], rechecked: Sequence[float]
) -> tuple[Outcome, float | None, tuple[str, ...], tuple[str, ...]]:
    """What a recheck's page-read values make of the contested claims, and the claims on
    each side (winning, losing). Settled when every value agrees, within ADR-0033's
    tolerance, with the same claims, those agree with each other, and others are left;
    unsettled when there is no value, they disagree, or they agree with both sides or
    neither."""
    agreeing = {
        frozenset(c.claim_id for c in contested if _agree(value, c.value)) for value in rechecked
    }
    if len(agreeing) != 1 or value_conflict_reason(list(rechecked)) is not None:
        return UNSETTLED, None, (), ()
    [winners] = agreeing
    winning = [c for c in contested if c.claim_id in winners]
    losing = [c for c in contested if c.claim_id not in winners]
    values = [c.value for c in winning if c.value is not None]
    if not winning or not losing or value_conflict_reason(values) is not None:
        return UNSETTLED, None, (), ()
    return (
        SETTLED,
        rechecked[0],
        tuple(sorted(winners)),
        tuple(sorted(c.claim_id for c in losing)),
    )


def _agree(value: float, other: float | None) -> bool:
    return other is not None and value_conflict_reason([value, other]) is None


def media_conflicts(paths: RuntimePaths, run: RunRecord) -> MediaConflicts:
    """The media conflicts of the run's gap among the points its period can adopt."""
    from pring_cycle.runs import member_key
    from pring_cycle.search_evidence import ModelInputSelector

    scope = run.retrieval_scope
    assert scope is not None
    selector = ModelInputSelector(paths, run)
    pending: list[MediaConflict] = []
    unsettled: set[str] = set()
    for metric_id in dict.fromkeys(scope.metric_ids):
        for point in selector.adoptable(metric_id, scope.period):
            if point.selection_status != "conflicted":
                continue
            contested = contested_claims(point.claims, point.verdicts)
            if not contested:
                continue
            member = member_key(metric_id, point.dimensions)
            judged = frozenset(c.claim_id for c in contested)
            verdict = next((v for v in point.verdicts if v.contested == judged), None)
            if verdict is None:
                pending.append(
                    MediaConflict(metric_id, member, point.dimensions, point.period_end, contested)
                )
            elif not verdict.winners:
                unsettled.add(member)
    return MediaConflicts(tuple(pending), frozenset(unsettled))


def record_rechecks(
    database: Path,
    conflicts: Iterable[MediaConflict],
    rechecked_claim_ids: Sequence[str],
    *,
    run_id: str,
    search_request_id: str,
) -> None:
    """Keep what one answer's adopted claims made of each conflict it was asked about."""
    from pring_cycle.evidence import EvidenceRepository
    from pring_cycle.storage import database_connection

    conflicts = tuple(conflicts)
    if not conflicts:
        return
    with database_connection(database) as connection:
        adopted = connection.execute(
            "SELECT claim_id, metric_id, period_end, dimensions_json, value FROM source_claim "
            "WHERE claim_id IN (SELECT value FROM json_each(?)) ORDER BY claim_id",
            (json.dumps(list(rechecked_claim_ids)),),
        ).fetchall()
        now = datetime.now(UTC).isoformat()
        for conflict in conflicts:
            recheck = [
                (str(claim_id), float(value))
                for claim_id, metric_id, period_end, dimensions_json, value in adopted
                if metric_id == conflict.metric_id
                and period_end == conflict.period_end
                and json.loads(dimensions_json) == conflict.dimensions
                and value is not None
            ]
            outcome, value, winning, losing = decide(conflict.contested, [v for _c, v in recheck])
            contested = sorted(c.claim_id for c in conflict.contested)
            connection.execute(
                "INSERT OR IGNORE INTO media_conflict_recheck VALUES "
                "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    _set_hash(contested),
                    conflict.metric_id,
                    conflict.period_end,
                    json.dumps(conflict.dimensions, sort_keys=True),
                    json.dumps(contested),
                    json.dumps(sorted(c for c, _v in recheck)),
                    outcome,
                    value,
                    json.dumps(list(winning)),
                    json.dumps(list(losing)),
                    run_id,
                    search_request_id,
                    now,
                    current_batch_id(),
                ),
            )
    # Repositories read their series again with the verdicts.
    EvidenceRepository(database).forget_selections()


def load_media_verdicts(connection: sqlite3.Connection) -> dict[str, tuple[MediaVerdict, ...]]:
    """Each recorded verdict, under every claim it judged or took as evidence."""
    if (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='media_conflict_recheck'"
        ).fetchone()
        is None
    ):
        return {}
    by_claim: dict[str, list[MediaVerdict]] = {}
    for contested, evidence, winning in connection.execute(
        "SELECT contested_claim_ids_json, recheck_claim_ids_json, winning_claim_ids_json "
        "FROM media_conflict_recheck"
    ):
        verdict = MediaVerdict(
            frozenset(json.loads(str(contested))),
            frozenset(json.loads(str(evidence))),
            frozenset(json.loads(str(winning))),
        )
        for claim_id in verdict.contested | verdict.evidence:
            by_claim.setdefault(claim_id, []).append(verdict)
    return {claim_id: tuple(verdicts) for claim_id, verdicts in by_claim.items()}


def _set_hash(claim_ids: Iterable[str]) -> str:
    return hashlib.sha256(json.dumps(sorted(claim_ids)).encode()).hexdigest()
