from __future__ import annotations

from mind_forge.contracts_v1 import QuestionKind
from mind_forge.pipeline_v1 import run_phase1_forge
from mind_forge.research_evidence_v1 import ResearchRoute


def test_raw_local_business_seed_generates_market_validation_questions_and_grounded_research():
    seed = "محل شاي في نامسوس"
    result = run_phase1_forge(seed)

    internal_questions = [
        item.text.casefold()
        for item in result.run_contract.questions
        if item.kind is QuestionKind.INTERNAL
    ]
    joined = "\n".join(internal_questions)

    assert "observable demand" in joined
    assert "direct competitors" in joined
    assert "unit economics" in joined
    assert "licenses" in joined

    external_ids = set(result.research.external_request_ids)
    external = [
        item for item in result.research.requests
        if item.request_id in external_ids
    ]

    assert len(external) >= 2

    demand = external[0]
    competition = external[1]

    assert seed in demand.claim_text
    assert demand.route is ResearchRoute.PUBLIC_DATA
    assert "local demand" in demand.claim_text.casefold()
    assert "official statistics" in demand.acceptable_source_types

    assert seed in competition.claim_text
    assert competition.route is ResearchRoute.WEB
    assert "direct competitors" in competition.claim_text.casefold()
    assert "direct competitor/public offer" in competition.acceptable_source_types

    # The first two paid searches must be seed-grounded market validation, not the
    # generic mechanism assumptions that produced unrelated retail/telecom sources.
    generic_fragments = (
        "subset of customers values speed",
        "adjacent need is common enough",
    )
    first_two_claims = "\n".join(item.claim_text.casefold() for item in external[:2])
    assert not any(fragment in first_two_claims for fragment in generic_fragments)
