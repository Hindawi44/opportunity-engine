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


def test_health_degrades_when_a_source_fails():
    payload = health.build_health(
        {"status": "SUCCESS", "stages": [{"name": "x", "status": "SUCCESS", "exit_code": 0}]},
        {"sources": {"A": {"available": True}, "B": {"available": False, "error": "missing secret"}}},
        {"record_count": 4, "status_counts": {"SCORED": 4}},
        "now",
    )
    assert payload["overall_health"] == "DEGRADED"
    assert payload["failed_source_count"] == 1
    assert payload["registry_record_count"] == 4
