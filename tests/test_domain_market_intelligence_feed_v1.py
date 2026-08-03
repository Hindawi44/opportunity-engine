from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import json

from sqlalchemy import inspect

from opportunity_engine.discovery.domain_market_intelligence_feed import (
    build_domain_market_intelligence_brief,
    market_signal_from_opportunity_record,
    persist_manifest_market_signals,
)
from opportunity_engine.discovery.phone_readable_market_bulletin import (
    enrich_phone_readable_market_bulletin,
    render_phone_readable_market_bulletin,
)
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
