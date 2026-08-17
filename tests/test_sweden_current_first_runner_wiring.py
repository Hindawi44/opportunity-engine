from scripts.run_market_clothing_inventory_discovery import select_market_runner


def test_sweden_market_selector_uses_current_first_runner():
    runner = select_market_runner("SE")
    assert runner.__module__ == (
        "scripts.run_sweden_clothing_inventory_discovery_search_current_first"
    )
