from __future__ import annotations

import json
from pathlib import Path

import pytest

from opportunity_engine.discovery import checkpoint_state_restore
from opportunity_engine.discovery import commercial_anchor_outcome_learning_cli_hook as hook
from opportunity_engine.discovery.commercial_anchor_historical_bootstrap import (
    DEFAULT_BOOTSTRAP_PATH,
    load_historical_anchor_bootstrap,
)
from opportunity_engine.discovery.commercial_anchor_outcome_learning import (
    MEMORY_FILENAME,
    OUTPUT_FILENAME,
)


ROOT = Path(__file__).resolve().parents[1]


def test_run_multi_cli_registers_one_read_only_anchor_learning_callback(monkeypatch) -> None:
    registered = []
    monkeypatch.setattr(hook, "_INSTALLED", False)
    monkeypatch.setattr(hook.sys, "argv", ["scripts/run_multi_market_daily_operator_checkpoint.py"])
    monkeypatch.setattr(hook.atexit, "register", lambda callback: registered.append(callback))

    assert hook.install_commercial_anchor_outcome_learning_cli_hook() is True
    assert registered == [hook._run_anchor_outcome_learning]


def test_restore_cli_extends_only_explicit_learning_state_allowlist(monkeypatch) -> None:
    original = ("search-success-memory.json", "missed-opportunities.json")
    monkeypatch.setattr(checkpoint_state_restore, "LEARNING_STATE_FILENAMES", original)
    monkeypatch.setattr(hook, "_INSTALLED", False)
    monkeypatch.setattr(hook.sys, "argv", ["scripts/restore_previous_checkpoint_state.py"])

    assert hook.install_commercial_anchor_outcome_learning_cli_hook() is True
    assert checkpoint_state_restore.LEARNING_STATE_FILENAMES == (*original, MEMORY_FILENAME)


def test_unrelated_cli_does_not_install_anchor_learning(monkeypatch) -> None:
    registered = []
    monkeypatch.setattr(hook, "_INSTALLED", False)
    monkeypatch.setattr(hook.sys, "argv", ["pytest"])
    monkeypatch.setattr(hook.atexit, "register", lambda callback: registered.append(callback))

    assert hook.install_commercial_anchor_outcome_learning_cli_hook() is False
    assert registered == []


def test_registration_order_runs_unified_search_runtime_before_anchor_learning() -> None:
    source = (ROOT / "src/opportunity_engine/discovery/__init__.py").read_text(encoding="utf-8")
    learner = source.index("install_commercial_anchor_outcome_learning_cli_hook()\n")
    runtime = source.index("install_unified_search_runtime_cli_hook()\n")

    # atexit is LIFO: learner registered first means runtime executes first.
    assert learner < runtime


def test_callback_bootstraps_corrected_salzmann_candidate_without_search(
    tmp_path: Path, monkeypatch
) -> None:
    input_root = tmp_path / "inputs"
    output_dir = tmp_path / "output"
    monkeypatch.setenv("INPUT_ROOT", str(input_root))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))
    monkeypatch.setenv("GITHUB_RUN_ID", "live-wiring-test")

    hook._run_anchor_outcome_learning()

    report = json.loads((output_dir / OUTPUT_FILENAME).read_text(encoding="utf-8"))
    memory = json.loads(
        (input_root / "learning" / MEMORY_FILENAME).read_text(encoding="utf-8")
    )

    assert report["status"] == "SUCCESS"
    assert report["current_run_observation_count"] == 0
    assert report["candidate_success_pattern_count"] == 1
    assert report["proven_success_pattern_count"] == 0
    assert report["historical_bootstrap"]["status"] == "MERGED"
    assert report["historical_bootstrap"]["search_requests"] == 0
    assert report["automatic_query_activation"] is False
    assert report["production_mutation"] is False

    salzmann = next(
        row for row in memory["patterns"] if row.get("anchor_value") == "Salzmann Restwaren"
    )
    assert salzmann["pattern_status"] == "CANDIDATE_SUCCESS"
    assert salzmann["market_code"] == "DE"
    assert salzmann["route"] == "MULTI_HOP"
    assert salzmann["verified_exact_lot_url_count"] == 21
    assert all("/product/" in url for url in salzmann["verified_exact_lot_urls"])
    assert all("/products/" not in url for url in salzmann["verified_exact_lot_urls"])


def _same_day_salzmann_resolution(url: str) -> dict:
    return {
        "schema_version": "exa-exact-lot-checkpoint-resolution-1.7",
        "generated_at": "2026-08-25T21:00:00+00:00",
        "market": "DE",
        "project_domain": "CLOTHING_INVENTORY",
        "provider": "exa",
        "production_mutation": False,
        "commercial_anchor_outcome_evidence": {
            "schema_version": "commercial-anchor-outcome-evidence-1.0",
            "status": "SUCCESS",
            "market_code": "DE",
            "project_domain": "CLOTHING_INVENTORY",
            "provider": "exa",
            "outcome_count": 1,
            "outcomes": [
                {
                    "anchor_type": "WHOLESALER",
                    "anchor_value": "Salzmann Restwaren",
                    "anchor_origin": "CONTROLLED_COMMERCIAL_ANCHOR_EXPANSION_V1_HISTORICAL",
                    "query": (
                        "Deutschland Bekleidung clothing Salzmann Restwaren "
                        "Restposten Großhandel Lager zu verkaufen"
                    ),
                    "outcome": "STRICT_EXACT_LOT_SUCCESS",
                    "strict_exact_lot_added_count": 1,
                    "strict_exact_lot_urls": [url],
                }
            ],
            "anchor_is_qualification_evidence": False,
            "learning_evidence_only": True,
            "automatic_query_activation": False,
            "automatic_source_promotion": False,
            "production_query_mutation": False,
            "production_mutation": False,
        },
        "verification": {"verified_pages": []},
        "multihop": {"exact_lots": [{"url": url, "final_url": url}]},
    }


def test_same_day_live_success_does_not_turn_historical_candidate_into_proven(
    tmp_path: Path, monkeypatch
) -> None:
    input_root = tmp_path / "inputs"
    output_dir = tmp_path / "output"
    de_dir = input_root / "de-exa-exact-lot"
    de_dir.mkdir(parents=True)
    bootstrap_rows = load_historical_anchor_bootstrap(ROOT / DEFAULT_BOOTSTRAP_PATH)
    url = bootstrap_rows[0]["strict_exact_lot_urls"][0]
    (de_dir / "exa-exact-lot-resolution.json").write_text(
        json.dumps(_same_day_salzmann_resolution(url), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("INPUT_ROOT", str(input_root))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))
    monkeypatch.setenv("GITHUB_RUN_ID", "same-day-live-run")
    hook._run_anchor_outcome_learning()

    report = json.loads((output_dir / OUTPUT_FILENAME).read_text(encoding="utf-8"))
    memory = json.loads(
        (input_root / "learning" / MEMORY_FILENAME).read_text(encoding="utf-8")
    )
    salzmann = next(
        row for row in memory["patterns"] if row.get("anchor_value") == "Salzmann Restwaren"
    )

    assert report["candidate_success_pattern_count"] == 1
    assert report["proven_success_pattern_count"] == 0
    assert salzmann["pattern_status"] == "CANDIDATE_SUCCESS"
    assert salzmann["successful_observation_count"] == 2
    assert salzmann["checkpoint_run_count"] == 2
    assert salzmann["checkpoint_day_count"] == 1
    assert salzmann["checkpoint_days"] == ["2026-08-25"]


def test_bootstrap_refuses_reintroduction_of_aggregate_products_url(tmp_path: Path) -> None:
    payload = json.loads((ROOT / DEFAULT_BOOTSTRAP_PATH).read_text(encoding="utf-8"))
    observation = payload["observations"][0]
    observation["strict_exact_lot_urls"][0] = (
        "https://salzmann-restwaren.de/products/bekleidung/page/3/"
    )
    bad = tmp_path / "bad-bootstrap.json"
    bad.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="aggregate /products/"):
        load_historical_anchor_bootstrap(bad)
