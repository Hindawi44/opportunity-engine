from __future__ import annotations

from pathlib import Path

from scripts.run_sweden_clothing_inventory_discovery_search import (
    TARGETED_SOURCES,
    _effective_brave_freshness,
)


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts/run_sweden_clothing_inventory_discovery_search.py"


def test_direct_sweden_sources_ignore_search_index_age() -> None:
    assert TARGETED_SOURCES == frozenset({"psauction", "klaravik", "blinto"})
    for source in TARGETED_SOURCES:
        assert _effective_brave_freshness(source, "pd") == "none"
        assert _effective_brave_freshness(source, "pw") == "none"
        assert _effective_brave_freshness(source, "pm") == "none"
        assert _effective_brave_freshness(source, "py") == "none"
        assert _effective_brave_freshness(source, "none") == "none"


def test_open_web_keeps_requested_freshness() -> None:
    for freshness in ("none", "pd", "pw", "pm", "py"):
        assert _effective_brave_freshness("open-web", freshness) == freshness


def test_runner_reports_requested_and_effective_freshness_separately() -> None:
    text = RUNNER.read_text(encoding="utf-8")
    assert 'report["brave_freshness_requested"] = args.freshness' in text
    assert 'report["brave_freshness"] = effective_freshness' in text
    assert 'report["source_status_verification_authoritative"]' in text
    assert "freshness=None if effective_freshness == \"none\"" in text
