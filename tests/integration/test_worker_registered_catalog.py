"""Worker paths on the activated isolated candidate and its registered metric catalog.

Every runtime is an independent copy of the public lifecycle material; its sources are synthetic
test inputs and no actual source is certified.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any, cast
from urllib.request import Request

import pytest

from pring_cycle.acquisition import AcquisitionRepository
from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.models import ModelRepository
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths
from pring_cycle.worker import process_pending_run
from tests.models.test_isolated_lifecycle import SCRATCH, isolated_lifecycle_material

TARGET_BUSINESS_DATE = "2026-09-11"
JULY_PPI = SCRATCH / (
    "evidence-a18-import-20260909/b323261248c08ecba00a96cf4401654896fd8a5709ce9bf81c2e38f7d5fbef09"
)
AUGUST_PPI_URL = "https://www.stats.gov.cn/sj/zxfb/202609/t20260909_1965007.html"
# A delivered TuShare response with an invalid schema: the parser must reject it.
INVALID_TUSHARE_RESPONSE = b'{"code":0,"data":{"fields":[],"items":[[]]}}'


def august_ppi_document() -> bytes:
    # Synthetic August release derived from the archived July NBS page: period and publication
    # time are rewritten, so its values are fixture data rather than official August figures.
    return (
        JULY_PPI.read_bytes()
        .replace("2026年7月".encode(), "2026年8月".encode())
        .replace(b"2026/08/09", b"2026/09/09")
        .replace(b"202608/t20260809", b"202609/t20260909")
    )


@pytest.mark.usefixtures("runtime_clock")
def test_worker_official_refresh_uses_the_active_registered_catalog(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, material = isolated_lifecycle_material(tmp_path / "runtime")
    candidate = material["candidate_model_version_id"]
    assert ModelRepository(paths.database).active().model_version_id == candidate
    version = material["metric_catalog_version"]
    now = datetime.now(UTC)
    runs = RunRepository(paths.database)
    submitted = runs.get(submit_august_ppi_refresh(paths, candidate, now))
    requested = serve_august_ppi(monkeypatch)
    block_history_page(monkeypatch, [])

    refresh_august_ppi(paths, now)

    stored = runs.get(submitted.run_id)
    assert requested == [AUGUST_PPI_URL]
    official = next(item for item in stored.retrieval_attempts if item["channel"] == "official")
    assert stored.status == "completed", stored
    assert official["outcome"] == "verified"
    august = refreshed_august_ppi(paths, as_of=now + timedelta(days=1), version=version)
    assert {p.dimensions["measure"] for p in august} >= {"yoy", "mom"}
    assert runs.reusable_checkpoints(submitted.run_id)


def serve_august_ppi(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    content = august_ppi_document()
    requested: list[str] = []

    class Response(BytesIO):
        status = 200
        headers = {"Content-Type": "text/html"}

        def geturl(self) -> str:
            return AUGUST_PPI_URL

    def fetch(request: Any, **kwargs: Any) -> Response:
        requested.append(request.full_url)
        return Response(content)

    monkeypatch.setattr("pring_cycle.official_context.urlopen", fetch)
    return requested


def submit_august_ppi_refresh(paths: RuntimePaths, candidate: str, now: datetime) -> str:
    return (
        RunRepository(paths.database)
        .submit(
            command_type="targeted_refresh",
            target_business_date=TARGET_BUSINESS_DATE,
            client_request_id="registered-official-ppi-2026-08",
            model_version_id=candidate,
            # An explicit cutoff after the refresh executes, so its own acquisition is visible.
            system_as_of=now + timedelta(days=1),
            release_event_id="nbs-ppi:2026-08",
            metric_ids=("CN_PPI",),
            period="2026-08",
            source_url=AUGUST_PPI_URL,
        )
        .run_id
    )


def refresh_august_ppi(paths: RuntimePaths, now: datetime) -> None:
    process_pending_run(
        paths,
        report_adapters=(),
        retrieval_now=now,
        # The external release calendar says the August release is out; the production
        # retrieval channels themselves still run (existing Worker test precedent).
        retrieval_release_resolver=lambda _scope, _now: True,
    )


def refreshed_august_ppi(paths: RuntimePaths, *, as_of: datetime, version: str) -> list[Any]:
    """The August PPI points, each claim certified and tied to the official original read back."""
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    receipt = next(
        r
        for r in acquisitions.history()
        if r.api_name == "official_http_get" and r.parameters.get("source_url") == AUGUST_PPI_URL
    )
    assert acquisitions.read_content(receipt.acquisition_id, "raw") == august_ppi_document()
    points = EvidenceRepository(paths.database).metric_series(
        "CN_PPI", mode=AsOfMode.SYSTEM, as_of=as_of, definition_version=version
    )
    august = [p for p in points if p.period_end == "2026-08-31"]
    assert august and all(
        claim.certification_status == "certified"
        and claim.source_reference == f"{AUGUST_PPI_URL}#sha256={receipt.raw_hash}"
        for point in august
        for claim in point.claims
    )
    return august


def real_core_opener() -> Any:
    """Serve the archived TuShare core responses, filtered to each requested date range."""
    from tests.models.test_isolated_lifecycle import CORE_TRANSPORT

    receipts = {
        item["name"]: item
        for item in json.loads((CORE_TRANSPORT / "receipts.json").read_text())["receipts"]
    }

    def rows(name: str) -> dict[str, Any]:
        document: dict[str, Any] = json.loads(
            (CORE_TRANSPORT / receipts[name]["local_file"]).read_bytes()
        )
        return document

    by_code = {
        "000985.CSI": rows("CN_EQUITY_CORE_000985"),
        "000012.SH": rows("CN_BOND_CORE_000012"),
        "NHII.NH": rows("CN_COMMODITY_CORE_NHII"),
    }
    calendar = rows("calendar")

    class Opener:
        def open(self, request: Any, *, timeout: float) -> BytesIO:
            payload = json.loads(request.data)
            params = payload["params"]
            start, end = params["start_date"], params["end_date"]
            source = calendar if payload["api_name"] == "trade_cal" else by_code[params["ts_code"]]
            fields = source["data"]["fields"]
            date_index = fields.index(
                "cal_date" if payload["api_name"] == "trade_cal" else "trade_date"
            )
            items = [item for item in source["data"]["items"] if start <= item[date_index] <= end]
            return BytesIO(
                json.dumps({"code": 0, "data": {"fields": fields, "items": items}}).encode()
            )

    return Opener()


EXTENSION_SESSIONS = tuple(
    date.fromisoformat(day)
    for day in (
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
    )
)


def extended_core_opener() -> Any:
    """Archived core responses followed by flat synthetic sessions through the target date."""
    archive = real_core_opener()

    class Opener:
        def open(self, request: Any, *, timeout: float) -> BytesIO:
            payload = json.loads(request.data)
            params = payload["params"]
            document = json.loads(archive.open(request, timeout=timeout).read())
            fields = document["data"]["fields"]
            calendar = payload["api_name"] == "trade_cal"
            if not calendar:
                everything = {**payload, "params": {**params, "start_date": "20170101"}}
                archived = json.loads(
                    archive.open(
                        Request(request.full_url, json.dumps(everything).encode()), timeout=timeout
                    ).read()
                )["data"]["items"]
                close = max(archived, key=lambda item: item[1])[fields.index("close")]
            added = []
            for day in (d.strftime("%Y%m%d") for d in EXTENSION_SESSIONS):
                if params["start_date"] <= day <= params["end_date"]:
                    row = (
                        {"cal_date": day, "is_open": 1}
                        if calendar
                        else {
                            "ts_code": params["ts_code"],
                            "trade_date": day,
                            "close": close,
                            "pre_close": close,
                            "pct_chg": 0.0,
                        }
                    )
                    added.append([row[field] for field in fields])
            # Archived rows are newest first.
            document["data"]["items"] = added[::-1] + document["data"]["items"]
            return BytesIO(json.dumps(document).encode())

    return Opener()


def extended_context_opener(requested: list[str], invalid_api: str | None = None) -> Any:
    """TuShare context rows continuing the lifecycle material's synthetic series to the target.

    Each series repeats the material importers' values on their own days, so a refresh over the
    material window restates identical facts; other families are unavailable.
    """
    from tests.models.test_isolated_lifecycle import trading_days

    sessions = (*trading_days(), *EXTENSION_SESSIONS)

    def since(start: str) -> list[str]:
        return [d.strftime("%Y%m%d") for d in sessions if d.isoformat() >= start]

    market, interbank = since("2026-03-02"), since("2026-02-20")
    warrant_listing = {
        "CU": ("SHFE", "吨"),
        "RB": ("SHFE", "吨"),
        "RU": ("SHFE", "吨"),
        "SP": ("SHFE", "吨"),
        "SC": ("INE", "桶"),
        "PP": ("DCE", "手"),
        "CF": ("CZCE", "张"),
        "PTA": ("CZCE", "张"),
    }

    def rows(api: str, params: dict[str, Any]) -> tuple[list[str], list[list[Any]]]:
        def within(days: list[str]) -> list[tuple[int, str]]:
            return [
                (i, d)
                for i, d in enumerate(days)
                if params["start_date"] <= d <= params["end_date"]
            ]

        code = params.get("ts_code")
        if api in {"index_daily", "fut_index_daily"}:
            return ["ts_code", "trade_date", "close"], [
                [code, d, 1000.0 + i] for i, d in within(market)
            ]
        if api == "margin":
            return ["trade_date", "exchange_id", "rzye", "rzmre"], [
                [d, exchange, 100_000_000 * (n + 1), 10_000_000 * (n + 1)]
                for _, d in within(market)
                for n, exchange in enumerate(("SSE", "SZSE", "BSE"))
            ]
        if api == "index_dailybasic":
            return ["ts_code", "trade_date", "pe", "pb", "turnover_rate"], [
                [code, d, 12.5, 1.4, 0.8] for _, d in within(market)
            ]
        if api == "repo_daily":
            return ["ts_code", "trade_date", "repo_maturity", "weight"], [
                ["DR007.IB", d, "DR007", 1.40 + i % 5 / 100] for i, d in within(interbank)
            ]
        if api == "shibor":
            return ["date", "on", "1w", "3m"], [[d, 1.30, 1.38, 1.43] for _, d in within(interbank)]
        if api == "fut_wsr":
            exchange, unit = warrant_listing[params["symbol"]]
            return [
                "trade_date",
                "symbol",
                "warehouse",
                "pre_vol",
                "vol",
                "vol_chg",
                "unit",
                "exchange",
            ], [
                [d, params["symbol"], "合成仓库", 100, 100, 0, unit, exchange]
                for _, d in within(market)
            ]
        raise OSError("fixture source unavailable")

    class Opener:
        def open(self, request: Any, *, timeout: float) -> BytesIO:
            payload = json.loads(request.data)
            api = payload["api_name"]
            requested.append(api)
            if api == invalid_api:
                return BytesIO(INVALID_TUSHARE_RESPONSE)
            fields, items = rows(api, payload["params"])
            return BytesIO(
                json.dumps({"code": 0, "data": {"fields": fields, "items": items}}).encode()
            )

    return Opener()


@pytest.mark.usefixtures("runtime_clock")
def test_worker_full_run_for_a_fixed_target_retrieves_gaps_and_failure_keeps_the_projection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pring_cycle.projections import ProjectionSetRepository

    paths, material = isolated_lifecycle_material(tmp_path / "runtime")
    candidate = material["candidate_model_version_id"]
    version = material["metric_catalog_version"]
    paths.secrets.write_text("TUSHARE_TOKEN=fixture-only\n", encoding="utf-8")
    paths.secrets.chmod(0o600)
    models = ModelRepository(paths.database)
    # The copied model identity and its acceptance receipt stay queryable before any run.
    assert models.active().model_version_id == candidate
    assert models.acceptance_details(candidate, material["acceptance_result_hash"])["passed"]
    # A targeted official refresh first; its adoption is proven separately by the full run.
    serve_august_ppi(monkeypatch)
    block_history_page(monkeypatch, [])
    submit_august_ppi_refresh(paths, candidate, datetime.now(UTC))
    refresh_august_ppi(paths, datetime.now(UTC))
    requested: list[str] = []
    monkeypatch.setattr(
        "pring_cycle.source_adapters.build_opener", lambda *h: extended_core_opener()
    )
    monkeypatch.setattr(
        "pring_cycle.tushare_context.build_opener", lambda *h: extended_context_opener(requested)
    )
    runs = RunRepository(paths.database)
    # The target trading day is fixed; the run executes days after it on the real clock.
    window_opened = datetime.now(UTC)
    run = runs.submit_manual_full(
        target_business_date=TARGET_BUSINESS_DATE,
        client_request_id="registered-full-run-2026-09-11",
        model_version_id=candidate,
        system_as_of=window_opened,
    )

    process_pending_run(paths, report_adapters=())

    stored = runs.get(run.run_id)
    assert stored.status == "completed", stored.error_classification
    projections = ProjectionSetRepository(paths.database)
    published = projections.get(stored.projection_set_id or "")
    assert projections.current().envelope.projection_set_id == published.envelope.projection_set_id
    assert published.envelope.model_version_id == candidate
    assert published.envelope.target_business_date == TARGET_BUSINESS_DATE
    assert models.activation_history()[-1] == {
        **models.activation_history()[-1],
        "model_version_id": candidate,
        "first_published_business_date": TARGET_BUSINESS_DATE,
    }
    # SYSTEM froze once after acquisition; projection, plan and report share that cutoff.
    plan = runs.full_retrieval_plan(run.run_id)
    assert plan["initial"]["cutoff_mode"] == "acquisition_window"
    assert plan["initial"]["initial_system_as_of"] == window_opened.isoformat()
    assert plan["initial"]["target_business_date"] == TARGET_BUSINESS_DATE
    assert stored.cutoffs_frozen is True
    assert stored.system_as_of > window_opened
    assert stored.system_as_of == stored.report_cutoff == published.envelope.system_as_of
    assert plan["final"]["system_as_of"] == stored.system_as_of.isoformat()
    gaps = {(g["metric_id"], g["period"]): g for g in plan["final"]["gaps"]}
    adopted = set(plan["adoption"]["selected_claim_ids"])
    assert plan["adoption"]["projection_set_id"] == published.envelope.projection_set_id
    evidence = EvidenceRepository(paths.database)
    # The Worker's own core refresh closes the P0 gaps on the target and they are adopted.
    core_requests = {
        item["acquisition_id"]
        for item in plan["acquisitions"]
        if item["api_name"] in {"index_daily", "fut_index_daily"}
        and item["state"] == "validated"
        and "CN_EQUITY_CORE_000985" in item["metric_ids"]
    }
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    for metric_id in ("CN_EQUITY_CORE_000985", "CN_BOND_CORE_000012", "CN_COMMODITY_CORE_NHII"):
        core = gaps[(metric_id, TARGET_BUSINESS_DATE)]
        assert core["complete"] is True, core
        assert core["selected_claim_ids"] and set(core["selected_claim_ids"]) <= adopted
        linked = evidence.source_claim_acquisitions_many(tuple(core["selected_claim_ids"]))
        assert linked and all(items for items in linked.values())
        parents = {item.receipt.acquisition_id for items in linked.values() for item in items}
        assert parents <= core_requests
        # Each adopted value's original delivery is read back and contains the target session.
        for acquisition_id in parents:
            raw = acquisitions.read_content(acquisition_id, "raw").decode()
            assert TARGET_BUSINESS_DATE.replace("-", "") in raw
    # The refreshed official August PPI is adopted by this later projection.
    august = refreshed_august_ppi(paths, as_of=stored.system_as_of, version=version)
    assert {str(point.selected_claim_id) for point in august} & adopted
    # Market indices are retrieved and validated, but TuShare delivers no publication time:
    # the target-bound PUBLIC rule keeps the P1 gap unresolved and unadopted, not blocking.
    index_requests = [
        item
        for item in plan["acquisitions"]
        if item["api_name"] == "index_daily" and "CN_EQ_CSI300" in item["metric_ids"]
    ]
    assert index_requests and all(item["state"] == "validated" for item in index_requests)
    (retrieved,) = [
        point
        for point in evidence.metric_series(
            "CN_EQ_CSI300",
            mode=AsOfMode.SYSTEM,
            as_of=stored.system_as_of,
            definition_version=version,
        )
        if point.period_end == TARGET_BUSINESS_DATE
    ]
    assert all(claim.public_available_at is None for claim in retrieved.claims)
    csi300 = gaps[("CN_EQ_CSI300", TARGET_BUSINESS_DATE)]
    assert csi300["complete"] is False and not csi300["selected_claim_ids"]
    assert str(retrieved.selected_claim_id) not in adopted
    # Reviewed breadth inputs end with the material: an unresolved P1 gap, not a block.
    assert gaps[("CN_EQ_ADV_DEC", TARGET_BUSINESS_DATE)]["complete"] is False

    # A later run for the same target whose required indices fail keeps the published projection.
    monkeypatch.setattr(
        "pring_cycle.tushare_context.build_opener",
        lambda *h: extended_context_opener(requested, invalid_api="index_daily"),
    )
    before_failing = acquisition_ids(paths)
    failed = runs.submit_manual_full(
        target_business_date=TARGET_BUSINESS_DATE,
        client_request_id="registered-full-run-2026-09-11-failing",
        model_version_id=candidate,
        system_as_of=datetime.now(UTC),
    )

    process_pending_run(paths, report_adapters=())

    rejected = runs.get(failed.run_id)
    assert rejected.status == "action_required"
    assert (rejected.error_classification or "").startswith("worker_failure:ValueError:")
    assert rejected.projection_set_id is None
    # The failing branch keeps its original delivery, classification and existing claims apart.
    assert_rejected_tushare_delivery(paths, "index_daily", earlier=before_failing)
    attempt = evidence.latest_retrieval_attempt(
        "CN_EQ_CSI300",
        period=TARGET_BUSINESS_DATE,
        as_of=datetime.now(UTC),
        definition_version=version,
    )
    assert attempt is not None and (attempt.channel, attempt.outcome) == (
        "tushare",
        "validation_failed",
    )
    assert attempt.safe_metadata.get("error_type") == "ValueError"
    assert [
        point.selected_claim_id
        for point in evidence.metric_series(
            "CN_EQ_CSI300",
            mode=AsOfMode.SYSTEM,
            as_of=datetime.now(UTC),
            definition_version=version,
        )
        if point.period_end == TARGET_BUSINESS_DATE
    ] == [retrieved.selected_claim_id]
    assert set(runs.full_retrieval_plan(run.run_id)["adoption"]["selected_claim_ids"]) == adopted
    assert projections.current().envelope.projection_set_id == published.envelope.projection_set_id
    assert projections.get(published.envelope.projection_set_id).datasets == published.datasets


def acquisition_ids(paths: RuntimePaths) -> set[str]:
    return {
        r.acquisition_id for r in AcquisitionRepository(paths.database, paths.artifacts).history()
    }


def assert_rejected_tushare_delivery(
    paths: RuntimePaths, api_name: str, *, earlier: set[str]
) -> None:
    """The invalid delivery is stored as received original and failed with the parser's error."""
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    rejected = [
        r
        for r in acquisitions.history()
        if r.api_name == api_name and r.state == "failed" and r.acquisition_id not in earlier
    ]
    assert rejected
    for receipt in rejected:
        assert receipt.provider == "tushare" and receipt.error_type == "ValueError"
        assert acquisitions.read_content(receipt.acquisition_id, "raw") == INVALID_TUSHARE_RESPONSE


@pytest.mark.parametrize(
    ("failing_family_api", "required"),
    [("index_daily", True), ("cn_gdp", False)],
    ids=["required-market-indices", "optional-gdp"],
)
@pytest.mark.usefixtures("runtime_clock")
def test_worker_tushare_failures_keep_required_blocking_and_optional_degrading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failing_family_api: str, required: bool
) -> None:
    paths, material = isolated_lifecycle_material(tmp_path / "runtime")
    candidate = material["candidate_model_version_id"]
    # Only TuShare is configured; EIA is explicitly absent to isolate the TuShare branch.
    paths.secrets.write_text("TUSHARE_TOKEN=fixture-only\n", encoding="utf-8")
    paths.secrets.chmod(0o600)
    block_history_page(monkeypatch, [])
    requested: list[str] = []

    class ContextOpener:
        def open(self, request: Any, *, timeout: float) -> BytesIO:
            api = json.loads(request.data)["api_name"]
            requested.append(api)
            if api == failing_family_api:
                return BytesIO(INVALID_TUSHARE_RESPONSE)
            raise OSError("fixture source unavailable")

    monkeypatch.setattr("pring_cycle.source_adapters.build_opener", lambda *h: real_core_opener())
    monkeypatch.setattr("pring_cycle.tushare_context.build_opener", lambda *h: ContextOpener())
    runs = RunRepository(paths.database)
    before_run = acquisition_ids(paths)
    run = runs.submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id=f"registered-tushare-{failing_family_api}",
        model_version_id=candidate,
        system_as_of=datetime.now(UTC),
    )

    process_pending_run(paths, report_adapters=())

    stored = runs.get(run.run_id)
    assert failing_family_api in requested
    assert_rejected_tushare_delivery(paths, failing_family_api, earlier=before_run)
    evidence = EvidenceRepository(paths.database)
    failing_metric = "CN_EQ_CSI300" if required else "CN_GDP"
    attempt = evidence.latest_retrieval_attempt(
        failing_metric,
        period="2026-08-28",
        as_of=datetime.now(UTC),
        definition_version=material["metric_catalog_version"],
    )
    assert attempt is not None and attempt.channel == "tushare"
    assert attempt.outcome == "validation_failed"
    assert attempt.safe_metadata.get("error_type") == "ValueError"
    failure = stored.error_classification or ""
    assert "unknown_metric_definition_version" not in failure
    if required:
        # The original upstream validation error blocks the run instead of a lookup error.
        assert stored.status == "action_required"
        assert failure.startswith("worker_failure:ValueError:"), failure
    else:
        # The optional failure is recorded and later TuShare families are still requested.
        assert {"us_tycr", "repo_daily"} <= set(requested), requested
        assert stored.status == "completed", failure
        assert stored.projection_set_id is not None


def block_history_page(monkeypatch: pytest.MonkeyPatch, requested: list[str]) -> None:
    """The key-free fallback page, served from the archived original instead of the network."""
    import hashlib

    from pring_cycle.eia_html import FetchedEiaHistory

    originals = {
        "RBRTE": "b078a362332a3d6b34ae2a5dc5a91b98ddfacc7979410b32081f07e9dadc243e",
        "RWTC": "7da3e5b6632942bfedf02642fde22867d24bb0cf6477eff5ac9e5f9be4d92497",
    }

    def fetch(url: str) -> FetchedEiaHistory:
        requested.append(url)
        series = "RWTC" if "RWTC" in url.upper() else "RBRTE"
        content = (SCRATCH / "evidence-14" / originals[series]).read_bytes()
        assert hashlib.sha256(content).hexdigest() == originals[series]
        return FetchedEiaHistory(content, url, 200, "text/html; charset=utf-8")

    monkeypatch.setattr("pring_cycle.worker.fetch_eia_history", fetch)


def eia_opener(scenario: str, requested: list[str]) -> Any:
    """EIA transport for one scenario; ``missing`` must never be called."""
    from urllib.parse import parse_qs, urlsplit

    class EiaResponse(BytesIO):
        status = 200
        headers = {"Content-Type": "application/json"}

        def geturl(self) -> str:
            return "https://api.eia.gov/v2/petroleum/pri/spt/data/"

    class Opener:
        def open(self, request: Any, *, timeout: float) -> BytesIO:
            requested.append(request.full_url)
            assert scenario != "missing", "missing credentials must not send a request"
            if scenario == "network":
                raise OSError("fixture EIA network failure")
            parameters = parse_qs(urlsplit(request.full_url).query)
            assert (parameters["start"], parameters["end"]) == (["2026-01-20"], ["2026-08-28"])
            if scenario == "parse":
                return EiaResponse(b'{"response": {"frequency": "daily", "data": [{"period": 1}]}}')
            rows = [
                {
                    "period": "2026-08-27",
                    "series": series,
                    "series-description": description,
                    "value": value,
                    "units": "Dollars per Barrel",
                }
                for series, description, value in (
                    ("RBRTE", "Europe Brent Spot Price FOB", "71.25"),
                    ("RWTC", "Cushing, OK WTI Spot Price FOB", "66.50"),
                )
            ]
            return EiaResponse(
                json.dumps({"response": {"frequency": "daily", "data": rows}}).encode()
            )

    return Opener


@pytest.mark.parametrize(
    ("scenario", "expected_status"),
    [
        ("missing", "missing_credentials"),
        ("success", "verified_candidate"),
        ("network", "source_failed"),
        ("parse", "validation_failed"),
    ],
)
@pytest.mark.usefixtures("runtime_clock")
def test_worker_full_run_publishes_the_registered_projection_across_eia_conditions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scenario: str, expected_status: str
) -> None:
    from pring_cycle.projections import ProjectionSetRepository

    paths, material = isolated_lifecycle_material(tmp_path / "runtime")
    candidate = material["candidate_model_version_id"]
    version = material["metric_catalog_version"]
    if scenario != "missing":
        # EIA only: the optional P2 branch must not affect the registered projection.
        paths.secrets.write_text("EIA_API_KEY=fixture-eia-key\n", encoding="utf-8")
        paths.secrets.chmod(0o600)
    requested: list[str] = []
    pages: list[str] = []
    block_history_page(monkeypatch, pages)
    monkeypatch.setattr("pring_cycle.eia_context.build_opener", eia_opener(scenario, requested))
    runs = RunRepository(paths.database)
    run = runs.submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id=f"registered-full-run-eia-{scenario}",
        model_version_id=candidate,
        system_as_of=datetime.now(UTC),
    )

    process_pending_run(paths, report_adapters=())

    stored = runs.get(run.run_id)
    assert stored.status == "completed", stored.error_classification
    assert stored.projection_set_id is not None
    assert len(requested) == (0 if scenario == "missing" else 1)
    projection = ProjectionSetRepository(paths.database).get(stored.projection_set_id)
    assert projection.envelope.model_version_id == candidate
    assert projection.envelope.target_business_date == "2026-08-28"
    context_rows = cast(list[dict[str, Any]], projection.datasets["macro"]["international_context"])
    rows = {row["metric_id"]: row for row in context_rows}
    # Without a usable API key the run falls back to the key-free history page, so the rows
    # carry its channel; a working key keeps the API channel and sends no page request.
    fell_back = scenario != "success"
    assert (len(pages) == 2) is fell_back
    for metric_id in ("EIA_BRENT_RBRTE", "EIA_WTI_RWTC"):
        row = rows[metric_id]
        assert row["acquisition_status"] == ("verified_candidate" if fell_back else expected_status)
        assert row["latest_acquisition"]["channel"] == (
            "eia_html_candidate" if fell_back else "eia_official_candidate"
        )
        assert row["latest_acquisition"]["definition_version"] == version
        assert row["certification_status"] == "awaiting_source_certification"
        assert row["role"] == "context_only_never_formal_stage"
    if scenario == "success":
        brent = EvidenceRepository(paths.database).metric_series(
            "EIA_BRENT_RBRTE",
            mode=AsOfMode.SYSTEM,
            as_of=datetime.now(UTC),
            definition_version=version,
        )
        assert brent[-1].selected_value == 71.25
        assert brent[-1].claims[0].certification_status == "awaiting_source_certification"
    receipts = [
        r
        for r in AcquisitionRepository(paths.database, paths.artifacts).history()
        if r.api_name == "eia_spot_prices"
    ]
    if scenario == "missing":
        assert receipts == []
    else:
        (receipt,) = receipts
        assert receipt.state == ("validated" if scenario == "success" else "failed")
        # The original network or parser exception type stays on the receipt.
        assert (
            receipt.error_type
            == {"success": None, "network": "OSError", "parse": "ValueError"}[scenario]
        )
    adopted = runs.full_retrieval_plan(run.run_id)["adoption"]
    assert adopted is not None and adopted["projection_set_id"] == stored.projection_set_id
