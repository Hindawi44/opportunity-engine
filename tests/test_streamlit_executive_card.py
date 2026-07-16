"""Static safety checks for the main Streamlit executive decision card."""

from __future__ import annotations

import ast
from pathlib import Path


def test_main_dashboard_is_valid_python_and_contains_executive_card() -> None:
    source = Path("streamlit_app.py").read_text(encoding="utf-8")

    ast.parse(source)
    assert "ExecutiveWorkflowInputs" in source
    assert "build_decision_from_analysis" in source
    assert "Executive Decision — القرار التنفيذي" in source
    assert "financial = None" in source


def test_main_dashboard_passes_available_evidence_without_inventing_values() -> None:
    source = Path("streamlit_app.py").read_text(encoding="utf-8")

    assert "evidence.evidence_score if evidence else None" in source
    assert "trend.market_health_score if trend else None" in source
    assert "trend.confidence if trend else None" in source
    assert "brreg=brreg_summary" in source
