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

    assert "default: brave_discovery" in dispatch
    assert "type: choice" in dispatch
    options_match = re.search(r"        options:\n(?P<options>(?:          - .*\n)+)", dispatch)
    assert options_match is not None
    options = [
        line.removeprefix("          - ").strip()
        for line in options_match.group("options").splitlines()
    ]
    assert options == ["brave_discovery", "active_clothing_scan"]

    for required_path in (
        '      - "scripts/run_active_clothing_inventory_scan.py"',
        '      - "tests/test_active_clothing_inventory_scan.py"',
        '      - "tests/test_active_clothing_inventory_operator_integration.py"',
    ):
        assert required_path in workflow


def test_brave_and_active_scan_jobs_are_mutually_selected() -> None:
    workflow = _workflow_text()
    brave_job = _job_block(workflow, "live-pilot")
    active_job = _job_block(workflow, "active-clothing-inventory-scan")

    assert (
        "if: ${{ github.event_name == 'workflow_dispatch' && "
        "inputs.operation == 'brave_discovery' }}"
    ) in brave_job
    assert (
        "if: ${{ github.event_name == 'workflow_dispatch' && "
        "inputs.operation == 'active_clothing_scan' }}"
    ) in active_job

    assert "python scripts/run_discovery_v12_live_pilot.py" in brave_job
    assert "BRAVE_SEARCH_API_KEY: ${{ secrets.BRAVE_SEARCH_API_KEY }}" in brave_job
    assert "run_active_clothing_inventory_scan.py" not in brave_job

    assert "BRAVE_SEARCH_API_KEY" not in active_job
    assert "run_discovery_v12_live_pilot.py" not in active_job
    assert active_job.count("python scripts/run_active_clothing_inventory_scan.py") == 1
    assert "--output-dir artifacts/active-clothing-inventory-scan" in active_job


def test_active_scan_summary_and_artifact_contract() -> None:
    active_job = _job_block(_workflow_text(), "active-clothing-inventory-scan")

    assert "if: ${{ always() }}" in active_job
    assert 'summary="artifacts/active-clothing-inventory-scan/operator-summary.txt"' in active_job
    assert 'cat "$summary"' in active_job
    assert "name: active-clothing-inventory-scan" in active_job
    assert "path: artifacts/active-clothing-inventory-scan/" in active_job
    assert "if-no-files-found: error" in active_job


def test_contract_tests_preserve_discovery_and_active_scan_coverage() -> None:
    contract_job = _job_block(_workflow_text(), "contract-tests")

    required_commands = (
        "pytest tests/test_discovery_v16_quality_engine.py -q",
        "pytest tests/test_discovery_v15_result_filter.py -q",
        "pytest tests/test_discovery_v12_live_pilot.py -q",
        "pytest tests/test_active_clothing_inventory_scan.py -q",
        "pytest tests/test_active_clothing_inventory_operator_integration.py -q",
    )
    for command in required_commands:
        assert command in contract_job


def test_review_workflow_and_commercial_safety_remain_separate() -> None:
    workflow = _workflow_text()
    review_workflow = REVIEW_WORKFLOW.read_text(encoding="utf-8")

    assert "run_active_clothing_inventory_scan.py" not in review_workflow
    assert "active_clothing_scan" not in review_workflow

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
