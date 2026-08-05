from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import json

from sqlalchemy import inspect

from opportunity_engine.discovery.brave_market_signal_radar import (
    MARKET_QUERIES,
    collect_manifest_brave_market_signals,
    market_signal_from_brave_hit,
)
from opportunity_engine.discovery.domain_market_intelligence_feed import (
    build_domain_market_intelligence_brief,
    market_signal_from_opportunity_record,
    persist_manifest_market_signals,
)
from opportunity_engine.discovery.phone_readable_market_bulletin import (
    enrich_phone_readable_market_bulletin,
    render_phone_readable_market_bulletin,
)
from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.persistence import (
    MarketSignalRepository,
    create_database_engine,
    create_session_factory,
    session_scope,
    upgrade_database,
)


ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_CONFIG = ROOT / "alembic.ini"


def _signal(**overrides) -> dict:
    payload = {
        "signal_id": "closure:NO:example-shop",
        "signal_type": "BUSINESS_CLOSURE",
        "value": "A clothing shop announced that the business will close.",
        "source": "Example Registry",
        "observed_at": "2026-08-03T08:00:00Z",
        "confidence": 0.8,
        "source_country": "NO",
        "source_url": "https://example.test/closure/1",
        "title": "Example clothing shop closing",
        "company_name": "Example AS",
        "seller_name": None,
        "location": "Trondheim",
        "first_observed_at": "2026-08-03T08:00:00Z",
        "latest_observed_at": "2026-08-03T08:00:00Z",
        "event_date": None,
        "evidence": [],
        "related_opportunity_id": None,
        "status": "WATCH",
        "metadata": {"signal_only": True},
    }
    payload.update(overrides)
    return payload


def _opportunity_record() -> dict:
    return {
        "opportunity_id": "auction:lot:1",
        "market_code": "SE",
        "domain": "TEXTILE_AND_SEWING",
        "category": "CLOTHING_INVENTORY",
        "title": "58 workwear trousers",
        "source_provider": "Blinto",
        "source_url": "https://example.test/auction/1",
        "listing_status": "ACTIVE",
        "evaluation_status": "REQUIRES_VERIFICATION",
        "workflow_status": "REQUIRES_VERIFICATION",
        "scenario": "LARGE_LOT_SALE",
        "company_name": None,
        "location": "Sem",
        "inventory_type": "workwear_inventory",
        "currency": "SEK",
        "price": None,
        "bid_price": None,
        "quantity": 58,
        "published_at": None,
        "discovered_at": "2026-08-03T08:00:00Z",
        "identity_stable": True,
        "verified": False,
        "analysis_eligible": False,
        "top5_eligible": True,
        "market_signals": [],
        "evidence": [],
        "missing_information": [],
        "metadata": {"discovery_score": 72, "page_role": "ITEM_LISTING"},
    }


def test_migration_creates_domain_market_signal_tables(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'signals.db'}"
    upgrade_database(database_url, config_path=ALEMBIC_CONFIG)
    engine = create_database_engine(database_url)
    tables = set(inspect(engine).get_table_names())
    assert "market_signals" in tables
    assert "market_signal_observations" in tables
    engine.dispose()


def test_signal_replay_is_idempotent_and_changed_evidence_is_append_only(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'signals.db'}"
    upgrade_database(database_url, config_path=ALEMBIC_CONFIG)
    engine = create_database_engine(database_url)
    factory = create_session_factory(engine)

    with session_scope(factory) as session:
        repository = MarketSignalRepository(session)
        first = repository.upsert_signal(_signal())
        replay = repository.upsert_signal(_signal())
        assert first["created"] is True
        assert replay["created"] is False
        assert replay["changed"] is False
        assert len(repository.list_observations("closure:NO:example-shop")) == 1

    changed = deepcopy(_signal())
    changed["value"] = "The closure notice now mentions inventory liquidation."
    changed["latest_observed_at"] = "2026-08-04T08:00:00Z"
    changed["observed_at"] = "2026-08-04T08:00:00Z"
    with session_scope(factory) as session:
        repository = MarketSignalRepository(session)
        outcome = repository.upsert_signal(changed)
        assert outcome["changed"] is True
        assert len(repository.list_observations("closure:NO:example-shop")) == 2

    engine.dispose()


def test_existing_listing_emits_signal_without_changing_opportunity_identity() -> None:
    signal = market_signal_from_opportunity_record(
        _opportunity_record(),
        generated_at=__import__("datetime").datetime.fromisoformat(
            "2026-08-03T08:00:00+00:00"
        ),
    )
    assert signal.signal_type.value == "ITEM_LISTING"
    assert signal.related_opportunity_id == "auction:lot:1"
    assert signal.signal_id == "opportunity-signal:auction:lot:1"


def test_closure_signal_is_retained_without_becoming_direct_opportunity(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "inputs" / "no-example"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "unified-opportunity-report.json").write_text(
        json.dumps(
            {
                "schema_version": "1.1",
                "generated_at": "2026-08-03T08:00:00Z",
                "record_count": 0,
                "records": [],
                "conversion_error_count": 0,
                "conversion_errors": [],
            }
        ),
        encoding="utf-8",
    )
    (artifact_dir / "market-signal-report.json").write_text(
        json.dumps({"signals": [_signal()]}),
        encoding="utf-8",
    )
    manifest = {
        "sources": [
            {
                "market_code": "NO",
                "source_name": "Example Registry",
                "artifact_dir": "inputs/no-example",
            }
        ]
    }
    persistence = persist_manifest_market_signals(
        manifest,
        root=tmp_path,
        config_path=ALEMBIC_CONFIG,
    )
    checkpoint = {
        "generated_at": "2026-08-03T08:00:00Z",
        "market_coverage": ["NO", "SE", "DE"],
        "sources": [
            {
                "market_code": "NO",
                "source_name": "Example Registry",
                "execution_status": "SUCCESS",
                "persistence_status": "SUCCESS",
            }
        ],
        "deduplicated_opportunities": [],
        "next_human_action": {
            "action": "NO_IMMEDIATE_ACTION",
            "reason": "No direct opportunity.",
        },
    }
    brief = build_domain_market_intelligence_brief(checkpoint, persistence)

    assert brief["counts"]["early_signals_to_watch"] == 1
    assert brief["counts"]["current_direct_opportunities"] == 0
    assert brief["selected_human_action"]["action"] == "MONITOR_INVENTORY_RELEASE"
    assert brief["selected_human_action"]["signal_id"] == "closure:NO:example-shop"
    assert brief["automatic_contact"] is False
    assert brief["automatic_bid"] is False
    assert brief["automatic_purchase"] is False
    assert brief["automatic_payment"] is False


def test_phone_bulletin_names_signals_and_selected_opportunity_in_arabic() -> None:
    listing_signal = _signal(
        signal_id="opportunity-signal:auction:lot:1",
        signal_type="ITEM_LISTING",
        value="58 workwear trousers",
        source="Blinto",
        source_country="SE",
        source_url="https://example.test/auction/1",
        title="58 workwear trousers",
        company_name=None,
        seller_name="Sem Workwear Seller",
        location="Sem",
        related_opportunity_id="auction:lot:1",
        status="ACTIVE",
        metadata={"quantity": 58, "inventory_type": "workwear_inventory"},
    )
    brief = {
        "generated_at": "2026-08-03T16:08:38Z",
        "counts": {
            "new_signals_today": 2,
            "changed_signals_since_previous_checkpoint": 0,
            "early_signals_to_watch": 1,
            "current_direct_opportunities": 1,
            "unavailable_or_failed_sources": 0,
        },
        "early_signals_to_watch": [_signal()],
        "current_direct_opportunities": [
            {
                "opportunity_identity": "auction:lot:1",
                "title": "58 workwear trousers",
                "market_code": "SE",
                "source_name": None,
                "source_url": None,
                "workflow_status": "ACTIVE_OPPORTUNITY",
                "listing_status": "ACTIVE",
                "discovery_score": 72,
                "location": None,
                "quantity": None,
            }
        ],
        "selected_human_action": {
            "action": "REVIEW_ONE_OPPORTUNITY",
            "reason": "A verified active opportunity is ready for human analysis review.",
            "opportunity_identity": "auction:lot:1",
            "signal_id": None,
        },
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }
    persistence = {
        "current_signals": [_signal(), listing_signal],
    }

    enriched = enrich_phone_readable_market_bulletin(brief, persistence)
    selected = enriched["phone_readable_summary"]["selected_opportunity"]
    assert selected["source_name"] == "Blinto"
    assert selected["source_url"] == "https://example.test/auction/1"
    assert selected["location"] == "Sem"
    assert selected["quantity"] == 58

    rendered = render_phone_readable_market_bulletin(enriched)
    assert "أهم الإشارات المبكرة اليوم:" in rendered
    assert "[إغلاق نشاط تجاري] Example clothing shop closing" in rendered
    assert "الجهة: Example AS" in rendered
    assert "https://example.test/closure/1" in rendered
    assert "أفضل فرصة مباشرة اليوم:" in rendered
    assert "الاسم: 58 workwear trousers" in rendered
    assert "المصدر: Blinto" in rendered
    assert "الموقع: Sem" in rendered
    assert "الكمية المعروفة: 58" in rendered
    assert "الإجراء البشري الوحيد: راجع فرصة واحدة" in rendered
    assert "السبب: توجد فرصة نشطة موثقة وجاهزة للمراجعة البشرية." in rendered
    assert "REVIEW_ONE_OPPORTUNITY" not in rendered
    assert "A verified active opportunity" not in rendered


def test_brave_radar_requires_clothing_and_market_event_terms() -> None:
    observed_at = datetime(2026, 8, 5, 10, 0, tzinfo=timezone.utc)
    signal = market_signal_from_brave_hit(
        SearchHit(
            title="Klesbutikk legger ned med opphørssalg av klær",
            url="https://news.example.no/story/1?utm_source=mail#details",
            description="Butikken avvikles og hele tekstillageret skal selges.",
            provider="Brave Search",
        ),
        market_code="NO",
        query=MARKET_QUERIES["NO"][0],
        rank=1,
        observed_at=observed_at,
    )

    assert signal is not None
    assert signal.signal_type.value == "BUSINESS_CLOSURE"
    assert str(signal.source_url) == "https://news.example.no/story/1"
    assert signal.related_opportunity_id is None
    assert signal.status.value == "WATCH"
    assert signal.metadata["signal_only"] is True
    assert signal.metadata["not_an_opportunity"] is True
    assert signal.evidence[0].verified is False

    ordinary_listing = market_signal_from_brave_hit(
        SearchHit(
            title="Nye sommerklær i nettbutikken",
            url="https://shop.example.no/summer",
            description="Vanlig salg av klær og nye sommervarer.",
            provider="Brave Search",
        ),
        market_code="NO",
        query=MARKET_QUERIES["NO"][0],
        rank=2,
        observed_at=observed_at,
    )
    assert ordinary_listing is None


def test_brave_radar_is_bounded_deduplicated_and_merges_market_reports(
    tmp_path: Path,
) -> None:
    manifest = {
        "sources": [
            {
                "market_code": "NO",
                "source_name": "Auksjonen.no",
                "artifact_dir": "inputs/no-auksjonen",
            },
            {
                "market_code": "SE",
                "source_name": "Blinto",
                "artifact_dir": "inputs/se-blinto",
            },
            {
                "market_code": "DE",
                "source_name": "Riegermann",
                "artifact_dir": "inputs/de-riegermann",
            },
        ]
    }
    no_dir = tmp_path / "inputs" / "no-auksjonen"
    no_dir.mkdir(parents=True)
    (no_dir / "market-signal-report.json").write_text(
        json.dumps({"signals": [_signal()]}),
        encoding="utf-8",
    )

    calls: list[tuple[str, str, int]] = []

    class FakeProvider:
        name = "Fake Brave"

        def __init__(self, market_code: str) -> None:
            self.market_code = market_code

        def search(self, query: str, *, count: int = 10):
            calls.append((self.market_code, query, count))
            if self.market_code == "NO":
                return [
                    SearchHit(
                        title="Opphørssalg i klesbutikk",
                        url="https://news.example.no/closure?utm_campaign=x",
                        description="Nedleggelse med salg av klær og tekstillager.",
                        provider="Brave Search",
                    )
                ]
            if self.market_code == "DE":
                return [
                    SearchHit(
                        title="Insolvenz eines Modegeschäfts",
                        url="https://news.example.de/insolvenz/77",
                        description="Bekleidung und Warenbestand können später verkauft werden.",
                        provider="Brave Search",
                    )
                ]
            return [
                SearchHit(
                    title="Neue Modekollektion",
                    url="https://news.example.se/mode",
                    description="Vanliga kläder och en ny modekollektion.",
                    provider="Brave Search",
                )
            ]

    report = collect_manifest_brave_market_signals(
        manifest,
        root=tmp_path,
        observed_at=datetime(2026, 8, 5, 10, 0, tzinfo=timezone.utc),
        environment={"BRAVE_SEARCH_API_KEY": "test-key"},
        provider_factory=lambda market, api_key, freshness: FakeProvider(market),
    )

    assert report["market_coverage"] == ["NO", "SE", "DE"]
    assert report["query_budget_total"] == 6
    assert report["requests_made"] == 6
    assert len(calls) == 6
    assert all(count == 10 for _, _, count in calls)
    assert report["signal_count"] == 2
    assert report["status_counts"] == {"SUCCESS": 2, "VALID_ZERO": 1}

    by_market = {item["source_country"]: item for item in report["sources"]}
    assert by_market["NO"]["accepted_signal_count"] == 1
    assert by_market["NO"]["duplicate_result_count"] == 1
    assert by_market["SE"]["status"] == "VALID_ZERO"
    assert by_market["DE"]["accepted_signal_count"] == 1

    merged = json.loads(
        (no_dir / "market-signal-report.json").read_text(encoding="utf-8")
    )
    signal_ids = {item["signal_id"] for item in merged["signals"]}
    assert "closure:NO:example-shop" in signal_ids
    assert len([value for value in signal_ids if value.startswith("brave-radar:no:")]) == 1
    assert report["automatic_contact"] is False
    assert report["automatic_bid"] is False
    assert report["automatic_purchase"] is False
    assert report["automatic_payment"] is False


def test_brave_radar_missing_key_is_truthfully_blocked_without_requests(
    tmp_path: Path,
) -> None:
    manifest = {
        "sources": [
            {"market_code": "NO", "artifact_dir": "inputs/no"},
            {"market_code": "SE", "artifact_dir": "inputs/se"},
            {"market_code": "DE", "artifact_dir": "inputs/de"},
        ]
    }

    def fail_factory(market_code: str, api_key: str, freshness: str | None):
        raise AssertionError("provider must not be initialized without credentials")

    report = collect_manifest_brave_market_signals(
        manifest,
        root=tmp_path,
        environment={},
        provider_factory=fail_factory,
    )

    assert report["requests_made"] == 0
    assert report["signal_count"] == 0
    assert report["status_counts"] == {"BLOCKED_CONFIGURATION": 3}
    assert all(
        item["block_reason"] == "BRAVE_SEARCH_API_KEY_MISSING"
        for item in report["sources"]
    )
