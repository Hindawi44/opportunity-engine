from __future__ import annotations

import json
from pathlib import Path

from opportunity_engine.parser_gap_rescue import save_parser_rescue_overlay
from opportunity_engine.parser_learning_promotion_gate import (
    load_parser_promotion_decisions,
    select_promoted_parser_terms,
)
from scripts.run_auksjonen_live_clothing import _parser_rescue_terms


SHADOW_OVERLAY = {
    "schema_version": "parser-gap-rescue-overlay-1.0",
    "sources": {
        "Auksjonen.no": [
            {
                "term": "sluttlager",
                "status": "PROVEN_BY_VERIFIED_PARSER_GAP",
                "raw_match_count": 1,
                "verified_case_ids": ["real-parser-gap-1"],
                "source": "Auksjonen.no",
                "affects": "INVENTORY_LOT_SIGNAL_ONLY",
            }
        ]
    },
}


def test_proven_parser_term_stays_shadow_only_without_explicit_promotion() -> None:
    assert select_promoted_parser_terms(SHADOW_OVERLAY, {}, "Auksjonen.no") == ()


def test_explicit_promotion_activates_only_proven_shadow_term() -> None:
    decisions = {
        ("Auksjonen.no", "sluttlager"): "PROMOTED",
        ("Auksjonen.no", "invented-term"): "PROMOTED",
    }

    assert select_promoted_parser_terms(
        SHADOW_OVERLAY,
        decisions,
        "Auksjonen.no",
    ) == ("sluttlager",)


def test_disabled_decision_rolls_back_runtime_term_without_deleting_shadow_evidence() -> None:
    decisions = {("Auksjonen.no", "sluttlager"): "DISABLED"}

    assert select_promoted_parser_terms(
        SHADOW_OVERLAY,
        decisions,
        "Auksjonen.no",
    ) == ()
    assert SHADOW_OVERLAY["sources"]["Auksjonen.no"][0]["term"] == "sluttlager"


def test_parser_promotion_config_requires_auditable_decision(tmp_path: Path) -> None:
    path = tmp_path / "parser-promotions.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "parser-promotion-gate-1.0",
                "decisions": [
                    {
                        "source": "Auksjonen.no",
                        "term": "sluttlager",
                        "status": "PROMOTED",
                        "reason": "Shadow parser replay recovered a verified missed lot.",
                        "approved_at": "2026-08-22T10:30:00Z",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert load_parser_promotion_decisions(path) == {
        ("Auksjonen.no", "sluttlager"): "PROMOTED"
    }


def test_runtime_helper_keeps_proven_term_out_until_promoted(tmp_path: Path) -> None:
    overlay_path = tmp_path / "parser-rescue-overlay.json"
    save_parser_rescue_overlay(overlay_path, SHADOW_OVERLAY)
    missing_promotions = tmp_path / "missing-parser-promotions.json"

    shadow_terms, promoted_terms = _parser_rescue_terms(
        overlay_path,
        missing_promotions,
    )

    assert shadow_terms == ("sluttlager",)
    assert promoted_terms == ()

    promotion_path = tmp_path / "parser-promotions.json"
    promotion_path.write_text(
        json.dumps(
            {
                "schema_version": "parser-promotion-gate-1.0",
                "decisions": [
                    {
                        "source": "Auksjonen.no",
                        "term": "sluttlager",
                        "status": "PROMOTED",
                        "reason": "Verified shadow parser proof passed.",
                        "approved_at": "2026-08-22T10:30:00Z",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    shadow_terms, promoted_terms = _parser_rescue_terms(
        overlay_path,
        promotion_path,
    )

    assert shadow_terms == ("sluttlager",)
    assert promoted_terms == ("sluttlager",)


def test_auksjonen_runtime_requires_parser_promotion_gate() -> None:
    source = Path("scripts/run_auksjonen_live_clothing.py").read_text(encoding="utf-8")

    assert "load_parser_promotion_decisions" in source
    assert "select_promoted_parser_terms" in source
    assert "--parser-rescue-promotions" in source
    assert "Parser shadow terms available" in source
    assert "Parser promoted terms loaded" in source
