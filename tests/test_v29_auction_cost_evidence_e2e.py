from __future__ import annotations

from datetime import datetime, timezone

import pytest

from opportunity_engine.evidence_store import EvidenceRepository
from opportunity_engine.external_financial_bridge import collect_external_financial_evidence
from opportunity_engine.external_research.auction_cost_evidence import candidate_to_auction_cost_evidence


OPPORTUNITY_ID = "e2e-auction-cost-test"
NOW = datetime.now(timezone.utc).isoformat()


def candidate(component: str, amount: float, url: str, *, zero: bool = False, currency: str = "NOK") -> dict:
    return {
        "component": component,
        "amount_nok": amount,
        "currency": currency,
        "source_url": url,
        "source_name": "Auction terms fixture",
        "observed_at": NOW,
        "basis": f"Published {component} term",
        "zero_cost_confirmed": zero,
    }


def test_six_cost_components_persist_reload_and_bridge(tmp_path) -> None:
    repository = EvidenceRepository(tmp_path / "evidence")
    candidates = (
        candidate("auction_price", 10000, "https://auction-one.no/lot/1"),
        candidate("auction_fee", 1500, "https://auction-one.no/terms/fees"),
        candidate("vat", 2875, "https://auction-one.no/terms/vat"),
        candidate("transport", 2200, "https://carrier-one.no/quote/1"),
        candidate("dismantling", 1200, "https://service-one.no/quote/1"),
        candidate("storage", 0, "https://warehouse-one.no/confirmation/1", zero=True),
    )

    persisted_ids = []
    for item in candidates:
        result = repository.upsert(candidate_to_auction_cost_evidence(item, OPPORTUNITY_ID))
        assert result.created is True
        persisted_ids.append(result.evidence.evidence_id)

    reloaded = repository.list_for_opportunity(OPPORTUNITY_ID)
    assert len(persisted_ids) == 6
    assert len(reloaded) == 6
    assert all(item.observations and item.observations[0].numeric_value is not None for item in reloaded)

    bridged = collect_external_financial_evidence(tmp_path / "evidence")[OPPORTUNITY_ID]
    assert bridged["auction_price_nok"] == 10000
    assert bridged["auction_fee_nok"] == 1500
    assert bridged["vat_nok"] == 2875
    assert bridged["transport_cost_nok"] == 2200
    assert bridged["dismantling_cost_nok"] == 1200
    assert bridged["storage_cost_nok"] == 0


@pytest.mark.parametrize(
    "payload",
    (
        candidate("auction_price", 0, "https://auction-one.no/lot/1"),
        {**candidate("auction_fee", 100, "https://auction-one.no/terms"), "source_url": ""},
        candidate("vat", 100, "https://unknown.no/item"),
        candidate("transport", 100, "http://carrier-one.no/quote"),
        candidate("dismantling", 100, "https://service-one.no/quote", currency="EUR"),
        {**candidate("storage", 0, "https://warehouse-one.no/confirmation"), "zero_cost_confirmed": False},
        {**candidate("auction_fee", 100, "https://auction-one.no/terms"), "basis": ""},
        {**candidate("auction_fee", 100, "https://auction-one.no/terms"), "amount_nok": None},
    ),
)
def test_invalid_cost_candidates_are_rejected(payload: dict) -> None:
    with pytest.raises(ValueError):
        candidate_to_auction_cost_evidence(payload, OPPORTUNITY_ID)
