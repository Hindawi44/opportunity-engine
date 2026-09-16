from pathlib import Path


def test_pending_investigation_script_is_a_production_dispatch_path() -> None:
    workflow = Path(
        ".github/workflows/production-dispatch-after-ci.yaml"
    ).read_text(encoding="utf-8")
    assert "run_pending_opportunity_investigation\\.py" in workflow


def test_dispatch_detects_changes_against_first_parent_of_merge_commit() -> None:
    workflow = Path(
        ".github/workflows/production-dispatch-after-ci.yaml"
    ).read_text(encoding="utf-8")
    assert 'git diff --name-only "${CURRENT}^1" "$CURRENT"' in workflow
    assert "git diff-tree --no-commit-id --name-only -r" not in workflow
