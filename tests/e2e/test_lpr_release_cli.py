from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest

from pring_cycle.cli import main
from pring_cycle.models import ModelRepository
from pring_cycle.official_lpr import LprIngestionResult
from pring_cycle.runtime import RuntimePaths

OFFICIAL_URL = "https://www.chinamoney.com.cn/chinese/rdgz/20260820/3399885.html"
ANNOUNCEMENT = (Path(__file__).parents[1] / "fixtures/chinamoney_lpr_20260820.html").read_bytes()


def invoke(capsys: object, *arguments: str) -> dict[str, Any]:
    main([*arguments, "--json"])
    output = cast(Any, capsys).readouterr().out
    return cast(dict[str, Any], json.loads(output))


def test_public_offline_contract_command_never_mutates_or_uses_network(
    tmp_path: Path,
    capsys: object,
) -> None:
    root = tmp_path / "runtime"
    source = tmp_path / "lpr.html"
    source.write_bytes(ANNOUNCEMENT)

    document = invoke(
        capsys,
        "lpr-contract",
        "--runtime-root",
        str(root),
        "--input",
        str(source),
        "--url",
        OFFICIAL_URL,
        "--period",
        "2026-08",
        "--fetched-at",
        "2026-08-20T01:02:00+00:00",
    )

    assert document["status"] == "validated"
    assert document["network_requests"] == 0
    assert document["observation_count"] == 2
    assert not root.exists()


def test_generic_evidence_command_cannot_self_certify_lpr(
    tmp_path: Path,
    capsys: object,
) -> None:
    root = tmp_path / "runtime"
    main(["init", "--runtime-root", str(root), "--json"])
    cast(Any, capsys).readouterr()
    forged = tmp_path / "forged.json"
    forged.write_text(
        json.dumps(
            {
                "metric_id": "CN_LPR_1Y_5Y",
                "definition_version": "metric-catalog-v0001",
                "period_kind": "month",
                "period_start": "2026-08-01",
                "period_end": "2026-08-31",
                "dimensions": {"tenor": "1y"},
                "value": 3.0,
                "value_state": "reported_value",
                "unit": "percent",
                "provider": "manual",
                "source_reference": "fixture://forged",
                "release_event_id": "forged",
                "release_at": "2026-08-20T01:00:00+00:00",
                "public_available_at": "2026-08-20T01:00:00+00:00",
                "fetched_at": "2026-08-20T01:02:00+00:00",
                "available_at": "2026-08-20T01:02:00+00:00",
                "certification_status": "certified",
                "quality_status": "validated",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit):
        main(
            [
                "evidence-ingest",
                "--runtime-root",
                str(root),
                "--input",
                str(forged),
                "--json",
            ]
        )

    assert "certified_evidence_requires_certified_adapter" in cast(Any, capsys).readouterr().err


def test_lpr_refresh_uses_the_active_models_definition_version(
    tmp_path: Path,
    capsys: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "runtime"
    main(["init", "--runtime-root", str(root), "--json"])
    cast(Any, capsys).readouterr()
    paths = RuntimePaths.discover(root)
    models = ModelRepository(paths.database)
    models.activate("model-v0001", explicitly_approved=True)
    captured: dict[str, object] = {}

    def fake_refresh(*_args: object, **kwargs: object) -> LprIngestionResult:
        captured.update(kwargs)
        return LprIngestionResult(
            status="stored",
            release_event_id="fixture:lpr",
            period="2026-08",
            artifact_hash="a" * 64,
            observation_ids=("observation",),
            claim_ids=("claim",),
            observation_count=1,
        )

    monkeypatch.setattr("pring_cycle.official_lpr.refresh_lpr_release", fake_refresh)

    document = invoke(
        capsys,
        "lpr-refresh",
        "--runtime-root",
        str(root),
        "--url",
        OFFICIAL_URL,
        "--period",
        "2026-08",
    )

    assert document["status"] == "stored"
    assert captured["definition_version"] == "metric-catalog-v0001"
    assert isinstance(captured["fetched_at"], datetime)
    assert cast(datetime, captured["fetched_at"]).tzinfo is UTC
