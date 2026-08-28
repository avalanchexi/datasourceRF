from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path

from pring_cycle.runtime import (
    RuntimeNotInitializedError,
    RuntimePaths,
    RuntimePolicyError,
    diagnose_runtime,
    initialize_runtime,
)
from pring_cycle.verification import VerificationError, verify_local_runtime


def main(arguments: Sequence[str] | None = None) -> None:
    parser = _parser()
    namespace = parser.parse_args(arguments)
    document: Mapping[str, object]
    try:
        paths = RuntimePaths.discover(namespace.runtime_root)
        if namespace.command == "init":
            document = initialize_runtime(paths)
        elif namespace.command == "doctor":
            document = diagnose_runtime(paths)
        elif namespace.command == "web":
            from pring_cycle.web import run_web

            run_web(paths, namespace.port)
            return
        elif namespace.command == "worker":
            from pring_cycle.worker import run_worker

            run_worker(paths)
            return
        elif namespace.command in {"test", "verify"}:
            document = verify_local_runtime(paths)
        else:
            parser.error("unsupported_command")
    except (RuntimeNotInitializedError, RuntimePolicyError, VerificationError) as error:
        parser.exit(2, f"error: {error}\n")

    _print_document(document, namespace.json)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pring-cycle")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("init", "doctor"):
        command_parser = subparsers.add_parser(command)
        command_parser.add_argument("--runtime-root", type=Path)
        command_parser.add_argument("--json", action="store_true")
    web_parser = subparsers.add_parser("web")
    web_parser.add_argument("--runtime-root", type=Path)
    web_parser.add_argument("--port", type=int, default=8050)
    worker_parser = subparsers.add_parser("worker")
    worker_parser.add_argument("--runtime-root", type=Path)
    for command in ("test", "verify"):
        verify_parser = subparsers.add_parser(command)
        verify_parser.add_argument("--runtime-root", type=Path)
        verify_parser.add_argument("--json", action="store_true")
    return parser


def _print_document(document: Mapping[str, object], as_json: bool) -> None:
    if as_json:
        print(json.dumps(document, ensure_ascii=False, sort_keys=True))
        return
    print(f"status={document['status']}")
    for section, value in document.items():
        if section == "status":
            continue
        if isinstance(value, Mapping):
            print(f"{section}=" + ",".join(f"{key}:{item}" for key, item in value.items()))
        else:
            print(f"{section}={value}")
