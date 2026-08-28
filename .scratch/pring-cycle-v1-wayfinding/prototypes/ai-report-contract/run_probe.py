#!/usr/bin/env python3
"""PROTOTYPE ONLY — empirically probe Codex and Claude report adapters."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
BUNDLE_PATH = ROOT / "evidence-bundle.json"
SCHEMA_PATH = ROOT / "report-output.schema.json"
SYSTEM_PROMPT_PATH = ROOT / "system-prompt.txt"
REQUIRED_SECTIONS = {
    "formal_stage",
    "core_assets",
    "policy_and_credit",
    "inventory_and_overheat",
    "price_pressure",
    "data_quality",
}


def sanitized_environment() -> dict[str, str]:
    allowed = {
        "HOME",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "LOGNAME",
        "PATH",
        "NO_PROXY",
        "SHELL",
        "TERM",
        "TMPDIR",
        "USER",
        "XDG_CACHE_HOME",
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
        "XDG_RUNTIME_DIR",
        "XDG_STATE_HOME",
        "http_proxy",
        "https_proxy",
        "all_proxy",
        "no_proxy",
    }
    return {key: value for key, value in os.environ.items() if key in allowed}


def build_user_prompt(bundle: dict[str, Any], system_prompt: str) -> str:
    return (
        "<report_contract>\n"
        + system_prompt
        + "\n</report_contract>\n"
        + "请将下面唯一允许使用的证据包渲染为符合输出 schema 的中文报告。"
        + "不要调用任何工具。\n<evidence_bundle>\n"
        + json.dumps(bundle, ensure_ascii=False, separators=(",", ":"))
        + "\n</evidence_bundle>\n"
    )


def run_process(
    command: list[str],
    prompt: str,
    timeout_seconds: float,
    cwd: Path,
) -> tuple[int | None, str, str, float, str]:
    started = time.monotonic()
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=sanitized_environment(),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(prompt, timeout=timeout_seconds)
        outcome = "completed"
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            stdout, stderr = process.communicate()
        outcome = "timed_out"
    duration = round(time.monotonic() - started, 3)
    return process.returncode, stdout, stderr, duration, outcome


def validate_report(report: Any, bundle: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(report, dict):
        return ["output_not_object"]
    expected = {
        "schema_version": "report.v1-prototype",
        "bundle_id": bundle["bundle_id"],
        "report_cutoff": bundle["report_cutoff"],
        "current_stage": bundle["formal_stage"]["current_stage"],
    }
    for key, value in expected.items():
        if report.get(key) != value:
            errors.append(f"immutable_field_mismatch:{key}")
    sections = report.get("sections")
    if not isinstance(sections, list):
        errors.append("sections_not_array")
        sections = []
    section_ids = {item.get("section_id") for item in sections if isinstance(item, dict)}
    if section_ids != REQUIRED_SECTIONS:
        errors.append("section_set_mismatch")
    allowed_ids = set(bundle["constraints"]["allowed_evidence_ids"])
    allowed_governance_refs = set(bundle["constraints"]["allowed_governance_refs"])
    cited_ids: set[str] = set()
    for section in sections:
        if not isinstance(section, dict):
            errors.append("section_not_object")
            continue
        evidence_ids = section.get("evidence_ids")
        governance_refs = section.get("governance_refs") or []
        section_id = section.get("section_id")
        if section_id != "data_quality" and not evidence_ids:
            errors.append(f"section_without_evidence:{section.get('section_id')}")
        if section_id == "data_quality" and not governance_refs:
            errors.append("data_quality_without_governance_ref")
        unknown = set(evidence_ids or []) - allowed_ids
        if len(evidence_ids or []) != len(set(evidence_ids or [])):
            errors.append(f"duplicate_evidence:{section_id}")
        if unknown:
            errors.append(f"unknown_evidence:{','.join(sorted(unknown))}")
        unknown_governance = set(governance_refs) - allowed_governance_refs
        if len(governance_refs) != len(set(governance_refs)):
            errors.append(f"duplicate_governance_ref:{section_id}")
        if unknown_governance:
            errors.append(f"unknown_governance_ref:{','.join(sorted(unknown_governance))}")
        cited_ids.update(evidence_ids or [])
    used_ids = set(report.get("used_evidence_ids") or [])
    if len(report.get("used_evidence_ids") or []) != len(used_ids):
        errors.append("duplicate_used_evidence")
    if used_ids - allowed_ids:
        errors.append("used_evidence_outside_bundle")
    if cited_ids - used_ids:
        errors.append("section_evidence_missing_from_used_list")
    watches = report.get("transition_watches") or []
    if len(watches) != 1 or watches[0].get("status") != "asset_candidate_only":
        errors.append("transition_watch_semantics_invalid")
    elif set(watches[0].get("evidence_ids") or []) != {
        "ev-commodity-state",
        "ev-commodity-watch",
    }:
        errors.append("transition_watch_evidence_invalid")
    gaps = report.get("data_gaps") or []
    if len(gaps) != 1 or gaps[0].get("proxy_used") is not False:
        errors.append("uncertified_source_proxy_violation")
    return errors


def codex_probe(prompt: str, timeout_seconds: float, temp_dir: Path) -> dict[str, Any]:
    output_path = temp_dir / "codex-final.json"
    command = [
        "codex",
        "exec",
        "--ephemeral",
        "--ignore-user-config",
        "--ignore-rules",
        "--skip-git-repo-check",
        "--sandbox",
        "read-only",
        "--json",
        "--output-schema",
        str(SCHEMA_PATH),
        "--output-last-message",
        str(output_path),
        "-C",
        str(temp_dir),
        "-",
    ]
    code, stdout, _stderr, duration, process_outcome = run_process(
        command, prompt, timeout_seconds, temp_dir
    )
    event_types: list[str] = []
    tool_events = 0
    cli_errors: list[str] = []
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        event_types.append(str(event.get("type", "unknown")))
        if event.get("type") == "turn.failed":
            failure = event.get("error") or event.get("message") or "unknown_turn_failure"
            cli_errors.append(str(failure)[:500])
        item = event.get("item") or {}
        if item.get("type") == "error":
            message = str(item.get("message", "unknown_error"))
            cli_errors.append(message[:240])
        if item.get("type") in {
            "command_execution",
            "file_change",
            "mcp_tool_call",
            "web_search",
        }:
            tool_events += 1
    report = None
    parse_error = None
    if output_path.exists():
        try:
            report = json.loads(output_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            parse_error = type(exc).__name__
    return {
        "adapter": "codex_cli",
        "exit_code": code,
        "process_outcome": process_outcome,
        "duration_seconds": duration,
        "tool_events": tool_events,
        "event_types": sorted(set(event_types)),
        "cli_errors": cli_errors,
        "parse_error": parse_error,
        "report": report,
    }


def claude_probe(
    prompt: str,
    schema: dict[str, Any],
    system_prompt: str,
    timeout_seconds: float,
    temp_dir: Path,
) -> dict[str, Any]:
    command = [
        "claude",
        "-p",
        "--safe-mode",
        "--disable-slash-commands",
        "--no-session-persistence",
        "--permission-mode",
        "dontAsk",
        "--tools",
        "",
        "--output-format",
        "json",
        "--json-schema",
        json.dumps(schema, ensure_ascii=False, separators=(",", ":")),
        "--system-prompt",
        system_prompt,
    ]
    code, stdout, _stderr, duration, process_outcome = run_process(
        command, prompt, timeout_seconds, temp_dir
    )
    wrapper = None
    report = None
    parse_error = None
    try:
        wrapper = json.loads(stdout)
        if wrapper.get("is_error"):
            parse_error = f"cli_error:{wrapper.get('terminal_reason') or 'unknown'}"
        else:
            report = wrapper.get("structured_output")
        if report is None and not wrapper.get("is_error") and isinstance(wrapper.get("result"), str):
            report = json.loads(wrapper["result"])
    except (json.JSONDecodeError, TypeError) as exc:
        parse_error = type(exc).__name__
    return {
        "adapter": "claude_code_cli",
        "exit_code": code,
        "process_outcome": process_outcome,
        "duration_seconds": duration,
        "tool_events": 0,
        "wrapper_subtype": wrapper.get("subtype") if isinstance(wrapper, dict) else None,
        "cli_is_error": wrapper.get("is_error") if isinstance(wrapper, dict) else None,
        "terminal_reason": wrapper.get("terminal_reason") if isinstance(wrapper, dict) else None,
        "cli_error_message": str(wrapper.get("result", ""))[:300]
        if isinstance(wrapper, dict) and wrapper.get("is_error")
        else None,
        "parse_error": parse_error,
        "report": report,
    }


def public_result(probe: dict[str, Any], bundle: dict[str, Any]) -> dict[str, Any]:
    validation_errors = validate_report(probe.get("report"), bundle)
    report_bytes = json.dumps(
        probe.get("report"), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return {
        key: value
        for key, value in probe.items()
        if key != "report"
    } | {
        "schema_valid": not validation_errors,
        "validation_errors": validation_errors,
        "output_sha256": hashlib.sha256(report_bytes).hexdigest()
        if probe.get("report") is not None
        else None,
        "report": probe.get("report"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--adapter", choices=["codex", "claude", "both"], default="both")
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    parser.add_argument("--save", type=Path)
    args = parser.parse_args()

    bundle = json.loads(BUNDLE_PATH.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    system_prompt = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    prompt = build_user_prompt(bundle, system_prompt)
    results: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="pring-ai-report-prototype-") as raw_temp:
        temp_dir = Path(raw_temp)
        if args.adapter in {"codex", "both"}:
            results.append(public_result(codex_probe(prompt, args.timeout_seconds, temp_dir), bundle))
        if args.adapter in {"claude", "both"}:
            results.append(
                public_result(
                    claude_probe(prompt, schema, system_prompt, args.timeout_seconds, temp_dir),
                    bundle,
                )
            )

    result = {
        "prototype": "ai-report-contract",
        "fixture_only": True,
        "bundle_id": bundle["bundle_id"],
        "results": results,
    }
    serialized = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.save:
        args.save.write_text(serialized, encoding="utf-8")
    print(serialized, end="")
    return 0 if all(item["schema_valid"] for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
