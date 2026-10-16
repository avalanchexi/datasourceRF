"""The site-wide right drawer: a trigger link and the server-rendered panel it opens.

A section renders a trigger and a panel under the same key. The panel is ordinary page
content, built from the selected projection like everything else, and stays hidden;
``assets/drawer.js`` shows one panel at a time as the right drawer while the URL fragment
is ``#drawer-<key>``, so an open drawer is a shareable link and Back closes it. Panels
belong outside cards and other styled containers: a filter or transform on an ancestor
would pin the fixed drawer to that container instead of the viewport.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any, cast

from dash import html

PREFIX = "drawer-"


def drawer_key(*parts: object) -> str:
    """A URL-safe key from parts such as a section, a metric id and its member dimensions."""
    text = "-".join(str(part) for part in parts if part not in (None, ""))
    return re.sub(r"[^A-Za-z0-9_.]+", "-", text).strip("-") or "item"


def drawer_trigger(key: str, children: Any, *, class_name: str = "") -> html.A:
    """A link that opens the panel rendered under ``key``; the whole link is clickable."""
    return html.A(
        children,
        href="#" + PREFIX + key,
        className=" ".join(("drawer-trigger", class_name)).strip(),
        **cast(Any, {"aria-haspopup": "dialog", "aria-controls": PREFIX + key}),
    )


def drawer_panel(key: str, title: str, body: Sequence[Any], *, code: str | None = None) -> html.Div:
    """The hidden drawer content for ``key``: its title, the code when it differs, and body."""
    return html.Div(
        [
            html.Header(
                [
                    html.Div(
                        [
                            html.H2(title, id=PREFIX + key + "-title"),
                            html.Small(code, className="drawer-code")
                            if code and code != title
                            else None,
                        ]
                    ),
                    html.A(
                        "关闭",
                        href="#",
                        className="drawer-close",
                        **cast(Any, {"aria-label": "关闭详情"}),
                    ),
                ],
                className="drawer-header",
            ),
            html.Div(list(body), className="drawer-body"),
        ],
        id=PREFIX + key,
        className="drawer-panel",
        role="dialog",
        hidden=True,
        **cast(Any, {"aria-modal": "true", "aria-labelledby": PREFIX + key + "-title"}),
    )
