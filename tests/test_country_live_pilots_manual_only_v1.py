from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
ARCHIVE = ROOT / "docs" / "workflow-archive"

PILOTS = (
    "sweden-clothing-inventory-live.yaml",
    "germany-clothing-inventory-live.yaml",
)


def test_country_live_pilots_are_archived_out_of_active_actions() -> None:
    for name in PILOTS:
        assert not (WORKFLOWS / name).exists(), name
        assert (ARCHIVE / name).exists(), name


def test_archived_country_live_pilots_preserve_manual_read_only_contract() -> None:
    for name in PILOTS:
        text = (ARCHIVE / name).read_text(encoding="utf-8")
        assert "workflow_dispatch:" in text
        assert "\n  pull_request:" not in text
        assert "\n  schedule:" not in text
        assert "permissions:\n  contents: read" in text

    sweden = (ARCHIVE / "sweden-clothing-inventory-live.yaml").read_text(
        encoding="utf-8"
    )
    germany = (ARCHIVE / "germany-clothing-inventory-live.yaml").read_text(
        encoding="utf-8"
    )
    assert "BRAVE_SEARCH_API_KEY" in sweden
    assert "RIEGERMANN" in germany
    assert "OPEN_WEB" in germany
