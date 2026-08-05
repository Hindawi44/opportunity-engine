from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from opportunity_engine.discovery.brave_market_signal_continuity import (
    stabilize_brave_signal,
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


def _raw_brave_signal() -> dict:
    return {
        "signal_type": "BUSINESS_CLOSURE",
        "value": "A clothing shop announced a closure and inventory sale.",
        "source": "Brave Search market signal radar",
        "observed_at": "2026-08-05T10:00:00Z",
        "confidence": 0.67,
        "signal_id": "brave-radar:no:stable-example",
        "source_country": "NO",
        "source_url": "https://news.example.no/closure/1",
        "title": "Klesbutikk avslutter driften",
        "company_name": None,
        "seller_name": None,
        "location": None,
        "first_observed_at": "2026-08-05T10:00:00Z",
        "latest_observed_at": "2026-08-05T10:00:00Z",
        "event_date": None,
        "evidence": [
            {
                "evidence_type": "BRAVE_SEARCH_RESULT",
                "value": "Klesbutikk avslutter driften og selger klær.",
                "source_url": "https://news.example.no/closure/1",
                "captured_at": "2026-08-05T10:00:00Z",
                "verified": False,
                "metadata": {
                    "query_id": "no-closure-insolvency",
                    "source_rank": 1,
                    "provider": "Brave Search",
                    "verification_status": "UNVERIFIED_PUBLIC_WEB",
                },
            }
        ],
        "related_opportunity_id": None,
        "status": "WATCH",
        "metadata": {
            "signal_only": True,
            "not_an_opportunity": True,
            "discovery_transport": "BRAVE_SEARCH",
            "verification_status": "UNVERIFIED_PUBLIC_WEB",
            "query_id": "no-closure-insolvency",
            "query": "first query text",
            "source_rank": 1,
            "clothing_terms": ["klær"],
            "event_terms": ["nedleggelse"],
            "canonical_url": "https://news.example.no/closure/1",
        },
    }


def test_brave_rank_query_and_capture_time_do_not_create_changed_state(
    tmp_path: Path,
) -> None:
    first = stabilize_brave_signal(_raw_brave_signal())
    second_raw = deepcopy(_raw_brave_signal())
    second_raw["observed_at"] = "2026-08-06T10:00:00Z"
    second_raw["latest_observed_at"] = "2026-08-06T10:00:00Z"
    second_raw["metadata"]["query_id"] = "no-surplus-auction"
    second_raw["metadata"]["query"] = "different query text"
    second_raw["metadata"]["source_rank"] = 7
    second_raw["evidence"][0]["captured_at"] = "2026-08-06T10:00:00Z"
    second_raw["evidence"][0]["metadata"]["query_id"] = "no-surplus-auction"
    second_raw["evidence"][0]["metadata"]["source_rank"] = 7
    second = stabilize_brave_signal(second_raw)

    database_url = f"sqlite:///{tmp_path / 'signals.db'}"
    upgrade_database(database_url, config_path=ALEMBIC_CONFIG)
    engine = create_database_engine(database_url)
    factory = create_session_factory(engine)
    try:
        with session_scope(factory) as session:
            repository = MarketSignalRepository(session)
            created = repository.upsert_signal(first)
            replay = repository.upsert_signal(second)

            assert created["created"] is True
            assert replay["created"] is False
            assert replay["changed"] is False
            assert len(
                repository.list_observations("brave-radar:no:stable-example")
            ) == 1
    finally:
        engine.dispose()
