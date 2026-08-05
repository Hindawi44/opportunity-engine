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


def _valid_hit() -> SearchHit:
    return SearchHit(
        title="Wholesale clothing liquidation stock 800 pcs — €4.50 per piece",
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


def test_accepts_complete_small_operator_b2b_listing() -> None:
    candidate = merkandi_candidate_from_hit(_valid_hit(), observed_at=NOW)

    assert candidate is not None
    assert candidate["feed_family"] == FEED_FAMILY
    assert candidate["source_url"] == (
        "https://merkandi.com/products/verified-clothing-stock/12345"
    )
    assert candidate["quantity"] == 800
    assert candidate["quantity_unit"] == "units"
    assert candidate["minimum_order"] == 100
    assert candidate["unit_price"] == 4.5
    assert candidate["currency"] == "EUR"
    assert candidate["seller_name"] == "Nordic Stock Partner AS"
    assert candidate["manifest_available"] is True
    assert candidate["authenticity_evidence_visible"] is True
    assert candidate["opportunity_state"] == "B2B_LEAD_REQUIRES_VERIFICATION"
    assert candidate["top5_eligible"] is False
    assert candidate["automatic_contact"] is False
    assert candidate["automatic_purchase"] is False


def test_rejects_unapproved_domain() -> None:
    hit = _valid_hit()
    candidate = merkandi_candidate_from_hit(
        SearchHit(
            title=hit.title,
            url="https://merkandi-fake.example/products/123",
            description=hit.description,
            provider=hit.provider,
        ),
        observed_at=NOW,
    )
    assert candidate is None


def test_rejects_listing_without_quantity() -> None:
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
    assert candidate is None


def test_rejects_unknown_seller() -> None:
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
    assert candidate is None


def test_rejects_single_item_listing() -> None:
    hit = _valid_hit()
    candidate = merkandi_candidate_from_hit(
        SearchHit(
            title=hit.title.replace("800 pcs", "1 pc"),
            url=hit.url,
            description=hit.description,
            provider=hit.provider,
        ),
        observed_at=NOW,
    )
    assert candidate is None


def test_rejects_branded_stock_without_authenticity_evidence() -> None:
    hit = _valid_hit()
    candidate = merkandi_candidate_from_hit(
        SearchHit(
            title=hit.title,
            url=hit.url,
            description=hit.description.replace("proof of authenticity; ", ""),
            provider=hit.provider,
        ),
        observed_at=NOW,
    )
    assert candidate is None


def test_rejects_quantity_above_small_operator_limit() -> None:
    hit = _valid_hit()
    candidate = merkandi_candidate_from_hit(
        SearchHit(
            title=hit.title.replace("800 pcs", "25000 pcs"),
            url=hit.url,
            description=hit.description,
            provider=hit.provider,
        ),
        observed_at=NOW,
    )
    assert candidate is None


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
                description="No quantity, seller or manifest shown.",
                provider=self.name,
            ),
        ]


def test_collection_uses_one_bounded_search_request() -> None:
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
    assert report["query_budget_total"] == 1
    assert report["requests_made"] == 1
    assert report["candidate_count"] == 1
    assert report["status_counts"] == {"SUCCESS": 1}
    assert report["not_part_of_opportunity_top5"] is True
    assert report["automatic_purchase"] is False
    assert len(providers) == 1
    assert providers[0].calls == [(QUERY, 10)]
    assert report["sources"][0]["rejected_result_count"] == 1


def test_missing_brave_key_is_explicit_and_makes_no_request() -> None:
    def forbidden_factory(*args, **kwargs):
        raise AssertionError("provider must not be initialized")

    report = collect_merkandi_b2b_liquidation_feed(
        observed_at=NOW,
        environment={},
        provider_factory=forbidden_factory,
    )

    assert report["requests_made"] == 0
    assert report["candidate_count"] == 0
    assert report["status_counts"] == {"BLOCKED_CONFIGURATION": 1}
    assert report["sources"][0]["block_reason"] == "BRAVE_SEARCH_API_KEY_MISSING"


def test_results_limit_is_bounded() -> None:
    try:
        collect_merkandi_b2b_liquidation_feed(
            observed_at=NOW,
            environment={},
            results=11,
        )
    except ValueError as exc:
        assert "results" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError")


def test_daily_builder_writes_and_attaches_merkandi_feed() -> None:
    text = BUILD_SCRIPT.read_text(encoding="utf-8")
    assert "collect_merkandi_b2b_liquidation_feed" in text
    assert 'merkandi-b2b-liquidation-feed.json' in text
    assert 'brief["merkandi_b2b_liquidation_feed"]' in text
    assert '"B2B_LEAD_REQUIRES_VERIFICATION"' in text
    assert '"automatic_purchase": False' in text
