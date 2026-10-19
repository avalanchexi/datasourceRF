"""The price verification under the macro judgement (ADR-0043, GLOSSARY: 价格验证).

The day's three cores -- a typical combination and its price stage, or a noncanonical one --
are set against the three assets the main conclusion's stage expects, asset by asset: they
agree, or the assets that do not are named. It changes neither the macro judgement nor the
price stage; the one-asset comparisons of a noncanonical combination are carried with it
as the Worker published them (``noncanonical_basis``), never ranked here.

The block is ``macro_judgement.price_verification``; a correction that states the conclusion
against another last confirmed stage states it again against the stage it then takes.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from itertools import product
from typing import Any

from pring_cycle.domain import CoreAssetState
from pring_cycle.domain.stage import derive_formal_stage

ASSETS = ("bond", "stock", "commodity")
VERDICTS = ("consistent", "deviates", "unavailable")
STATES = tuple(state.value for state in CoreAssetState)


def _typical() -> dict[str, dict[str, str]]:
    """Each stage's typical combination, as the price stage maps one."""
    typical: dict[str, dict[str, str]] = {}
    for states in product(CoreAssetState, repeat=len(ASSETS)):
        stage = derive_formal_stage(
            bond=states[0], stock=states[1], commodity=states[2], last_confirmed_stage=None
        ).current_stage
        if stage is not None:
            typical[stage.value] = {
                asset: state.value for asset, state in zip(ASSETS, states, strict=True)
            }
    return typical


TYPICAL = _typical()


def verification(
    stage: str | None,
    *,
    price_stage: str | None,
    reason: str,
    combination: Mapping[str, str | None],
    comparisons: Sequence[Mapping[str, Any]] = (),
) -> dict[str, object]:
    """The verification of the conclusion's ``stage`` by the day's cores: ``combination`` is
    each core's state, None while unavailable; ``reason`` the price stage's own."""
    expected = TYPICAL.get(str(stage)) if stage is not None else None
    states = {asset: combination.get(asset) for asset in ASSETS}
    deviations = (
        [
            asset
            for asset in ASSETS
            if states[asset] is not None and states[asset] != expected[asset]
        ]
        if expected is not None
        else []
    )
    unread = expected is None or any(state is None for state in states.values())
    return {
        "price_stage": price_stage,
        "reason": reason,
        "combination": states,
        "expected_stage": stage if expected is not None else None,
        "expected": dict(expected) if expected is not None else None,
        "deviations": deviations,
        "verdict": "deviates" if deviations else "unavailable" if unread else "consistent",
        "comparisons": [dict(item) for item in comparisons],
    }


def combination_of(assets: Sequence[Mapping[str, Any]]) -> dict[str, str | None]:
    """Each core's state as the set's core asset documents publish it; None unless read."""
    states = {str(item.get("asset")): item.get("state") for item in assets}
    return {asset: str(states[asset]) if states.get(asset) in STATES else None for asset in ASSETS}


def verified(block: Mapping[str, object], **facts: Any) -> dict[str, object]:
    """``block`` with the verification of its main conclusion by ``facts`` (``verification``'s
    keywords but the stage)."""
    stage = _object(block.get("conclusion")).get("stage")
    return {**block, "price_verification": verification(_text(stage), **facts)}


def restated(block: Mapping[str, object]) -> dict[str, object]:
    """``block``'s verification against the stage its conclusion now takes, its cores and
    price stage as they were; a block without one stays as it is."""
    current = block.get("price_verification")
    if not isinstance(current, Mapping):
        return dict(block)
    return verified(
        block,
        price_stage=current.get("price_stage"),
        reason=str(current.get("reason")),
        combination=_object(current.get("combination")),
        comparisons=_objects(current.get("comparisons")),
    )


def validate(
    block: object,
    *,
    price_stage: object,
    reason: object,
    assets: Sequence[Mapping[str, Any]],
    comparisons: object,
) -> None:
    """A published verification states the set's own cores, price stage and comparisons, and
    sets them against the stage of the judgement's conclusion; a judgement without one (made
    before this ticket's rules) passes."""
    if not isinstance(block, Mapping) or block.get("price_verification") is None:
        return
    stage = _object(block.get("conclusion")).get("stage")
    expected = verification(
        _text(stage),
        price_stage=_text(price_stage),
        reason=str(reason),
        combination=combination_of(assets),
        comparisons=_objects(comparisons),
    )
    if block.get("price_verification") != expected:
        raise ValueError("projection_macro_judgement_invalid")


def _text(value: object) -> str | None:
    return None if value is None else str(value)


def _object(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _objects(value: object) -> list[Mapping[str, Any]]:
    return [item for item in value if isinstance(item, Mapping)] if isinstance(value, list) else []
