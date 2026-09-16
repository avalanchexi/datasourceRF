"""One consistent read of captured evidence shared by nested computations.

Inside ``shared_read_scope`` callers may reuse results that depend only on inputs nothing inside
the scope captures or alters: the reviewed futures inputs (only their reviewed import captures
them) and a stored claim's own immutable parent originals. A replay and one Worker run qualify;
a Worker run does capture other evidence, so a cached result must never depend on it. Outside a
scope every caller reads and verifies again.
"""

from __future__ import annotations

from collections.abc import Callable, Hashable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

_SCOPE: ContextVar[dict[str, dict[Any, Any]] | None] = ContextVar("shared_read_scope", default=None)


@contextmanager
def shared_read_scope() -> Iterator[None]:
    if _SCOPE.get() is not None:
        yield
        return
    token = _SCOPE.set({})
    try:
        yield
    finally:
        _SCOPE.reset(token)


def scope_cache(name: str) -> dict[Any, Any] | None:
    """The named cache of the active scope, or None when no consistent read is shared."""
    scope = _SCOPE.get()
    return None if scope is None else scope.setdefault(name, {})


def claims_checked_once(
    name: str,
    context: tuple[Hashable, ...],
    claim_ids: set[str],
    check: Callable[[set[str]], set[str]],
) -> set[str]:
    """The valid subset of ``claim_ids``; inside a scope each claim is checked once per context.

    ``context`` must name everything the check reads besides the claim itself.
    """
    shared = scope_cache(name)
    if shared is None:
        return check(claim_ids)
    known = {claim_id for claim_id in claim_ids if (*context, claim_id) in shared}
    remaining = claim_ids - known
    fresh = check(remaining) if remaining else set()
    shared.update({(*context, claim_id): claim_id in fresh for claim_id in remaining})
    return {claim_id for claim_id in known if shared[(*context, claim_id)]} | fresh
