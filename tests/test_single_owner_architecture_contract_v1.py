from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "opportunity_engine"


def _source(relative: str) -> str:
    return (SRC / relative).read_text(encoding="utf-8")


def _imports(relative: str) -> set[str]:
    tree = ast.parse(_source(relative))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            imported.add(module)
            imported.update(f"{module}.{alias.name}" for alias in node.names)
    return imported


def test_lifecycle_checkpoint_is_observer_not_lifecycle_classifier() -> None:
    source = _source("discovery/lifecycle_checkpoint_integration.py")

    assert "classify_opportunity_lifecycle" not in source
    assert "_derived_lifecycle" not in source
    assert "missing canonical lifecycle truth" in source


def test_checkpoint_does_not_resurrect_eligibility_from_local_flags() -> None:
    source = _source("discovery/multi_market_operator_checkpoint.py")

    assert "raw_top5_eligible" not in source
    assert "raw_analysis_eligible" not in source
    assert "missing canonical lifecycle truth" in source
    assert "conflicting canonical lifecycle truth" in source


def test_value_owns_financial_math_and_decision_does_not_import_cost_or_market_math() -> None:
    value_source = _source("ods/opportunity_value.py")
    decision_imports = _imports("ods/opportunity_profit.py")

    for token in (
        "expected_profit_nok",
        "margin_on_resale",
        "maximum_total_cost_nok",
        "maximum_purchase_price_nok",
        "target_roi_for_max_bid",
    ):
        assert token in value_source

    assert not any("market_pricing" in item for item in decision_imports)
    assert not any("real_cost" in item for item in decision_imports)
    assert not any("OpportunityValueEngine" in item for item in decision_imports)
    assert any("opportunity_value.OpportunityValueReport" in item for item in decision_imports)


def test_intelligence_mirrors_canonical_decision_instead_of_recommending_again() -> None:
    source = _source("ods/opportunity_intelligence.py")

    assert "def _recommendation(" not in source
    assert "recommendation = decision.decision" in source
    assert "label = decision.decision_label" in source


def test_evidence_collection_and_fact_extraction_share_one_dedupe_contract() -> None:
    live_source = _source("ods/live_data.py")
    unified_source = _source("ods/unified_opportunity.py")

    assert "def deduplicate_source_documents(" in live_source
    assert "SourceEvidenceConflictError" in live_source
    assert "deduplicate_source_documents(documents)" in unified_source
    assert "source_evidence_identity" in unified_source


def test_fact_merge_is_conflict_safe_and_auditable() -> None:
    source = _source("ods/multi_source.py")

    assert "MultiSourceFactConflictError" in source
    assert "fact_provenance" in source
    assert "canonical_fact_identity" in source
    assert "source_opportunity_ids" in source


def test_pipeline_order_is_fact_then_value_then_decision_then_observers() -> None:
    source = _source("ods/daily_pipeline.py")

    fact_index = source.index("merge_result = self.multi_source_engine.merge")
    value_index = source.index("value = self.value_engine.evaluate")
    decision_index = source.index("decision = self.decision_engine.decide")
    score_index = source.index("score = self.scoring_engine.score")
    intelligence_index = source.index("intelligence = self.intelligence_engine.explain")
    discovery_index = source.index("discovery = self.discovery_engine.discover")

    assert fact_index < value_index < decision_index
    assert decision_index < score_index < intelligence_index < discovery_index
