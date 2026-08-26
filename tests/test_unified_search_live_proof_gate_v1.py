from pathlib import Path


WORKFLOW = Path(".github/workflows/tests.yml")


def test_auto_dispatch_gate_covers_unified_search_runtime_changes() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    required_paths = (
        "automatic_query_gap_miss_scout_cli_hook",
        "exa_403_extractive_evidence_shadow_v1",
        "exa_search",
        "market_fit_evidence_v1",
        "provider_unique_page_verification",
        "six_market_fabric_coverage_rotation_v1",
        "unified_search_runtime_cli_hook",
        "unified_search_truth_reconciliation_cli_hook",
    )
    for path_token in required_paths:
        assert path_token in text

    assert "Auto-dispatch live checkpoint after relevant main change" in text
    assert "actions: write" in text
    assert "multi-market-daily-operator-checkpoint.yaml" in text


def test_live_proof_gate_does_not_create_a_second_search_runtime() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    # The gate may dispatch the established operator checkpoint only. It must not
    # add a new search workflow, provider, market or runtime command.
    assert "TARGET_WORKFLOW: multi-market-daily-operator-checkpoint.yaml" in text
    assert "run_exa_exact_lot_checkpoint" in text
    assert "new-runtime" not in text.casefold()
