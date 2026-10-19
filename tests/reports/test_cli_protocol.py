from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from pring_cycle.reports import CliReportAdapter, ReportInput, ReportRepository, ReportService


def frozen_bundle(**extra_results: object) -> ReportInput:
    return ReportInput.create(
        projection_set_id="projection-protocol",
        target_business_date="2026-08-28",
        report_cutoff=datetime(2026, 8, 28, 10, tzinfo=UTC),
        system_as_of=datetime(2026, 8, 28, 10, tzinfo=UTC),
        model_version_id="model-v0001",
        trend_rule_version="trend-v0001",
        current_stage="stage_ii",
        stage_reason="canonical_combination",
        core_states={"bond": "bull", "stock": "bull", "commodity": "bear"},
        conclusions={
            "policy_direction": "easing",
            "credit_response": "insufficient_data",
            "overheat_state": "insufficient_data",
            "price_pressure": "producer_diffusion",
            "inventory_quadrant": None,
        },
        results={
            "formal_stage": {
                "value": "stage_ii",
                "reason": "canonical_combination",
                "source": "三核心价格状态",
                "anomaly": [],
            },
            **extra_results,
        },
    )


def install_cli(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    primary: str = "success",
    record_prompt: bool = False,
) -> Path:
    """Replace the external executable only; run the real process and report boundary."""
    import os

    executable_dir = tmp_path / "cli"
    executable_dir.mkdir()
    calls = executable_dir / "calls.jsonl"
    source = """#!/usr/bin/python3
import json, os, sys
from pathlib import Path
name=Path(sys.argv[0]).name
calls=Path(__file__).parent/'calls.jsonl'
if '--version-child' in sys.argv:
    import signal, time
    def terminate(*args):
        Path(__file__).with_suffix('.child-terminated').write_text('terminated')
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, terminate)
    Path(__file__).with_suffix('.child-ready').write_text('ready')
    time.sleep(60)
    raise SystemExit(0)
if '--version' in sys.argv:
    if PRIMARY=='version_hang':
        import subprocess, time
        child=subprocess.Popen([sys.executable,__file__,'--version-child'])
        while not Path(__file__).with_suffix('.child-ready').exists(): time.sleep(0.01)
        print('version probe partial',flush=True)
        child.wait()
        raise SystemExit(0)
    print('fixture-'+name+' 1.0');raise SystemExit(0)
if '--help' in sys.argv:
    print('--output-schema --json --safe-mode --json-schema --tools --max-turns')
    raise SystemExit(0)
event={'name':name,'args':sys.argv[1:],'https_proxy':os.environ.get('HTTPS_PROXY'),
       'key_visible':any(k in os.environ for k in ('OPENAI_API_KEY','ANTHROPIC_API_KEY'))}
with calls.open('a') as f: f.write(json.dumps(event)+'\\n')
if PRIMARY=='slow_stdin':
    import time
    time.sleep(0.75)
prompt=json.load(sys.stdin)
if PRIMARY=='both_hang' or (PRIMARY=='codex_hang' and name=='codex'):
    import time
    print(json.dumps({'type':'progress','partial':True}),flush=True)
    time.sleep(60)
if name=='codex' and PRIMARY=='authentication':
    print('Authentication required: please log in',file=sys.stderr);raise SystemExit(1)
bundle=prompt['report_input']
if RECORD:
    Path(__file__).with_suffix('.prompt.json').write_text(json.dumps(prompt))
document={'bundle_id':bundle['bundle_id'],'current_stage':bundle['current_stage'],'report_cutoff':bundle['report_cutoff'],'core_states':bundle['core_states'],'conclusions':bundle['conclusions'],'proxy_used':False,'sections':[{'title':'阶段依据','explanation':'债券与股票为牛市，商品为熊市，对应阶段II；宏观证据不参与正式阶段分类。'}]}
if PRIMARY=='rewrite_conclusion':
    document['conclusions']=dict(document['conclusions'],policy_direction='tightening')
if PRIMARY.startswith('tool_failure:'):
    if name=='codex':
        event={'type':'item.completed','item':{'type':'command_execution'}}
        Path(sys.argv[sys.argv.index('--output-last-message')+1]).write_bytes(b'{"partial":')
    else:
        event={'type':'assistant','message':{'content':[{'type':'tool_use','name':'Bash'}]}}
    print(json.dumps(event),flush=True)
    reason=PRIMARY.split(':')[1]
    if reason=='timeout':
        import time
        time.sleep(60)
    if reason=='malformed':
        print('{"partial":',flush=True)
        raise SystemExit(0)
    raise SystemExit(1)
if PRIMARY=='two_paragraphs':
    document['sections'][0]['explanation'] += '\\n\\n这是需要另行核查的第二段。'
if PRIMARY.startswith('wrong_type:'):
    field, value = PRIMARY[len('wrong_type:'):].split('=',1)
    document['sections'][0][field] = json.loads(value)
if name=='codex':
    Path(sys.argv[sys.argv.index('--output-last-message')+1]).write_text(json.dumps(document))
    if PRIMARY=='codex_other_tool':
        print(json.dumps({'type':'item.completed','item':{'type':'image_view'}}))
    if PRIMARY=='codex_notice':
        print(json.dumps({'type':'item.completed','item':{'id':'item_0','type':'error',
            'message':'Skill descriptions were shortened to fit the skills context budget.'}}))
    print(json.dumps({'type':'thread.started','thread_id':'fixture','model':'fixture-codex-model'}))
    print(json.dumps({'type':'turn.completed','usage':{'input_tokens':100,'output_tokens':50}}))
else:
    if PRIMARY=='claude_tool':
        block={'type':'tool_use','name':'Bash','input':{'command':'not executed by fixture'}}
        print(json.dumps({'type':'assistant','message':{'content':[block]}}))
    print(json.dumps({'type':'result','subtype':'success','is_error':False,'structured_output':document,'modelUsage':{'fixture-claude-model':{'inputTokens':100,'outputTokens':50}}}))
"""
    source = source.replace("PRIMARY", repr(primary)).replace("RECORD", repr(record_prompt))
    for name in ("codex", "claude"):
        program = executable_dir / name
        program.write_text(source)
        program.chmod(0o700)
    monkeypatch.setenv("PATH", str(executable_dir) + os.pathsep + os.environ.get("PATH", ""))
    monkeypatch.setenv("OPENAI_API_KEY", "fixture-must-not-reach-cli")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fixture-must-not-reach-cli")
    return calls


@pytest.mark.parametrize("primary", ["success", "authentication"])
def test_real_cli_boundary_persists_protocol_provenance_and_classifies_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, primary: str
) -> None:
    calls = install_cli(tmp_path, monkeypatch, primary=primary)
    reports = ReportRepository.create(tmp_path / "reports.sqlite3")
    result = ReportService(
        reports, (CliReportAdapter("codex_cli"), CliReportAdapter("claude_code_cli"))
    ).generate(frozen_bundle())
    assert result.status == "completed"
    events = [json.loads(line) for line in calls.read_text().splitlines()]
    assert [e["name"] for e in events] == (
        ["codex"] if primary == "success" else ["codex", "claude"]
    )
    assert all(not e["key_visible"] for e in events)
    attempts = reports.attempts(result.report_snapshot_id)
    assert attempts[0].adapter_version == "fixture-codex 1.0"
    if primary == "authentication":
        assert attempts[0].outcome == "authentication_required"
        assert attempts[0].process_audit["exit_code"] == 1
    success = attempts[-1]
    assert success.process_audit["exit_code"] == 0
    assert success.process_audit["model_id"] == (
        "fixture-codex-model" if primary == "success" else "fixture-claude-model"
    )
    assert len(success.process_audit["stdout_sha256"]) == 64
    assert len(success.process_audit["schema_sha256"]) == 64
    assert len(success.process_audit["prompt_sha256"]) == 64
    assert (
        reports.get(result.report_snapshot_id).body["explanation_verification"]["status"]
        == "pending_evidence_review"
    )


def test_new_report_records_current_protocol_without_rewriting_legacy_input_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_cli(tmp_path, monkeypatch)
    source = replace(
        frozen_bundle(), schema_version="report-schema-v0002", prompt_version="report-prompt-v0002"
    )
    before = source.document()
    reports = ReportRepository.create(tmp_path / "reports.sqlite3")
    original_hash = reports.save_bundle(source)
    result = ReportService(reports, (CliReportAdapter("codex_cli"),)).generate(source)
    snapshot = reports.get(result.report_snapshot_id)
    attempt = reports.attempts(result.report_snapshot_id)[0]
    assert (
        snapshot.schema_version == attempt.process_audit["schema_version"] == "report-schema-v0004"
    )
    assert (
        snapshot.prompt_version == attempt.process_audit["prompt_version"] == "report-prompt-v0008"
    )
    assert snapshot.input_schema_version == "report-schema-v0002"
    assert snapshot.input_prompt_version == "report-prompt-v0002"
    assert snapshot.bundle_id == source.bundle_id
    assert snapshot.bundle_hash == original_hash == reports.save_bundle(source)
    assert source.document() == before


def test_worker_environment_can_find_an_installed_user_cli_outside_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = install_cli(tmp_path, monkeypatch)
    user_prefix = tmp_path / "home" / ".npm-global" / "bin"
    user_prefix.mkdir(parents=True)
    (user_prefix / "claude").write_bytes((calls.parent / "claude").read_bytes())
    (user_prefix / "claude").chmod(0o700)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    reports = ReportRepository.create(tmp_path / "reports.sqlite3")
    result = ReportService(reports, (CliReportAdapter("claude_code_cli"),)).generate(
        frozen_bundle()
    )
    assert result.status == "completed"
    attempt = reports.attempts(result.report_snapshot_id)[0]
    assert attempt.adapter_version == "fixture-claude 1.0"
    assert attempt.process_audit["executable"] == str(user_prefix / "claude")


def test_report_cli_preserves_configured_network_route_without_model_api_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = install_cli(tmp_path, monkeypatch)
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:12345")
    reports = ReportRepository.create(tmp_path / "reports.sqlite3")
    result = ReportService(reports, (CliReportAdapter("codex_cli"),)).generate(frozen_bundle())
    assert result.status == "completed"
    event = json.loads(calls.read_text().splitlines()[0])
    assert event["https_proxy"] == "http://127.0.0.1:12345"
    assert event["key_visible"] is False


@pytest.mark.parametrize("cancel", [False, True])
def test_version_probe_shares_deadline_cancellation_and_process_group_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cancel: bool
) -> None:
    calls = install_cli(tmp_path, monkeypatch, primary="version_hang")
    reports = ReportRepository.create(tmp_path / "reports.sqlite3")
    source = frozen_bundle()
    ready = calls.parent / "codex.child-ready"
    adapter = CliReportAdapter(
        "codex_cli", timeout_seconds=1, cancel_requested=lambda: cancel and ready.exists()
    )
    service = ReportService(reports, (adapter,))
    if cancel:
        with pytest.raises(ValueError, match="report_generation_cancelled"):
            service.generate(source)
        assert reports.history() == ()
    else:
        result = service.generate(source)
        assert result.status == "completed_degraded"
    assert not calls.exists(), "generation must not start after version timeout/cancellation"
    assert (calls.parent / "codex.child-terminated").read_text() == "terminated"
    attempts = reports.attempts_for_bundle(source.bundle_id)
    assert len(attempts) == 1
    assert attempts[0].outcome == ("cancelled" if cancel else "timed_out")
    assert attempts[0].process_audit["process_phase"] == "version"
    assert attempts[0].process_audit["version_probe"]["stdout_bytes"] > 0


def test_cli_cancellation_is_audited_and_never_falls_back_or_publishes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = install_cli(tmp_path, monkeypatch, primary="both_hang")
    reports = ReportRepository.create(tmp_path / "reports.sqlite3")
    source = frozen_bundle()
    adapter = CliReportAdapter("codex_cli", cancel_requested=lambda: calls.exists())
    with pytest.raises(ValueError, match="report_generation_cancelled"):
        ReportService(
            reports, (adapter, CliReportAdapter("claude_code_cli", timeout_seconds=1))
        ).generate(source)
    assert reports.history() == ()
    assert [json.loads(line)["name"] for line in calls.read_text().splitlines()] == ["codex"]
    attempts = reports.attempts_for_bundle(source.bundle_id)
    assert len(attempts) == 1
    assert attempts[0].outcome == "cancelled"
    assert attempts[0].process_audit["exit_code"] == -15
    assert attempts[0].process_audit["stdout_bytes"] > 0


@pytest.mark.parametrize(
    "mode, expected", [("codex_hang", "completed"), ("both_hang", "completed_degraded")]
)
def test_cli_timeout_audit_preserves_partial_hash_and_bounded_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str, expected: str
) -> None:
    calls = install_cli(tmp_path, monkeypatch, primary=mode)
    reports = ReportRepository.create(tmp_path / "reports.sqlite3")
    result = ReportService(
        reports,
        (
            CliReportAdapter("codex_cli", timeout_seconds=1),
            CliReportAdapter("claude_code_cli", timeout_seconds=1),
        ),
    ).generate(frozen_bundle())
    assert result.status == expected
    assert [json.loads(line)["name"] for line in calls.read_text().splitlines()] == [
        "codex",
        "claude",
    ]
    attempt = reports.attempts(result.report_snapshot_id)[0]
    assert attempt.outcome == "timed_out"
    assert attempt.process_audit["exit_code"] == -15
    assert attempt.process_audit["stdout_bytes"] > 0


def test_a_prompt_larger_than_the_pipe_reaches_a_cli_that_reads_stdin_late(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The 10-19 report: 91,805 bytes against a 64 KiB pipe, read after the first poll."""
    install_cli(tmp_path, monkeypatch, primary="slow_stdin", record_prompt=True)
    source = frozen_bundle(padding="仓" * 40_000)
    reports = ReportRepository.create(tmp_path / "reports.sqlite3")
    result = ReportService(reports, (CliReportAdapter("codex_cli", timeout_seconds=10),)).generate(
        source
    )
    assert result.status == "completed"
    received = json.loads((tmp_path / "cli" / "codex.prompt.json").read_text())
    assert received["report_input"]["results"]["padding"] == "仓" * 40_000
    audit = reports.attempts(result.report_snapshot_id)[0].process_audit
    assert audit["prompt_bytes"] > 65_536
    assert audit["prompt_bytes_sent"] == audit["prompt_bytes"]


def test_claude_tool_event_is_rejected_even_with_a_valid_structured_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_cli(tmp_path, monkeypatch, primary="claude_tool")
    reports = ReportRepository.create(tmp_path / "reports.sqlite3")
    result = ReportService(reports, (CliReportAdapter("claude_code_cli"),)).generate(
        frozen_bundle()
    )
    assert result.status == "completed_degraded"
    attempt = reports.attempts(result.report_snapshot_id)[0]
    assert attempt.outcome == "tool_use_rejected"
    assert attempt.tool_events == 1


def test_a_codex_notice_is_recorded_without_counting_as_tool_use(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """codex reports its own notices as error items; they are not the model using a tool."""
    install_cli(tmp_path, monkeypatch, primary="codex_notice")
    reports = ReportRepository.create(tmp_path / "reports.sqlite3")

    result = ReportService(reports, (CliReportAdapter("codex_cli"),)).generate(frozen_bundle())

    assert result.status == "completed"
    attempt = reports.attempts(result.report_snapshot_id)[0]
    assert attempt.outcome == "succeeded"
    assert attempt.tool_events == 0
    # The notice itself stays visible in the audit rather than being silently dropped.
    assert attempt.process_audit["cli_notices"] == [
        "Skill descriptions were shortened to fit the skills context budget."
    ]


def test_codex_unknown_action_is_rejected_even_when_final_json_is_valid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_cli(tmp_path, monkeypatch, primary="codex_other_tool")
    reports = ReportRepository.create(tmp_path / "reports.sqlite3")
    result = ReportService(reports, (CliReportAdapter("codex_cli"),)).generate(frozen_bundle())
    assert result.status == "completed_degraded"
    assert reports.attempts(result.report_snapshot_id)[0].outcome == "tool_use_rejected"


def test_report_sections_require_one_paragraph_for_individual_evidence_review(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = install_cli(tmp_path, monkeypatch, primary="two_paragraphs")
    reports = ReportRepository.create(tmp_path / "reports.sqlite3")
    result = ReportService(
        reports, (CliReportAdapter("codex_cli"), CliReportAdapter("claude_code_cli"))
    ).generate(frozen_bundle())
    assert result.status == "completed_degraded"
    assert [json.loads(line)["name"] for line in calls.read_text().splitlines()] == [
        "codex",
        "claude",
    ]
    assert [a.outcome for a in reports.attempts(result.report_snapshot_id)] == [
        "paragraph_structure_invalid",
        "paragraph_structure_invalid",
    ]
    assert "ai_explanation" not in reports.get(result.report_snapshot_id).body


@pytest.mark.parametrize("adapter_name", ["codex_cli", "claude_code_cli"])
@pytest.mark.parametrize(
    "reason, outcome",
    [("timeout", "timed_out"), ("malformed", "invalid_json_output"), ("exit", "nonzero_exit")],
)
def test_failed_cli_output_retains_observed_tools_and_output_file_fingerprint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, adapter_name: str, reason: str, outcome: str
) -> None:
    import hashlib

    install_cli(tmp_path, monkeypatch, primary="tool_failure:" + reason)
    reports = ReportRepository.create(tmp_path / "reports.sqlite3")
    result = ReportService(reports, (CliReportAdapter(adapter_name, timeout_seconds=1),)).generate(
        frozen_bundle()
    )
    assert result.status == "completed_degraded"
    attempt = reports.attempts(result.report_snapshot_id)[0]
    assert attempt.outcome == outcome
    assert attempt.tool_events == 1
    assert attempt.process_audit["tool_events"] == 1
    if adapter_name == "codex_cli":
        assert (
            attempt.process_audit["output_file_sha256"]
            == hashlib.sha256(b'{"partial":').hexdigest()
        )
        assert attempt.process_audit["output_file_bytes"] == 11
    assert "ai_explanation" not in reports.get(result.report_snapshot_id).body


@pytest.mark.parametrize(
    "invalid_field",
    ["title=42", "explanation=null", 'evidence_ids=["obs-bond"]'],
)
def test_invalid_cli_schema_is_audited_and_falls_back_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, invalid_field: str
) -> None:
    calls = install_cli(tmp_path, monkeypatch, primary="wrong_type:" + invalid_field)
    reports = ReportRepository.create(tmp_path / "reports.sqlite3")
    result = ReportService(
        reports, (CliReportAdapter("codex_cli"), CliReportAdapter("claude_code_cli"))
    ).generate(frozen_bundle())
    assert result.status == "completed_degraded"
    assert [json.loads(line)["name"] for line in calls.read_text().splitlines()] == [
        "codex",
        "claude",
    ]
    attempts = reports.attempts(result.report_snapshot_id)
    assert [a.outcome for a in attempts] == ["schema_validation_failed", "schema_validation_failed"]
    assert all(a.output_hash and a.process_audit["exit_code"] == 0 for a in attempts)


def test_paragraph_review_binds_exact_output_and_facts_without_rewriting_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_cli(tmp_path, monkeypatch)
    reports = ReportRepository.create(tmp_path / "reports.sqlite3")
    result = ReportService(reports, (CliReportAdapter("codex_cli"),)).generate(frozen_bundle())
    before = reports.get(result.report_snapshot_id)
    output_hash = reports.attempts(result.report_snapshot_id)[0].output_hash
    sections = [
        {
            "index": 0,
            "verdict": "supported",
            "assessment": "三核心状态和阶段II均与冻结事实一致；已说明宏观证据不决定阶段。",
            "support": [
                {"pointer": "/core_states/bond", "value": "bull"},
                {"pointer": "/core_states/stock", "value": "bull"},
                {"pointer": "/core_states/commodity", "value": "bear"},
                {"pointer": "/current_stage", "value": "stage_ii"},
            ],
            "counterevidence": [
                {"pointer": "/results/formal_stage/source", "value": "三核心价格状态"}
            ],
        }
    ]
    with pytest.raises(ValueError, match="review_output_mismatch"):
        reports.record_explanation_review(
            result.report_snapshot_id,
            output_hash="0" * 64,
            reviewer="protocol-fixture",
            sections=sections,
        )
    bad = json.loads(json.dumps(sections))
    bad[0]["support"][0]["value"] = "bear"
    with pytest.raises(ValueError, match="review_fact_mismatch"):
        reports.record_explanation_review(
            result.report_snapshot_id,
            output_hash=output_hash,
            reviewer="protocol-fixture",
            sections=bad,
        )
    assert reports.explanation_reviews(result.report_snapshot_id) == ()
    reports.record_explanation_review(
        result.report_snapshot_id,
        output_hash=output_hash,
        reviewer="protocol-fixture",
        sections=sections,
    )
    after = reports.get(result.report_snapshot_id)
    assert after.body == before.body
    assert after.bundle_hash == before.bundle_hash
    assert after.explanation_verification["status"] == "passed"
    assert len(reports.explanation_reviews(result.report_snapshot_id)) == 1


def test_rewritten_conclusion_is_rejected_and_the_report_degrades(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_cli(tmp_path, monkeypatch, primary="rewrite_conclusion")
    reports = ReportRepository.create(tmp_path / "reports.sqlite3")
    result = ReportService(
        reports, (CliReportAdapter("codex_cli"), CliReportAdapter("claude_code_cli"))
    ).generate(frozen_bundle())

    assert result.status == "completed_degraded"
    assert [a.outcome for a in reports.attempts(result.report_snapshot_id)] == [
        "conclusion_mutation_rejected",
        "conclusion_mutation_rejected",
    ]
    body = reports.get(result.report_snapshot_id).body
    assert body["conclusions"]["policy_direction"] == "easing"
    assert "ai_explanation" not in body
