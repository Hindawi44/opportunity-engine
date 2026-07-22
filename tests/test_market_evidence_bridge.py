import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_opportunity_evidence_registry.py"
spec = importlib.util.spec_from_file_location("build_opportunity_evidence_registry", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def test_market_candidates_are_imported_as_pending_only() -> None:
    item = {
        "opportunity_id": "opp-1",
        "title": "Lagerreol",
        "url": "https://example.no/opp-1",
    }
    market = {
        "candidate_market_value_nok": 5000,
        "evidence_status": "REVIEW_REQUIRED",
        "review_reasons": ["quantity_not_confirmed_for_all_comparables"],
        "accepted_comparables": [
            {
                "source": "FINN",
                "url": "https://www.finn.no/item/1",
                "price_nok": 4900,
                "similarity_score": 0.8,
                "quantity_status": "UNKNOWN",
                "verified": False,
            }
        ],
    }

    record = module._normalize(item, {}, market)

    assert record["market_comparables"] == []
    assert len(record["pending_market_comparables"]) == 1
    assert record["pending_market_comparables"][0]["verified"] is False
    assert record["candidate_market_value_nok"] == 5000.0
    assert record["verified"] is False
    assert "pending_market_comparables_require_review" in record["missing_evidence"]


def test_verified_existing_comparables_are_preserved() -> None:
    item = {
        "opportunity_id": "opp-2",
        "title": "Butikkinnredning",
        "url": "https://example.no/opp-2",
    }
    existing = {
        "market_comparables": [
            {"source": "A", "url": "https://a.no/1", "price_nok": 1000, "verified": True},
            {"source": "B", "url": "https://b.no/2", "price_nok": 1100, "verified": True},
            {"source": "C", "url": "https://c.no/3", "price_nok": 1200, "verified": True},
        ],
        "vat_status": "included",
        "auction_fee_nok": 0,
        "vat_nok": 0,
        "transport_cost_nok": 0,
        "dismantling_cost_nok": 0,
        "storage_cost_nok": 0,
        "repair_cost_nok": 0,
        "other_costs_nok": 0,
    }

    record = module._normalize(item, existing, {})

    assert len(record["market_comparables"]) == 3
    assert record["pending_market_comparables"] == []
    assert record["verified"] is True
    assert record["missing_evidence"] == []
