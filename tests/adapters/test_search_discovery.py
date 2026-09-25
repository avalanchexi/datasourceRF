from __future__ import annotations

from pring_cycle.search_discovery import (
    SearchHttpResponse,
    build_search_query,
    search_discovery_adapter,
)


def test_tavily_and_exa_contracts_return_unverified_urls_and_bounded_summaries() -> None:
    calls: list[tuple[str, dict[str, str], dict[str, object]]] = []

    def transport(
        endpoint: str,
        headers: dict[str, str],
        payload: dict[str, object],
    ) -> SearchHttpResponse:
        calls.append((endpoint, headers, payload))
        return SearchHttpResponse(
            200,
            {
                "results": [
                    {
                        "title": "untrusted result body must not persist",
                        "url": "https://unknown.example/release",
                        "content": "full external response sentinel",
                    }
                ]
            },
        )

    tavily = search_discovery_adapter(
        "tavily",
        "tavily-secret",
        "LPR 2026-08 official release",
        transport=transport,
    )("release-lpr")
    exa = search_discovery_adapter(
        "exa",
        "exa-secret",
        "LPR 2026-08 official release",
        transport=transport,
    )("release-lpr")

    assert tavily.status == exa.status == "candidate_source"
    assert tavily.evidence == exa.evidence == "https://unknown.example/release"
    assert tavily.classification == exa.classification == "unverified_candidate"
    assert calls[0][0] == "https://api.tavily.com/search"
    assert calls[0][1]["Authorization"] == "Bearer tavily-secret"
    assert calls[0][2]["include_raw_content"] is False
    assert calls[1][0] == "https://api.exa.ai/search"
    assert calls[1][1]["x-api-key"] == "exa-secret"
    assert (
        tavily.candidate_summaries
        == exa.candidate_summaries
        == ("full external response sentinel",)
    )
    assert "untrusted result body must not persist" not in repr((tavily, exa))
    assert "secret" not in repr((tavily, exa))


def test_search_failures_are_classified_without_returning_response_bodies() -> None:
    def response(status: int) -> object:
        return search_discovery_adapter(
            "tavily",
            "secret",
            "query",
            transport=lambda _endpoint, _headers, _payload: SearchHttpResponse(
                status,
                {"detail": "provider-response-sentinel"},
            ),
        )("release")

    assert response(401).classification == "authentication_failed"  # type: ignore[union-attr]
    assert response(429).classification == "rate_limited"  # type: ignore[union-attr]
    assert response(500).classification == "transient_transport_error"  # type: ignore[union-attr]
    assert "provider-response-sentinel" not in repr(response(400))


def test_query_is_the_family_release_title_with_a_chinese_period() -> None:
    assert (
        build_search_query(
            ("CN_PMI_ACTIVITY", "CN_PMI_INVENTORY", "CN_PMI_PRICES"), period="2026-08"
        )
        == "2026年8月份中国采购经理指数运行情况"
    )
    assert build_search_query(("CN_CPI_HEADLINE",), period="2026-08") == "2026年8月份居民消费价格"
    assert build_search_query(("CN_GDP",), period="2026-Q2") == (
        "2026年二季度和上半年国内生产总值初步核算结果"
    )
    assert build_search_query(("CN_LPR_1Y_5Y",), period="2026-08") == (
        "2026年8月贷款市场报价利率（LPR）公告"
    )
    assert "CN_" not in build_search_query(("CN_EQUITY_CORE_000985",), period="2026-08-27")


def test_every_registered_family_has_a_query_template() -> None:
    from pring_cycle.retrieval_registry import RETRIEVAL_FAMILIES, search_query

    for family in RETRIEVAL_FAMILIES.values():
        for metric_id in family.metric_ids:
            for period in ("2026-08-27", "2026-08", "2026-Q2"):
                query = search_query((metric_id,), period)
                assert query and metric_id not in query and "tushare" not in query


def test_media_whitelist_names_the_outlets_and_leaves_out_wind() -> None:
    from pring_cycle.retrieval_registry import MEDIA_WHITELIST, media_outlet, search_domains

    assert set(MEDIA_WHITELIST) == {
        "财联社",
        "新华网",
        "人民网",
        "中国政府网",
        "中国证券报",
        "上海证券报",
        "证券时报",
        "第一财经",
        "财新",
        "华尔街见闻",
        "新浪财经",
        "东方财富",
        "路透",
        "彭博",
        "CNBC",
        "MarketWatch",
        "华尔街日报",
        "金融时报",
        "雅虎财经",
        "Investing.com",
    }
    assert not any("wind" in domain for domains in MEDIA_WHITELIST.values() for domain in domains)
    assert media_outlet("https://www.cls.cn/detail/123") == "财联社"
    assert media_outlet("https://finance.sina.com.cn/x.html") == "新浪财经"
    assert media_outlet("https://sina.com.cn/x.html") is None
    assert media_outlet("https://www.stats.gov.cn/sj/x.html") is None
    domains = search_domains(("CN_CPI_HEADLINE",))
    assert domains[0] == "www.stats.gov.cn" and "cls.cn" in domains and "reuters.com" in domains


def test_tavily_and_exa_limit_the_search_to_the_given_domains() -> None:
    payloads: list[dict[str, object]] = []

    def transport(
        _endpoint: str, _headers: dict[str, str], payload: dict[str, object]
    ) -> SearchHttpResponse:
        payloads.append(payload)
        return SearchHttpResponse(200, {"results": []})

    for provider in ("tavily", "exa"):
        search_discovery_adapter(
            provider,
            "secret",
            "2026年8月份居民消费价格",
            transport=transport,
            domains=("www.stats.gov.cn", "cls.cn"),
        )("release")

    tavily, exa = payloads
    assert tavily["include_domains"] == ["www.stats.gov.cn", "cls.cn"]
    assert exa["includeDomains"] == ["www.stats.gov.cn", "cls.cn"]
    assert exa["contents"] == {"text": {"maxCharacters": 1500}}
