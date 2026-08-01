import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "config" / "sources" / "de_riegermann_v1.json"
AUDIT_PATH = ROOT / "docs" / "RIEGERMANN_PUBLIC_ACCESS_AUDIT_v1.md"
PLAN_PATH = ROOT / "config" / "source_expansion_plan.json"


def _riegermann_plan_entry() -> dict:
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    germany = next(row for row in plan["markets"] if row["market"] == "Germany")
    return next(row for row in germany["sources"] if row["source"] == "Riegermann")


def test_riegermann_audit_keeps_source_planned_until_adapter_exists() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    plan_entry = _riegermann_plan_entry()

    assert contract["source_id"] == "DE_RIEGERMANN_V1"
    assert contract["market_code"] == "DE"
    assert contract["currency_code"] == "EUR"
    assert contract["runtime_status"] == "PLANNED"
    assert contract["audit_decision"] == "GO_FOR_BOUNDED_EVENT_ADAPTER"

    assert plan_entry["audit_status"] == "PLANNED"
    assert plan_entry["public_access_audit"] == "GO_FOR_BOUNDED_EVENT_ADAPTER"
    assert plan_entry["source_contract"] == "config/sources/de_riegermann_v1.json"
    assert plan_entry["audit_document"] == "docs/RIEGERMANN_PUBLIC_ACCESS_AUDIT_v1.md"


def test_riegermann_url_and_identity_contracts_are_stable_and_bounded() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    urls = contract["url_contract"]
    identity = contract["identity_contract"]

    assert set(contract["access"]["accepted_hosts"]) == {
        "riegermann.de",
        "www.riegermann.de",
    }
    assert urls["auction_information_path_regex"].endswith("(?P<auction_id>[0-9]+)$")
    assert "au-(?P<auction_id>[0-9]+)" in urls["auction_catalog_path_regex"]
    assert "(?P<object_id>[0-9]+)" in urls["item_detail_path_regex"]

    assert identity["auction_identity"] == "riegermann-auction:<auction_id>"
    assert identity["item_identity"] == "riegermann-object:<object_id>"
    assert identity["lot_number_is_globally_unique"] is False
    assert identity["object_id_is_required_for_item_deduplication"] is True


def test_riegermann_aggregation_prevents_single_garment_flooding() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    aggregation = contract["aggregation_contract"]

    assert aggregation["mode"] == "AUCTION_EVENT_WITH_CHILD_LOTS"
    assert aggregation["promote_auction_event"] is True
    assert aggregation["promote_single_garment_lot"] is False
    assert aggregation["promote_explicit_bulk_lot"] is True
    assert aggregation["single_garment_top5_eligible"] is False
    assert aggregation["bulk_lot_requires_quantity_or_posten_wording"] is True


def test_riegermann_price_and_safety_contracts_fail_closed() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    prices = contract["price_contract"]
    safety = contract["safety_contract"]

    assert prices["source_currency"] == "EUR"
    assert prices["startpreis_is_current_sale_price"] is False
    assert prices["mindestpreis_is_current_sale_price"] is False
    assert prices["active_displayed_bid_requires_bid_count"] is True
    assert prices["final_price_requires_explicit_sold_marker"] is True
    assert prices["normalized_price_enabled"] is False
    assert prices["fx_conversion_enabled"] is False
    assert prices["vat_calculation_enabled"] is False
    assert prices["premium_calculation_enabled"] is False

    assert all(value is False for value in safety.values())


def test_riegermann_audit_documents_live_cabrini_evidence_and_acceptance_gate() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    evidence = contract["known_current_evidence"]
    audit = AUDIT_PATH.read_text(encoding="utf-8")

    assert evidence["auction_title"] == "Versteigerung Cabrini GmbH"
    assert evidence["auction_id"] == "908"
    assert evidence["sample_item_object_id"] == "73457"
    assert evidence["sample_item_lot_number"] == "410"
    assert evidence["buyer_premium_percent"] == 20
    assert evidence["vat_percent"] == 19

    assert "GO_FOR_BOUNDED_EVENT_ADAPTER" in audit
    assert "AUCTION_EVENT_WITH_CHILD_LOTS" in audit
    assert "riegermann-auction:<auction-id>" in audit
    assert "riegermann-object:<object-id>" in audit
    assert "single jacket" in audit
    assert "EUR-to-NOK conversion" in audit
    assert "zero accepted opportunities remains a valid run result" in audit
