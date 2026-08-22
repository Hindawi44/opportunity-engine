from __future__ import annotations

import json
from pathlib import Path


REQUIRED_HOLDOUTS = {
    "HOLDOUT-NO-MARNBURG-2008": "https://www.dagsavisen.no/nyheter/marnburg-legger-ned-ostehuset-flytter-inn/6791594",
    "HOLDOUT-NO-FAGHANDEL-SURNADAL-2024": "https://www.trollheimsporten.no/coop-surnadal-sport1-surnadal-surnadalsnytt/avviklingssalg-pa-faghandel-surnadal/288445",
}


def test_validation_pack_contains_two_independent_avviklingssalg_holdouts() -> None:
    payload = json.loads(Path("config/learning/query_gap_validation_cases.json").read_text(encoding="utf-8"))
    rows = {row["case_id"]: row for row in payload["cases"]}

    for case_id, expected_url in REQUIRED_HOLDOUTS.items():
        assert case_id in rows
        row = rows[case_id]
        assert row["discovered_by"] == "HIDDEN_VALIDATION_PUBLIC_SOURCE"
        assert row["root_cause"] == "VALIDATION_HOLDOUT"
        assert row["learning_status"] == "HOLDOUT"
        assert row["stock_proven"] is True
        assert row["ground_truth"]["url"] == expected_url
        assert "BAUHAUS" not in row["ground_truth"]["company"].upper()

    assert len(set(REQUIRED_HOLDOUTS.values())) == 2
