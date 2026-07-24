from opportunity_engine.discovery.classifier import classify_candidate, to_canonical_opportunity
from opportunity_engine.discovery.models import DiscoveryCandidate

NOW = "2026-07-24T15:30:00+00:00"


def candidate(title: str, text: str = "", *, price=None, url="https://example.no/item"):
    return DiscoveryCandidate(
        title=title,
        text=text,
        url=url,
        source="Public Web",
        discovered_at=NOW,
        location="Oslo",
        price_nok=price,
    )


def test_confirmed_inventory_sale_enters_canonical_boundary():
    result = classify_candidate(candidate("Vareparti klær til salgs", "Komplett klesparti selges", price=25000))
    assert result.status == "SALE_CONFIRMED"
    assert result.record_type == "SALE_LISTING"
    canonical = to_canonical_opportunity(result)
    assert canonical is not None
    assert canonical["source"]["asking_price_nok"] == 25000
    assert canonical["verified_cost_evidence"]["vat_nok"] is None
    assert canonical["automatic_purchase_decision"] is False


def test_bankruptcy_notice_stays_outside_analysis_until_sale_confirmed():
    result = classify_candidate(candidate("Konkurs klesbutikk", "Konkursbo klær i Oslo"))
    assert result.status == "CONTACT_REQUIRED"
    assert result.record_type == "BANKRUPTCY_LEAD"
    assert to_canonical_opportunity(result) is None


def test_store_closure_with_sale_signal_is_confirmed_sale():
    result = classify_candidate(candidate("Klesbutikk avvikling", "Alt skal bort, hele lageret selges"))
    assert result.status == "SALE_CONFIRMED"
    assert result.record_type == "SALE_LISTING"


def test_single_used_garment_is_rejected():
    result = classify_candidate(candidate("Brukt jakke", "Fin jakke i størrelse M", price=500))
    assert result.status == "REJECTED"
    assert result.record_type == "REJECTED_RESULT"
    assert to_canonical_opportunity(result) is None


def test_missing_data_remains_unknown_not_invented():
    result = classify_candidate(candidate("Restlager klær selges", "Restlager klær"))
    canonical = to_canonical_opportunity(result)
    assert canonical is not None
    assert canonical["source"]["asking_price_nok"] is None
    assert canonical["discovery_data"]["quantity"] is None
    assert canonical["discovery_data"]["contact"] is None
