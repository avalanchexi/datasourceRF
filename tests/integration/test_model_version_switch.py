"""A model is a version and an explicit pointer: switching needs no replay or acceptance."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.cli import main
from pring_cycle.models import ModelRepository, certified_model_v0001_manifest
from pring_cycle.runtime import RuntimePaths
from pring_cycle.worker import process_pending_run
from tests.integration.test_decertified_main_chain import TARGET, seed_published_inputs
from tests.integration.test_worker_execution import runtime


def cli(paths: RuntimePaths, capsys: pytest.CaptureFixture[str], *argv: str) -> dict[str, Any]:
    main([argv[0], "--runtime-root", str(paths.override_root), *argv[1:], "--json"])
    return dict(json.loads(capsys.readouterr().out))


def run_once(paths: RuntimePaths, capsys: pytest.CaptureFixture[str], request_id: str) -> str:
    submitted = cli(
        paths,
        capsys,
        "run-submit",
        "--target-date",
        TARGET.isoformat(),
        "--request-id",
        request_id,
        "--as-of",
        datetime(2026, 8, 28, 21).astimezone().isoformat(),
    )
    process_pending_run(paths, report_adapters=())
    return str(submitted["run_id"])


def summaries(paths: RuntimePaths) -> list[tuple[str, str]]:
    connection = sqlite3.connect(paths.database)
    try:
        return connection.execute(
            "SELECT projection_set_id, envelope_json FROM projection_set ORDER BY rowid"
        ).fetchall()
    finally:
        connection.close()


def batch_model(paths: RuntimePaths, run_id: str) -> str:
    connection = sqlite3.connect(paths.database)
    try:
        return str(
            connection.execute(
                "SELECT model_version_id FROM parent_run WHERE run_id=?", (run_id,)
            ).fetchone()[0]
        )
    finally:
        connection.close()


def test_activation_moves_the_pointer_for_later_runs_only(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = runtime(tmp_path)
    seed_published_inputs(paths)
    first = run_once(paths, capsys, "before-switch")
    published = summaries(paths)
    variant = certified_model_v0001_manifest()
    variant["model_version_id"] = "model-v0001-persistence-7"
    variant["trend_rules"]["persistence_days"] = 7
    manifest = tmp_path / "variant.json"
    manifest.write_text(json.dumps(variant), encoding="utf-8")

    registered = cli(paths, capsys, "model-register", "--manifest", str(manifest))
    activated = cli(
        paths, capsys, "model-activate", "--model", variant["model_version_id"], "--confirm"
    )
    second = run_once(paths, capsys, "after-switch")

    assert registered["status"] == "registered"
    assert activated["status"] == "active"
    assert batch_model(paths, first) == "model-v0001"
    assert batch_model(paths, second) == "model-v0001-persistence-7"
    assert summaries(paths)[: len(published)] == published
    assert len(summaries(paths)) == len(published) + 1

    cli(paths, capsys, "model-activate", "--model", "model-v0001", "--confirm")
    third = run_once(paths, capsys, "rolled-back")

    assert batch_model(paths, third) == "model-v0001"
    assert ModelRepository(paths.database).active().model_version_id == "model-v0001"


def test_activation_still_needs_explicit_confirmation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = runtime(tmp_path)

    with pytest.raises(SystemExit):
        main(
            [
                "model-activate",
                "--runtime-root",
                str(paths.override_root),
                "--model",
                "model-v0003",
                "--json",
            ]
        )

    assert ModelRepository(paths.database).active().model_version_id == "model-v0001"
    assert "explicit_model_approval_required" in capsys.readouterr().err
