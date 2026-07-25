from pathlib import Path


WORKFLOW = Path(".github/workflows/v3.7-production-pilot.yml")


def test_v37_is_manual_only_and_preserves_operator_contract() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "name: 2 — Review One Opportunity End to End" in text
    assert "workflow_dispatch:" in text
    assert "pull_request:" not in text
    assert "schedule:" not in text
    assert '17 * * * *' not in text

    assert "production-pilot:" in text
    assert 'python-version: "3.11"' in text
    assert "pytest tests/test_v37_production_pilot.py -q" in text
    assert "python scripts/run_v37_production_pilot_acceptance.py" in text
    assert "cat artifacts/v3.7-production-pilot-summary.json" in text
    assert "name: v3.7-production-pilot-summary" in text
    assert "path: artifacts/v3.7-production-pilot-summary.json" in text

    assert "Run regression suite" not in text
    assert "run: pytest -q\n" not in text
