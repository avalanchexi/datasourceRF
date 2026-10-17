"""The data chain's Sankey and request table as a reader sees them (ticket 09).

Requests flow source → phase → result. Nodes read as a Chinese name and a request count,
links are coloured by what the request came to, and sources with a single request are
folded into one "其他 N 个来源" node so the chart does not splinter.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from dash import dcc, html

from pring_cycle import cockpit_operations
from pring_cycle.cockpit_operations import data_chain
from pring_cycle.runs import RunRecord, RunRepository
from tests.web.test_overseas_cards import _find, _words


def _run(tmp_path: Path) -> RunRecord:
    runs = RunRepository.create(tmp_path / "runs.sqlite3")
    return runs.submit_manual_full(
        target_business_date="2026-10-14",
        client_request_id="sankey",
        model_version_id="model-v0015",
        system_as_of=datetime(2026, 10, 14, 13, tzinfo=UTC),
    )


def _request(index: int, channel: str, phase: str, result: str) -> dict[str, Any]:
    return {
        "request_id": f"request-{index}",
        "channel": channel,
        "phase": phase,
        "result": result,
        "classification": None,
        "metric_ids": ["CN_EQ_CSI300"],
        "gap_ids": [],
        "source_record_count": 1,
        "claim_count": 1,
    }


def _sankey(tmp_path: Path, flows: list[tuple[str, str, str, int]]) -> dict[str, Any]:
    """The Sankey trace for requests given as (channel, phase, result, how many)."""
    requests = [
        _request(index, channel, phase, result)
        for index, (channel, phase, result) in enumerate(
            (channel, phase, result)
            for channel, phase, result, count in flows
            for _ in range(count)
        )
    ]
    run = _run(tmp_path)
    page = data_chain([run], run, {"gaps": [], "requests": requests}, {"run": run.run_id}, None)
    (graph,) = _find(page, lambda item: isinstance(item, dcc.Graph))
    trace: dict[str, Any]
    (trace,) = cast(Any, graph).figure["data"]
    assert trace["type"] == "sankey"
    return trace


def test_nodes_read_as_a_chinese_name_and_a_request_count_without_prefixes(
    tmp_path: Path,
) -> None:
    trace = _sankey(
        tmp_path,
        [
            ("tushare", "direct_context_refresh", "accepted", 3),
            ("official", "retrieval", "candidate_source", 2),
        ],
    )

    assert trace["node"]["label"] == [
        "TuShare · 3",
        "官方发布 · 2",
        "背景指标取数 · 3",
        "补缺 · 2",
        "已接纳 · 3",
        "候选来源 · 2",
    ]


def test_sources_with_a_single_request_fold_into_one_other_node(tmp_path: Path) -> None:
    trace = _sankey(
        tmp_path,
        [
            ("tushare", "direct_context_refresh", "accepted", 3),
            ("国家统计局", "retrieval", "verified", 1),
            ("European Central Bank", "retrieval", "verified", 1),
            ("Cboe Global Markets", "direct_context_refresh", "accepted", 1),
        ],
    )
    labels = trace["node"]["label"]
    links = trace["link"]

    assert labels[:2] == ["TuShare · 3", "其他 3 个来源 · 3"]
    assert not any("国家统计局" in label or "欧洲央行" in label for label in labels)
    other = labels.index("其他 3 个来源 · 3")
    assert sorted(
        (labels[target], value)
        for source, target, value in zip(
            links["source"], links["target"], links["value"], strict=True
        )
        if source == other
    ) == [("背景指标取数 · 4", 1), ("补缺 · 2", 2)]


def test_a_lone_small_source_keeps_its_own_name(tmp_path: Path) -> None:
    trace = _sankey(
        tmp_path,
        [
            ("tushare", "direct_context_refresh", "accepted", 3),
            ("European Central Bank", "retrieval", "verified", 1),
        ],
    )

    assert trace["node"]["label"][:2] == ["TuShare · 3", "欧洲央行 · 1"]


def test_links_record_the_colour_family_of_what_the_request_came_to(tmp_path: Path) -> None:
    results = {
        "accepted": "success",
        "verified": "success",
        "validated": "success",
        "candidate_source": "candidate",
        "not_found": "neutral",
        "started": "neutral",
        "reserved": "neutral",
        "unknown_completion": "neutral",
        "completed": "neutral",
        "failed": "failure",
        "interrupted": "failure",
        "timeout": "failure",
        "error": "failure",
        "rejected": "failure",
        "brand_new_state": "neutral",
    }
    trace = _sankey(tmp_path, [("tushare", "retrieval", result, 2) for result in results])
    labels = trace["node"]["label"]
    links = trace["link"]
    tones = trace["meta"]["link_tones"]
    into_results = {
        labels[target]: tone
        for source, target, tone in zip(links["source"], links["target"], tones, strict=True)
        if labels[source] == "补缺 · 30"
    }
    from_source = {
        tone
        for source, tone in zip(links["source"], tones, strict=True)
        if labels[source] == "TuShare · 30"
    }

    assert into_results == {
        "已接纳 · 2": "success",
        "已验证 · 2": "success",
        "校验通过 · 2": "success",
        "候选来源 · 2": "candidate",
        "未找到 · 2": "neutral",
        "已开始 · 2": "neutral",
        "已预留 · 2": "neutral",
        "完成情况未知 · 2": "neutral",
        "已完成 · 2": "neutral",
        "失败 · 2": "failure",
        "已中断 · 2": "failure",
        "超时 · 2": "failure",
        "出错 · 2": "failure",
        "已拒绝 · 2": "failure",
        "brand_new_state · 2": "neutral",
    }
    assert from_source == {"success", "candidate", "neutral", "failure"}
    assert trace["meta"]["node_columns"] == ["source"] + ["phase"] + ["result"] * 15


def test_the_figure_starts_in_one_neutral_colour_until_the_theme_paints_it(
    tmp_path: Path,
) -> None:
    # The colour of each family lives once, in the theme's --flow-* variables.
    trace = _sankey(
        tmp_path,
        [("tushare", "retrieval", "accepted", 2), ("official", "retrieval", "failed", 2)],
    )

    assert len({*trace["link"]["color"], *trace["node"]["color"]}) == 1


def test_every_colour_family_the_figure_records_has_a_theme_variable_in_both_themes() -> None:
    stylesheet = (Path(cockpit_operations.__file__).parent / "assets" / "report.css").read_text(
        encoding="utf-8"
    )
    families = {tone for _name, tone in cockpit_operations.FLOW_RESULTS.values()}
    families |= {"neutral", "source", "phase", "result"}
    rules = re.findall(r"([^{}]*)\{([^{}]*)\}", stylesheet)
    blocks = [
        " ".join(body for selectors, body in rules if theme in selectors)
        for theme in (":root:not([data-theme])", ':root[data-theme="dark"]')
    ]

    for block in blocks:
        assert all(f"--flow-{family}:" in block for family in families)


def test_hovering_a_link_or_node_shows_its_requests_and_share(tmp_path: Path) -> None:
    trace = _sankey(
        tmp_path,
        [
            ("tushare", "direct_context_refresh", "accepted", 5),
            ("official", "retrieval", "candidate_source", 3),
            ("国家统计局", "retrieval", "verified", 1),
            ("European Central Bank", "retrieval", "failed", 1),
        ],
    )
    labels = trace["node"]["label"]
    node_hover = dict(zip(labels, trace["node"]["customdata"], strict=True))
    links = trace["link"]
    link_hover = {
        (labels[source], labels[target]): text
        for source, target, text in zip(
            links["source"], links["target"], links["customdata"], strict=True
        )
    }

    assert "%{customdata}" in trace["node"]["hovertemplate"]
    assert "%{customdata}" in links["hovertemplate"]
    assert node_hover["TuShare · 5"] == "5 次请求 · 占比 50.0%"
    assert node_hover["其他 2 个来源 · 2"] == "国家统计局、欧洲央行 · 2 次请求 · 占比 20.0%"
    assert link_hover["官方发布 · 3", "补缺 · 5"] == "候选来源 · 3 次请求 · 占比 30.0%"
    assert link_hover["补缺 · 5", "失败 · 1"] == "失败 · 1 次请求 · 占比 10.0%"


def test_the_request_table_names_results_the_way_the_sankey_does(tmp_path: Path) -> None:
    run = _run(tmp_path)
    requests = [
        _request(1, "official", "retrieval", "candidate_source"),
        _request(2, "tavily", "retrieval", "timeout"),
        _request(3, "tavily", "retrieval", "brand_new_state"),
    ]
    page = data_chain([run], run, {"gaps": [], "requests": requests}, {"run": run.run_id}, None)
    (request_table,) = [
        found
        for found in _find(page, lambda item: isinstance(item, html.Table))
        if _words(found).startswith("请求 来源 / 环节")
    ]
    rows = _find(request_table, lambda item: isinstance(item, html.Tr))[1:]
    cells = [_find(row, lambda item: isinstance(item, html.Td)) for row in rows]

    assert [_words(row[2]) for row in cells] == [
        "候选来源 · —",
        "超时 · —",
        "brand_new_state · —",
    ]
    assert [_words(row[3]) for row in cells] == ["沪深 300"] * 3
