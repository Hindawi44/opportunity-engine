from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from opportunity_engine.discovery.merkandi_b2b_liquidation_feed import (
    FEED_FAMILY,
    QUERY,
    SOURCE_DOMAIN,
    collect_merkandi_b2b_liquidation_feed,
    merkandi_candidate_from_hit,
)
from opportunity_engine.discovery.search_provider import SearchHit

NOW = datetime(2026, 8, 6, 0, 30, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = ROOT / "scripts/build_domain_market_intelligence_feed.py"


def _valid_hit(quantity: str = "800 pcs") -> SearchHit:
    return SearchHit(
        title=f"Wholesale clothing liquidation stock {quantity} — €4.50 per piece",
        url="https://merkandi.com/products/verified-clothing-stock/12345?utm_source=test",
        description=(
            "Seller: Nordic Stock Partner AS; minimum order: 100 pcs; new with tags; "
            "manifest and packing list available; Brands: Example Label; proof of "
            "authenticity; warehouse location: Sweden; shipping available for export."
        ),
        provider="Brave Search",
    )


def test_query_is_bounded_to_official_merkandi_domain() -> None:
    assert SOURCE_DOMAIN == "merkandi.com"
    assert "site:merkandi.com" in QUERY


def test_accepts_complete_b2b_listing_for_human_decision() -> None:
    candidate = merkandi_candidate_from_hit(_valid_hit(), observed_at=NOW)
    assert candidate is not None
    assert candidate["feed_family"] == FEED_FAMILY
    assert candidate["source_url"] == "https://merkandi.com/products/verified-clothing-stock/12345"
    assert candidate["quantity"] == 800
    assert candidate["lot_size_band"] == "MEDIUM"
    assert candidate["minimum_order"] == 100
    assert candidate["unit_price"] == 4.5
    assert candidate["seller_name"] == "Nordic Stock Partner AS"
    assert candidate["opportunity_state"] == "B2B_LEAD_REQUIRES_VERIFICATION"
    assert candidate["decision_owner"] == "HUMAN_OPERATOR"
    assert candidate["quantity_size_rejection_applied"] is False
    assert candidate["top5_eligible"] is False
    assert candidate["automatic_purchase"] is False


def test_preserves_large_lot_instead_of_rejecting_it() -> None:
    candidate = merkandi_candidate_from_hit(_valid_hit("25000 pcs"), observed_at=NOW)
    assert candidate is not None
    assert candidate["quantity"] == 25000
    assert candidate["lot_size_band"] == "VERY_LARGE"
    assert candidate["quantity_size_rejection_applied"] is False
    assert candidate["decision_owner"] == "HUMAN_OPERATOR"


def test_preserves_serious_listing_with_missing_quantity_as_early_signal() -> None:
    hit = _valid_hit()
    candidate = merkandi_candidate_from_hit(
        SearchHit(
            title="Wholesale clothing liquidation stock — €4.50 per piece",
            url=hit.url,
            description=hit.description,
            provider=hit.provider,
        ),
        observed_at=NOW,
    )
    assert candidate is not None
    assert candidate["quantity"] is None
    assert "QUANTITY" in candidate["missing_information"]
    assert candidate["opportunity_state"] == "EARLY_B2B_SIGNAL_REQUIRES_VERIFICATION"


def test_preserves_unknown_seller_as_missing_information() -> None:
    hit = _valid_hit()
    candidate = merkandi_candidate_from_hit(
        SearchHit(
            title=hit.title,
            url=hit.url,
            description=hit.description.replace("Seller: Nordic Stock Partner AS; ", ""),
            provider=hit.provider,
        ),
        observed_at=NOW,
    )
    assert candidate is not None
    assert candidate["seller_name"] is None
    assert "SELLER_IDENTITY" in candidate["missing_information"]


def test_rejects_unapproved_domain_and_single_item() -> None:
    hit = _valid_hit()
    assert merkandi_candidate_from_hit(
        SearchHit(title=hit.title, url="https://merkandi-fake.example/p/1", description=hit.description),
        observed_at=NOW,
    ) is None
    assert merkandi_candidate_from_hit(_valid_hit("1 pc"), observed_at=NOW) is None


class FakeProvider:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    @property
    def name(self) -> str:
        return "Fake Brave"

    def search(self, query: str, *, count: int = 10) -> Sequence[SearchHit]:
        self.calls.append((query, count))
        return [
            _valid_hit(),
            SearchHit(
                title="Wholesale clothing clearance",
                url="https://merkandi.com/products/missing-evidence/999",
                description="Bulk apparel stock. No quantity, seller or manifest shown.",
                provider=self.name,
            ),
        ]


def test_collection_uses_one_request_and_preserves_incomplete_signals() -> None:
    providers: list[FakeProvider] = []

    def factory(country: str, api_key: str, freshness: str | None) -> FakeProvider:
        assert country == "DE"
        assert api_key == "secret"
        assert freshness == "pm"
        provider = FakeProvider()
        providers.append(provider)
        return provider

    report = collect_merkandi_b2b_liquidation_feed(
        observed_at=NOW,
        environment={"BRAVE_SEARCH_API_KEY": "secret"},
        provider_factory=factory,
        results=10,
    )
    assert report["feed_family"] == FEED_FAMILY
    assert report["requests_made"] == 1
    assert report["candidate_count"] == 2
    assert report["incomplete_signals_preserved"] is True
    assert report["quantity_size_rejection_enabled"] is False
    assert report["human_decision_required"] is True
    assert providers[0].calls == [(QUERY, 10)]


def test_missing_brave_key_is_explicit_and_makes_no_request() -> None:
    report = collect_merkandi_b2b_liquidation_feed(
        observed_at=NOW,
        environment={},
        provider_factory=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError()),
    )
    assert report["requests_made"] == 0
    assert report["status_counts"] == {"BLOCKED_CONFIGURATION": 1}


def test_results_limit_is_bounded() -> None:
    try:
        collect_merkandi_b2b_liquidation_feed(observed_at=NOW, environment={}, results=11)
    except ValueError as exc:
        assert "results" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_daily_builder_attaches_decision_support_contract() -> None:
    text = BUILD_SCRIPT.read_text(encoding="utf-8")
    assert "collect_merkandi_b2b_liquidation_feed" in text
    assert 'merkandi-b2b-liquidation-feed.json' in text
    assert 'brief["merkandi_b2b_liquidation_feed"]' in text
    assert '"EARLY_B2B_SIGNAL_REQUIRES_VERIFICATION"' in text
    assert '"automatic_purchase": False' in text
