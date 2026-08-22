from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from opportunity_engine.discovery.unified_market_intelligence_river import (
    build_unified_market_intelligence_river,
)
from opportunity_engine.promoted_source_production import (
    build_promoted_stocklear_feed,
    select_promoted_source_domains,
)


SCORECARD = {
    "source_domain": "joblot.stocklear.eu",
    "decision": "PROMOTE_CANDIDATE",
    "promotion_readiness_score": 100.0,
    "blocking_reasons": [],
    "production_active": False,
    "automatic_promotion": False,
}

PROMOTIONS = {
    "schema_version": "source-promotion-gate-1.0",
    "decisions": [
        {
            "source_domain": "joblot.stocklear.eu",
            "status": "PROMOTED",
            "reason": "Explicit operator approval after two independent 5/5 verified shadow rounds and stable public access.",
            "approved_at": "2026-08-22T15:48:00+02:00",
        }
    ],
}


def test_explicit_promotion_requires_proven_scorecard() -> None:
    assert select_promoted_source_domains(PROMOTIONS, SCORECARD) == {"joblot.stocklear.eu"}

    weak = dict(SCORECARD)
    weak["decision"] = "KEEP_SHADOW"
    assert select_promoted_source_domains(PROMOTIONS, weak) == set()


def test_disabled_decision_rolls_back_immediately() -> None:
    disabled = {**PROMOTIONS, "decisions": [{**PROMOTIONS["decisions"][0], "status": "DISABLED"}]}
    assert select_promoted_source_domains(disabled, SCORECARD) == set()


def test_config_cannot_invent_unproven_source() -> None:
    invented = {**PROMOTIONS, "decisions": [{**PROMOTIONS["decisions"][0], "source_domain": "example.invalid"}]}
    assert select_promoted_source_domains(invented, SCORECARD) == set()


def _promoted_feed() -> dict:
    index = """
    <html><body>
      <a href='/auction/30001/'>Lot 30001</a>
      <a href='/auction/30002/'>Lot 30002</a>
      <a href='/login'>Login</a>
    </body></html>
    """
    detail1 = """
    <html><head><title>111 Bosch Siemens appliances</title></head><body>
    Starting price 2,000 EUR. Number of pallets 2. 111 units.
    Quality: Functional customer returns. RRP 14,922 EUR.
    </body></html>
    """
    detail2 = """
    <html><head><title>Mixed household stock</title></head><body>
    Last bid 1,250 EUR. Number of pallets 4. 699 units.
    Quality: New in original packaging.
    </body></html>
    """
    pages = {
        "https://joblot.stocklear.eu/": index,
        "https://joblot.stocklear.eu/auction/30001": detail1,
        "https://joblot.stocklear.eu/auction/30002": detail2,
    }

    def fetcher(url: str) -> str:
        return pages[url.rstrip("/") if url != "https://joblot.stocklear.eu/" else url]

    return build_promoted_stocklear_feed(
        PROMOTIONS,
        SCORECARD,
        fetcher=fetcher,
        max_candidates=2,
        observed_at="2026-08-22T13:48:00+00:00",
    )


def test_promoted_stocklear_feed_is_exact_page_verified_and_bounded() -> None:
    report = _promoted_feed()

    assert report["status"] == "ACTIVE"
    assert report["production_source_active"] is True
    assert report["candidate_count"] == 2
    assert report["network_request_count"] == 3
    assert report["automatic_promotion"] is False
    assert report["explicit_promotion_required"] is True
    assert all(row["source_page_verified"] is True for row in report["candidates"])
    assert all(row["feed_family"] == "STOCKLEAR_PROMOTED_AUCTION_FEED_V1" for row in report["candidates"])


def test_promoted_feed_enters_unified_river_as_auction_inventory() -> None:
    report = _promoted_feed()
    artifacts = {
        "domain-market-intelligence-brief.json": {
            "generated_at": "2026-08-22T13:48:00+00:00",
            "current_direct_opportunities": [],
            "early_signals_to_watch": [],
        },
        "stocklear-promoted-source-feed.json": report,
    }
    river = build_unified_market_intelligence_river(
        artifacts,
        generated_at=datetime(2026, 8, 22, 13, 48, tzinfo=timezone.utc),
    )
    kinds = [row["record_kind"] for row in river["items"]["items"]]
    assert kinds == ["AUCTION_LOT", "AUCTION_LOT"]
    assert river["brief"]["counts"]["deduplicated_items"] == 2


def test_missing_or_disabled_promotion_performs_zero_network_requests() -> None:
    calls: list[str] = []

    def fetcher(url: str) -> str:
        calls.append(url)
        raise AssertionError("network must remain closed")

    disabled = {**PROMOTIONS, "decisions": [{**PROMOTIONS["decisions"][0], "status": "DISABLED"}]}
    report = build_promoted_stocklear_feed(disabled, SCORECARD, fetcher=fetcher)
    assert report["status"] == "DISABLED"
    assert report["production_source_active"] is False
    assert report["network_request_count"] == 0
    assert calls == []


def test_daily_cli_registers_promoted_source_after_river_for_lifo_order() -> None:
    root = Path(__file__).resolve().parents[1]
    init_text = (root / "src/opportunity_engine/discovery/__init__.py").read_text(encoding="utf-8")
    hook_text = (root / "src/opportunity_engine/discovery/promoted_stocklear_cli_hook.py").read_text(encoding="utf-8")
    assert "install_promoted_stocklear_cli_hook()" in init_text
    assert init_text.index("install_unified_market_intelligence_river_cli_hook()") < init_text.index(
        "install_promoted_stocklear_cli_hook()"
    )
    assert "stocklear-promoted-source-feed.json" in hook_text
    assert "river_module.INPUT_ARTIFACTS" in hook_text
