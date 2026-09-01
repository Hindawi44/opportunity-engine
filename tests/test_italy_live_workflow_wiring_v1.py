from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/research-shadow-manual.yaml"


def test_italy_live_validation_reuses_existing_workflow() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "italy-market-discovery-live:" in text
    assert "Italy market discovery live validation" in text
    assert "BRAVE_SEARCH_API_KEY: ${{ secrets.BRAVE_SEARCH_API_KEY }}" in text
    assert "pytest tests/test_italy_market_discovery_v1.py -q" in text
    assert "python scripts/build_italy_market_discovery.py" in text
    assert "artifacts/italy-market-discovery/italy-market-discovery.json" in text
    assert "name: italy-market-discovery-v1" in text
    assert "workflow_dispatch:" in text
    assert "if: ${{ inputs.italy_live_validation }}" in text


def test_italy_live_validation_does_not_add_a_fifth_workflow() -> None:
    workflows = list((ROOT / ".github/workflows").glob("*.y*ml"))
    assert len(workflows) == 6
