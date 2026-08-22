from __future__ import annotations

from datetime import datetime, timezone
import json

from opportunity_engine.daily_learning_operator import DailyLearningPolicy
from opportunity_engine.daily_learning_runtime import run_daily_learning_runtime


def test_daily_runtime_writes_one_clear_shadow_proof_report(tmp_path) -> None:
    inbox = tmp_path / "inbox.json"
    inbox.write_text(
        json.dumps(
            {
                "schema_version": "missed-opportunity-inbox-1.0",
                "cases": [
                    {
                        "case_id": "REAL-MISS-1",
                        "market_code": "NO",
                        "discovered_by": "AUTOMATIC_SOURCE_VERIFIED_GAP_DETECTOR",
                        "observed_at": "2026-08-22T08:00:00+00:00",
                        "opportunity_type": "VERIFIED_BULK_CLOTHING_STOCK",
                        "stock_proven": True,
                        "ground_truth": {
                            "company": "Example AS",
                            "url": "https://example.no/REAL-MISS-1",
                        },
                        "trace": {"query_generated": False},
                        "learning_evidence_text": "Sluttlager med arbeidsklær selges.",
                        "root_cause": "QUERY_GAP",
                        "learning_status": "DIAGNOSED",
                        "repeat_miss": False,
                        "learned_patterns": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    learning_dir = tmp_path / "learning"

    def search(term: str, market: str):
        if term == "sluttlager":
            return [
                {
                    "url": "https://example.no/REAL-MISS-1",
                    "company": "Example AS",
                    "verified_relevant": True,
                },
                {"url": "https://noise.example/1"},
            ]
        return []

    report = run_daily_learning_runtime(
        learning_dir=learning_dir,
        inbox_path=inbox,
        active_query_config=tmp_path / "missing-queries.json",
        promotion_config_path=tmp_path / "missing-promotions.json",
        environment={},
        search_override=search,
        policy=DailyLearningPolicy(max_candidates_per_run=5, min_precision=0.2),
        observed_at=datetime(2026, 8, 22, 10, 0, tzinfo=timezone.utc),
    )

    proof_path = learning_dir / "safe-learning-proof.json"
    assert proof_path.exists()
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    assert proof["status"] == "SHADOW_PASSED"
    assert proof["shadow_recovered_case_count"] == 1
    assert proof["promotion_eligible_count"] == 1
    row = proof["cases"][0]
    assert row["baseline_missed"] is True
    assert row["shadow_recovered"] is True
    assert row["shadow_raw_hit_count"] == 2
    assert row["shadow_verified_relevant_count"] == 1
    assert row["shadow_false_positive_count"] == 1
    assert row["production_term_active"] is False
    assert row["production_unchanged_during_shadow"] is True
    assert row["automatic_promotion"] is False
    assert report["safe_learning_proof_status"] == "SHADOW_PASSED"
    assert report["safe_learning_promotion_eligible_count"] == 1
