from __future__ import annotations

import json
from pathlib import Path
import sys

from scripts import collect_brave_search_results


def _write_config(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "country": "NO",
                "search_lang": "nb",
                "results_per_query": 1,
                "max_queries_per_run": 2,
                "queries": [
                    "konkurssalg varelager tekstil Norge",
                    "varelager konkursbo Norge",
                    "klesstativ utstillingsdukker selges Norge",
                ],
            }
        ),
        encoding="utf-8",
    )


def _write_active_overlay(path: Path, *, safe: bool = True) -> None:
    row = {
        "term": "avviklingssalg",
        "signal_type": "BUSINESS_CLOSURE",
        "precision": 0.333333,
        "source_verdict": "PROVEN",
        "evaluation_scope": "HOLDOUT_TRANSFER",
        "transfer_validation_case_ids": [
            "HOLDOUT-NO-SENZE-OF-JOY",
            "HOLDOUT-NO-TOFF-OG-LITEN-STEINKJER",
            "HOLDOUT-NO-GAULA-NATURSENTER",
        ],
        "independent_transfer_case_count": 3,
    }
    if safe:
        row["promotion_status"] = "PROMOTED"
        row["activation_source"] = "EXPLICIT_PROMOTION"
    payload = {
        "schema_version": "learned-query-overlay-1.0",
        "markets": {"NO": [row]},
        "max_terms_per_market": 5,
        "active_term_count": 1,
        "automatic_query_activation": False,
        "promotion_gate_enforced": safe,
        "activation_source": "EXPLICIT_PROMOTION" if safe else "SHADOW",
        "automatic_financial_action": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_promoted_learning_uses_core_query_slot_without_extra_request(
    monkeypatch, tmp_path
) -> None:
    config_path = tmp_path / "brave-search.json"
    overlay_path = tmp_path / "active-keyword-overlay.json"
    output_path = tmp_path / "web-search-results.json"
    _write_config(config_path)
    _write_active_overlay(overlay_path)

    calls: list[str] = []

    class RecordingClient:
        def __init__(self, api_key: str) -> None:
            assert api_key == "secret"

        def search(
            self, query: str, *, count: int, country: str, search_lang: str
        ) -> list[dict[str, object]]:
            assert count == 1
            assert country == "NO"
            assert search_lang == "nb"
            calls.append(query)
            return []

    monkeypatch.setenv("BRAVE_API_KEY", "secret")
    monkeypatch.setenv(
        "OPPORTUNITY_LEARNED_QUERY_OVERLAY_PATH", str(overlay_path)
    )
    monkeypatch.setattr(
        collect_brave_search_results, "BraveSearchClient", RecordingClient
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "collect_brave_search_results.py",
            "--config",
            str(config_path),
            "--output",
            str(output_path),
        ],
    )

    assert collect_brave_search_results.main() == 0
    assert calls == [
        '"avviklingssalg"',
        "konkurssalg varelager tekstil Norge",
    ]

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["request_count"] == 2
    assert payload["learned_query_overlay"]["active_terms"] == ["avviklingssalg"]
    assert payload["learned_query_overlay"]["applied_terms"] == ["avviklingssalg"]
    assert payload["learned_query_overlay"]["learned_query_slot_count"] == 1
    assert payload["learned_query_overlay"]["extra_search_requests"] == 0
    assert payload["learned_query_overlay"]["request_budget_unchanged"] is True


def test_unpromoted_overlay_cannot_enter_core_query_plan(monkeypatch, tmp_path) -> None:
    config_path = tmp_path / "brave-search.json"
    overlay_path = tmp_path / "shadow-disguised-as-active.json"
    output_path = tmp_path / "web-search-results.json"
    _write_config(config_path)
    _write_active_overlay(overlay_path, safe=False)

    calls: list[str] = []

    class RecordingClient:
        def __init__(self, api_key: str) -> None:
            assert api_key == "secret"

        def search(
            self, query: str, *, count: int, country: str, search_lang: str
        ) -> list[dict[str, object]]:
            calls.append(query)
            return []

    monkeypatch.setenv("BRAVE_API_KEY", "secret")
    monkeypatch.setenv(
        "OPPORTUNITY_LEARNED_QUERY_OVERLAY_PATH", str(overlay_path)
    )
    monkeypatch.setattr(
        collect_brave_search_results, "BraveSearchClient", RecordingClient
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "collect_brave_search_results.py",
            "--config",
            str(config_path),
            "--output",
            str(output_path),
        ],
    )

    assert collect_brave_search_results.main() == 0
    assert calls == [
        "konkurssalg varelager tekstil Norge",
        "varelager konkursbo Norge",
    ]
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["learned_query_overlay"]["applied_terms"] == []
