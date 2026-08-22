from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

from opportunity_engine.adaptive_keyword_learning import (
    evaluate_keyword_candidate,
    propose_query_gap_keywords,
)
from opportunity_engine.missed_opportunity_learning import (
    DiscoveryTrace,
    MissedOpportunityCase,
)


def missed_case(case_id: str, evidence: str) -> MissedOpportunityCase:
    return MissedOpportunityCase(
        case_id=case_id,
        market_code="NO",
        discovered_by="human",
        observed_at=datetime(2026, 8, 21, tzinfo=timezone.utc),
        opportunity_type="STOCK_LIQUIDATION",
        stock_proven=True,
        ground_truth_company=f"Company {case_id} AS",
        ground_truth_url=f"https://example.com/{case_id}",
        trace=DiscoveryTrace(query_generated=False),
        learning_evidence_text=evidence,
    ).with_diagnosis()


def test_learning_evidence_is_persisted_but_never_exposed_to_replay_context() -> None:
    case = missed_case(
        "MISS-1",
        "Butikken avsluttes. Avviklingssalg med restlager av arbeidsklær.",
    )
    restored = MissedOpportunityCase.from_dict(case.to_dict())

    assert "Avviklingssalg" in restored.learning_evidence_text
    context = restored.replay_context()
    assert "learning_evidence_text" not in context
    assert "Company MISS-1 AS" not in str(context)


def test_query_gap_proposer_extracts_commercial_pattern_missing_from_active_queries() -> None:
    case = missed_case(
        "MISS-1",
        "Nordlys AS avvikler butikken. Avviklingssalg og restlager av arbeidsklær selges.",
    )

    candidates = propose_query_gap_keywords(
        [case],
        active_queries=["konkurssalg varelager tekstil Norge"],
    )
    terms = {item.term for item in candidates}

    assert "avviklingssalg" in terms
    assert "nordlys" not in terms
    assert all(item.root_cause == "QUERY_GAP" for item in candidates)


def test_single_case_ordinary_words_are_not_promoted_as_candidates() -> None:
    case = missed_case(
        "MISS-1",
        "Hyggelig lokal butikk med mange fine varer og god kundeservice.",
    )

    candidates = propose_query_gap_keywords([case], active_queries=[])

    assert candidates == []


def test_candidate_is_proven_when_it_recovers_a_real_miss_with_acceptable_precision() -> None:
    case = missed_case(
        "MISS-1",
        "Avviklingssalg med restlager av arbeidsklær.",
    )
    candidate = next(
        item
        for item in propose_query_gap_keywords([case], active_queries=[])
        if item.term == "avviklingssalg"
    )

    def search(term: str, market_code: str):
        assert term == "avviklingssalg"
        assert market_code == "NO"
        return [
            {
                "company": "Company MISS-1 AS",
                "url": "https://example.com/MISS-1",
                "verified_relevant": True,
            },
            {"company": "Noise AS", "url": "https://noise.example/a"},
        ]

    result = evaluate_keyword_candidate(
        candidate,
        [case],
        search,
        min_recovered_cases=1,
        min_precision=0.5,
    )

    assert result.status == "PROVEN"
    assert result.recovered_case_ids == ("MISS-1",)
    assert result.raw_hit_count == 2
    assert result.verified_relevant_count == 1
    assert result.precision == 0.5
    assert result.automatic_activation is False


def test_noisy_candidate_is_rejected_even_when_it_recovers_one_case() -> None:
    case = missed_case(
        "MISS-1",
        "Lagersalg med restlager av arbeidsklær.",
    )
    candidate = next(
        item
        for item in propose_query_gap_keywords([case], active_queries=[])
        if item.term == "lagersalg"
    )

    def noisy_search(term: str, market_code: str):
        hits = [
            {
                "company": "Company MISS-1 AS",
                "url": "https://example.com/MISS-1",
                "verified_relevant": True,
            }
        ]
        hits.extend(
            {"company": f"Noise {i}", "url": f"https://noise.example/{i}"}
            for i in range(19)
        )
        return hits

    result = evaluate_keyword_candidate(
        candidate,
        [case],
        noisy_search,
        min_recovered_cases=1,
        min_precision=0.2,
    )

    assert result.status == "REJECTED_NOISY"
    assert result.precision == 0.05
    assert result.automatic_activation is False


def test_only_query_gap_cases_feed_keyword_learning() -> None:
    query_gap = missed_case("MISS-Q", "Avviklingssalg med restlager.")
    parser_gap = replace(
        missed_case("MISS-P", "Tømmesalg med restlager."),
        trace=DiscoveryTrace(
            query_generated=True,
            search_hit=True,
            retrieved=True,
            parsed=False,
        ),
        root_cause="PARSER_GAP",
    )

    candidates = propose_query_gap_keywords([query_gap, parser_gap], active_queries=[])
    support = {item.term: item.support_case_ids for item in candidates}

    assert "MISS-Q" in support["avviklingssalg"]
    assert all("MISS-P" not in ids for ids in support.values())
