"""Static integration checks for the unified intelligence Streamlit page."""
from __future__ import annotations

import ast
from pathlib import Path


PAGE = Path(__file__).resolve().parents[1] / "pages" / "Unified_Intelligence.py"


def test_page_is_valid_python() -> None:
    source = PAGE.read_text(encoding="utf-8")
    ast.parse(source)


def test_page_uses_real_sources_and_unified_engine() -> None:
    source = PAGE.read_text(encoding="utf-8")
    required = (
        "run_ods",
        "SSBMarketEvidenceService",
        "SSBTrendIntelligenceService",
        "BrregClient",
        "build_unified_intelligence",
        "rank_unified_reports",
        "ODS Score",
        "Evidence completeness",
    )
    for marker in required:
        assert marker in source


def test_page_preserves_missing_evidence_guardrail() -> None:
    source = PAGE.read_text(encoding="utf-8")
    assert "البيانات الناقصة لا تُخترع" in source
    assert "ليس ضمان ربح" in source
