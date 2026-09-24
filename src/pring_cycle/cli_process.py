"""One structured call of an installed AI CLI (Codex or Claude Code) as a child process.

Shared by the report adapter and AI WebSearch: the executable is found on PATH (or the
user's install prefixes), its version is probed within the same deadline, the call runs
in its own process group with a JSON Schema for its answer, and is killed with its group
on timeout or cancellation. Only a fixed set of environment variables reaches it: no
model vendor API key is ever passed, the CLI's own login is used (ADR-0009).

web_search opens the CLI's own live web search and nothing else: any other tool event
is counted as tool use, which the caller rejects.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import signal
import subprocess
import tempfile
import time
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

CLI_EXECUTABLES = {"codex_cli": "codex", "claude_code_cli": "claude"}
_ENVIRONMENT = {
    "PATH",
    "HOME",
    "LANG",
    "LC_ALL",
    "TERM",
    "COLORTERM",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "no_proxy",
    "SSL_CERT_FILE",
    "NODE_EXTRA_CA_CERTS",
}
# The web search tool itself, as each CLI reports it.
CODEX_WEB_SEARCH_ITEMS = {"web_search"}
CLAUDE_WEB_SEARCH_TOOLS = {"WebSearch"}


@dataclass(frozen=True)
class CliOutcome:
    document: dict[str, Any] | None
    classification: str | None
    version: str
    audit: dict[str, Any] = field(default_factory=dict)
    tool_events: int = 0


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def resolve_cli(name: str) -> str | None:
    executable = CLI_EXECUTABLES[name]
    resolved = shutil.which(executable)
    if resolved is not None:
        return resolved
    return next(
        (
            str(candidate)
            for directory in (Path.home() / ".local/bin", Path.home() / ".npm-global/bin")
            if (candidate := directory / executable).is_file() and os.access(candidate, os.X_OK)
        ),
        None,
    )


def run_structured_cli(
    name: str,
    prompt: str,
    schema: dict[str, Any],
    *,
    timeout_seconds: float,
    cancel_requested: Callable[[], bool] | None = None,
    audit: dict[str, Any] | None = None,
    web_search: bool = False,
) -> CliOutcome:
    """Run one CLI call; its document, or why none, with the process audit."""
    deadline = time.monotonic() + timeout_seconds
    resolved = resolve_cli(name)
    if resolved is None:
        return CliOutcome(None, "cli_not_installed", "runtime-detected")
    environment = {key: value for key, value in os.environ.items() if key in _ENVIRONMENT}
    version = "unavailable"
    with tempfile.TemporaryDirectory(prefix="pring-cli-") as work_directory:
        work_path = Path(work_directory)
        schema_path = work_path / "output.schema.json"
        output_path = work_path / "output.json"
        schema_path.write_text(_canonical_json(schema), encoding="utf-8")
        record: dict[str, Any] = {
            "executable": resolved,
            "cli_version": version,
            "model_id": None,
            "model_reporting": "not_reported",
            **(audit or {}),
            "schema_sha256": hashlib.sha256(_canonical_json(schema).encode()).hexdigest(),
            "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "prompt_bytes": len(prompt.encode()),
            "web_search": web_search,
            "exit_code": None,
            "process_phase": "version",
        }

        def failed(classification: str) -> CliOutcome:
            return CliOutcome(
                None, classification, version, record, int(record.get("tool_events", 0))
            )

        try:
            version_process = subprocess.Popen(
                [resolved, "--version"],
                cwd=work_directory,
                env=environment,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
                text=True,
            )
        except OSError:
            return failed("process_start_failed")
        version_stdout, version_stderr, version_outcome = _communicate_with_limits(
            version_process,
            "",
            deadline=min(deadline, time.monotonic() + 5),
            cancel_requested=cancel_requested,
        )
        record["version_probe"] = {
            **_process_output_fingerprint(version_process, version_stdout, version_stderr),
            "outcome": version_outcome
            or ("succeeded" if version_process.returncode == 0 else "nonzero_exit"),
        }
        if version_outcome is not None:
            record["exit_code"] = version_process.returncode
            return failed(version_outcome)
        if version_process.returncode == 0 and version_stdout.strip():
            version = version_stdout.strip()[:200]
        record["cli_version"] = version
        if cancel_requested is not None and cancel_requested():
            return failed("cancelled")
        if time.monotonic() >= deadline:
            return failed("timed_out")
        record["process_phase"] = "generation"
        command = (
            [
                resolved,
                *(["--search"] if web_search else []),
                "exec",
                "--ephemeral",
                "--ignore-user-config",
                "--ignore-rules",
                "--sandbox",
                "read-only",
                "--skip-git-repo-check",
                "--output-schema",
                str(schema_path),
                "--output-last-message",
                str(output_path),
                "--json",
                "-",
            ]
            if name == "codex_cli"
            else [
                resolved,
                "--print",
                "--safe-mode",
                "--disable-slash-commands",
                "--tools",
                "WebSearch" if web_search else "",
                *(["--allowedTools", "WebSearch"] if web_search else []),
                "--permission-mode",
                "dontAsk",
                "--no-session-persistence",
                "--output-format",
                "stream-json",
                "--verbose",
                "--json-schema",
                _canonical_json(schema),
            ]
        )
        try:
            process = subprocess.Popen(
                command,
                cwd=work_directory,
                env=environment,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
                text=True,
            )
        except OSError:
            return failed("process_start_failed")
        stdout, stderr, outcome = _communicate_with_limits(
            process, prompt, deadline=deadline, cancel_requested=cancel_requested
        )
        record.update(_process_output_fingerprint(process, stdout, stderr))
        models = _reported_cli_models(stdout)
        if models:
            record["model_ids"] = models
            record["model_id"] = models[0] if len(models) == 1 else None
            record["model_reporting"] = "cli_output"
        record.update(_cli_event_audit(name, stdout, web_search=web_search))
        if name == "codex_cli":
            try:
                output_bytes = output_path.read_bytes()
            except OSError:
                record["output_file_status"] = "unavailable"
            else:
                record.update(
                    output_file_status="captured",
                    output_file_sha256=hashlib.sha256(output_bytes).hexdigest(),
                    output_file_bytes=len(output_bytes),
                )
        if outcome is not None:
            return failed(outcome)
        if process.returncode != 0:
            return failed(_cli_failure_classification(stdout, stderr))
        try:
            document = (
                _codex_output(stdout, output_path)
                if name == "codex_cli"
                else _claude_output(stdout)
            )
        except (json.JSONDecodeError, OSError, ValueError):
            return failed("invalid_json_output")
    if not isinstance(document, dict):
        return failed("invalid_json_schema")
    return CliOutcome(document, None, version, record, int(record["tool_events"]))


def _process_output_fingerprint(
    process: subprocess.Popen[str], stdout: str, stderr: str
) -> dict[str, Any]:
    return {
        "exit_code": process.returncode,
        "stdout_sha256": hashlib.sha256(stdout.encode()).hexdigest(),
        "stderr_sha256": hashlib.sha256(stderr.encode()).hexdigest(),
        "stdout_bytes": len(stdout.encode()),
        "stderr_bytes": len(stderr.encode()),
    }


def _communicate_with_limits(
    process: subprocess.Popen[str],
    prompt: str,
    *,
    deadline: float,
    cancel_requested: Callable[[], bool] | None,
) -> tuple[str, str, str | None]:
    first = True
    while True:
        if cancel_requested is not None and cancel_requested():
            stdout, stderr = _terminate_process_group(process)
            return stdout, stderr, "cancelled"
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            stdout, stderr = _terminate_process_group(process)
            return stdout, stderr, "timed_out"
        try:
            stdout, stderr = process.communicate(
                prompt if first else None,
                timeout=min(0.5, remaining),
            )
            return stdout, stderr, None
        except subprocess.TimeoutExpired:
            first = False


def _terminate_process_group(process: subprocess.Popen[str]) -> tuple[str, str]:
    with suppress(ProcessLookupError):
        os.killpg(process.pid, signal.SIGTERM)
    try:
        return process.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        return process.communicate()


def _reported_cli_models(stdout: str) -> list[str]:
    models: set[str] = set()
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        if isinstance(event.get("model"), str):
            models.add(event["model"])
        if isinstance(event.get("modelUsage"), dict):
            models.update(str(model) for model in event["modelUsage"])
    return sorted(models)


def _cli_failure_classification(stdout: str, stderr: str) -> str:
    error = (stderr + "\n" + stdout).lower()
    if any(
        term in error
        for term in (
            "not logged in",
            "please log in",
            "authentication required",
            "unauthorized",
            "invalid authentication",
        )
    ):
        return "authentication_required"
    if any(
        term in error
        for term in ("rate limit", "quota exceeded", "usage limit", "insufficient credits")
    ):
        return "quota_or_rate_limited"
    if any(
        term in error
        for term in (
            "unexpected argument",
            "unknown option",
            "invalid json schema",
            "invalid schema",
        )
    ):
        return "cli_protocol_incompatible"
    return "nonzero_exit"


# Item types codex reports that are the CLI speaking about itself, not the model acting:
# its own notices ("error") and its visible thinking. Anything else counts as tool use, so an
# unknown type is rejected rather than quietly allowed.
CODEX_NON_TOOL_ITEMS = {"reasoning", "agent_message", "error"}


def _cli_event_audit(adapter: str, stdout: str, *, web_search: bool = False) -> dict[str, Any]:
    """Count observable complete events independently of process/output acceptance."""
    tools, invalid_lines = 0, 0
    notices: list[str] = []
    for line in stdout.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            invalid_lines += 1
            continue
        if not isinstance(event, dict):
            invalid_lines += 1
            continue
        if adapter == "codex_cli":
            item = event.get("item")
            if not isinstance(item, dict):
                continue
            if item.get("type") == "error" and isinstance(item.get("message"), str):
                notices.append(item["message"])
            allowed = CODEX_NON_TOOL_ITEMS | (CODEX_WEB_SEARCH_ITEMS if web_search else set())
            tools += int(item.get("type") not in allowed)
        elif event.get("type") == "assistant":
            message = event.get("message")
            if not isinstance(message, dict) or not isinstance(message.get("content"), list):
                invalid_lines += 1
                continue
            tools += sum(
                1
                for block in message["content"]
                if isinstance(block, dict)
                and block.get("type") == "tool_use"
                and block.get("name") != "StructuredOutput"
                and not (web_search and block.get("name") in CLAUDE_WEB_SEARCH_TOOLS)
            )
    return {
        "tool_events": tools,
        "unparsed_event_lines": invalid_lines,
        "cli_notices": notices,
    }


def _codex_output(stdout: str, output_path: Path) -> dict[str, Any]:
    for line in stdout.splitlines():
        if line.strip() and not isinstance(json.loads(line), dict):
            raise ValueError("codex_event_not_object")
    document = json.loads(output_path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("codex_output_not_object")
    return document


def _claude_output(stdout: str) -> dict[str, Any]:
    events = [json.loads(line) for line in stdout.splitlines() if line.strip()]
    if not events or any(not isinstance(event, dict) for event in events):
        raise ValueError("claude_output_not_object")
    results = [
        event for event in events if event.get("type") == "result" or "structured_output" in event
    ]
    if len(results) != 1:
        raise ValueError("claude_result_missing_or_ambiguous")
    wrapper = results[0]
    if wrapper.get("is_error") is True or wrapper.get("subtype", "success") != "success":
        raise ValueError("claude_result_failed")
    document = wrapper.get("structured_output")
    if not isinstance(document, dict):
        raise ValueError("claude_structured_output_missing")
    for event in events:
        if event.get("type") != "assistant":
            continue
        message = event.get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content"), list):
            raise ValueError("claude_assistant_event_invalid")
    return document
