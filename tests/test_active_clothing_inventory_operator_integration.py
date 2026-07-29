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

    assert "default: cross_source_clothing_verification" in dispatch
    assert "type: choice" in dispatch
    options_match = re.search(r"        options:\n(?P<options>(?:          - .*\n)+)", dispatch)
    assert options_match is not None
    options = [
        line.removeprefix("          - ").strip()
        for line in options_match.group("options").splitlines()
    ]
    assert options == [
        "cross_source_clothing_verification",
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
        '      - "src/opportunity_engine/discovery/auksjonen_multi_category_adapter.py"',
        '      - "src/opportunity_engine/discovery/konkurs_app_clothing_adapter.py"',
        '      - "src/opportunity_engine/discovery/cross_source_clothing_sale_verifier.py"',
        '      - "src/opportunity_engine/discovery/source_targeted_queries.py"',
        '      - "src/opportunity_engine/discovery/source_targeted_retrieval.py"',
        '      - "scripts/run_active_clothing_inventory_scan.py"',
        '      - "scripts/run_clothing_inventory_discovery_search.py"',
        '      - "scripts/run_auksjonen_live_clothing.py"',
        '      - "scripts/run_cross_source_clothing_verification.py"',
        '      - "scripts/run_source_targeted_retrieval.py"',
        '      - "scripts/run_brave_retrieval_probe.py"',
        '      - "tests/test_discovery_v11_live_search.py"',
        '      - "tests/test_brave_precision.py"',
        '      - "tests/test_brave_retrieval_probe.py"',
        '      - "tests/test_active_clothing_inventory_scan.py"',
        '      - "tests/test_clothing_inventory_discovery_search.py"',
        '      - "tests/test_auksjonen_public_api_adapter.py"',
        '      - "tests/test_auksjonen_multi_category_adapter.py"',
        '      - "tests/test_konkurs_app_clothing_adapter.py"',
        '      - "tests/test_cross_source_clothing_sale_verifier.py"',
        '      - "tests/test_source_targeted_queries.py"',
        '      - "tests/test_source_targeted_retrieval.py"',
        '      - "tests/test_active_clothing_inventory_operator_integration.py"',
    ):
        assert required_path in workflow


def test_all_discovery_jobs_are_mutually_selected() -> None:
    workflow = _workflow_text()
    cross_source_job = _job_block(workflow, "cross-source-clothing-verification")
    auksjonen_job = _job_block(workflow, "auksjonen-live-clothing")
    brave_job = _job_block(workflow, "live-pilot")
    active_job = _job_block(workflow, "active-clothing-inventory-scan")
    structured_job = _job_block(workflow, "structured-clothing-discovery")
    targeted_job = _job_block(workflow, "source-targeted-validation")
    probe_job = _job_block(workflow, "brave-retrieval-probe")

    assert (
        "if: ${{ github.event_name == 'workflow_dispatch' && "
        "inputs.operation == 'cross_source_clothing_verification' }}"
    ) in cross_source_job
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

    assert "BRAVE_SEARCH_API_KEY" not in cross_source_job
    assert "OPENAI" not in cross_source_job.upper()
    assert cross_source_job.count(
        "python scripts/run_cross_source_clothing_verification.py"
    ) == 1
    assert "--max-bankruptcy-leads 100" in cross_source_job
    assert "--max-detail-pages 5" in cross_source_job
    assert "cross-source-clothing-verification" in cross_source_job

    assert "BRAVE_SEARCH_API_KEY" not in auksjonen_job
    assert auksjonen_job.count("python scripts/run_auksjonen_live_clothing.py") == 1
    assert "--max-listings 10" in auksjonen_job
    assert "--output-dir artifacts/auksjonen-live-clothing" in auksjonen_job
