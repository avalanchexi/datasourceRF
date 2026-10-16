"""Reader-facing domain wording, kept in one place for every page that shows it.

The board, the stage history page and the report page all name core asset states,
30-day candidate directions, asset candidates and formal stages through these
mappings, so the glossary terms change together (GLOSSARY.md).
"""

from __future__ import annotations

UNAVAILABLE = "不可用"
NO_FORMAL_STAGE = "暂无正式阶段"

CORE_STATE_LABELS = {
    "bull": "牛市",
    "bullish": "牛市",
    "bear": "熊市",
    "bearish": "熊市",
}

STAGE_TITLES = {
    "stage_i": "第一阶段 · Stage I",
    "stage_ii": "第二阶段 · Stage II",
    "stage_iii": "第三阶段 · Stage III",
    "stage_iv": "第四阶段 · Stage IV",
    "stage_v": "第五阶段 · Stage V",
    "stage_vi": "第六阶段 · Stage VI",
}


def core_state_label(value: object) -> str:
    """A core asset state, 30-day candidate direction or asset candidate as 牛市 / 熊市."""
    if value is None:
        return UNAVAILABLE
    return CORE_STATE_LABELS.get(str(value).lower(), UNAVAILABLE)


def stage_code(value: object) -> str:
    """A formal stage's short name, as the reason line maps a combination to it."""
    return STAGE_TITLES.get(str(value).lower(), str(value)).rpartition(" · ")[2]


def stage_title(value: object) -> str:
    """A formal stage title; an empty current stage is a result, not a pending judgement."""
    if value is None:
        return NO_FORMAL_STAGE
    return STAGE_TITLES.get(str(value).lower(), str(value))
