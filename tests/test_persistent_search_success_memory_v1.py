from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile

from opportunity_engine.discovery.checkpoint_state_restore import (
    LEARNING_STATE_FILENAMES,
    extract_previous_learning_state,
)


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/multi-market-daily-operator-checkpoint.yaml"
DAILY_SCRIPT = ROOT / "scripts/run_daily_search_success_learning.py"


def _archive_bytes(entries: dict[str, bytes]) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        for name, payload in entries.items():
            archive.writestr(name, payload)
    return buffer.getvalue()


def test_search_success_memory_is_allowlisted_and_restored(tmp_path) -> None:
    assert "search-success-memory.json" in LEARNING_STATE_FILENAMES

    memory = {
        "schema_version": "search-success-memory-1.0",
        "run_count": 2,
        "replicated_route_count": 1,
        "automatic_provider_activation": False,
        "automatic_source_promotion": False,
        "production_query_mutation": False,
        "production_mutation": False,
    }
    archive = _archive_bytes(
        {
            "artifacts/multi-market-inputs/learning/search-success-memory.json": json.dumps(memory).encode()
        }
    )

    restored = extract_previous_learning_state(archive, tmp_path)

    assert {item["filename"] for item in restored} == {"search-success-memory.json"}
    restored_memory = json.loads(
        (tmp_path / "learning" / "search-success-memory.json").read_text(encoding="utf-8")
    )
    assert restored_memory == memory


def test_daily_checkpoint_wires_durable_search_success_learning() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert 'EXA_API_KEY: ${{ secrets.EXA_API_KEY }}' in text
    assert "scripts/run_daily_search_success_learning.py" in text
    assert '"$INPUT_ROOT/learning/search-success-memory.json"' in text
    assert '"$OUTPUT_DIR/search-success-review.json"' in text
    assert '"$OUTPUT_DIR/search-success-review.txt"' in text
    assert "continue-on-error: true" in text
    assert 'cat "$OUTPUT_DIR/search-success-review.txt" >> "$OUTPUT_DIR/multi-market-phone-summary.txt"' in text

    restore = text.index("- name: Restore previous lifecycle SQLite state")
    learning = text.index("- name: Run daily Search Success shadow learning")
    build = text.index("- name: Build the three-market operator checkpoint")
    append_review = text.index("- name: Append Search Success review to phone summary")
    validate = text.index("- name: Validate checkpoint safety, coverage and lifecycle integrity")

    assert restore < learning < build < append_review < validate


def test_daily_search_success_script_keeps_learning_review_only() -> None:
    text = DAILY_SCRIPT.read_text(encoding="utf-8")

    assert "CLOTHING_INVENTORY" in text
    assert 'provider="exa"' in text
    assert 'provider_mode="exa"' in text
    assert 'query_mode="exact_lot"' in text
    assert 'markets=["FR"]' in text
    assert "update_search_success_memory" in text
    assert "REPLICATED_FOR_REVIEW" in text
    assert "CANDIDATE" in text
    assert '"automatic_provider_activation": False' in text
    assert '"automatic_source_promotion": False' in text
    assert '"production_query_mutation": False' in text
    assert '"production_mutation": False' in text
    assert "automatic_contact" in text
    assert "automatic_bid" in text
    assert "automatic_reservation" in text
    assert "automatic_purchase" in text
    assert "automatic_payment" in text
