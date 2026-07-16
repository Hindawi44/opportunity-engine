from __future__ import annotations

from datetime import datetime, timezone

from opportunity_engine.ods.brreg_collector import BrregCollectionResult, BrregSearchSlice
from opportunity_engine.ods.live_feed import LiveOpportunityFeed
from opportunity_engine.ods.memory import MemoryRunResult
from opportunity_engine.ods.models import OpportunityCandidate
from opportunity_engine.ods.ranking import RankedOpportunity
from opportunity_engine.ods.scanner import ScanSnapshot


class StubCollector:
    def __init__(self, result: BrregCollectionResult) -> None:
        self.result = result

    def collect(self, slices, *, country="Norway"):
        tuple(slices)
        return self.result


def _result(title: str = "Example AS") -> BrregCollectionResult:
    candidate = OpportunityCandidate(
        opportunity_id="brreg-123",
        title=title,
        description="Official liquidation status lead.",
        category="business_status_lead",
        evidence=("official-status:liquidation", "https://example.test/123"),
        confidence=0.7,
        source_plugin="brreg_status_extractor",
    )
    now = datetime.now(timezone.utc)
    snapshot = ScanSnapshot(
        scan_id="scan-1",
        started_at=now,
        completed_at=now,
        documents=(),
        opportunities=(candidate,),
        connector_statuses=(),
        duplicate_count=0,
    )
    ranked = RankedOpportunity(rank=1, opportunity=candidate, final_score=72.0, score_breakdown=())
    memory = MemoryRunResult(records=(), changes=())
    return BrregCollectionResult(1, 1, 0, 0, snapshot, (ranked,), memory, None, ())


def test_feed_marks_first_item_new_and_deduplicates_next_run(tmp_path) -> None:
    feed = LiveOpportunityFeed(tmp_path / "feed.json", tmp_path / "memory.json")
    feed.collector = StubCollector(_result())
    first = feed.refresh((BrregSearchSlice("butikk"),))
    second = feed.refresh((BrregSearchSlice("butikk"),))
    assert first.new_count == 1
    assert first.items[0].status == "NEW"
    assert second.new_count == 0
    assert second.unchanged_count == 1
    assert second.items[0].times_seen == 2


def test_feed_marks_changed_candidate_updated(tmp_path) -> None:
    feed = LiveOpportunityFeed(tmp_path / "feed.json", tmp_path / "memory.json")
    feed.collector = StubCollector(_result("Example AS"))
    feed.refresh((BrregSearchSlice("butikk"),))
    feed.collector = StubCollector(_result("Example Retail AS"))
    result = feed.refresh((BrregSearchSlice("butikk"),))
    assert result.updated_count == 1
    assert result.items[0].status == "UPDATED"
