"""Read the published cockpit through a real HTTP server."""

import json
import socket
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
import uvicorn

from pring_cycle.acquisition import AcquisitionRepository, own_acquisitions
from pring_cycle.batches import processing_batch
from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.projections import ProjectionSetRepository
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths
from pring_cycle.web import create_web_application
from tests.integration.test_core_carry_forward import CUTOFF, TARGET, seed_cores
from tests.integration.test_day_summary import target_projection
from tests.integration.test_decertified_main_chain import claim
from tests.integration.test_worker_execution import runtime


@contextmanager
def serving(paths: RuntimePaths) -> Iterator[str]:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        server = uvicorn.Server(
            uvicorn.Config(create_web_application(paths, port), log_level="error", lifespan="off")
        )
        thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 10
            while not server.started and time.monotonic() < deadline:
                time.sleep(0.01)
            assert server.started
            yield f"http://127.0.0.1:{port}"
        finally:
            server.should_exit = True
            thread.join(timeout=10)
            assert not thread.is_alive()


def get(url: str | Request) -> tuple[int, Any]:
    try:
        response = urlopen(url, timeout=10)
    except HTTPError as error:
        response = error
    with response:
        return response.status, json.loads(response.read())


def post(
    base: str, payload: dict[str, Any], *, host: str | None = None, origin: str | None = None
) -> tuple[int, Any]:
    headers = {"Content-Type": "application/json", "Origin": origin or base}
    if host:
        headers["Host"] = host
    return get(
        Request(base + "/api/v1/commands", data=json.dumps(payload).encode(), headers=headers)
    )


def rendered_page(
    base: str,
    pathname: str,
    search: str,
    previous: str | None = None,
    *,
    command: str | None = None,
    poll: int = 0,
) -> dict[str, Any]:
    dependencies = get(base + "/_dash-dependencies")[1]
    callback = next(item for item in dependencies if "page-content.children" in item["output"])
    payload = {
        "output": callback["output"],
        "outputs": [
            {"id": component, "property": prop}
            for component, prop in (
                ("page-content", "children"),
                ("runtime-poll", "interval"),
                ("projection-strip", "children"),
                ("view-fingerprint", "data"),
                ("refresh-notice", "children"),
            )
        ],
        "inputs": [
            {"id": "dashboard-location", "property": "pathname", "value": pathname},
            {"id": "dashboard-location", "property": "search", "value": search},
            {"id": "runtime-poll", "property": "n_intervals", "value": poll},
            {"id": "command-refresh", "property": "data", "value": command},
        ],
        "state": [{"id": "view-fingerprint", "property": "data", "value": previous}],
        "changedPropIds": ["command-refresh.data" if command else "runtime-poll.n_intervals"],
    }
    status, document = get(
        Request(
            base + "/_dash-update-component",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json", "Origin": base},
        )
    )
    assert status == 200
    return document["response"]


def test_a_report_accepted_from_an_idle_board_immediately_shows_pending_state(
    tmp_path: Path,
) -> None:
    paths = runtime(tmp_path)
    seed_cores(paths)
    projection = target_projection(paths)
    identity = projection.envelope.projection_set_id
    search = f"?projection={identity}"
    with serving(paths) as base:
        initial = rendered_page(base, "/", search)
        assert initial["runtime-poll"]["interval"] == 300_000
        status, accepted = post(
            base,
            {
                "command": "report_generation",
                "client_request_id": "idle-board-report",
                "target_business_date": TARGET.isoformat(),
                "projection_set_id": identity,
            },
        )
        assert status == 202
        updated = rendered_page(
            base, "/", search, initial["view-fingerprint"]["data"], command=accepted["run_id"]
        )
        assert updated["runtime-poll"]["interval"] == 30_000
        rendered = json.dumps(updated.get("page-content"), ensure_ascii=False)
        assert "报告任务：排队" in rendered
        assert "完成后自动显示新版本" in rendered


def test_live_chain_refreshes_requests_without_a_run_step_change(tmp_path: Path) -> None:
    paths = runtime(tmp_path)
    with serving(paths) as base:
        _, accepted = post(
            base,
            {
                "command": "manual_full",
                "client_request_id": "live-flow",
                "target_business_date": TARGET.isoformat(),
            },
        )
        run_id = accepted["run_id"]
        search = f"?run={run_id}"
        initial = rendered_page(base, "/data-chain", search)
        assert "取数流向 · 0 次真实请求" in json.dumps(initial, ensure_ascii=False)
        with own_acquisitions(paths.database, run_id, "direct_core_refresh"):
            AcquisitionRepository(paths.database, paths.artifacts).capture(
                provider="fixture",
                api_name="price",
                parameters={},
                fields="value",
                parser_version="fixture",
                fetch=lambda: b"100",
                parse=float,
                normalize=lambda value: {"value": value},
            )
        updated = rendered_page(
            base, "/data-chain", search, initial["view-fingerprint"]["data"], poll=1
        )
        assert "取数流向 · 1 次真实请求" in json.dumps(updated, ensure_ascii=False)
        assert updated["runtime-poll"]["interval"] == 30_000
        unchanged = rendered_page(
            base, "/data-chain", search, updated["view-fingerprint"]["data"], poll=2
        )
        assert "page-content" not in unchanged


def test_configured_host_origin_and_health_share_the_boundary(tmp_path: Path) -> None:
    paths = runtime(tmp_path)
    paths.config_file.write_text(
        '[server]\nhost="127.0.0.1"\nport=8060\n'
        'allowed_hosts=["cockpit.test"]\n'
        'allowed_origins=["https://cockpit.test"]\n'
    )
    with serving(paths) as base:
        assert get(Request(base + "/api/v1/health", headers={"Host": "evil.test"}))[0] == 403
        status, health = get(Request(base + "/api/v1/health", headers={"Host": "cockpit.test"}))
        assert status == 200
        assert health["binding"] == {"host": "127.0.0.1", "port": int(base.rsplit(":", 1)[1])}
        payload = {
            "command": "manual_full",
            "client_request_id": "custom-host",
            "target_business_date": "2026-08-28",
        }
        assert post(base, payload, host="cockpit.test", origin="https://evil.test")[0] == 403
        status, accepted = post(base, payload, host="cockpit.test", origin="https://cockpit.test")
        assert status == 202
        assert (
            post(base, payload, host="cockpit.test", origin="https://cockpit.test")[1]["run_id"]
            == accepted["run_id"]
        )


def test_wildcard_access_configuration_is_rejected(tmp_path: Path) -> None:
    paths = runtime(tmp_path)
    paths.config_file.write_text('[server]\nallowed_hosts=["*"]\n')
    with pytest.raises(ValueError, match="invalid_allowed_host"):
        create_web_application(paths, 8050)


def _full_run(paths: RuntimePaths, name: str) -> str:
    return (
        RunRepository(paths.database)
        .submit_manual_full(
            target_business_date=TARGET.isoformat(),
            client_request_id=name,
            model_version_id="model-v0001",
            system_as_of=CUTOFF,
        )
        .run_id
    )


def _identity_bar(base: str, search: str) -> str:
    strip = rendered_page(base, "/", search)["projection-strip"]["children"]
    return json.dumps(strip, ensure_ascii=False)


def test_pinned_projection_does_not_mix_with_a_new_current_pointer(tmp_path: Path) -> None:
    paths = runtime(tmp_path)
    seed_cores(paths)
    runs = RunRepository(paths.database)
    first_run = _full_run(paths, "first-full")
    first = target_projection(paths)
    # Published before batches existed: only the run's own link names its producer.
    runs.link_projection(first_run, first.envelope.projection_set_id)
    runs.cancel(first_run)  # terminal, so its health summary is persisted
    with serving(paths) as base:
        status, current = get(base + "/api/v1/projections/current")
        assert status == 200
        identity = current["envelope"]["projection_set_id"]
        second = replace(first.envelope, projection_set_id="projection-new-current")
        datasets = {
            name: {**data, "projection_set_id": second.projection_set_id}
            for name, data in first.datasets.items()
        }
        second_run = _full_run(paths, "second-full")
        with processing_batch(second_run):  # e.g. a backfilled day: the batch alone names it
            ProjectionSetRepository(paths.database).publish(second, datasets)

        status, core = get(base + f"/api/v1/projections/{identity}/core_assets")
        assert status == 200
        assert core["envelope"]["projection_set_id"] == identity
        assert core["data"]["projection_set_id"] == identity
        assert core["data"]["display"]["bond"]["latest_value"] == 279
        status, entire = get(base + f"/api/v1/projections/{identity}")
        assert status == 200
        assert entire["envelope"] == core["envelope"]
        assert get(base + "/api/v1/projections/no-such-projection")[0] == 404

        pinned = _identity_bar(base, f"?projection={identity}")
        assert identity in pinned and first_run in pinned
        assert "projection-new-current" not in pinned and second_run not in pinned
        latest = _identity_bar(base, "")
        assert "projection-new-current" in latest and second_run in latest
        assert first_run not in latest

        orphan = replace(first.envelope, projection_set_id="projection-without-run")
        ProjectionSetRepository(paths.database).publish(
            orphan,
            {
                name: {**data, "projection_set_id": orphan.projection_set_id}
                for name, data in first.datasets.items()
            },
            as_current=False,
        )
        unknown = _identity_bar(base, "?projection=projection-without-run")
        assert "未提供" in unknown
        assert first_run not in unknown and second_run not in unknown


def test_board_method_row_reads_the_trend_rules_the_worker_froze(tmp_path: Path) -> None:
    paths = runtime(tmp_path)
    seed_cores(paths)
    projection = target_projection(paths)
    with serving(paths) as base:
        page = json.dumps(
            rendered_page(base, "/", "?projection=" + projection.envelope.projection_set_id),
            ensure_ascii=False,
        )

    assert (
        "MA120 + 20 日斜率定稳定牛熊，噪声带 1.5×20 日波动，持续 8 日确认，30 日候选只作转折观察；"
        "宏观与库存只做事后确认，不改写阶段 · " + projection.envelope.model_version_id
    ) in page
    assert "该模型版本未提供趋势规则参数" not in page


def test_evidence_opens_the_exact_version_drawn_by_the_projection(tmp_path: Path) -> None:
    paths = runtime(tmp_path)
    seed_cores(paths)
    projection = target_projection(paths)
    point = projection.datasets["core_assets"]["display"]["bond"]["points"][-1]
    with serving(paths) as base:
        status, evidence = get(
            base
            + "/api/v1/projection-evidence/"
            + projection.envelope.projection_set_id
            + "/"
            + point["selected_claim_id"]
        )
        assert status == 200
        assert evidence["trace"]["selected_value"] == 279
        assert evidence["trace"]["selected_claim_id"] == point["selected_claim_id"]
        assert evidence["selection_basis"] == "frozen_version"
        assert (
            get(
                base
                + "/api/v1/projection-evidence/"
                + projection.envelope.projection_set_id
                + "/not-in-snapshot"
            )[0]
            == 404
        )


def test_report_command_stays_pinned_after_current_advances(tmp_path: Path) -> None:
    paths = runtime(tmp_path)
    seed_cores(paths)
    first = target_projection(paths)
    envelope = replace(first.envelope, projection_set_id="projection-new-current")
    ProjectionSetRepository(paths.database).publish(
        envelope,
        {
            name: {**data, "projection_set_id": envelope.projection_set_id}
            for name, data in first.datasets.items()
        },
    )
    with serving(paths) as base:
        payload = {
            "command": "report_generation",
            "client_request_id": "pinned-report",
            "projection_set_id": first.envelope.projection_set_id,
        }
        status, accepted = post(base, payload)
        assert status == 202
        _, audit = get(base + f"/api/v1/runs/{accepted['run_id']}/audit")
        assert audit["run"]["projection_set_id"] == first.envelope.projection_set_id
        assert post(base, payload)[1]["run_id"] == accepted["run_id"]
        assert post(base, {**payload, "projection_set_id": envelope.projection_set_id})[0] == 409


def test_cancelled_queue_has_immutable_health_and_is_not_duplicated(tmp_path: Path) -> None:
    paths = runtime(tmp_path)
    with serving(paths) as base:
        _, accepted = post(
            base,
            {
                "command": "manual_full",
                "client_request_id": "queue",
                "target_business_date": "2026-08-28",
            },
        )
        payload = {"command": "cancel", "run_id": accepted["run_id"], "client_request_id": "cancel"}
        assert post(base, payload)[0] == 202
        status, first = get(base + f"/api/v1/runs/{accepted['run_id']}/health")
        assert status == 200
        assert first["summary"]["status"] == "cancelled"
        assert first["summary"]["request_count"] == 0
        assert first["summary"]["projection_set_id"] is None
        assert post(base, payload)[0] == 202
        assert get(base + f"/api/v1/runs/{accepted['run_id']}/health")[1] == first


def test_old_frozen_claim_keeps_its_own_receipt_after_a_visible_revision(tmp_path: Path) -> None:
    paths = runtime(tmp_path)
    evidence = EvidenceRepository(paths.database)
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    ids = []
    receipts = []
    for index, value in enumerate((100, 999)):
        at = CUTOFF + timedelta(hours=index)
        receipt = acquisitions.capture(
            provider="fixture",
            api_name="price",
            parameters={},
            fields="value",
            parser_version="fixture",
            fetch=lambda value=value: str(value).encode(),
            parse=float,
            normalize=lambda v: {"value": v},
            clock=lambda at=at: at,
        ).receipt
        source = claim(
            "CN_BOND_CORE_000012",
            TARGET,
            value,
            unit="index_points",
            provider="fixture",
            reference="fixture:price",
        )
        stored = evidence.append_source_claim(
            replace(
                source,
                release_event_id="fixture:price-revision",
                available_at=at,
                fetched_at=at,
                acquisition_id=receipt.acquisition_id,
            )
        )
        ids.append(stored.claim_id)
        receipts.append(receipt)
    frozen = evidence.freeze_snapshot(
        (ids[0],), mode=AsOfMode.SYSTEM, as_of=CUTOFF + timedelta(hours=2)
    )
    seed_cores(paths)
    source_projection = target_projection(paths)
    envelope = replace(
        source_projection.envelope,
        projection_set_id="projection-old-selected",
        evidence_snapshot_id=frozen.evidence_snapshot_id,
        system_as_of=CUTOFF + timedelta(hours=2),
    )
    ProjectionSetRepository(paths.database).publish(
        envelope,
        {
            name: {**data, "projection_set_id": envelope.projection_set_id}
            for name, data in source_projection.datasets.items()
        },
    )
    with serving(paths) as base:
        status, document = get(
            base + f"/api/v1/projection-evidence/{envelope.projection_set_id}/{ids[0]}"
        )
        assert status == 200
        trace = document["trace"]
        assert trace["selected_value"] == 100
        assert next(item for item in trace["claims"] if item["claim_id"] == ids[0])["value"] == 100
        assert [item["acquisition_id"] for item in trace["acquisitions"]] == [
            receipts[0].acquisition_id
        ]


def test_artifact_http_distinguishes_expired_missing_and_corrupt_content(tmp_path: Path) -> None:
    paths = runtime(tmp_path)
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    now = datetime.now(UTC)

    def capture(provider: str, at: datetime) -> Any:
        return acquisitions.capture(
            provider=provider,
            api_name="search",
            parameters={},
            fields="body",
            parser_version="fixture",
            fetch=lambda: b"<script>alert('unsafe')</script>",
            parse=lambda raw: raw.decode(),
            normalize=lambda value: {"body": value},
            clock=lambda: at,
        ).receipt

    current = capture("fixture", now)
    expired = capture("tavily", now - timedelta(days=31))
    with serving(paths) as base:
        url = base + f"/api/v1/acquisitions/{current.acquisition_id}/artifacts/raw"
        with urlopen(url + "?view=true", timeout=10) as response:
            assert response.status == 200
            assert response.headers.get_content_type() == "text/plain"
            assert "sandbox" in response.headers["Content-Security-Policy"]
            assert b"<script>" in response.read()
        assert get(base + f"/api/v1/acquisitions/{expired.acquisition_id}/artifacts/raw")[0] == 410
        artifact = paths.artifacts / current.raw_hash[:2] / current.raw_hash
        artifact.write_bytes(b"corrupted")
        assert get(url) == (409, {"error": "artifact_hash_mismatch"})
        artifact.unlink()
        assert get(url) == (404, {"error": "artifact_file_missing"})
        assert get(base + "/api/v1/acquisitions/absent/artifacts/raw")[0] == 404


def test_recursive_evidence_follows_exact_parent_versions_and_rejects_false_edges(
    tmp_path: Path,
) -> None:
    paths = runtime(tmp_path)
    seed_cores(paths)
    original = target_projection(paths)
    evidence = EvidenceRepository(paths.database)
    point = original.datasets["core_assets"]["display"]["bond"]["points"][-1]
    source_id = point["selected_claim_id"]
    parent = source_id
    nodes = []
    for metric in ("fixture-derived", "fixture-parent"):
        node = evidence.append_derived_observation(
            metric_id=metric,
            formula_version="fixture-v1",
            input_observation_version_ids=(parent,),
            as_of_mode=AsOfMode.SYSTEM,
            as_of_cutoff=CUTOFF,
            computed_at=CUTOFF,
            value=279,
            unit="index_points",
        ).derived_observation_id
        nodes.append(node)
        parent = node
    frozen = evidence.freeze_snapshot((nodes[-1],), mode=AsOfMode.SYSTEM, as_of=CUTOFF)
    envelope = replace(
        original.envelope,
        projection_set_id="projection-derived-tree",
        evidence_snapshot_id=frozen.evidence_snapshot_id,
    )
    ProjectionSetRepository(paths.database).publish(
        envelope,
        {
            name: {**data, "projection_set_id": envelope.projection_set_id}
            for name, data in original.datasets.items()
        },
    )
    with serving(paths) as base:
        root = base + f"/api/v1/projection-evidence/{envelope.projection_set_id}/"
        assert get(root + nodes[0] + "?trail=" + nodes[1])[0] == 200
        status, document = get(root + source_id + "?trail=" + nodes[1] + "," + nodes[0])
        assert status == 200 and document["trace"]["selected_value"] == 279
        assert (
            get(root + source_id + "?trail=" + nodes[1])[1]["error"]
            == "version_not_in_parent_inputs"
        )
        assert get(root + nodes[1] + "?trail=" + nodes[1])[1]["error"] == "lineage_cycle"
