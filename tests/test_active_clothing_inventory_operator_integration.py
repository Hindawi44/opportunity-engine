import re
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DISCOVERY_WORKFLOW = (
    REPOSITORY_ROOT / ".github/workflows/discovery-v1.2-live-pilot.yml"
)
REVIEW_WORKFLOW = REPOSITORY_ROOT / ".github/workflows/v3.7-production-pilot.yml"


def _workflow_text() -> str:
    return DISCOVERY_WORKFLOW.read_text(encoding="utf-8")


def _job_block(workflow: str, job_name: str) -> str:
    match = re.search(
        rf"\n  {re.escape(job_name)}:\n(?P<body>.*?)(?=\n  [A-Za-z0-9_-]+:\n|\Z)",
        workflow,
        flags=re.DOTALL,
    )
    assert match is not None, f"Missing workflow job: {job_name}"
    return match.group("body")


def test_manual_operation_contract_and_path_scope() -> None:
    workflow = _workflow_text()

    assert workflow.startswith("name: 1 — Discover Clothing Inventory Opportunities\n")
    assert "schedule:" not in workflow

    dispatch_match = re.search(
        r"  workflow_dispatch:\n(?P<body>.*?)\njobs:\n",
        workflow,
        flags=re.DOTALL,
    )
    assert dispatch_match is not None
    dispatch = dispatch_match.group("body")

    assert "default: auksjonen_live_clothing" in dispatch
    assert "type: choice" in dispatch
    options_match = re.search(r"        options:\n(?P<options>(?:          - .*\n)+)", dispatch)
    assert options_match is not None
    options = [
        line.removeprefix("          - ").strip()
        for line in options_match.group("options").splitlines()
    ]
    assert options == [
        "auksjonen_live_clothing",
        "brave_discovery",
        "active_clothing_scan",
        "structured_clothing_discovery",
        "source_targeted_validation",
        "brave_retrieval_probe",
    ]

    for required_path in (
        '      - "src/opportunity_engine/discovery/brave_search.py"',
        '      - "src/opportunity_engine/discovery/brave_precision.py"',
        '      - "src/opportunity_engine/discovery/brave_retrieval_probe.py"',
        '      - "src/opportunity_engine/discovery/clothing_inventory_search.py"',
        '      - "src/opportunity_engine/discovery/auksjonen_public_api_adapter.py"',
        '      - "src/opportunity_engine/discovery/source_targeted_queries.py"',
        '      - "src/opportunity_engine/discovery/source_targeted_retrieval.py"',
        '      - "scripts/run_active_clothing_inventory_scan.py"',
        '      - "scripts/run_clothing_inventory_discovery_search.py"',
        '      - "scripts/run_auksjonen_live_clothing.py"',
        '      - "scripts/run_source_targeted_retrieval.py"',
        '      - "scripts/run_brave_retrieval_probe.py"',
        '      - "tests/test_discovery_v11_live_search.py"',
        '      - "tests/test_brave_precision.py"',
        '      - "tests/test_brave_retrieval_probe.py"',
        '      - "tests/test_active_clothing_inventory_scan.py"',
        '      - "tests/test_clothing_inventory_discovery_search.py"',
        '      - "tests/test_auksjonen_public_api_adapter.py"',
        '      - "tests/test_source_targeted_queries.py"',
        '      - "tests/test_source_targeted_retrieval.py"',
        '      - "tests/test_active_clothing_inventory_operator_integration.py"',
    ):
        assert required_path in workflow


def test_all_discovery_jobs_are_mutually_selected() -> None:
    workflow = _workflow_text()
    auksjonen_job = _job_block(workflow, "auksjonen-live-clothing")
    brave_job = _job_block(workflow, "live-pilot")
    active_job = _job_block(workflow, "active-clothing-inventory-scan")
    structured_job = _job_block(workflow, "structured-clothing-discovery")
    targeted_job = _job_block(workflow, "source-targeted-validation")
    probe_job = _job_block(workflow, "brave-retrieval-probe")

    assert (
        "if: ${{ github.event_name == 'workflow_dispatch' && "
        "inputs.operation == 'auksjonen_live_clothing' }}"
    ) in auksjonen_job
    assert (
        "if: ${{ github.event_name == 'workflow_dispatch' && "
        "inputs.operation == 'brave_discovery' }}"
    ) in brave_job
    assert (
        "if: ${{ github.event_name == 'workflow_dispatch' && "
        "inputs.operation == 'active_clothing_scan' }}"
    ) in active_job
    assert (
        "if: ${{ github.event_name == 'workflow_dispatch' && "
        "inputs.operation == 'structured_clothing_discovery' }}"
    ) in structured_job
    assert (
        "if: ${{ github.event_name == 'workflow_dispatch' && "
        "inputs.operation == 'source_targeted_validation' }}"
    ) in targeted_job
    assert (
        "if: ${{ github.event_name == 'workflow_dispatch' && "
        "inputs.operation == 'brave_retrieval_probe' }}"
    ) in probe_job

    assert "BRAVE_SEARCH_API_KEY" not in auksjonen_job
    assert auksjonen_job.count("python scripts/run_auksjonen_live_clothing.py") == 1
    assert "--max-listings 10" in auksjonen_job
    assert "--output-dir artifacts/auksjonen-live-clothing" in auksjonen_job
    for unrelated in (
        "run_discovery_v12_live_pilot.py",
        "run_active_clothing_inventory_scan.py",
        "run_clothing_inventory_discovery_search.py",
        "run_source_targeted_retrieval.py",
        "run_brave_retrieval_probe.py",
    ):
        assert unrelated not in auksjonen_job

    assert "python scripts/run_discovery_v12_live_pilot.py" in brave_job
    assert "BRAVE_SEARCH_API_KEY: ${{ secrets.BRAVE_SEARCH_API_KEY }}" in brave_job
    assert "run_auksjonen_live_clothing.py" not in brave_job
    assert "run_active_clothing_inventory_scan.py" not in brave_job
    assert "run_clothing_inventory_discovery_search.py" not in brave_job
    assert "run_source_targeted_retrieval.py" not in brave_job
    assert "run_brave_retrieval_probe.py" not in brave_job

    assert "BRAVE_SEARCH_API_KEY" not in active_job
    assert "run_auksjonen_live_clothing.py" not in active_job
    assert "run_discovery_v12_live_pilot.py" not in active_job
    assert "run_clothing_inventory_discovery_search.py" not in active_job
    assert "run_source_targeted_retrieval.py" not in active_job
    assert "run_brave_retrieval_probe.py" not in active_job
    assert active_job.count("python scripts/run_active_clothing_inventory_scan.py") == 1
    assert "--output-dir artifacts/active-clothing-inventory-scan" in active_job

    assert "BRAVE_SEARCH_API_KEY: ${{ secrets.BRAVE_SEARCH_API_KEY }}" in structured_job
    assert "run_auksjonen_live_clothing.py" not in structured_job
    assert "run_discovery_v12_live_pilot.py" not in structured_job
    assert "run_active_clothing_inventory_scan.py" not in structured_job
    assert "run_source_targeted_retrieval.py" not in structured_job
    assert "run_brave_retrieval_probe.py" not in structured_job
    assert structured_job.count(
        "python scripts/run_clothing_inventory_discovery_search.py"
    ) == 1
    assert "--verify-pages" in structured_job
    assert "--output-dir artifacts/clothing-inventory-discovery" in structured_job

    assert "BRAVE_SEARCH_API_KEY: ${{ secrets.BRAVE_SEARCH_API_KEY }}" in targeted_job
    assert "run_auksjonen_live_clothing.py" not in targeted_job
    assert "run_discovery_v12_live_pilot.py" not in targeted_job
    assert "run_active_clothing_inventory_scan.py" not in targeted_job
    assert "run_clothing_inventory_discovery_search.py" not in targeted_job
    assert "run_brave_retrieval_probe.py" not in targeted_job
    assert targeted_job.count("python scripts/run_source_targeted_retrieval.py") == 1
    assert "--query-budget 8" in targeted_job
    assert "--freshness none" in targeted_job
    assert "--output-dir artifacts/source-targeted-retrieval" in targeted_job

    assert "BRAVE_SEARCH_API_KEY: ${{ secrets.BRAVE_SEARCH_API_KEY }}" in probe_job
    assert "run_auksjonen_live_clothing.py" not in probe_job
    assert "run_discovery_v12_live_pilot.py" not in probe_job
    assert "run_active_clothing_inventory_scan.py" not in probe_job
    assert "run_clothing_inventory_discovery_search.py" not in probe_job
    assert "run_source_targeted_retrieval.py" not in probe_job
    assert probe_job.count("python scripts/run_brave_retrieval_probe.py") == 1
    assert "--output-dir artifacts/brave-retrieval-probe" in probe_job


def test_auksjonen_live_summary_and_artifact_contract() -> None:
    live_job = _job_block(_workflow_text(), "auksjonen-live-clothing")

    assert "if: ${{ always() }}" in live_job
    assert 'summary="artifacts/auksjonen-live-clothing/operator-summary.txt"' in live_job
    assert 'cat "$summary"' in live_job
    assert "name: auksjonen-live-clothing" in live_job
    assert "path: artifacts/auksjonen-live-clothing/" in live_job
    assert "if-no-files-found: error" in live_job


def test_active_scan_summary_and_artifact_contract() -> None:
    active_job = _job_block(_workflow_text(), "active-clothing-inventory-scan")

    assert "if: ${{ always() }}" in active_job
    assert 'summary="artifacts/active-clothing-inventory-scan/operator-summary.txt"' in active_job
    assert 'cat "$summary"' in active_job
    assert "name: active-clothing-inventory-scan" in active_job
    assert "path: artifacts/active-clothing-inventory-scan/" in active_job
    assert "if-no-files-found: error" in active_job


def test_structured_discovery_summary_and_artifact_contract() -> None:
    structured_job = _job_block(_workflow_text(), "structured-clothing-discovery")

    assert "if: ${{ always() }}" in structured_job
    assert (
        'summary="artifacts/clothing-inventory-discovery/operator-summary.txt"'
        in structured_job
    )
    assert 'cat "$summary"' in structured_job
    assert "name: clothing-inventory-discovery-top5" in structured_job
    assert "path: artifacts/clothing-inventory-discovery/" in structured_job
    assert "if-no-files-found: error" in structured_job


def test_source_targeted_summary_and_artifact_contract() -> None:
    targeted_job = _job_block(_workflow_text(), "source-targeted-validation")

    assert "if: ${{ always() }}" in targeted_job
    assert (
        'summary="artifacts/source-targeted-retrieval/'
        'source-targeted-validation-summary.txt"'
        in targeted_job
    )
    assert 'cat "$summary"' in targeted_job
    assert "name: source-targeted-clothing-retrieval" in targeted_job
    assert "path: artifacts/source-targeted-retrieval/" in targeted_job
    assert "if-no-files-found: error" in targeted_job


def test_brave_retrieval_probe_summary_and_artifact_contract() -> None:
    probe_job = _job_block(_workflow_text(), "brave-retrieval-probe")

    assert "if: ${{ always() }}" in probe_job
    assert (
        'summary="artifacts/brave-retrieval-probe/'
        'brave-retrieval-probe-summary.txt"'
        in probe_job
    )
    assert 'cat "$summary"' in probe_job
    assert "name: brave-retrieval-probe" in probe_job
    assert "path: artifacts/brave-retrieval-probe/" in probe_job
    assert "if-no-files-found: error" in probe_job


def test_contract_tests_preserve_all_discovery_operation_coverage() -> None:
    contract_job = _job_block(_workflow_text(), "contract-tests")

    required_commands = (
        "pytest tests/test_discovery_v11_live_search.py -q",
        "pytest tests/test_brave_precision.py -q",
        "pytest tests/test_brave_retrieval_probe.py -q",
        "pytest tests/test_discovery_v16_quality_engine.py -q",
        "pytest tests/test_discovery_v15_result_filter.py -q",
        "pytest tests/test_discovery_v12_live_pilot.py -q",
        "pytest tests/test_active_clothing_inventory_scan.py -q",
        "pytest tests/test_clothing_inventory_discovery_search.py -q",
        "pytest tests/test_auksjonen_public_api_adapter.py -q",
        "pytest tests/test_source_targeted_queries.py -q",
        "pytest tests/test_source_targeted_retrieval.py -q",
        "pytest tests/test_active_clothing_inventory_operator_integration.py -q",
    )
    for command in required_commands:
        assert command in contract_job


def test_review_workflow_and_commercial_safety_remain_separate() -> None:
    workflow = _workflow_text()
    review_workflow = REVIEW_WORKFLOW.read_text(encoding="utf-8")

    for discovery_only_term in (
        "run_auksjonen_live_clothing.py",
        "auksjonen_live_clothing",
        "run_active_clothing_inventory_scan.py",
        "active_clothing_scan",
        "run_clothing_inventory_discovery_search.py",
        "structured_clothing_discovery",
        "run_source_targeted_retrieval.py",
        "source_targeted_validation",
        "run_brave_retrieval_probe.py",
        "brave_retrieval_probe",
    ):
        assert discovery_only_term not in review_workflow

    lowered = workflow.casefold()
    for prohibited_term in (
        "automatic_purchase",
        "automatic_bid",
        "automatic_contact",
        "automatic_payment",
        "place_bid",
        "send_payment",
    ):
        assert prohibited_term not in lowered
