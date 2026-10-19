"""Reader-facing domain wording, kept in one place for every page that shows it.

The board, the stage history page and the report page all name core asset states,
30-day candidate directions, asset candidates and formal stages through these
mappings, so the glossary terms change together (GLOSSARY.md). Metrics and their members
are named once here too, for the cockpit, the data chain and its Sankey alike, and so are the
reasons a gap list records.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

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


# The macro stage judgement's words (ADR-0043, GLOSSARY: 宏观判断阶段, 维度方向).
MACRO_JUDGEMENT = "宏观判断"
NO_MACRO_JUDGEMENT = "该投影生成时尚无宏观判断"
MACRO_CONFIDENCES = {"explicit": "明确", "tendency": "倾向", "weak": "弱"}
# A stage history day without a macro conclusion: summarized before the rules took effect,
# or with no stage to take (decision 49).
MACRO_HISTORY_BLANKS = {"not_effective": "生效前", "no_stage": "无可取阶段"}
# A day corrected on its cores only keeps the conclusion it published (integration review F4).
MACRO_NOT_RECOMPUTED = "未重算"
MACRO_KEPT = "上下文明细已超出留存，只更正核心：沿用该日已发布的宏观判断，未重算"
MACRO_GROUPS = {"monetary": "货币周期", "economic": "经济周期", "inventory": "库存周期"}
MACRO_DIMENSIONS = {
    "policy": "政策",
    "credit": "信用",
    "overheat": "增长",
    "price": "物价",
    "inventory": "库存",
}
MACRO_VALUES = {
    "up": "上行",
    "down": "下行",
    "flat": "持平",
    "easing": "宽松",
    "tightening": "收紧",
    "neutral": "中性",
    "active_destocking": "主动去库存",
    "passive_destocking": "被动去库存",
    "active_restocking": "主动补库存",
    "passive_restocking": "被动补库存",
}
MACRO_POSITIONS = {"high": "高位", "middle": "中位", "low": "低位"}
MACRO_UNKNOWN = "不明"
# Section 04 under a judgement: its five dimensions' basis (macro stage ticket 07).
MACRO_BASIS = "宏观判断依据"
# The signal list under the judgement (macro stage ticket 04).
MACRO_SIGNAL_LIST = "信号清单"
MACRO_NO_SIGNALS = "当日无成形以上的转折信号"
MACRO_SAME_SOURCE = "同源，不参与投票"
MACRO_SIGNAL_GROUPS = {
    "forward": "支持前进",
    "back": "支持后退",
    "hold": "支持维持",
    "open": "转换未定",
    "unmapped": "资产转向（未映射阶段）",
}
MACRO_MATURITIES = {"sprout": "萌芽", "forming": "成形", "confirmed": "确认"}
# A divergence recounted to the day's raw judgement while the hysteresis holds (decision 60).
MACRO_RAW_UNCHANGED = "不改变当日原始判断"
MACRO_ASSETS = {"bond": "债券", "stock": "股票", "commodity": "商品"}
# The price verification row and its drawer (macro stage ticket 06).
MACRO_VERIFICATION = "价格验证"
MACRO_BOARD_NOTES = "补充说明"


# How a report's formal stage changed on its day, as its verified results record it.
STAGE_CHANGE_LABELS = {"formal": "形成正式阶段", "gap": NO_FORMAL_STAGE}
NONCANONICAL_NO_STAGE = "非典型组合，暂无正式阶段"
# Under the macro judgement the cores' stage is the price stage (GLOSSARY: 价格阶段).
FORMAL_TERM, PRICE_TERM = "正式阶段", "价格阶段"


def noncanonical_stage_change(change: object, reason: object) -> bool:
    """Whether a day's ``gap`` stage change is a noncanonical combination's result with no
    formal stage, not missing core data (ticket 13)."""
    return change == "gap" and reason == "noncanonical_combination"


def stage_change_label(change: object, reason: object) -> str | None:
    """A day's stage change in reader's words."""
    if change is None:
        return None
    if noncanonical_stage_change(change, reason):
        return NONCANONICAL_NO_STAGE
    return STAGE_CHANGE_LABELS.get(str(change), str(change))


def core_state_label(value: object) -> str:
    """A core asset state, 30-day candidate direction or asset candidate as 牛市 / 熊市."""
    if value is None:
        return UNAVAILABLE
    return CORE_STATE_LABELS.get(str(value).lower(), UNAVAILABLE)


def stage_code(value: object) -> str:
    """A formal stage's short name, as the reason line maps a combination to it."""
    return STAGE_TITLES.get(str(value).lower(), str(value)).rpartition(" · ")[2]


def stage_name(value: object) -> str:
    """A formal stage's Chinese name alone (第三阶段), as report prose names it."""
    return STAGE_TITLES.get(str(value).lower(), str(value)).partition(" · ")[0]


def stage_title(value: object) -> str:
    """A formal stage title; an empty current stage is a result, not a pending judgement."""
    if value is None:
        return NO_FORMAL_STAGE
    return STAGE_TITLES.get(str(value).lower(), str(value))


# The page's display-name table, by metric (P0–P2 of the registered catalog) and then by
# member dimensions. The frozen catalog has no member layer and gives Chinese names to few
# metrics, so this table names the members that would otherwise share one label; a catalog
# ``name_cn`` other than the code still wins at the metric level (ticket 02).
METRIC_NAMES = {
    "CN_TRADE_CALENDAR": "交易日历",
    "CN_RELEASE_SCHEDULE": "发布日历",
    "SOURCE_OBSERVED_AVAILABILITY": "来源实际可得时点",
    "CN_EQUITY_CORE_000985": "中证全指",
    "CN_BOND_CORE_000012": "上证国债指数",
    "CN_COMMODITY_CORE_NHII": "南华工业品指数",
    "CN_EQ_CSI300": "沪深 300",
    "CN_EQ_CSI500": "中证 500",
    "CN_EQ_CSI1000": "中证 1000",
    "CN_EQ_ADV_DEC": "涨跌家数",
    "CN_EQ_AD_RATIO": "涨跌家数比",
    "CN_EQ_ADV_AMOUNT_SHARE": "上涨成交额占比",
    "CN_EQ_NEW_HIGH_LOW_90": "90 日新高新低",
    "CN_EQ_NEW_HIGH_LOW_250": "250 日新高新低",
    "CN_EQ_ABOVE_MA90": "站上 90 日均线占比",
    "CN_EQ_ABOVE_MA250": "站上 250 日均线占比",
    "CN_MARGIN_BALANCE_SSE_SZSE": "沪深两所融资余额与买入额",
    "CN_INDEX_VALUATION": "指数估值",
    "CN_BOND_FULL_PRICE_CNY030": "中债 030 全价",
    "CN_BOND_10Y_930916": "10 年国债价格指数",
    "CN_DR007": "DR007",
    "CN_OMO_7D_RATE": "七天逆回购利率",
    "CN_OMO_7D_AMOUNT": "七天逆回购净投放",
    "CN_DR007_POLICY_SPREAD": "DR007 政策利差",
    "CN_SHIBOR_ON_1W_3M": "SHIBOR",
    "CN_LPR_1Y_5Y": "LPR",
    "CN_RRR_EVENT": "存款准备金率调整",
    "CN_TOOL_LIQUIDITY_MONTHLY": "月度工具投放",
    "CN_COMMODITY_BROAD_NHCI": "南华综合指数",
    "CN_COMMODITY_EX_HOG_BASKET": "商品篮子",
    "CN_COMMODITY_SLEEVE_CONTRIBUTION": "商品篮子分项贡献",
    "CN_FUTURES_WARRANTS": "期货注册仓单",
    "CN_PMI_ACTIVITY": "制造业 PMI",
    "CN_PMI_INVENTORY": "PMI 产成品库存",
    "CN_PMI_PRICES": "PMI 价格",
    "CN_ORDER_INVENTORY_SPREAD": "PMI 新订单与产成品库存差",
    "CN_PRODUCTION_ORDER_SPREAD": "PMI 生产与新订单差",
    "CN_CPI_HEADLINE": "居民消费价格",
    "CN_CORE_CPI": "核心 CPI",
    "CN_PPI": "工业生产者价格",
    "CN_INDUSTRIAL_VA": "工业增加值",
    "CN_INDUSTRIAL_FINANCE": "工业企业盈利",
    "CN_FINISHED_GOODS_INVENTORY": "产成品存货",
    "CN_INVENTORY_TURNOVER": "产成品周转天数",
    "CN_CAPACITY_UTILIZATION": "产能利用率",
    "CN_M1_M2": "M1/M2",
    "CN_SF_TOTAL": "社融存量",
    "CN_SF_COMPONENTS": "社融分项",
    "CN_LOAN_STRUCTURE": "贷款结构",
    "CN_CREDIT_IMPULSE": "信用脉冲",
    "CN_GDP": "GDP",
    "CN_USDCNY_CENTRAL_PARITY": "美元兑人民币中间价",
    "CN_USDCNY_CLOSE_1630": "美元兑人民币 16:30 收盘价",
    "CN_USDCNY_ECB_REFERENCE_CROSS": "ECB 美元兑人民币参考交叉汇率",
    "EIA_BRENT_RBRTE": "Brent 原油",
    "EIA_WTI_RWTC": "WTI 原油",
    "UST10Y_NOMINAL_YIELD": "美国 10 年期国债收益率",
    "UST2Y_NOMINAL_YIELD": "美国 2 年期国债收益率",
    "UST_2S10S_SPREAD": "美债 10 年减 2 年利差",
    "CBOE_VIX_INDEX": "VIX 波动率指数",
    "NASDAQ_SOX_INDEX": "费城半导体指数",
}
_INDEXES = {"000300.SH": "沪深 300", "000905.SH": "中证 500", "000852.SH": "中证 1000"}
_VALUATIONS = {"price_book": "市净率", "price_earnings": "市盈率", "turnover_rate": "换手率"}
_GDP_AGGREGATES = {
    "total": "GDP 总量",
    "primary": "第一产业",
    "secondary": "第二产业",
    "tertiary": "第三产业",
}
_GDP_MEASURES = {"real_quarter_yoy": "实际季度同比", "nominal_ytd_level": "名义累计值"}
_HIGH_LOW = {"new_highs": "新高家数", "new_lows": "新低家数"}
_WARRANT_SYMBOLS = {
    "CF": "棉花",
    "TA": "PTA",
    "PP": "聚丙烯",
    "CU": "铜",
    "RB": "螺纹钢",
    "RU": "天然橡胶",
    "SP": "纸浆",
    "SC": "原油",
}
# Social financing's measures, and the components of its stock as the PBC's report names them.
_SF_MEASURES = {"stock_end": "期末存量", "ytd_increment": "累计增量", "stock_yoy": "存量同比"}
_SF_COMPONENTS = {
    "renminbi_loans": "人民币贷款",
    "foreign_currency_loans_rmb": "外币贷款（折合人民币）",
    "entrusted_loans": "委托贷款",
    "trust_loans": "信托贷款",
    "undiscounted_bank_acceptances": "未贴现银行承兑汇票",
    "corporate_bonds": "企业债券",
    "government_bonds": "政府债券",
    "nonfinancial_enterprise_equity": "非金融企业境内股票融资",
    "depository_abs": "存款类金融机构资产支持证券",
    "loan_writeoffs": "贷款核销",
}
# Each member entry names the dimension values it matches; a row may carry more dimensions.
MEMBER_NAMES: dict[str, tuple[tuple[dict[str, str], str], ...]] = {
    "CN_EQ_ADV_DEC": tuple(
        ({"measure": measure}, name)
        for measure, name in (
            ("advances", "上涨家数"),
            ("declines", "下跌家数"),
            ("flats", "平盘家数"),
            ("net", "净上涨家数"),
            ("participants", "参与交易家数"),
        )
    ),
    **{
        f"CN_EQ_NEW_HIGH_LOW_{days}": tuple(
            ({"measure": measure}, f"{days} 日{name}") for measure, name in _HIGH_LOW.items()
        )
        for days in (90, 250)
    },
    "CN_INDEX_VALUATION": tuple(
        ({"index": index, "measure": measure}, f"{index_name} {measure_name}")
        for index, index_name in _INDEXES.items()
        for measure, measure_name in _VALUATIONS.items()
    ),
    "CN_MARGIN_BALANCE_SSE_SZSE": (
        ({"measure": "financing_balance"}, "融资余额"),
        ({"measure": "financing_buy_amount"}, "融资买入额"),
    ),
    "CN_COMMODITY_SLEEVE_CONTRIBUTION": tuple(
        ({"sleeve": sleeve}, name)
        for sleeve, name in (
            ("copper", "铜"),
            ("crude_oil", "原油"),
            ("polypropylene", "聚丙烯"),
            ("pulp", "纸浆"),
            ("rebar", "螺纹钢"),
            ("rubber", "天然橡胶"),
            ("textiles", "纺织（棉花与 PTA 合计）"),
        )
    ),
    "CN_GDP": tuple(
        (
            {"aggregate": aggregate, "measure": measure},
            aggregate_name + measure_name,
        )
        for aggregate, aggregate_name in _GDP_AGGREGATES.items()
        for measure, measure_name in _GDP_MEASURES.items()
    ),
    "CN_FUTURES_WARRANTS": tuple(
        ({"symbol": symbol}, name) for symbol, name in _WARRANT_SYMBOLS.items()
    ),
    "CN_SF_TOTAL": tuple(({"measure": measure}, name) for measure, name in _SF_MEASURES.items()),
    "CN_SF_COMPONENTS": tuple(
        ({"component": component, "measure": measure}, component_name + measure_name)
        for component, component_name in _SF_COMPONENTS.items()
        for measure, measure_name in _SF_MEASURES.items()
    ),
}
# Request sources as the data chain and its Sankey name them; providers arrive as free text.
# A registered source code (``tushare:index_daily``) is named by its provider, before the colon.
SOURCE_NAMES = {
    "official": "官方发布",
    "tushare": "TuShare",
    "tushare_news": "TuShare 资讯",
    "tavily": "Tavily",
    "exa": "Exa",
    "ai_websearch": "AI 联网检索",
    "local": "本地复用",
    "U.S. Energy Information Administration": "美国能源信息署",
    "European Central Bank": "欧洲央行",
    "Cboe Global Markets": "Cboe",
    "Nasdaq Global Indexes": "纳斯达克指数",
    "pbc": "中国人民银行",
    "chinamoney": "中国货币网",
    "eia": "美国能源信息署",
    "ecb": "欧洲央行",
    "cboe": "Cboe",
    "nasdaq": "纳斯达克指数",
    "derived": "派生计算",
}
# Why a metric period is a gap, as the gap list records it: the row's own reason, the release
# gate that kept a period from being requested, where an official listing's reading stopped,
# and why a search candidate was not adopted. One table for every place that shows them, so a
# new code is one row here; an unmapped code is shown as recorded (ticket 13).
REASON_LABELS = {
    # A gap row's reason.
    "not_held": "未持有",
    "one_period_behind_carried": "落后一期，沿用上一期",
    "two_or_more_periods_behind": "落后两期及以上",
    "backtrack_incomplete": "回溯未完成（来源失败）",
    "freshness_not_registered": "未登记时效规则",
    "restricted_license": "授权受限，不取数也不检索",
    "period_not_requested": "未请求",
    "listing_not_covered": "官方列表未覆盖",
    "members_missing": "部分成员未取得",
    "historical_periods_missing": "历史缺期",
    "not_computed": "未计算",
    "missing_inputs": "缺少输入",
    "incomparable_gdp_vintages": "GDP 前后版本不可比",
    "acquisition_time_invalid": "取数时点无效",
    # Why a count of companies has no 120-day difference on the page.
    "count_window_outside_points": "点列只含 120 个交易日，无法算 120 日家数差",
    # The release gate's reason for a period it kept from being requested.
    "awaiting_release": "等待发布",
    "earlier_session_not_searched": "较早交易日不逐日检索",
    "unknown_release_configuration": "发布规则未登记",
    "negative_cache_active": "被负缓存拦下",
    # What a period awaiting release takes its next release date from (worker gaps 03).
    "source_next_release_date": "来源原件写明",
    "registered_release_lag": "按登记发布滞后推算",
    # Where an official listing's reading stopped.
    "page_limit": "本轮该站列表页额度用完",
    "repeated_page": "翻到重复页",
    "unreadable_page": "列表页多次读取失败",
    "last_page": "栏目已到底",
    # Why a search candidate was not adopted.
    "not_whitelisted": "不在白名单",
    "parse_failed": "解析失败",
    "period_mismatch": "统计期不符",
    "no_publication_date": "无发布日期",
    "date_after_cutoff": "日期晚于截止时点",
    "search_value_mismatch": "与搜索结果不一致",
    "fetch_failed": "抓取失败",
    "incomplete_model_input": "数值不完整",
    "retrieval_blocked": "请求被缓存或预算拦下",
    "rule_not_matched": "解析规则未命中",
    # Why the request a negative cache holds a candidate back for first failed (worker
    # gaps 01); "negative_cache_active" itself is above.
    "official_context_usdcny_quote_missing": "官方页未见美元中间价",
    "official_context_period_identity_mismatch": "官方页日期与所需期不符",
    "official_context_source_http_status_invalid": "官方页返回异常状态",
}
NO_CHINESE_NAME = "未提供中文名"
NO_MEMBER_NAME = "未提供成员中文名"


@dataclass(frozen=True)
class DisplayName:
    """A metric or member as a reader sees it: Chinese name first, code second."""

    name: str
    code: str
    provided: bool
    # The name is the Chinese label of the member's group, not of the row itself.
    group: bool = False


def display_name(
    metric_id: object,
    dimensions: Mapping[str, object] | None = None,
    catalog_name: object = None,
) -> DisplayName:
    """Name a metric row: member table, then a catalog name, then the metric table, then code.

    The code is the metric id with the dimension values that tell its members apart: those
    of the matching member entry, or every value when no entry matches.
    """
    code = str(metric_id or "")
    values = {str(key): str(value) for key, value in (dimensions or {}).items()}
    member = max(
        (
            entry
            for entry in MEMBER_NAMES.get(code, ())
            if all(values.get(key) == value for key, value in entry[0].items())
        ),
        key=lambda entry: len(entry[0]),
        default=None,
    )
    shown = (
        [values[key] for key in member[0]] if member else [values[key] for key in sorted(values)]
    )
    full_code = " · ".join([code, " × ".join(shown)]) if shown else code
    catalog = str(catalog_name) if catalog_name and str(catalog_name) != code else None
    name = (member[1] if member else None) or catalog or METRIC_NAMES.get(code)
    return DisplayName(name or code, full_code, name is not None)


def reason_label(code: object) -> str:
    """A gap reason in Chinese, or the recorded code when none is mapped."""
    return REASON_LABELS.get(str(code), str(code))


def metric_label(metric_id: object) -> str:
    """A metric in running text: its Chinese name with the code after it, or the code alone."""
    name = display_name(metric_id)
    return f"{name.name}（{name.code}）" if name.provided else name.code


def source_name(channel: object) -> str:
    """A request source's Chinese name, or the recorded value when none is mapped."""
    value = str(channel)
    return SOURCE_NAMES.get(value) or SOURCE_NAMES.get(value.partition(":")[0], value)
