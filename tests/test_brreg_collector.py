from datetime import datetime, timezone

from opportunity_engine.ods import (
    BrregOpportunityCollector,
    BrregSearchSlice,
    LiveBrregAnalysis,
    ODSRequest,
    OpportunityCandidate,
    ScanSnapshot,
)


def _analysis(subject: str, opportunity_id: str | None) -> LiveBrregAnalysis:
    request = ODSRequest(subject=subject, country="Norway")
    opportunities = ()
    if opportunity_id is not None:
        opportunities = (
            OpportunityCandidate(
                opportunity_id=opportunity_id,
                title=f"Verify assets: {subject}",
                description="Official status lead requiring manual verification.",
                category="liquidation_assets",
                evidence=("official-status:bankruptcy",),
                confidence=0.72,
                source_plugin="brreg_status_extractor",
            ),
        )
    now = datetime.now(timezone.utc)
    scan = ScanSnapshot(
        scan_id=f"scan-{subject}",
        started_at=now,
        completed_at=now,
        documents=(),
        opportunities=opportunities,
        connector_statuses=(),
        duplicate_count=0,
    )
    return LiveBrregAnalysis(request, scan, (), None)


def test_collector_deduplicates_ranks_and_persists(tmp_path):
    def runner(subject: str, **kwargs):
        mapping = {
            "retail": _analysis(subject, "brreg-status-111111111"),
            "clothing": _analysis(subject, "brreg-status-111111111"),
            "furniture": _analysis(subject, "brreg-status-222222222"),
        }
        return mapping[subject]

    collector = BrregOpportunityCollector(tmp_path / "memory.json", runner=runner)
    result = collector.collect(
        (
            BrregSearchSlice("retail"),
            BrregSearchSlice("clothing"),
            BrregSearchSlice("furniture"),
        )
    )

    assert result.slices_requested == 3
    assert result.slices_completed == 3
    assert result.slices_failed == 0
    assert result.duplicate_count == 1
    assert len(result.snapshot.opportunities) == 2
    assert len(result.ranked_opportunities) == 2
    assert result.memory.new_count == 2
    assert result.decision is not None
    assert (tmp_path / "memory.json").exists()


def test_collector_keeps_partial_results_when_one_slice_fails(tmp_path):
    def runner(subject: str, **kwargs):
        if subject == "broken":
            raise RuntimeError("temporary Brreg failure")
        return _analysis(subject, "brreg-status-333333333")

    collector = BrregOpportunityCollector(tmp_path / "memory.json", runner=runner)
    result = collector.collect(
        (BrregSearchSlice("broken"), BrregSearchSlice("working"))
    )

    assert result.slices_completed == 1
    assert result.slices_failed == 1
    assert len(result.snapshot.opportunities) == 1
    assert result.errors


def test_collector_accepts_empty_grounded_result(tmp_path):
    def runner(subject: str, **kwargs):
        return _analysis(subject, None)

    collector = BrregOpportunityCollector(tmp_path / "memory.json", runner=runner)
    result = collector.collect((BrregSearchSlice("no-status-signals"),))

    assert result.snapshot.opportunities == ()
    assert result.ranked_opportunities == ()
    assert result.decision is None
    assert result.memory.new_count == 0


def test_search_slice_rejects_invalid_page_size():
    try:
        BrregSearchSlice("retail", page_size=101)
    except ValueError as exc:
        assert "page_size" in str(exc)
    else:
        raise AssertionError("expected ValueError")
