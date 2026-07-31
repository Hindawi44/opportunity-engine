from opportunity_engine.discovery.norway_textile_keywords import (
    DOMAIN,
    NORWAY_TEXTILE_CATEGORIES,
    build_norway_textile_keyword_queries,
)
from opportunity_engine.discovery.opportunity_maps import CLOTHING_INVENTORY_MAP
from opportunity_engine.discovery.query_builder import build_clothing_inventory_queries
from opportunity_engine.discovery.textile_taxonomy import OpportunityCategory


def test_clothing_inventory_map_preserves_existing_event_scenarios():
    assert set(CLOTHING_INVENTORY_MAP) == {
        "STORE_CLOSING",
        "COMPANY_BANKRUPTCY",
        "INVENTORY_LIQUIDATION",
        "AUCTION",
        "WAREHOUSE_SURPLUS",
        "IMPORTER_LIQUIDATION",
        "MANUFACTURER_EXCESS",
        "LARGE_LOT_SALE",
        "BUSINESS_MODEL_CHANGE",
        "BRANCH_CLOSURE",
    }
    assert all(CLOTHING_INVENTORY_MAP.values())


def test_query_builder_uses_bounded_expanded_keyword_pack():
    queries = build_clothing_inventory_queries()
    specs = build_norway_textile_keyword_queries()

    assert len(queries) == len(specs) == 16
    assert len({item["query"].casefold() for item in queries}) == len(queries)
    assert all(item["domain"] == DOMAIN for item in queries)
    assert all(item["query"].endswith("Norge") for item in queries)
    assert {item["category"] for item in queries} == NORWAY_TEXTILE_CATEGORIES
    assert NORWAY_TEXTILE_CATEGORIES == {category.value for category in OpportunityCategory}
    assert all(item["event_term"] in item["query"] for item in queries)
    assert all(item["sector_term"] in item["query"] for item in queries)
    assert all(item["asset_term"] in item["query"] for item in queries)
