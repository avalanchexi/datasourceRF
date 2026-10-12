"""Exact recovery of the frozen core inputs that retention deleted (residual ticket 03).

The three core prices before the evidence window are not kept for the projections that use
them (ADR-0022, ADR-0035, ADR-0040), so some frozen core input ids no longer join a stored
claim. By the user's call of 2026-10-11 (option B) retention stays as it is and the audit
rebuilds each such id from the run's own core receipt: it checks the receipt (artifact hashes,
source identity, cutoff, raw and normalized values agreeing, one claim template), rebuilds the
claim id of every raw row by the documented id rule, and matches it against the frozen ids.
A matched id is verified; an id nothing matches, or that two different values match, is not.

The id rule is written down in ``docs/development/data-quality-audit.md``; production code is
not imported.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field

from common import Run, iso_day, parse_time

SEPARATOR = "\x1f"  # the unit separator joins the parts of an id before hashing


def stable_hash(*parts: str) -> str:
    return hashlib.sha256(SEPARATOR.join(parts).encode()).hexdigest()


@dataclass(frozen=True)
class Template:
    """The fields a receipt's claims share, read from its surviving claims."""

    definition_version: str
    period_kind: str
    dimensions_json: str
    value_state: str
    public_available_at: str | None
    available_at: str  # the batch's ingestion clock, not the receipt's validated_at


def claim_id(metric: str, template: Template, source_reference: str, day: str, close) -> str:
    observation = stable_hash(
        metric,
        template.definition_version,
        template.period_kind,
        day,
        day,
        template.dimensions_json,
    )
    return stable_hash(
        observation,
        "tushare",
        source_reference,
        template.value_state,
        repr(float(close)),
        template.public_available_at or "",
        template.available_at,
    )


@dataclass(frozen=True)
class Recovered:
    metric: str
    day: str
    close: float
    receipt: str


@dataclass
class Recovery:
    """The frozen core ids without a stored claim, and which of them were rebuilt exactly."""

    unresolved: frozenset[str] = frozenset()
    recovered: dict[str, Recovered] = field(default_factory=dict)
    ambiguous: frozenset[str] = frozenset()  # matched by more than one (day, value)
    receipts: dict[str, list[str]] = field(default_factory=dict)  # metric -> receipts that hit
    rejected: list[str] = field(default_factory=list)  # receipts not used, with the reason

    @property
    def missed(self) -> frozenset[str]:
        return self.unresolved - set(self.recovered) - self.ambiguous

    def by_metric(self, metric: str) -> list[Recovered]:
        return sorted(
            (r for r in self.recovered.values() if r.metric == metric), key=lambda r: r.day
        )


def core_receipts(run: Run, metric: str) -> list[str]:
    """The run's own receipts behind the core metric's stored claims."""
    return [
        r[0]
        for r in run.db.execute(
            "SELECT DISTINCT sca.acquisition_id FROM source_claim_acquisition sca"
            " JOIN source_claim s ON s.claim_id = sca.claim_id"
            " JOIN full_run_acquisition f ON f.acquisition_id = sca.acquisition_id"
            " WHERE f.run_id = ? AND s.metric_id = ?",
            (run.run_id, metric),
        )
    ]


def unresolved_ids(run: Run, ids: list[str]) -> frozenset[str]:
    held: set[str] = set()
    for start in range(0, len(ids), 500):
        part = ids[start : start + 500]
        marks = ",".join("?" * len(part))
        held |= {
            r[0]
            for r in run.db.execute(
                f"SELECT claim_id FROM source_claim WHERE claim_id IN ({marks})", part
            )
        }
    return frozenset(ids) - held


def _read(run: Run, content_hash: str | None) -> bytes:
    """An artifact whose content hashes to its name, else ValueError."""
    if not content_hash:
        raise ValueError("没有登记哈希")
    content = run.artifact(content_hash)
    if hashlib.sha256(content).hexdigest() != content_hash:
        raise ValueError(f"制品 {content_hash[:12]}… 的内容与哈希不符")
    return content


def _number(value) -> bool:
    """A finite JSON number (``True`` is an ``int`` in Python, but not a price)."""
    return isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value)


def _by_cutoff(run: Run, moment: str | None) -> bool:
    """Compared as times, not as text: stored offsets need not all be ``+00:00``."""
    return bool(moment) and parse_time(moment) <= parse_time(run.cutoff)


@dataclass(frozen=True)
class _Receipt:
    """One stored request, read here rather than through ``Run.receipts``: that parses every
    receipt's parameters before any check can run."""

    acquisition_id: str
    provider: str
    api_name: str
    parameters_json: str
    state: str
    started_at: str | None
    received_at: str | None
    validated_at: str | None
    raw_hash: str | None
    normalized_hash: str | None

    @property
    def code(self) -> str:
        try:
            parameters = json.loads(self.parameters_json)
        except ValueError:
            raise ValueError("请求参数不是 JSON") from None
        code = parameters.get("ts_code") if isinstance(parameters, dict) else None
        if not isinstance(code, str):
            raise ValueError("请求参数没有 ts_code")
        return code

    def reference(self, day: str) -> str:
        return f"tushare:{self.api_name}:{self.code}:{day}"


def _receipt_rows(run: Run, receipt: _Receipt, metric: str) -> tuple[dict[str, float], Template]:
    """Raw closes by day and the claim template, after every documented check; ValueError
    names the check that failed."""
    if not (
        receipt.raw_hash
        and receipt.state == "validated"
        and _by_cutoff(run, receipt.started_at)
        and _by_cutoff(run, receipt.received_at)
        and _by_cutoff(run, receipt.validated_at)
    ):
        raise ValueError("截止前未取得应答或未通过校验")
    if receipt.provider != "tushare":
        raise ValueError(f"来源为 {receipt.provider}")
    code = receipt.code
    try:
        raw = json.loads(_read(run, receipt.raw_hash))
        fields, items = raw["data"]["fields"], raw["data"]["items"]
        rows = [dict(zip(fields, item, strict=True)) for item in items]
        normalized = json.loads(_read(run, receipt.normalized_hash))
    except OSError:
        raise ValueError("原件不可读") from None
    except (KeyError, TypeError) as error:
        raise ValueError(f"原件结构不对（{type(error).__name__}）") from None
    closes: dict[str, float] = {}
    for row in rows:
        day, close = iso_day(str(row.get("trade_date", ""))), row.get("close")
        if day in closes or not _number(close):
            raise ValueError(f"原始件 {day} 重复或收盘不是有限数")
        closes[day] = float(close)
    if not isinstance(normalized, list):
        raise ValueError("规范化件不是数组")
    seen: dict[str, object] = {}
    for row in normalized:
        if not isinstance(row, dict) or row.get("metric_id") != metric:
            raise ValueError("规范化件中有别的指标")
        if row.get("source_code") != code:
            raise ValueError(f"规范化件来源代码不是 {code}")
        day = str(row.get("business_date"))
        if day in seen:
            raise ValueError(f"规范化件 {day} 重复")
        if not _number(row.get("close")):
            raise ValueError(f"规范化件 {day} 收盘不是有限数")
        seen[day] = row.get("close")
    if set(seen) != set(closes) or any(seen[d] != closes[d] for d in closes):
        raise ValueError("原始件与规范化件的日期或收盘不一致")

    claims = run.db.execute(
        "SELECT s.claim_id, s.definition_version, s.period_kind, s.dimensions_json,"
        " s.value_state, s.public_available_at, s.available_at, s.provider,"
        " s.source_reference, s.period_start, s.period_end, s.value"
        " FROM source_claim_acquisition sca JOIN source_claim s ON s.claim_id = sca.claim_id"
        " WHERE sca.acquisition_id = ? AND s.metric_id = ?",
        (receipt.acquisition_id, metric),
    ).fetchall()
    templates = {Template(*c[1:7]) for c in claims}
    if len(templates) != 1:
        raise ValueError(f"现存声明的模板有 {len(templates)} 组（有歧义）")
    (template,) = templates
    if not _by_cutoff(run, template.available_at):
        raise ValueError("声明入库时间晚于截止")
    for stored, *_, provider, reference, start, end, value in claims:
        if provider != "tushare" or start != end or reference != receipt.reference(end):
            raise ValueError("现存声明的来源身份与回执不符")
        if end not in closes or value != closes[end]:
            raise ValueError(f"现存声明 {end} 的值与原始件收盘不一致")
        if claim_id(metric, template, reference, end, closes[end]) != stored:
            raise ValueError("编号规则未重现现存声明")
    return closes, template


def recover(run: Run, ids: list[str]) -> Recovery:
    """Rebuild the frozen core ids that no longer join a stored claim (see module doc)."""
    unresolved = unresolved_ids(run, ids)
    recovery = Recovery(unresolved=unresolved)
    candidates: dict[str, set[Recovered]] = {}
    for metric in run.manifest["core_metrics"].values():
        receipt_ids = core_receipts(run, metric)
        recovery.receipts[metric] = []
        if not receipt_ids or not unresolved:
            continue
        marks = ",".join("?" * len(receipt_ids))
        for row in run.db.execute(
            "SELECT acquisition_id, provider, api_name, parameters_json, state, started_at,"
            " received_at, validated_at, raw_hash, normalized_hash FROM acquisition_request"
            f" WHERE acquisition_id IN ({marks}) ORDER BY acquisition_id",
            receipt_ids,
        ).fetchall():
            receipt = _Receipt(*row)
            try:
                closes, template = _receipt_rows(run, receipt, metric)
            except ValueError as error:
                recovery.rejected.append(f"{metric} {receipt.acquisition_id}：{error}")
                continue
            except (TypeError, AttributeError, OverflowError) as error:  # malformed stored data
                reason = f"原件或声明的结构不对（{type(error).__name__}）"
                recovery.rejected.append(f"{metric} {receipt.acquisition_id}：{reason}")
                continue
            hits = 0
            for day, close in closes.items():
                found = claim_id(metric, template, receipt.reference(day), day, close)
                if found in unresolved:
                    hit = Recovered(metric, day, close, receipt.acquisition_id)
                    candidates.setdefault(found, set()).add(hit)
                    hits += 1
            if hits:  # only receipts that rebuilt at least one id are listed as used
                recovery.receipts[metric].append(receipt.acquisition_id)
    ambiguous = set()
    for found, hits in candidates.items():
        if len({(h.metric, h.day, h.close) for h in hits}) == 1:
            recovery.recovered[found] = min(hits, key=lambda h: h.receipt)
        else:
            ambiguous.add(found)
    recovery.ambiguous = frozenset(ambiguous)
    return recovery
