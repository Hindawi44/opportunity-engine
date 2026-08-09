from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
PLAN = ROOT / "docs" / "WORKFLOW_CLEANUP_IMPLEMENTATION_PLAN_v1.0.md"

ALLOWED_DISPOSITIONS = {
    "KEEP_UNCHANGED",
    "KEEP_OPERATOR_FACING_RENAME_LATER",
    "KEEP_NARROW_TRIGGERS_LATER",
    "KEEP_SCHEDULED_SUPPORT",
    "CONVERT_TO_MANUAL_OR_PATH_SCOPED_LATER",
    "ARCHIVE_OR_DISABLE_AFTER_VERIFICATION",
    "REVIEW_REQUIRED_BEFORE_CHANGE",
}


# The implementation plan is now a historical 31-workflow baseline. Current
# .yml files must remain represented by that baseline, but archived workflow
# shells are intentionally absent from .github/workflows.
def test_cleanup_plan_represents_every_current_yml_workflow() -> None:
    text = PLAN.read_text(encoding="utf-8")
    workflow_names = sorted(path.name for path in WORKFLOWS.glob("*.yml"))

    assert len(workflow_names) == 24
    for name in workflow_names:
        assert text.count(f"`{name}`") >= 1, name

    numbered_rows = re.findall(r"^\|\s*(\d+)\s*\|\s*`([^`]+\.yml)`\s*\|", text, re.MULTILINE)
    assert len(numbered_rows) == 31
    planned_names = {name for _, name in numbered_rows}
    assert set(workflow_names).issubset(planned_names)


def test_cleanup_plan_uses_one_allowed_disposition_per_workflow_row() -> None:
    text = PLAN.read_text(encoding="utf-8")
    numbered_rows = [line for line in text.splitlines() if re.match(r"^\|\s*\d+\s*\|", line)]

    assert len(numbered_rows) == 31
    for row in numbered_rows:
        matches = [item for item in ALLOWED_DISPOSITIONS if f"`{item}`" in row]
        assert len(matches) == 1, row


def test_cleanup_plan_preserves_required_operator_and_quality_roles() -> None:
    text = PLAN.read_text(encoding="utf-8")

    assert "1 — Discover Clothing Inventory Opportunities" in text
    assert "2 — Review One Opportunity End to End" in text
    assert "`tests.yml` remains the only canonical full `pytest -q` gate" in text
    assert "No workflow file" in text or "no workflow file" in text
