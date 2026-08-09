from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SWEDEN = ROOT / ".github" / "workflows" / "sweden-clothing-inventory-live.yaml"
GERMANY = ROOT / ".github" / "workflows" / "germany-clothing-inventory-live.yaml"


def test_country_live_pilots_are_manual_only() -> None:
    for path in (SWEDEN, GERMANY):
        text = path.read_text(encoding="utf-8")
        assert "workflow_dispatch:" in text
        assert "\n  pull_request:" not in text
        assert "\n  schedule:" not in text


def test_country_live_pilots_keep_read_only_safety_and_no_auto_actions() -> None:
    sweden = SWEDEN.read_text(encoding="utf-8")
    germany = GERMANY.read_text(encoding="utf-8")

    assert "permissions:\n  contents: read" in sweden
    assert "permissions:\n  contents: read" in germany
    assert "BRAVE_SEARCH_API_KEY" in sweden
    assert "RIEGERMANN" in germany
    assert "OPEN_WEB" in germany
