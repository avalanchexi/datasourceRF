from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from pring_cycle.acquisition import AcquisitionRepository
from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime

ORIGINALS = {
    "RBRTE": "b078a362332a3d6b34ae2a5dc5a91b98ddfacc7979410b32081f07e9dadc243e",
    "RWTC": "7da3e5b6632942bfedf02642fde22867d24bb0cf6477eff5ac9e5f9be4d92497",
}


def original(series: str) -> bytes:
    content = (
        Path(__file__).resolve().parents[2]
        / ".scratch/pring-data-acquisition-repair/evidence-14"
        / ORIGINALS[series]
    ).read_bytes()
    assert hashlib.sha256(content).hexdigest() == ORIGINALS[series]
    return content


@pytest.mark.parametrize(
    ("series", "start", "end", "expected", "missing"),
    [
        ("RBRTE", "2026-08-31", "2026-09-04", {"2026-09-01": 96.02}, 4),
        (
            "RWTC",
            "2020-04-20",
            "2020-04-24",
            {
                "2020-04-20": -36.98,
                "2020-04-21": 8.91,
                "2020-04-22": 13.64,
                "2020-04-23": 15.06,
                "2020-04-24": 15.99,
            },
            0,
        ),
        ("RWTC", "1985-12-30", "1986-01-03", {"1986-01-02": 25.56, "1986-01-03": 26}, 3),
    ],
)
@pytest.mark.usefixtures("runtime_clock")
def test_official_html_acquisition_keeps_dates_signed_values_and_unknown_public_time(
    tmp_path: Path, series: str, start: str, end: str, expected: dict[str, float], missing: int
) -> None:
    from pring_cycle.eia_html import FetchedEiaHistory, refresh_eia_history

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    raw = original(series)
    calls = []

    def fetch(url: str) -> FetchedEiaHistory:
        calls.append(url)
        return FetchedEiaHistory(raw, url, 200, "text/html; charset=utf-8")

    result = refresh_eia_history(
        paths,
        series_id=series,
        start_date=date.fromisoformat(start),
        end_date=date.fromisoformat(end),
        definition_version="metric-catalog-v0002",
        fetcher=fetch,
    )
    assert len(calls) == 1
    assert result.observation_count == len(expected)
    assert result.missing_cell_count == missing
    metric = "EIA_BRENT_RBRTE" if series == "RBRTE" else "EIA_WTI_RWTC"
    evidence = EvidenceRepository(paths.database)
    points = evidence.metric_series(
        metric,
        mode=AsOfMode.SYSTEM,
        as_of=datetime.now(UTC),
        definition_version="metric-catalog-v0002",
    )
    assert {p.period_end: p.claims[0].value for p in points} == expected
    assert all(p.period_start == p.period_end for p in points)
    assert all(c.unit == "usd_per_barrel" for p in points for c in p.claims)
    assert all(c.parsed_public_available_at is None for p in points for c in p.claims)
    assert all(c.release_at is None for p in points for c in p.claims)
    assert all(
        c.certification_status == "awaiting_source_certification" for p in points for c in p.claims
    )
    receipts = AcquisitionRepository(paths.database, paths.artifacts)
    receipt = receipts.get(result.acquisition_id)
    assert receipts.read_content(receipt.acquisition_id, "raw") == raw
    # Its receipt says the values entered the evidence store (ticket 18).
    assert receipts.ingest_result(receipt.acquisition_id) == ("accepted", None)
    normalized = json.loads(receipts.read_content(receipt.acquisition_id, "normalized"))
    assert normalized["release_date"] == "2026-09-02"
    assert normalized["next_release_date"] == "2026-09-10"
    assert normalized["release_timezone"] == "America/New_York"
    assert normalized["release_precision"] == "date"
    assert normalized["http_response"] == {
        "response_final_url": calls[0],
        "response_http_status": "200",
        "response_media_type": "text/html; charset=utf-8",
    }
    assert {c["state"] for c in normalized["cells"] if c["value"] is None} == (
        {"blank"} if missing else set()
    )
    for point in points:
        trace = evidence.trace(point.observation_id, mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC))
        assert trace.acquisition_status == "linked"
        assert {r.acquisition_id for r in trace.acquisitions} == {receipt.acquisition_id}
        assert point.claims[0].available_at >= receipt.validated_at


@pytest.mark.usefixtures("runtime_clock")
def test_public_cli_can_acquire_html_without_an_api_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from io import BytesIO

    from pring_cycle.cli import main

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    calls = []

    class Response(BytesIO):
        status = 200
        headers = {"Content-Type": "text/html; charset=utf-8"}

        def geturl(self):
            return "https://www.eia.gov/dnav/pet/hist/RBRTED.htm"

    def fetch(request, *, timeout):
        calls.append(request.full_url)
        return Response(original("RBRTE"))

    monkeypatch.setattr("pring_cycle.eia_html.open_no_redirects", fetch)
    main(
        [
            "eia-html-refresh",
            "--runtime-root",
            str(tmp_path / "runtime"),
            "--series",
            "RBRTE",
            "--start",
            "2026-08-31",
            "--end",
            "2026-09-04",
            "--definition-version",
            "metric-catalog-v0002",
            "--json",
        ]
    )
    result = json.loads(capsys.readouterr().out)
    assert result["observation_count"] == 1
    assert result["missing_cell_count"] == 4
    assert len(calls) == 1
    assert len(AcquisitionRepository(paths.database, paths.artifacts).history()) == 1


@pytest.mark.parametrize(
    "case",
    [
        "wrong_series",
        "wrong_unit",
        "wrong_host",
        "wrong_media",
        "wrong_columns",
        "missing_cell",
        "wrong_week",
        "reversed_week",
        "duplicate_week",
        "nonfinite",
        "truncated",
        "conflicting_release",
        "reverse_release",
        "colspan",
        "rowspan",
        "http_charset",
        "meta_charset",
    ],
)
@pytest.mark.usefixtures("runtime_clock")
def test_bad_official_history_is_retained_and_rejected_before_claims(
    tmp_path: Path, case: str
) -> None:
    from pring_cycle.eia_html import FetchedEiaHistory, refresh_eia_history

    raw = original("RWTC" if case == "wrong_series" else "RBRTE")
    changes = {
        "wrong_unit": (b"Dollars per Barrel", b"Dollars per Gallon"),
        "wrong_columns": (b">Mon&nbsp;</th>", b">Tue&nbsp;</th>"),
        "missing_cell": (b"<td class='B3'>18.63</td>", b""),
        "wrong_week": (b"1987 May-18 to May-22", b"1987 May-19 to May-22"),
        "nonfinite": (b"<td class='B3'>18.63</td>", b"<td class='B3'>NaN</td>"),
        "conflicting_release": (
            b"<td class='F2'>Release Date: 9/2/2026</td>",
            b"<td class='F2'>Release Date: 9/2/2026</td><td>Release Date: 9/3/2026</td>",
        ),
        "reverse_release": (b"Next Release Date: 9/10/2026", b"Next Release Date: 9/1/2026"),
        "colspan": (b"<td class='B3'>18.63</td>", b"<td class='B3' colspan='2'>18.63</td>"),
        "rowspan": (b"<td class='B3'>18.63</td>", b"<td class='B3' rowspan='2'>18.63</td>"),
        "meta_charset": (b"<head>", b"<head><meta charset='utf-16'>"),
    }
    if case in changes:
        before, after = changes[case]
        assert before in raw
        raw = raw.replace(before, after, 1)
    if case == "duplicate_week":
        row = re.search(rb"<tr>\s*<td class='B6'>.*?</tr>", raw, re.DOTALL).group()
        raw = raw.replace(row, row + row, 1)
    if case == "truncated":
        raw = raw[: raw.rfind(b"</table>")]
    if case == "reversed_week":
        row = re.search(
            rb"<tr>\s*<td class='B6'>[^<]*2026 Aug-24 to Aug-28</td>.*?</tr>", raw, re.DOTALL
        ).group()
        later = re.search(
            rb"<tr>\s*<td class='B6'>[^<]*2026 Aug-31 to Sep- 4</td>.*?</tr>", raw, re.DOTALL
        ).group()
        raw = raw.replace(row, b"\0", 1).replace(later, row, 1).replace(b"\0", later, 1)
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)

    def fetch(url):
        return FetchedEiaHistory(
            raw,
            "https://example.com/" if case == "wrong_host" else url,
            200,
            "application/json"
            if case == "wrong_media"
            else "text/html; charset=utf-16"
            if case == "http_charset"
            else "text/html",
        )

    with pytest.raises(ValueError, match="eia_history_"):
        refresh_eia_history(
            paths,
            series_id="RBRTE",
            start_date=date(2026, 8, 31),
            end_date=date(2026, 9, 4),
            fetcher=fetch,
            definition_version="metric-catalog-v0002",
        )
    receipts = AcquisitionRepository(paths.database, paths.artifacts)
    assert len(receipts.history()) == 1
    receipt = receipts.history()[0]
    assert receipt.state == "failed"
    assert receipt.normalized_hash is None
    assert receipts.read_content(receipt.acquisition_id, "raw") == raw
    evidence = EvidenceRepository(paths.database)
    assert (
        evidence.metric_series(
            "EIA_BRENT_RBRTE",
            mode=AsOfMode.SYSTEM,
            as_of=datetime.now(UTC),
            definition_version="metric-catalog-v0002",
        )
        == ()
    )
    attempt = evidence.latest_retrieval_attempt(
        "EIA_BRENT_RBRTE",
        period="2026-09-04",
        as_of=datetime.now(UTC),
        definition_version="metric-catalog-v0002",
    )
    # Its structure check refused it, with the rule's reason (ticket 18).
    assert (attempt.outcome, attempt.safe_metadata["step"]) == ("structure_rejected", "structure")
    assert attempt.safe_metadata["rule_reason"]
    assert attempt.safe_metadata["acquisition_ids"] == receipt.acquisition_id
    assert attempt.safe_metadata["response_final_url"] == (
        "https://example.com/"
        if case == "wrong_host"
        else "https://www.eia.gov/dnav/pet/hist/RBRTED.htm"
    )
    assert attempt.safe_metadata["response_http_status"] == "200"


@pytest.mark.parametrize("day, missing", [("2026-08-31", 1), ("1900-01-01", 0)])
@pytest.mark.usefixtures("runtime_clock")
def test_empty_requested_window_reports_missing_values_without_zero_or_success(
    tmp_path: Path, day: str, missing: int
) -> None:
    from pring_cycle.eia_html import FetchedEiaHistory, refresh_eia_history

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    result = refresh_eia_history(
        paths,
        series_id="RBRTE",
        start_date=date.fromisoformat(day),
        end_date=date.fromisoformat(day),
        fetcher=lambda url: FetchedEiaHistory(original("RBRTE"), url, 200, "text/html"),
    )
    assert result.observation_count == 0 and result.missing_cell_count == missing
    assert result.status == "missing_values"
    assert result.condition == (
        "no_reported_values_in_source_cells"
        if missing
        else "no_source_calendar_cells_in_requested_window"
    )


@pytest.mark.usefixtures("runtime_clock")
def test_explicit_zero_and_four_missing_markers_keep_distinct_date_coordinates(
    tmp_path: Path,
) -> None:
    from pring_cycle.eia_html import FetchedEiaHistory, refresh_eia_history

    raw = original("RBRTE")
    old = re.search(
        rb"<tr>\s*<td class='B6'>[^<]*2026 Aug-31 to Sep- 4</td>.*?</tr>", raw, re.DOTALL
    ).group()
    new = (
        b"<tr><td class='B6'>2026 Aug-31 to Sep- 4</td>"
        + b"".join(
            b"<td class='B3'>" + cell + b"</td>" for cell in (b"0", b"-", b"--", b"NA", b"W")
        )
        + b"</tr>"
    )
    raw = raw.replace(old, new, 1)
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    result = refresh_eia_history(
        paths,
        series_id="RBRTE",
        start_date=date(2026, 8, 31),
        end_date=date(2026, 9, 4),
        fetcher=lambda url: FetchedEiaHistory(raw, url, 200, "text/html"),
        definition_version="metric-catalog-v0002",
    )
    assert result.observation_count == 1 and result.missing_cell_count == 4
    normalized = json.loads(
        AcquisitionRepository(paths.database, paths.artifacts).read_content(
            result.acquisition_id, "normalized"
        )
    )
    assert [(c["business_date"], c["state"], c["value"]) for c in normalized["cells"]] == [
        ("2026-08-31", "reported_value", 0.0),
        ("2026-09-01", "no_data_reported", None),
        ("2026-09-02", "not_applicable", None),
        ("2026-09-03", "not_available", None),
        ("2026-09-04", "withheld", None),
    ]


@pytest.mark.usefixtures("runtime_clock")
def test_later_html_snapshot_preserves_prior_values_and_source_request_identity(
    tmp_path: Path,
) -> None:
    from pring_cycle.eia_html import FetchedEiaHistory, refresh_eia_history

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    original_bytes = original("RBRTE")
    raw = original_bytes

    def fetch(url):
        return FetchedEiaHistory(raw, url, 200, "text/html")

    kwargs = {
        "series_id": "RBRTE",
        "start_date": date(2026, 9, 1),
        "end_date": date(2026, 9, 1),
        "definition_version": "metric-catalog-v0002",
        "fetcher": fetch,
    }
    first = refresh_eia_history(paths, **kwargs)
    before_revision = datetime.now(UTC)
    raw = raw.replace(b">96.02</td>", b">97.01</td>")
    second = refresh_eia_history(paths, **kwargs)
    assert first.acquisition_id != second.acquisition_id
    evidence = EvidenceRepository(paths.database)
    before = evidence.trace(first.observation_ids[0], mode=AsOfMode.SYSTEM, as_of=before_revision)
    after = evidence.trace(first.observation_ids[0], mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC))
    assert {c.value for c in before.claims} == {96.02}
    assert {c.value for c in after.claims} == {97.01}
    assert all(c.parsed_public_available_at is None for c in after.claims)
    assert first.observation_ids == second.observation_ids
    assert (
        AcquisitionRepository(paths.database, paths.artifacts).read_content(
            first.acquisition_id, "raw"
        )
        == original_bytes
    )


@pytest.mark.usefixtures("runtime_clock")
def test_html_source_failure_is_recorded_after_completion_without_fake_raw(tmp_path: Path) -> None:
    from pring_cycle.eia_html import refresh_eia_history

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    before = datetime.now(UTC)

    def fail(url):
        raise OSError("fixture network failure")

    with pytest.raises(OSError, match="fixture network failure"):
        refresh_eia_history(
            paths,
            series_id="RBRTE",
            start_date=date(2026, 8, 28),
            end_date=date(2026, 8, 28),
            fetcher=fail,
            definition_version="metric-catalog-v0002",
        )
    receipt = AcquisitionRepository(paths.database, paths.artifacts).history()[0]
    assert receipt.state == "failed" and receipt.raw_hash is None
    attempt = EvidenceRepository(paths.database).latest_retrieval_attempt(
        "EIA_BRENT_RBRTE",
        period="2026-08-28",
        as_of=datetime.now(UTC),
        definition_version="metric-catalog-v0002",
    )
    assert attempt.outcome == "source_failed"
    assert attempt.fetched_at >= before
    assert attempt.safe_metadata["acquisition_ids"] == receipt.acquisition_id


@pytest.mark.usefixtures("runtime_clock")
def test_http_error_keeps_actual_status_identity_and_error_body(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from email.message import Message
    from io import BytesIO
    from urllib.error import HTTPError

    from pring_cycle.eia_html import refresh_eia_history

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    raw = b'{"error":"fixture upstream denied"}'
    headers = Message()
    headers["Content-Type"] = "application/json"

    def fail(request, *, timeout):
        raise HTTPError(request.full_url, 403, "fixture denied", headers, BytesIO(raw))

    monkeypatch.setattr("pring_cycle.eia_html.open_no_redirects", fail)
    with pytest.raises(OSError, match="eia_history_response_http_status_invalid"):
        refresh_eia_history(
            paths,
            series_id="RBRTE",
            start_date=date(2026, 8, 28),
            end_date=date(2026, 8, 28),
            definition_version="metric-catalog-v0002",
        )
    repository = AcquisitionRepository(paths.database, paths.artifacts)
    receipt = repository.history()[0]
    assert receipt.state == "failed"
    assert repository.read_content(receipt.acquisition_id, "raw") == raw
    attempt = EvidenceRepository(paths.database).latest_retrieval_attempt(
        "EIA_BRENT_RBRTE",
        period="2026-08-28",
        as_of=datetime.now(UTC),
        definition_version="metric-catalog-v0002",
    )
    assert attempt.outcome == "source_failed"
    assert attempt.safe_metadata["response_http_status"] == "403"
    assert attempt.safe_metadata["response_media_type"] == "application/json"
    assert (
        attempt.safe_metadata["response_final_url"]
        == "https://www.eia.gov/dnav/pet/hist/RBRTED.htm"
    )


def real_history(series: str) -> bytes:
    """The history tables of release 9/23/2026 (see tests/fixtures/eia/README.md)."""
    name = {"RBRTE": "RBRTED_20260923.htm", "RWTC": "RWTCD_20260923.htm"}[series]
    return (Path(__file__).resolve().parents[1] / "fixtures" / "eia" / name).read_bytes()


def refresh_real(paths: RuntimePaths, series: str, raw: bytes, start: date, end: date) -> object:
    from pring_cycle.eia_html import FetchedEiaHistory, refresh_eia_history

    return refresh_eia_history(
        paths,
        series_id=series,
        start_date=start,
        end_date=end,
        definition_version="metric-catalog-v0002",
        fetcher=lambda url: FetchedEiaHistory(raw, url, 200, "text/html"),
    )


@pytest.mark.parametrize(
    ("series", "metric", "close"),
    [("RBRTE", "EIA_BRENT_RBRTE", 116.15), ("RWTC", "EIA_WTI_RWTC", 96.97)],
)
@pytest.mark.usefixtures("runtime_clock")
def test_weeks_absent_long_before_the_window_do_not_reject_the_table(
    tmp_path: Path, series: str, metric: str, close: float
) -> None:
    """The first real run lost Brent to weeks without quotes in 1994-2002 (and WTI in 1999)."""
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)

    result = refresh_real(paths, series, real_history(series), date(2026, 2, 15), date(2026, 9, 23))

    assert result.observation_count > 100  # type: ignore[attr-defined]
    points = EvidenceRepository(paths.database).metric_series(
        metric,
        mode=AsOfMode.SYSTEM,
        as_of=datetime.now(UTC),
        definition_version="metric-catalog-v0002",
    )
    assert {p.period_end: p.selected_value for p in points}["2026-09-21"] == close


@pytest.mark.usefixtures("runtime_clock")
def test_a_week_absent_inside_the_window_is_recorded_as_missing_days(tmp_path: Path) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    raw = real_history("RBRTE")
    row = re.search(
        rb"<tr>\s*<td class='B6'>[^<]*2026 Sep-14 to Sep-18</td>.*?</tr>", raw, re.DOTALL
    ).group()

    result = refresh_real(
        paths, "RBRTE", raw.replace(row, b"", 1), date(2026, 9, 7), date(2026, 9, 23)
    )

    receipts = AcquisitionRepository(paths.database, paths.artifacts)
    normalized = json.loads(receipts.read_content(result.acquisition_id, "normalized"))  # type: ignore[attr-defined]
    absent = [c["business_date"] for c in normalized["cells"] if c["state"] == "week_absent"]
    assert absent == [f"2026-09-{day}" for day in range(14, 19)]
    points = EvidenceRepository(paths.database).metric_series(
        "EIA_BRENT_RBRTE",
        mode=AsOfMode.SYSTEM,
        as_of=datetime.now(UTC),
        definition_version="metric-catalog-v0002",
    )
    held = {p.period_end for p in points}
    assert not held & set(absent)
    assert {"2026-09-11", "2026-09-21"} <= held
