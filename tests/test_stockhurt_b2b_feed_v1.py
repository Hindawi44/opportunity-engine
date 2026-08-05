from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.discovery.stockhurt_b2b_feed import (
    APPROVED_DOMAINS,
    FEED_FAMILY,
    QUERIES,
    collect_stockhurt_b2b_feed,
    stockhurt_candidate_from_hit,
)

NOW = datetime(2026, 8, 6, 1, 30, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = ROOT / "scripts/build_domain_market_intelligence_feed.py"


def _large_offer() -> SearchHit:
    return SearchHit(
        title=(
            "Warehouse women's clothing grade B (kg) — "
            "25000 kg — €4.50 per kg"
        ),
        url=(
            "https://stockhurt.com/en/product/"
            "warehouse-womens-clothing-grade-b/?utm_source=test"
        ),
        description=(
            "Wholesale outlet clothing. Minimum weight of 20 kg. "
            "Brand: Warehouse. Original stock; stock list available; "
            "delivery in Europe."
        ),
        provider="Brave Search",
    )


def _auction() -> SearchHit:
    return SearchHit(
        title="Pallet auctions — Nike BOX 9464564",
        url="https://stockhurt.com/en/licytacje/",
        description=(
            "Auction of pallets and packages with branded clothing, "
            "bidding from 1 PLN."
        ),
        provider="Brave Search",
    )


def test_official_domain_and_bounded_queries_are_explicit() -> None:
    assert APPROVED_DOMAINS == ("stockhurt.com",)
    assert len(QUERIES) == 2
    assert all("site:stockhurt.com" in query for query in QUERIES)


def test_preserves_very_large_product_offer_for_human_decision() -> None:
    candidate = stockhurt_candidate_from_hit(_large_offer(), observed_at=NOW)

    assert candidate is not None
    assert candidate["feed_family"] == FEED_FAMILY
    assert candidate["page_role"] == "SPECIFIC_STOCK_OFFER"
    assert candidate["quantity"] == 25000
    assert candidate["quantity_unit"] == "kg"
    assert candidate["lot_size_band"] == "VERY_LARGE"
    assert candidate["minimum_order"] == 20
    assert candidate["minimum_order_unit"] == "kg"
    assert candidate["unit_price"] == 4.5
    assert candidate["currency"] == "EUR"
    assert candidate["grade"] == "B"
    assert candidate["decision_owner"] == "HUMAN_OPERATOR"
    assert candidate["quantity_size_rejection_applied"] is False
    assert candidate["automatic_purchase"] is False


def test_preserves_incomplete_specific_product_as_early_signal() -> None:
    candidate = stockhurt_candidate_from_hit(
        SearchHit(
            title="Warehouse women's clothing grade B (kg)",
            url=(
                "https://stockhurt.com/en/product/"
                "warehouse-womens-clothing-grade-b/"
            ),
            description=(
                "Wholesale outlet clothing available for pallets and packages "
                "with a minimum weight of 20 kg. Brand: Warehouse."
            ),
            provider="Brave Search",
        ),
        observed_at=NOW,
    )

    assert candidate is not None
    assert candidate["opportunity_state"] == (
        "EARLY_B2B_SIGNAL_REQUIRES_VERIFICATION"
    )
    assert candidate["minimum_order"] == 20
    assert "QUANTITY" in candidate["missing_information"]
    assert "VISIBLE_PRICE" in candidate["missing_information"]


def test_preserves_pallet_auction_without_automatic_bid() -> None:
    candidate = stockhurt_candidate_from_hit(_auction(), observed_at=NOW)

    assert candidate is not None
    assert candidate["page_role"] == "PALLET_AUCTION_SIGNAL"
    assert candidate["currency"] == "PLN"
    assert candidate["total_price"] == 1
    assert candidate["decision_owner"] == "HUMAN_OPERATOR"
    assert candidate["automatic_bid"] is False
    assert candidate["automatic_purchase"] is False


def test_out_of_stock_product_remains_visible_as_history_signal() -> None:
    candidate = stockhurt_candidate_from_hit(
        SearchHit(
            title="Out of stock Veepee clothing grade A",
            url="https://stockhurt.com/en/product/veepee-clothing-grade-a/",
            description="Wholesale outlet clothing package. Brand: Veepee.",
            provider="Brave Search",
        ),
        observed_at=NOW,
    )

    assert candidate is not None
    assert candidate["listing_status"] == "OUT_OF_STOCK"
    assert candidate["opportunity_state"] == (
        "EARLY_B2B_SIGNAL_REQUIRES_VERIFICATION"
    )


def test_rejects_impostor_domain_and_single_item() -> None:
    hit = _large_offer()
    assert stockhurt_candidate_from_hit(
        SearchHit(
            title=hit.title,
            url="https://stockhurt-fake.example/product/lot",
            description=hit.description,
        ),
        observed_at=NOW,
    ) is None

    assert stockhurt_candidate_from_hit(
        SearchHit(
            title="Wholesale outlet clothing — 1 piece — €5 per piece",
            url="https://stockhurt.com/en/product/single-item/",
            description="Brand: Warehouse; stock list available.",
        ),
        observed_at=NOW,
    ) is None


class FakeProvider:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    @property
    def name(self) -> str:
        return "Fake Brave"

    def search(self, query: str, *, count: int = 10) -> Sequence[SearchHit]:
        self.calls.append((query, count))
        return [_large_offer()] if "/product/" in query else [_auction()]


def test_collection_is_bounded_to_two_official_domain_queries() -> None:
    providers: list[FakeProvider] = []

    def factory(country: str, api_key: str, freshness: str | None) -> FakeProvider:
        assert country == "PL"
        assert api_key == "secret"
        assert freshness == "pm"
        provider = FakeProvider()
        providers.append(provider)
        return provider

    report = collect_stockhurt_b2b_feed(
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
    assert report["out_of_stock_signals_preserved"] is True
    assert len(providers[0].calls) == 2


def test_missing_key_is_explicit_and_makes_no_request() -> None:
    def forbidden_factory(*args, **kwargs):
        raise AssertionError("provider must not be initialized")

    report = collect_stockhurt_b2b_feed(
        observed_at=NOW,
        environment={},
        provider_factory=forbidden_factory,
    )

    assert report["requests_made"] == 0
    assert report["status_counts"] == {"BLOCKED_CONFIGURATION": 1}


def test_builder_writes_and_attaches_stockhurt_feed() -> None:
    text = BUILD_SCRIPT.read_text(encoding="utf-8")
    assert "collect_stockhurt_b2b_feed" in text
    assert 'stockhurt-b2b-feed.json' in text
    assert 'brief["stockhurt_b2b_feed"]' in text
    assert '"HUMAN_OPERATOR"' in text
    assert '"automatic_purchase": False' in text
