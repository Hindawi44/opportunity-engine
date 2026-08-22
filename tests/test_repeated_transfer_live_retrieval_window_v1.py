from __future__ import annotations

import json
from pathlib import Path


HOOK = Path("src/opportunity_engine/discovery/daily_auto_miss_learning_cli_hook.py")
VALIDATION = Path("config/learning/query_gap_validation_cases.json")

LIVE_REACHABLE_HOLDOUTS = {
    "HOLDOUT-NO-SENZE-OF-JOY": (
        "Senze of Joy",
        "https://www.lagersalg.no/lagersalg/avviklingssalg-senze-of-joy-2",
    ),
    "HOLDOUT-NO-TOFF-OG-LITEN-STEINKJER": (
        "Tøff og Liten",
        "https://www.steinkjer-avisa.no/amfi-butikk-stenger-dorene/s/5-117-364719",
    ),
    "HOLDOUT-NO-GAULA-NATURSENTER": (
        "Gaula Natursenter AS",
        "https://www.mgk.no/avviklingssalg",
    ),
}


def test_scheduled_learning_reads_ten_results_per_candidate_without_more_requests() -> None:
    hook = HOOK.read_text(encoding="utf-8")
    assert "max_candidates_per_run=2" in hook
    assert "results_per_candidate=10" in hook
    assert "results_per_candidate=5" not in hook


def test_validation_pack_has_distinct_live_reachable_avviklingssalg_holdouts() -> None:
    payload = json.loads(VALIDATION.read_text(encoding="utf-8"))
    rows = {row["case_id"]: row for row in payload["cases"]}

    companies: list[str] = []
    urls: list[str] = []
    for case_id, (expected_company, expected_url) in LIVE_REACHABLE_HOLDOUTS.items():
        assert case_id in rows
        row = rows[case_id]
        assert row["discovered_by"] == "HIDDEN_VALIDATION_PUBLIC_SOURCE"
        assert row["root_cause"] == "VALIDATION_HOLDOUT"
        assert row["learning_status"] == "HOLDOUT"
        assert row["stock_proven"] is True
        assert row["ground_truth"]["company"] == expected_company
        assert row["ground_truth"]["url"] == expected_url
        companies.append(expected_company.casefold())
        urls.append(expected_url)

    assert len(companies) == len(set(companies)) == 3
    assert len(urls) == len(set(urls)) == 3

    # Multiple Brave URLs for the same Senze of Joy event must never masquerade
    # as independent transfer proof.
    senze_rows = [
        row
        for row in payload["cases"]
        if str((row.get("ground_truth") or {}).get("company") or "").casefold()
        == "senze of joy"
    ]
    assert len(senze_rows) == 1
