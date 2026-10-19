from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from pring_cycle.batches import add_batch_columns, current_batch_id
from pring_cycle.bond_attribution import DRIVERS as ATTRIBUTION_DRIVERS
from pring_cycle.confirmation import DIMENSIONS as CONFIRMATION_DIMENSIONS
from pring_cycle.confirmation import OUTPUT_STRUCTURE as CONFIRMATION_STRUCTURE
from pring_cycle.confirmation import RELATIONS as CONFIRMATION_RELATIONS
from pring_cycle.macro_judgement import validate as validate_macro_judgement
from pring_cycle.metric_contracts import EFFECTIVE_UNTIL_CHANGED_METRICS
from pring_cycle.publication_corrections import (
    PUBLICATION_CORRECTION_SCHEMA,
    publication_corrections,
    record_publication_corrections,
)
from pring_cycle.source_adapters import CORE_API_IDENTITIES
from pring_cycle.source_contract_review import require_stored_model_source_contract
from pring_cycle.storage import database_connection, ensure_wal

ANALYTICAL_DATASETS = (
    "cycle_overview",
    "core_assets",
    "macro",
    "inventory",
    "release_calendar",
    "stage_history",
)
INVENTORY_CARD_NAMES = (
    "orders_inventory_gap",
    "materials_finished_goods",
    "physical_inventory",
    "inventory_sales_turnover",
    "prices_profits",
    "capacity",
    "credit_physical_inventory",
)
_FORMAL_STAGE_BY_STATES = {
    ("bull", "bear", "bear"): "stage_i",
    ("bull", "bull", "bear"): "stage_ii",
    ("bull", "bull", "bull"): "stage_iii",
    ("bear", "bull", "bull"): "stage_iv",
    ("bear", "bear", "bull"): "stage_v",
    ("bear", "bear", "bear"): "stage_vi",
}


@dataclass(frozen=True)
class ProjectionEnvelope:
    projection_set_id: str
    system_as_of: datetime
    target_business_date: str
    evidence_snapshot_id: str
    model_version_id: str
    trend_rule_version: str
    evidence_window_start: str
    evidence_window_end: str
    generated_at: datetime
    completeness: str
    refresh_status: str
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class ProjectionSet:
    envelope: ProjectionEnvelope
    datasets: dict[str, dict[str, object]]
    # Read with it: whether it was computed on a value read for the wrong period, and the
    # projections that correct it or that it corrects (audit 06).
    corrections: dict[str, Any] = field(default_factory=dict)


# A day's summaries, latest first: by cutoff; at one cutoff (a resumed run's), one a
# correction corrects goes after it, and a correction before a summary; then by id.
_NEWER_FIRST = """
    PARTITION BY target_business_date
    ORDER BY julianday(system_as_of) DESC,
        assessment_id IN (
            SELECT json_extract(document_json, '$.corrects.assessment_id') FROM p0_assessment
            WHERE json_extract(document_json, '$.corrects.assessment_id') IS NOT NULL
        ) ASC,
        json_extract(document_json, '$.corrects') IS NOT NULL DESC,
        assessment_id DESC
"""


class ProjectionSetRepository:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def producer_run_id(self, projection_set_id: str) -> str | None:
        """The writing batch also owns backfilled days, not only the run's target day."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT batch_id FROM projection_set WHERE projection_set_id=?",
                (projection_set_id,),
            ).fetchone()
        return str(row[0]) if row and row[0] is not None else None

    @classmethod
    def create(cls, database_path: Path) -> ProjectionSetRepository:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        repository = cls(database_path)
        with repository._connect() as connection:
            connection.executescript(_PROJECTION_SCHEMA)
            connection.executescript(_P0_ASSESSMENT_SCHEMA)
            connection.executescript(PUBLICATION_CORRECTION_SCHEMA)
            connection.executescript(UNCORRECTABLE_DAY_SCHEMA)
            add_batch_columns(connection)
        return repository

    def publish(
        self,
        envelope: ProjectionEnvelope,
        datasets: dict[str, dict[str, object]],
        *,
        fail_before_pointer: bool = False,
        p0_assessment: dict[str, object] | None = None,
        as_current: bool = True,
    ) -> None:
        """Store the set; ``as_current`` lets it take the current pointer, never back in time.

        A backfilled day's set is kept as history only: the page stays on the last whole
        set until the run publishes its target (ADR-0008). A set already stored under its id
        is not written again; with ``as_current`` it may still take the pointer. A new set
        marks the kept ones computed on a value read for the wrong period, and corrects its
        day's (audit 06).
        """
        _validate_projection(envelope, datasets)
        envelope_json = _canonical_json(_envelope_document(envelope))
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            require_stored_model_source_contract(connection, envelope.model_version_id)
            stored = connection.execute(
                "SELECT 1 FROM projection_set WHERE projection_set_id=?",
                (envelope.projection_set_id,),
            ).fetchone()
            if stored is None:
                self._insert_set(connection, envelope, envelope_json, datasets)
                record_publication_corrections(
                    connection, envelope.projection_set_id, envelope.target_business_date
                )
            if fail_before_pointer:
                connection.rollback()
                raise RuntimeError("injected_projection_failure")
            if p0_assessment is not None:
                self._insert_p0_assessment(connection, p0_assessment)
            if as_current:
                self._take_current(connection, envelope)

    def _insert_set(
        self,
        connection: sqlite3.Connection,
        envelope: ProjectionEnvelope,
        envelope_json: str,
        datasets: dict[str, dict[str, object]],
    ) -> None:
        connection.execute(
            "INSERT INTO projection_set(projection_set_id, envelope_json, batch_id) "
            "VALUES (?, ?, ?)",
            (envelope.projection_set_id, envelope_json, current_batch_id()),
        )
        for dataset_name in ANALYTICAL_DATASETS:
            connection.execute(
                """
                INSERT INTO analytical_dataset(
                    projection_set_id, dataset_name, document_json, batch_id
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    envelope.projection_set_id,
                    dataset_name,
                    _canonical_json(datasets[dataset_name]),
                    current_batch_id(),
                ),
            )

    def _take_current(self, connection: sqlite3.Connection, envelope: ProjectionEnvelope) -> None:
        current_row = connection.execute(
            """
            SELECT projection_set.envelope_json
            FROM current_projection
            JOIN projection_set USING (projection_set_id)
            WHERE current_projection.singleton=1
            """
        ).fetchone()
        current_target = None
        if current_row is not None:
            current_document = json.loads(str(current_row["envelope_json"]))
            current_target = str(current_document["target_business_date"])
        if current_target is None or envelope.target_business_date >= current_target:
            connection.execute(
                """
                INSERT INTO current_projection(singleton, projection_set_id, batch_id)
                VALUES (1, ?, ?)
                ON CONFLICT(singleton) DO UPDATE
                SET projection_set_id=excluded.projection_set_id, batch_id=excluded.batch_id
                """,
                (envelope.projection_set_id, current_batch_id()),
            )

    def prepare_p0_assessment(self, document: dict[str, object]) -> dict[str, object]:
        normalized = _canonical_json(document)
        assessment_id = "p0-assessment-" + hashlib.sha256(normalized.encode()).hexdigest()[:20]
        return {"assessment_id": assessment_id, **document}

    def record_p0_assessment(self, assessment: dict[str, object]) -> str:
        with self._connect() as connection:
            self._insert_p0_assessment(connection, assessment)
        return str(assessment["assessment_id"])

    def p0_assessment(self, assessment_id: str) -> dict[str, object]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT document_json FROM p0_assessment WHERE assessment_id=?",
                (assessment_id,),
            ).fetchone()
        if row is None:
            raise LookupError("p0_assessment_not_found")
        value = json.loads(str(row["document_json"]))
        if not isinstance(value, dict):
            raise ValueError("p0_assessment_document_invalid")
        return {str(key): item for key, item in value.items()}

    def stage_history(self, *, through: str | None = None) -> tuple[dict[str, object], ...]:
        """Each day's latest assessment in day order; ``through`` keeps those on or before it.

        A day summarized again, by a re-run or as a correction (ticket 07), is listed once, at
        its latest summary; the earlier ones stay stored, read by their id. A correction made
        at the cutoff of the summary it corrects (a resumed run's) is the later of the two.
        """
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT document_json FROM (
                    SELECT target_business_date, document_json,
                           row_number() OVER ({_NEWER_FIRST}) AS newer
                    FROM p0_assessment WHERE ? IS NULL OR target_business_date <= ?
                )
                WHERE newer = 1
                ORDER BY target_business_date
                """,
                (through, through),
            ).fetchall()
        return tuple(
            {str(key): value for key, value in json.loads(str(row["document_json"])).items()}
            for row in rows
        )

    def corrected_days(
        self, batch_id: str, reason: str, *, scope: str | None = None
    ) -> tuple[str, ...]:
        """The days the batch summarized again as corrections for ``reason`` (ticket 07),
        read from what it stored, so a resumed run counts those its first attempt made.

        ``scope`` keeps those corrected whole or on their cores only (ticket 08); a
        correction stating none was made whole.
        """
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT target_business_date FROM p0_assessment
                WHERE batch_id = ? AND json_extract(document_json, '$.corrects.reason') = ?
                    AND (? IS NULL OR coalesce(
                        json_extract(document_json, '$.corrects.scope'), 'whole_day'
                    ) = ?)
                ORDER BY target_business_date
                """,
                (batch_id, reason, scope, scope),
            ).fetchall()
        return tuple(str(row[0]) for row in rows)

    def context_details_held(self, projection_set_id: str) -> bool:
        """Whether every source claim the set's context cites is still held: those its rows
        show, are derived from or compare with, and those its confirmation read. One gone
        has left retention, and the context cannot be summarized again as it was (ticket
        08). A derived row's own identity is no claim, and the cores' own prices are no
        context detail: retention keeps none for being cited."""
        with self._connect() as connection:
            documents = [
                json.loads(row[0])
                for row in connection.execute(
                    "SELECT document_json FROM analytical_dataset "
                    "WHERE projection_set_id = ? AND dataset_name IN ('macro', 'inventory')",
                    (projection_set_id,),
                )
            ]
            context, cores = _citations(documents)
            # The model's inputs gather every row's, the cores' own among them; those named
            # only there, as the price consistency's, are cited all the same.
            inputs = {
                str(item)
                for document in documents
                for item in document.get("model_input_observation_version_ids") or ()
            }
            claims = sorted((context | (inputs - cores)) - _derived_identities(documents))
            for start in range(0, len(claims), 500):
                chunk = claims[start : start + 500]
                (held,) = connection.execute(
                    "SELECT count(*) FROM source_claim "
                    f"WHERE claim_id IN ({','.join('?' * len(chunk))})",
                    chunk,
                ).fetchone()
                if held < len(chunk):
                    return False
        return True

    def record_uncorrectable(
        self, day: str, *, basis: str, corrected_assessment_id: str, reason: str
    ) -> None:
        """Record that ``day``'s summary cannot be corrected on ``basis``, and why: no later
        run on the same basis tries it again (ticket 08). Recorded once."""
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO uncorrectable_day(
                    target_business_date, core_history_basis, corrected_assessment_id,
                    reason, recorded_at, batch_id
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    day,
                    basis,
                    corrected_assessment_id,
                    reason,
                    datetime.now(UTC).isoformat(),
                    current_batch_id(),
                ),
            )

    def uncorrectable_days(
        self, *, basis: str | None = None, batch_id: str | None = None
    ) -> tuple[tuple[str, str], ...]:
        """Each day recorded as uncorrectable, with why, in day order: on ``basis``, or by
        the batch ``batch_id``, when given."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT target_business_date, reason FROM uncorrectable_day
                WHERE (? IS NULL OR core_history_basis = ?) AND (? IS NULL OR batch_id = ?)
                ORDER BY target_business_date
                """,
                (basis, basis, batch_id, batch_id),
            ).fetchall()
        return tuple((str(row[0]), str(row[1])) for row in rows)

    def last_confirmed_stage(self, *, on_or_before: str) -> str | None:
        """The stage of the latest day on or before ``on_or_before`` that had one.

        Each day counts by its latest summary, as ``stage_history`` lists it: a day
        summarized again without a stage no longer has one.
        """
        date.fromisoformat(on_or_before)
        with self._connect() as connection:
            row = connection.execute(
                f"""
                SELECT document_json FROM (
                    SELECT event_kind, target_business_date, document_json,
                           row_number() OVER ({_NEWER_FIRST}) AS newer
                    FROM p0_assessment WHERE target_business_date <= ?
                )
                WHERE newer = 1 AND event_kind='formal'
                ORDER BY target_business_date DESC
                LIMIT 1
                """,
                (on_or_before,),
            ).fetchone()
        if row is None:
            return None
        document = json.loads(str(row["document_json"]))
        value = document.get("current_stage")
        return str(value) if value is not None else None

    def create_gap_notice(
        self,
        assessment_id: str,
        *,
        client_request_id: str,
    ) -> dict[str, object]:
        if not client_request_id:
            raise ValueError("gap_notice_request_id_required")
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT document_json FROM data_gap_notice WHERE client_request_id=?",
                (client_request_id,),
            ).fetchone()
            if existing is not None:
                value = json.loads(str(existing["document_json"]))
                return {str(key): item for key, item in value.items()}
        assessment = self.p0_assessment(assessment_id)
        if assessment.get("event_kind") != "gap" or assessment.get("current_stage") is not None:
            raise ValueError("gap_notice_requires_p0_gap_assessment")
        notice_id = (
            "gap-notice-"
            + hashlib.sha256(f"{assessment_id}:{client_request_id}".encode()).hexdigest()[:20]
        )
        document: dict[str, object] = {
            "ai_calls": 0,
            "assessment_id": assessment_id,
            "client_request_id": client_request_id,
            "current_stage": None,
            "gaps": assessment.get("gaps", []),
            "last_confirmed_stage": assessment.get("last_confirmed_stage"),
            "model_version_id": assessment.get("model_version_id"),
            "notice_id": notice_id,
            "notice_type": "data_gap_notice",
            "statement": "目标交易日核心数据未通过 P0 门禁，未发布新的正式阶段。",
            "status": "completed",
            "system_as_of": assessment.get("system_as_of"),
            "target_business_date": assessment.get("business_date"),
        }
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO data_gap_notice(
                    notice_id, assessment_id, client_request_id, document_json, created_at,
                    batch_id
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    notice_id,
                    assessment_id,
                    client_request_id,
                    _canonical_json(document),
                    datetime.now(UTC).isoformat(),
                    current_batch_id(),
                ),
            )
        return document

    def gap_notices(self) -> tuple[dict[str, object], ...]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT document_json FROM data_gap_notice ORDER BY notice_id DESC"
            ).fetchall()
        return tuple(
            {str(key): value for key, value in json.loads(str(row["document_json"])).items()}
            for row in rows
        )

    def _insert_p0_assessment(
        self,
        connection: sqlite3.Connection,
        assessment: dict[str, object],
    ) -> None:
        required = {
            "assessment_id",
            "business_date",
            "system_as_of",
            "event_kind",
        }
        if not required <= set(assessment):
            raise ValueError("p0_assessment_identity_incomplete")
        connection.execute(
            """
            INSERT OR IGNORE INTO p0_assessment(
                assessment_id, target_business_date, system_as_of,
                event_kind, projection_set_id, document_json, batch_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(assessment["assessment_id"]),
                str(assessment["business_date"]),
                str(assessment["system_as_of"]),
                str(assessment["event_kind"]),
                (
                    str(assessment["projection_set_id"])
                    if assessment.get("projection_set_id") is not None
                    else None
                ),
                _canonical_json(assessment),
                current_batch_id(),
            ),
        )

    def current(self) -> ProjectionSet:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT projection_set.projection_set_id
                FROM current_projection
                JOIN projection_set USING (projection_set_id)
                WHERE singleton = 1
                """
            ).fetchone()
            if row is None:
                raise LookupError("current_projection_unavailable")
        return self.get(str(row["projection_set_id"]))

    def get(self, projection_set_id: str) -> ProjectionSet:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT projection_set_id, envelope_json FROM projection_set
                WHERE projection_set_id = ?
                """,
                (projection_set_id,),
            ).fetchone()
            if row is None:
                raise LookupError("projection_set_not_found")
            dataset_rows = connection.execute(
                """
                SELECT dataset_name, document_json FROM analytical_dataset
                WHERE projection_set_id = ?
                """,
                (projection_set_id,),
            ).fetchall()
            corrections = publication_corrections(connection, projection_set_id)
        document = json.loads(str(row["envelope_json"]))
        envelope = ProjectionEnvelope(
            projection_set_id=str(document["projection_set_id"]),
            system_as_of=datetime.fromisoformat(str(document["system_as_of"])),
            target_business_date=str(document["target_business_date"]),
            evidence_snapshot_id=str(document["evidence_snapshot_id"]),
            model_version_id=str(document["model_version_id"]),
            trend_rule_version=str(document["trend_rule_version"]),
            evidence_window_start=str(document["evidence_window_start"]),
            evidence_window_end=str(document["evidence_window_end"]),
            generated_at=datetime.fromisoformat(str(document["generated_at"])),
            completeness=str(document["completeness"]),
            refresh_status=str(document["refresh_status"]),
            warnings=tuple(str(item) for item in document["warnings"]),
        )
        return ProjectionSet(
            envelope,
            {
                str(item["dataset_name"]): json.loads(str(item["document_json"]))
                for item in dataset_rows
            },
            corrections,
        )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        with database_connection(self._database_path) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            ensure_wal(connection, self._database_path)
            yield connection


def _validate_projection(
    envelope: ProjectionEnvelope, datasets: dict[str, dict[str, object]]
) -> None:
    if set(datasets) != set(ANALYTICAL_DATASETS):
        raise ValueError("projection_dataset_manifest_incomplete")
    if any(
        document.get("projection_set_id") != envelope.projection_set_id
        for document in datasets.values()
    ):
        raise ValueError("projection_dataset_identity_mismatch")


def validate_analytical_projection(
    envelope: ProjectionEnvelope,
    datasets: dict[str, dict[str, object]],
) -> None:
    _validate_projection(envelope, datasets)
    if envelope.system_as_of.tzinfo is None or envelope.generated_at.tzinfo is None:
        raise ValueError("projection_envelope_times_must_be_timezone_aware")
    if envelope.evidence_window_end != envelope.target_business_date:
        raise ValueError("projection_evidence_window_target_mismatch")
    if envelope.completeness not in {"complete", "degraded"}:
        raise ValueError("projection_completeness_invalid")
    if bool(envelope.warnings) != (envelope.completeness == "degraded"):
        raise ValueError("projection_completeness_warning_mismatch")
    overview = datasets["cycle_overview"]
    core = datasets["core_assets"]
    macro = datasets["macro"]
    inventory = datasets["inventory"]
    assets = core.get("assets")
    overview_assets = overview.get("core_assets")
    if not isinstance(assets, list) or overview_assets != assets:
        raise ValueError("projection_core_asset_reference_mismatch")
    by_asset = {
        str(item.get("asset")): item
        for item in assets
        if isinstance(item, dict) and item.get("asset") is not None
    }
    if set(by_asset) != {"bond", "stock", "commodity"}:
        raise ValueError("projection_core_asset_manifest_invalid")
    states = (
        str(by_asset["bond"].get("state")),
        str(by_asset["stock"].get("state")),
        str(by_asset["commodity"].get("state")),
    )
    if overview.get("stage_reason") == "core_data_pending":
        # A held stage publishes the rest of the run; it may not claim a formal stage.
        if overview.get("current_stage") is not None:
            raise ValueError("projection_formal_stage_invariant_failed")
    else:
        if any(state not in {"bull", "bear"} for state in states):
            raise ValueError("projection_core_asset_state_invalid")
        expected_stage = _FORMAL_STAGE_BY_STATES.get(states)
        if overview.get("current_stage") != expected_stage:
            raise ValueError("projection_formal_stage_invariant_failed")
    if macro.get("score") is not None or inventory.get("score") is not None:
        raise ValueError("projection_context_score_forbidden")
    _validate_visible_context_window(
        (macro, inventory),
        window_start=envelope.evidence_window_start,
        window_end=envelope.evidence_window_end,
    )
    structure = macro.get("output_structure")
    if inventory.get("output_structure") != structure:
        raise ValueError("projection_output_structure_mismatch")
    if structure == CONFIRMATION_STRUCTURE:
        _validate_confirmation(macro, inventory, overview, bond_state=by_asset["bond"].get("state"))
    elif structure is not None:
        raise ValueError("projection_output_structure_unknown")
    else:
        cards = inventory.get("cards")
        if (
            not isinstance(cards, list)
            or tuple(str(card.get("name")) for card in cards if isinstance(card, dict))
            != INVENTORY_CARD_NAMES
        ):
            raise ValueError("projection_inventory_card_manifest_invalid")
    if "macro_judgement" in overview:
        # Judged from the dimension summary's key indicators only (ADR-0043).
        if structure != CONFIRMATION_STRUCTURE:
            raise ValueError("projection_macro_judgement_invalid")
        validate_macro_judgement(overview["macro_judgement"])
    release_events = datasets["release_calendar"].get("events")
    stage_events = datasets["stage_history"].get("events")
    if not isinstance(release_events, list) or not isinstance(stage_events, list):
        raise ValueError("projection_event_dataset_invalid")


_RETIRED_MACRO_LABELS = ("policy_direction", "credit_response", "overheat_state", "price_pressure")


def _validate_confirmation(
    macro: dict[str, object],
    inventory: dict[str, object],
    overview: dict[str, object],
    *,
    bond_state: object,
) -> None:
    """A dimension summary of the published stage, with no label standing in (ADR-0037).

    It confirms the stage the set states, or none; each dimension's counts are its key
    indicators' relations, and a dimension not read yet has neither. A counterevidence
    waiting on grace counts only past it. An inventory card tells its data's availability
    apart from the relation, which is its quadrant's: never the seven cards' support for
    data held (N07). The bond's trend attribution explains the bond core's state as
    published, never another.
    """
    if any(label in macro for label in _RETIRED_MACRO_LABELS):
        raise ValueError("projection_confirmation_retired_label_present")
    # Shown beside the summary, never counted; the supply-demand note never names what
    # drives prices (macro semantics ticket 09); nor is the bond's trend attribution (10).
    for name in (
        "observation_interfaces",
        "price_consistency",
        "supply_demand",
        "bond_attribution",
    ):
        shown = macro.get(name)
        if shown is not None and (not isinstance(shown, dict) or shown.get("counted") is not False):
            raise ValueError("projection_confirmation_price_notes_invalid")
    note = macro.get("supply_demand")
    if isinstance(note, dict) and note.get("driver") != "unconfirmed":
        raise ValueError("projection_confirmation_price_notes_invalid")
    attribution = macro.get("bond_attribution")
    if isinstance(attribution, dict) and (
        attribution.get("driver") not in ATTRIBUTION_DRIVERS
        # No bond state standing names no driver.
        or (attribution.get("bond_trend") is None and attribution.get("driver") != "unclear")
        or attribution.get("bond_trend") != (bond_state if bond_state in {"bull", "bear"} else None)
    ):
        raise ValueError("projection_bond_attribution_invalid")
    confirmation = macro.get("confirmation")
    if not isinstance(confirmation, dict):
        raise ValueError("projection_confirmation_invalid")
    stage = overview.get("current_stage")
    if (
        confirmation.get("stage") != stage
        or confirmation.get("stage_reason") != overview.get("stage_reason")
        or confirmation.get("applicable") is not (stage is not None)
    ):
        raise ValueError("projection_confirmation_stage_mismatch")
    dimensions = confirmation.get("dimensions")
    if (
        not isinstance(dimensions, list)
        or not all(isinstance(item, dict) for item in dimensions)
        or [item.get("dimension") for item in dimensions] != list(CONFIRMATION_DIMENSIONS)
    ):
        raise ValueError("projection_confirmation_invalid")
    for dimension in dimensions:
        indicators = dimension.get("key_indicators")
        counts = dimension.get("counts")
        if not isinstance(indicators, list) or not all(
            isinstance(item, dict) for item in indicators
        ):
            raise ValueError("projection_confirmation_invalid")
        relations = [item.get("relation") for item in indicators]
        if dimension.get("status") == "not_connected":
            if indicators or counts is not None:
                raise ValueError("projection_confirmation_invalid")
            continue
        if (
            dimension.get("status") != "connected"
            or not indicators
            or any(relation not in CONFIRMATION_RELATIONS for relation in relations)
            or any((relation == "not_applicable") is (stage is not None) for relation in relations)
            or not isinstance(counts, dict)
            or set(counts) != set(CONFIRMATION_RELATIONS)
            or any(
                type(counts[relation]) is not int or counts[relation] != relations.count(relation)
                for relation in CONFIRMATION_RELATIONS
            )
            # Only a signal past its grace counts as counterevidence (ADR-0037).
            or any(
                item.get("relation") == "counterevidence"
                and isinstance(item.get("grace"), dict)
                and item["grace"].get("past") is not True
                for item in indicators
            )
        ):
            raise ValueError("projection_confirmation_invalid")
    inventory_dimension = dimensions[CONFIRMATION_DIMENSIONS.index("inventory")]
    quadrant = next(iter(inventory_dimension.get("key_indicators") or []), None)
    cards = inventory.get("cards")
    if cards is None and quadrant is None:
        return
    if (
        quadrant is None
        or not isinstance(cards, list)
        or not cards
        or any(
            not isinstance(card, dict)
            or "status" in card
            or card.get("availability") not in ("available", "unavailable")
            or card.get("relation") != quadrant.get("relation")
            or card.get("counted") is not False
            for card in cards
        )
    ):
        raise ValueError("projection_confirmation_inventory_card_invalid")


def _validate_visible_context_window(
    documents: tuple[dict[str, object], ...],
    *,
    window_start: str,
    window_end: str,
) -> None:
    try:
        visible_start = date.fromisoformat(window_start)
        visible_end = date.fromisoformat(window_end)
    except ValueError as error:
        raise ValueError("projection_context_visible_window_invalid") from error
    if visible_start > visible_end:
        raise ValueError("projection_context_visible_window_invalid")

    def walk(value: object) -> None:
        if isinstance(value, dict):
            period = value.get("period")
            if value.get("metric_id") is not None and period is not None:
                period_start = value.get("period_start", period)
                try:
                    evidence_start = date.fromisoformat(str(period_start))
                    evidence_end = date.fromisoformat(str(period))
                except ValueError as error:
                    raise ValueError(
                        "projection_context_evidence_outside_visible_window"
                    ) from error
                # A metric in force until changed is shown however old (ADR-0028).
                baseline = value["metric_id"] in EFFECTIVE_UNTIL_CHANGED_METRICS
                if (
                    not isinstance(period, str)
                    or not isinstance(period_start, str)
                    or evidence_start > evidence_end
                    or (evidence_end < visible_start and not baseline)
                    or evidence_start > visible_end
                ):
                    raise ValueError("projection_context_evidence_outside_visible_window")
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    for document in documents:
        walk(document)


def _envelope_document(envelope: ProjectionEnvelope) -> dict[str, object]:
    document = asdict(envelope)
    document["system_as_of"] = envelope.system_as_of.isoformat()
    document["generated_at"] = envelope.generated_at.isoformat()
    document["warnings"] = list(envelope.warnings)
    return document


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


_PROJECTION_SCHEMA = """
CREATE TABLE IF NOT EXISTS projection_set (
    projection_set_id TEXT PRIMARY KEY,
    envelope_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS analytical_dataset (
    projection_set_id TEXT NOT NULL REFERENCES projection_set(projection_set_id),
    dataset_name TEXT NOT NULL,
    document_json TEXT NOT NULL,
    PRIMARY KEY(projection_set_id, dataset_name)
);
CREATE TABLE IF NOT EXISTS current_projection (
    singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
    projection_set_id TEXT NOT NULL REFERENCES projection_set(projection_set_id)
);
CREATE TRIGGER IF NOT EXISTS projection_set_no_update
BEFORE UPDATE ON projection_set BEGIN SELECT RAISE(ABORT, 'projection_set_is_immutable'); END;
CREATE TRIGGER IF NOT EXISTS projection_set_no_delete
BEFORE DELETE ON projection_set BEGIN SELECT RAISE(ABORT, 'projection_set_is_immutable'); END;
CREATE TRIGGER IF NOT EXISTS analytical_dataset_no_update
BEFORE UPDATE ON analytical_dataset BEGIN
    SELECT RAISE(ABORT, 'analytical_dataset_is_immutable');
END;
CREATE TRIGGER IF NOT EXISTS analytical_dataset_no_delete
BEFORE DELETE ON analytical_dataset BEGIN
    SELECT RAISE(ABORT, 'analytical_dataset_is_immutable');
END;
"""

_P0_ASSESSMENT_SCHEMA = """
CREATE TABLE IF NOT EXISTS p0_assessment (
    assessment_id TEXT PRIMARY KEY,
    target_business_date TEXT NOT NULL,
    system_as_of TEXT NOT NULL,
    event_kind TEXT NOT NULL CHECK(event_kind IN ('formal', 'gap')),
    projection_set_id TEXT REFERENCES projection_set(projection_set_id),
    document_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS data_gap_notice (
    notice_id TEXT PRIMARY KEY,
    assessment_id TEXT NOT NULL REFERENCES p0_assessment(assessment_id),
    client_request_id TEXT NOT NULL UNIQUE,
    document_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS p0_assessment_no_update
BEFORE UPDATE ON p0_assessment BEGIN
    SELECT RAISE(ABORT, 'p0_assessment_is_immutable');
END;
CREATE TRIGGER IF NOT EXISTS p0_assessment_no_delete
BEFORE DELETE ON p0_assessment BEGIN
    SELECT RAISE(ABORT, 'p0_assessment_is_immutable');
END;
CREATE TRIGGER IF NOT EXISTS data_gap_notice_no_update
BEFORE UPDATE ON data_gap_notice BEGIN
    SELECT RAISE(ABORT, 'data_gap_notice_is_immutable');
END;
CREATE TRIGGER IF NOT EXISTS data_gap_notice_no_delete
BEFORE DELETE ON data_gap_notice BEGIN
    SELECT RAISE(ABORT, 'data_gap_notice_is_immutable');
END;
"""

# Where a context document's rows name the source claims they show, are derived from or
# are compared with, and those its confirmation read; a derived row's own identity is
# named there too, as the row's selected one (ticket 08).
_CITING_KEYS = frozenset(
    {
        "claim_id",
        "claim_ids",
        "selected_claim_id",
        "input_observation_version_ids",
        "direction_input_observation_version_ids",
        "trading_calendar_observation_version_ids",
        "observation_version_ids",
    }
)


def _citations(value: object, metric_id: object = None) -> tuple[set[str], set[str]]:
    """The source claims a context document's rows cite: those of the context, and those
    of the rows of the cores' own prices."""
    if isinstance(value, dict):
        metric_id = value.get("metric_id", metric_id)
        cited = {
            item
            for key in _CITING_KEYS & value.keys()
            for item in (value[key] if isinstance(value[key], list) else [value[key]])
            if isinstance(item, str)
        }
        children = [_citations(child, metric_id) for child in value.values()]
        context = set().union(*(child[0] for child in children))
        cores = set().union(*(child[1] for child in children))
        if metric_id in CORE_API_IDENTITIES:
            return context, cores | cited
        return context | cited, cores
    if isinstance(value, list):
        children = [_citations(child, metric_id) for child in value]
        return (
            set().union(*(child[0] for child in children)),
            set().union(*(child[1] for child in children)),
        )
    return set(), set()


def _derived_identities(value: object) -> set[str]:
    """The identities of the derived rows a context document shows."""
    if isinstance(value, dict):
        own = value.get("derived_observation_id")
        found = {own} if isinstance(own, str) else set()
        return found.union(*(_derived_identities(child) for child in value.values()))
    if isinstance(value, list):
        return set().union(*(_derived_identities(child) for child in value))
    return set()


# A window day whose summary cannot be corrected on a core history basis, and why (ticket
# 08); it goes with the day at retention.
UNCORRECTABLE_DAY_SCHEMA = """
CREATE TABLE IF NOT EXISTS uncorrectable_day (
    target_business_date TEXT NOT NULL,
    core_history_basis TEXT NOT NULL,
    corrected_assessment_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    batch_id TEXT,
    PRIMARY KEY (target_business_date, core_history_basis)
);
CREATE TRIGGER IF NOT EXISTS uncorrectable_day_no_update
BEFORE UPDATE ON uncorrectable_day BEGIN
    SELECT RAISE(ABORT, 'uncorrectable_day_is_append_only');
END;
CREATE TRIGGER IF NOT EXISTS uncorrectable_day_no_delete
BEFORE DELETE ON uncorrectable_day BEGIN
    SELECT RAISE(ABORT, 'uncorrectable_day_is_append_only');
END;
"""
