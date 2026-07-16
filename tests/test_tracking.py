from opportunity_engine.ods import OpportunityCandidate, track_workflow_opportunities


def _candidate(confidence: float = 0.7) -> OpportunityCandidate:
    return OpportunityCandidate(
        opportunity_id="opp-track",
        title="Tracked opportunity",
        description="A tracked workflow opportunity.",
        category="inventory",
        evidence=("source:test",),
        confidence=confidence,
        source_plugin="test",
    )


def test_tracking_marks_new_then_unchanged(tmp_path):
    path = tmp_path / "history.json"
    first = track_workflow_opportunities((_candidate(),), storage_path=path, country="Norway")
    second = track_workflow_opportunities((_candidate(),), storage_path=path, country="Norway")

    assert first.new_count == 1
    assert second.unchanged_count == 1
    assert second.records[0].times_seen == 2


def test_tracking_marks_updated_confidence(tmp_path):
    path = tmp_path / "history.json"
    track_workflow_opportunities((_candidate(),), storage_path=path)
    result = track_workflow_opportunities((_candidate(0.82),), storage_path=path)

    assert result.updated_count == 1
    assert result.changes[0].current_confidence == 0.82
