"""The complete registered catalog end to end: an official PPI fallback reaches the report.

The model is the builtin effective catalog, registered and activated directly (ADR-0022);
no admission, replay or acceptance material is built. Core series are the archived TuShare
responses extended with flat sessions to the target; the other TuShare families come from
synthetic rows, PPI is only available from the NBS page, and EIA from its archived page.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.request import Request

import pytest

from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.models import EFFECTIVE_CATALOG_VERSION, ModelRepository, effective_model_manifest
from pring_cycle.projections import ProjectionSetRepository
from pring_cycle.reports import ReportRepository
from pring_cycle.runs import RunRecord, RunRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.storage import database_connection
from pring_cycle.worker import process_pending_run
from tests.fixtures.czce_report import czce_exchange

# The newest model, whatever it is numbered.
CURRENT_MODEL = str(effective_model_manifest()["model_version_id"])

SCRATCH = Path(__file__).parents[2] / ".scratch/pring-data-acquisition-repair"
CORE_TRANSPORT = SCRATCH / "core-transport-196"
TARGET_BUSINESS_DATE = "2026-09-11"
JULY_PPI = SCRATCH / (
    "evidence-a18-import-20260909/b323261248c08ecba00a96cf4401654896fd8a5709ce9bf81c2e38f7d5fbef09"
)
AUGUST_PPI_URL = "https://www.stats.gov.cn/sj/zxfb/202609/t20260909_1965007.html"
AUGUST_CPI_URL = "https://www.stats.gov.cn/sj/zxfb/202609/t20260909_1965006.html"
INVALID_TUSHARE_RESPONSE = b'{"code":0,"data":{"fields":[],"items":[[]]}}'


def trading_days() -> tuple[date, ...]:
    receipts = {
        item["name"]: item
        for item in json.loads((CORE_TRANSPORT / "receipts.json").read_text())["receipts"]
    }
    rows = json.loads((CORE_TRANSPORT / receipts["calendar"]["local_file"]).read_bytes())
    return tuple(
        sorted(
            date.fromisoformat(f"{d[:4]}-{d[4:6]}-{d[6:]}")
            for d, is_open in ((item[0], item[1]) for item in rows["data"]["items"])
            if is_open
        )
    )


def august_ppi_document() -> bytes:
    # Synthetic August release derived from the archived July NBS page: period and publication
    # time are rewritten, so its values are fixture data rather than official August figures.
    return (
        JULY_PPI.read_bytes()
        .replace("2026年7月".encode(), "2026年8月".encode())
        .replace(b"2026/08/09", b"2026/09/09")
        .replace(b"202608/t20260809", b"202609/t20260909")
    )


def serve_august_ppi(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    content = august_ppi_document()
    requested: list[str] = []

    class Response(BytesIO):
        status = 200
        headers = {"Content-Type": "text/html"}

        def __init__(self, body: bytes, url: str) -> None:
            super().__init__(body)
            self.url = url

        def geturl(self) -> str:
            return self.url

    def fetch(request: Any, **kwargs: Any) -> Response:
        requested.append(request.full_url)
        if request.full_url == "https://www.stats.gov.cn/sj/zxfb/":
            # The August CPI release is listed too (CPI has no other history here); only the
            # PPI page is served, so CPI stays a visible gap.
            listing = (
                f'<a href="{AUGUST_PPI_URL}">2026年8月份工业生产者出厂价格</a>'
                f'<a href="{AUGUST_CPI_URL}">2026年8月份居民消费价格</a>'
            )
            return Response(listing.encode(), request.full_url)
        if request.full_url != AUGUST_PPI_URL:
            raise OSError("unrelated fixture official source unavailable")
        return Response(content, request.full_url)

    monkeypatch.setattr("pring_cycle.official_context.urlopen", fetch)
    return requested


def real_core_opener() -> Any:
    """Serve the archived TuShare core responses, filtered to each requested date range."""
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


# The last day the archived calendar states.
ARCHIVE_END = date(2026, 8, 28)


def _compact_date(value: str) -> date:
    return date(int(value[:4]), int(value[4:6]), int(value[6:]))


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
            # The calendar states every day past the archive, closed ones too (ticket 02).
            sessions = {d.strftime("%Y%m%d") for d in EXTENSION_SESSIONS}
            extension = (
                (ARCHIVE_END + timedelta(days=n)).strftime("%Y%m%d")
                for n in range(1, (_compact_date(params["end_date"]) - ARCHIVE_END).days + 1)
            )
            for day in extension if calendar else sorted(sessions):
                if params["start_date"] <= day <= params["end_date"]:
                    row = (
                        {"cal_date": day, "is_open": int(day in sessions)}
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


# Monthly and quarterly families served only when a test asks for them (ticket 30).
MACRO_APIS = frozenset({"cn_pmi", "cn_cpi", "cn_ppi", "cn_m", "sf_month", "cn_gdp"})


def macro_rows(api: str, params: dict[str, Any], fields: list[str]) -> list[list[Any]]:
    """Every requested field of each month (quarter) from 2024 to the requested end, rising.

    Only the requested range is answered, so a narrower request holds fewer periods. Like
    TuShare, January PPI carries a cumulative average the official contract has no member for.
    """
    if api == "cn_gdp":
        periods = [f"{year}Q{quarter}" for year in (2024, 2025, 2026) for quarter in (1, 2, 3, 4)]
        start, end = params["start_q"], params["end_q"]
    else:
        periods = [f"{year}{month:02d}" for year in (2024, 2025, 2026) for month in range(1, 13)]
        start, end = params["start_m"], params["end_m"]
    return [
        [
            period if field in {"month", "quarter"} else round(50.0 + index * 0.3, 2)
            for field in fields
        ]
        for index, period in enumerate(periods)
        if start <= period <= end
    ]


def extended_context_opener(
    requested: list[str], invalid_api: str | None = None, *, macro: bool = False
) -> Any:
    """TuShare context rows continuing the lifecycle material's synthetic series to the target.

    Each series repeats the material importers' values on their own days, so a refresh over the
    material window restates identical facts; other families are unavailable, the monthly and
    quarterly ones unless ``macro`` serves them.
    """
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
            if macro and api in MACRO_APIS:
                fields = payload["fields"].split(",")
                items = macro_rows(api, payload["params"], fields)
            else:
                fields, items = rows(api, payload["params"])
            return BytesIO(
                json.dumps({"code": 0, "data": {"fields": fields, "items": items}}).encode()
            )

    return Opener()


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


def run_full_catalog(
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
    context_requests: list[str],
    *,
    macro: bool = False,
) -> tuple[RuntimePaths, RunRecord, list[str]]:
    """One manual full run of the current model over the extended fixture sources."""
    paths = RuntimePaths.discover(root)
    initialize_runtime(paths)
    models = ModelRepository(paths.database)
    models.register(effective_model_manifest())
    models.activate(CURRENT_MODEL, explicitly_approved=True)
    paths.secrets.write_text("TUSHARE_TOKEN=fixture-only\n")
    paths.secrets.chmod(0o600)
    requested = serve_august_ppi(monkeypatch)
    block_history_page(monkeypatch, [])
    monkeypatch.setattr(
        "pring_cycle.source_adapters.build_opener", lambda *h: extended_core_opener()
    )
    monkeypatch.setattr(
        "pring_cycle.tushare_context.build_opener",
        lambda *h: extended_context_opener(context_requests, macro=macro),
    )
    # TA and CF from CZCE's own report (ADR-0032), over the same sessions as the others.
    sessions = {d for d in (*trading_days(), *EXTENSION_SESSIONS) if d >= date(2026, 3, 2)}
    monkeypatch.setattr("pring_cycle.czce_warrants._fetch", czce_exchange(sessions.__contains__))
    runs = RunRepository(paths.database)
    submitted = runs.submit_manual_full(
        target_business_date=TARGET_BUSINESS_DATE,
        client_request_id="full-automatic-ppi-fallback",
        model_version_id=CURRENT_MODEL,
        system_as_of=datetime.now(UTC),
    )

    process_pending_run(paths, report_adapters=())

    return paths, runs.get(submitted.run_id), requested


@pytest.mark.usefixtures("runtime_clock")
def test_full_worker_falls_back_to_official_ppi_and_exposes_delivery_in_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context_requests: list[str] = []
    paths, stored, requested = run_full_catalog(tmp_path / "runtime", monkeypatch, context_requests)
    runs = RunRepository(paths.database)
    assert stored.status == "completed", stored.error_classification
    assert AUGUST_PPI_URL in requested
    assert "cn_cpi" in context_requests
    projection = ProjectionSetRepository(paths.database).get(stored.projection_set_id or "")
    adopted = set(runs.full_retrieval_plan(stored.run_id)["adoption"]["selected_claim_ids"])
    august = [
        point
        for point in EvidenceRepository(paths.database).metric_series(
            "CN_PPI",
            mode=AsOfMode.SYSTEM,
            as_of=stored.system_as_of,
            definition_version=EFFECTIVE_CATALOG_VERSION,
        )
        if point.period_end == "2026-08-31"
    ]
    assert august and {point.selected_claim_id for point in august} <= adopted
    report = ReportRepository(paths.database).history()[0]
    assert report.projection_set_id == projection.envelope.projection_set_id
    prices = projection.datasets["macro"]["price_chain"]
    rows = [row for row in prices["evidence"] if row["metric_id"] == "CN_PPI"]
    assert rows and all(row["period"] == "2026-08-31" for row in rows)
    assert all(
        claim["provider"] == "国家统计局"
        for row in rows
        for claim in row["claims"]
        if claim["selected"]
    )
    # The report names the source of its PPI reading, not the evidence rows (ADR-0027).
    ppi = report.body["verified_results"]["confirmation"]["key_indicators"]["ppi"]
    assert "国家统计局" in ppi["source"]
    assert projection.datasets["cycle_overview"]["gap_list"]


class _TwoYearStarts:
    """The ranges before ticket 30: two years back for periods, 220 days for days."""

    def __init__(self, target: date) -> None:
        self.target = target
        self.daily = target - timedelta(days=220)

    def period(self, *metric_ids: str) -> str:
        quarter = (self.target.month - 1) // 3 + 1
        if "CN_GDP" in metric_ids:
            return f"{self.target.year - 2}Q{quarter}"
        return date(self.target.year - 2, self.target.month, 1).strftime("%Y%m")


def _analysis(projection: Any) -> dict[str, object]:
    """What a run concluded, without identities, request parameters or fetch times."""

    def rows(value: object) -> list[tuple[object, ...]]:
        if isinstance(value, dict):
            own = (
                [
                    (
                        value.get("metric_id") or value.get("name") or value.get("formula"),
                        json.dumps(value.get("dimensions"), sort_keys=True),
                        value.get("period"),
                        value.get("value"),
                        value.get("direction"),
                        value.get("status"),
                        value.get("state"),
                    )
                ]
                # A formula's document and a card's state count as much as a row.
                if "status" in value and ({"value", "state", "direction"} & value.keys())
                else []
            )
            return own + [row for child in value.values() for row in rows(child)]
        if isinstance(value, list):
            return [row for child in value for row in rows(child)]
        return []

    datasets = projection.datasets
    return {
        "stage": datasets["cycle_overview"]["current_stage"],
        "assets": [
            (item["asset"], item["state"], item["reason"])
            for item in datasets["core_assets"]["assets"]
        ],
        "macro": sorted(rows(datasets["macro"]), key=repr),
        "inventory": sorted(rows(datasets["inventory"]), key=repr),
    }


def _days(root: Path) -> dict[str, dict[str, object]]:
    """Each summarized day's conclusions, by business date."""
    paths = RuntimePaths.discover(root)
    with database_connection(paths.database) as connection:
        published = connection.execute(
            "SELECT projection_set_id, json_extract(envelope_json, '$.target_business_date') "
            "FROM projection_set"
        ).fetchall()
    repository = ProjectionSetRepository(paths.database)
    return {day: _analysis(repository.get(projection_id)) for projection_id, day in published}


def _february_cumulative_ppi(
    day: str, conclusions: dict[str, object], direction: str
) -> tuple[str, str, bool]:
    """A day's conclusions, February's cumulative PPI checked to go ``direction``, then dropped."""
    kept: dict[str, object] = {}
    february = False
    for key, value in conclusions.items():
        if key not in {"macro", "inventory"}:
            kept[key] = value
            continue
        rows = []
        for row in value:  # type: ignore[attr-defined]
            if (
                row[0] == "CN_PPI"
                and '"cumulative_average_yoy"' in row[1]
                and row[2] == "2026-02-28"
            ):
                assert row[4] == direction, (day, row)
                february = True
                row = (*row[:4], None, *row[5:])
            rows.append(row)
        kept[key] = rows
    return day, repr(kept), february


@pytest.mark.usefixtures("runtime_clock")
def test_a_fetch_from_before_the_window_concludes_what_two_years_did(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Starting each family before the window's first day changes no conclusion (#30)."""
    narrow_requests: list[str] = []
    paths, narrow, _ = run_full_catalog(
        tmp_path / "narrow", monkeypatch, narrow_requests, macro=True
    )
    narrow_projection = ProjectionSetRepository(paths.database).get(narrow.projection_set_id or "")
    wide_requests: list[str] = []
    with monkeypatch.context() as wide_patch:
        wide_patch.setattr(
            "pring_cycle.worker._window_fetch_starts",
            lambda paths, target, as_of=None: _TwoYearStarts(target),
        )
        paths, wide, _ = run_full_catalog(tmp_path / "wide", wide_patch, wide_requests, macro=True)
    wide_projection = ProjectionSetRepository(paths.database).get(wide.projection_set_id or "")

    assert narrow.status == wide.status == "completed"
    assert _analysis(narrow_projection) == _analysis(wide_projection)
    # Every summarized day concludes the same, the window's first day included.
    narrow_days, wide_days = _days(tmp_path / "narrow"), _days(tmp_path / "wide")
    assert len(narrow_days) > 100
    # February's cumulative PPI, which January lacks, is compared with December's in both:
    # the narrow range reaches back as far as the confirmation readings declare (macro
    # semantics 02), past the year's turn.
    narrow_kept = {
        _february_cumulative_ppi(day, conclusions, "up") for day, conclusions in narrow_days.items()
    }
    assert narrow_kept == {
        _february_cumulative_ppi(day, conclusions, "up") for day, conclusions in wide_days.items()
    }
    # The days February was the newest PPI out: from the window's first to April's release.
    assert sorted(day for day, _kept, february in narrow_kept if february) == [
        "2026-03-23",
        "2026-03-24",
        "2026-03-25",
        "2026-03-26",
        "2026-03-27",
        "2026-03-30",
        "2026-03-31",
        "2026-04-01",
        "2026-04-02",
        "2026-04-03",
        "2026-04-07",
        "2026-04-08",
        "2026-04-09",
    ]
    # The monthly and quarterly families were answered, the window's first day compared.
    first_day = narrow_days[min(narrow_days)]
    compared = {
        row[0]
        for row in first_day["macro"]  # type: ignore[attr-defined]
        if row[4] in {"up", "down"}
    }
    assert {"CN_CPI_HEADLINE", "CN_PPI", "CN_M1_M2", "CN_SF_TOTAL"} <= compared, compared
    # The TuShare context requests each range took, by interface (recorded in ticket 30).
    with capsys.disabled():
        print(
            "\nTUSHARE_CONTEXT_REQUESTS",
            json.dumps(
                {
                    "narrow": dict(sorted(Counter(narrow_requests).items())),
                    "wide": dict(sorted(Counter(wide_requests).items())),
                },
                ensure_ascii=False,
            ),
        )
    narrow_count, wide_count = Counter(narrow_requests), Counter(wide_requests)
    # Each range is one call per family; the warrants' daily chunks are what shrink.
    assert narrow_count["fut_wsr"] < wide_count["fut_wsr"]
    assert {api: n for api, n in narrow_count.items() if api != "fut_wsr"} == {
        api: n for api, n in wide_count.items() if api != "fut_wsr"
    }
