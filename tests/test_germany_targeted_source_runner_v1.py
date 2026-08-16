from __future__ import annotations

from pathlib import Path

from scripts.run_germany_clothing_inventory_discovery_search import (
    TARGETED_SOURCES,
    _effective_brave_freshness,
)


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts/run_germany_clothing_inventory_discovery_search.py"


def test_sen_sen_ignores_search_index_age_before_exact_page_verification() -> None:
    assert TARGETED_SOURCES == frozenset({"sen-sen"})
    for freshness in ("none", "pd", "pw", "pm", "py"):
        assert _effective_brave_freshness("sen-sen", freshness) == "none"


def test_germany_open_web_keeps_requested_freshness() -> None:
    for freshness in ("none", "pd", "pw", "pm", "py"):
        assert _effective_brave_freshness("open-web", freshness) == freshness


def test_runner_exposes_source_and_freshness_diagnostics() -> None:
    text = RUNNER.read_text(encoding="utf-8")
    assert 'choices=("open-web", "sen-sen")' in text
    assert 'report["source_diagnostics"] = source_diagnostics' in text
    assert 'report["brave_freshness_requested"] = args.freshness' in text
    assert 'report["brave_freshness"] = effective_freshness' in text
    assert 'report["source_status_verification_authoritative"]' in text
