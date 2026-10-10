"""Audit 06: publications computed on a value read for the wrong period are kept as published,
marked affected, and linked to the later publication of their day that corrects them."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from pring_cycle.dashboard import _report_reader, dashboard_shell
from pring_cycle.projections import ANALYTICAL_DATASETS, ProjectionSetRepository
from pring_cycle.publication_corrections import (
    PUBLICATION_CORRECTION_SCHEMA,
    WRONG_PERIOD_VALUE,
    mark_affected_publications,
    publication_corrections,
)
from pring_cycle.reports import ReportRepository
from pring_cycle.retention import prune_to_window
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.storage import database_connection
from tests.integration.test_atomic_projection import envelope
from tests.integration.test_claim_adoption import news_claim, registered_version

QUOTE = "1—8月份，规模以上工业增加值同比增长{}%。"


@pytest.fixture
def paths(tmp_path: Path) -> RuntimePaths:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    return paths


def publish(paths: RuntimePaths, projection_set_id: str, day: str, inputs: list[str]) -> None:
    datasets: dict[str, dict[str, object]] = {
        name: {"projection_set_id": projection_set_id, "dataset": name}
        for name in ANALYTICAL_DATASETS
    }
    datasets["macro"]["model_input_observation_version_ids"] = inputs
    ProjectionSetRepository(paths.database).publish(
        envelope(projection_set_id, target_business_date=day), datasets
    )


def report(paths: RuntimePaths, report_snapshot_id: str, projection_set_id: str, day: str) -> None:
    with database_connection(paths.database) as connection:
        connection.execute(
            "INSERT INTO evidence_bundle VALUES (?, 'hash', ?, ?, '2026-10-09T20:00:00+00:00')",
            (
                f"bundle-{report_snapshot_id}",
                projection_set_id,
                json.dumps(
                    {
                        "report_cutoff": "2026-10-09T19:58:56+00:00",
                        "system_as_of": "2026-10-09T19:58:56+00:00",
                        "schema_version": "report-schema-v0003",
                        "prompt_version": "report-prompt-v0003",
                    }
                ),
            ),
        )
        connection.execute(
            "INSERT INTO report_snapshot(report_snapshot_id, client_request_id, "
            "projection_set_id, target_business_date, version, status, adapter, current_stage, "
            "bundle_id, bundle_hash, model_version_id, schema_version, prompt_version, "
            "body_json, body_retained, created_at) VALUES (?, ?, ?, ?, "
            "(SELECT count(*) + 1 FROM report_snapshot WHERE target_business_date=?), "
            "'completed', 'deterministic', NULL, ?, 'hash', 'model-v0001', 'report-schema-v0003', "
            "'report-prompt-v0003', ?, 1, '2026-10-09T20:00:00+00:00')",
            (
                report_snapshot_id,
                report_snapshot_id,
                projection_set_id,
                day,
                day,
                f"bundle-{report_snapshot_id}",
                json.dumps({"support": ["住户贷款增加"]}, ensure_ascii=False),
            ),
        )


@pytest.mark.usefixtures("runtime_clock")
def test_a_publication_on_a_wrong_period_value_is_marked_and_linked_to_its_correction(
    paths: RuntimePaths, capsys: pytest.CaptureFixture[str]
) -> None:
    version = registered_version(paths, capsys)
    known = datetime(2026, 9, 16, 2, tzinfo=UTC)
    wrong = news_claim(
        paths,
        version,
        "中国政府网",
        5.9,
        QUOTE.format(5.9),
        known,
        title="2025年1—8月份规模以上工业增加值增长5.9%",
    )
    right = news_claim(
        paths,
        version,
        "新浪财经",
        5.3,
        QUOTE.format(5.3),
        known,
        title="国家统计局：2026年1—8月份规模以上工业增加值增长5.3%",
    )
    publish(paths, "projection-old", "2026-10-09", [wrong, right])
    publish(paths, "projection-earlier", "2026-10-08", [wrong])
    # Its claims were candidates only: what the model did not read did not affect it.
    publish(paths, "projection-unread", "2026-10-07", [right])
    report(paths, "report-old", "projection-old", "2026-10-09")
    report(paths, "report-earlier", "projection-earlier", "2026-10-08")

    with database_connection(paths.database) as connection:
        assert publication_corrections(connection, "projection-old") == {
            "affected": [{"reason": WRONG_PERIOD_VALUE, "claim_ids": [wrong]}],
            "corrected_by": [],
            "corrects": [],
        }
        assert publication_corrections(connection, "projection-unread") == {}

    # The fixed run's publication of the same day reads the year's own value.
    publish(paths, "projection-new", "2026-10-09", [right])
    report(paths, "report-new", "projection-new", "2026-10-09")

    with database_connection(paths.database) as connection:
        assert publication_corrections(connection, "projection-old")["corrected_by"] == [
            "projection-new"
        ]
        assert publication_corrections(connection, "projection-new") == {
            "affected": [],
            "corrected_by": [],
            "corrects": ["projection-old"],
        }
        # No later publication of its day: marked, not corrected.
        assert publication_corrections(connection, "projection-earlier")["corrected_by"] == []

    # Read with the projection, as the API, the CLI and the page show it.
    projections = ProjectionSetRepository(paths.database)
    assert projections.get("projection-old").corrections["corrected_by"] == ["projection-new"]
    current = projections.current()
    assert current.corrections["corrects"] == ["projection-old"]
    assert "本投影更正 projection-old" in str(dashboard_shell(current, (), ()))
    assert "受错期值影响：当前投影" in str(
        dashboard_shell(projections.get("projection-earlier"), (), ())
    )
    assert projections.get("projection-unread").corrections == {}

    reports = ReportRepository(paths.database)
    old, new, earlier = (reports.get(f"report-{name}") for name in ("old", "new", "earlier"))
    assert old.corrections == {
        "affected": [{"reason": WRONG_PERIOD_VALUE, "claim_ids": [wrong]}],
        "corrected_by": ["report-new"],
        "corrects": [],
    }
    assert new.corrections == {"affected": [], "corrected_by": [], "corrects": ["report-old"]}
    assert earlier.corrections["corrected_by"] == []
    assert asdict(old)["corrections"] == old.corrections
    # Published as it was: its body is not rewritten.
    assert old.body == {"support": ["住户贷款增加"]}
    page = str(_report_reader(old))
    assert "受错期值影响" in page and "report-new" in page
    assert "更正" in str(_report_reader(new)) and "report-old" in str(_report_reader(new))
    assert "尚无更正版本" in str(_report_reader(earlier))
    assert "受错期值影响" not in str(_report_reader(replace(old, corrections={})))

    # Marks are appended only.
    with (
        database_connection(paths.database) as connection,
        pytest.raises(sqlite3.IntegrityError, match="publication_impact_is_append_only"),
    ):
        connection.execute("UPDATE publication_impact SET reason='other'")


@pytest.mark.usefixtures("runtime_clock")
def test_marks_go_with_their_projection_at_retention(
    paths: RuntimePaths, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    version = registered_version(paths, capsys)
    wrong = news_claim(
        paths,
        version,
        "中国政府网",
        5.9,
        QUOTE.format(5.9),
        datetime(2026, 9, 16, 2, tzinfo=UTC),
        title="2025年1—8月份规模以上工业增加值增长5.9%",
    )
    publish(paths, "projection-old", "2026-01-05", [wrong])
    publish(paths, "projection-fixed", "2026-01-05", [])
    publish(paths, "projection-current", "2026-10-09", [])

    # The window a successful full run would give.
    monkeypatch.setattr(
        "pring_cycle.retention.retention_window", lambda _c: ("2026-04-10", "2026-10-09")
    )
    with database_connection(paths.database) as connection:
        assert connection.execute("SELECT count(*) FROM publication_impact").fetchone() == (1,)

    prune_to_window(paths)

    with database_connection(paths.database) as connection:
        assert connection.execute("SELECT count(*) FROM publication_impact").fetchone() == (0,)
        assert connection.execute("SELECT count(*) FROM publication_correction").fetchone() == (0,)


@pytest.mark.usefixtures("runtime_clock")
def test_projections_kept_before_the_marks_are_marked_once_they_are_introduced(
    paths: RuntimePaths, capsys: pytest.CaptureFixture[str]
) -> None:
    """The upgrade marks what is kept at once: no publication is awaited."""
    version = registered_version(paths, capsys)
    wrong = news_claim(
        paths,
        version,
        "中国政府网",
        5.9,
        QUOTE.format(5.9),
        datetime(2026, 9, 16, 2, tzinfo=UTC),
        url="https://app.www.gov.cn/govdata/gov/202509/15/536600/article.html",
    )
    # Dated by its subject clause alone.
    subject = news_claim(
        paths,
        version,
        "中国政府网",
        5.8,
        QUOTE.format(5.8),
        datetime(2026, 9, 16, 3, tzinfo=UTC),
        subject="2025年1—8月份，全国规模以上工业增加值同比增长5.8%",
    )
    with database_connection(paths.database) as connection:
        connection.execute("DROP TABLE publication_impact")
        connection.execute("DROP TABLE publication_correction")
    publish(paths, "projection-old", "2026-10-09", [wrong])
    publish(paths, "projection-subject", "2026-10-08", [subject])

    with database_connection(paths.database) as connection:
        connection.executescript(PUBLICATION_CORRECTION_SCHEMA)
        assert mark_affected_publications(connection) == {"projection-old", "projection-subject"}
        assert publication_corrections(connection, "projection-old")["affected"] == [
            {"reason": WRONG_PERIOD_VALUE, "claim_ids": [wrong]}
        ]
