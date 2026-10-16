"""The data chain's Sankey and request table as a reader sees them (ticket 09).

Requests flow source → phase → result. Nodes read as a Chinese name and a request count,
links are coloured by what the request came to, and sources with a single request are
folded into one "其他（N）" node so the chart does not splinter.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from dash import dcc, html

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

    assert labels[:2] == ["TuShare · 3", "其他（3） · 3"]
    assert not any("国家统计局" in label or "欧洲央行" in label for label in labels)
    other = labels.index("其他（3） · 3")
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


def _rgb(colour: str) -> tuple[int, int, int]:
    if colour.startswith("#"):
        return int(colour[1:3], 16), int(colour[3:5], 16), int(colour[5:7], 16)
    red, green, blue = colour[colour.index("(") + 1 : colour.index(")")].split(",")[:3]
    return int(red), int(green), int(blue)


def _family(colour: str) -> str:
    red, green, blue = _rgb(colour)
    if max(red, green, blue) - min(red, green, blue) < 40:
        return "grey"
    if green > red and green > blue:
        return "green"
    if red > green > blue and green > red * 0.5:
        return "amber"
    return "red" if red > green and red > blue else "other"


def test_links_take_the_colour_of_what_the_request_came_to(tmp_path: Path) -> None:
    results = {
        "accepted": "green",
        "verified": "green",
        "validated": "green",
        "candidate_source": "amber",
        "not_found": "grey",
        "started": "grey",
        "reserved": "grey",
        "unknown_completion": "grey",
        "completed": "grey",
        "failed": "red",
        "interrupted": "red",
        "timeout": "red",
        "error": "red",
        "rejected": "red",
        "brand_new_state": "grey",
    }
    trace = _sankey(tmp_path, [("tushare", "retrieval", result, 2) for result in results])
    labels = trace["node"]["label"]
    links = trace["link"]
    into_results = {
        labels[target]: _family(colour)
        for source, target, colour in zip(
            links["source"], links["target"], links["color"], strict=True
        )
        if labels[source] == "补缺 · 30"
    }
    from_source = {
        _family(colour)
        for source, colour in zip(links["source"], links["color"], strict=True)
        if labels[source] == "TuShare · 30"
    }

    assert into_results == {
        "已接纳 · 2": "green",
        "已验证 · 2": "green",
        "校验通过 · 2": "green",
        "候选来源 · 2": "amber",
        "未找到 · 2": "grey",
        "已开始 · 2": "grey",
        "已预留 · 2": "grey",
        "完成情况未知 · 2": "grey",
        "已完成 · 2": "grey",
        "失败 · 2": "red",
        "已中断 · 2": "red",
        "超时 · 2": "red",
        "出错 · 2": "red",
        "已拒绝 · 2": "red",
        "brand_new_state · 2": "grey",
    }
    assert from_source == {"green", "amber", "grey", "red"}


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
    assert node_hover["其他（2） · 2"] == "国家统计局、欧洲央行 · 2 次请求 · 占比 20.0%"
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
