import json
from pathlib import Path

from opportunity_engine.discovery.clothing_inventory_search import ACTIVE, ENDED
from opportunity_engine.discovery.germany_riegermann import (
    AGGREGATION_MODE,
    REQUIRES_VERIFICATION,
    UPCOMING,
    build_riegermann_adapter_result,
    canonicalize_riegermann_url,
    map_riegermann_lifecycle,
    parse_riegermann_catalog_html,
    parse_riegermann_item_html,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "riegermann"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_riegermann_url_contract_keeps_auction_and_object_identity_separate():
    information = canonicalize_riegermann_url(
        "https://www.riegermann.de/de/Versteigerung-Cabrini-GmbH/a/908?utm_source=test"
    )
    catalog = canonicalize_riegermann_url(
        "https://riegermann.de/de/objekte/au-908/versteigerung-cabrini-gmbh/"
    )
    item = canonicalize_riegermann_url(
        "https://www.riegermann.de/de/l/73457/damen-lederjacke-groesse-36"
    )

    assert information is not None
    assert information.kind == "AUCTION_INFORMATION"
    assert information.auction_id == "908"
    assert information.object_id is None
    assert information.canonical_url == (
        "https://riegermann.de/de/Versteigerung-Cabrini-GmbH/a/908"
    )

    assert catalog is not None
    assert catalog.kind == "AUCTION_CATALOG"
    assert catalog.auction_id == "908"

    assert item is not None
    assert item.kind == "ITEM_DETAIL"
    assert item.object_id == "73457"
    assert item.auction_id is None

    assert canonicalize_riegermann_url("https://example.de/de/l/73457/item") is None
    assert canonicalize_riegermann_url("https://riegermann.de/de/Auktionen/alle") is None


def test_lifecycle_mapping_is_explicit_and_fail_closed():
    assert map_riegermann_lifecycle("Aktuell – Jetzt bieten") == ACTIVE
    assert map_riegermann_lifecycle("Auktion beendet") == ENDED
    assert map_riegermann_lifecycle("Nachverkauf") == REQUIRES_VERIFICATION
    assert map_riegermann_lifecycle("Vorschau") == UPCOMING
    assert map_riegermann_lifecycle("Allgemeine Informationen") == "UNKNOWN"


def test_active_catalog_builds_one_parent_and_only_one_bulk_candidate():
    event = parse_riegermann_catalog_html(
        "https://riegermann.de/de/objekte/au-908/versteigerung-cabrini-gmbh",
        _fixture("cabrini_active_catalog.html"),
    )

    assert event.auction_id == "908"
    assert event.opportunity_identity == "riegermann-auction:908"
    assert event.title == "Versteigerung Cabrini GmbH"
    assert event.listing_status == ACTIVE
    assert event.scenario == "INVENTORY_LIQUIDATION"
    assert event.location == "DE-55450 Langenlonsheim"
    assert event.buyer_premium_percent == 20.0
    assert event.vat_percent == 19.0
    assert len(event.child_lots) == 3
    assert len(event.ordinary_child_lots) == 2
    assert len(event.promoted_bulk_lots) == 1

    ordinary = next(lot for lot in event.child_lots if lot.object_id == "73457")
    assert ordinary.ordinary_single_garment is True
    assert ordinary.promotion_eligible is False
    assert ordinary.top5_eligible is False
    assert ordinary.source_price_kind == "MINIMUM_PRICE"
    assert ordinary.source_start_or_minimum_price_eur == 25.0
    assert ordinary.source_displayed_bid_eur is None
    assert ordinary.price_nok is None
    assert ordinary.bid_price_nok is None

    bulk = event.promoted_bulk_lots[0]
    assert bulk.object_id == "73490"
    assert bulk.quantity == 24
    assert bulk.bulk_evidence is True
    assert bulk.promotion_eligible is True
    assert bulk.top5_eligible is False
    assert bulk.source_price_kind == "START_PRICE"
    assert bulk.source_start_or_minimum_price_eur == 300.0
    assert bulk.source_bid_count == 2
    assert bulk.source_displayed_bid_eur == 420.0
    assert bulk.normalized_price_eur is None

    result = build_riegermann_adapter_result(event)
    discovery = result.to_discovery_result()

    assert result.parent_candidate["opportunity_identity"] == "riegermann-auction:908"
    assert result.parent_candidate["aggregation_mode"] == AGGREGATION_MODE
    assert result.parent_candidate["child_lot_count"] == 3
    assert result.parent_candidate["ordinary_child_lot_count"] == 2
    assert result.parent_candidate["promoted_bulk_lot_count"] == 1
    assert result.parent_candidate["top5_eligible"] is False
    assert result.parent_candidate["price_nok"] is None
    assert result.parent_candidate["bid_price_nok"] is None

    assert len(result.promoted_bulk_candidates) == 1
    promoted = result.promoted_bulk_candidates[0]
    assert promoted["opportunity_identity"] == "riegermann-object:73490"
    assert promoted["parent_opportunity_identity"] == "riegermann-auction:908"
    assert promoted["top5_eligible"] is False
    assert promoted["price"] is None
    assert promoted["price_nok"] is None
    assert promoted["bid_price_nok"] is None
    assert promoted["source_displayed_bid_eur"] == 420.0

    emitted_identities = {
        candidate["opportunity_identity"]
        for candidate in discovery["all_discovered_candidates"]
    }
    assert emitted_identities == {
        "riegermann-auction:908",
        "riegermann-object:73490",
    }
    assert "riegermann-object:73457" not in emitted_identities
    assert discovery["discovery_top5"] == []
    assert discovery["source_adapter"]["single_garment_candidate_count"] == 0
    assert discovery["source_adapter"]["nok_price_fields_written"] is False


def test_sold_item_requires_explicit_sold_and_price_markers():
    lot = parse_riegermann_item_html(
        "https://riegermann.de/de/l/73490/posten-lederjacken-24-stueck",
        _fixture("sold_bulk_item.html"),
        auction_id="908",
    )

    assert lot.listing_status == ENDED
    assert lot.promotion_eligible is True
    assert lot.final_sale_price_eur == 650.0
    assert lot.final_sale_price_trusted is True
    assert lot.source_start_or_minimum_price_eur == 300.0
    assert lot.normalized_price_eur is None
    assert lot.price_nok is None


def test_not_sold_is_not_interpreted_as_zero_or_final_price():
    lot = parse_riegermann_item_html(
        "https://riegermann.de/de/l/73457/damen-lederjacke-groesse-36",
        _fixture("unsold_single_item.html"),
        auction_id="908",
    )

    assert lot.listing_status == ENDED
    assert lot.ordinary_single_garment is True
    assert lot.promotion_eligible is False
    assert lot.final_sale_price_eur is None
    assert lot.final_sale_price_trusted is False
    assert lot.source_start_or_minimum_price_eur == 25.0


def test_source_contract_is_active_and_still_fail_closed():
    contract = json.loads(
        (ROOT / "config" / "sources" / "de_riegermann_v1.json").read_text(
            encoding="utf-8"
        )
    )

    assert contract["runtime_status"] == "ACTIVE"
    assert contract["aggregation_contract"]["mode"] == AGGREGATION_MODE
    assert contract["aggregation_contract"]["promote_single_garment_lot"] is False
    assert contract["price_contract"]["fx_conversion_enabled"] is False
    assert contract["activation_validation"]["catalog_item_url_count"] == 869
    assert contract["activation_validation"]["catalog_coverage_complete"] is True
    assert contract["activation_validation"]["single_garment_candidate_count"] == 0
    assert contract["activation_validation"]["top5_count"] == 0
    assert contract["activation_validation"]["production_ready"] is True
