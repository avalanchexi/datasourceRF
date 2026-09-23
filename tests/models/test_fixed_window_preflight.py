"""Fixed-window diagnostics through public CLI and captured calendar transport.

Only synthetic calendar responses and the existing reviewed candidate contract are
prepared here. No price histories, lifecycle builders, calibration or replay run.
"""

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from pring_cycle.acquisition import AcquisitionRepository
from pring_cycle.cli import main
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.source_adapters import TushareCoreAdapter
from tests.conftest import _clock_datetime
from tests.models.test_candidate_admission import prepared_request, save, submit

PLAN = Path(__file__).resolve().parents[2] / (
    ".scratch/pring-window-publication-20260922/calendar-plan.json"
)


@pytest.fixture
def calendar_runtime(tmp_path, capsys, monkeypatch):
    clock = _clock_datetime(lambda: datetime(2026, 9, 23, 9, tzinfo=UTC))
    monkeypatch.setattr("pring_cycle.acquisition.datetime", clock)
    monkeypatch.setattr("pring_cycle.material_preflight.datetime", clock)
    paths = RuntimePaths.discover(tmp_path)
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    candidate = json.loads(capsys.readouterr().out)["model_version_id"]
    return paths, candidate


def capture_calendar(paths, days):
    raw = json.dumps(
        {
            "code": 0,
            "data": {
                "fields": ["cal_date", "is_open"],
                "items": [[day.replace("-", ""), 1] for day in days],
            },
        }
    ).encode()
    return TushareCoreAdapter("synthetic-token", transport=lambda _: raw).acquire_calendar(
        AcquisitionRepository(paths.database, paths.artifacts),
        date(2026, 3, 9),
        date(2026, 9, 22),
    )


def preflight(paths, candidate, capsys, *extra):
    main(
        [
            "model-input-preflight",
            "--runtime-root",
            str(paths.override_root),
            "--model",
            candidate,
            "--start",
            "2026-04-01",
            "--end",
            "2026-09-22",
            "--json",
            *extra,
        ]
    )
    return json.loads(capsys.readouterr().out)


def read_preflight_receipt(paths, receipt_hash, capsys):
    main(
        [
            "model-input-preflight-read",
            "--runtime-root",
            str(paths.override_root),
            "--receipt-hash",
            receipt_hash,
            "--json",
        ]
    )
    return json.loads(capsys.readouterr().out)


def test_preflight_returns_fixed_calendar_dates_and_hash_after_execution_day_moves(
    calendar_runtime,
    capsys,
):
    paths, candidate = calendar_runtime
    plan = json.loads(PLAN.read_text())
    capture_calendar(paths, plan["window"]["dates"])

    result = preflight(paths, candidate, capsys)

    assert result["requested_start"] == "2026-04-01"
    assert result["requested_end"] == "2026-09-22"
    assert result["inspected_at"] == "2026-09-23T09:00:00+00:00"
    calendar = result["calendar"]
    assert calendar["status"] == "available"
    assert calendar["dates"] == plan["window"]["dates"]
    assert len(calendar["dates"]) == 120
    assert calendar["ordered_dates_sha256"] == (
        "4b9329da4e532e4b8104dd83b2e49dea084632928a1145f730943e13e45b6eb2"
    )
    # Calendar availability must not promote the wholly missing economic inputs.
    assert result["status"] == "blocked"
    assert result["checks_complete"] is False


def test_preflight_receipt_retains_request_and_calendar_after_later_inspection(
    calendar_runtime, capsys
):
    paths, candidate = calendar_runtime
    plan = json.loads(PLAN.read_text())
    capture_calendar(paths, plan["window"]["dates"])
    result = preflight(paths, candidate, capsys)
    receipt_hash = result["receipt_hash"]

    # A later inspection with a different range must not rewrite the first one.
    diagnostic = preflight(
        paths, candidate, capsys, "--start", "2026-09-18", "--expected-trading-days", "3"
    )
    assert diagnostic["calendar"]["status"] == "available"
    assert diagnostic["request"]["expected_trading_days"] == 3
    assert diagnostic["request"]["requested_start"] == "2026-09-18"
    assert diagnostic["calendar"]["observed_trading_days"] == 3
    assert read_preflight_receipt(paths, diagnostic["receipt_hash"], capsys) == diagnostic
    saved = read_preflight_receipt(paths, receipt_hash, capsys)
    assert saved == result
    assert saved["request"] == {
        "model_version_id": candidate,
        "manifest_hash": result["manifest_hash"],
        "requested_start": "2026-04-01",
        "requested_end": "2026-09-22",
        "target_business_date": "2026-09-22",
        "expected_trading_days": 120,
    }
    assert saved["public_cutoffs"]["2026-04-01"] == "2026-04-01T15:59:59.999999+00:00"
    assert saved["public_cutoffs"]["2026-09-22"] == "2026-09-22T15:59:59.999999+00:00"
    assert saved["calendar"]["system_as_of"] == "2026-09-23T09:00:00+00:00"
    assert saved["calendar"]["provenance"]["raw_hash"]
    assert saved["calendar"]["provenance"]["normalized_hash"]


def test_fixed_window_rejects_119_sessions_even_with_earlier_history(calendar_runtime, capsys):
    paths, candidate = calendar_runtime
    days = json.loads(PLAN.read_text())["window"]["dates"]
    capture_calendar(paths, ["2026-03-31", *[d for d in days if d != "2026-06-10"]])
    result = preflight(paths, candidate, capsys)
    assert result["calendar"]["status"] == "unavailable"
    assert result["calendar"]["basis"] == "calendar_window_count_mismatch"
    assert result["calendar"]["observed_trading_days"] == 119
    assert result["request"]["expected_trading_days"] == 120
    assert read_preflight_receipt(paths, result["receipt_hash"], capsys) == result


@pytest.mark.parametrize("damaged", ["raw", "normalized"])
def test_preflight_failure_keeps_calendar_original_identity(
    calendar_runtime, capsys, monkeypatch, damaged
):
    paths, candidate = calendar_runtime
    days = json.loads(PLAN.read_text())["window"]["dates"]
    earlier = _clock_datetime(lambda: datetime(2026, 9, 22, 9, tzinfo=UTC))
    monkeypatch.setattr("pring_cycle.acquisition.datetime", earlier)
    previous = capture_calendar(paths, ["2026-03-31", *days])
    later = _clock_datetime(lambda: datetime(2026, 9, 23, 9, tzinfo=UTC))
    monkeypatch.setattr("pring_cycle.acquisition.datetime", later)
    acquired = capture_calendar(paths, days)
    digest = getattr(acquired.receipt, f"{damaged}_hash")
    (paths.artifacts / digest[:2] / digest).write_bytes(b"truncated calendar")

    result = preflight(paths, candidate, capsys, "--expected-trading-days", "120")

    assert result["calendar"]["status"] == "unavailable"
    assert result["calendar"]["error"] == "artifact_hash_mismatch"
    receipts = result["calendar"]["acquisition_receipts"]
    assert {r["acquisition_id"] for r in receipts} == {
        previous.receipt.acquisition_id,
        acquired.receipt.acquisition_id,
    }
    failed = result["calendar"]["provenance"]
    assert failed["acquisition_id"] == acquired.receipt.acquisition_id
    assert failed["raw_hash"] == acquired.receipt.raw_hash
    assert failed["normalized_hash"] == acquired.receipt.normalized_hash
    assert read_preflight_receipt(paths, result["receipt_hash"], capsys) == result


@pytest.mark.parametrize("fault", ["start", "end", "119", "duplicate", "sunday", "normalized"])
def test_fixed_window_calendar_guards_remain_readable(calendar_runtime, capsys, fault):
    paths, candidate = calendar_runtime
    days = json.loads(PLAN.read_text())["window"]["dates"]
    if fault == "start":
        days = ["2026-03-31", *days[1:]]
    elif fault == "end":
        days = ["2026-03-31", *days[:-1]]
    elif fault == "119":
        days = [day for day in days if day != "2026-06-10"]
    elif fault == "duplicate":
        days = [*days, "2026-09-22"]
    elif fault == "sunday":
        days = [*days, "2026-09-20"]
    if fault in {"duplicate", "sunday"}:
        with pytest.raises(ValueError, match="china_trading_calendar_invalid"):
            capture_calendar(paths, days)
    else:
        acquired = capture_calendar(paths, days)
        if fault == "normalized":
            digest = acquired.receipt.normalized_hash
            (paths.artifacts / digest[:2] / digest).write_bytes(b"[]")

    result = preflight(paths, candidate, capsys)
    assert result["calendar"]["status"] == "unavailable"
    assert any(gap["metric_id"] == "CN_TRADE_CALENDAR" for gap in result["gaps"])
    assert result["checks_complete"] is False
    assert len(result["calendar"]["acquisition_receipts"]) == 1
    receipt = result["calendar"]["acquisition_receipts"][0]
    assert receipt["raw_hash"]
    if fault in {"duplicate", "sunday"}:
        assert receipt["state"] == "failed"
        assert receipt["normalized_hash"] is None
    assert read_preflight_receipt(paths, result["receipt_hash"], capsys) == result


def test_old_and_new_windows_reconcile_without_discarding_warmup(calendar_runtime, capsys):
    paths, candidate = calendar_runtime
    plan = json.loads(PLAN.read_text())
    capture_calendar(
        paths, [*plan["window_delta"]["removed_from_display_dates"], *plan["window"]["dates"]]
    )
    old = preflight(paths, candidate, capsys, "--start", "2026-03-09", "--end", "2026-08-28")
    new = preflight(paths, candidate, capsys)

    assert old["calendar"]["status"] == new["calendar"]["status"] == "available"
    old_dates = set(old["calendar"]["dates"])
    new_dates = set(new["calendar"]["dates"])
    assert len(old_dates) == len(new_dates) == 120
    assert len(old_dates & new_dates) == 103
    assert sorted(new_dates - old_dates) == [
        "2026-08-31",
        "2026-09-01",
        "2026-09-02",
        "2026-09-03",
        "2026-09-04",
        "2026-09-07",
        "2026-09-08",
        "2026-09-09",
        "2026-09-10",
        "2026-09-11",
        "2026-09-14",
        "2026-09-15",
        "2026-09-16",
        "2026-09-17",
        "2026-09-18",
        "2026-09-21",
        "2026-09-22",
    ]
    assert len(old_dates - new_dates) == 17
    # Removed report dates remain available for formula-input checks.
    assert old_dates - new_dates <= set(new["calendar"]["history_dates"])
    assert new["calendar"]["provenance"] == old["calendar"]["provenance"]
    assert read_preflight_receipt(paths, old["receipt_hash"], capsys) == old


def test_calendar_uses_inspection_system_time_without_moving_public_window(
    calendar_runtime, capsys, monkeypatch
):
    paths, candidate = calendar_runtime
    later = _clock_datetime(lambda: datetime(2026, 9, 24, 9, tzinfo=UTC))
    monkeypatch.setattr("pring_cycle.acquisition.datetime", later)
    capture_calendar(paths, json.loads(PLAN.read_text())["window"]["dates"])

    before = preflight(paths, candidate, capsys)
    assert before["calendar"]["status"] == "unavailable"
    assert before["calendar"]["acquisition_receipts"] == []
    monkeypatch.setattr("pring_cycle.material_preflight.datetime", later)
    after = preflight(paths, candidate, capsys)
    assert after["calendar"]["status"] == "available"
    assert after["request"] == before["request"]
    assert after["requested_end"] == "2026-09-22"
    assert after["public_cutoffs"]["2026-09-22"] == before["public_cutoffs"]["2026-09-22"]
    assert after["calendar"]["system_as_of"] == "2026-09-24T09:00:00+00:00"
    assert read_preflight_receipt(paths, before["receipt_hash"], capsys) == before


def test_saved_preflight_rejects_modified_receipt(calendar_runtime, capsys):
    paths, candidate = calendar_runtime
    result = preflight(paths, candidate, capsys)
    digest = result["receipt_hash"]
    (paths.artifacts / digest[:2] / digest).write_bytes(b'{"status":"ready"}')
    with pytest.raises(SystemExit) as error:
        main(
            [
                "model-input-preflight-read",
                "--runtime-root",
                str(paths.override_root),
                "--receipt-hash",
                digest,
                "--json",
            ]
        )
    assert error.value.code == 2
    assert "material_preflight_receipt_hash_mismatch" in capsys.readouterr().err
