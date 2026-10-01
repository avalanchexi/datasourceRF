from __future__ import annotations

import csv
import hashlib
import json
from collections.abc import Callable
from datetime import UTC, date, datetime
from io import BytesIO, StringIO
from pathlib import Path

import pytest

from pring_cycle.acquisition import AcquisitionRepository
from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime


@pytest.mark.usefixtures("runtime_clock")
def test_official_csv_creates_two_traceable_candidates_with_unknown_public_time(
    tmp_path: Path,
) -> None:
    from pring_cycle.treasury_context import FetchedTreasuryYieldCsv, refresh_treasury_yields

    raw_hash = "a14a321adffded36dfd9ab1aec72cc81423aeca271110f76569d37dd02ca4ee5"
    repository = Path(__file__).resolve().parents[2]
    raw = (
        repository
        / ".scratch/pring-data-acquisition-repair/evidence-14-treasury-followup"
        / raw_hash
    ).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == raw_hash
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)

    def fetch(url: str) -> FetchedTreasuryYieldCsv:
        return FetchedTreasuryYieldCsv(raw, url, 200, "text/csv; charset=UTF-8")

    result = refresh_treasury_yields(
        paths,
        start_date=date(2026, 9, 4),
        end_date=date(2026, 9, 4),
        definition_version="metric-catalog-v0002",
        fetcher=fetch,
    )
    assert result.status == "stored_candidate" and result.observation_count == 2
    assert result.missing_cell_count == 0
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    receipt = acquisitions.get(result.acquisition_id)
    assert acquisitions.read_content(receipt.acquisition_id, "raw") == raw
    # Its receipt says the values entered the evidence store (ticket 18).
    assert acquisitions.ingest_result(receipt.acquisition_id) == ("accepted", None)
    normalized = json.loads(acquisitions.read_content(receipt.acquisition_id, "normalized"))
    assert normalized["source_timezone"] == "America/New_York"
    evidence = EvidenceRepository(paths.database)
    for metric, expected in (("UST2Y_NOMINAL_YIELD", 4.37), ("UST10Y_NOMINAL_YIELD", 4.78)):
        points = evidence.metric_series(
            metric,
            mode=AsOfMode.SYSTEM,
            as_of=datetime.now(UTC),
            definition_version="metric-catalog-v0002",
        )
        assert len(points) == 1
        point = points[0]
        assert point.period_start == point.period_end == "2026-09-04"
        assert len(point.claims) == 1
        claim = point.claims[0]
        assert claim.value == expected and claim.unit == "percent"
        assert claim.release_at is None and claim.parsed_public_available_at is None
        assert claim.certification_status == "awaiting_source_certification"
        assert claim.available_at >= receipt.validated_at
        trace = evidence.trace(point.observation_id, mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC))
        assert trace.acquisition_status == "linked"
        assert {item.acquisition_id for item in trace.acquisitions} == {receipt.acquisition_id}


@pytest.mark.usefixtures("runtime_clock")
def test_public_cli_acquires_treasury_candidates_without_an_account(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from pring_cycle.cli import main

    raw = (
        Path(__file__).resolve().parents[2]
        / ".scratch/pring-data-acquisition-repair/evidence-14-treasury-followup"
        / "a14a321adffded36dfd9ab1aec72cc81423aeca271110f76569d37dd02ca4ee5"
    ).read_bytes()

    class Response(BytesIO):
        status = 200
        headers = {"Content-Type": "text/csv; charset=UTF-8"}

        def __init__(self, url: str):
            super().__init__(raw)
            self.url = url

        def geturl(self):
            return self.url

    def fetch(request, *, timeout):
        return Response(request.full_url)

    monkeypatch.setattr("pring_cycle.treasury_context.open_no_redirects", fetch)
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    main(
        [
            "treasury-csv-refresh",
            "--runtime-root",
            str(tmp_path / "runtime"),
            "--start",
            "2026-09-04",
            "--end",
            "2026-09-04",
            "--definition-version",
            "metric-catalog-v0002",
            "--json",
        ]
    )
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "stored_candidate" and result["observation_count"] == 2
    assert len(AcquisitionRepository(paths.database, paths.artifacts).history()) == 1


@pytest.mark.usefixtures("runtime_clock")
def test_requested_historical_window_keeps_the_newer_reported_source_period(tmp_path: Path) -> None:
    from pring_cycle.treasury_context import FetchedTreasuryYieldCsv, refresh_treasury_yields

    raw = (
        Path(__file__).resolve().parents[2]
        / ".scratch/pring-data-acquisition-repair/evidence-14-treasury-followup"
        / "a14a321adffded36dfd9ab1aec72cc81423aeca271110f76569d37dd02ca4ee5"
    ).read_bytes()
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    result = refresh_treasury_yields(
        paths,
        start_date=date(2026, 8, 28),
        end_date=date(2026, 8, 28),
        definition_version="metric-catalog-v0002",
        fetcher=lambda url: FetchedTreasuryYieldCsv(raw, url, 200, "text/csv"),
    )
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    batch = json.loads(acquisitions.read_content(result.acquisition_id, "normalized"))
    assert batch["latest_reported_periods"] == {
        "UST2Y_NOMINAL_YIELD": "2026-09-04",
        "UST10Y_NOMINAL_YIELD": "2026-09-04",
    }
    evidence = EvidenceRepository(paths.database)
    for metric, expected in (("UST2Y_NOMINAL_YIELD", 4.34), ("UST10Y_NOMINAL_YIELD", 4.73)):
        points = evidence.metric_series(
            metric,
            mode=AsOfMode.SYSTEM,
            as_of=datetime.now(UTC),
            definition_version="metric-catalog-v0002",
        )
        assert {p.period_end: p.claims[0].value for p in points} == {"2026-08-28": expected}
        attempt = evidence.latest_retrieval_attempt(
            metric,
            period="2026-08-28",
            as_of=datetime.now(UTC),
            definition_version="metric-catalog-v0002",
        )
        assert attempt.safe_metadata["latest_source_period"] == "2026-09-04"


def source_csv() -> bytes:
    digest = "a14a321adffded36dfd9ab1aec72cc81423aeca271110f76569d37dd02ca4ee5"
    raw = (
        Path(__file__).resolve().parents[2]
        / ".scratch/pring-data-acquisition-repair/evidence-14-treasury-followup"
        / digest
    ).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == digest
    return raw


def csv_bytes(rows: list[list[str]]) -> bytes:
    output = StringIO()
    csv.writer(output).writerows(rows)
    return output.getvalue().encode()


@pytest.mark.parametrize("case", ["reordered", "zero", "missing_2y"])
@pytest.mark.usefixtures("runtime_clock")
def test_columns_and_missing_values_keep_each_tenors_own_evidence(
    tmp_path: Path, case: str
) -> None:
    from pring_cycle.treasury_context import FetchedTreasuryYieldCsv, refresh_treasury_yields

    rows = list(csv.reader(StringIO(source_csv().decode())))
    two = rows[0].index("2 Yr")
    if case == "zero":
        rows[1][two] = "0.00"
    elif case == "missing_2y":
        rows[1][two] = "N/A"
    else:
        rows = [list(reversed(row)) for row in rows]
    raw = csv_bytes(rows)
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    result = refresh_treasury_yields(
        paths,
        start_date=date(2026, 9, 4),
        end_date=date(2026, 9, 4),
        definition_version="metric-catalog-v0002",
        fetcher=lambda url: FetchedTreasuryYieldCsv(raw, url, 200, "text/csv"),
    )
    evidence = EvidenceRepository(paths.database)
    assert result.observation_count == (1 if case == "missing_2y" else 2)
    assert result.missing_cell_count == (1 if case == "missing_2y" else 0)
    for metric, expected in (
        ("UST2Y_NOMINAL_YIELD", 0.0 if case == "zero" else 4.37),
        ("UST10Y_NOMINAL_YIELD", 4.78),
    ):
        points = evidence.metric_series(
            metric,
            mode=AsOfMode.SYSTEM,
            as_of=datetime.now(UTC),
            definition_version="metric-catalog-v0002",
        )
        missing = metric == "UST2Y_NOMINAL_YIELD" and case == "missing_2y"
        assert [point.claims[0].value for point in points] == ([] if missing else [expected])
        attempt = evidence.latest_retrieval_attempt(
            metric,
            period="2026-09-04",
            as_of=datetime.now(UTC),
            definition_version="metric-catalog-v0002",
        )
        # An empty delivery is no failure; it says so (ticket 18).
        assert attempt.outcome == "succeeded"
        assert attempt.safe_metadata["completeness"] == ("source_empty" if missing else "complete")
    normalized = json.loads(
        AcquisitionRepository(paths.database, paths.artifacts).read_content(
            result.acquisition_id, "normalized"
        )
    )
    if case == "missing_2y":
        cell = next(
            cell for cell in normalized["cells"] if cell["metric_id"] == "UST2Y_NOMINAL_YIELD"
        )
        assert cell["state"] == "not_available" and cell["source_text"] == "N/A"
        assert normalized["latest_reported_periods"]["UST2Y_NOMINAL_YIELD"] == "2026-09-03"


@pytest.mark.parametrize(
    "case",
    [
        "wrong_host",
        "wrong_curve",
        "http_403",
        "wrong_media",
        "bad_charset",
        "charset_repeat",
        "ascii_with_nonascii",
        "missing_column",
        "duplicate_column",
        "short_row",
        "duplicate_date",
        "other_year",
        "malformed_quotes",
        "negative",
        "nonfinite",
        "empty_document",
        "header_only",
    ],
)
@pytest.mark.usefixtures("runtime_clock")
def test_invalid_source_response_is_retained_but_never_creates_a_claim(
    tmp_path: Path, case: str
) -> None:
    from pring_cycle.treasury_context import FetchedTreasuryYieldCsv, refresh_treasury_yields

    raw = source_csv()
    rows = list(csv.reader(StringIO(raw.decode())))
    two = rows[0].index("2 Yr")
    if case == "missing_column":
        rows[0][two] = "3 Yr alias"
    elif case == "duplicate_column":
        rows[0][-1] = "2 Yr"
    elif case == "short_row":
        rows[1].pop()
    elif case == "duplicate_date":
        rows.append(rows[1].copy())
    elif case == "other_year":
        rows[1][0] = "09/04/2025"
    elif case in {"negative", "nonfinite"}:
        rows[1][two] = "-0.01" if case == "negative" else "NaN"
    raw = csv_bytes(rows)
    if case == "malformed_quotes":
        raw = raw.splitlines(keepends=True)[0] + b'"unterminated'
    elif case == "empty_document":
        raw = b""
    elif case == "header_only":
        raw = raw.splitlines(keepends=True)[0]
    elif case == "http_403":
        raw = b'{"error":"denied"}'
    elif case == "ascii_with_nonascii":
        raw += "\u00e9".encode()
    status = 403 if case == "http_403" else 200
    media = {
        "wrong_media": "text/html",
        "bad_charset": "text/csv; charset=utf-16",
        "charset_repeat": "text/csv; charset=utf-8; charset=ascii",
        "ascii_with_nonascii": "text/csv; charset=ascii",
    }.get(case, "text/csv")
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)

    def fetch(url: str) -> FetchedTreasuryYieldCsv:
        if case == "wrong_host":
            url = "https://example.com/data.csv"
        elif case == "wrong_curve":
            url = url.replace(
                "type=daily_treasury_yield_curve", "type=daily_treasury_real_yield_curve"
            )
        return FetchedTreasuryYieldCsv(raw, url, status, media)

    before = datetime.now(UTC)
    with pytest.raises((ValueError, OSError)):
        refresh_treasury_yields(
            paths,
            start_date=date(2026, 9, 4),
            end_date=date(2026, 9, 4),
            definition_version="metric-catalog-v0002",
            fetcher=fetch,
        )
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    receipt = acquisitions.history()[0]
    assert acquisitions.read_content(receipt.acquisition_id, "raw") == raw
    evidence = EvidenceRepository(paths.database)
    for metric in ("UST2Y_NOMINAL_YIELD", "UST10Y_NOMINAL_YIELD"):
        assert (
            evidence.metric_series(
                metric,
                mode=AsOfMode.SYSTEM,
                as_of=datetime.now(UTC),
                definition_version="metric-catalog-v0002",
            )
            == ()
        )
        attempt = evidence.latest_retrieval_attempt(
            metric,
            period="2026-09-04",
            as_of=datetime.now(UTC),
            definition_version="metric-catalog-v0002",
        )
        # An HTTP error is the source's, with its code; anything else the structure check's.
        assert attempt.outcome == ("source_failed" if case == "http_403" else "structure_rejected")
        if case == "http_403":
            assert attempt.safe_metadata["external_code"] == "403"
        assert attempt.fetched_at >= before
        assert attempt.safe_metadata["acquisition_ids"] == receipt.acquisition_id
        assert attempt.safe_metadata["response_http_status"] == str(status)
        assert attempt.safe_metadata["response_media_type"] == media


def test_later_snapshot_and_failed_request_preserve_prior_treasury_values(
    tmp_path: Path, acquisition_clock: Callable[[], datetime]
) -> None:
    from pring_cycle.treasury_context import FetchedTreasuryYieldCsv, refresh_treasury_yields

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    raw = source_csv()
    original = raw

    def fetch(url: str) -> FetchedTreasuryYieldCsv:
        return FetchedTreasuryYieldCsv(raw, url, 200, "text/csv")

    first = refresh_treasury_yields(
        paths,
        start_date=date(2026, 9, 4),
        end_date=date(2026, 9, 4),
        definition_version="metric-catalog-v0002",
        fetcher=fetch,
    )
    before_revision = acquisition_clock()
    rows = list(csv.reader(StringIO(raw.decode())))
    rows[1][rows[0].index("10 Yr")] = "4.80"
    raw = csv_bytes(rows)
    second = refresh_treasury_yields(
        paths,
        start_date=date(2026, 9, 4),
        end_date=date(2026, 9, 4),
        definition_version="metric-catalog-v0002",
        fetcher=fetch,
    )
    assert first.acquisition_id != second.acquisition_id
    evidence = EvidenceRepository(paths.database)
    for cutoff, expected in ((before_revision, 4.78), (acquisition_clock(), 4.80)):
        points = evidence.metric_series(
            "UST10Y_NOMINAL_YIELD",
            mode=AsOfMode.SYSTEM,
            as_of=cutoff,
            definition_version="metric-catalog-v0002",
        )
        assert points[0].claims[0].value == expected
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    assert acquisitions.read_content(first.acquisition_id, "raw") == original
    before_failure = acquisition_clock()

    def fail(url):
        raise OSError("source unavailable")

    with pytest.raises(OSError, match="source unavailable"):
        refresh_treasury_yields(
            paths,
            start_date=date(2026, 9, 4),
            end_date=date(2026, 9, 4),
            definition_version="metric-catalog-v0002",
            fetcher=fail,
        )
    receipt = acquisitions.history()[-1]
    assert receipt.raw_hash is None
    for metric in ("UST2Y_NOMINAL_YIELD", "UST10Y_NOMINAL_YIELD"):
        attempt = evidence.latest_retrieval_attempt(
            metric,
            period="2026-09-04",
            as_of=acquisition_clock(),
            definition_version="metric-catalog-v0002",
        )
        assert attempt.outcome == "source_failed" and attempt.fetched_at >= before_failure
        previous = evidence.latest_retrieval_attempt(
            metric,
            period="2026-09-04",
            as_of=before_failure,
            definition_version="metric-catalog-v0002",
        )
        assert previous.outcome == "succeeded"


@pytest.mark.usefixtures("runtime_clock")
def test_no_dates_in_requested_window_is_an_explicit_empty_candidate_result(tmp_path: Path) -> None:
    from pring_cycle.treasury_context import FetchedTreasuryYieldCsv, refresh_treasury_yields

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    result = refresh_treasury_yields(
        paths,
        start_date=date(2026, 9, 5),
        end_date=date(2026, 9, 6),
        definition_version="metric-catalog-v0002",
        fetcher=lambda url: FetchedTreasuryYieldCsv(source_csv(), url, 200, "text/csv"),
    )
    assert result.status == "missing_values" and result.observation_count == 0
    assert result.condition == "no_source_dates_in_requested_window"


@pytest.mark.usefixtures("runtime_clock")
def test_later_missing_cell_retains_the_old_value_identity_and_new_missing_receipt(
    tmp_path: Path,
) -> None:
    from pring_cycle.treasury_context import FetchedTreasuryYieldCsv, refresh_treasury_yields

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    raw = source_csv()

    def fetch(url):
        return FetchedTreasuryYieldCsv(raw, url, 200, "text/csv")

    first = refresh_treasury_yields(
        paths,
        start_date=date(2026, 9, 4),
        end_date=date(2026, 9, 4),
        definition_version="metric-catalog-v0002",
        fetcher=fetch,
    )
    evidence = EvidenceRepository(paths.database)
    old = evidence.metric_series(
        "UST2Y_NOMINAL_YIELD",
        mode=AsOfMode.SYSTEM,
        as_of=datetime.now(UTC),
        definition_version="metric-catalog-v0002",
    )[0]
    rows = list(csv.reader(StringIO(raw.decode())))
    rows[1][rows[0].index("2 Yr")] = "N/A"
    raw = csv_bytes(rows)
    second = refresh_treasury_yields(
        paths,
        start_date=date(2026, 9, 4),
        end_date=date(2026, 9, 4),
        definition_version="metric-catalog-v0002",
        fetcher=fetch,
    )
    assert second.observation_count == 1 and second.missing_cell_count == 1
    current = evidence.metric_series(
        "UST2Y_NOMINAL_YIELD",
        mode=AsOfMode.SYSTEM,
        as_of=datetime.now(UTC),
        definition_version="metric-catalog-v0002",
    )[0]
    assert current.claims[0].claim_id == old.claims[0].claim_id
    assert (
        current.claims[0].value == 4.37
        and current.claims[0].available_at == old.claims[0].available_at
    )
    trace = evidence.trace(current.observation_id, mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC))
    assert {item.acquisition_id for item in trace.acquisitions} == {first.acquisition_id}
    attempt = evidence.latest_retrieval_attempt(
        "UST2Y_NOMINAL_YIELD",
        period="2026-09-04",
        as_of=datetime.now(UTC),
        definition_version="metric-catalog-v0002",
    )
    assert (attempt.outcome, attempt.safe_metadata["completeness"]) == ("succeeded", "source_empty")
    assert attempt.safe_metadata["acquisition_ids"] == second.acquisition_id
    assert attempt.safe_metadata["observations"] == "0"


@pytest.mark.usefixtures("runtime_clock")
def test_http_error_transport_retains_the_actual_error_body(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from urllib.error import HTTPError

    from pring_cycle.treasury_context import refresh_treasury_yields

    body = b'{"error":"forbidden"}'

    def deny(request, *, timeout):
        raise HTTPError(
            request.full_url, 403, "Forbidden", {"Content-Type": "application/json"}, BytesIO(body)
        )

    monkeypatch.setattr("pring_cycle.treasury_context.open_no_redirects", deny)
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    with pytest.raises(OSError, match="treasury_csv_response_http_status_invalid"):
        refresh_treasury_yields(
            paths,
            start_date=date(2026, 9, 4),
            end_date=date(2026, 9, 4),
            definition_version="metric-catalog-v0002",
        )
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    receipt = acquisitions.history()[0]
    assert acquisitions.read_content(receipt.acquisition_id, "raw") == body
    attempt = EvidenceRepository(paths.database).latest_retrieval_attempt(
        "UST2Y_NOMINAL_YIELD",
        period="2026-09-04",
        as_of=datetime.now(UTC),
        definition_version="metric-catalog-v0002",
    )
    assert attempt.outcome == "source_failed"
    assert attempt.safe_metadata["response_http_status"] == "403"
    assert attempt.safe_metadata["response_media_type"] == "application/json"
