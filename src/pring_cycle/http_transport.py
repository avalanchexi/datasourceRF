from __future__ import annotations

from email.message import Message
from typing import Any
from urllib.request import HTTPRedirectHandler, Request, build_opener


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(
        self, req: Request, fp: Any, code: int, msg: str, headers: Message, newurl: str
    ) -> None:
        # A redirect requires another physical request and a new source identity check.
        return None


def open_no_redirects(request: Request, *, timeout: float) -> Any:
    return build_opener(_NoRedirect()).open(request, timeout=timeout)
