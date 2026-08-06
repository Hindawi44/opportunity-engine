from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from opportunity_engine.discovery.jobalots_clothing_auction_feed import (
    APPROVED_DOMAINS,
    FEED_FAMILY,
    QUERIES,
    collect_jobalots_clothing_auction_feed,
    jobalots_candidate_from_hit,
)
from opportunity_engine.discovery.search_provider import SearchHit

NOW = datetime(2026, 8, 6, 6, 30, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = ROOT / "scripts/build_domain_market_intelligence_feed.py"


def _active_lot() -> SearchHit:
    return SearchHit(
        title=(
            "Clothing customer returns job lot — 12000 items — "
            "3 pallets — Current bid £750 — RRP £15000"
        ),
        url=(
            "https://jobalots.com/en/products/CLOTHING-LOT-12000"
            "?currency=gbp&utm_source=test"
        ),
        description=(
            "Wholesale clothing and footwear auction. Full manifest with itemised "
            "contents. Customer returns. Warehouse location: Germany. Original "
            "stock. EU delivery available. Auction ends: 9 August 2026 18:00."
        ),
        provider="Brave Search",
    )


def _unmanifested_lot() -> SearchHit:
    return SearchHit(
        title="Pallet of unmanifested clothing customer returns",
        url="https://jobalots.com/en/products/BLACK-CLOTHING-RETURNS",
        description=(
            "Wholesale job lot pallet with womens clothing and footwear. "
            "Unmanifested customer returns; place bid after checking the lot page."
        ),
        provider="Brave Search",
    )


def test_official_domain_and_bounded_queries_are_explicit() -> None:
    assert APPROVED_DOMAINS == ("jobalots.com",)
    assert len(QUERIES) == 2
    assert all("site:jobalots.com" in query for query in QUERIES)


def test_preserves_large_active_clothing_lot_for_human_decision() -> None:
    candidate = jobalots_candidate_from_hit(_active_lot(), observed_at=NOW)

    assert candidate is not None
    assert candidate["feed_family"] == FEED_FAMILY
    assert candidate["page_role"] == "SPECIFIC_AUCTION_OR_JOB_LOT"
    assert candidate["listing_status"] == "ACTIVE_REQUIRES_VERIFICATION"
    assert candidate["quantity"] == 12000
    assert candidate["quantity_unit"] == "units"
    assert candidate["lot_units"] == 3
    assert candidate["lot_unit_type"] == "pallets"
    assert candidate["lot_size_band"] == "VERY_LARGE"
    assert candidate["current_bid"] == 750
    assert candidate["currency"] == "GBP"
    assert candidate["estimated_retail_value"] == 15000
    assert candidate["estimated_retail_currency"] == "GBP"
    assert candidate["manifest_available"] is True
    assert candidate["opportunity_state"] == "B2B_LEAD_REQUIRES_VERIFICATION"
    assert candidate["decision_owner"] == "HUMAN_OPERATOR"
    assert candidate["quantity_size_rejection_applied"] is False
    assert candidate["automatic_bid"] is False
    assert candidate["automatic_purchase"] is False


def test_preserves_unmanifested_incomplete_lot_as_early_signal() -> None:
    candidate = jobalots_candidate_from_hit(_unmanifested_lot(), observed_at=NOW)

    assert candidate is not None
    assert candidate["manifest_available"] is False
    assert candidate["unmanifested_terms"] == ["unmanifested"]
    assert "MANIFEST_OR_ITEMISED_CONTENTS" in candidate["missing_information"]
    assert candidate["opportunity_state"] == (
        "EARLY_B2B_SIGNAL_REQUIRES_VERIFICATION"
    )
    assert candidate["automatic_bid"] is False


def test_ended_clothing_lot_remains_historical_signal() -> None:
    candidate = jobalots_candidate_from_hit(
        SearchHit(
            title="Auction ended — clothing pallet — 189 items — RRP £3402",
            url="https://classic.jobalots.com/products/mos3591",
            description=(
                "Brand new clothing hoodies job lot. Download manifest. "
                "This auction has ended."
            ),
            provider="Brave Search",
        ),
        observed_at=NOW,
    )

    assert candidate is not None
    assert candidate["listing_status"] == "ENDED"
    assert candidate["opportunity_state"] == (
        "EARLY_B2B_SIGNAL_REQUIRES_VERIFICATION"
    )


def test_rejects_impostor_domain_and_non_clothing_lot() -> None:
    active = _active_lot()
    assert jobalots_candidate_from_hit(
        SearchHit(
            title=active.title,
            url="https://jobalots-fake.example/en/products/lot",
            description=active.description,
        ),
        observed_at=NOW,
    ) is None

    assert jobalots_candidate_from_hit(
        SearchHit(
            title="Pallet of garden tools customer returns",
            url="https://jobalots.com/en/products/GARDEN-TOOLS-1",
            description="Wholesale auction pallet with full manifest and current bid £10.",
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
        return [_active_lot()] if "/en/products/" in query else [_unmanifested_lot()]


def test_collection_is_bounded_to_two_official_domain_queries() -> None:
    providers: list[FakeProvider] = []

    def factory(country: str, api_key: str, freshness: str | None) -> FakeProvider:
        assert country == "GB"
        assert api_key == "secret"
        assert freshness == "pm"
        provider = FakeProvider()
        providers.append(provider)
        return provider

    report = collect_jobalots_clothing_auction_feed(
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
    assert report["ended_lots_preserved"] is True
    assert report["unmanifested_lots_preserved"] is True
    assert len(providers[0].calls) == 2


def test_missing_key_is_explicit_and_makes_no_request() -> None:
    def forbidden_factory(*args, **kwargs):
        raise AssertionError("provider must not be initialized")

    report = collect_jobalots_clothing_auction_feed(
        observed_at=NOW,
        environment={},
        provider_factory=forbidden_factory,
    )

    assert report["requests_made"] == 0
    assert report["status_counts"] == {"BLOCKED_CONFIGURATION": 1}


def test_builder_writes_and_attaches_jobalots_feed() -> None:
    text = BUILD_SCRIPT.read_text(encoding="utf-8")
    assert "collect_jobalots_clothing_auction_feed" in text
    assert 'jobalots-clothing-auction-feed.json' in text
    assert 'brief["jobalots_clothing_auction_feed"]' in text
    assert '"HUMAN_OPERATOR"' in text
    assert '"automatic_bid": False' in text
    assert '"automatic_purchase": False' in text
