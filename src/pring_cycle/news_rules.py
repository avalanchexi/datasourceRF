"""News extraction rules: which sentences of a news or media text may give a P1/P2 value.

Each registered family lists one rule per metric and dimension member (ADR-0026). A rule
only recognizes the publisher's own wording, for example "2026年8月份，全国居民消费价格
同比上涨0.8%"; any other number in the text is never taken. A value is adopted only when
its sentence names the gap's due period. The sentence it came from is kept as the
matched quote, with the title, source, publication time and a hash of the text, for as
long as the value itself is kept.

Rules are written against real texts (tests/fixtures/news). A family whose members are
not all stated in the text (PPI's cumulative component averages appear only in the
official table) cannot be completed from the news; its values still land, and the model
input stays incomplete until another route fills the rest.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import sqlite3
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from pring_cycle.evidence import MetricSeriesPoint

NEWS_RULES_VERSION = "news-rules-v0001"
RULE_NOT_MATCHED = "rule_not_matched"
PERIOD_MISMATCH = "period_mismatch"
# How a value came from a text, recorded with its matched quote.
MEDIA_PAGE = "media_page"
TUSHARE_NEWS = "tushare_news"
AI_WEBSEARCH = "ai_websearch"
MEDIA_PAGE_API = "media_page_get"

_VALUE = r"(?:(?P<dir>上涨|下降|增长|回落)(?P<value>\d+(?:\.\d+)?)%|(?P<flat>持平))"
_MONTH = r"(?:(?P<year>\d{4})年)?(?P<month>\d{1,2})月份?"
_YEAR_TO_MONTH = r"(?:(?P<year>\d{4})年)?1[—–\-－~至](?P<month>\d{1,2})月份?平均"
_SEP = r"[，,]\s*"
_NUM = r"(?P<value>\d+(?:\.\d+)?)"
_PCT = _NUM + "%"
_AMOUNT = _NUM + r"(?P<unit>万亿元|亿元)"
_CHANGE = r"(?P<dir>增加|减少)"
_GROWTH = r"(?P<dir>增长|下降)"
_OTHER = r"\d+(?:\.\d+)?%"
# Words that make a stated change negative.
_NEGATIVE = frozenset({"下降", "回落", "减少"})

# How a sentence names its period, and what each wording stands for. A sentence without
# one takes the nearest wording before it (the paragraph's "8月份，" or "前八个月").
Form = Literal["day", "month", "year_to_month", "quarter", "year_to_quarter"]
_CHINESE = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6}
_CHINESE.update({"七": 7, "八": 8, "九": 9, "十": 10, "十一": 11, "十二": 12})
_MENTION = re.compile(
    r"(?:(?P<year>\d{4})年)?(?:"
    r"(?P<dm>\d{1,2})月(?P<dd>\d{1,2})日"
    r"|1[—–\-－~至](?P<ytd>\d{1,2})月份?"
    r"|前(?P<ytdn>\d{1,2}|十[一二]?|[一二三四五六七八九])个?月"
    r"|(?P<half>上半年)"
    r"|前(?P<q3>三)季度"
    r"|(?P<fy>全年)"
    r"|(?P<q>[一二三四])季度"
    r"|(?P<m>\d{1,2})月(?:份|末)?"
    r")"
)
_CONTEXT_CHARS = 600


def _mention_keys(match: re.Match[str]) -> dict[Form, tuple[int, ...]]:
    """Each period form a wording can stand for, with its key (day, month or quarter)."""
    if match["dm"]:
        return {"day": (int(match["dm"]), int(match["dd"]))}
    if match["ytd"] or match["ytdn"]:
        count = match["ytd"] or match["ytdn"]
        return {"year_to_month": (int(count) if count.isdigit() else _CHINESE[count],)}
    if match["half"]:
        return {"year_to_month": (6,), "year_to_quarter": (2,)}
    if match["q3"]:
        return {"year_to_month": (9,), "year_to_quarter": (3,)}
    if match["fy"]:
        return {"year_to_month": (12,), "year_to_quarter": (4,)}
    if match["q"]:
        quarter = _CHINESE[match["q"]]
        keys: dict[Form, tuple[int, ...]] = {"quarter": (quarter,)}
        if quarter == 1:
            keys["year_to_quarter"] = (1,)
        return keys
    return {"month": (int(match["m"]),)}


def _wanted(period: str, form: Form) -> tuple[int, ...]:
    """The key a gap's period gives a form (day and month compare by day or month)."""
    if "-Q" in period:
        return (int(period[-1]),) if form in {"quarter", "year_to_quarter"} else ()
    month = int(period[5:7])
    if form == "day":
        return (month, int(period[8:10])) if len(period) == 10 else (month,)
    if form in {"month", "year_to_month"}:
        return (month,)
    return ((month - 1) // 3 + 1,) if month % 3 == 0 else ()


@dataclass(frozen=True)
class NewsRule:
    metric_id: str
    dimensions: tuple[tuple[str, str], ...]
    pattern: re.Pattern[str]
    # The period forms the value may carry: its own wording or the nearest one before it.
    forms: tuple[Form, ...] = ("month",)
    # The sentence must contain this (e.g. "分季度看" for per-quarter growth).
    sentence_must: str | None = None
    # The value must sit under the first heading, not the second (manufacturing PMI).
    section: tuple[str, str] | None = None


def _rule(
    metric_id: str,
    dimensions: dict[str, str],
    pattern: str,
    forms: tuple[Form, ...] = ("month",),
    *,
    sentence_must: str | None = None,
    section: tuple[str, str] | None = None,
) -> NewsRule:
    return NewsRule(
        metric_id,
        tuple(sorted(dimensions.items())),
        re.compile(pattern),
        forms,
        sentence_must,
        section,
    )


def _cpi(measure: str, pattern: str, form: Form = "month") -> NewsRule:
    return _rule("CN_CPI_HEADLINE", {"category": "headline", "measure": measure}, pattern, (form,))


def _core(measure: str, pattern: str, form: Form = "month") -> NewsRule:
    return _rule(
        "CN_CORE_CPI", {"category": "ex_food_energy", "measure": measure}, pattern, (form,)
    )


def _ppi(category: str, measure: str, pattern: str) -> NewsRule:
    return _rule("CN_PPI", {"category": category, "measure": measure}, pattern)


def _pmi(metric_id: str, series: str, pattern: str) -> NewsRule:
    # Manufacturing only: non-manufacturing indices share some names (新订单指数).
    manufacturing = (r"(?<!非)制造业", r"非制造业")
    member = {"series": series, "measure": "level"}
    return _rule(metric_id, member, pattern, section=manufacturing)


def _sf(component: str, name: str) -> tuple[NewsRule, ...]:
    member = {"component": component}
    return (
        _rule(
            "CN_SF_COMPONENTS",
            {**member, "measure": "stock_end"},
            name + "余额" + _AMOUNT,
        ),
        _rule(
            "CN_SF_COMPONENTS",
            {**member, "measure": "stock_yoy"},
            name + r"余额\d+(?:\.\d+)?(?:万亿元|亿元)" + _SEP + "同比" + _GROWTH + _PCT,
        ),
    )


def _loan(borrower: str, tenor: str, pattern: str) -> NewsRule:
    return _rule(
        "CN_LOAN_STRUCTURE",
        {"borrower": borrower, "tenor": tenor, "measure": "ytd_increment"},
        pattern,
        ("year_to_month",),
    )


_PPI_PRICES_IN = _MONTH + _SEP + "工业生产者出厂价格中" + _SEP
_CORE_YOY = r"核心CPI同比(?:(?P<dir>上涨|下降)|涨幅(?:回升|扩大|回落|收窄)?(?:至|为))" + _PCT
_ENTERPRISE = r"企[（(]事[）)]业单位贷款"
_HOUSEHOLD = r"住户贷款"
_OPENING = r"(?:增加|减少)[\d.]+(?:万亿元|亿元)" + _SEP + "其中" + r"[，,]?\s*"

NEWS_RULES: dict[str, tuple[NewsRule, ...]] = {
    "nbs_core_cpi": (
        _cpi("yoy", _MONTH + _SEP + "全国居民消费价格同比" + _VALUE),
        _cpi("mom", _MONTH + _SEP + "全国居民消费价格环比" + _VALUE),
        _cpi(
            "cumulative_average_yoy",
            _YEAR_TO_MONTH + _SEP + "全国居民消费价格比上年同期" + _VALUE,
            "year_to_month",
        ),
        # Core CPI's month-on-month change is not stated in the news (only in the table).
        _core("yoy", _CORE_YOY),
        _core("cumulative_average_yoy", _CORE_YOY, "year_to_month"),
    ),
    "nbs_ppi": (
        _ppi("headline", "yoy", _MONTH + _SEP + "全国工业生产者出厂价格同比" + _VALUE),
        _ppi(
            "headline",
            "mom",
            _MONTH + _SEP + "全国工业生产者出厂价格同比[^，,。]*" + _SEP + "环比" + _VALUE,
        ),
        _ppi(
            "headline",
            "cumulative_average_yoy",
            _YEAR_TO_MONTH + _SEP + "工业生产者出厂价格比上年同期" + _VALUE,
        ),
        _ppi("means_of_production", "yoy", _PPI_PRICES_IN + "生产资料价格同比" + _VALUE),
        _ppi("means_of_production", "mom", _PPI_PRICES_IN + "生产资料价格环比" + _VALUE),
        # The consumer-goods figure is the first "生活资料价格" sentence after the
        # producer-goods one, in the same paragraph (a breakdown may come between).
        _ppi(
            "consumer_goods",
            "yoy",
            _PPI_PRICES_IN + "生产资料价格同比[^\\n]*?。\\s*生活资料价格" + _VALUE,
        ),
        _ppi(
            "consumer_goods",
            "mom",
            _PPI_PRICES_IN + "生产资料价格环比[^\\n]*?。\\s*生活资料价格" + _VALUE,
        ),
    ),
    # The finished-goods inventory index is not stated in the news.
    "nbs_pmi": (
        _pmi(
            "CN_PMI_ACTIVITY",
            "manufacturing",
            r"制造业(?:采购经理指数(?:[（(]PMI[）)])?|PMI)(?:为|升至|降至|回升至|回落至)" + _PCT,
        ),
        _pmi("CN_PMI_ACTIVITY", "production", r"(?<!产出指数的制造业)生产指数为" + _PCT),
        _pmi(
            "CN_PMI_ACTIVITY",
            "production",
            r"生产指数和新订单指数分别(?:为|升至)" + _PCT + "和" + _OTHER,
        ),
        _pmi("CN_PMI_ACTIVITY", "new_orders", r"新订单指数为" + _PCT),
        _pmi(
            "CN_PMI_ACTIVITY",
            "new_orders",
            r"生产指数和新订单指数分别(?:为|升至)" + _OTHER + "和" + _PCT,
        ),
        _pmi("CN_PMI_ACTIVITY", "purchase_volume", r"采购量指数为" + _PCT),
        _pmi("CN_PMI_INVENTORY", "raw_materials", r"原材料库存指数为" + _PCT),
        _pmi(
            "CN_PMI_PRICES",
            "purchase_prices",
            r"主要原材料购进价格指数和出厂价格指数分别(?:为|升至|降至)" + _PCT + "和" + _OTHER,
        ),
        _pmi(
            "CN_PMI_PRICES",
            "output_prices",
            r"主要原材料购进价格指数和出厂价格指数分别(?:为|升至|降至)" + _OTHER + "和" + _PCT,
        ),
    ),
    "nbs_industrial_value_added": (
        _rule(
            "CN_INDUSTRIAL_VA",
            {"measure": "current_month_real_yoy"},
            r"规模以上工业增加值同比(?:实际)?" + _GROWTH + _PCT,
        ),
        _rule(
            "CN_INDUSTRIAL_VA",
            {"measure": "ytd_real_yoy"},
            r"规模以上工业增加值同比(?:实际)?" + _GROWTH + _PCT,
            ("year_to_month",),
        ),
        # "从环比看，8月份，规模以上工业增加值比上月增长0.54%": the NBS seasonally
        # adjusted month-on-month rate, the only one it publishes.
        _rule(
            "CN_INDUSTRIAL_VA",
            {"measure": "mom_seasonally_adjusted"},
            r"规模以上工业增加值比上月" + _GROWTH + _PCT,
        ),
    ),
    "nbs_industrial_finance": (
        *(
            rule
            for item, pattern in (
                ("revenue", r"规模以上工业企业实现营业收入" + _AMOUNT + _SEP + "同比" + _GROWTH),
                ("cost", r"发生营业成本" + _AMOUNT + _SEP + _GROWTH),
                (
                    "profit",
                    r"全国规模以上工业企业实现利润总额" + _AMOUNT + _SEP + "同比" + _GROWTH,
                ),
            )
            for rule in (
                _rule(
                    "CN_INDUSTRIAL_FINANCE",
                    {"item": item, "measure": "ytd_level"},
                    pattern.replace("(?P<dir>增长|下降)", "(?:增长|下降)"),
                    ("year_to_month",),
                ),
                _rule(
                    "CN_INDUSTRIAL_FINANCE",
                    {"item": item, "measure": "official_yoy"},
                    pattern.replace("(?P<value>", "(?:").replace("(?P<unit>", "(?:") + _PCT,
                    ("year_to_month",),
                ),
            )
        ),
        _rule(
            "CN_FINISHED_GOODS_INVENTORY",
            {"measure": "nominal_end_level"},
            r"产成品存货" + _AMOUNT + _SEP + r"(?:增长|下降)",
        ),
        _rule(
            "CN_FINISHED_GOODS_INVENTORY",
            {"measure": "official_yoy"},
            r"产成品存货\d+(?:\.\d+)?(?:万亿元|亿元)" + _SEP + _GROWTH + _PCT,
        ),
        _rule(
            "CN_INVENTORY_TURNOVER",
            {"measure": "days"},
            r"产成品存货周转天数为" + _NUM + "天",
            ("year_to_month", "month"),
        ),
        _rule(
            "CN_INVENTORY_TURNOVER",
            {"measure": "official_yoy_change"},
            r"产成品存货周转天数为\d+(?:\.\d+)?天" + _SEP + "同比" + _CHANGE + _NUM + "天",
            ("year_to_month", "month"),
        ),
    ),
    # The cumulative rate for the year is not stated in the news.
    "nbs_capacity_utilization": (
        _rule(
            "CN_CAPACITY_UTILIZATION",
            {"industry": "all_industry", "measure": "quarter_rate"},
            r"全国规模以上工业产能利用率为" + _PCT,
            ("quarter",),
        ),
        _rule(
            "CN_CAPACITY_UTILIZATION",
            {"industry": "all_industry", "measure": "yoy_change"},
            r"全国规模以上工业产能利用率为" + _OTHER + r"[^。]*?比上年同期"
            r"(?P<dir>上升|下降|提高)" + _NUM + "个百分点",
            ("quarter",),
        ),
    ),
    # Each industry's quarterly growth is not stated in the news (only its year to date).
    "nbs_gdp": (
        _rule(
            "CN_GDP",
            {"aggregate": "total", "measure": "nominal_ytd_level"},
            r"国内生产总值(?:[（(]GDP[）)])?" + _AMOUNT,
            ("year_to_quarter",),
        ),
        *(
            _rule(
                "CN_GDP",
                {"aggregate": aggregate, "measure": "nominal_ytd_level"},
                name + "增加值" + _AMOUNT,
                ("year_to_quarter",),
            )
            for aggregate, name in (
                ("primary", "第一产业"),
                ("secondary", "第二产业"),
                ("tertiary", "第三产业"),
            )
        ),
        _rule(
            "CN_GDP",
            {"aggregate": "total", "measure": "real_quarter_yoy"},
            r"(?P<q>[一二三四])季度(?:国内生产总值同比)?增长" + _PCT,
            ("quarter",),
            sentence_must="分季度看",
        ),
    ),
    "pbc_social_financing": (
        _rule(
            "CN_SF_TOTAL",
            {"measure": "ytd_increment"},
            r"社会融资规模增量累计为" + _AMOUNT,
            ("year_to_month",),
        ),
        _rule("CN_SF_TOTAL", {"measure": "stock_end"}, r"社会融资规模存量为" + _AMOUNT),
        *_sf("renminbi_loans", r"对实体经济发放的人民币贷款"),
        *_sf("foreign_currency_loans_rmb", r"对实体经济发放的外币贷款折合人民币"),
        *_sf("entrusted_loans", r"委托贷款"),
        *_sf("trust_loans", r"信托贷款"),
        *_sf("undiscounted_bank_acceptances", r"未贴现的银行承兑汇票"),
        *_sf("corporate_bonds", r"(?<!非金融)企业债券"),
        *_sf("government_bonds", r"政府债券"),
        *_sf("nonfinancial_enterprise_equity", r"非金融企业境内股票"),
        *(
            _rule(
                "CN_SF_COMPONENTS",
                {"component": component, "measure": "ytd_increment"},
                pattern,
                ("year_to_month",),
            )
            for component, pattern in (
                ("renminbi_loans", r"对实体经济发放的人民币贷款" + _CHANGE + _AMOUNT),
                (
                    "foreign_currency_loans_rmb",
                    r"对实体经济发放的外币贷款折合人民币" + _CHANGE + _AMOUNT,
                ),
                ("entrusted_loans", r"委托贷款" + _CHANGE + _AMOUNT),
                ("trust_loans", r"信托贷款" + _CHANGE + _AMOUNT),
                ("undiscounted_bank_acceptances", r"未贴现的银行承兑汇票" + _CHANGE + _AMOUNT),
                ("corporate_bonds", r"(?<!非金融)企业债券净融资" + _AMOUNT),
                ("government_bonds", r"政府债券净融资" + _AMOUNT),
                ("nonfinancial_enterprise_equity", r"非金融企业境内股票融资" + _AMOUNT),
            )
        ),
    ),
    "pbc_loan_structure": (
        _loan("household", "total", _HOUSEHOLD + _CHANGE + _AMOUNT),
        _loan("household", "short_term", _HOUSEHOLD + _OPENING + "短期贷款" + _CHANGE + _AMOUNT),
        _loan("household", "long_term", _HOUSEHOLD + r"[^；;。]*?中长期贷款" + _CHANGE + _AMOUNT),
        _loan("enterprise", "total", _ENTERPRISE + _CHANGE + _AMOUNT),
        _loan("enterprise", "short_term", _ENTERPRISE + _OPENING + "短期贷款" + _CHANGE + _AMOUNT),
        _loan("enterprise", "long_term", _ENTERPRISE + r"[^；;。]*?中长期贷款" + _CHANGE + _AMOUNT),
        _loan(
            "enterprise", "bill_financing", _ENTERPRISE + r"[^；;。]*?票据融资" + _CHANGE + _AMOUNT
        ),
        _loan("nonbank_financial", "total", r"非银行业金融机构贷款" + _CHANGE + _AMOUNT),
        # All RMB loans, not the social-financing measure "对实体经济发放的人民币贷款".
        _loan("all_rmb_loans", "total", r"(?<!对实体经济发放的)人民币贷款" + _CHANGE + _AMOUNT),
    ),
    "pbc_money": tuple(
        rule
        for aggregate, name in (("m2", r"广义货币[（(]M2[）)]"), ("m1", r"狭义货币[（(]M1[）)]"))
        for rule in (
            _rule(
                "CN_M1_M2", {"aggregate": aggregate, "measure": "balance"}, name + "余额" + _AMOUNT
            ),
            _rule(
                "CN_M1_M2",
                {"aggregate": aggregate, "measure": "yoy"},
                name + r"余额\d+(?:\.\d+)?(?:万亿元|亿元)\s*[，,]\s*同比" + _GROWTH + _PCT,
            ),
        )
    ),
    "chinamoney_lpr": (
        _rule(
            "CN_LPR_1Y_5Y",
            {"tenor": "1y"},
            r"1年期(?:LPR|贷款市场报价利率[（(]LPR[）)])为" + _PCT,
            ("day", "month"),
        ),
        _rule(
            "CN_LPR_1Y_5Y",
            {"tenor": "5y_plus"},
            r"5年期以上(?:LPR|贷款市场报价利率[（(]LPR[）)])为" + _PCT,
            ("day", "month"),
        ),
    ),
    # The date must be written: "今日开展" alone does not say which day.
    "pbc_omo_notice": (
        _rule(
            "CN_OMO_7D_AMOUNT",
            {"measure": "injection"},
            r"开展了?" + _NUM + r"(?P<unit>亿元)7天期?逆回购操作",
            ("day",),
        ),
        _rule(
            "CN_OMO_7D_RATE",
            {},
            r"7天期?逆回购操作[^。]*?操作利率(?:为)?" + _PCT,
            ("day",),
        ),
    ),
    "pbc_usdcny_central_parity": (
        _rule(
            "CN_USDCNY_CENTRAL_PARITY",
            {"currency_pair": "USD/CNY", "quote_direction": "CNY per USD"},
            r"人民币汇率中间价为[：:]?\s*1美元对人民币" + _NUM + "元",
            ("day",),
        ),
    ),
}
NEWS_RULE_METRICS = frozenset(rule.metric_id for rules in NEWS_RULES.values() for rule in rules)


@dataclass(frozen=True)
class NewsValue:
    metric_id: str
    dimensions: dict[str, str]
    # In the member's unit, a decrease negative; ``stated`` is the number as written.
    value: float
    quote: str
    stated: float = 0.0


@dataclass(frozen=True)
class NewsExtraction:
    values: tuple[NewsValue, ...]
    # Why nothing was taken: the rules found no sentence, or only another period's.
    reason: str | None


def rules_for(metric_ids: tuple[str, ...]) -> tuple[NewsRule, ...]:
    wanted = set(metric_ids)
    return tuple(
        rule for rules in NEWS_RULES.values() for rule in rules if rule.metric_id in wanted
    )


def rules_cover(metric_ids: tuple[str, ...], period: str) -> bool:
    """Whether the rules can state every member the catalog requires of these metrics.

    Only then can a text complete the model input; AI WebSearch is asked only for those.
    """
    from pring_cycle.metric_contracts import required_dimension_members

    covered = {(rule.metric_id, rule.dimensions) for rule in rules_for(metric_ids)}
    for metric_id in metric_ids:
        members = required_dimension_members(
            metric_id, definition_version="registered", period=period
        )
        if members is None:
            # The parser names the one member (central parity): any rule states it.
            if not any(metric == metric_id for metric, _dimensions in covered):
                return False
        elif not all((metric_id, tuple(sorted(member.items()))) in covered for member in members):
            return False
    return True


def plain_text(content: str) -> str:
    """Readable text of an HTML or plain body: one line per paragraph, entities decoded."""
    text = re.sub(r"(?is)<(script|style)\b.*?</\1>", "", content)
    text = re.sub(r"(?i)</(p|div|h\d|li|tr)>|<br\s*/?>", "\n", text)
    text = html.unescape(re.sub(r"<[^>]+>", "", text))
    text = text.replace("　", " ").replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def extract(
    metric_ids: tuple[str, ...], period: str, text: str, *, recheck: bool = False
) -> NewsExtraction:
    """The values the registered rules state for ``period`` in ``text``.

    ``period`` is the gap's: a day (2026-09-21), a month (2026-08) or a quarter (2026-Q2).
    A value's period is the wording inside its match, else the nearest one before it; a
    rule takes the value only when that wording is of its form (so "1—8月份" is never read
    as August) and names the gap's period. A member stated twice with different values is
    not taken: the text contradicts itself. ``recheck`` re-reads a kept quote, whose
    heading context was checked when it was first taken.
    """
    year = int(period[:4])
    found: dict[tuple[str, tuple[tuple[str, str], ...]], list[NewsValue]] = {}
    other_period = False
    for rule in rules_for(metric_ids):
        for match in rule.pattern.finditer(text):
            placed = _place(rule, match, text)
            if placed is None:
                continue
            (form, key, stated_year), context = placed
            # Compared as far as both go: "8月" answers a day of August, and a fixing's
            # "9月20日" answers September's (the LPR's gap is its month).
            wanted = _wanted(period, form)
            common = min(len(key), len(wanted))
            if (
                not wanted
                or key[:common] != wanted[:common]
                or (stated_year and stated_year != year)
            ):
                other_period = True
                continue
            sentence = _sentence(text, match)
            if rule.sentence_must and rule.sentence_must not in sentence:
                continue
            if rule.section and not recheck and not _in_section(text, match.start(), rule.section):
                continue
            stated = 0.0 if match.groupdict().get("flat") else float(match["value"])
            value = stated
            if match.groupdict().get("dir") in _NEGATIVE:
                value = -value
            unit = match.groupdict().get("unit")
            if unit == "万亿元":
                value = round(value * 10_000, 6)
            quote = sentence if context is None or context in sentence else f"{context}，{sentence}"
            found.setdefault((rule.metric_id, rule.dimensions), []).append(
                NewsValue(rule.metric_id, dict(rule.dimensions), value, quote, stated)
            )
    values = tuple(items[0] for items in found.values() if len({i.value for i in items}) == 1)
    if values:
        return NewsExtraction(values, None)
    return NewsExtraction((), PERIOD_MISMATCH if other_period else RULE_NOT_MATCHED)


def _place(
    rule: NewsRule, match: re.Match[str], text: str
) -> tuple[tuple[Form, tuple[int, ...], int | None], str | None] | None:
    """The period a match states: in its own words, else the nearest wording before it."""
    groups = match.groupdict()
    stated_year = int(groups["year"]) if groups.get("year") else None
    if groups.get("month"):
        return (rule.forms[0], (int(groups["month"]),), stated_year), None
    if groups.get("q"):
        return (rule.forms[0], (_CHINESE[groups["q"]],), stated_year), None
    window = text[max(0, match.start() - _CONTEXT_CHARS) : match.start()]
    mentions = list(_MENTION.finditer(window))
    if not mentions:
        return None
    nearest = mentions[-1]
    keys = _mention_keys(nearest)
    form = next((form for form in rule.forms if form in keys), None)
    if form is None:
        return None
    year = int(nearest["year"]) if nearest["year"] else None
    return (form, keys[form], year), nearest.group(0)


def _in_section(text: str, at: int, section: tuple[str, str]) -> bool:
    before = text[max(0, at - 3 * _CONTEXT_CHARS) : at]
    good = [m.end() for m in re.finditer(section[0], before)]
    bad = [m.end() for m in re.finditer(section[1], before)]
    return bool(good) and (not bad or good[-1] > bad[-1])


def _sentence(text: str, match: re.Match[str]) -> str:
    """The whole sentence(s) the rule matched: a recheck runs the same rule on it again."""
    start = max(text.rfind(mark, 0, match.start()) for mark in "。；\n") + 1
    ends = [position for mark in "。；\n" if (position := text.find(mark, match.end())) >= 0]
    return text[start : min(ends) + 1 if ends else len(text)].strip()


def page_title(content: str) -> str:
    match = re.search(r"(?is)<title[^>]*>(.*?)</title>", content)
    return plain_text(match.group(1)) if match else ""


_PUBLISHED_META = (
    r"(?i)<meta[^>]+(?:property|name)=[\"'](?:article:published_time|pubdate|publishdate|"
    r"publish_time|og:release_date)[\"'][^>]+content=[\"']([^\"']+)"
)
_PUBLISHED_STAMP = r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})日?\s+(\d{1,2}):(\d{2})"


def page_published_at(content: str) -> str | None:
    """The page's own publication time as written (a meta tag, else the first timestamp)."""
    meta = re.search(_PUBLISHED_META, content)
    if meta:
        return meta.group(1).strip()
    stamp = re.search(_PUBLISHED_STAMP, plain_text(content))
    if stamp:
        year, month, day, hour, minute = stamp.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}T{int(hour):02d}:{minute}:00+08:00"
    return None


def parse_published_at(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


MATCHED_QUOTE_SCHEMA = """
CREATE TABLE IF NOT EXISTS claim_matched_quote (
    claim_id TEXT PRIMARY KEY REFERENCES source_claim(claim_id),
    route TEXT NOT NULL,
    quote TEXT NOT NULL,
    title TEXT NOT NULL,
    source_name TEXT NOT NULL,
    published_at TEXT,
    body_hash TEXT NOT NULL,
    url TEXT,
    rules_version TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class MatchedQuote:
    claim_id: str
    route: str
    quote: str
    title: str
    source_name: str
    published_at: str | None
    body_hash: str
    url: str | None


def record_matched_quotes(connection: sqlite3.Connection, quotes: tuple[MatchedQuote, ...]) -> None:
    connection.executemany(
        "INSERT OR IGNORE INTO claim_matched_quote VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                q.claim_id,
                q.route,
                q.quote,
                q.title,
                q.source_name,
                q.published_at,
                q.body_hash,
                q.url,
                NEWS_RULES_VERSION,
            )
            for q in quotes
        ],
    )


def matched_quotes(
    connection: sqlite3.Connection, claim_ids: tuple[str, ...]
) -> list[dict[str, object]]:
    cursor = connection.cursor()
    cursor.row_factory = sqlite3.Row
    return [
        dict(row)
        for row in cursor.execute(
            "SELECT * FROM claim_matched_quote WHERE claim_id IN (SELECT value FROM json_each(?))",
            (json.dumps(list(claim_ids)),),
        )
    ]


def member_period(metric_id: str, dimensions: dict[str, str], period: str) -> tuple[str, str, str]:
    """A member's period kind and bounds for a gap period, as the official parsers store it.

    Year-to-date members start on 1 January; a month or quarter covers itself; a day is a
    business day.
    """
    from pring_cycle.metric_contracts import official_source_members
    from pring_cycle.release_calendar import month_bounds

    members = official_source_members(metric_id, period) or ()
    kind = next((m.period_kind for m in members if m.dimensions == dimensions), None)
    if len(period) == 10:
        return kind or "business_day", period, period
    if "-Q" in period:
        year, quarter = int(period[:4]), int(period[-1])
        first = f"{year:04d}-{quarter * 3 - 2:02d}"
        last_start, last_end = month_bounds(f"{year:04d}-{quarter * 3:02d}")
        kind = kind or "quarter"
        start = f"{year:04d}-01-01" if kind == "year_to_quarter" else f"{first}-01"
        return kind, start, last_end
    start, end = month_bounds(period)
    kind = kind or "month"
    return kind, f"{period[:4]}-01-01" if kind == "year_to_month" else start, end


def gap_period(metric_id: str, dimensions: dict[str, str], start: str, end: str) -> str:
    """The gap period a stored member answers (the inverse of ``member_period``)."""
    from pring_cycle.metric_contracts import official_source_members

    members = official_source_members(metric_id, end[:7]) or ()
    kind = next((m.period_kind for m in members if m.dimensions == dimensions), None)
    if kind == "business_day" or (kind is None and start == end):
        return end
    if kind in {"quarter", "year_to_quarter"}:
        return f"{end[:4]}-Q{(int(end[5:7]) - 1) // 3 + 1}"
    return end[:7]


def member_unit(metric_id: str, dimensions: dict[str, str], period: str, default: str) -> str:
    from pring_cycle.metric_contracts import official_source_members

    members = official_source_members(metric_id, period) or ()
    return next((m.unit for m in members if m.dimensions == dimensions), default)


@dataclass(frozen=True)
class TakenValue:
    """A value a rule took from one text, with what the text says about itself."""

    value: NewsValue
    title: str
    source_name: str
    published_at: str | None
    body_hash: str
    url: str | None
    acquisition_id: str
    fetched_at: datetime
    release_at: datetime | None


def store_news_values(
    database: Path,
    taken: tuple[TakenValue, ...],
    *,
    route: str,
    provider: str,
    source_reference: Callable[[TakenValue], str],
    period: str,
    definition_version: str,
    available_at: datetime,
) -> tuple[str, ...]:
    """Store each taken value as a claim of its member's period, with its matched quote."""
    from pring_cycle.catalog import metric_definition
    from pring_cycle.evidence import EvidenceRepository, EvidenceValueState, SourceClaimInput
    from pring_cycle.storage import database_connection

    claims = []
    for item in taken:
        value = item.value
        kind, start, end = member_period(value.metric_id, value.dimensions, period)
        definition = metric_definition(
            value.metric_id, definition_version=definition_version, database_path=database
        )
        claims.append(
            SourceClaimInput(
                metric_id=value.metric_id,
                definition_version=definition_version,
                period_kind=kind,
                period_start=start,
                period_end=end,
                dimensions=value.dimensions,
                value=value.value,
                value_state=EvidenceValueState.REPORTED_VALUE,
                unit=member_unit(value.metric_id, value.dimensions, period, definition.unit),
                provider=provider,
                source_reference=source_reference(item),
                release_event_id=f"{route}:{value.metric_id}:{period}:{item.acquisition_id}",
                release_at=item.release_at,
                public_available_at=None,
                fetched_at=item.fetched_at,
                available_at=available_at,
                quality_status="validated",
                acquisition_id=item.acquisition_id,
            )
        )
    stored = EvidenceRepository(database).append_source_claims(tuple(claims))
    with database_connection(database) as connection:
        record_matched_quotes(
            connection,
            tuple(
                MatchedQuote(
                    claim.claim_id,
                    route,
                    item.value.quote,
                    item.title,
                    item.source_name,
                    item.published_at,
                    item.body_hash,
                    item.url,
                )
                for claim, item in zip(stored, taken, strict=True)
            ),
        )
    return tuple(claim.claim_id for claim in stored)


def news_claims_matching_quotes(
    database: Path, points_by_metric: Mapping[str, tuple[MetricSeriesPoint, ...]]
) -> set[str]:
    """Selected claims whose kept matched quote still gives their value under the rules.

    The original text is kept only a few days; the quote is kept as long as the claim.
    """
    from pring_cycle.storage import database_connection

    selected = {
        point.selected_claim_id: (metric_id, point)
        for metric_id, points in points_by_metric.items()
        for point in points
        if point.selected_claim_id is not None
    }
    if not selected:
        return set()
    with database_connection(database) as connection:
        if not connection.execute(
            "SELECT 1 FROM sqlite_master WHERE name='claim_matched_quote'"
        ).fetchone():
            return set()
        quotes = {str(row["claim_id"]): row for row in matched_quotes(connection, tuple(selected))}
    valid = set()
    for claim_id, row in quotes.items():
        metric_id, point = selected[claim_id]
        period = gap_period(metric_id, point.dimensions, point.period_start, point.period_end)
        values = extract((metric_id,), period, str(row["quote"]), recheck=True).values
        if any(
            item.dimensions == point.dimensions and item.value == point.selected_value
            for item in values
        ):
            valid.add(claim_id)
    return valid
