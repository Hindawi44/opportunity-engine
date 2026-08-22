from __future__ import annotations

from datetime import datetime, timezone


def _query_gap_case(*, diagnosed_terms=()):
    from opportunity_engine.missed_opportunity_learning import (
        DiscoveryTrace,
        MissedOpportunityCase,
    )

    return MissedOpportunityCase(
        case_id="auto-query-gap:no:bauhaus-test",
        market_code="NO",
        discovered_by="AUTOMATIC_INDEPENDENT_QUERY_GAP_SCOUT",
        observed_at=datetime(2026, 8, 22, 18, 0, tzinfo=timezone.utc),
        opportunity_type="VERIFIED_STORE_CLOSURE_INVENTORY_LIQUIDATION",
        stock_proven=True,
        ground_truth_company="BAUHAUS",
        ground_truth_url="https://www.bauhaus.no/bauhaus-norge-informasjon",
        trace=DiscoveryTrace(query_generated=False),
        learning_evidence_text=(
            "BAUHAUS Norge Informasjon Opphørssalg! Klikk her for mer informasjon. "
            "BAUHAUS avvikler virksomheten i Norge og lagerbeholdningen tømmes."
        ),
        diagnosed_query_gap_terms=tuple(diagnosed_terms),
    ).with_diagnosis()


def test_missed_opportunity_round_trip_preserves_diagnosed_query_gap_terms() -> None:
    from opportunity_engine.missed_opportunity_learning import MissedOpportunityCase

    case = _query_gap_case(diagnosed_terms=("avviklingssalg",))
    restored = MissedOpportunityCase.from_dict(case.to_dict())

    assert restored.diagnosed_query_gap_terms == ("avviklingssalg",)
    assert restored.learned_patterns == ()


def test_diagnosed_gap_term_is_first_candidate_under_one_candidate_budget() -> None:
    from opportunity_engine.adaptive_keyword_learning import propose_query_gap_keywords

    case = _query_gap_case(diagnosed_terms=("avviklingssalg",))
    candidates = propose_query_gap_keywords(
        [case],
        active_queries=["opphørssalg arbeidsklær sikkerhetssko Norge"],
        max_candidates=1,
    )

    assert len(candidates) == 1
    assert candidates[0].term == "avviklingssalg"
    assert candidates[0].support_case_ids == (case.case_id,)
    assert candidates[0].root_cause == "QUERY_GAP"


def test_active_core_query_still_blocks_diagnosed_gap_candidate() -> None:
    from opportunity_engine.adaptive_keyword_learning import propose_query_gap_keywords

    case = _query_gap_case(diagnosed_terms=("avviklingssalg",))
    candidates = propose_query_gap_keywords(
        [case],
        active_queries=["avviklingssalg butikk varelager Norge"],
        max_candidates=20,
    )

    assert all(candidate.term != "avviklingssalg" for candidate in candidates)


def test_verified_scout_case_carries_filtered_query_gap_term_to_learner() -> None:
    from opportunity_engine.automatic_query_gap_miss_scout import PublicPage
    from opportunity_engine.discovery.search_provider import SearchHit
    from opportunity_engine.query_gap_scout_waterfall import discover_query_gap_misses

    news_url = "https://www.nrk.no/nyheter/bauhaus-legger-ned-i-norge-1.17996380"
    official_url = "https://www.bauhaus.no/bauhaus-norge-informasjon"

    def search(query: str):
        return [
            SearchHit(
                title="Bauhaus legger ned i Norge",
                url=news_url,
                description="Bauhaus legger ned alle butikker i Norge.",
                provider="Brave Search",
            )
        ]

    def fetch_page(url: str):
        if url == news_url:
            return PublicPage(
                requested_url=url,
                final_url=url,
                status_code=200,
                content_type="text/html; charset=utf-8",
                html=(
                    "<html><body><h1>Bauhaus legger ned i Norge</h1>"
                    "<p>Bauhaus legger ned alle butikker i Norge.</p></body></html>"
                ),
            )
        if url == "https://bauhaus.no/":
            return PublicPage(
                requested_url=url,
                final_url="https://www.bauhaus.no/",
                status_code=200,
                content_type="text/html; charset=utf-8",
                html=(
                    '<html><body><a href="/bauhaus-norge-informasjon">Informasjon</a>'
                    "<p>BAUHAUS Norge</p></body></html>"
                ),
            )
        if url == official_url:
            return PublicPage(
                requested_url=url,
                final_url=url,
                status_code=200,
                content_type="text/html; charset=utf-8",
                html=(
                    "<html><body><h1>BAUHAUS avvikler virksomheten i Norge</h1>"
                    "<p>Opphørssalget starter lørdag 22. august.</p>"
                    "<p>Dette er også et avviklingssalg, og lagerbeholdningen selges ut.</p>"
                    "</body></html>"
                ),
            )
        raise AssertionError(url)

    outcome = discover_query_gap_misses(
        {"deduplicated_opportunities": []},
        active_queries=["opphørssalg arbeidsklær sikkerhetssko Norge"],
        search=search,
        fetch_page=fetch_page,
        max_pages=3,
    )

    assert outcome["detected_miss_count"] == 1
    assert outcome["cases_metadata"][0]["query_gap_term"] == "avviklingssalg"
    assert outcome["cases"][0].diagnosed_query_gap_terms == ("avviklingssalg",)
    assert outcome["cases"][0].learned_patterns == ()
