from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest

from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.official_lpr import (
    ingest_lpr_document,
    parse_lpr_announcement,
)
from pring_cycle.release_calendar import lpr_release_calendar
from pring_cycle.runtime import RuntimePaths, initialize_runtime

OFFICIAL_URL = "https://www.chinamoney.com.cn/chinese/rdgz/20260820/3399885.html"
ANNOUNCEMENT = (Path(__file__).parents[1] / "fixtures/chinamoney_lpr_20260820.html").read_bytes()


def test_offline_contract_extracts_exact_release_identity_and_two_tenors() -> None:
    parsed = parse_lpr_announcement(
        ANNOUNCEMENT,
        source_url=OFFICIAL_URL,
        fetched_at=datetime(2026, 8, 20, 1, 2, tzinfo=UTC),
        expected_period="2026-08",
    )

    assert (
        parsed.release_event_id
        == "chinamoney-lpr:2026-08-20:" + hashlib.sha256(ANNOUNCEMENT).hexdigest()
    )
    assert parsed.period == "2026-08"
    assert parsed.release_at is not None
    assert parsed.release_at.isoformat() == "2026-08-20T09:00:00+08:00"
    assert [(item.tenor, item.value) for item in parsed.observations] == [
        ("1y", 3.0),
        ("5y_plus", 3.5),
    ]


@pytest.mark.parametrize(
    ("content", "url", "message"),
    [
        (ANNOUNCEMENT, "https://example.com/20260820/1.html", "lpr_source_url_not_official"),
        (
            ANNOUNCEMENT.replace(b"3.5%", b"3.0%", 1).replace(
                b"5\xe5\xb9\xb4", b"4\xe5\xb9\xb4", 1
            ),
            OFFICIAL_URL,
            "lpr_5y_plus_value_missing",
        ),
        (
            ANNOUNCEMENT.replace(b"2026-08-20 09:00", b"2026-08-21 09:00"),
            OFFICIAL_URL,
            "lpr_fetched_before_public_release",
        ),
        (
            ANNOUNCEMENT.replace(b"2026-08-20 09:00", b"2026-08-20 10:00"),
            OFFICIAL_URL,
            "lpr_fetched_before_public_release",
        ),
    ],
)
def test_offline_contract_fails_closed_on_wrong_origin_or_malformed_identity(
    content: bytes,
    url: str,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        parse_lpr_announcement(
            content,
            source_url=url,
            fetched_at=datetime(2026, 8, 20, 1, 2, tzinfo=UTC),
            expected_period="2026-08",
        )


def test_certified_ingest_persists_artifact_claims_trace_and_release_read_model(
    tmp_path: Path,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)

    result = ingest_lpr_document(
        paths,
        ANNOUNCEMENT,
        source_url=OFFICIAL_URL,
        fetched_at=datetime(2026, 8, 20, 1, 2, tzinfo=UTC),
        expected_period="2026-08",
        clock=lambda: datetime(2026, 8, 20, 1, 2, tzinfo=UTC),
    )
    evidence = EvidenceRepository(paths.database)
    trace = evidence.trace(
        result.observation_ids[0],
        mode=AsOfMode.SYSTEM,
        as_of=datetime(2026, 8, 20, 2, tzinfo=UTC),
    )
    events = evidence.release_events(metric_id="CN_LPR_1Y_5Y")

    assert result.status == "stored"
    assert result.observation_count == 2
    assert len(result.artifact_hash) == 64
    assert trace.metric_id == "CN_LPR_1Y_5Y"
    assert trace.claims[0].provider == "中国货币网"
    assert trace.claims[0].certification_status == "certified"
    assert events[0].observation_count == 2
    assert events[0].period == "2026-08"


def test_calendar_before_window_carries_previous_release_without_retrieval(
    tmp_path: Path,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    july = ANNOUNCEMENT.replace("2026年8月20日".encode(), "2026年7月20日".encode()).replace(
        b"2026-08-20", b"2026-07-20"
    )
    ingest_lpr_document(
        paths,
        july,
        source_url="https://www.chinamoney.com.cn/chinese/rdgz/20260720/3377000.html",
        fetched_at=datetime(2026, 7, 20, 1, 2, tzinfo=UTC),
        expected_period="2026-07",
        clock=lambda: datetime(2026, 7, 20, 1, 2, tzinfo=UTC),
    )

    event = lpr_release_calendar(
        EvidenceRepository(paths.database),
        period="2026-08",
        as_of=datetime(2026, 8, 19, tzinfo=UTC),
    )[0]

    assert event.status == "awaiting_release"
    assert event.carried_period == "2026-07"
    assert event.observation_count == 0
    assert event.next_check_at is not None


def test_repeated_import_appends_receipt_and_preserves_earlier_availability(
    tmp_path: Path,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    first = ingest_lpr_document(
        paths,
        ANNOUNCEMENT,
        source_url=OFFICIAL_URL,
        fetched_at=datetime(2026, 8, 20, 1, 2, tzinfo=UTC),
        expected_period="2026-08",
        clock=lambda: datetime(2026, 8, 20, 1, 2, tzinfo=UTC),
    )
    repeated = ingest_lpr_document(
        paths,
        ANNOUNCEMENT,
        source_url=OFFICIAL_URL,
        fetched_at=datetime(2026, 8, 20, 2, tzinfo=UTC),
        expected_period="2026-08",
        clock=lambda: datetime(2026, 8, 20, 2, tzinfo=UTC),
    )
    trace = EvidenceRepository(paths.database).trace(
        first.observation_ids[0],
        mode=AsOfMode.SYSTEM,
        as_of=datetime(2026, 8, 20, 3, tzinfo=UTC),
    )

    assert repeated.observation_ids == first.observation_ids
    assert repeated.claim_ids != first.claim_ids
    assert len(trace.claims) == 1
    assert trace.claims[0].available_at == datetime(2026, 8, 20, 2, tzinfo=UTC)
    earlier = EvidenceRepository(paths.database).trace(
        first.observation_ids[0],
        mode=AsOfMode.SYSTEM,
        as_of=datetime(2026, 8, 20, 1, 2, tzinfo=UTC),
    )
    assert earlier.claims[0].claim_id == first.claim_ids[0]
    assert earlier.claims[0].available_at == datetime(2026, 8, 20, 1, 2, tzinfo=UTC)




def test_calendar_uses_visible_revision_time_after_publication_is_restored(tmp_path: Path) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    times = (
        datetime(2026, 8, 20, 2, tzinfo=UTC),
        datetime(2026, 8, 21, 2, tzinfo=UTC),
        datetime(2026, 8, 22, 2, tzinfo=UTC),
    )
    contents = (
        ANNOUNCEMENT,
        ANNOUNCEMENT.replace(b"3.0%", b"3.1%"),
        ANNOUNCEMENT.replace(b"3.0%", b"3.2%").replace(b"2026-08-20 09:00", b"2026-08-22 09:00"),
    )
    imported = []
    for acquired_at, content in zip(times, contents, strict=True):

        def clock(value: datetime = acquired_at) -> datetime:
            return value

        imported.append(
            ingest_lpr_document(
                paths,
                content,
                source_url=OFFICIAL_URL,
                fetched_at=acquired_at,
                expected_period="2026-08",
                clock=clock,
            )
        )
    for cutoff, mode, expected_index, expected_public in (
        (times[1], AsOfMode.SYSTEM, 1, None),
        (times[1], AsOfMode.PUBLIC, 0, datetime(2026, 8, 20, 1, tzinfo=UTC)),
        (times[2], AsOfMode.SYSTEM, 2, datetime(2026, 8, 22, 1, tzinfo=UTC)),
        (times[2], AsOfMode.PUBLIC, 2, datetime(2026, 8, 22, 1, tzinfo=UTC)),
    ):
        event = lpr_release_calendar(
            EvidenceRepository(paths.database), period="2026-08", as_of=cutoff, as_of_mode=mode
        )[0]
        assert event.status == "current"
        assert event.public_available_at == expected_public
        assert event.available_at == times[expected_index]
        assert event.source_reference == (
            OFFICIAL_URL + "#sha256=" + imported[expected_index].artifact_hash
        )
