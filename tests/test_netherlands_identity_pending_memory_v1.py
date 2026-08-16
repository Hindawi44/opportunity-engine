from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from opportunity_engine.discovery.netherlands_identity_pending_cycle import (
    run_netherlands_case_memory_cycle,
)
from opportunity_engine.discovery.netherlands_identity_pending_memory import (
    IDENTITY_PENDING,
    load_identity_pending_signals,
)
from opportunity_engine.discovery.netherlands_market_discovery import (
    NETHERLANDS_DISCOVERY_QUERIES,
    netherlands_signal_from_hit,
)
from opportunity_engine.discovery.search_provider import SearchHit


DAY_1 = datetime(2026, 8, 16, 10, 0, tzinfo=timezone.utc)
DAY_2 = datetime(2026, 8, 17, 10, 0, tzinfo=timezone.utc)


def _query(intent: str):
    return next(item for item in NETHERLANDS_DISCOVERY_QUERIES if item.intent == intent)


def _unnamed_mall_signal() -> dict:
    signal = netherlands_signal_from_hit(
        SearchHit(
            title=(
                "Deze week failliet: winkel in Mall of the Netherlands "
                "failliet verklaard - Omroep West"
            ),
            url=(
                "https://www.omroepwest.nl/economie/5132174/"
                "deze-week-failliet-winkel-in-mall-of-the-netherlands-failliet-verklaard"
            ),
            description=(
                "Het doek is gevallen voor een kledingwinkel in Leidschendam. "
                "De curator onderzoekt de handelsvoorraad en mogelijke verkoop."
            ),
            provider="Fake Brave",
        ),
        query=_query("INSOLVENCY_LIQUIDATION"),
        rank=1,
        observed_at=DAY_1,
    )
    assert signal is not None
    payload = signal.model_dump(mode="json")
    assert payload["company_name"] is None
    return payload


class PendingDayProvider:
    def __init__(self, *, resolve_identity: bool) -> None:
        self.resolve_identity = resolve_identity
        self.calls: list[tuple[str, int]] = []

    @property
    def name(self) -> str:
        return "Fake Brave"

    def search(self, query: str, *, count: int = 10) -> Sequence[SearchHit]:
        self.calls.append((query, count))
        folded = query.casefold()

        if "bedrijfsnaam" in folded:
            if not self.resolve_identity:
                return [
                    SearchHit(
                        title="Failliete kledingwinkel in Leidschendam",
                        url="https://regional.example.nl/mall-failliet",
                        description="Curator onderzoekt de voorraad van de winkel.",
                        provider="Fake Brave",
                    )
                ]
            return [
                SearchHit(
                    title="Faillissement MD Fashion Netherlands B.V.",
                    url="https://regional.example.nl/md-fashion-failliet",
                    description=(
                        "De kledingwinkel van MD Fashion Netherlands B.V. in "
                        "Leidschendam is failliet verklaard."
                    ),
                    provider="Fake Brave",
                )
            ]

        if "md fashion netherlands" in folded and "faillissement" in folded:
            return [
                SearchHit(
                    title=(
                        "MD FASHION NETHERLANDS B.V. - "
                        "Centraal Insolventieregister"
                    ),
                    url="https://insolventies.rechtspraak.nl/#!/details/09.26.268",
                    description=(
                        "Faillissement MD FASHION NETHERLANDS B.V. "
                        "KvK 93290497 F.09/26/268."
                    ),
                    provider="Fake Brave",
                )
            ]

        # Follow-Up after identity resolution is intentionally empty here. The
        # contract under test is persistence of the scent, not lot discovery.
        return []


def test_unnamed_signal_survives_discovery_disappearance_and_resolves_next_day(
    tmp_path: Path,
) -> None:
    original = _unnamed_mall_signal()
    signal_id = original["signal_id"]

    day_one_provider = PendingDayProvider(resolve_identity=False)
    day_one = run_netherlands_case_memory_cycle(
        [original],
        input_root=tmp_path,
        environment={"BRAVE_SEARCH_API_KEY": "test-key"},
        provider_factory=lambda market, key: day_one_provider,
        observed_at=DAY_1,
        max_cases=1,
    )

    assert day_one["persistent_case_count"] == 0
    assert day_one["pending_identity_count"] == 1
    pending_summary = day_one["identity_pending_memory"]
    assert pending_summary["new_pending_identity_count"] == 1
    assert pending_summary["remaining_pending_identity_count"] == 1
    assert pending_summary["pending_is_not_entity_scent"] is True
    assert pending_summary["pending_is_not_follow_up_eligible"] is True

    stored_day_one, errors = load_identity_pending_signals(input_root=tmp_path)
    assert errors == []
    assert len(stored_day_one) == 1
    pending = stored_day_one[0]
    assert pending["signal_id"] == signal_id
    assert pending["company_name"] is None
    assert pending["metadata"]["identity_lifecycle_state"] == IDENTITY_PENDING
    assert pending["metadata"]["identity_resolution_attempt_count"] == 1
    assert pending["metadata"]["promotion_to_opportunity_allowed"] is False
    assert pending["metadata"]["automatic_purchase"] is False

    # Day 2 deliberately has ZERO current discovery signals. The only way to
    # recover the case is by restoring yesterday's IDENTITY_PENDING row.
    day_two_provider = PendingDayProvider(resolve_identity=True)
    day_two = run_netherlands_case_memory_cycle(
        [],
        input_root=tmp_path,
        environment={"BRAVE_SEARCH_API_KEY": "test-key"},
        provider_factory=lambda market, key: day_two_provider,
        observed_at=DAY_2,
        max_cases=1,
    )

    summary = day_two["identity_pending_memory"]
    assert summary["loaded_pending_identity_count"] == 1
    assert summary["current_discovery_signal_count"] == 0
    assert summary["resolved_from_pending_identity_count"] == 1
    assert summary["remaining_pending_identity_count"] == 0
    assert day_two["pending_identity_count"] == 0
    assert day_two["persistent_case_count"] == 1

    case = day_two["cases"][0]
    assert case["entity_key"] == "md fashion netherlands"
    assert case["first_seen"] == DAY_1.isoformat()
    assert case["case_status"] == "WATCH"

    entity = day_two["adapter"]["entity_signals"][0]
    assert entity["signal_id"] == signal_id
    assert entity["company_name"].casefold() == "md fashion netherlands b.v."
    assert entity["metadata"]["entity_scent_classification"] == "ENTITY_SCENT"
    assert entity["metadata"]["promotion_to_opportunity_allowed"] is False
    assert entity["metadata"]["automatic_purchase"] is False

    stored_day_two, errors = load_identity_pending_signals(input_root=tmp_path)
    assert errors == []
    assert stored_day_two == []
    assert any("bedrijfsnaam" in query.casefold() for query, _ in day_two_provider.calls)
    assert any("md fashion netherlands" in query.casefold() for query, _ in day_two_provider.calls)


def test_missing_api_key_keeps_pending_without_faking_a_retry(tmp_path: Path) -> None:
    original = _unnamed_mall_signal()
    provider = PendingDayProvider(resolve_identity=False)
    first = run_netherlands_case_memory_cycle(
        [original],
        input_root=tmp_path,
        environment={"BRAVE_SEARCH_API_KEY": "test-key"},
        provider_factory=lambda market, key: provider,
        observed_at=DAY_1,
        max_cases=1,
    )
    assert first["pending_identity_count"] == 1

    second = run_netherlands_case_memory_cycle(
        [],
        input_root=tmp_path,
        environment={},
        observed_at=DAY_2,
        max_cases=1,
    )
    assert second["identity_resolution_status"] == "SKIPPED_NO_API_KEY"
    assert second["pending_identity_count"] == 1

    stored, errors = load_identity_pending_signals(input_root=tmp_path)
    assert errors == []
    assert len(stored) == 1
    # Day 2 had no API key, so it must not be counted as a real search attempt.
    assert stored[0]["metadata"]["identity_resolution_attempt_count"] == 1
    assert stored[0]["metadata"]["automatic_contact"] is False
    assert stored[0]["metadata"]["automatic_payment"] is False
