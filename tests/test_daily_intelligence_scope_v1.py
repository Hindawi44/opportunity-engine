from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DAILY = ROOT / "scripts" / "build_domain_market_intelligence_feed.py"
OPTIONAL = ROOT / "scripts" / "build_optional_market_intelligence_side_feeds.py"
WORKFLOW = ROOT / ".github" / "workflows" / "multi-market-daily-operator-checkpoint.yaml"

SIDE_FEED_COLLECTORS = (
    "collect_fabric_procurement_watch",
    "collect_merkandi_b2b_liquidation_feed",
    "collect_fashion_stock_netherlands_feed",
    "collect_stockhurt_b2b_feed",
    "collect_stockhurt_official_catalog_enrichment",
    "collect_jobalots_clothing_auction_feed",
    "collect_jobalots_official_page_enrichment",
    "collect_jobalots_official_catalog_discovery",
)


def test_daily_entrypoint_delegates_to_no_se_de_core_only() -> None:
    text = DAILY.read_text(encoding="utf-8")

    assert "build_domain_market_intelligence_feed_core.py" in text
    assert "DEFAULT_DAILY_SCOPE_NO_SE_DE_ONLY" in text
    assert "build_optional_market_intelligence_side_feeds.py" in text
    assert "from opportunity_engine.discovery.fabric_procurement_watch import" not in text
    assert "from opportunity_engine.discovery.merkandi_b2b_liquidation_feed import" not in text
    assert "from opportunity_engine.discovery.fashion_stock_netherlands_feed import" not in text
    assert "from opportunity_engine.discovery.stockhurt_b2b_feed import" not in text
    assert "from opportunity_engine.discovery.jobalots_clothing_auction_feed import" not in text
    assert "def _run(" not in text
    assert "collector(environment=os.environ)" not in text


def test_optional_side_feed_implementation_is_preserved() -> None:
    text = OPTIONAL.read_text(encoding="utf-8")

    for collector in SIDE_FEED_COLLECTORS:
        assert collector in text
    assert "fabric-procurement-watch.json" in text
    assert "merkandi-b2b-liquidation-feed.json" in text
    assert "jobalots-official-catalog-discovery.json" in text


def test_automatic_checkpoint_uses_scoped_daily_entrypoint_only() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "python scripts/build_domain_market_intelligence_feed.py" in text
    assert "build_optional_market_intelligence_side_feeds.py" not in text
    assert '"market_code": "NO"' in text
    assert '"market_code": "SE"' in text
    assert '"market_code": "DE"' in text
    for market in ('"market_code": "NL"', '"market_code": "PL"', '"market_code": "UK"'):
        assert market not in text
