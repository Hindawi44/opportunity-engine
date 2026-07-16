from opportunity_engine.ods import (
    FashionDiscoveryPlugin,
    ODSRequest,
    ODSSession,
    OpportunityCandidate,
    OpportunityRankingPlugin,
    PluginRegistry,
    RankingWeights,
    Stage,
    StageResult,
    Status,
    WorkflowEngine,
)


def _session_with_candidates(candidates: tuple[OpportunityCandidate, ...]) -> ODSSession:
    session = ODSSession(request=ODSRequest(subject="Fashion", country="Norway"))
    session.results[Stage.DISCOVERY] = StageResult(
        stage=Stage.DISCOVERY,
        status=Status.COMPLETED,
        payload=candidates,
    )
    return session


def test_ranking_returns_stable_top_five_without_modifying_opportunities() -> None:
    discovery = FashionDiscoveryPlugin()
    source_session = ODSSession(
        request=ODSRequest(subject="Fashion", country="Norway")
    )
    discovery_result = discovery.run(source_session)
    candidates = discovery_result.payload

    plugin = OpportunityRankingPlugin(shortlist_size=5)
    result = plugin.run(_session_with_candidates(candidates))

    assert result.status is Status.COMPLETED
    assert result.stage is Stage.RANKING
    assert len(result.payload) == 5
    assert [item.rank for item in result.payload] == [1, 2, 3, 4, 5]
    assert [item.final_score for item in result.payload] == sorted(
        [item.final_score for item in result.payload], reverse=True
    )
    original_by_id = {item.opportunity_id: item for item in candidates}
    assert all(
        ranked.opportunity is original_by_id[ranked.opportunity.opportunity_id]
        for ranked in result.payload
    )


def test_ranking_is_deterministic_for_equal_inputs() -> None:
    discovery = FashionDiscoveryPlugin()
    discovery_result = discovery.run(
        ODSSession(request=ODSRequest(subject="ملابس", country="Norway"))
    )
    plugin = OpportunityRankingPlugin()

    first = plugin.run(_session_with_candidates(discovery_result.payload))
    second = plugin.run(_session_with_candidates(discovery_result.payload))

    assert [
        (item.opportunity.opportunity_id, item.final_score)
        for item in first.payload
    ] == [
        (item.opportunity.opportunity_id, item.final_score)
        for item in second.payload
    ]


def test_ranking_fails_without_discovery_result() -> None:
    plugin = OpportunityRankingPlugin()
    session = ODSSession(request=ODSRequest(subject="Fashion"))

    result = plugin.run(session)

    assert result.status is Status.FAILED
    assert "completed discovery" in result.errors[0]


def test_ranking_respects_minimum_score_cut_line() -> None:
    candidate = OpportunityCandidate(
        opportunity_id="weak",
        title="Weak candidate",
        description="Test candidate",
        category="unknown",
        evidence=(),
        confidence=0.1,
        source_plugin="test",
    )
    plugin = OpportunityRankingPlugin(minimum_score=90.0)

    result = plugin.run(_session_with_candidates((candidate,)))

    assert result.status is Status.COMPLETED
    assert result.payload == ()


def test_ranking_weights_must_sum_to_one() -> None:
    try:
        RankingWeights(confidence=0.5)
    except ValueError as exc:
        assert "sum to 1.0" in str(exc)
    else:
        raise AssertionError("invalid weights should fail")


def test_discovery_and_ranking_run_in_workflow() -> None:
    registry = PluginRegistry(
        [FashionDiscoveryPlugin(), OpportunityRankingPlugin(shortlist_size=3)]
    )
    engine = WorkflowEngine(
        registry,
        workflow=(Stage.DISCOVERY, Stage.RANKING),
    )

    session = engine.run(
        ODSRequest(subject="أزياء", country="Norway")
    )

    assert session.status is Status.COMPLETED
    assert len(session.results[Stage.DISCOVERY].payload) == 10
    assert len(session.results[Stage.RANKING].payload) == 3
