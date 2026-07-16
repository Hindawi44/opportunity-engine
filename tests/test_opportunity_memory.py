from datetime import datetime, timezone

from opportunity_engine.ods import (
    ConnectorScanStatus,
    OpportunityCandidate,
    OpportunityChangeType,
    OpportunityMemoryEngine,
    ScanSnapshot,
)


def _candidate(confidence: float = 0.7, evidence: tuple[str, ...] = ("source:a",)) -> OpportunityCandidate:
    return OpportunityCandidate(
        opportunity_id="opp-1",
        title="Inventory recovery",
        description="Recover value from surplus inventory.",
        category="inventory",
        evidence=evidence,
        confidence=confidence,
        source_plugin="test",
    )


def _snapshot(*candidates: OpportunityCandidate) -> ScanSnapshot:
    now = datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc)
    return ScanSnapshot(
        scan_id="scan-test",
        started_at=now,
        completed_at=now,
        documents=(),
        opportunities=tuple(candidates),
        connector_statuses=(ConnectorScanStatus("test", "completed", 0),),
        duplicate_count=0,
    )


def test_memory_marks_new_then_unchanged(tmp_path):
    engine = OpportunityMemoryEngine(tmp_path / "memory.json")

    first = engine.run(_snapshot(_candidate()), country="Norway")
    second = engine.run(_snapshot(_candidate()), country="Norway")

    assert first.new_count == 1
    assert second.unchanged_count == 1
    assert second.records[0].times_seen == 2
    assert second.records[0].active is True


def test_memory_marks_updated_when_confidence_or_evidence_changes(tmp_path):
    engine = OpportunityMemoryEngine(tmp_path / "memory.json")
    engine.run(_snapshot(_candidate()))

    result = engine.run(_snapshot(_candidate(0.82, ("source:a", "source:b"))))

    assert result.updated_count == 1
    assert result.changes[0].previous_confidence == 0.7
    assert result.changes[0].current_confidence == 0.82


def test_memory_marks_removed_once_and_keeps_history(tmp_path):
    engine = OpportunityMemoryEngine(tmp_path / "memory.json")
    engine.run(_snapshot(_candidate()))

    removed = engine.run(_snapshot())
    removed_again = engine.run(_snapshot())

    assert removed.removed_count == 1
    assert removed.records[0].active is False
    assert removed_again.removed_count == 0
    assert removed_again.records[0].times_seen == 1


def test_memory_persists_without_duplicate_records(tmp_path):
    path = tmp_path / "memory.json"
    OpportunityMemoryEngine(path).run(_snapshot(_candidate()))
    result = OpportunityMemoryEngine(path).run(_snapshot(_candidate()))

    assert len(result.records) == 1
    assert result.records[0].opportunity_id == "opp-1"
