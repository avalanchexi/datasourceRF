"""Complete isolated model lifecycle: public admission, calibration, replay and activation.

All inputs are synthetic test materials: real core transport bytes are acquired through the public
adapter, publication times are marked ``synthetic:``, and no actual source is certified.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from functools import partial
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.acquisition import AcquisitionRepository
from pring_cycle.evidence import EvidenceRepository, EvidenceValueState, SourceClaimInput
from pring_cycle.models import CALIBRATION_BASELINE, ModelRepository
from pring_cycle.projections import ProjectionSetRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.source_adapters import CORE_API_IDENTITIES, TushareCoreAdapter
from tests.models.test_candidate_admission import (
    bind_synthetic_review,
    encode,
    prepared_capacity_mapping_request,
    save,
    save_amount_breadth_review,
    save_breadth_review,
    submit,
    synthetic_breadth_universe,
    synthetic_coherent_gdp_release,
)

SCRATCH = Path(__file__).parents[2] / ".scratch/pring-data-acquisition-repair"
CORE_TRANSPORT = SCRATCH / "core-transport-196"
REPLAY_START = "2026-03-09"
REPLAY_END = "2026-08-28"


def invoke_process(*arguments: str) -> dict[str, Any]:
    """Run one public CLI command in its own process, releasing its memory when it exits.

    Calibration, the 120-day replay and activation each build large evaluation documents.
    """
    import subprocess
    import sys

    completed = subprocess.run(
        [sys.executable, "-m", "pring_cycle", *arguments, "--json"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr[-4000:]
    document: dict[str, Any] = json.loads(completed.stdout)
    return document


def trading_days() -> tuple[date, ...]:
    receipts = {
        item["name"]: item
        for item in json.loads((CORE_TRANSPORT / "receipts.json").read_text())["receipts"]
    }
    rows = json.loads((CORE_TRANSPORT / receipts["calendar"]["local_file"]).read_bytes())
    return tuple(
        sorted(
            date.fromisoformat(f"{d[:4]}-{d[4:6]}-{d[6:]}")
            for d, is_open in rows["data"]["items"]
            if is_open == 1
        )
    )


def admit_complete_candidate(paths: RuntimePaths, capsys: pytest.CaptureFixture[str]) -> str:
    # The reviewed Q1 capacity mapping is bound at admission, as its registered contract requires.
    request, _, _, _, _ = prepared_capacity_mapping_request(paths, side="isolated-lifecycle")
    # Reviewed derived families use their registered contracts; GDP is a required
    # credit-impulse input, so its P2 definition must be certified too.
    manifest = request["manifest"]
    registered_sources = {
        "CN_EQ_ADV_DEC": "tushare:daily:breadth-v0002",
        "CN_EQ_AD_RATIO": "tushare:daily:breadth-v0002",
        "CN_EQ_NEW_HIGH_LOW_120": "tushare:daily:breadth-window-v0002",
        "CN_EQ_ABOVE_MA120": "tushare:daily:breadth-window-v0002",
        "CN_EQ_ADV_AMOUNT_SHARE": "tushare:daily:breadth-amount-v0002",
        "CN_COMMODITY_EX_HOG_BASKET": "tushare:fut_daily:ex-hog-calendar-settlement-v0002",
        "CN_COMMODITY_SLEEVE_CONTRIBUTION": "tushare:fut_daily:ex-hog-calendar-settlement-v0002",
    }
    # PPI precedes its month's inventory release; the common-month formula stays computable.
    manifest["derived_formula_versions"]["real_inventory_approximation"] = (
        "inventory-ppi-common-month-v0002"
    )
    for item in manifest["metric_definitions"]:
        if item["metric_id"] in registered_sources:
            item["source_codes"] = [registered_sources[item["metric_id"]]]
        if item["metric_id"] == "CN_GDP":
            item["certification_status"] = "certified"
    package_hash = request["package_hashes"][0]
    package = json.loads((paths.artifacts / package_hash[:2] / package_hash).read_bytes())
    package["definition_bindings"] = {
        item["metric_id"]: hashlib.sha256(encode(item)).hexdigest()
        for item in manifest["metric_definitions"]
        if item["metric_id"] in package["definition_bindings"] or item["metric_id"] == "CN_GDP"
    }
    bind_synthetic_review(paths, request, package)
    submit(paths, save(paths, request))
    return str(json.loads(capsys.readouterr().out)["model_version_id"])


def import_core_histories(
    paths: RuntimePaths, definition_version: str, clock: Callable[[], datetime]
) -> None:
    receipts = {
        item["name"]: item
        for item in json.loads((CORE_TRANSPORT / "receipts.json").read_text())["receipts"]
    }
    days = trading_days()
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    evidence = EvidenceRepository(paths.database)
    for metric_id, (api, code) in CORE_API_IDENTITIES.items():
        raw = (CORE_TRANSPORT / receipts[metric_id]["local_file"]).read_bytes()
        closes = {row[1]: float(row[2]) for row in json.loads(raw)["data"]["items"]}

        def transport(payload: dict[str, Any], body: bytes = raw) -> bytes:
            return body

        receipt = (
            TushareCoreAdapter("synthetic-token", transport=transport)
            .acquire_core_bars(
                acquisitions,
                metric_id,
                start=days[0],
                end=days[-1],
                expected_business_dates=days,
            )
            .receipt
        )
        assert receipt.received_at is not None
        claims = []
        for catalog in (definition_version, "metric-catalog-v0001"):
            registered = catalog == definition_version
            for day in days:
                published = datetime(day.year, day.month, day.day, 8, tzinfo=UTC)
                claims.append(
                    SourceClaimInput(
                        metric_id=metric_id,
                        definition_version=catalog,
                        period_kind="business_day",
                        period_start=day.isoformat(),
                        period_end=day.isoformat(),
                        dimensions={},
                        value=closes[day.strftime("%Y%m%d")],
                        value_state=EvidenceValueState.REPORTED_VALUE,
                        unit="index_points",
                        provider="tushare" if registered else "fixture",
                        source_reference=(
                            f"tushare:{api}:{code}:{day.isoformat()}"
                            if registered
                            else f"fixture:{catalog}:{metric_id}:{day.isoformat()}"
                        ),
                        release_event_id=f"synthetic:core-public:{catalog}:{metric_id}:{day}",
                        release_at=published,
                        public_available_at=published,
                        fetched_at=receipt.received_at if registered else published,
                        available_at=clock() if registered else published,
                        certification_status="certified",
                        quality_status="validated",
                        acquisition_id=receipt.acquisition_id if registered else None,
                    )
                )
        evidence.append_source_claims(tuple(claims))


def import_lpr_announcements(
    paths: RuntimePaths, definition_version: str, clock: Callable[[], datetime]
) -> None:
    from pring_cycle.official_lpr import ingest_lpr_document

    folder = SCRATCH / "evidence-lpr-import-20260908"
    # Real archived announcements; the parser derives their publication times.
    for item in json.loads((folder / "receipts.json").read_text())["receipts"]:
        receipt = item["receipt"]
        ingest_lpr_document(
            paths,
            (folder / receipt["raw_hash"]).read_bytes(),
            source_url=receipt["parameters"]["source_url"],
            fetched_at=clock(),
            expected_period=receipt["parameters"]["period"],
            definition_version=definition_version,
            clock=clock,
        )


def import_official_archive(
    paths: RuntimePaths, definition_version: str, clock: Callable[[], datetime]
) -> None:
    from pring_cycle.official_context import ingest_official_context_document

    folder = SCRATCH / "evidence-a18-import-20260909"
    # Real archived official releases; the parsers derive their publication times.
    for item in json.loads((folder / "receipts.json").read_text())["receipts"]:
        if item.get("status") != "captured" or item["receipt"]["state"] != "validated":
            continue
        ingest_official_context_document(
            paths,
            (folder / item["artifact_sha256"]).read_bytes(),
            family=item["family"],
            source_url=item["source_url"],
            expected_period=item["period"],
            fetched_at=clock(),
            definition_version=definition_version,
            clock=clock,
        )


def import_gdp_releases(
    paths: RuntimePaths, definition_version: str, clock: Callable[[], datetime]
) -> None:
    from pring_cycle.official_context import ingest_official_context_document

    # Synthetic mutually comparable releases; the real archived vintages are not comparable
    # across publications and cannot supply the credit-impulse window (see manifest 186).
    for year, quarter in [(y, q) for y in (2024, 2025) for q in (1, 2, 3, 4)] + [
        (2026, 1),
        (2026, 2),
    ]:
        period = f"{year}-Q{quarter}"
        raw, source_url = synthetic_coherent_gdp_release(period)
        ingest_official_context_document(
            paths,
            raw,
            family="nbs_gdp",
            source_url=source_url,
            expected_period=period,
            fetched_at=clock(),
            definition_version=definition_version,
            clock=clock,
        )


def import_rrr_notice(
    paths: RuntimePaths, definition_version: str, clock: Callable[[], datetime]
) -> None:
    from pring_cycle.official_context import ingest_official_context_document

    digest = "27d57bb20481abc714ea45c9d99dd532652df8ee92c263b1a15cc222c256a3d9"
    # Real archived May 2025 notice; still within the RRR event freshness at the replay end.
    ingest_official_context_document(
        paths,
        (SCRATCH / "evidence-search-preexperiment-20260908-n4-v1" / digest).read_bytes(),
        family="pbc_rrr_notice",
        source_url="https://www.pbc.gov.cn/goutongjiaoliu/113456/113469/2025092212554653911/index.html",
        expected_period="2025-05",
        fetched_at=clock(),
        definition_version=definition_version,
        clock=clock,
    )


def synthetic_public_scalars(scalars: tuple[Any, ...]) -> tuple[Any, ...]:
    """Mark each daily scalar with a synthetic publication time after that session."""
    return tuple(
        replace(
            scalar,
            release_at=(published := datetime.fromisoformat(f"{scalar.period_end}T08:00:00+00:00")),
            public_available_at=published,
        )
        for scalar in scalars
    )


def window_days(start: str, end: str = REPLAY_END) -> tuple[date, ...]:
    return tuple(day for day in trading_days() if start <= day.isoformat() <= end)


def import_interbank_rates(paths: RuntimePaths, definition_version: str) -> None:
    from pring_cycle.tushare_context import TushareContextAdapter

    days = window_days("2026-02-20")
    # Synthetic TuShare rows on the real trading calendar; covers the policy-spread warmup.
    rows = {
        "repo_daily": (
            ["ts_code", "trade_date", "repo_maturity", "weight"],
            [
                ["DR007.IB", d.strftime("%Y%m%d"), "DR007", 1.40 + i % 5 / 100]
                for i, d in enumerate(days)
            ],
        ),
        "shibor": (
            ["date", "on", "1w", "3m"],
            [[d.strftime("%Y%m%d"), 1.30, 1.38, 1.43] for d in days],
        ),
    }

    def transport(payload: dict[str, Any]) -> bytes:
        fields, items = rows[payload["api_name"]]
        return encode({"code": 0, "data": {"fields": fields, "items": items}})

    adapter = TushareContextAdapter("synthetic-token", transport=transport)
    adapter.acquire_scalars(
        paths,
        lambda: synthetic_public_scalars(
            adapter.transmission(start_date=days[0], end_date=days[-1])
        ),
        definition_version=definition_version,
    )


def import_market_daily(paths: RuntimePaths, definition_version: str) -> None:
    from pring_cycle.tushare_context import TushareContextAdapter

    days = window_days("2026-03-02")
    compact = [d.strftime("%Y%m%d") for d in days]

    # Synthetic TuShare rows on the real trading calendar for indices, margin and valuation.
    def transport(payload: dict[str, Any]) -> bytes:
        api, code = payload["api_name"], payload["params"].get("ts_code")
        if api in {"index_daily", "fut_index_daily"}:
            fields = ["ts_code", "trade_date", "close"]
            items = [[code, d, 1000.0 + i] for i, d in enumerate(compact)]
        elif api == "margin":
            fields = ["trade_date", "exchange_id", "rzye", "rzmre"]
            items = [
                [d, exchange, 100_000_000 * (n + 1), 10_000_000 * (n + 1)]
                for d in compact
                for n, exchange in enumerate(("SSE", "SZSE", "BSE"))
            ]
        elif api == "index_dailybasic":
            fields = ["ts_code", "trade_date", "pe", "pb", "turnover_rate"]
            items = [[code, d, 12.5, 1.4, 0.8] for d in compact]
        else:
            raise AssertionError(api)
        return encode({"code": 0, "data": {"fields": fields, "items": items}})

    adapter = TushareContextAdapter("synthetic-token", transport=transport)

    def published(retrieve: Callable[..., tuple[Any, ...]]) -> tuple[Any, ...]:
        return synthetic_public_scalars(retrieve(start_date=days[0], end_date=days[-1]))

    for retrieve in (adapter.market_indices, adapter.margin_financing, adapter.index_valuation):
        adapter.acquire_scalars(
            paths, partial(published, retrieve), definition_version=definition_version
        )


def import_futures_warrants(paths: RuntimePaths, definition_version: str) -> None:
    from pring_cycle.tushare_context import TushareContextAdapter

    days = window_days("2026-03-02")
    listing = {
        "CU": ("SHFE", "吨"),
        "RB": ("SHFE", "吨"),
        "RU": ("SHFE", "吨"),
        "SP": ("SHFE", "吨"),
        "SC": ("INE", "桶"),
        "PP": ("DCE", "手"),
        "CF": ("CZCE", "张"),
        "PTA": ("CZCE", "张"),
    }

    # Synthetic fut_wsr rows: one warehouse per symbol on each real trading day of the request.
    def transport(payload: dict[str, Any]) -> bytes:
        params = payload["params"]
        exchange, unit = listing[params["symbol"]]
        items = [
            [d.strftime("%Y%m%d"), params["symbol"], "合成仓库", 100, 100, 0, unit, exchange]
            for d in days
            if params["start_date"] <= d.strftime("%Y%m%d") <= params["end_date"]
        ]
        fields = [
            "trade_date",
            "symbol",
            "warehouse",
            "pre_vol",
            "vol",
            "vol_chg",
            "unit",
            "exchange",
        ]
        return encode({"code": 0, "data": {"fields": fields, "items": items}})

    adapter = TushareContextAdapter("synthetic-token", transport=transport)
    adapter.acquire_scalars(
        paths,
        lambda: synthetic_public_scalars(
            tuple(
                scalar
                for symbol in ("CF", "CU", "PP", "RB", "RU", "SC", "SP", "TA")
                for scalar in adapter.futures_warrants(
                    start_date=days[0], end_date=days[-1], symbol=symbol
                )
            )
        ),
        definition_version=definition_version,
    )


def import_market_breadth(paths: RuntimePaths, definition_version: str) -> None:
    from pring_cycle.tushare_context import TushareContextAdapter

    all_days = trading_days()
    outputs = window_days("2026-03-02")
    first = all_days.index(outputs[0]) - 121
    days = all_days[first:]
    compact = [d.strftime("%Y%m%d") for d in days]
    universe = synthetic_breadth_universe(paths)
    universe["members"] = universe["members"][:3]
    universe["coverage_start"] = days[0].isoformat()
    universe["coverage_end"] = days[-1].isoformat()
    before = datetime.combine(days[0] - timedelta(days=1), datetime.min.time(), UTC).isoformat()
    universe["evidence"][0].update(release_at=before, public_available_at=before)
    universe["publications"] = {}
    for day in days:
        proof = save(paths, {"synthetic": True, "published_prices_and_suspensions": str(day)})
        published = datetime(day.year, day.month, day.day, 8, tzinfo=UTC).isoformat()
        universe["evidence"].append(
            {
                "artifact_hash": proof,
                "source_reference": "synthetic:dated-market-publication",
                "release_at": published,
                "public_available_at": published,
            }
        )
        universe["publications"][day.isoformat()] = [proof]
    universe_hash = save_breadth_review(paths, universe)
    # One rising, one falling and one flat ordinary A share; references chain day to day.
    closes = {
        "600000.SH": [10.0 + i / 100 for i in range(len(days))],
        "000001.SZ": [20.0 - i / 100 for i in range(len(days))],
        "920001.BJ": [15.0 for _ in days],
    }
    quotes = [
        {
            "ts_code": code,
            "trade_date": compact[i],
            "close": f"{values[i]:.2f}",
            "pre_close": f"{values[max(i - 1, 0)]:.2f}",
            "vol": "1",
        }
        for code, values in closes.items()
        for i in range(len(days))
    ]
    coverage_hash = save(paths, {"synthetic": True, "kind": "complete corporate-action coverage"})
    window_inputs = {
        "schema_version": "market-breadth-window-inputs-v0001",
        "coverage_start": days[0].isoformat(),
        "coverage_end": days[-1].isoformat(),
        "coverage_evidence": [coverage_hash],
        "adjustments": [],
        "evidence": [
            {
                "artifact_hash": coverage_hash,
                "source_reference": "synthetic:official-actions",
                "release_at": before,
                "public_available_at": before,
            }
        ],
    }
    window_hash = save(
        paths,
        {
            **window_inputs,
            "review_hash": save(
                paths,
                {
                    "schema_version": "market-breadth-window-review-v0001",
                    "subject_hash": hashlib.sha256(encode(window_inputs)).hexdigest(),
                    "reviewer": "synthetic adjustment reviewer",
                    "reviewed_at": "2026-09-13T00:00:00+00:00",
                    "decision": "accepted",
                },
            ),
        },
    )
    amount_hash = save_amount_breadth_review(
        paths, synthetic_amount_window(paths, universe["members"], outputs, before)
    )

    def transport(payload: dict[str, Any]) -> bytes:
        params, api = payload["params"], payload["api_name"]
        rows: list[dict[str, Any]]
        if api == "trade_cal":
            rows = [
                {"cal_date": d, "is_open": 1}
                for d in compact
                if params["start_date"] <= d <= params["end_date"]
            ]
        elif api == "daily":
            rows = [q for q in quotes if q["trade_date"] == params["trade_date"]]
        else:
            rows = []
        fields = payload["fields"].split(",")
        items = [[row[field] for field in fields] for row in rows]
        return encode({"code": 0, "data": {"fields": fields, "items": items}})

    adapter = TushareContextAdapter("synthetic-token", transport=transport)
    options: tuple[dict[str, Any], ...] = (
        {},
        {"window_inputs_hash": window_hash, "output_days": len(outputs)},
        {"amount_inputs_hash": amount_hash},
    )
    for option in options:
        adapter.acquire_scalars(
            paths,
            partial(
                adapter.market_breadth,
                start_date=outputs[0],
                end_date=outputs[-1],
                universe_hash=universe_hash,
                **option,
            ),
            definition_version=definition_version,
        )


def synthetic_amount_window(
    paths: RuntimePaths, members: list[dict[str, Any]], days: tuple[date, ...], public_at: str
) -> dict[str, Any]:
    methods = ["auction", "after_hours", "block"]
    until = (days[-1] + timedelta(days=1)).isoformat()
    coverage_hash = save(
        paths,
        {
            "synthetic": True,
            "scope": "complete ordinary A exchange turnover for this fixture",
            "effective_from": days[0].isoformat(),
            "effective_until": until,
            "methods": methods,
            "disjoint": True,
            "daily_amount_unit": "thousand_yuan",
            "block_amount_unit": "ten_thousand_yuan",
        },
    )
    evidence = [
        {
            "artifact_hash": coverage_hash,
            "source_reference": "synthetic:complete-disjoint-amount-coverage",
            "release_at": public_at,
            "public_available_at": public_at,
        }
    ]
    amount_days = []
    for day in days:
        compact = day.strftime("%Y%m%d")
        published = datetime(day.year, day.month, day.day, 8, tzinfo=UTC).isoformat()
        # Each session's amounts are a separate delivery published after that session.
        daily_hash = save(
            paths,
            {
                "code": 0,
                "data": {
                    "fields": ["ts_code", "trade_date", "amount", "ah_amount"],
                    "items": [[m["ts_code"], compact, "100", "10"] for m in members],
                },
            },
        )
        block_hash = save(
            paths,
            {
                "code": 0,
                "data": {
                    "fields": ["ts_code", "trade_date", "amount"],
                    "items": [[m["ts_code"], compact, "2"] for m in members],
                },
            },
        )
        evidence.extend(
            {
                "artifact_hash": digest,
                "source_reference": f"{reference}:{day.isoformat()}",
                "release_at": published,
                "public_available_at": published,
            }
            for digest, reference in (
                (daily_hash, "synthetic:tushare-daily-amounts"),
                (block_hash, "synthetic:tushare-block-amounts"),
            )
        )
        amount_days.append(
            {
                "business_date": day.isoformat(),
                "members": [
                    {
                        "security_id": m["security_id"],
                        "ts_code": m["ts_code"],
                        "required_methods": methods,
                        "components": [
                            {
                                "methods": [method],
                                "state": "reported",
                                "artifact_hash": digest,
                                "field": field,
                                "unit": unit,
                            }
                            for method, digest, field, unit in (
                                ("auction", daily_hash, "amount", "thousand_yuan"),
                                ("after_hours", daily_hash, "ah_amount", "thousand_yuan"),
                                ("block", block_hash, "amount", "ten_thousand_yuan"),
                            )
                        ],
                    }
                    for m in members
                ],
            }
        )
    return {
        "schema_version": "market-breadth-amount-inputs-v0001",
        "coverage_start": days[0].isoformat(),
        "coverage_end": days[-1].isoformat(),
        "coverage_evidence": [coverage_hash],
        "coverage_rules": [
            {
                "security_id": m["security_id"],
                "exchange": m["ts_code"].split(".")[1],
                "effective_from": days[0].isoformat(),
                "effective_until": until,
                "methods": methods,
                "evidence": [coverage_hash],
            }
            for m in members
        ],
        "evidence": evidence,
        "days": amount_days,
    }


def import_commodity_basket(paths: RuntimePaths, definition_version: str) -> None:
    from pring_cycle.commodity_basket import persist_commodity_basket
    from pring_cycle.evidence import AsOfMode
    from pring_cycle.futures_inputs import bind_futures_input_evidence
    from pring_cycle.tushare_context import TushareContextAdapter
    from tests.adapters.test_commodity_basket import (
        BASKET_CONTRACTS,
        encode_document,
        encode_rows,
        save_synthetic_document,
    )

    open_days = {d.isoformat() for d in window_days("2026-03-02")}
    days = sorted(d for d in open_days if d >= "2026-03-06")
    months = [f"2026{m:02d}" for m in range(3, 11)]

    def is_open(day: date) -> bool:
        # Real sessions inside the replay window; synthetic weekdays after it.
        return day.isoformat() in open_days if day <= date(2026, 8, 28) else day.weekday() < 5

    def last_trading_day(month: str) -> str:
        day = date(int(month[:4]), int(month[4:]), 14)
        while not is_open(day):
            day -= timedelta(days=1)
        return day.strftime("%Y%m%d")

    def contracts(product: str) -> list[dict[str, Any]]:
        code, exchange, _ = BASKET_CONTRACTS[product]
        suffix, unit = code.split(".")[1], "桶" if product == "SC" else "吨"
        return [
            {
                "ts_code": f"{product}{month[2:]}.{suffix}",
                "symbol": f"{product}{month[2:]}",
                "exchange": exchange,
                "fut_code": product,
                "d_month": month,
                "list_date": "20250101",
                "delist_date": last_trading_day(month),
                "quote_unit": "人民币元/" + unit,
                "per_unit": 1000 if product == "SC" else 10,
                "trade_unit": unit,
            }
            for month in months
        ]

    # Synthetic contract, calendar and flat settlement deliveries across the replay window.
    def transport(payload: dict[str, Any]) -> bytes:
        params = payload["params"]
        start, end = date.fromisoformat(params.get("start_date", "20260101")), None
        if payload["api_name"] == "fut_basic":
            return encode_rows(contracts(params["fut_code"]))
        end = date.fromisoformat(params["end_date"])
        span = [start + timedelta(days=n) for n in range((end - start).days + 1)]
        if payload["api_name"] == "fut_trade_cal":
            return encode_rows(
                [
                    {
                        "exchange": params["exchange"],
                        "cal_date": d.isoformat(),
                        "is_open": int(is_open(d)),
                    }
                    for d in span
                ]
            )
        assert payload["api_name"] == "fut_daily"
        return encode_rows(
            [
                {
                    "ts_code": params["ts_code"],
                    "trade_date": d.strftime("%Y%m%d"),
                    "pre_settle": "100",
                    "settle": "100",
                    "close": "999",
                }
                for d in span
                if d.isoformat() in open_days
            ]
        )

    acquired = TushareContextAdapter("synthetic-token", transport=transport).acquire_futures_inputs(
        paths,
        products=tuple(BASKET_CONTRACTS),
        start_date=date(2026, 3, 6),
        end_date=date(2026, 8, 28),
    )
    repository = AcquisitionRepository(paths.database, paths.artifacts)
    proof = save_synthetic_document(paths, {"synthetic": True, "purpose": "lifecycle basket"})
    listed_at = "2026-01-01T08:00:00+00:00"
    publications = []
    for identity in acquired.acquisition_ids:
        receipt = repository.get(identity)
        rows = json.loads(repository.read_content(identity, "raw"))["data"]["items"]
        for day in (
            sorted({f"{r[1][:4]}-{r[1][4:6]}-{r[1][6:]}" for r in rows})
            if receipt.api_name == "fut_daily"
            else [None]
        ):
            published = listed_at if day is None else day + "T08:00:00+00:00"
            publications.append(
                {
                    "api_name": receipt.api_name,
                    "parameters": receipt.parameters,
                    "raw_hash": receipt.raw_hash,
                    "business_date": day,
                    "release_at": published,
                    "public_available_at": published,
                    "evidence": [proof],
                }
            )
    packet = {
        "schema_version": "futures-input-evidence-v0001",
        "evidence": [{"artifact_hash": proof, "source_reference": "synthetic:lifecycle-basket"}],
        "publications": publications,
        "sessions": [
            {
                "product": product,
                "exchange": exchange,
                "business_date": day,
                "session_start_at": previous + "T21:00:00+08:00",
                "release_at": listed_at,
                "public_available_at": listed_at,
                "evidence": [proof],
            }
            for product, (_, exchange, _) in BASKET_CONTRACTS.items()
            for previous, day in zip(["2026-03-05", *days], days, strict=False)
        ],
    }
    review = save_synthetic_document(
        paths,
        {
            "schema_version": "futures-input-evidence-review-v0001",
            "subject_hash": hashlib.sha256(encode_document(packet)).hexdigest(),
            "reviewer": "synthetic lifecycle reviewer",
            "reviewed_at": "2026-09-07T00:00:00+00:00",
            "decision": "accepted",
        },
    )
    bind_futures_input_evidence(
        paths,
        acquisition_ids=acquired.acquisition_ids,
        evidence_hash=save_synthetic_document(paths, {**packet, "review_hash": review}),
    )
    for day in days[1:]:
        business_date = date.fromisoformat(day)
        result = persist_commodity_basket(
            paths,
            business_date=business_date,
            as_of=datetime(
                business_date.year, business_date.month, business_date.day, 12, tzinfo=UTC
            ),
            mode=AsOfMode.PUBLIC,
            definition_version=definition_version,
        )
        assert result["missing"] == [], (day, result["missing"])


def prepare_isolated_candidate_inputs(
    paths: RuntimePaths, capsys: Any, clock: Callable[[], datetime]
) -> str:
    """Admit the complete synthetic candidate and import every family's replay inputs.

    ``clock`` must be one advancing timeline also patched into the acquisition modules, as the
    ``runtime_clock`` fixture does; tests/fixtures/isolated_lifecycle_inputs.py runs this.
    """
    initialize_runtime(paths)
    models = ModelRepository(paths.database)
    # Isolated comparison baseline bootstrap, as in the existing replay tests.
    models.record_acceptance("model-v0001", CALIBRATION_BASELINE)
    models.activate("model-v0001", explicitly_approved=True)

    candidate_id = admit_complete_candidate(paths, capsys)
    version = models.manifest(candidate_id)["metric_catalog_version"]
    import_core_histories(paths, version, clock)
    for catalog in (version, "metric-catalog-v0001"):
        import_lpr_announcements(paths, catalog, clock)
    import_official_archive(paths, version, clock)
    import_gdp_releases(paths, version, clock)
    import_rrr_notice(paths, version, clock)
    import_interbank_rates(paths, version)
    import_market_daily(paths, version)
    import_futures_warrants(paths, version)
    import_market_breadth(paths, version)
    import_commodity_basket(paths, version)
    return candidate_id


def build_complete_isolated_lifecycle(paths: RuntimePaths) -> dict[str, Any]:
    """Admit, calibrate, replay and activate the complete synthetic candidate publicly.

    Each stage runs in its own process so the large evaluation documents of calibration,
    the 120-day replay and activation never accumulate in the test process.
    """
    import subprocess
    import sys

    assert paths.override_root is not None
    prepared = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).parents[1] / "fixtures/isolated_lifecycle_inputs.py"),
            str(paths.override_root),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert prepared.returncode == 0, prepared.stderr[-4000:]
    candidate_id = str(json.loads(prepared.stdout.splitlines()[-1])["candidate_model_version_id"])
    common = ("--runtime-root", str(paths.override_root))

    accepted = invoke_process("model-accept", *common, "--model", candidate_id)
    assert accepted["status"] == "accepted"
    replay = invoke_process(
        "model-replay",
        *common,
        "--model",
        candidate_id,
        "--compared-with",
        "model-v0001",
        "--start",
        REPLAY_START,
        "--end",
        REPLAY_END,
    )
    assert replay["gaps"] == [], json.dumps(replay["gaps"], ensure_ascii=False)
    assert replay["status"] == "passed"
    activated = invoke_process("model-activate", *common, "--model", candidate_id, "--confirm")
    assert activated["status"] == "active"
    return {
        "candidate_model_version_id": candidate_id,
        "comparison_model_version_id": "model-v0001",
        "acceptance_result_hash": accepted["result_hash"],
        "replay_id": replay["replay_id"],
        "replay_calendar_hash": replay["calendar_hash"],
        "replay_trading_days": replay["evaluated_trading_days"],
    }


MATERIAL_SCHEMA = "isolated-lifecycle-material-v0001"
MATERIAL_BUILDERS = (
    Path(__file__),
    Path(__file__).parents[1] / "models/test_candidate_admission.py",
    Path(__file__).parents[1] / "adapters/test_commodity_basket.py",
    Path(__file__).parents[1] / "conftest.py",
    Path(__file__).parents[1] / "fixtures/isolated_lifecycle_inputs.py",
)
MATERIAL_INPUTS = (
    CORE_TRANSPORT,
    SCRATCH / "evidence-lpr-import-20260908",
    SCRATCH / "evidence-a18-import-20260909",
    SCRATCH / "evidence-official-consumer-edge",
    SCRATCH / "evidence-search-preexperiment-20260908-n4-v1",
    SCRATCH / "capacity-q1-source-mapping-decision.md",
)


def _content_hashes(roots: tuple[Path, ...]) -> dict[str, str]:
    files = sorted(
        path
        for root in roots
        for path in ([root] if root.is_file() else root.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts
    )
    project = Path(__file__).parents[2]
    return {
        str(path.relative_to(project)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in files
    }


def material_identity(paths: RuntimePaths) -> dict[str, Any]:
    """Everything a stored material depends on; any change requires a new build."""
    from pring_cycle.runtime_fingerprint import execution_fingerprint

    fingerprint = execution_fingerprint(paths)
    # The migration head is part of the code; a not-yet-created destination has no revision.
    return {
        "schema_version": MATERIAL_SCHEMA,
        "code_hash": fingerprint["code_hash"],
        "configuration_version": fingerprint["configuration_version"],
        "dependency_hash": fingerprint["dependency_hash"],
        "builders": _content_hashes(MATERIAL_BUILDERS),
        "inputs": _content_hashes(MATERIAL_INPUTS),
    }


def material_store() -> Path:
    """Rebuildable test cache location (docs/development/local-runtime.md cache directory)."""
    configured = os.environ.get("PRING_TEST_MATERIALS_ROOT")
    if configured:
        return Path(configured)
    cache = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(cache) / "pring-cycle" / "test-materials"


def _runtime_contents(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def store_isolated_lifecycle_material(paths: RuntimePaths, built: dict[str, Any]) -> Path:
    """Keep a verified build as immutable material unless an identical one is stored."""
    import shutil

    identity = material_identity(paths)
    key = hashlib.sha256(encode(identity)).hexdigest()
    stored = material_store() / key
    if (stored / "material.json").is_file():
        return stored
    models = ModelRepository(paths.database)
    candidate = built["candidate_model_version_id"]
    staging = material_store() / f"{key}.staging-{os.getpid()}"
    shutil.rmtree(staging, ignore_errors=True)
    assert paths.override_root is not None
    shutil.copytree(paths.override_root, staging / "runtime")
    from pring_cycle.runtime_fingerprint import execution_fingerprint

    manifest = models.manifest(candidate)
    contents = _runtime_contents(staging / "runtime")
    (staging / "runtime-contents.json").write_text(json.dumps(contents, indent=2, sort_keys=True))
    document = {
        **identity,
        **built,
        "certification_request_hash": manifest["certification_request_hash"],
        "comparison_baseline": (
            "model-v0001 acceptance recorded and activated directly, as in the existing "
            "isolated replay tests; only the candidate uses the public lifecycle commands"
        ),
        "database_revision": execution_fingerprint(paths)["database_revision"],
        "manifest_hash": models.get(candidate).manifest_hash,
        "material_key": key,
        "metric_catalog_version": manifest["metric_catalog_version"],
        "purpose": "synthetic isolated test material; no actual source is certified",
        "runtime_contents_sha256": hashlib.sha256(encode(contents)).hexdigest(),
    }
    (staging / "material.json").write_text(json.dumps(document, indent=2, sort_keys=True))
    try:
        staging.rename(stored)
    except OSError:
        # Another process stored an identical build first.
        shutil.rmtree(staging, ignore_errors=True)
    return stored


def isolated_lifecycle_material(destination: Path) -> tuple[RuntimePaths, dict[str, Any]]:
    """An independent copy of the activated synthetic model for mutable isolated tests.

    A stored build is reused only when its identity matches the current code, dependencies,
    builders and inputs and every stored runtime file still matches its recorded hash; each
    caller receives its own full copy, never a shared runtime. This is a rebuildable test
    cache, not a backup of operational runtime data (see docs/development/local-runtime.md).
    """
    import shutil

    identity = material_identity(RuntimePaths.discover(destination))
    key = hashlib.sha256(encode(identity)).hexdigest()
    stored = material_store() / key
    if not (stored / "material.json").is_file():
        build = material_store() / f"{key}.build-{os.getpid()}" / "runtime"
        shutil.rmtree(build.parent, ignore_errors=True)
        build_paths = RuntimePaths.discover(build)
        store_isolated_lifecycle_material(
            build_paths, build_complete_isolated_lifecycle(build_paths)
        )
        shutil.rmtree(build.parent, ignore_errors=True)
    document = json.loads((stored / "material.json").read_text())
    if hashlib.sha256(encode({name: document.get(name) for name in identity})).hexdigest() != key:
        raise AssertionError("isolated_lifecycle_material_identity_mismatch")
    # A stored material is reused only if every runtime file still matches its build.
    contents = _runtime_contents(stored / "runtime")
    recorded = json.loads((stored / "runtime-contents.json").read_text())
    if (
        contents != recorded
        or hashlib.sha256(encode(recorded)).hexdigest() != document["runtime_contents_sha256"]
    ):
        raise AssertionError("isolated_lifecycle_material_contents_changed")
    shutil.copytree(stored / "runtime", destination, dirs_exist_ok=True)
    return RuntimePaths.discover(destination), document


def test_complete_isolated_candidate_is_calibrated_replayed_and_activated(tmp_path: Path) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    built = build_complete_isolated_lifecycle(paths)

    assert (
        ModelRepository(paths.database).active().model_version_id
        == (built["candidate_model_version_id"])
    )
    assert built["replay_trading_days"] == 120
    # Activation alone publishes nothing.
    with pytest.raises(LookupError, match="current_projection_unavailable"):
        ProjectionSetRepository(paths.database).current()
    store_isolated_lifecycle_material(paths, built)


def test_isolated_material_copy_keeps_the_activated_candidate_and_its_evidence(
    tmp_path: Path,
) -> None:
    from pring_cycle.runtime_fingerprint import execution_fingerprint

    first, material = isolated_lifecycle_material(tmp_path / "first")
    second, _ = isolated_lifecycle_material(tmp_path / "second")
    candidate = material["candidate_model_version_id"]
    for paths in (first, second):
        models = ModelRepository(paths.database)
        assert models.active().model_version_id == candidate
        assert models.get(candidate).manifest_hash == material["manifest_hash"]
        assert {
            key: value
            for key, value in execution_fingerprint(paths).items()
            if key in {"code_hash", "database_revision", "dependency_hash"}
        } == {key: material[key] for key in ("code_hash", "database_revision", "dependency_hash")}
    # Copies are independent: damaging one runtime's original leaves the other intact.
    receipt = next(
        r for r in AcquisitionRepository(first.database, first.artifacts).history() if r.raw_hash
    )
    assert receipt.raw_hash is not None
    (first.artifacts / receipt.raw_hash[:2] / receipt.raw_hash).write_bytes(b"damaged copy")
    assert AcquisitionRepository(second.database, second.artifacts).read_content(
        receipt.acquisition_id, "raw"
    )
    # A changed stored material is refused rather than silently copied.
    stored_original = (
        material_store()
        / material["material_key"]
        / "runtime/data/artifacts/sha256"
        / receipt.raw_hash[:2]
        / receipt.raw_hash
    )
    original = stored_original.read_bytes()
    stored_original.write_bytes(b"changed stored material")
    try:
        with pytest.raises(AssertionError, match="isolated_lifecycle_material_contents_changed"):
            isolated_lifecycle_material(tmp_path / "third")
    finally:
        stored_original.write_bytes(original)
    third, _ = isolated_lifecycle_material(tmp_path / "fourth")
    assert ModelRepository(third.database).active().model_version_id == candidate
