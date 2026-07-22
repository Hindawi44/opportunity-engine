import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


registry = load_module("opportunity_registry", ROOT / "scripts" / "build_opportunity_registry.py")
health = load_module("discovery_health", ROOT / "scripts" / "build_discovery_health_report.py")
gaps = load_module("source_gap_matrix", ROOT / "scripts" / "build_source_gap_matrix.py")


def test_registry_deduplicates_and_preserves_first_seen():
    discovery = {"items": [{"lead_id": "x", "title": "Reol", "url": "https://EXAMPLE.no/a?utm_source=x"}]}
    scored = {"opportunities": [{"opportunity_id": "x", "opportunity_score": 80, "recommendation": "BUY_REVIEW"}]}
    first = registry.build_registry(discovery, scored, {}, "2026-07-22T10:00:00+00:00")
    second = registry.build_registry(discovery, scored, first, "2026-07-22T11:00:00+00:00")
    assert second["record_count"] == 1
    record = second["records"][0]
    assert record["first_seen_at"] == "2026-07-22T10:00:00+00:00"
    assert record["runs_seen"] == 2
    assert record["lifecycle_status"] == "ACTIONABLE_REVIEW"


def test_registry_marks_missing_items_without_deleting_history():
    existing = {"records": [{"registry_id": "old", "first_seen_at": "t0", "runs_seen": 3}]}
    payload = registry.build_registry({}, {}, existing, "t1")
    assert payload["record_count"] == 1
    assert payload["records"][0]["lifecycle_status"] == "NOT_SEEN_THIS_RUN"


def test_health_reads_source_funnel_and_degrades_when_active_source_fails():
    payload = health.build_health(
        {"status": "SUCCESS", "stages": [{"name": "x", "status": "SUCCESS", "exit_code": 0}]},
        {"sources": [
            {"source": "A", "active": True, "configured": True, "status": "collecting", "fetched": 4},
            {"source": "B", "active": True, "configured": True, "status": "failed", "fetched": 0, "error": "timeout"},
            {"source": "C", "active": False, "configured": False, "status": "awaiting_authorized_configuration", "required_configuration": ["TOKEN"]},
        ]},
        {"record_count": 4, "status_counts": {"SCORED": 4}},
        "now",
    )
    assert payload["source_count"] == 3
    assert payload["overall_health"] == "DEGRADED"
    assert payload["failed_source_count"] == 1
    assert payload["registry_record_count"] == 4
    assert next(item for item in payload["sources"] if item["source"] == "B")["health"] == "FAILED"
    assert next(item for item in payload["sources"] if item["source"] == "C")["health"] == "BLOCKED"


def test_healthy_is_impossible_when_enabled_source_has_error():
    payload = health.build_health(
        {"status": "SUCCESS", "stages": []},
        {"sources": [{"source": "A", "active": True, "configured": True, "status": "collecting", "error": "403"}]},
        {},
        "now",
    )
    assert payload["overall_health"] != "HEALTHY"


def test_gap_matrix_uses_only_official_statuses():
    plan = {"markets": [{"market": "Norway", "sources": [
        {"source": "A", "priority": 1, "audit_status": "ACTIVE"},
        {"source": "B", "priority": 2, "audit_status": "BLOCKED_AUTH"},
        {"source": "C", "priority": 3, "audit_status": "PLANNED"},
        {"source": "D", "priority": 4, "audit_status": "DEPRECATED"},
    ]}]}
    funnel = {"sources": [
        {"source": "A", "active": True, "configured": True, "fetched": 10},
        {"source": "B", "active": False, "configured": False, "required_configuration": ["KEY"]},
    ]}
    payload = gaps.build_matrix(plan, funnel, "now")
    statuses = {row["status"] for row in payload["sources"]}
    assert statuses <= gaps.ALLOWED
    assert payload["status_counts"]["ACTIVE"] == 1
    assert payload["status_counts"]["BLOCKED_AUTH"] == 1
    assert payload["status_counts"]["PLANNED"] == 1
    assert payload["status_counts"]["DEPRECATED"] == 1


def test_configured_but_inactive_source_is_code_ready():
    status = gaps.classify(
        {"source": "X", "audit_status": "PLANNED"},
        {"source": "X", "configured": True, "active": False, "required_configuration": []},
    )
    assert status == "CODE_READY"
