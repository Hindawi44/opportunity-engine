from pathlib import Path


RUNNER = Path("scripts/run_source_targeted_retrieval.py")


def test_strict_runner_uses_norway_textile_source_targeted_queries() -> None:
    source = RUNNER.read_text(encoding="utf-8")

    assert "select_norway_textile_source_targeted_queries" in source
    assert "discovery_queries = select_norway_textile_source_targeted_queries(" in source
    assert "select_source_targeted_queries(args.query_budget)" not in source
    assert '"domain": "TEXTILE_AND_SEWING"' in source
    assert '"market_code": "NO"' in source
    assert '"taxonomy_aware_queries": True' in source


def test_strict_runner_preserves_existing_safety_gates() -> None:
    source = RUNNER.read_text(encoding="utf-8")

    assert "run_clothing_inventory_discovery(" in source
    assert "apply_early_opportunity_gate(raw_result)" in source
    assert "apply_post_verification_top5_hard_gate(result)" in source
    assert "SourceTargetedSearchProvider(" in source
    assert '"automatic_contact": False' in source
    assert '"automatic_purchase_decision": False' in source
    assert '"page_verification_performed": False' in source
    assert '"playwright_used": False' in source
    assert '"analysis_engine_used": False' in source


def test_strict_runner_keeps_zero_hit_diagnostics_fail_closed() -> None:
    source = RUNNER.read_text(encoding="utf-8")

    assert 'if diagnostics["zero_raw_hits"]:' in source
    assert 'and not diagnostics["zero_raw_hits"]' in source
    assert '"source_targeting_zero_raw_hits": diagnostics["zero_raw_hits"]' in source
