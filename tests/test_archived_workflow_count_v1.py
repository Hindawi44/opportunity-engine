from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "docs" / "workflow-archive"
WORKFLOWS = ROOT / ".github" / "workflows"


def test_archive_contains_thirty_five_retired_workflow_contracts() -> None:
    archived = {
        path.name
        for path in ARCHIVE.iterdir()
        if path.suffix in {".yml", ".yaml"}
    }
    assert len(archived) == 35


def test_live_actions_directory_contains_six_workflows() -> None:
    live = [
        path
        for path in WORKFLOWS.iterdir()
        if path.suffix in {".yml", ".yaml"}
    ]
    assert len(live) == 6
