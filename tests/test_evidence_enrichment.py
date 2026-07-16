from __future__ import annotations

from opportunity_engine.ods.evidence_enrichment import EvidenceBand, enrich_feed_item
from opportunity_engine.ods.live_feed import FeedItem


def _item(evidence: tuple[str, ...]) -> FeedItem:
    return FeedItem(
        opportunity_id="opp-1",
        title="Example AS",
        category="business_status_lead",
        description="Official status lead.",
        source="brreg_status_extractor",
        discovered_at="2026-01-01T00:00:00+00:00",
        last_seen_at="2026-01-01T00:00:00+00:00",
        times_seen=1,
        score=70.0,
        status="NEW",
        evidence=evidence,
    )


def test_brreg_only_evidence_stays_partial_and_blocks_profit_claims() -> None:
    result = enrich_feed_item(
        _item((
            "official-status:liquidation",
            "organisation-number:123456789",
            "municipality:NAMSOS",
            "https://data.brreg.no/example",
        ))
    )
    assert result.band is EvidenceBand.PARTIAL
    assert result.independent_sources == 1
    assert "Comparable market-price evidence" in result.missing_evidence
    assert any("Do not estimate profit" in value for value in result.blockers)


def test_multiple_documented_sources_can_reach_strong_band() -> None:
    result = enrich_feed_item(
        _item((
            "official-status:liquidation",
            "organisation-number:123456789",
            "municipality:NAMSOS",
            "market-price:Comparable sales documented",
            "asset-listing:Verified auction listing",
            "financials:Transport and fees documented",
        ))
    )
    assert result.band is EvidenceBand.STRONG
    assert result.independent_sources >= 2
    assert result.completeness == 100.0
    assert result.missing_evidence == ()


def test_unknown_evidence_does_not_inflate_score() -> None:
    result = enrich_feed_item(_item(("unverified-claim:high profit",)))
    assert result.evidence_score == 0.0
    assert result.band is EvidenceBand.WEAK
