from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DAILY = ROOT / "scripts/build_domain_market_intelligence_feed.py"
OPTIONAL = ROOT / "scripts/build_optional_market_intelligence_side_feeds.py"
WORKFLOW = ROOT / ".github/workflows/multi-market-daily-operator-checkpoint.yaml"
ARCHIVE = ROOT / "docs/archive/legacy-six-market-checkpoint-20260919.yaml.txt"

OPTIONAL_SIDE_FEED_COLLECTORS = (
    "collect_fabric_procurement_watch", "collect_fashion_stock_netherlands_feed",
    "collect_stockhurt_b2b_feed", "collect_stockhurt_official_catalog_enrichment",
    "collect_jobalots_clothing_auction_feed", "collect_jobalots_official_page_enrichment",
    "collect_jobalots_official_catalog_discovery",
)
OPTIONAL_SIDE_FEED_MODULES = (
    "fabric_procurement_watch", "fashion_stock_netherlands_feed", "stockhurt_b2b_feed",
    "stockhurt_official_catalog_enrichment", "jobalots_clothing_auction_feed",
    "jobalots_official_page_enrichment", "jobalots_official_catalog_discovery",
)


def test_historical_daily_entrypoint_and_side_feed_separation_are_preserved() -> None:
    text = DAILY.read_text(encoding="utf-8")
    for marker in ("build_domain_market_intelligence_feed_core.py", "DEFAULT_DAILY_SCOPE_NO_SE_DE_ONLY",
                   "DAILY_COMMERCIAL_FEEDS_RECONCILIATION_V1", "DAILY_B2B_SCOPE_DE_MERKANDI_ONLY",
                   "collect_merkandi_b2b_liquidation_feed", '"search_lane_country": "DE"',
                   '"stock_country_must_be_verified": True'):
        assert marker in text
    for module in OPTIONAL_SIDE_FEED_MODULES:
        assert f"from opportunity_engine.discovery.{module} import" not in text


def test_historical_daily_entrypoint_does_not_promote_bridal_clearance() -> None:
    text = DAILY.read_text(encoding="utf-8")
    for marker in ("bridal-liquidation-feed.json", 'brief["bridal_clearance_watch"]',
                   '"top_bridal_clearance_signals"', '"not_part_of_opportunity_top5": True',
                   '"promotion_to_opportunity_allowed": False', '"decision_owner": "HUMAN_OPERATOR"'):
        assert marker in text


def test_optional_side_feed_implementation_is_preserved() -> None:
    text = OPTIONAL.read_text(encoding="utf-8")
    for collector in ("collect_fabric_procurement_watch", "collect_merkandi_b2b_liquidation_feed",
                      *OPTIONAL_SIDE_FEED_COLLECTORS):
        assert collector in text
    assert "fabric-procurement-watch.json" in text
    assert "merkandi-b2b-liquidation-feed.json" in text
    assert "jobalots-official-catalog-discovery.json" in text


def test_six_market_bulletin_is_archived_and_not_called_by_norway_daily() -> None:
    old = ARCHIVE.read_text(encoding="utf-8")
    active = WORKFLOW.read_text(encoding="utf-8")
    assert "python scripts/build_domain_market_intelligence_feed.py" in old
    assert '"source_name": "Exa Exact-Lot NL"' in old
    assert active.startswith("name: Norway Opportunity Hunter\n")
    assert "python scripts/build_domain_market_intelligence_feed.py" not in active
    assert "build_optional_market_intelligence_side_feeds.py" not in active
    assert "run_event_first_hunter_pilot.py" in active
    assert "--live --lookback-days 1" in active
