"""The AI report leads with the macro judgement (ADR-0043, macro stage ticket 09): it says
why the five dimensions point to the judged stage and how sure the judgement is, then the
turn signals, then the price verification. The judgement's stage and confidence are the
deterministic rules' (ADR-0003): the report explains them and may not rewrite them.

Each case reads a projection its own run published with the macro rules: the 10-15 macro
day over a noncanonical bond bull · stock bear · commodity bull (stage V, explicit), the
tie of stages III, V and VI broken toward III (tendency), and two dimensions known over the
same noncanonical cores (stage III, weak).
"""

from __future__ import annotations

import copy
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.dashboard import dashboard_page
from pring_cycle.projections import ProjectionSet
from pring_cycle.reports import (
    AdapterResponse,
    CliReportAdapter,
    ReportInput,
    ReportRepository,
    ReportService,
    report_input_from_projection,
)
from tests.integration.test_confirmation_publish import publish
from tests.integration.test_macro_fallback import tied, weak_off_typical
from tests.integration.test_macro_hysteresis import SF_REVISED, last, macro_day, revise_credit
from tests.integration.test_macro_judgement import MODEL, publish_from
from tests.integration.test_macro_signals import with_peers
from tests.integration.test_price_verification import verified
from tests.reports.test_cli_protocol import install_cli
from tests.reports.test_report_boundary import FakeAdapter
from tests.web.test_dashboard_contract import _text


@pytest.fixture(scope="module")
def explicit(tmp_path_factory: pytest.TempPathFactory) -> ProjectionSet:
    """Stage V explicit (4 of 5) on a noncanonical day, the bond off what V expects."""
    return verified(tmp_path_factory.mktemp("explicit"), "stock")


@pytest.fixture(scope="module")
def tendency(tmp_path_factory: pytest.TempPathFactory) -> ProjectionSet:
    """Stage III a tendency, tied with V and VI, one step on from the price stage II."""
    return tied(tmp_path_factory.mktemp("tendency"), "bull", "bull", "bear")


@pytest.fixture(scope="module")
def signalled(tmp_path_factory: pytest.TempPathFactory) -> ProjectionSet:
    """Stage V explicit on rising cores, its PMI diverging and its bond peers turning bear:
    a divergence and two same-source price signals, each a step or two back."""
    return publish(with_peers(tmp_path_factory.mktemp("signalled")), MODEL)


@pytest.fixture(scope="module")
def weak(tmp_path_factory: pytest.TempPathFactory) -> ProjectionSet:
    """Stage III weak: two dimensions known on a noncanonical day, no price stage."""
    return weak_off_typical(tmp_path_factory.mktemp("weak"))


def keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {key for item in value.values() for key in keys(item)}
    if isinstance(value, list):
        return {key for item in value for key in keys(item)}
    return set()


def test_the_report_input_leads_with_the_macro_judgement(explicit: ProjectionSet) -> None:
    source = report_input_from_projection(explicit)

    # The judged stage and its confidence are conclusions the AI must echo.
    assert source.conclusions["macro_stage"] == "stage_v"
    assert source.conclusions["macro_confidence"] == "explicit"
    assert (source.schema_version, source.prompt_version) == (
        "report-schema-v0006",
        "report-prompt-v0011",
    )
    macro = source.results["macro_judgement"]
    assert macro["title"] == "宏观判断：第五阶段（明确，5 维中 4 维吻合）· 无上一确认阶段"
    assert [item["dimension"] for item in macro["dimensions"]] == [
        "policy",
        "credit",
        "overheat",
        "price",
        "inventory",
    ]
    assert macro["dimensions"][0]["line"].startswith("政策：中性 · 吻合")
    verification = macro["price_verification"]
    assert (verification["verdict"], verification["deviations"]) == ("deviates", ["bond"])
    assert verification["line"].endswith("债券偏离")
    # The noncanonical day is read as the prices off the judgement, not by the old reading.
    assert "noncanonical_basis" not in source.results
    # Only what the report needs: no evidence or observation identifiers.
    assert not {key for key in keys(macro) if key.endswith(("_id", "_ids"))}
    assert source.display_names["stages"]["stage_v"] == "第五阶段"


def test_the_cli_is_asked_for_the_dimensions_then_the_signals_then_the_verification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, explicit: ProjectionSet
) -> None:
    source = report_input_from_projection(explicit)
    install_cli(tmp_path, monkeypatch, record_prompt=True)
    reports = ReportRepository.create(tmp_path / "reports.sqlite3")

    result = ReportService(reports, (CliReportAdapter("codex_cli"),)).generate(source)

    assert (result.status, result.adapter) == ("completed", "codex_cli")
    prompt = json.loads((tmp_path / "cli" / "codex.prompt.json").read_text())
    assert prompt["execution_contract"]["prompt_version"] == "report-prompt-v0011"
    # The old noncanonical reading's fixed sentences give way to the judgement.
    assert "noncanonical_reading_contract" not in prompt
    contract = prompt["macro_reading_contract"]
    assert contract["sections_in_order"] == ["宏观判断与五维依据", "转折信号", "价格验证与偏离"]
    for told in ("倾向", "弱", "价格偏离宏观判断", "不得改写"):
        assert told in contract["instruction"]
    assert prompt["report_input"]["conclusions"]["macro_stage"] == "stage_v"


def written(source: ReportInput, text: str, **conclusions: Any) -> dict[str, Any]:
    """The report the AI would return: the input's identity and conclusions, ``text``."""
    return {
        "bundle_id": source.bundle_id,
        "current_stage": source.current_stage,
        "report_cutoff": source.report_cutoff.isoformat(),
        "core_states": dict(source.core_states),
        "conclusions": {**source.conclusions, **conclusions},
        "sections": [{"title": "宏观判断与五维依据", "explanation": text}],
        "proxy_used": False,
    }


@pytest.mark.parametrize(
    ("judgement", "text", "change", "check"),
    [
        # Told as the rules judged it, with the stages tied and the price stage apart.
        (
            "tendency",
            "宏观判断为第三阶段（倾向），与第五阶段、第六阶段并列，各 3 维；价格阶段为第二阶段。",
            {},
            None,
        ),
        ("tendency", "当前处于第三阶段，属倾向判断，取离上次确认第二阶段最近者。", {}, None),
        ("weak", "宏观判断为第三阶段（弱），已知 2 维；股票走弱，价格偏离宏观判断。", {}, None),
        ("explicit", "宏观判断为第五阶段（明确，5 维中 4 维吻合），债券偏离。", {}, None),
        # The conclusions echoed otherwise.
        ("tendency", "宏观判断为第三阶段（倾向）。", {"macro_stage": "stage_v"}, "conclusions"),
        (
            "tendency",
            "宏观判断为第三阶段（倾向）。",
            {"macro_confidence": "explicit"},
            "conclusions",
        ),
        # Another stage said as the judgement, or as the price stage.
        ("tendency", "宏观判断为第五阶段（倾向）。", {}, "macro_stated_stage"),
        ("tendency", "当前处于第二阶段，倾向判断。", {}, "macro_stated_stage"),
        (
            "tendency",
            "宏观判断为第三阶段，倾向判断；价格阶段为第三阶段。",
            {},
            "price_stated_stage",
        ),
        ("weak", "宏观判断为第三阶段（弱）；价格阶段为第三阶段。", {}, "price_stated_stage"),
        # A tendency or a weak judgement said to be explicit, or certain.
        ("tendency", "宏观判断为第三阶段（明确）。", {}, "macro_stated_confidence"),
        ("tendency", "宏观判断明确为第三阶段，属倾向判断。", {}, "macro_stated_confidence"),
        ("weak", "宏观判断为第三阶段（倾向）。", {}, "macro_stated_confidence"),
        ("weak", "宏观判断为第三阶段（弱），已经确定。", {}, "macro_stated_confidence"),
        # An explicit judgement said to lean, there or elsewhere.
        ("explicit", "宏观判断为第五阶段（倾向）。", {}, "macro_stated_confidence"),
        ("explicit", "宏观判断为第五阶段（明确）；目前倾向第六阶段。", {}, "macro_stated_stage"),
        # A tendency or a weak judgement never told as such.
        ("tendency", "宏观判断为第三阶段，五维指向清楚。", {}, "macro_confidence_unstated"),
        ("weak", "宏观判断为第三阶段，股票走弱。", {}, "macro_confidence_unstated"),
        # Another stage however its number is written, or however the judgement is named.
        ("tendency", "宏观判断为第5阶段（倾向）。", {}, "macro_stated_stage"),
        ("tendency", "宏观判断为阶段Ⅴ（倾向）。", {}, "macro_stated_stage"),
        ("tendency", "宏观判断为 Stage 5，倾向判断。", {}, "macro_stated_stage"),
        ("tendency", "主结论已经进入第五阶段，属倾向判断。", {}, "macro_stated_stage"),
        ("tendency", "宏观阶段为第六阶段，属于倾向判断。", {}, "macro_stated_stage"),
        ("tendency", "第五阶段（倾向）的五维依据如下。", {}, "macro_stated_stage"),
        # A tendency told by a word that says something else.
        (
            "tendency",
            "宏观判断为第三阶段；PMI 分化提示转向倾向。",
            {},
            "macro_confidence_unstated",
        ),
        # The scores of the stages tied, told right, or otherwise.
        ("tendency", "宏观判断为第三阶段（倾向），第五阶段、第六阶段同为 3 分。", {}, None),
        ("tendency", "宏观判断为第三阶段（倾向），第五阶段 4 分。", {}, "macro_stated_score"),
        # The day's raw judgement told as another stage.
        (
            "held",
            "宏观判断为第五阶段（明确）；原始判断为第五阶段（倾向）。",
            {},
            "macro_stated_stage",
        ),
    ],
)
def test_a_report_rewriting_the_judged_stage_or_its_confidence_is_rejected(
    request: pytest.FixtureRequest,
    tmp_path: Path,
    judgement: str,
    text: str,
    change: dict[str, Any],
    check: str | None,
) -> None:
    source = report_input_from_projection(request.getfixturevalue(judgement))
    reports = ReportRepository.create(tmp_path / "reports.sqlite3")
    first = FakeAdapter("codex_cli", AdapterResponse.succeeded(written(source, text, **change)))
    second = FakeAdapter("claude_code_cli", AdapterResponse.unavailable("fixture"))

    result = ReportService(reports, (first, second)).generate(source)

    (attempt, *_) = reports.attempts(result.report_snapshot_id)
    assert attempt.process_audit.get("rejection", {}).get("check") == check
    assert result.adapter == ("codex_cli" if check is None else "deterministic")


@pytest.mark.parametrize(
    ("judgement", "told"),
    [
        (
            "explicit",
            [
                "宏观判断：第五阶段（明确，5 维中 4 维吻合）· 无上一确认阶段",
                "非典型组合（债券牛市 · 股票熊市 · 商品牛市） · 第五阶段预期：",
                "价格偏离宏观判断：债券与第五阶段预期相反",
            ],
        ),
        (
            "tendency",
            [
                "宏观判断：第三阶段（倾向，5 维中 3 维吻合）· 相对上次确认第二阶段 前进 1 步",
                "倾向第三阶段（与第五阶段、第六阶段并列，各 3 维）：取离上次确认第二阶段最近者",
                "价格阶段：第二阶段（债券牛市 · 股票牛市 · 商品熊市）",
                "价格偏离宏观判断：商品与第三阶段预期相反",
            ],
        ),
        (
            "weak",
            [
                "宏观判断：第三阶段（弱，2 维中 2 维吻合）· 相对上次确认第三阶段 不变",
                "弱判断：已知 2 维，缺信用、增长、物价，不足 3 维；退回价格组合推断",
                "价格偏离宏观判断：股票与第三阶段预期相反",
            ],
        ),
        (
            "signalled",
            [
                "支持后退：",
                "若 PMI 改投少数方向，增长上行，判第三阶段（倾向",
                "10 年国债价格指数、中债 030 全价",
                "同源，不参与投票",
            ],
        ),
    ],
)
def test_two_cli_failures_publish_the_template_led_by_the_judgement(
    request: pytest.FixtureRequest, tmp_path: Path, judgement: str, told: list[str]
) -> None:
    published: ProjectionSet = request.getfixturevalue(judgement)
    source = report_input_from_projection(published)
    reports = ReportRepository.create(tmp_path / "reports.sqlite3")
    codex = FakeAdapter("codex_cli", AdapterResponse.unavailable("cli_not_authenticated"))
    claude = FakeAdapter("claude_code_cli", AdapterResponse.unavailable("cli_not_installed"))

    result = ReportService(reports, (codex, claude)).generate(source)

    assert (result.status, result.adapter) == ("completed_degraded", "deterministic")
    body = reports.get(result.report_snapshot_id).body
    assert body["explanation_source"] == "deterministic_template"
    sections = body["ai_explanation"]
    # The five dimensions first, then the turn signals, then the price verification.
    assert [item["title"] for item in sections] == [
        "宏观判断与五维依据",
        "转折信号",
        "价格验证与偏离",
    ]
    assert sections[0]["explanation"].startswith(source.results["macro_judgement"]["title"])
    assert "政策：" in sections[0]["explanation"]
    text = "".join(item["explanation"] for item in sections)
    for line in told:
        assert line in text
    assert not any(separator in text for separator in "\r\n\u2028\u2029")
    # The old noncanonical reading gives way to the judgement on the page as well.
    snapshot = reports.get(result.report_snapshot_id)
    home = _text(dashboard_page("/", published, (), (snapshot,)))
    assert "确定性模板" in home and "价格验证与偏离" in home
    assert "非典型组合解读" not in home
    # The reader keeps the structured facts beside the template's reading.
    reader = _text(dashboard_page("/reports", published, (), (snapshot,)))
    assert "价格验证与偏离" in reader and "已验证结果" in reader


@pytest.mark.parametrize("judgement", ["explicit", "tendency", "weak", "signalled"])
def test_the_template_written_back_as_a_reading_is_accepted(
    request: pytest.FixtureRequest, tmp_path: Path, judgement: str
) -> None:
    # The template says only what the rules judged, so the checks never refuse it.
    source = report_input_from_projection(request.getfixturevalue(judgement))
    reading = {**written(source, ""), "sections": source.deterministic_skeleton()["ai_explanation"]}
    reports = ReportRepository.create(tmp_path / "reports.sqlite3")

    result = ReportService(
        reports, (FakeAdapter("codex_cli", AdapterResponse.succeeded(reading)),)
    ).generate(source)

    assert reports.attempts(result.report_snapshot_id)[0].outcome == "succeeded"


@pytest.fixture(scope="module")
def held(tmp_path_factory: pytest.TempPathFactory) -> ProjectionSet:
    """Stage V explicit held by the hysteresis against the day's raw stage III tendency, on
    its second session (decision 45), as the day summary publishes it."""
    paths = macro_day(tmp_path_factory.mktemp("held"))
    revise_credit(paths, SF_REVISED, on=-2)
    return publish_from(paths, last(3))


def test_a_divergence_s_confidence_is_not_the_conclusion_s(
    tmp_path: Path, signalled: ProjectionSet
) -> None:
    # The conclusion stage V a tendency, the PMI's recount stage V explicit: the explicit
    # one is the recount's, never the conclusion's (spec story 37).
    datasets = copy.deepcopy(signalled.datasets)
    block: dict[str, Any] = datasets["cycle_overview"]["macro_judgement"]  # type: ignore[assignment]
    block["conclusion"]["confidence"] = "tendency"
    pmi = next(item for item in block["signals"] if item["id"] == "D-pmi")
    pmi["rejudged"].update(stage="stage_v", confidence="explicit")
    source = report_input_from_projection(replace(signalled, datasets=datasets))
    reports = ReportRepository.create(tmp_path / "reports.sqlite3")
    told = "宏观判断为第五阶段（明确）；PMI 分化提示转向倾向。"
    first = FakeAdapter("codex_cli", AdapterResponse.succeeded(written(source, told)))

    result = ReportService(reports, (first,)).generate(source)

    (attempt,) = reports.attempts(result.report_snapshot_id)
    assert attempt.process_audit["rejection"]["check"] == "macro_stated_confidence"


@pytest.mark.parametrize(
    ("text", "check"),
    [
        ("宏观判断为第五阶段（明确），滞回保持，当日原始判断：第三阶段（倾向）。", None),
        ("宏观判断为第五阶段（明确），当日原始判断：第四阶段（倾向）。", "macro_stated_stage"),
        ("宏观判断为第三阶段（倾向）。", "macro_stated_stage"),
    ],
)
def test_a_judgement_the_hysteresis_holds_is_told_as_held(
    tmp_path: Path, held: ProjectionSet, text: str, check: str | None
) -> None:
    source = report_input_from_projection(held)
    assert source.results["macro_judgement"]["held"] == "滞回保持，当日原始判断：第三阶段（倾向）"
    assert (
        "滞回保持，当日原始判断：第三阶段（倾向）。"
        in (source.deterministic_skeleton()["ai_explanation"][0]["explanation"])
    )
    reports = ReportRepository.create(tmp_path / "reports.sqlite3")
    first = FakeAdapter("codex_cli", AdapterResponse.succeeded(written(source, text)))

    result = ReportService(reports, (first,)).generate(source)

    (attempt,) = reports.attempts(result.report_snapshot_id)
    assert attempt.process_audit.get("rejection", {}).get("check") == check
