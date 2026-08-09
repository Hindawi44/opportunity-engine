from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "docs" / "workflow-archive"
WORKFLOWS = ROOT / ".github" / "workflows"


def test_archive_contains_thirty_three_retired_workflow_contracts() -> None:
    archived = {
        path.name
        for path in ARCHIVE.iterdir()
        if path.suffix in {".yml", ".yaml"}
    }
    assert len(archived) == 33


def test_live_actions_directory_contains_five_workflows() -> None:
    live = [
        path
        for path in WORKFLOWS.iterdir()
        if path.suffix in {".yml", ".yaml"}
    ]
    assert len(live) == 5
