"""Audit ticket 09: rates the old ingest left out of stored OMO notices are restored from the
originals already on file, through today's ingest path, with no request made."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.acquisition import AcquisitionRepository
from pring_cycle.evidence import (
    AsOfMode,
    EvidenceRepository,
    EvidenceValueState,
    SourceClaimInput,
)
from pring_cycle.models import ModelRepository, effective_model_manifest
from pring_cycle.official_context import (
    FetchedOfficialContextDocument,
    OfficialReprocessResult,
    official_member,
    refresh_official_context_document,
    reprocess_stored_official_releases,
)
from pring_cycle.runtime import RuntimePaths, initialize_runtime

FIXTURES = Path(__file__).parents[1] / "fixtures"
OMO_COLUMN = "https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/125431/125475/"
REPO_0923 = OMO_COLUMN + "2026092308513432696/index.html"
ZERO_0603 = OMO_COLUMN + "2026060308560312345/index.html"
# 6/3's notice as the PBC wrote it: no operation, so no rate, only the amounts (zero).
AMOUNT_ONLY_NOTICE = """
<html><body>
  <h1>公开市场业务交易公告 [2026]第105号</h1>
  <p>文章来源： 2026-06-03 09:20:30</p>
  <p>根据公开市场业务一级交易商的需求，2026年6月3日7天期逆回购操作量为零。具体情况如下：</p>
  <table>
    <tr><th>逆回购操作情况 期限</th><th>投标量</th><th>中标量</th></tr>
    <tr><td>7 天</td><td>0 亿元</td><td>0 亿元</td></tr>
  </table>
</body></html>
""".encode()
RATE = official_member("CN_OMO_7D_RATE", {})


def _rate_notice(day: str, rate: str, amount: str = "80") -> bytes:
    """A notice as the PBC writes one, with the day's rate (``1. 40``) beside the amount."""
    year, month, date = (int(part) for part in day.split("-"))
    return f"""
<html><body>
  <h1>公开市场业务交易公告 [2026]第187号</h1>
  <p>文章来源： {day} 09:20:30</p>
  <p>{year}年{month}月{date}日中国人民银行开展了80亿元7天期逆回购操作。</p>
  <table>
    <tr><th>7天期逆回购操作情况 期限</th><th>操作 利率</th><th>投标量</th><th>中标量</th></tr>
    <tr><td>7 天</td><td>{rate} %</td><td>{amount} 亿元</td><td>{amount} 亿元</td></tr>
  </table>
</body></html>
""".encode()


def _runtime(tmp_path: Path) -> tuple[RuntimePaths, str]:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    models = ModelRepository(paths.database)
    models.register(effective_model_manifest())
    models.activate(str(effective_model_manifest()["model_version_id"]), explicitly_approved=True)
    return paths, str(effective_model_manifest()["metric_catalog_version"])


def _stored_as_the_old_ingest_did(
    paths: RuntimePaths, version: str, url: str, period: str, content: bytes
) -> str:
    """Fetch and store a notice the way the code before e10db1b did: the amount the
    retrieval asked for, without the rate the same page states."""
    acquisition_ids: list[str] = []
    refresh_official_context_document(
        paths,
        family="pbc_omo_notice",
        source_url=url,
        expected_period=period,
        fetched_at=datetime.now(UTC),
        fetcher=_serving(content),
        definition_version=version,
        on_acquisition_started=acquisition_ids.append,
        metric_ids=("CN_OMO_7D_AMOUNT",),
        held_members=frozenset({RATE}),
    )
    return acquisition_ids[-1]


def _serving(content: bytes) -> Callable[[str], FetchedOfficialContextDocument]:
    return lambda url: FetchedOfficialContextDocument(content, "text/html", url, 200)


@pytest.fixture
def no_requests(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    requested: list[str] = []

    def refuse(url: str, *args: object, **kwargs: object) -> object:
        requested.append(str(url))
        raise AssertionError("reprocessing_made_a_request")

    monkeypatch.setattr("pring_cycle.official_context._fetch_official_context_document", refuse)
    monkeypatch.setattr("pring_cycle.official_context.urlopen", refuse)
    return requested


def _series(
    paths: RuntimePaths, metric_id: str, version: str, as_of: datetime
) -> dict[str, float | None]:
    return {
        point.period_end: point.selected_value
        for point in EvidenceRepository(paths.database).metric_series(
            metric_id, mode=AsOfMode.SYSTEM, as_of=as_of, definition_version=version
        )
    }


def _claims(paths: RuntimePaths) -> list[dict[str, Any]]:
    import sqlite3

    with sqlite3.connect(paths.database) as connection:
        connection.row_factory = sqlite3.Row
        return [
            dict(row)
            for row in connection.execute(
                "SELECT * FROM source_claim WHERE metric_id LIKE 'CN_OMO_7D_%' ORDER BY rowid"
            )
        ]


def _retrieval_attempts(paths: RuntimePaths) -> int:
    import sqlite3

    with sqlite3.connect(paths.database) as connection:
        return int(connection.execute("SELECT COUNT(*) FROM retrieval_attempt").fetchone()[0])


def test_a_stored_notice_restores_the_rate_its_ingest_left_out(
    tmp_path: Path, no_requests: list[str]
) -> None:
    paths, version = _runtime(tmp_path)
    content = (FIXTURES / "pbc_omo_notice" / "2026092308513432696.html").read_bytes()
    acquisition_id = _stored_as_the_old_ingest_did(paths, version, REPO_0923, "2026-09-23", content)
    receipts = AcquisitionRepository(paths.database, paths.artifacts)
    receipt = receipts.get(acquisition_id)
    stored_before = _claims(paths)
    attempts_before = _retrieval_attempts(paths)
    ingest_before = receipts.ingest_result(acquisition_id)
    assert {row["metric_id"] for row in stored_before} == {"CN_OMO_7D_AMOUNT"}
    reprocessed_at = datetime.now(UTC) + timedelta(minutes=5)

    result = reprocess_stored_official_releases(
        paths,
        metric_ids=("CN_OMO_7D_RATE",),
        start="2026-09-01",
        end="2026-09-30",
        definition_version=version,
        clock=lambda: reprocessed_at,
    )

    assert no_requests == []
    assert result.network_requests == 0
    assert [(item.period, item.acquisition_id, item.metric_ids) for item in result.restored] == [
        ("2026-09-23", acquisition_id, ("CN_OMO_7D_RATE",))
    ]
    claims = _claims(paths)
    # The amount already stored is left as it was; only the rate is added.
    assert claims[: len(stored_before)] == stored_before
    (rate,) = claims[len(stored_before) :]
    amount = stored_before[0]
    assert (rate["metric_id"], rate["period_end"], rate["value"]) == (
        "CN_OMO_7D_RATE",
        "2026-09-23",
        1.4,
    )
    # Same announcement and original as the amount; announced when the PBC published it,
    # fetched when the original was, and available to this system only from reprocessing.
    assert rate["source_reference"] == amount["source_reference"]
    assert rate["release_event_id"] == amount["release_event_id"]
    assert rate["public_available_at"] == amount["public_available_at"] is not None
    assert receipt.received_at is not None
    assert rate["fetched_at"] == receipt.received_at.isoformat() == amount["fetched_at"]
    assert rate["available_at"] == reprocessed_at.isoformat() > amount["available_at"]
    assert result.restored[0].claim_ids == (rate["claim_id"],)
    assert (
        EvidenceRepository(paths.database).source_claim_originals(rate["claim_id"])[0][0] == receipt
    )
    # A system cutoff before the reprocessing does not see the rate; one after does.
    assert _series(paths, "CN_OMO_7D_RATE", version, reprocessed_at - timedelta(seconds=1)) == {}
    assert _series(paths, "CN_OMO_7D_RATE", version, reprocessed_at) == {"2026-09-23": 1.4}
    # Nothing was retrieved, and the original's receipt keeps what its ingest said.
    assert _retrieval_attempts(paths) == attempts_before
    assert receipts.ingest_result(acquisition_id) == ingest_before


def test_reprocessing_again_stores_nothing_more(tmp_path: Path, no_requests: list[str]) -> None:
    paths, version = _runtime(tmp_path)
    content = (FIXTURES / "pbc_omo_notice" / "2026092308513432696.html").read_bytes()
    # The notice was fetched twice; its rate comes back once.
    _stored_as_the_old_ingest_did(paths, version, REPO_0923, "2026-09-23", content)
    _stored_as_the_old_ingest_did(paths, version, REPO_0923, "2026-09-23", content)

    def reprocess(at: datetime) -> OfficialReprocessResult:
        return reprocess_stored_official_releases(
            paths,
            metric_ids=("CN_OMO_7D_RATE",),
            start="2026-09-01",
            end="2026-09-30",
            definition_version=version,
            clock=lambda: at,
        )

    first = reprocess(datetime.now(UTC))
    after_first = _claims(paths)
    second = reprocess(datetime.now(UTC) + timedelta(hours=1))

    assert len(first.restored) == 1
    assert first.examined == second.examined == 2
    assert second.restored == ()
    assert _claims(paths) == after_first
    assert [row["metric_id"] for row in after_first].count("CN_OMO_7D_RATE") == 1
    assert no_requests == []


def _store_today(paths: RuntimePaths, version: str, content: bytes) -> None:
    """Store a 9/23 notice whole, as today's ingest does."""
    refresh_official_context_document(
        paths,
        family="pbc_omo_notice",
        source_url=REPO_0923,
        expected_period="2026-09-23",
        fetched_at=datetime.now(UTC),
        fetcher=_serving(content),
        definition_version=version,
        metric_ids=("CN_OMO_7D_AMOUNT",),
    )


def _reprocess_september(paths: RuntimePaths, version: str) -> OfficialReprocessResult:
    return reprocess_stored_official_releases(
        paths,
        metric_ids=("CN_OMO_7D_RATE",),
        start="2026-09-01",
        end="2026-09-30",
        definition_version=version,
        clock=lambda: datetime.now(UTC) + timedelta(minutes=5),
    )


def _skips(result: OfficialReprocessResult) -> list[str]:
    return [item.reason for item in result.skipped]


def test_an_older_notice_is_not_restored_beside_a_revision_already_held(
    tmp_path: Path, no_requests: list[str]
) -> None:
    """9/23's first notice (1.4) lost its rate; a revised one (1.5) was stored whole. Stored
    now, the old rate would be the newest claim of its source and turn the selection back."""
    paths, version = _runtime(tmp_path)
    _stored_as_the_old_ingest_did(
        paths, version, REPO_0923, "2026-09-23", _rate_notice("2026-09-23", "1. 40")
    )
    _store_today(paths, version, _rate_notice("2026-09-23", "1. 50"))
    later = datetime.now(UTC) + timedelta(hours=1)
    stored = _claims(paths)
    assert _series(paths, "CN_OMO_7D_RATE", version, later) == {"2026-09-23": 1.5}

    result = _reprocess_september(paths, version)

    assert result.restored == ()
    assert _claims(paths) == stored
    assert _series(paths, "CN_OMO_7D_RATE", version, later) == {"2026-09-23": 1.5}
    assert no_requests == []


def test_a_notice_a_later_original_revised_is_left_to_a_run(
    tmp_path: Path, no_requests: list[str]
) -> None:
    """Both of 9/23's notices lost their rate, and the second revised the amount (80 to 90)
    published no later. The ingest would read the first against the held revision and take
    it for a revision itself, so neither is restored: a run decides."""
    paths, version = _runtime(tmp_path)
    for amount in ("80", "90"):
        _stored_as_the_old_ingest_did(
            paths, version, REPO_0923, "2026-09-23", _rate_notice("2026-09-23", "1. 40", amount)
        )
    stored = _claims(paths)

    result = _reprocess_september(paths, version)

    assert result.restored == ()
    assert _skips(result) == ["revised_by_another_original"] * 2
    assert _claims(paths) == stored
    assert no_requests == []


def test_originals_stating_different_rates_are_left_to_a_run(
    tmp_path: Path, no_requests: list[str]
) -> None:
    paths, version = _runtime(tmp_path)
    for rate in ("1. 40", "1. 50"):
        _stored_as_the_old_ingest_did(
            paths, version, REPO_0923, "2026-09-23", _rate_notice("2026-09-23", rate)
        )
    stored = _claims(paths)

    result = _reprocess_september(paths, version)

    assert result.restored == ()
    assert _skips(result) == ["revised_by_another_original"] * 2
    assert _claims(paths) == stored
    assert no_requests == []


def test_a_rate_another_source_delivered_is_not_restated(
    tmp_path: Path, no_requests: list[str]
) -> None:
    paths, version = _runtime(tmp_path)
    content = (FIXTURES / "pbc_omo_notice" / "2026092308513432696.html").read_bytes()
    _stored_as_the_old_ingest_did(paths, version, REPO_0923, "2026-09-23", content)
    delivered_at = datetime(2026, 9, 23, 2, tzinfo=UTC)
    EvidenceRepository(paths.database).append_source_claim(
        SourceClaimInput(
            metric_id="CN_OMO_7D_RATE",
            definition_version=version,
            period_kind="business_day",
            period_start="2026-09-23",
            period_end="2026-09-23",
            dimensions={},
            value=1.4,
            value_state=EvidenceValueState.REPORTED_VALUE,
            unit="percent",
            provider="another_source",
            source_reference="another_source:omo:2026-09-23",
            release_event_id="another_source:omo:2026-09-23",
            release_at=delivered_at,
            public_available_at=delivered_at,
            fetched_at=delivered_at,
            available_at=delivered_at,
            quality_status="validated",
        )
    )
    stored = _claims(paths)

    result = reprocess_stored_official_releases(
        paths,
        metric_ids=("CN_OMO_7D_RATE",),
        start="2026-09-01",
        end="2026-09-30",
        definition_version=version,
    )

    assert result.restored == ()
    assert _claims(paths) == stored
    assert no_requests == []


def test_a_notice_with_only_amounts_restores_no_rate(
    tmp_path: Path, no_requests: list[str]
) -> None:
    paths, version = _runtime(tmp_path)
    _stored_as_the_old_ingest_did(paths, version, ZERO_0603, "2026-06-03", AMOUNT_ONLY_NOTICE)
    stored = _claims(paths)
    assert [(row["metric_id"], row["value"]) for row in stored] == [("CN_OMO_7D_AMOUNT", 0.0)]

    result = reprocess_stored_official_releases(
        paths,
        metric_ids=("CN_OMO_7D_RATE",),
        start="2026-06-01",
        end="2026-06-30",
        definition_version=version,
    )

    assert result.examined == 1
    assert result.restored == ()
    assert _claims(paths) == stored
    assert no_requests == []


def test_a_notice_outside_the_period_range_is_left_alone(
    tmp_path: Path, no_requests: list[str]
) -> None:
    """Values retention removed before the range are not brought back."""
    paths, version = _runtime(tmp_path)
    content = (FIXTURES / "pbc_omo_notice" / "2026092308513432696.html").read_bytes()
    _stored_as_the_old_ingest_did(paths, version, REPO_0923, "2026-09-23", content)
    stored = _claims(paths)

    result = reprocess_stored_official_releases(
        paths,
        metric_ids=("CN_OMO_7D_RATE",),
        start="2026-09-24",
        end="2026-10-09",
        definition_version=version,
    )

    assert result.restored == ()
    assert _claims(paths) == stored


def test_the_maintenance_command_reports_what_it_restored(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], no_requests: list[str]
) -> None:
    from pring_cycle.cli import main

    paths, version = _runtime(tmp_path)
    content = (FIXTURES / "pbc_omo_notice" / "2026092308513432696.html").read_bytes()
    acquisition_id = _stored_as_the_old_ingest_did(paths, version, REPO_0923, "2026-09-23", content)
    command = [
        "official-reprocess",
        "--runtime-root",
        str(tmp_path / "runtime"),
        "--metric",
        "CN_OMO_7D_RATE",
        "--start",
        "2026-04-13",
        "--end",
        "2026-10-09",
        "--definition-version",
        version,
        "--json",
    ]

    main(command)
    first = json.loads(capsys.readouterr().out)
    main(command)
    second = json.loads(capsys.readouterr().out)

    assert first["status"] == "completed"
    assert first["family"] == "pbc_omo_notice"
    assert first["network_requests"] == 0
    assert [(item["period"], item["acquisition_id"]) for item in first["restored"]] == [
        ("2026-09-23", acquisition_id)
    ]
    assert first["restored_claim_count"] == 1
    assert (second["restored"], second["restored_claim_count"]) == ([], 0)
    assert no_requests == []
