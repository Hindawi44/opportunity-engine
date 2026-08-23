from __future__ import annotations

from opportunity_engine.discovery.exa_shadow_page_verification import (
    ACTIVE_STOCK_SIGNAL,
    EXACT_LOT_CANDIDATE,
    verify_exa_unique_pages,
)
from opportunity_engine.discovery.keyword_shadow_verification import PageFetchResult


def _benchmark(urls: list[str]) -> dict:
    return {
        "status": "SUCCESS",
        "shadow_only": True,
        "market_results": [
            {
                "market_code": "NO",
                "query": "exact lot",
                "exa": {
                    "results": [
                        {"title": "stock page", "url": url, "domain": "market.example"}
                        for url in urls
                    ]
                },
                "brave": {"results": []},
            }
        ],
    }


def _fetch(url: str) -> PageFetchResult:
    text = (
        "Vareparti til salgs. 640 stk arbeidsjakker. Pris 18 500 NOK. "
        "Varene er på lager og tilgjengelig nå."
    )
    return PageFetchResult(
        requested_url=url,
        final_url=url,
        ok=True,
        status_code=200,
        title="Vareparti til salgs",
        text=text,
    )


def test_search_and_homepage_cannot_be_exact_lot_even_with_price_and_quantity() -> None:
    urls = [
        "https://market.example/search?category=stock",
        "https://market.example/",
    ]
    report = verify_exa_unique_pages(_benchmark(urls), page_fetcher=_fetch, max_page_fetches=2)
    by_url = {item["url"]: item for item in report["verified_pages"]}

    assert by_url[urls[0]]["classification"] == ACTIVE_STOCK_SIGNAL
    assert by_url[urls[1]]["classification"] == ACTIVE_STOCK_SIGNAL
    assert by_url[urls[0]]["evidence"]["item_specific_url_evidence"] is False
    assert by_url[urls[1]]["evidence"]["item_specific_url_evidence"] is False
    assert report["exact_lot_candidate_count"] == 0


def test_item_or_lot_detail_url_can_be_exact_when_all_commercial_evidence_exists() -> None:
    urls = [
        "https://market.example/item/24362849",
        "https://market.example/lot/44",
        "https://market.example/lot-77",
    ]
    report = verify_exa_unique_pages(_benchmark(urls), page_fetcher=_fetch, max_page_fetches=3)

    assert report["exact_lot_candidate_count"] == 3
    for item in report["verified_pages"]:
        assert item["classification"] == EXACT_LOT_CANDIDATE
        assert item["evidence"]["item_specific_url_evidence"] is True
