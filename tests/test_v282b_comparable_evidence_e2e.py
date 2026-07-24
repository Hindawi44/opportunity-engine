from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from opportunity_engine.evidence_store import EvidenceRepository
from opportunity_engine.external_financial_bridge import collect_external_financial_evidence
from opportunity_engine.external_market_comparables import ComparableCandidate, MarketComparablesEngine
from opportunity_engine.external_research.comparable_evidence import candidate_to_market_price_evidence


OPPORTUNITY_ID = "e2e-comparable-test"
NOW = datetime.now(timezone.utc).isoformat()


def candidate(title: str, url: str, price: float, *, currency: str = "NOK", similarity: float = 0.82):
    return SimpleNamespace(
        title=title,
        url=url,
        price_nok=price,
        price_currency=currency,
        source_name="V2.8.2B fixture",
        observed_at=NOW,
        similarity_score=similarity,
    )


def test_comparable_evidence_end_to_end(tmp_path) -> None:
    candidates = (
        candidate("Comparable A", "https://market-a.no/item/1", 10_000),
        candidate("Comparable B", "https://market-b.no/item/2", 12_000),
        candidate("Comparable C", "https://market-c.no/item/3", 14_000),
    )
    accepted = MarketComparablesEngine().analyse(candidates).accepted
    assert len(accepted) == 3

    repository = EvidenceRepository(tmp_path / "evidence")
    persisted_ids = [
        repository.upsert(candidate_to_market_price_evidence(item, OPPORTUNITY_ID)).evidence.evidence_id
        for item in accepted
    ]
    assert len(persisted_ids) == 3

    reloaded = [repository.load(OPPORTUNITY_ID, evidence_id) for evidence_id in persisted_ids]
    assert len(reloaded) == 3
    assert all(item.observations[0].numeric_value for item in reloaded)

    external = collect_external_financial_evidence(tmp_path / "evidence")
    verified = external[OPPORTUNITY_ID]["market_comparables"]
    assert len(verified) == 3

    summary = {
        "valid_price_candidates": len(accepted),
        "evidence_persisted": len(persisted_ids),
        "evidence_reloaded": len(reloaded),
        "verified_comparable_count": len(verified),
        "comparable_status": "COMPLETE" if len(verified) >= 3 else "INCOMPLETE",
    }
    assert summary == {
        "valid_price_candidates": 3,
        "evidence_persisted": 3,
        "evidence_reloaded": 3,
        "verified_comparable_count": 3,
        "comparable_status": "COMPLETE",
    }


@pytest.mark.parametrize(
    "bad_candidate",
    [
        candidate("Zero", "https://market-a.no/zero", 0),
        candidate("Missing URL", "", 1000),
        candidate("Placeholder", "https://unknown.no/item", 1000),
        candidate("Wrong currency", "https://market-a.no/eur", 1000, currency="EUR"),
        SimpleNamespace(
            title="Missing numeric value",
            url="https://market-a.no/missing",
            price_currency="NOK",
            source_name="fixture",
            observed_at=NOW,
            similarity_score=0.82,
        ),
    ],
)
def test_contract_rejects_invalid_comparables(bad_candidate) -> None:
    with pytest.raises(ValueError):
        candidate_to_market_price_evidence(bad_candidate, OPPORTUNITY_ID)
