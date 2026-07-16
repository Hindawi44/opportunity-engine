from opportunity_engine.ods import (
    BDNAPlugin,
    BusinessBlueprint,
    FashionDiscoveryPlugin,
    ODSRequest,
    ODSSession,
    OpportunityCandidate,
    OpportunityRankingPlugin,
    PluginRegistry,
    RankedOpportunity,
    Stage,
    StageResult,
    Status,
    WorkflowEngine,
)


def _ranked(category: str = "inventory", rank: int = 1) -> RankedOpportunity:
    candidate = OpportunityCandidate(
        opportunity_id=f"opp-{category}",
        title="Test opportunity",
        description="Test description",
        category=category,
        evidence=("evidence-1", "evidence-2"),
        confidence=0.8,
        source_plugin="test",
    )
    return RankedOpportunity(
        opportunity=candidate,
        final_score=82.0,
        component_scores=(("confidence", 0.8),),
        rank=rank,
    )


def test_bdna_builds_blueprint_from_top_ranked_opportunity() -> None:
    session = ODSSession(request=ODSRequest(subject="Fashion"))
    session.results[Stage.RANKING] = StageResult(
        stage=Stage.RANKING,
        status=Status.COMPLETED,
        payload=(_ranked("inventory"),),
    )

    result = BDNAPlugin().run(session)

    assert result.status is Status.COMPLETED
    assert isinstance(result.payload, BusinessBlueprint)
    assert result.payload.opportunity.category == "inventory"
    assert result.payload.ranking_score == 82.0
    assert "aggregation" in result.payload.business_dna
    assert result.payload.core_asset
    assert result.payload.revenue_models
    assert result.payload.moat
    assert result.payload.growth_path
    assert result.payload.risks
    assert result.payload.hypotheses


def test_bdna_uses_only_rank_one_opportunity() -> None:
    rank_two = _ranked("fit_data", rank=2)
    rank_one = _ranked("returns", rank=1)
    session = ODSSession(request=ODSRequest(subject="Fashion"))
    session.results[Stage.RANKING] = StageResult(
        stage=Stage.RANKING,
        status=Status.COMPLETED,
        payload=(rank_two, rank_one),
    )

    result = BDNAPlugin().run(session)

    assert result.status is Status.COMPLETED
    assert result.payload.opportunity.category == "returns"
    assert result.payload.opportunity is rank_one.opportunity


def test_bdna_fails_without_ranking_result() -> None:
    session = ODSSession(request=ODSRequest(subject="Fashion"))

    result = BDNAPlugin().run(session)

    assert result.status is Status.FAILED
    assert "ranking" in result.errors[0]


def test_bdna_fails_for_invalid_ranking_payload() -> None:
    session = ODSSession(request=ODSRequest(subject="Fashion"))
    session.results[Stage.RANKING] = StageResult(
        stage=Stage.RANKING,
        status=Status.COMPLETED,
        payload=("invalid",),
    )

    result = BDNAPlugin().run(session)

    assert result.status is Status.FAILED
    assert "invalid" in result.errors[0]


def test_bdna_default_profile_supports_unknown_category() -> None:
    session = ODSSession(request=ODSRequest(subject="Fashion"))
    session.results[Stage.RANKING] = StageResult(
        stage=Stage.RANKING,
        status=Status.COMPLETED,
        payload=(_ranked("new_category"),),
    )

    result = BDNAPlugin().run(session)

    assert result.status is Status.COMPLETED
    assert result.payload.core_asset == "Operational knowledge and customer relationship dataset"


def test_discovery_ranking_bdna_workflow() -> None:
    registry = PluginRegistry(
        [
            FashionDiscoveryPlugin(),
            OpportunityRankingPlugin(shortlist_size=5),
            BDNAPlugin(),
        ]
    )
    workflow = WorkflowEngine(
        registry,
        workflow=(Stage.DISCOVERY, Stage.RANKING, Stage.BDNA),
    )

    session = workflow.run(
        ODSRequest(subject="Fashion", country="Norway")
    )

    assert session.status is Status.COMPLETED
    assert isinstance(session.results[Stage.BDNA].payload, BusinessBlueprint)
    assert session.results[Stage.BDNA].payload.opportunity is session.results[Stage.RANKING].payload[0].opportunity
