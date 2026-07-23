import pytest

from opportunity_engine.buyer_discovery import (
    BuyerCandidate,
    BuyerDiscoveryEngine,
    BuyerType,
)


def candidate(**overrides):
    data = {
        "name": "Nordic Shop Equipment",
        "website_url": "https://buyer.example.no",
        "buyer_type": BuyerType.SPECIALIST_DEALER,
        "source_url": "https://source.example.no/company",
        "source_name": "Brave Search",
        "rationale": "Company sells and buys shop equipment.",
        "location": "Trøndelag",
        "contact_url": "https://buyer.example.no/contact",
        "matched_terms": ("butikkinnredning", "hyller"),
        "scenario_ids": ("generated-v251-brokerage",),
        "evidence_score": 80.0,
    }
    data.update(overrides)
    return BuyerCandidate(**data)


def test_ranks_relevant_buyer_and_preserves_reasoning():
    result = BuyerDiscoveryEngine().discover(
        [candidate()],
        opportunity_terms=("butikkinnredning", "hyller"),
        opportunity_location="Trøndelag",
        required_scenario_ids=("generated-v251-brokerage",),
    )
    assert len(result.accepted) == 1
    ranked = result.accepted[0]
    assert ranked.fit_score >= 75
    assert ranked.confidence.value == "high"
    assert any("Matched 2 of 2" in reason for reason in ranked.reasons)


def test_rejects_low_fit_candidate():
    result = BuyerDiscoveryEngine().discover(
        [candidate(matched_terms=(), buyer_type=BuyerType.OTHER, location="Oslo", contact_url=None, evidence_score=None)],
        opportunity_terms=("industrisymaskin", "overlock"),
        opportunity_location="Trøndelag",
        required_scenario_ids=("generated-v251-purchase",),
    )
    assert not result.accepted
    assert result.rejected[0][1] == "fit_below_threshold"


def test_deduplicates_by_company_domain():
    first = candidate()
    second = candidate(name="Same company result", source_url="https://other.example.no", website_url="https://www.buyer.example.no/about")
    result = BuyerDiscoveryEngine().discover(
        [first, second], opportunity_terms=("butikkinnredning", "hyller")
    )
    assert result.duplicate_count == 1
    assert len(result.accepted) == 1


def test_does_not_require_or_invent_contact_details():
    item = candidate(contact_url=None, email=None, phone=None)
    result = BuyerDiscoveryEngine().discover(
        [item], opportunity_terms=("butikkinnredning", "hyller"), minimum_fit_score=0
    )
    assert result.accepted[0].candidate.email is None
    assert "No public contact channel supplied" in result.accepted[0].warnings


def test_validates_urls_and_evidence_score():
    with pytest.raises(ValueError):
        candidate(website_url="http://buyer.example.no")
    with pytest.raises(ValueError):
        candidate(evidence_score=101)


def test_direction_is_discovery_only_not_automatic_contact():
    item = candidate(email="sales@buyer.example.no")
    result = BuyerDiscoveryEngine().discover(
        [item], opportunity_terms=("butikkinnredning", "hyller"), minimum_fit_score=0
    )
    assert result.accepted[0].candidate.email == "sales@buyer.example.no"
    assert not hasattr(result.accepted[0], "contact_sent")
