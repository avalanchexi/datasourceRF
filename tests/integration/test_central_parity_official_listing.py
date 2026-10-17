"""Worker gaps 01: the day's central parity looked up on the PBC's announcement column.

The catalog registers the column (``…/125925/index.html``), not an announcement. The run of
10-15 read the column as if it were the day's announcement and failed
(official_context_usdcny_quote_missing), though it listed 10-15's. The column is a listing
now: the day's announcement is followed from it and read.

The column page is the run's own original (tests/fixtures/central_parity). The 10-15 copy
kept no announcement of that day, the run never having opened it: its body below is written
here as 4-30's is laid out (its stamp after the time in the column's path), with the value
CLS reported for that day. The one
announcement original kept, 4-30's, is read as published.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest

from pring_cycle.catalog import METRIC_CATALOG_VERSION
from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.official_context import (
    FetchedOfficialContextDocument,
    refresh_official_context_document,
)
from pring_cycle.runtime import RuntimePaths, initialize_runtime

FIXTURES = Path(__file__).parents[1] / "fixtures" / "central_parity"
COLUMN = "https://www.pbc.gov.cn/zhengcehuobisi/125207/125217/125925/"
ANNOUNCEMENT_1015 = COLUMN + "2026101509014017867/index.html"
ANNOUNCEMENT_1015_BODY = (
    "<html><head><title>2026年10月15日中国外汇交易中心受权公布人民币汇率中间价公告</title>"
    "</head><body><h2>2026年10月15日中国外汇交易中心受权公布人民币汇率中间价公告</h2>"
    "<p>文章来源：</p><p>2026-10-15 09:01:40</p>"
    "<p>中国人民银行授权中国外汇交易中心公布，2026年10月15日银行间外汇市场人民币汇率"
    "中间价为1美元对人民币6.7253元，1欧元对人民币7.8875元。</p></body></html>"
).encode()


def parity(paths: RuntimePaths, day: str) -> list[float]:
    return [
        point.selected_value
        for point in EvidenceRepository(paths.database).metric_series(
            "CN_USDCNY_CENTRAL_PARITY",
            mode=AsOfMode.SYSTEM,
            as_of=datetime.now(UTC),
            definition_version=METRIC_CATALOG_VERSION,
        )
        if point.period_end == day
    ]


def serve(
    documents: dict[str, bytes], requested: list[str]
) -> Callable[[str], FetchedOfficialContextDocument]:
    def fetch(url: str) -> FetchedOfficialContextDocument:
        requested.append(url)
        if url not in documents:
            raise OSError("fixture_official_page_unavailable")
        return FetchedOfficialContextDocument(documents[url], "text/html", url, 200)

    return fetch


@pytest.mark.usefixtures("runtime_clock")
def test_the_day_s_announcement_is_followed_from_the_column(tmp_path: Path) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    requested: list[str] = []
    documents = {
        COLUMN + "index.html": (FIXTURES / "pbc_125925_index_20261015.html").read_bytes(),
        ANNOUNCEMENT_1015: ANNOUNCEMENT_1015_BODY,
    }

    refresh_official_context_document(
        paths,
        family="pbc_usdcny_central_parity",
        source_url=COLUMN + "index.html",
        expected_period="2026-10-15",
        fetched_at=datetime.now(UTC),
        fetcher=serve(documents, requested),
    )

    assert requested == [COLUMN + "index.html", ANNOUNCEMENT_1015]
    assert parity(paths, "2026-10-15") == [6.7253]


@pytest.mark.usefixtures("runtime_clock")
def test_the_kept_announcement_original_gives_its_day_s_parity(tmp_path: Path) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    url = COLUMN + "2026042916250715970/index.html"

    refresh_official_context_document(
        paths,
        family="pbc_usdcny_central_parity",
        source_url=url,
        expected_period="2026-04-30",
        fetched_at=datetime.now(UTC),
        fetcher=serve({url: (FIXTURES / "pbc_125925_20260430.html").read_bytes()}, []),
    )

    assert parity(paths, "2026-04-30") == [6.8628]
