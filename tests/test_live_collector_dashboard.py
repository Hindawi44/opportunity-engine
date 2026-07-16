"""Static tests for the live collector Streamlit page.

The page performs network work only after a form submission, so these tests validate
syntax and the critical integration markers without making external requests.
"""
from __future__ import annotations

import ast
from pathlib import Path


PAGE = Path(__file__).resolve().parents[1] / "pages" / "Live_Collector.py"


def test_live_collector_page_is_valid_python() -> None:
    source = PAGE.read_text(encoding="utf-8")
    ast.parse(source)


def test_live_collector_page_wires_real_collector() -> None:
    source = PAGE.read_text(encoding="utf-8")
    required_markers = (
        "BrregOpportunityCollector",
        "BrregSearchSlice",
        "collector.collect(slices)",
        "brreg_opportunity_history.json",
        "OpportunityChangeType.NEW",
        "result.ranked_opportunities",
        "result.decision",
        "LinkColumn",
    )
    for marker in required_markers:
        assert marker in source


def test_live_collector_page_preserves_grounding_warning() -> None:
    source = PAGE.read_text(encoding="utf-8")
    assert "لا يفترض توفر مخزون أو معدات للبيع" in source
    assert "لا يصدر تقدير ربح" in source
