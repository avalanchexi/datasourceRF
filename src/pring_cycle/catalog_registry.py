"""Runtime catalog identities written only by reviewed candidate admission."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pring_cycle.catalog import (
    MARGIN_FINANCING_V0002,
    METRIC_CATALOG_V0001,
    METRIC_CATALOG_V0003,
    METRIC_CATALOG_VERSION,
    MetricDefinition,
)
from pring_cycle.read_scope import scope_cache
from pring_cycle.storage import database_connection

BUILTIN_CATALOG_VERSIONS = frozenset(
    {
        METRIC_CATALOG_V0001,
        METRIC_CATALOG_VERSION,
        METRIC_CATALOG_V0003,
        MARGIN_FINANCING_V0002,
    }
)

SYSTEM_TARGET_CUTOFF_VERSION = "dual-cutoff-v0003"

CATALOG_REGISTRY_SCHEMA = """
CREATE TABLE registered_metric_catalog (
    catalog_version TEXT PRIMARY KEY,
    definitions_hash TEXT NOT NULL,
    definitions_json TEXT NOT NULL,
    admitted_by_model_id TEXT NOT NULL REFERENCES model_version(model_version_id)
);
"""


def _definition_document(definitions: list[dict[str, Any]]) -> str:
    return json.dumps(
        sorted(definitions, key=lambda item: item["metric_id"]),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _register_admitted_catalog(connection: sqlite3.Connection, manifest: dict[str, Any]) -> None:
    """Part of the candidate transaction, after the service validates its review."""
    version = manifest["metric_catalog_version"]
    if version in BUILTIN_CATALOG_VERSIONS:
        raise ValueError("builtin_metric_catalog_cannot_be_registered")
    document = _definition_document(manifest["metric_definitions"])
    digest = hashlib.sha256(document.encode()).hexdigest()
    existing = connection.execute(
        "SELECT definitions_hash, definitions_json FROM registered_metric_catalog "
        "WHERE catalog_version=?",
        (version,),
    ).fetchone()
    if existing is not None:
        if existing[0] != digest or existing[1] != document:
            raise ValueError(f"metric_catalog_version_is_immutable:{version}")
        return
    connection.execute(
        "INSERT INTO registered_metric_catalog VALUES (?, ?, ?, ?)",
        (version, digest, document, manifest["model_version_id"]),
    )


def registered_definitions(database_path: Path, version: str) -> list[dict[str, Any]]:
    """Read a registered identity; never create a database or invent a catalog.

    A registered catalog is a single row that only candidate admission writes, and admission
    never runs inside a shared read. So one read answers every caller in that scope, and the
    returned list is shared with all of them: it must be treated as read-only, down to the
    dictionaries and lists nested inside it. Nothing enforces that; callers today only read
    (``registered_metric_definition`` copies before it converts, and the binding check only
    serialises). Outside a scope nothing is shared and every caller reads and verifies again.

    Only a verified read is shared. A failure is never remembered -- an unregistered version
    is a fact about this moment, not a verdict, and admission can register the row this read
    missed -- so every caller re-reads and re-verifies until one succeeds.
    """
    shared = scope_cache("registered_catalog_definitions")
    key = (str(database_path.resolve()), version)
    if shared is not None and key in shared:
        reused: list[dict[str, Any]] = shared[key]
        return reused
    with database_connection(f"{database_path.resolve().as_uri()}?mode=ro", uri=True) as connection:
        row = connection.execute(
            """SELECT c.definitions_hash, c.definitions_json, m.manifest_json
            FROM registered_metric_catalog c
            JOIN model_version m ON m.model_version_id=c.admitted_by_model_id
            WHERE c.catalog_version=?""",
            (version,),
        ).fetchone()
    if row is None:
        raise KeyError("unknown_metric_definition_version")
    digest, document, admitted_manifest_json = row
    if hashlib.sha256(document.encode()).hexdigest() != digest:
        raise ValueError("registered_metric_catalog_hash_mismatch")
    admitted = json.loads(admitted_manifest_json)
    if (
        admitted["metric_catalog_version"] != version
        or _definition_document(admitted["metric_definitions"]) != document
    ):
        raise ValueError("registered_metric_catalog_admission_mismatch")
    # Parsed separately from the admitted manifest above, and it must stay that way. Returning
    # that one instead would tie this result to model_version.manifest_json; a later scope cache
    # on ModelRepository.manifest would then be enough to hand require_registered_manifest the
    # same object on both sides, and its binding check would compare an object with itself.
    definitions: list[dict[str, Any]] = json.loads(document)
    if shared is not None:
        shared[key] = definitions
    return definitions


def registered_metric_definition(
    database_path: Path, version: str, metric_id: str
) -> MetricDefinition:
    for definition in registered_definitions(database_path, version):
        if definition["metric_id"] == metric_id:
            values = dict(definition)
            for field in ("dimensions", "source_codes", "source_candidates", "allowed_units"):
                values[field] = tuple(values[field])
            return MetricDefinition(**values)
    raise KeyError("unknown_metric_id")


def require_registered_manifest(database_path: Path, manifest: Mapping[str, Any]) -> None:
    version = str(manifest["metric_catalog_version"])
    if version in BUILTIN_CATALOG_VERSIONS:
        if manifest.get("point_in_time_rule_version") == SYSTEM_TARGET_CUTOFF_VERSION:
            raise ValueError("model_manifest_binding_mismatch")
        return
    definitions = registered_definitions(database_path, version)
    if _definition_document(manifest["metric_definitions"]) != _definition_document(definitions):
        raise ValueError("model_metric_catalog_binding_mismatch")
    with database_connection(f"{database_path.resolve().as_uri()}?mode=ro", uri=True) as connection:
        admitted = connection.execute(
            "SELECT manifest_json FROM model_version WHERE model_version_id=?",
            (manifest.get("model_version_id"),),
        ).fetchone()
    if admitted is None or json.loads(admitted[0]) != manifest:
        raise ValueError("model_manifest_binding_mismatch")
