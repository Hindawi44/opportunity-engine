from pathlib import Path

RUNNER = Path("scripts/run_clothing_inventory_discovery_search.py")


def test_live_runner_uses_textile_queries_and_policy() -> None:
    source = RUNNER.read_text(encoding="utf-8")
    assert "select_norway_textile_source_targeted_queries" in source
    assert "select_source_targeted_queries" not in source
    assert "apply_norway_textile_page_verification_policy" in source
    assert 'report["domain"] = "TEXTILE_AND_SEWING"' in source
    assert 'report["market_code"] = "NO"' in source


def test_policy_runs_before_final_artifact_write() -> None:
    source = RUNNER.read_text(encoding="utf-8")
    hard_gate = source.index("apply_post_verification_top5_hard_gate(result)")
    policy = source.index("apply_norway_textile_page_verification_policy(result)")
    artifact_write = source.index("write_discovery_artifacts(result")
    assert hard_gate < policy < artifact_write


def test_existing_verifier_boundaries_remain() -> None:
    source = RUNNER.read_text(encoding="utf-8")
    assert "enforce_source_channel_identity(verify_public_page(url))" in source
    assert "AuksjonenPlaywrightFallbackVerifier(" in source
    assert "verification_limit=args.verification_limit" in source
    assert '"automatic_contact": False' in source
    assert '"automatic_purchase_decision": False' in source
