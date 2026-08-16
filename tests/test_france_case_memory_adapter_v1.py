from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from opportunity_engine.discovery.france_case_memory_adapter import (
    adapt_france_signal_to_entity_memory,
    build_france_case_memory_adapter,
    run_france_case_memory_cycle,
)
from opportunity_engine.discovery.france_market_discovery import (
    FRANCE_DISCOVERY_QUERIES,
    france_signal_from_hit,
)
from opportunity_engine.discovery.search_provider import SearchHit


DAY_1 = datetime(2026, 8, 16, 10, 0, tzinfo=timezone.utc)
DAY_2 = datetime(2026, 8, 17, 10, 0, tzinfo=timezone.utc)


def _query(intent: str):
    return next(item for item in FRANCE_DISCOVERY_QUERIES if item.intent == intent)


def _bodacc_signal(*, observed_at: datetime, url: str) -> dict:
    signal = france_signal_from_hit(
        SearchHit(
            title="Liquidation judiciaire - PAPRIKA SAS",
            url=url,
            description=(
                "Dénomination : PAPRIKA SAS Forme juridique : Société par actions simplifiée "
                "Activité : vente de vêtements prêt-à-porter. Jugement prononçant la liquidation judiciaire."
            ),
            provider="Fake Brave",
        ),
        query=_query("OFFICIAL_INSOLVENCY"),
        rank=1,
        observed_at=observed_at,
    )
    assert signal is not None
    return signal.model_dump(mode="json")


def test_bodacc_denomination_seeds_entity_scent() -> None:
    raw = _bodacc_signal(
        observed_at=DAY_1,
        url="https://www.bodacc.fr/pages/annonces-commerciales-detail/?q.id=id:A202612345678",
    )
    adapted, reason = adapt_france_signal_to_entity_memory(raw)
    assert reason is None
    assert adapted is not None
    assert adapted["company_name"] == "PAPRIKA SAS"
    assert adapted["metadata"]["entity_key"] == "paprika"
    assert adapted["metadata"]["entity_shape"] == "BODACC_DENOMINATION"
    assert adapted["metadata"]["entity_cluster_score"] == 95
    assert adapted["metadata"]["promotion_to_opportunity_allowed"] is False


def test_generic_french_auction_without_company_does_not_create_case() -> None:
    signal = france_signal_from_hit(
        SearchHit(
            title="Vente aux enchères judiciaire de vêtements",
            url="https://www.interencheres.com/biens-equipement/lot-999",
            description="Stock de vêtements en lots après liquidation judiciaire.",
            provider="Fake Brave",
        ),
        query=_query("JUDICIAL_AUCTION_STOCK"),
        rank=1,
        observed_at=DAY_1,
    )
    assert signal is not None
    adapted, reason = adapt_france_signal_to_entity_memory(signal.model_dump(mode="json"))
    assert adapted is None
    assert reason == "NO_EXPLICIT_FRENCH_ENTITY"


def test_same_company_across_days_builds_one_stable_case_and_rotates_stages() -> None:
    first = _bodacc_signal(
        observed_at=DAY_1,
        url="https://www.bodacc.fr/pages/annonces-commerciales-detail/?q.id=id:A202612345678",
    )
    second = _bodacc_signal(
        observed_at=DAY_2,
        url="https://www.bodacc.fr/pages/annonces-commerciales-detail/?q.id=id:A202612345679",
    )
    report = build_france_case_memory_adapter([first, second], observed_at=DAY_2)
    assert report["persistent_case_count"] == 1
    case = report["cases"][0]
    assert case["entity_key"] == "paprika"
    assert case["entity_source_signal_count"] == 2
    assert case["first_seen"] == DAY_1.isoformat()
    assert case["last_seen"] == DAY_2.isoformat()

    stages = []
    for day in (16, 17, 18, 19, 20):
        daily = build_france_case_memory_adapter(
            [first],
            observed_at=datetime(2026, 8, day, 10, 0, tzinfo=timezone.utc),
        )
        stages.append(daily["follow_up_plan"][0]["follow_up_stage"])
    assert stages == [
        "STOCK_MARCHANDISES",
        "VENTE_AUX_ENCHERES",
        "DESTOCKAGE",
        "LIQUIDATEUR",
        "LOTS_CONCRETS",
    ]


class FakeProvider:
    def __init__(self, hits: list[SearchHit]) -> None:
        self.hits = hits
        self.calls: list[tuple[str, int]] = []

    def search(self, query: str, *, count: int = 10) -> Sequence[SearchHit]:
        self.calls.append((query, count))
        return self.hits[:count]


def test_persisted_france_case_survives_next_run_and_follow_up_uses_existing_engine(
    tmp_path: Path,
) -> None:
    first = _bodacc_signal(
        observed_at=DAY_1,
        url="https://www.bodacc.fr/pages/annonces-commerciales-detail/?q.id=id:A202612345678",
    )
    day_one = run_france_case_memory_cycle(
        [first],
        input_root=tmp_path,
        environment={},
        observed_at=DAY_1,
        max_cases=1,
    )
    assert day_one["persistent_case_count"] == 1
    case_id = day_one["cases"][0]["case_id"]
    assert day_one["follow_up"]["status"] == "SKIPPED_NO_API_KEY"

    provider = FakeProvider([
        SearchHit(
            title="PAPRIKA SAS - vente aux enchères stock vêtements",
            url="https://www.interencheres.com/biens-equipement/paprika/lot-1",
            description="Lot judiciaire de 1048 pièces de vêtements, vente aux enchères.",
            provider="Fake Brave",
        )
    ])
    day_two = run_france_case_memory_cycle(
        [],
        input_root=tmp_path,
        environment={"BRAVE_SEARCH_API_KEY": "test-key"},
        provider_factory=lambda market, key: provider,
        observed_at=DAY_2,
        max_cases=1,
        results_per_case=5,
    )
    assert day_two["persistent_case_count"] == 1
    assert day_two["cases"][0]["case_id"] == case_id
    assert day_two["persistence"]["loaded_france_entity_signal_count"] == 1
    assert provider.calls
    assert "ench" in provider.calls[0][0].casefold()
    assert day_two["follow_up"]["status"] == "SUCCESS"
    assert day_two["follow_up"]["commercial_lead_count"] == 1
    lead = day_two["follow_up"]["cases"][0]["leads"][0]
    assert lead["verification_status"] == "UNVERIFIED_PUBLIC_WEB_SEARCH_HIT"
    assert lead["promotion_to_opportunity_allowed"] is False
