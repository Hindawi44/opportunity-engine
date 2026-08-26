from __future__ import annotations

import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/tests.yml"
EXACT_LOT_QUERY_SOURCE = (
    "src/opportunity_engine/discovery/exa_exact_lot_shadow_hunt.py"
)


def _changed_path_gate_pattern() -> str:
    text = WORKFLOW.read_text(encoding="utf-8")
    match = re.search(r"grep -Eq '([^']+)'", text)
    assert match is not None, "auto live-proof changed-path gate regex is missing"
    return match.group(1)


def _matches_gate(path: str) -> bool:
    result = subprocess.run(
        ["grep", "-Eq", _changed_path_gate_pattern()],
        input=f"{path}\n",
        text=True,
        check=False,
    )
    return result.returncode == 0


def test_exact_lot_query_source_triggers_auto_live_proof() -> None:
    assert _matches_gate(EXACT_LOT_QUERY_SOURCE)


def test_unrelated_document_does_not_trigger_auto_live_proof() -> None:
    assert not _matches_gate("docs/README-example.md")
