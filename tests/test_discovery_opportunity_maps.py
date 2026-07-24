from opportunity_engine.discovery.opportunity_maps import CLOTHING_INVENTORY_MAP
from opportunity_engine.discovery.query_builder import build_clothing_inventory_queries


def test_clothing_inventory_map_covers_blueprint_scenarios():
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


def test_query_builder_is_traceable_and_deduplicated():
    queries = build_clothing_inventory_queries()
    assert len(queries) >= 30
    assert len({item["query"].lower() for item in queries}) == len(queries)
    assert all(item["domain"] == "CLOTHING_INVENTORY" for item in queries)
    assert all(item["scenario"] in CLOTHING_INVENTORY_MAP for item in queries)
    assert all(item["query"].endswith("Norge") for item in queries)
