"""Which catalog versions give a metric the same definition (ADR-0036).

A model's catalog version labels the whole set of definitions, and a new model stamps every
definition with it even when only one metric changed. A version label is not an economic
fact: two catalogs define a metric the same way when its unit, allowed units, frequency,
dimensions and source codes agree, and, for a derived metric, its admitting models' formula
versions too. Name, priority, role, candidate pages, certification and release rules do not
change what a value means, so they are not compared.

A derived metric's formula is known for a catalog only when every model using it names the
same formula version; a builtin catalog, a model missing the formula, or two models disagreeing
leave it unknown, and an unknown formula shares the definition with no other version.

Builtin catalogs are compared from code; registered ones are read the way the catalog
registry reads them: verified against their hash and their admitting model, shared inside a
``shared_read_scope`` and read again outside one.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Mapping
from dataclasses import asdict
from functools import cache
from pathlib import Path
from typing import Any

from pring_cycle.catalog import (
    _REQUIRED_FORMULAS,
    MARGIN_FINANCING_V0002,
    METRIC_CATALOG_V0001,
    METRIC_CATALOG_V0003,
    METRIC_CATALOG_VERSION,
    metric_catalog,
    metric_catalog_v0001,
    metric_catalog_v0003,
    metric_definition,
)
from pring_cycle.catalog_registry import _definition_document
from pring_cycle.read_scope import scope_cache
from pring_cycle.storage import database_connection

IDENTITY_FIELDS = ("unit", "allowed_units", "frequency", "dimensions", "source_codes")

# Definitions by metric, and the formula version each derived metric has under every model
# using the catalog (None: not known).
_Catalog = tuple[dict[str, Mapping[str, Any]], Mapping[str, str | None]]


def _formula_key(metric_id: str) -> str:
    """``CN_CREDIT_IMPULSE`` -> ``credit_impulse``, the manifest's formula name."""
    return metric_id.lower().removeprefix("cn_")


def _fields(definition: Mapping[str, Any]) -> tuple[object, ...]:
    values: list[object] = []
    for field in IDENTITY_FIELDS:
        value = definition.get(field)
        if field == "allowed_units" and not value:
            value = (definition.get("unit"),)
        values.append(tuple(value) if isinstance(value, list | tuple) else value)
    return tuple(values)


def _same(metric_id: str, one: _Catalog, other: _Catalog) -> bool:
    if _fields(one[0][metric_id]) != _fields(other[0][metric_id]):
        return False
    key = _formula_key(metric_id)
    if key not in _REQUIRED_FORMULAS or one is other:
        return True
    formula = one[1].get(key)
    return formula is not None and formula == other[1].get(key)


@cache
def _builtin_catalogs() -> dict[str, _Catalog]:
    """The catalogs in code; which formulas their models used is not known here."""
    catalogs: dict[str, _Catalog] = {
        version: ({item.metric_id: asdict(item) for item in definitions}, {})
        for version, definitions in (
            (METRIC_CATALOG_V0001, metric_catalog_v0001()),
            (METRIC_CATALOG_VERSION, metric_catalog()),
            (METRIC_CATALOG_V0003, metric_catalog_v0003()),
        )
    }
    margin = metric_definition("CN_MARGIN_BALANCE", definition_version=MARGIN_FINANCING_V0002)
    catalogs[MARGIN_FINANCING_V0002] = ({margin.metric_id: asdict(margin)}, {})
    return catalogs


def _registered_catalogs(connection: sqlite3.Connection, location: str) -> dict[str, _Catalog]:
    shared = scope_cache("same_definition_catalogs")
    if shared is not None and location in shared:
        reused: dict[str, _Catalog] = shared[location]
        return reused
    try:
        rows = connection.execute(
            """SELECT c.catalog_version, c.definitions_hash, c.definitions_json, m.manifest_json
            FROM registered_metric_catalog c
            JOIN model_version m ON m.model_version_id=c.admitted_by_model_id"""
        ).fetchall()
        manifests = [
            str(row[0]) for row in connection.execute("SELECT manifest_json FROM model_version")
        ]
    except sqlite3.OperationalError as error:
        # A database from before the catalog registry has no registered catalogs.
        if "no such table" not in str(error):
            raise
        rows, manifests = [], []
    used: dict[str, list[Mapping[str, str]]] = {}
    for manifest_json in manifests:
        manifest = json.loads(manifest_json)
        used.setdefault(str(manifest.get("metric_catalog_version")), []).append(
            manifest.get("derived_formula_versions") or {}
        )
    catalogs: dict[str, _Catalog] = {}
    for version, digest, document, manifest_json in rows:
        if hashlib.sha256(str(document).encode()).hexdigest() != digest:
            raise ValueError("registered_metric_catalog_hash_mismatch")
        admitted = json.loads(manifest_json)
        if (
            admitted["metric_catalog_version"] != version
            or _definition_document(admitted["metric_definitions"]) != document
        ):
            raise ValueError("registered_metric_catalog_admission_mismatch")
        formulas: dict[str, str | None] = {}
        for key in _REQUIRED_FORMULAS:
            named = {models.get(key) for models in used.get(str(version), [])}
            formulas[key] = named.pop() if len(named) == 1 else None
        catalogs[str(version)] = (
            {str(item["metric_id"]): item for item in json.loads(document)},
            formulas,
        )
    if shared is not None:
        shared[location] = catalogs
    return catalogs


def same_definition_versions(
    connection: sqlite3.Connection, database_path: Path, metric_id: str, version: str
) -> tuple[str, ...]:
    """The catalog versions defining ``metric_id`` as ``version`` does, ``version`` included."""
    catalogs = {
        **_builtin_catalogs(),
        **_registered_catalogs(connection, str(database_path.resolve())),
    }
    own = catalogs.get(version)
    if own is None or metric_id not in own[0]:
        return (version,)
    return tuple(
        sorted(
            other
            for other, catalog in catalogs.items()
            if metric_id in catalog[0] and _same(metric_id, own, catalog)
        )
    )


def family_identity(database_path: Path, version: str, family: str) -> str:
    """What a release family's metrics mean under ``version``, without the version label.

    Every metric the catalog places in the family, with its compared fields and, when derived,
    its formula; an unknown formula keeps the version so nothing else matches it. Unchanged
    definitions give the same identity under every catalog version (ADR-0036).
    """
    uri = f"{database_path.resolve().as_uri()}?mode=ro"
    with database_connection(uri, uri=True) as connection:
        catalogs = {
            **_builtin_catalogs(),
            **_registered_catalogs(connection, str(database_path.resolve())),
        }
    if version not in catalogs:
        return json.dumps(["catalog", version])
    definitions, formulas = catalogs[version]
    members = []
    for metric_id, definition in sorted(definitions.items()):
        if definition.get("release_event_family") != family:
            continue
        key = _formula_key(metric_id)
        formula = (formulas.get(key) or f"unknown:{version}") if key in _REQUIRED_FORMULAS else None
        members.append([metric_id, list(_fields(definition)), formula])
    return json.dumps(members, sort_keys=True, default=list)
