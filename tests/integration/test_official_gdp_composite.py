"""GDP read from the NBS monthly indicators table as well as its accounting release.

On 2026-10-19 the bureau first stated the third quarter in "2026年9月份及前三季度主要指标
数据": its rows are named "一、国内生产总值（亿元）", its columns run quarter level, quarter
growth, year-to-date level, year-to-date growth, and its quarter cells carry "（三季度）"
(go-live leftovers 05). The fixture is that original, minimized (fixtures README).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest

import pring_cycle.tushare_context as tushare_context
from pring_cycle import credit_impulse
from pring_cycle.acquisition import own_acquisitions
from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.models import ModelRepository
from pring_cycle.official_context import (
    FetchedOfficialContextDocument,
    official_member,
    parse_official_context_document,
    refresh_official_context_document,
)
from pring_cycle.worker import refresh_context_sources
from tests.conftest import install_runtime_clock
from tests.integration.test_worker_reviewed_context import (
    _GDP_YTD,
    context_http,
    credit_coverage,
    reviewed_run,
)

FIXTURES = Path(__file__).parents[1] / "fixtures/official_period_fallback"
COMPOSITE = FIXTURES / "nbs_gdp_composite_2026q3.html"
COMPOSITE_URL = "https://www.stats.gov.cn/sj/zxfbhjd/202610/t20261019_1965618.html"
FETCHED = datetime(2026, 10, 19, 11, 11, 30, tzinfo=UTC)


def parsed_gdp(content: bytes, period: str, url: str) -> dict[tuple[str, str], float]:
    release = parse_official_context_document(
        content, family="nbs_gdp", source_url=url, expected_period=period, fetched_at=FETCHED
    )
    return {
        (scalar.dimensions["aggregate"], scalar.dimensions["measure"]): scalar.value
        for scalar in release.scalars
    }


def test_the_composite_table_gives_the_four_gdp_rows_by_its_own_columns() -> None:
    # The quarter's real growth is the "（三季度）" column, never the year to date's
    # (4.6/3.7/3.8/5.2, also in the release's text).
    assert parsed_gdp(COMPOSITE.read_bytes(), "2026-Q3", COMPOSITE_URL) == {
        ("total", "nominal_ytd_level"): 1071071.0,
        ("total", "real_quarter_yoy"): 4.5,
        ("primary", "nominal_ytd_level"): 58994.0,
        ("primary", "real_quarter_yoy"): 3.6,
        ("secondary", "nominal_ytd_level"): 383822.0,
        ("secondary", "real_quarter_yoy"): 3.4,
        ("tertiary", "nominal_ytd_level"): 628255.0,
        ("tertiary", "real_quarter_yoy"): 5.2,
    }


def test_the_accounting_release_table_still_parses() -> None:
    content = (FIXTURES / "nbs_gdp_q3.html").read_bytes()
    url = "https://www.stats.gov.cn/sj/zxfb/202510/t20251021_1961646.html"
    values = parsed_gdp(content, "2025-Q3", url)
    assert values[("total", "nominal_ytd_level")] == 1015036.0
    assert values[("total", "real_quarter_yoy")] == 4.8


@pytest.mark.parametrize(
    ("old", "new"),
    [
        # The quarter cells name another quarter.
        ("（三季度）", "（二季度）"),
        # The columns are no longer quarter level, quarter growth, then the year's.
        (
            "<p>绝对量</p></td>\n<td>\n<p>同比增长<br />（%）</p></td>\n<td>\n<p>绝对量</p>",
            "<p>绝对量</p></td>\n<td>\n<p>绝对量</p></td>\n<td>\n<p>同比增长<br />（%）</p>",
        ),
        # The year-to-date column is another period's.
        ("<p>1—9月</p>", "<p>1—6月</p>"),
    ],
)
def test_a_composite_table_of_another_shape_or_period_is_refused(old: str, new: str) -> None:
    document = COMPOSITE.read_text()
    assert old in document
    with pytest.raises(ValueError, match="official_context_table_schema_mismatch"):
        parsed_gdp(document.replace(old, new).encode(), "2026-Q3", COMPOSITE_URL)


@pytest.fixture
def runtime_clock(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> Any:
    return install_runtime_clock(monkeypatch, request, datetime(2026, 10, 20, 1, tzinfo=UTC))


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize(
    ("third_quarter", "official", "status"),
    [
        # Q3 came alone, so no delivery states it with Q2; nothing shows one vintage.
        (1071071.0, False, "incomparable_gdp_vintages"),
        # The composite table states 375,367 for the quarter: 1,071,071 - 695,704.
        (1071071.0, True, "available"),
        # A year to date the release does not state proves nothing of its vintage.
        (1071000.0, True, "incomparable_gdp_vintages"),
    ],
)
def test_the_credit_impulse_reconciles_a_quarter_with_the_composite_table(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    third_quarter: float,
    official: bool,
    status: str,
) -> None:
    """A quarter another delivery stated is checked against the bureau's own quarter.

    On 2026-10-19 Q3 came from the news, Q2 from TuShare's series, and the official page
    was refused, so the impulse stayed ``incomparable_gdp_vintages`` (go-live leftovers
    05). TuShare fetching Q3 alone stands in for the news: neither is an official release
    nor states Q2.
    """
    paths, run, version = reviewed_run(
        tmp_path,
        capsys,
        target="2026-10-19",
        extra_markers={"CN_GDP": "tushare:cn_gdp:official-sampled-v0001"},
    )
    months = [f"{year}{month:02d}" for year in (2024, 2025, 2026) for month in range(1, 13)]
    # What the run's coverage asks for on 2026-10-19: 2024-09 to 2026-09, 2024Q3 on.
    months = months[months.index("202409") : months.index("202609") + 1]

    def gdp_row(quarter: str, level: float) -> dict[str, Any]:
        return {
            "quarter": quarter,
            "gdp": level,
            "gdp_yoy": 5.0,
            "pi": level * 0.07,
            "pi_yoy": 3.5,
            "si": level * 0.36,
            "si_yoy": 5.0,
            "ti": level * 0.57,
            "ti_yoy": 5.0,
        }

    rows = {
        "sf_month": [
            {"month": month, "inc_cumval": 30000.0 * int(month[4:]), "stk_endval": 400.0 + i}
            for i, month in enumerate(months)
        ],
        "cn_gdp": [gdp_row(quarter, level) for quarter, level in _GDP_YTD.items()][1:],
    }

    class Opener:
        def open(self, request: Any, *, timeout: float) -> BytesIO:
            payload = json.loads(request.data)
            fields = payload["fields"].split(",")
            items = [[row[field] for field in fields] for row in rows.get(payload["api_name"], [])]
            if not items:
                raise OSError("fixture source unavailable")
            return BytesIO(
                json.dumps({"code": 0, "data": {"fields": fields, "items": items}}).encode()
            )

    context_http(monkeypatch, {})
    monkeypatch.setattr("pring_cycle.tushare_context.build_opener", lambda *args: Opener())
    with own_acquisitions(paths.database, run.run_id, "direct_context_refresh"):
        refresh_context_sources(
            paths,
            run.target_business_date,
            definition_version=version,
            covered=credit_coverage(paths, run),
        )
    rows["cn_gdp"] = [gdp_row("2026Q3", third_quarter)]
    adapter = tushare_context.TushareContextAdapter("fixture-only")
    adapter.acquire_scalars(
        paths,
        lambda: adapter.gdp(start_quarter="2026Q3", end_quarter="2026Q3"),
        definition_version=version,
    )
    if official:
        # As the Worker fetches it: the levels another source delivered are held back.
        refresh_official_context_document(
            paths,
            family="nbs_gdp",
            source_url=COMPOSITE_URL,
            expected_period="2026-Q3",
            fetched_at=datetime.now(UTC),
            fetcher=lambda url: FetchedOfficialContextDocument(
                COMPOSITE.read_bytes(), "text/html", url, 200
            ),
            definition_version=version,
            held_members=frozenset(
                official_member("CN_GDP", {"aggregate": aggregate, "measure": "nominal_ytd_level"})
                for aggregate in ("total", "primary", "secondary", "tertiary")
            ),
        )

    manifest = ModelRepository(paths.database).manifest(run.model_version_id)
    derived = credit_impulse.derive(
        EvidenceRepository(paths.database),
        manifest["derived_formula_versions"]["credit_impulse"],
        as_of=datetime.now(UTC),
        as_of_mode=AsOfMode.SYSTEM,
        definition_version=version,
    )
    assert derived.status == status, derived
    if status == "available":
        assert derived.failures == () and derived.latest_gdp_period == "2026-09-30"
    else:
        assert [(f.reason, f.periods) for f in derived.failures] == [
            ("incomparable_gdp_vintages", ("2026-Q3",))
        ]
