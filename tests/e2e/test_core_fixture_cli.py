from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from pring_cycle.cli import main


def invoke(capsys: object, *arguments: str) -> dict[str, object]:
    main([*arguments, "--json"])
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    return json.loads(captured.out)


def trading_days_ending(target: date, count: int) -> list[str]:
    days: list[str] = []
    candidate = target
    while len(days) < count:
        if candidate.weekday() < 5:
            days.append(candidate.isoformat())
        candidate -= timedelta(days=1)
    return list(reversed(days))


def core_fixture(
    *,
    target: date = date(2026, 8, 28),
    count: int = 300,
) -> dict[str, object]:
    calendar = trading_days_ending(target, count)
    assets = {}
    for asset, metric_id, increasing in (
        ("bond", "CN_BOND_CORE_000012", True),
        ("stock", "CN_EQUITY_CORE_000985", True),
        ("commodity", "CN_COMMODITY_CORE_NHII", False),
    ):
        assets[asset] = {
            "metric_id": metric_id,
            "prices": [
                {
                    "business_date": business_date,
                    "value": 100.0 + index if increasing else 500.0 - index,
                }
                for index, business_date in enumerate(calendar)
            ],
        }
    return {
        "schema_version": "core-price-fixture-v0001",
        "target_business_date": target.isoformat(),
        "system_as_of": f"{target.isoformat()}T21:00:00+08:00",
        "model_version_id": "model-v0001",
        "trading_calendar": calendar,
        "assets": assets,
    }


def test_public_fixture_command_projects_the_three_core_tracks_atomically(
    tmp_path: Path,
    capsys: object,
) -> None:
    runtime_root = tmp_path / "runtime"
    fixture_path = tmp_path / "core-fixture.json"
    fixture_path.write_text(json.dumps(core_fixture()), encoding="utf-8")
    common = ("--runtime-root", str(runtime_root))
    invoke(capsys, "init", *common)

    published = invoke(capsys, "fixture-project", *common, "--input", str(fixture_path))
    duplicate = invoke(capsys, "fixture-project", *common, "--input", str(fixture_path))
    projection = invoke(capsys, "projection", *common)
    models = invoke(capsys, "models", *common)

    assert published == duplicate
    assert published["status"] == "published"
    assert published["acceptance_only"] is True
    assert published["network_requests"] == 0
    assert published["current_stage"] == "stage_ii"
    assert published["projection_set_id"] == projection["envelope"]["projection_set_id"]  # type: ignore[index]
    assert projection["envelope"]["warnings"][0] == "acceptance_fixture_only"  # type: ignore[index]
    assert "policy_context_degraded:insufficient_data" in projection["envelope"][  # type: ignore[index]
        "warnings"
    ]
    assert len(projection["datasets"]["inventory"]["cards"]) == 7  # type: ignore[index]
    assert projection["envelope"]["evidence_window_end"] == "2026-08-28"  # type: ignore[index]
    assert projection["datasets"]["cycle_overview"]["current_stage"] == "stage_ii"  # type: ignore[index]
    assets = projection["datasets"]["core_assets"]["assets"]  # type: ignore[index]
    assert [(item["asset"], item["state"], item["proxy_12m"]) for item in assets] == [  # type: ignore[index]
        ("bond", "bull", "bull"),
        ("stock", "bull", "bull"),
        ("commodity", "bear", "bear"),
    ]
    assert models["models"][0]["status"] == "registered"  # type: ignore[index]


def test_fixture_command_rejects_an_incomplete_asset_manifest_without_a_projection(
    tmp_path: Path,
    capsys: object,
) -> None:
    runtime_root = tmp_path / "runtime"
    fixture = core_fixture()
    fixture["assets"].pop("commodity")  # type: ignore[union-attr]
    fixture_path = tmp_path / "invalid-core-fixture.json"
    fixture_path.write_text(json.dumps(fixture), encoding="utf-8")
    common = ("--runtime-root", str(runtime_root))
    invoke(capsys, "init", *common)

    with pytest.raises(SystemExit):
        main(
            [
                "fixture-project",
                *common,
                "--input",
                str(fixture_path),
                "--json",
            ]
        )

    assert "core_fixture_asset_manifest_invalid" in capsys.readouterr().err  # type: ignore[attr-defined]
    with pytest.raises(SystemExit):
        main(["projection", *common, "--json"])
    assert "current_projection_unavailable" in capsys.readouterr().err  # type: ignore[attr-defined]


def test_p0_gap_keeps_current_projection_and_can_create_a_deterministic_notice(
    tmp_path: Path,
    capsys: object,
) -> None:
    runtime_root = tmp_path / "runtime"
    valid_path = tmp_path / "valid-core-fixture.json"
    blocked_path = tmp_path / "blocked-core-fixture.json"
    valid_path.write_text(json.dumps(core_fixture()), encoding="utf-8")
    blocked_path.write_text(
        json.dumps(core_fixture(target=date(2026, 8, 31), count=100)),
        encoding="utf-8",
    )
    common = ("--runtime-root", str(runtime_root))
    invoke(capsys, "init", *common)
    first = invoke(capsys, "fixture-project", *common, "--input", str(valid_path))

    blocked = invoke(
        capsys,
        "fixture-project",
        *common,
        "--input",
        str(blocked_path),
    )
    current = invoke(capsys, "projection", *common)
    history = invoke(capsys, "stage-history", *common)
    notice = invoke(
        capsys,
        "gap-notice",
        *common,
        "--assessment-id",
        str(blocked["assessment_id"]),
        "--request-id",
        "fixture-gap-notice-1",
    )
    duplicate = invoke(
        capsys,
        "gap-notice",
        *common,
        "--assessment-id",
        str(blocked["assessment_id"]),
        "--request-id",
        "fixture-gap-notice-1",
    )
    notices = invoke(capsys, "gap-notices", *common)

    assert blocked["status"] == "action_required"
    assert blocked["current_stage"] is None
    assert blocked["projection_set_id"] is None
    assert isinstance(blocked["assessment_id"], str)
    assert current["envelope"]["projection_set_id"] == first["projection_set_id"]  # type: ignore[index]
    assert [event["event_kind"] for event in history["events"]] == ["formal", "gap"]  # type: ignore[index]
    gap = history["events"][1]  # type: ignore[index]
    assert gap["business_date"] == "2026-08-31"
    assert gap["current_stage"] is None
    assert gap["last_confirmed_stage"] == "stage_ii"
    assert gap["stage_reason"] == "p0_unavailable"
    assert gap["gaps"] == [
        "bond:insufficient_history",
        "stock:insufficient_history",
        "commodity:insufficient_history",
    ]
    assert notice == duplicate
    assert notice["status"] == "completed"
    assert notice["notice_type"] == "data_gap_notice"
    assert notice["ai_calls"] == 0
    assert notice["current_stage"] is None
    assert notice["last_confirmed_stage"] == "stage_ii"
    assert notices["notices"][0]["notice_id"] == notice["notice_id"]  # type: ignore[index]
    assert invoke(capsys, "reports", *common)["reports"] == []
