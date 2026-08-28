from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, cast

import uvicorn
from dash import Dash, html
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from pring_cycle.logging import write_runtime_event
from pring_cycle.runtime import (
    RuntimeHealthDocument,
    RuntimeNotInitializedError,
    RuntimePaths,
    runtime_health,
)
from pring_cycle.storage import database_health


def create_web_application(paths: RuntimePaths, port: int) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_application: FastAPI) -> AsyncIterator[None]:
        write_runtime_event(paths, "web", "web_started")
        try:
            yield
        finally:
            write_runtime_event(paths, "web", "web_stopped")

    server = FastAPI(
        docs_url=None,
        lifespan=lifespan,
        openapi_url=None,
        redoc_url=None,
        title="Pring local runtime",
    )

    @server.get("/api/v1/health")
    def health() -> RuntimeHealthDocument:
        return runtime_health(paths, port)

    @server.post("/api/v1/commands", response_model=None)
    async def append_command(request: Request) -> JSONResponse:
        trusted_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        trusted_origins = {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}
        if (
            request.headers.get("host") not in trusted_hosts
            or request.headers.get("origin") not in trusted_origins
        ):
            return JSONResponse(
                status_code=403,
                content={
                    "error": "untrusted_local_command_origin",
                    "status": "rejected",
                },
            )
        content_length = request.headers.get("content-length")
        if content_length is not None and int(content_length) > 4096:
            return JSONResponse(
                status_code=413,
                content={"error": "command_body_too_large", "status": "rejected"},
            )
        if len(await request.body()) > 4096:
            return JSONResponse(
                status_code=413,
                content={"error": "command_body_too_large", "status": "rejected"},
            )
        return JSONResponse(
            status_code=501,
            content={"status": "command_append_not_available"},
        )

    dashboard = Dash(
        __name__,
        server=cast(Any, server),
        title="Pring 本机运行状态",
    )
    dashboard.layout = lambda: _health_layout(runtime_health(paths, port))
    return server


def run_web(paths: RuntimePaths, port: int) -> None:
    if database_health(paths.database)["status"] != "ok":
        raise RuntimeNotInitializedError("runtime_not_initialized")
    if not 1 <= port <= 65535:
        raise ValueError("invalid_port")
    uvicorn.run(
        create_web_application(paths, port),
        host="127.0.0.1",
        port=port,
        access_log=False,
        log_level="warning",
    )


def _health_layout(health: RuntimeHealthDocument) -> html.Main:
    service_rows = [
        html.Li(f"Web：{health['services']['web']['status']}"),
        html.Li(f"Worker：{health['services']['worker']['status']}"),
        html.Li(
            f"SQLite / Alembic：{health['database']['status']} / {health['database']['migration']}"
        ),
        html.Li(f"内容寻址制品目录：{health['artifacts']['status']}"),
    ]
    return html.Main(
        [
            html.P("LOCAL RUNTIME", style={"fontSize": "13px"}),
            html.H1("Pring 本机运行状态"),
            html.P("启动不会自动刷新、联网或调用 AI。", style={"fontSize": "16px"}),
            html.Ul(service_rows, style={"fontSize": "16px"}),
        ],
        style={
            "background": "#f4f1e8",
            "color": "#17202a",
            "fontFamily": "sans-serif",
            "margin": "0 auto",
            "maxWidth": "880px",
            "minHeight": "100vh",
            "padding": "48px",
        },
    )
