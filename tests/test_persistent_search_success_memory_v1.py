from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile

from opportunity_engine.discovery.checkpoint_state_restore import (
    LEARNING_STATE_FILENAMES,
    extract_previous_learning_state,
)
from scripts import run_daily_search_success_learning as daily_search_success


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/multi-market-daily-operator-checkpoint.yaml"
DAILY_SCRIPT = ROOT / "scripts/run_daily_search_success_learning.py"
QUERY_FR = "France vêtements mode lot de marchandises à vendre prix quantité stock déstockage disponible"
HUB = "https://friptadium.com/pages/lot-de-vetements-revendeur"
PRODUCT = "https://friptadium.com/products/hauts-femme-au-kilo"


def _archive_bytes(entries: dict[str, bytes]) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        for name, payload in entries.items():
            archive.writestr(name, payload)
    return buffer.getvalue()


def _benchmark() -> dict:
    return {
        "status": "SUCCESS",
        "shadow_only": True,
        "provider_mode": "exa",
        "query_mode": "exact_lot",
        "project_domain": "CLOTHING_INVENTORY",
        "project_domain_gate_enforced": True,
        "market_results": [
            {
                "market_code": "FR",
                "query": QUERY_FR,
                "exa": {"results": [{"url": HUB, "domain": "friptadium.com", "provider": "exa"}]},
                "brave": {"results": []},
            }
        ],
    }


def _verification() -> dict:
    return {
        "status": "SUCCESS",
        "provider": "exa",
        "shadow_only": True,
        "symmetric_provider_verification": True,
        "commercial_specificity_gate_enforced": True,
        "project_domain_gate_enforced": True,
        "required_project_domain": "CLOTHING_INVENTORY",
        "provider_unique_url_count": 1,
        "page_fetches_succeeded": 1,
        "verified_pages": [],
    }


def _exact() -> dict:
    return {
        "url": PRODUCT,
        "parent_url": HUB,
        "market_code": "FR",
        "query": QUERY_FR,
        "provider": "exa",
        "classification": "EXACT_LOT_CANDIDATE",
        "fetch_ok": True,
        "evidence": {
            "project_domain": "CLOTHING_INVENTORY",
            "page_subject_domain": "CLOTHING_INVENTORY",
            "inventory_evidence": True,
            "direct_sale_evidence": True,
            "item_specific_url_evidence": True,
            "price_evidence": True,
            "quantity_evidence": True,
        },
    }


def _multihop() -> dict:
    return {
        "status": "SUCCESS",
        "provider": "exa",
        "shadow_only": True,
        "required_project_domain": "CLOTHING_INVENTORY",
        "project_domain_gate_enforced": True,
        "commercial_specificity_gate_enforced": True,
        "child_subject_domain_gate_enforced": True,
        "same_origin_only": True,
        "bounded_multi_hop": True,
        "exact_lot_acceptance_only": True,
        "production_mutation": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
        "eligible_root_parent_count": 1,
        "navigation_page_fetches_succeeded": 2,
        "exact_lot_candidate_count": 1,
        "exact_lots": [_exact()],
    }


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


def test_daily_learning_persists_memory_and_promotes_only_to_review(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(daily_search_success, "run_benchmark", lambda **_: _benchmark())
    monkeypatch.setattr(
        daily_search_success,
        "verify_provider_unique_pages",
        lambda *_args, **_kwargs: _verification(),
    )
    monkeypatch.setattr(
        daily_search_success,
        "resolve_exact_lot_multihop",
        lambda *_args, **_kwargs: _multihop(),
    )

    input_root = tmp_path / "inputs"
    output_dir = tmp_path / "output"

    first = daily_search_success.run_daily_search_success_learning(
        exa_api_key="test-key",
        input_root=input_root,
        output_dir=output_dir,
        run_id="daily-run-1",
    )
    assert first["review_status"] == "CANDIDATE"
    assert first["memory_run_count"] == 1
    assert first["replicated_route_count"] == 0

    second = daily_search_success.run_daily_search_success_learning(
        exa_api_key="test-key",
        input_root=input_root,
        output_dir=output_dir,
        run_id="daily-run-2",
    )
    assert second["review_status"] == "REPLICATED_FOR_REVIEW"
    assert second["memory_run_count"] == 2
    assert second["replicated_route_count"] == 1
    assert second["routes_for_review"][0]["independent_run_count"] == 2

    memory_path = input_root / "learning" / "search-success-memory.json"
    memory = json.loads(memory_path.read_text(encoding="utf-8"))
    assert memory["run_count"] == 2
    assert memory["route_learning"][0]["status"] == "REPLICATED_FOR_REVIEW"
    assert memory["automatic_provider_activation"] is False
    assert memory["automatic_source_promotion"] is False
    assert memory["production_query_mutation"] is False
    assert memory["production_mutation"] is False

    for name in (
        "search-success-observation.json",
        "search-success-review.json",
        "search-success-review.txt",
        "search-success-benchmark.json",
        "search-success-verification.json",
        "search-success-multihop.json",
    ):
        assert (output_dir / name).exists()


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
    build = text.index(
        "- name: Build the legacy-compatible core and FR/IT/NL market cycles"
    )
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
