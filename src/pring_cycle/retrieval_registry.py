"""One registry of what search can reach: each family's hosts, metrics and parser.

A family is a set of metrics one publisher's pages carry, the hosts (and path prefixes)
those pages live on, and the parser that turns a page into claims:

- ``official_context``: the registered NBS/PBC release parser;
- ``lpr``: the China Money LPR announcement parser;
- ``csindex``: the CSI index performance parser for the two CSI cores;
- ``lenient``: the P2 lenient path, which keeps the search channel's own value.

A gap is searchable only when its metric belongs to one of these families. Every other
gap (derived metrics computed from TuShare, NHII) has no web page to search.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlsplit

ParserKind = Literal["official_context", "lpr", "csindex", "lenient"]


@dataclass(frozen=True)
class RetrievalFamily:
    provider: str
    hosts: tuple[tuple[str, str], ...]
    metric_ids: tuple[str, ...]
    parser: ParserKind
    required_p1_rehearsal: bool = True

    @property
    def host(self) -> str:
        return self.hosts[0][0]


_NBS = ("www.stats.gov.cn", "/sj/")
_PBC = ("www.pbc.gov.cn", "/")


def _nbs(*metric_ids: str) -> RetrievalFamily:
    return RetrievalFamily("国家统计局", (_NBS,), metric_ids, "official_context")


def _pbc(*metric_ids: str, required_p1_rehearsal: bool = True) -> RetrievalFamily:
    return RetrievalFamily(
        "中国人民银行",
        (_PBC,),
        metric_ids,
        "official_context",
        required_p1_rehearsal=required_p1_rehearsal,
    )


RETRIEVAL_FAMILIES: dict[str, RetrievalFamily] = {
    "nbs_core_cpi": _nbs("CN_CPI_HEADLINE", "CN_CORE_CPI"),
    "nbs_pmi": _nbs("CN_PMI_ACTIVITY", "CN_PMI_INVENTORY", "CN_PMI_PRICES"),
    "nbs_ppi": _nbs("CN_PPI"),
    "nbs_gdp": _nbs("CN_GDP"),
    "nbs_industrial_value_added": _nbs("CN_INDUSTRIAL_VA"),
    "nbs_industrial_finance": _nbs(
        "CN_INDUSTRIAL_FINANCE", "CN_FINISHED_GOODS_INVENTORY", "CN_INVENTORY_TURNOVER"
    ),
    "nbs_capacity_utilization": _nbs("CN_CAPACITY_UTILIZATION"),
    "pbc_omo_notice": _pbc("CN_OMO_7D_RATE", "CN_OMO_7D_AMOUNT"),
    "pbc_rrr_notice": _pbc("CN_RRR_EVENT"),
    "pbc_tool_liquidity_monthly": _pbc("CN_TOOL_LIQUIDITY_MONTHLY"),
    "pbc_social_financing": _pbc("CN_SF_TOTAL", "CN_SF_COMPONENTS"),
    "pbc_loan_structure": _pbc("CN_LOAN_STRUCTURE"),
    "pbc_money": _pbc("CN_M1_M2"),
    "pbc_usdcny_central_parity": _pbc("CN_USDCNY_CENTRAL_PARITY", required_p1_rehearsal=False),
    "chinamoney_lpr": RetrievalFamily(
        "中国货币网", (("www.chinamoney.com.cn", "/chinese/"),), ("CN_LPR_1Y_5Y",), "lpr"
    ),
    "csindex_core": RetrievalFamily(
        "中证指数",
        (("www.csindex.com.cn", "/"),),
        ("CN_EQUITY_CORE_000985", "CN_BOND_CORE_000012"),
        "csindex",
    ),
    # The P2 lenient path (ticket 20): hosts registered per metric as host and path prefix.
    "chinamoney_usdcny_1630": RetrievalFamily(
        "中国货币网",
        (("www.chinamoney.com.cn", "/chinese/"),),
        ("CN_USDCNY_CLOSE_1630",),
        "lenient",
    ),
    "cboe_vix": RetrievalFamily(
        "Cboe", (("www.cboe.com", "/"), ("cdn.cboe.com", "/")), ("CBOE_VIX_INDEX",), "lenient"
    ),
    "nasdaq_sox": RetrievalFamily(
        "Nasdaq",
        (("www.nasdaq.com", "/"), ("indexes.nasdaqomx.com", "/")),
        ("NASDAQ_SOX_INDEX",),
        "lenient",
    ),
}

RETRIEVAL_FAMILY_BY_METRIC: dict[str, str] = {
    metric_id: name
    for name, family in RETRIEVAL_FAMILIES.items()
    for metric_id in family.metric_ids
}


def families_of(parser: ParserKind) -> dict[str, RetrievalFamily]:
    return {name: family for name, family in RETRIEVAL_FAMILIES.items() if family.parser == parser}


def retrieval_family(metric_id: str) -> RetrievalFamily | None:
    name = RETRIEVAL_FAMILY_BY_METRIC.get(metric_id)
    return None if name is None else RETRIEVAL_FAMILIES[name]


def is_searchable_gap(metric_id: str) -> bool:
    """Whether a web page can carry this metric's value: it belongs to a registered family."""
    return metric_id in RETRIEVAL_FAMILY_BY_METRIC


def parser_for_scope(metric_ids: tuple[str, ...]) -> ParserKind | None:
    """The one parser every metric of a scope shares, if they share one family."""
    names = {RETRIEVAL_FAMILY_BY_METRIC.get(metric_id) for metric_id in metric_ids}
    if len(names) != 1 or None in names:
        return None
    [name] = names
    assert name is not None
    return RETRIEVAL_FAMILIES[name].parser


def registered_host(metric_id: str, url: str) -> str | None:
    """The registered host ``url`` is on for ``metric_id``'s family, or None."""
    family = retrieval_family(metric_id)
    parsed = urlsplit(url)
    if (
        family is None
        or parsed.scheme != "https"
        or parsed.port not in {None, 443}
        or parsed.username
    ):
        return None
    for host, prefix in family.hosts:
        if parsed.hostname == host and parsed.path.startswith(prefix):
            return host
    return None
