from __future__ import annotations

from datetime import datetime, timezone

from opportunity_engine.adaptive_keyword_learning import propose_query_gap_keywords
from opportunity_engine.daily_learning_operator import run_daily_learning_cycle
from opportunity_engine.daily_learning_runtime import _market_anchor
from opportunity_engine.learned_query_overlay import learned_terms_for_market
from opportunity_engine.missed_opportunity_learning import DiscoveryTrace, MissedOpportunityCase


LENE_INTERIOR_URL = (
    "https://www.stavangersentrum.no/nyheter/"
    "15-fantastiske-ar-og-en-varm-takk-til-stavanger"
)


def _real_lene_interior_miss() -> MissedOpportunityCase:
    return MissedOpportunityCase(
        case_id="REAL-MISS-NO-LENE-INTERIOR-2025-08",
        market_code="NO",
        discovered_by="HUMAN_VERIFIED_PUBLIC_SOURCE",
        observed_at=datetime(2025, 8, 28, tzinfo=timezone.utc),
        opportunity_type="STORE_CLOSURE_STOCK_LIQUIDATION",
        stock_proven=True,
        ground_truth_company="Lene Interiør",
        ground_truth_url=LENE_INTERIOR_URL,
        trace=DiscoveryTrace(query_generated=False),
        learning_evidence_text=(
            "Lene Interiør legges ned. Stort avslutningssalg på alle varer i butikken."
        ),
    ).with_diagnosis()


def test_real_miss_proposes_avslutningssalg_as_query_gap() -> None:
    case = _real_lene_interior_miss()

    candidates = propose_query_gap_keywords(
        [case],
        active_queries=[
            '("opphørssalg" OR "avviklingssalg" OR "konkurssalg" OR konkurs) klær',
            '("restlager" OR "varelager" OR "lagersalg") salg',
        ],
    )

    by_term = {candidate.term: candidate for candidate in candidates}
    assert case.root_cause == "QUERY_GAP"
    assert "avslutningssalg" in by_term
    assert by_term["avslutningssalg"].support_case_ids == (case.case_id,)


def test_real_miss_can_be_recovered_in_shadow_without_production_activation() -> None:
    case = _real_lene_interior_miss()

    def search(term: str, market_code: str):
        assert market_code == "NO"
        if term != "avslutningssalg":
            return []
        return [
            {
                "company": "Lene Interiør",
                "url": LENE_INTERIOR_URL,
                "verified_relevant": True,
            },
            {
                "company": "Ordinary seasonal sale",
                "url": "https://noise.example/seasonal-sale",
            },
        ]

    outcome = run_daily_learning_cycle(
        existing_cases=[case],
        inbox_cases=[],
        active_queries=[
            '("opphørssalg" OR "avviklingssalg" OR "konkurssalg" OR konkurs) klær',
            '("restlager" OR "varelager" OR "lagersalg") salg',
        ],
        search=search,
    )

    shadow_terms = learned_terms_for_market(outcome.shadow_overlay, "NO")
    active_terms = learned_terms_for_market(outcome.overlay, "NO")
    learned_case = next(item for item in outcome.cases if item.case_id == case.case_id)

    assert "avslutningssalg" in shadow_terms
    assert "avslutningssalg" not in active_terms
    assert learned_case.learning_status == "RECOVERED"
    assert "avslutningssalg" in learned_case.learned_patterns
    assert outcome.report["automatic_query_activation"] is False
    assert outcome.report["promotion_gate_enforced"] is True


def test_learning_search_anchor_covers_broad_inventory_not_only_clothing() -> None:
    anchor = _market_anchor("NO").casefold()

    assert "varelager" in anchor
    assert "interiør" in anchor
    assert "elektronikk" in anchor
    assert "byggevarer" in anchor
