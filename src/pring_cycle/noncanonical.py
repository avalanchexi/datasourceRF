"""Verified single-asset comparisons, never a stage estimate or a forecast."""

from __future__ import annotations

from typing import Any

from pring_cycle.domain import CoreAssetState
from pring_cycle.domain.stage import single_asset_differences
from pring_cycle.wording import core_state_label, stage_name

TITLE = "非典型组合解读"
PROMPT_VERSION = "report-prompt-v0010"
_ASSETS = {"bond": "债券", "stock": "股票", "commodity": "商品"}
_STATES = {"bull": core_state_label("bull"), "bear": core_state_label("bear"), None: "无"}


def build_basis(assets: list[dict[str, Any]], last_confirmed_stage: str | None) -> dict[str, Any]:
    by_asset = {item["asset"]: item for item in assets}
    differences = single_asset_differences(
        {asset: CoreAssetState(item["state"]) for asset, item in by_asset.items()}
    )
    return {
        "version": "noncanonical-basis-v1",
        "last_confirmed_stage": last_confirmed_stage,
        "comparisons": [
            {
                "stage": stage.value,
                "asset": asset,
                "current_state": by_asset[asset]["state"],
                "required_state": required.value,
                "candidate_30d": by_asset[asset].get("candidate_30d"),
                "candidate_state": by_asset[asset].get("candidate_state"),
                "candidate_days": by_asset[asset].get("candidate_days", 0),
                "persistence_required": by_asset[asset].get("persistence_required"),
            }
            for stage, asset, required in differences
        ],
    }


def _stage(value: str | None) -> str:
    """A stage in the fixed sentences, named as the prompt asks the prose to (第三阶段)."""
    return stage_name(value) if value else "暂无"


def fact_sentences(basis: dict[str, Any]) -> list[str]:
    sentences = [
        "当前三核心为非典型组合，暂无正式阶段，确认度不适用（来源：三核心价格状态与模型趋势规则）。"
    ]
    for row in basis["comparisons"]:
        name = _ASSETS[row["asset"]]
        candidate = _STATES[row["candidate_state"]]
        duration = f"，已持续 {row['candidate_days']} 日" if row["candidate_state"] else ""
        threshold = row.get("persistence_required")
        persistence = f"，持续确认要求 {threshold} 日" if threshold is not None else ""
        sentences.append(
            f"与{_stage(row['stage'])}只差{name}一项"
            f"（当前{_STATES[row['current_state']]}，该典型组合要求{_STATES[row['required_state']]}；"
            f"30 日候选方向：{_STATES[row['candidate_30d']]}；"
            f"资产候选状态：{candidate}{duration}{persistence}）。"
        )
    sentences.append(f"上一确认阶段：{_stage(basis['last_confirmed_stage'])}，仅作历史上下文。")
    return sentences


def observation_sentences(basis: dict[str, Any]) -> list[str]:
    sentences = []
    for row in basis["comparisons"]:
        name = _ASSETS[row["asset"]]
        if row["candidate_30d"] == row["required_state"]:
            direction = "已指向上述差异所需方向"
        elif row["candidate_30d"] is None:
            direction = "尚无方向"
        else:
            direction = "尚未指向上述差异所需方向"
        sentences.append(
            f"观察{name}：30 日候选{direction}，继续观察资产候选状态及其持续确认条件，"
            "候选信号不等于稳定状态切换，也不预测下一阶段。"
        )
    return sentences


def fallback_section(basis: dict[str, Any]) -> dict[str, str]:
    return {"title": TITLE, "explanation": "".join(fact_sentences(basis))}


# Restrict factual prose to worker-supplied sentences. Token checks cannot establish
# equivalence (e.g. a negation before an otherwise exact fact changes its meaning).
# AI selects/reorders the applicable observation sentences; no free factual additions.
def reading_error(basis: dict[str, Any], section: dict[str, Any]) -> str | None:
    text = section["explanation"]
    facts = "".join(fact_sentences(basis))
    if not text.startswith(facts):
        return "noncanonical_facts"
    remaining = text[len(facts) :].strip()
    observations = observation_sentences(basis)
    found = False
    while remaining:
        sentence = next((item for item in observations if remaining.startswith(item)), None)
        if sentence is None:
            return "noncanonical_unverified_claim"
        found = True
        observations.remove(sentence)
        remaining = remaining[len(sentence) :].strip()
    return None if found else "noncanonical_observation_missing"
