from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DAILY = ROOT / "scripts" / "build_domain_market_intelligence_feed.py"
OPTIONAL = ROOT / "scripts" / "build_optional_market_intelligence_side_feeds.py"
WORKFLOW = ROOT / ".github" / "workflows" / "multi-market-daily-operator-checkpoint.yaml"

OPTIONAL_SIDE_FEED_COLLECTORS = (
    "collect_fabric_procurement_watch",
    "collect_fashion_stock_netherlands_feed",
    "collect_stockhurt_b2b_feed",
    "collect_stockhurt_official_catalog_enrichment",
    "collect_jobalots_clothing_auction_feed",
    "collect_jobalots_official_page_enrichment",
    "collect_jobalots_official_catalog_discovery",
)

OPTIONAL_SIDE_FEED_MODULES = (
    "fabric_procurement_watch",
    "fashion_stock_netherlands_feed",
    "stockhurt_b2b_feed",
    "stockhurt_official_catalog_enrichment",
    "jobalots_clothing_auction_feed",
    "jobalots_official_page_enrichment",
    "jobalots_official_catalog_discovery",
)


def test_daily_entrypoint_keeps_primary_scope_no_se_de_and_restores_only_bounded_de_b2b() -> None:
    text = DAILY.read_text(encoding="utf-8")

    assert "build_domain_market_intelligence_feed_core.py" in text
    assert "DEFAULT_DAILY_SCOPE_NO_SE_DE_ONLY" in text
    assert "DAILY_COMMERCIAL_FEEDS_RECONCILIATION_V1" in text
    assert "DAILY_B2B_SCOPE_DE_MERKANDI_ONLY" in text
    assert "from opportunity_engine.discovery.merkandi_b2b_liquidation_feed import" in text
    assert "collect_merkandi_b2b_liquidation_feed" in text
    assert '"search_lane_country": "DE"' in text
    assert '"stock_country_must_be_verified": True' in text

    for module in OPTIONAL_SIDE_FEED_MODULES:
        assert f"from opportunity_engine.discovery.{module} import" not in text


def test_daily_entrypoint_surfaces_bridal_clearance_without_promoting_it_to_top5() -> None:
    text = DAILY.read_text(encoding="utf-8")

    assert "bridal-liquidation-feed.json" in text
    assert 'brief["bridal_clearance_watch"]' in text
    assert '"top_bridal_clearance_signals"' in text
    assert '"not_part_of_opportunity_top5": True' in text
    assert '"promotion_to_opportunity_allowed": False' in text
    assert '"decision_owner": "HUMAN_OPERATOR"' in text


def test_optional_side_feed_implementation_is_preserved() -> None:
    text = OPTIONAL.read_text(encoding="utf-8")

    for collector in (
        "collect_fabric_procurement_watch",
        "collect_merkandi_b2b_liquidation_feed",
        *OPTIONAL_SIDE_FEED_COLLECTORS,
    ):
        assert collector in text
    assert "fabric-procurement-watch.json" in text
    assert "merkandi-b2b-liquidation-feed.json" in text
    assert "jobalots-official-catalog-discovery.json" in text


def test_automatic_checkpoint_uses_scoped_daily_entrypoint_and_not_full_optional_bundle() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "python scripts/build_domain_market_intelligence_feed.py" in text
    assert "build_optional_market_intelligence_side_feeds.py" not in text
    assert '"market_code": "NO"' in text
    assert '"market_code": "SE"' in text
    assert '"market_code": "DE"' in text
    for market in ('"market_code": "NL"', '"market_code": "PL"', '"market_code": "UK"'):
        assert market not in text
