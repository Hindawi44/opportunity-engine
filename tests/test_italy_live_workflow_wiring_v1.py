from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/research-shadow-manual.yaml"
ARCHIVED = ROOT / "docs/archive/foreign-manual-research-20260919.yaml.txt"


def test_italy_live_validation_is_historically_preserved_but_not_runnable() -> None:
    text = ARCHIVED.read_text(encoding="utf-8")
    active = WORKFLOW.read_text(encoding="utf-8")
    for marker in (
        "italy-market-discovery-live:", "Italy market discovery live validation",
        "BRAVE_SEARCH_API_KEY: ${{ secrets.BRAVE_SEARCH_API_KEY }}",
        "pytest tests/test_italy_market_discovery_v1.py -q",
        "python scripts/build_italy_market_discovery.py",
        "artifacts/italy-market-discovery/italy-market-discovery.json",
        "name: italy-market-discovery-v1", "workflow_dispatch:",
        "if: ${{ inputs.italy_live_validation }}",
    ):
        assert marker in text
    assert "italy-market-discovery-live:" not in active
    assert "BRAVE_SEARCH_API_KEY:" not in active
    assert "python scripts/build_italy_market_discovery.py" not in active
    assert "workflow_dispatch:" in active
    assert active.startswith("name: Norway Hunter Manual Verification\n")


def test_italy_live_validation_does_not_add_a_fifth_workflow() -> None:
    workflows = list((ROOT / ".github/workflows").glob("*.y*ml"))
    assert len(workflows) == 6
