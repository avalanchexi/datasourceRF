"""One shared read of a registered catalog, without letting a check pass on memory."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.catalog_registry import registered_definitions, registered_metric_definition
from pring_cycle.models import ModelRepository
from pring_cycle.read_scope import shared_read_scope
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from tests.fixtures.model_registration import (
    bind_synthetic_review,
    prepared_request,
    save,
    submit,
)

VERSION = "synthetic-metric-catalog-admission-v1"


def admitted_catalog(paths: RuntimePaths, capsys: pytest.CaptureFixture[str]) -> str:
    """Register the synthetic catalog unchanged; no actual source is certified."""
    request, _ = prepared_request(paths)
    package_hash = request["package_hashes"][0]
    package = json.loads((paths.artifacts / package_hash[:2] / package_hash).read_bytes())
    bind_synthetic_review(paths, request, package)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    return str(ModelRepository(paths.database).manifest(model_id)["metric_catalog_version"])


def count_reads(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Every read-only connection the catalog registry opens, in order."""
    from pring_cycle import catalog_registry

    opened: list[str] = []
    connect = catalog_registry.database_connection

    def record(*args: Any, **kwargs: Any) -> Any:
        opened.append(str(args[0]) if args else "")
        return connect(*args, **kwargs)

    monkeypatch.setattr(catalog_registry, "database_connection", record)
    return opened


def two_definitions(paths: RuntimePaths, version: str) -> tuple[Any, Any]:
    return (
        registered_metric_definition(paths.database, version, "CN_GDP"),
        registered_metric_definition(paths.database, version, "CN_PPI"),
    )


@pytest.mark.usefixtures("acquisition_clock")
def test_one_read_answers_every_metric_from_a_single_catalog_query(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A registered catalog is one row; reading it once per metric is reading it again.

    Inside a shared read the row cannot change -- it is written only by candidate admission,
    which never runs in a scope -- so the second metric is answered from the first read.
    Outside a scope nothing is shared and every caller reads and verifies again.
    """
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    version = admitted_catalog(paths, capsys)
    assert version == VERSION

    opened = count_reads(monkeypatch)
    with shared_read_scope():
        gdp, ppi = two_definitions(paths, version)
        shared, again = (
            registered_definitions(paths.database, version),
            registered_definitions(paths.database, version),
        )
    assert len(opened) == 1
    assert shared is again

    opened.clear()
    unshared = two_definitions(paths, version)
    assert len(opened) == 2
    # One read must answer with what two reads would have: same definitions, not just same ids.
    assert (gdp, ppi) == unshared
    assert gdp.metric_id == "CN_GDP" and ppi.metric_id == "CN_PPI"


@pytest.mark.usefixtures("acquisition_clock")
def test_an_unknown_version_is_never_remembered_as_unknown(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Remembering a failure would pin a version that admission could still register.

    Admission writes the row this read misses, and that table has no immutability trigger,
    so "not registered yet" is a fact about now, never a verdict to keep.
    """
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    admitted_catalog(paths, capsys)

    opened = count_reads(monkeypatch)
    with shared_read_scope():
        for _ in range(2):
            with pytest.raises(KeyError, match="unknown_metric_definition_version"):
                registered_definitions(paths.database, "never-registered")
    assert len(opened) == 2


@pytest.mark.usefixtures("acquisition_clock")
def test_a_rejected_catalog_is_rejected_again_inside_the_same_read(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every way this read can refuse must refuse again, not once per scope.

    The unknown version is only one of three refusals; a hash that does not match its
    document, and a document the admitting manifest disagrees with, are the other two.
    None of them is a verdict to keep.
    """
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    version = admitted_catalog(paths, capsys)

    for column, expected in (
        ("definitions_json='[]'", "registered_metric_catalog_hash_mismatch"),
        ("definitions_hash=?", "registered_metric_catalog_admission_mismatch"),
    ):
        connection = sqlite3.connect(paths.database)
        try:
            statement = f"UPDATE registered_metric_catalog SET {column} WHERE catalog_version=?"
            if "?" in column:
                document = json.dumps([{"metric_id": "CN_GDP"}])
                connection.execute(
                    "UPDATE registered_metric_catalog SET definitions_json=? "
                    "WHERE catalog_version=?",
                    (document, version),
                )
                connection.execute(
                    statement,
                    (hashlib.sha256(document.encode()).hexdigest(), version),
                )
            else:
                connection.execute(statement, (version,))
            connection.commit()
        finally:
            connection.close()

        opened = count_reads(monkeypatch)
        with shared_read_scope():
            for _ in range(2):
                with pytest.raises(ValueError, match=expected):
                    registered_definitions(paths.database, version)
        assert len(opened) == 2


@pytest.mark.usefixtures("acquisition_clock")
def test_a_damaged_catalog_is_caught_again_by_the_next_read(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verifying once must not become a permit: each shared read verifies for itself."""
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    version = admitted_catalog(paths, capsys)

    with shared_read_scope():
        assert registered_definitions(paths.database, version)

    connection = sqlite3.connect(paths.database)
    try:
        connection.execute(
            "UPDATE registered_metric_catalog SET definitions_json='[]' WHERE catalog_version=?",
            (version,),
        )
        connection.commit()
    finally:
        connection.close()

    with (
        shared_read_scope(),
        pytest.raises(ValueError, match="registered_metric_catalog_hash_mismatch"),
    ):
        registered_definitions(paths.database, version)
