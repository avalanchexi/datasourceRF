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
    # How the publisher titles the release, with the period in Chinese (see search_query).
    query_template: str = ""
    # A per-metric title where one family publishes several differently named series.
    metric_queries: tuple[tuple[str, str], ...] = ()
    required_p1_rehearsal: bool = True

    @property
    def host(self) -> str:
        return self.hosts[0][0]


_NBS = ("www.stats.gov.cn", "/sj/")
_PBC = ("www.pbc.gov.cn", "/")


def _nbs(query_template: str, *metric_ids: str) -> RetrievalFamily:
    return RetrievalFamily("国家统计局", (_NBS,), metric_ids, "official_context", query_template)


def _pbc(
    query_template: str, *metric_ids: str, required_p1_rehearsal: bool = True
) -> RetrievalFamily:
    return RetrievalFamily(
        "中国人民银行",
        (_PBC,),
        metric_ids,
        "official_context",
        query_template,
        required_p1_rehearsal=required_p1_rehearsal,
    )


# Query templates follow each publisher's release titles. Placeholders: {year}, {month},
# {day}, {date} (2026年8月27日), {quarter} (二季度), {quarter_title} (二季度和上半年),
# {en_date} (August 27, 2026).
RETRIEVAL_FAMILIES: dict[str, RetrievalFamily] = {
    "nbs_core_cpi": _nbs("{year}年{month}月份居民消费价格", "CN_CPI_HEADLINE", "CN_CORE_CPI"),
    "nbs_pmi": _nbs(
        "{year}年{month}月份中国采购经理指数运行情况",
        "CN_PMI_ACTIVITY",
        "CN_PMI_INVENTORY",
        "CN_PMI_PRICES",
    ),
    "nbs_ppi": _nbs("{year}年{month}月份工业生产者出厂价格", "CN_PPI"),
    "nbs_gdp": _nbs("{year}年{quarter_title}国内生产总值初步核算结果", "CN_GDP"),
    "nbs_industrial_value_added": _nbs("{year}年{month}月份规模以上工业增加值", "CN_INDUSTRIAL_VA"),
    "nbs_industrial_finance": _nbs(
        "{year}年1—{month}月份全国规模以上工业企业利润",
        "CN_INDUSTRIAL_FINANCE",
        "CN_FINISHED_GOODS_INVENTORY",
        "CN_INVENTORY_TURNOVER",
    ),
    "nbs_capacity_utilization": _nbs(
        "{year}年{quarter}全国工业产能利用率", "CN_CAPACITY_UTILIZATION"
    ),
    "pbc_omo_notice": _pbc(
        "公开市场业务交易公告 {date} 7天期逆回购", "CN_OMO_7D_RATE", "CN_OMO_7D_AMOUNT"
    ),
    "pbc_rrr_notice": _pbc(
        "中国人民银行决定下调金融机构存款准备金率 {year}年{month}月", "CN_RRR_EVENT"
    ),
    "pbc_tool_liquidity_monthly": _pbc(
        "{year}年{month}月中央银行各项工具流动性投放情况", "CN_TOOL_LIQUIDITY_MONTHLY"
    ),
    "pbc_social_financing": _pbc(
        "{year}年{month}月社会融资规模增量统计数据报告", "CN_SF_TOTAL", "CN_SF_COMPONENTS"
    ),
    "pbc_loan_structure": _pbc("{year}年{month}月金融统计数据报告 人民币贷款", "CN_LOAN_STRUCTURE"),
    "pbc_money": _pbc("{year}年{month}月金融统计数据报告 M2 M1", "CN_M1_M2"),
    "pbc_usdcny_central_parity": _pbc(
        "{date}人民币汇率中间价公告",
        "CN_USDCNY_CENTRAL_PARITY",
        required_p1_rehearsal=False,
    ),
    "chinamoney_lpr": RetrievalFamily(
        "中国货币网",
        (("www.chinamoney.com.cn", "/chinese/"),),
        ("CN_LPR_1Y_5Y",),
        "lpr",
        "{year}年{month}月贷款市场报价利率（LPR）公告",
    ),
    "csindex_core": RetrievalFamily(
        "中证指数",
        (("www.csindex.com.cn", "/"),),
        ("CN_EQUITY_CORE_000985", "CN_BOND_CORE_000012"),
        "csindex",
        metric_queries=(
            ("CN_EQUITY_CORE_000985", "中证全指 000985 {date} 收盘"),
            ("CN_BOND_CORE_000012", "上证国债指数 000012 {date} 收盘"),
        ),
    ),
    # The P2 lenient path (ticket 20): hosts registered per metric as host and path prefix.
    "chinamoney_usdcny_1630": RetrievalFamily(
        "中国货币网",
        (("www.chinamoney.com.cn", "/chinese/"),),
        ("CN_USDCNY_CLOSE_1630",),
        "lenient",
        "{date} 人民币对美元 16:30 收盘价",
    ),
    "cboe_vix": RetrievalFamily(
        "Cboe",
        (("www.cboe.com", "/"), ("cdn.cboe.com", "/")),
        ("CBOE_VIX_INDEX",),
        "lenient",
        "Cboe VIX index close {en_date}",
    ),
    "nasdaq_sox": RetrievalFamily(
        "Nasdaq",
        (("www.nasdaq.com", "/"), ("indexes.nasdaqomx.com", "/")),
        ("NASDAQ_SOX_INDEX",),
        "lenient",
        "PHLX Semiconductor Index SOX close {en_date}",
    ),
}

# Mainstream financial media a search may land on (ADR-0026). A host matches a domain
# when it is the domain or one of its subdomains. Wind has no public news pages.
MEDIA_WHITELIST: dict[str, tuple[str, ...]] = {
    "财联社": ("cls.cn",),
    "新华网": ("news.cn", "xinhuanet.com"),
    "人民网": ("people.com.cn",),
    "中国政府网": ("www.gov.cn",),
    "中国证券报": ("cs.com.cn",),
    "上海证券报": ("cnstock.com",),
    "证券时报": ("stcn.com",),
    "第一财经": ("yicai.com",),
    "财新": ("caixin.com",),
    "华尔街见闻": ("wallstreetcn.com",),
    "新浪财经": ("finance.sina.com.cn",),
    "东方财富": ("eastmoney.com",),
    "路透": ("reuters.com",),
    "彭博": ("bloomberg.com",),
    "CNBC": ("cnbc.com",),
    "MarketWatch": ("marketwatch.com",),
    "华尔街日报": ("wsj.com",),
    "金融时报": ("ft.com",),
    "雅虎财经": ("finance.yahoo.com",),
    "Investing.com": ("investing.com",),
}
MEDIA_DOMAINS = tuple(domain for domains in MEDIA_WHITELIST.values() for domain in domains)

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


def media_outlet(url: str) -> str | None:
    """The whitelisted outlet ``url`` is published by, or None."""
    parsed = urlsplit(url)
    host = parsed.hostname or ""
    if parsed.scheme != "https" or parsed.port not in {None, 443} or parsed.username:
        return None
    for outlet, domains in MEDIA_WHITELIST.items():
        if any(host == domain or host.endswith("." + domain) for domain in domains):
            return outlet
    return None


def search_domains(metric_ids: tuple[str, ...]) -> tuple[str, ...]:
    """The domains a search for these metrics is limited to: official hosts, then media."""
    official = {
        host
        for metric_id in metric_ids
        if (family := retrieval_family(metric_id)) is not None
        for host, _prefix in family.hosts
    }
    return (*sorted(official), *MEDIA_DOMAINS)


_QUARTERS = ("一季度", "二季度", "三季度", "四季度")
_QUARTER_TITLES = ("一季度", "二季度和上半年", "三季度", "四季度和全年")
_EN_MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


def search_query(metric_ids: tuple[str, ...], period: str) -> str:
    """The query for a gap: its family's release title with the period written in Chinese.

    ``period`` is a day (2026-08-27), a month (2026-08) or a quarter (2026-Q2). A family
    that titles each metric differently gets one title per metric in the scope.
    """
    if not metric_ids:
        raise ValueError("search_metric_ids_required")
    families = {retrieval_family(metric_id) for metric_id in metric_ids}
    if None in families or len(families) != 1:
        raise ValueError("search_family_not_registered")
    [family] = families
    assert family is not None
    per_metric = dict(family.metric_queries)
    templates = dict.fromkeys(per_metric.get(m, family.query_template) for m in metric_ids)
    if not all(templates):
        raise ValueError("search_query_template_missing")
    fields = _period_fields(period)
    return " ".join(template.format(**fields) for template in templates)


def _period_fields(period: str) -> dict[str, str]:
    if "-Q" in period:
        year, quarter = int(period[:4]), int(period[-1])
        month, day = quarter * 3, None
    else:
        parts = period.split("-")
        year, month = int(parts[0]), int(parts[1])
        day = int(parts[2]) if len(parts) == 3 else None
        quarter = (month - 1) // 3 + 1
    return {
        "year": str(year),
        "month": str(month),
        "day": str(day or ""),
        "date": f"{year}年{month}月{day}日" if day else f"{year}年{month}月",
        "quarter": _QUARTERS[quarter - 1],
        "quarter_title": _QUARTER_TITLES[quarter - 1],
        "en_date": (
            f"{_EN_MONTHS[month - 1]} {day}, {year}" if day else f"{_EN_MONTHS[month - 1]} {year}"
        ),
    }
