"""Phase two #11: AI WebSearch through the installed CLIs, Codex first and Claude after."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.models import ModelRepository
from pring_cycle.runs import RunRecord, RunRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.storage import database_connection
from pring_cycle.worker import process_pending_run
from tests.fixtures.model_registration import prepared_request, save, submit

CLS = "https://www.cls.cn/detail/2140001"
SENTENCES = {
    "yoy": ("2026年8月份，全国居民消费价格同比上涨0.8%。", 0.8),
    "mom": ("8月份，全国居民消费价格环比上涨0.4%。", 0.4),
    "cumulative_average_yoy": ("1—8月平均，全国居民消费价格比上年同期上涨0.9%。", 0.9),
}

FAKE_CLI = """#!/usr/bin/python3
import json, os, sys, time
from pathlib import Path
here = Path(__file__).parent
name = Path(sys.argv[0]).name
if '--version' in sys.argv:
    print('fixture-' + name + ' 1.0'); raise SystemExit(0)
plan = json.loads((here / 'plan.json').read_text())[name]
with (here / 'calls.jsonl').open('a') as f:
    f.write(json.dumps({'name': name, 'args': sys.argv[1:],
        'key_visible': any(k in os.environ for k in ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY')),
        'prompt': json.load(sys.stdin)}) + '\\n')
if plan['mode'] == 'hang':
    time.sleep(60)
document = {'candidates': plan['candidates']}
if name == 'codex':
    out = sys.argv[sys.argv.index('--output-last-message') + 1]
    Path(out).write_text(json.dumps(document))
    print(json.dumps({'type': 'item.completed', 'item': {'type': 'web_search'}}))
    print(json.dumps({'type': 'turn.completed'}))
else:
    block = {'type': 'tool_use', 'name': 'WebSearch', 'input': {'query': 'cpi'}}
    print(json.dumps({'type': 'assistant', 'message': {'content': [block]}}))
    print(json.dumps({'type': 'result', 'subtype': 'success', 'is_error': False,
        'structured_output': document}))
"""


def candidate(measure: str, **changes: Any) -> dict[str, Any]:
    quote, value = SENTENCES[measure]
    return {
        "url": CLS,
        "quote": quote,
        "value": value,
        "period": "2026-08",
        "published_date": "2026-09-09",
        **changes,
    }


def install(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, plan: dict[str, Any]) -> Path:
    directory = tmp_path / "cli"
    directory.mkdir()
    for name in ("codex", "claude"):
        program = directory / name
        program.write_text(FAKE_CLI)
        program.chmod(0o700)
    (directory / "plan.json").write_text(json.dumps(plan))
    monkeypatch.setenv("PATH", str(directory) + os.pathsep + os.environ.get("PATH", ""))
    monkeypatch.setenv("OPENAI_API_KEY", "fixture-must-not-reach-cli")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fixture-must-not-reach-cli")
    return directory / "calls.jsonl"


def ai_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    plan: dict[str, Any],
    *,
    metric_ids: tuple[str, ...] = ("CN_CPI_HEADLINE",),
) -> tuple[RunRecord, RuntimePaths, str, list[dict[str, Any]]]:
    calls = install(tmp_path, monkeypatch, plan)
    monkeypatch.delenv("PRING_CYCLE_AI_WEBSEARCH")
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    ModelRepository(paths.database).activate(model_id, explicitly_approved=True)
    paths.config_file.write_text(
        paths.config_file.read_text() + "\n[retrieval]\nai_websearch = true\n"
    )
    runs = RunRepository(paths.database)
    submitted = runs.submit(
        command_type="targeted_refresh",
        target_business_date="2026-09-10",
        client_request_id="ai-websearch",
        model_version_id=model_id,
        system_as_of=datetime.now(UTC) + timedelta(days=1),
        release_event_id="ai:cpi:2026-08",
        metric_ids=metric_ids,
        period="2026-08",
    )
    process_pending_run(paths, report_adapters=())
    made = [json.loads(line) for line in calls.read_text().splitlines()] if calls.exists() else []
    return runs.get(submitted.run_id), paths, request["manifest"]["metric_catalog_version"], made


def cpi(paths: RuntimePaths, version: str) -> dict[str, float | None]:
    return {
        p.dimensions["measure"]: p.selected_value
        for p in EvidenceRepository(paths.database).metric_series(
            "CN_CPI_HEADLINE",
            mode=AsOfMode.SYSTEM,
            as_of=datetime.now(UTC) + timedelta(days=2),
            definition_version=version,
        )
    }


ALL_THREE = [candidate(measure) for measure in SENTENCES]


@pytest.mark.usefixtures("runtime_clock")
def test_codex_candidates_fill_the_p1_gap_with_their_quotes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    stored, paths, version, calls = ai_run(
        tmp_path,
        monkeypatch,
        capsys,
        {
            "codex": {"mode": "ok", "candidates": ALL_THREE},
            "claude": {"mode": "ok", "candidates": []},
        },
    )

    assert stored.status == "completed", stored.error_classification
    assert [call["name"] for call in calls] == ["codex"]
    assert calls[0]["args"][0] == "--search"
    assert not calls[0]["key_visible"]
    assert calls[0]["prompt"]["search_query"] == "2026年8月份居民消费价格"
    assert calls[0]["prompt"]["allowed_domains"][0] == "www.stats.gov.cn"
    assert cpi(paths, version) == {"yoy": 0.8, "mom": 0.4, "cumulative_average_yoy": 0.9}
    ledger = stored.retrieval_ledger
    [request] = [r for r in ledger["requests"] if r["channel"] == "ai_websearch"]
    assert (request["provider"], request["outcome"]) == ("codex_cli", "verified")
    assert request["started_at"] <= request["completed_at"]
    assert [v["outcome"] for v in ledger["candidate_validations"]] == ["model_usable"] * 3
    with database_connection(paths.database) as connection:
        routes = connection.execute("SELECT DISTINCT route, source_name FROM claim_matched_quote")
        assert routes.fetchall() == [("ai_websearch", "财联社")]


@pytest.mark.usefixtures("runtime_clock")
def test_claude_fills_the_gap_when_codex_times_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("pring_cycle.ai_websearch.AI_CALL_SECONDS", 2)

    stored, paths, version, calls = ai_run(
        tmp_path,
        monkeypatch,
        capsys,
        {
            "codex": {"mode": "hang", "candidates": []},
            "claude": {"mode": "ok", "candidates": ALL_THREE},
        },
    )

    assert stored.status == "completed", stored.error_classification
    assert [call["name"] for call in calls] == ["codex", "claude"]
    assert "WebSearch" in calls[1]["args"]
    assert cpi(paths, version) == {"yoy": 0.8, "mom": 0.4, "cumulative_average_yoy": 0.9}
    [request] = [r for r in stored.retrieval_ledger["requests"] if r["channel"] == "ai_websearch"]
    assert request["provider"] == "claude_code_cli"


@pytest.mark.usefixtures("runtime_clock")
def test_each_unusable_candidate_is_rejected_with_its_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    candidates = [
        candidate("yoy", url="https://finance.example.com/cpi"),
        candidate("yoy", value=0.9),
        candidate("yoy", period="2026-07"),
        candidate("yoy", published_date="2099-01-01"),
        candidate("yoy", quote="8月份CPI同比涨幅扩大至0.8%。"),
    ]

    stored, paths, version, _calls = ai_run(
        tmp_path,
        monkeypatch,
        capsys,
        {
            "codex": {"mode": "ok", "candidates": candidates},
            "claude": {"mode": "ok", "candidates": []},
        },
    )

    assert [
        (v["outcome"], v["reason"]) for v in stored.retrieval_ledger["candidate_validations"]
    ] == [
        ("not_model_usable", "not_whitelisted"),
        ("not_model_usable", "search_value_mismatch"),
        ("not_model_usable", "period_mismatch"),
        ("not_model_usable", "date_after_cutoff"),
        ("not_model_usable", "rule_not_matched"),
    ]
    assert cpi(paths, version) == {}


@pytest.mark.usefixtures("runtime_clock")
def test_the_run_stops_calling_once_its_ai_time_is_spent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("pring_cycle.ai_websearch.AI_RUN_BUDGET", timedelta(0))

    stored, _paths, _version, calls = ai_run(
        tmp_path,
        monkeypatch,
        capsys,
        {
            "codex": {"mode": "ok", "candidates": ALL_THREE},
            "claude": {"mode": "ok", "candidates": []},
        },
    )

    assert calls == []
    [attempt] = [a for a in stored.retrieval_attempts if a["channel"] == "ai_websearch"]
    assert (attempt["outcome"], attempt["classification"]) == (
        "not_attempted",
        "ai_time_exhausted",
    )


@pytest.mark.usefixtures("runtime_clock")
def test_a_figure_given_as_the_sentence_writes_it_is_the_same_figure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """ "下降0.4%" is -0.4 for the member; the CLI may report the 0.4 it reads."""
    falling = candidate("yoy", quote="2026年8月份，全国居民消费价格同比下降0.4%。", value=0.4)

    stored, paths, version, _calls = ai_run(
        tmp_path,
        monkeypatch,
        capsys,
        {
            "codex": {"mode": "ok", "candidates": [falling, *ALL_THREE[1:]]},
            "claude": {"mode": "ok", "candidates": []},
        },
    )

    assert stored.status == "completed", stored.error_classification
    assert cpi(paths, version)["yoy"] == -0.4


@pytest.mark.usefixtures("runtime_clock")
def test_a_gap_the_rules_cannot_complete_is_not_asked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """PPI's component year-to-date averages are only in the official table."""
    stored, _paths, _version, calls = ai_run(
        tmp_path,
        monkeypatch,
        capsys,
        {"codex": {"mode": "ok", "candidates": []}, "claude": {"mode": "ok", "candidates": []}},
        metric_ids=("CN_PPI",),
    )

    assert calls == []
    [attempt] = [a for a in stored.retrieval_attempts if a["channel"] == "ai_websearch"]
    assert attempt["outcome"] == "not_configured"


def test_ai_websearch_is_on_unless_turned_off(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pring_cycle.ai_websearch import ai_websearch_enabled

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    monkeypatch.delenv("PRING_CYCLE_AI_WEBSEARCH")
    assert ai_websearch_enabled(paths)
    paths.config_file.write_text("[retrieval]\nai_websearch = false\n")
    assert not ai_websearch_enabled(paths)
    paths.config_file.write_text("[retrieval]\nai_websearch = true\n")
    monkeypatch.setenv("PRING_CYCLE_AI_WEBSEARCH", "off")
    assert not ai_websearch_enabled(paths)
