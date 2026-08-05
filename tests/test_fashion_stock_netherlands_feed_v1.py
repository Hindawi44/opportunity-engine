from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from opportunity_engine.discovery.fashion_stock_netherlands_feed import (
    APPROVED_DOMAINS,
    FEED_FAMILY,
    QUERIES,
    collect_fashion_stock_netherlands_feed,
    fashion_stock_candidate_from_hit,
)
from opportunity_engine.discovery.search_provider import SearchHit

NOW = datetime(2026, 8, 6, 1, 0, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = ROOT / "scripts/build_domain_market_intelligence_feed.py"


def _offer(quantity: str = "5500 pieces") -> SearchHit:
    return SearchHit(
        title=f"Lerros stock clothing collection — {quantity} — €6.50 per piece",
        url="https://www.fashionstock.eu/shop_by_price.php?language=en&page=all&utm_source=test",
        description=(
            "Wholesale bulk fashion stock. Minimum order: 1000 pieces. Brands: Lerros; "
            "100% original stock; stock list available; new clothing; worldwide delivery."
        ),
        provider="Brave Search",
    )


def test_official_domain_family_is_explicit() -> None:
    assert APPROVED_DOMAINS == ("fashion-stock.eu", "fashionstock.eu", "fashion-stock.nl")
    assert len(QUERIES) == 2
    assert all("site:" in query for query in QUERIES)


def test_accepts_large_official_offer_without_size_rejection() -> None:
    candidate = fashion_stock_candidate_from_hit(_offer("25000 pieces"), observed_at=NOW)
    assert candidate is not None
    assert candidate["feed_family"] == FEED_FAMILY
    assert candidate["quantity"] == 25000
    assert candidate["lot_size_band"] == "VERY_LARGE"
    assert candidate["decision_owner"] == "HUMAN_OPERATOR"
    assert candidate["quantity_size_rejection_applied"] is False
    assert candidate["automatic_purchase"] is False


def test_preserves_catalogue_signal_when_price_and_quantity_are_missing() -> None:
    candidate = fashion_stock_candidate_from_hit(
        SearchHit(
            title="European brand clothing stock wholesale",
            url="https://www.fashion-stock.eu/stock/",
            description="Bulk stock clothing and leftovers for outlet owners and distributors.",
            provider="Brave Search",
        ),
        observed_at=NOW,
    )
    assert candidate is not None
    assert candidate["opportunity_state"] == "EARLY_B2B_SIGNAL_REQUIRES_VERIFICATION"
    assert "QUANTITY" in candidate["missing_information"]
    assert "VISIBLE_PRICE" in candidate["missing_information"]


def test_rejects_impostor_domain_and_single_item() -> None:
    hit = _offer()
    assert fashion_stock_candidate_from_hit(
        SearchHit(title=hit.title, url="https://fashion-stock-fake.example/lot", description=hit.description),
        observed_at=NOW,
    ) is None
    assert fashion_stock_candidate_from_hit(_offer("1 piece"), observed_at=NOW) is None


class FakeProvider:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    @property
    def name(self) -> str:
        return "Fake Brave"

    def search(self, query: str, *, count: int = 10) -> Sequence[SearchHit]:
        self.calls.append((query, count))
        if "fashion-stock.eu" in query:
            return [
                SearchHit(
                    title="Stock clothes wholesale from Europe",
                    url="https://www.fashion-stock.eu/stock/",
                    description="Bulk branded clothing leftovers and overproduction stock.",
                    provider=self.name,
                )
            ]
        return [_offer()]


def test_collection_is_bounded_to_two_queries() -> None:
    providers: list[FakeProvider] = []

    def factory(country: str, api_key: str, freshness: str | None) -> FakeProvider:
        assert country == "NL"
        assert api_key == "secret"
        provider = FakeProvider()
        providers.append(provider)
        return provider

    report = collect_fashion_stock_netherlands_feed(
        observed_at=NOW,
        environment={"BRAVE_SEARCH_API_KEY": "secret"},
        provider_factory=factory,
        results_per_query=8,
    )
    assert report["query_budget_total"] == 2
    assert report["requests_made"] == 2
    assert report["candidate_count"] == 2
    assert report["quantity_size_rejection_enabled"] is False
    assert report["human_decision_required"] is True
    assert len(providers[0].calls) == 2


def test_missing_key_is_explicit() -> None:
    def forbidden_factory(*args, **kwargs):
        raise AssertionError("provider must not be initialized")

    report = collect_fashion_stock_netherlands_feed(
        observed_at=NOW,
        environment={},
        provider_factory=forbidden_factory,
    )
    assert report["requests_made"] == 0
    assert report["status_counts"] == {"BLOCKED_CONFIGURATION": 1}


def test_builder_writes_and_attaches_fashion_stock_feed() -> None:
    text = BUILD_SCRIPT.read_text(encoding="utf-8")
    assert "collect_fashion_stock_netherlands_feed" in text
    assert 'fashion-stock-netherlands-feed.json' in text
    assert 'brief["fashion_stock_netherlands_feed"]' in text
    assert '"HUMAN_OPERATOR"' in text
