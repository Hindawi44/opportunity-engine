from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile

from opportunity_engine.discovery.checkpoint_state_restore import (
    extract_previous_learning_state,
)


WORKFLOW = Path(".github/workflows/multi-market-daily-operator-checkpoint.yaml")


def _archive(entries: dict[str, object]) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        for name, payload in entries.items():
            archive.writestr(name, json.dumps(payload).encode("utf-8"))
    return buffer.getvalue()


def test_previous_checkpoint_restores_shadow_keyword_evidence(tmp_path: Path) -> None:
    shadow = {
        "schema_version": "learned-query-overlay-1.0",
        "markets": {
            "NO": [
                {
                    "term": "stort avslutningssalg",
                    "evaluation_scope": "HOLDOUT_TRANSFER",
                    "transfer_validation_case_ids": ["HOLDOUT-NO-NOREM-BAADE-2010"],
                    "independent_transfer_case_count": 1,
                    "source_verdict": "PROVEN",
                }
            ]
        },
    }
    archive = _archive(
        {
            "artifacts/multi-market-inputs/learning/shadow-keyword-overlay.json": shadow,
        }
    )

    restored = extract_previous_learning_state(archive, tmp_path)

    assert {item["filename"] for item in restored} == {"shadow-keyword-overlay.json"}
    restored_shadow = json.loads(
        (tmp_path / "learning" / "shadow-keyword-overlay.json").read_text(
            encoding="utf-8"
        )
    )
    assert restored_shadow == shadow


def test_daily_workflow_consumes_captured_misses_in_learning_cycle() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    bulletin = workflow.index("- name: Build domain market intelligence bulletin")
    learning = workflow.index("- name: Run bounded learning on captured misses")
    validation = workflow.index("- name: Validate checkpoint safety, coverage and lifecycle integrity")
    upload = workflow.index("- name: Upload checkpoint and source evidence")

    assert bulletin < learning < validation < upload
    learning_block = workflow[learning:validation]
    assert "python scripts/run_daily_learning_operator.py" in learning_block
    assert '--learning-dir "$INPUT_ROOT/learning"' in learning_block
    assert '--report "$OUTPUT_DIR/daily-learning-cycle.json"' in learning_block
    assert '--max-candidates 2' in learning_block
    assert '--results-per-candidate 5' in learning_block
    assert "--min-precision 0.20" in learning_block


def test_daily_workflow_validates_learning_safety_contract() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert 'daily-learning-cycle.json' in workflow
    assert 'safe-learning-proof.json' in workflow
    assert 'automatic_query_activation' in workflow
    assert 'promotion_gate_enforced' in workflow
    assert 'active_learned_term_count' in workflow
    assert 'shadow_proven_term_count' in workflow


def test_learning_code_changes_trigger_checkpoint_contract_ci() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    required_paths = (
        'scripts/run_daily_learning_operator.py',
        'src/opportunity_engine/daily_learning_runtime.py',
        'src/opportunity_engine/daily_learning_operator.py',
        'src/opportunity_engine/automatic_missed_opportunity_capture.py',
        'src/opportunity_engine/discovery/checkpoint_state_restore.py',
        'tests/test_daily_auto_miss_learning_wiring_v1.py',
    )
    for path in required_paths:
        assert f'- "{path}"' in workflow

    contract_test_block = workflow[
        workflow.index("- name: Test the multi-market checkpoint contract") :
        workflow.index("operator-read-only-checkpoint:")
    ]
    assert "pytest tests/test_daily_auto_miss_learning_wiring_v1.py -q" in contract_test_block
