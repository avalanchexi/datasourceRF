"""One explicit listener and access boundary for startup, health and commands."""

from __future__ import annotations

import ipaddress
import re
import tomllib
from dataclasses import dataclass
from urllib.parse import urlsplit

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from pring_cycle.runtime import RuntimePaths


class HostBoundary:
    def __init__(self, app: ASGIApp, *, config: WebConfig) -> None:
        self.app = app
        self.config = config

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            host = dict(scope["headers"]).get(b"host", b"").decode("latin-1").lower()
            if host not in self.config.allowed_hosts:
                await JSONResponse(status_code=403, content={"error": "untrusted_host"})(
                    scope, receive, send
                )
                return
        await self.app(scope, receive, send)


@dataclass(frozen=True)
class WebConfig:
    host: str
    port: int
    allowed_hosts: frozenset[str]
    allowed_origins: frozenset[str]

    @classmethod
    def read(cls, paths: RuntimePaths, port: int | None = None) -> WebConfig:
        document = (
            tomllib.loads(paths.config_file.read_text(encoding="utf-8"))
            if paths.config_file.exists()
            else {}
        )
        server = document.get("server", {})
        if not isinstance(server, dict):
            raise ValueError("invalid_server_configuration")
        bind = server.get("host", "127.0.0.1")
        if not isinstance(bind, str) or not _hostname(bind):
            raise ValueError("invalid_bind_host")
        number = server.get("port", 8050) if port is None else port
        if type(number) is not int or not 1 <= number <= 65535:
            raise ValueError("invalid_port")
        hosts = server.get("allowed_hosts", [f"127.0.0.1:{number}", f"localhost:{number}"])
        origins = server.get(
            "allowed_origins", [f"http://127.0.0.1:{number}", f"http://localhost:{number}"]
        )
        if not isinstance(hosts, list) or not hosts or any(not _authority(item) for item in hosts):
            raise ValueError("invalid_allowed_host")
        if (
            not isinstance(origins, list)
            or not origins
            or any(not _origin(item) for item in origins)
        ):
            raise ValueError("invalid_allowed_origin")
        return cls(bind, number, frozenset(item.lower() for item in hosts), frozenset(origins))


def _hostname(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return bool(re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?", value))


def _authority(value: object) -> bool:
    if not isinstance(value, str) or not value or any(char in value for char in "*/\\@?# \t\r\n"):
        return False
    try:
        parsed = urlsplit("http://" + value)
        return bool(
            parsed.hostname
            and _hostname(parsed.hostname)
            and not parsed.path
            and (parsed.port is None or 1 <= parsed.port <= 65535)
        )
    except ValueError:
        return False


def _origin(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = urlsplit(value)
        return (
            parsed.scheme in {"http", "https"}
            and _authority(parsed.netloc)
            and value == f"{parsed.scheme}://{parsed.netloc}"
        )
    except ValueError:
        return False
