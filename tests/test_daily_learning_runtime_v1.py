from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from opportunity_engine.daily_learning_operator import DailyLearningPolicy
from opportunity_engine.daily_learning_runtime import run_daily_learning_runtime
from opportunity_engine.learned_query_overlay import load_learned_query_overlay
from opportunity_engine.missed_opportunity_learning import load_missed_opportunity_memory


def write_inbox(path: Path) -> None:
    payload = {
        "schema_version": "missed-opportunity-inbox-1.0",
        "cases": [
            {
                "case_id": "MISS-1",
                "market_code": "NO",
                "discovered_by": "human",
                "observed_at": "2026-08-22T07:00:00+00:00",
                "opportunity_type": "STOCK_LIQUIDATION",
                "stock_proven": True,
                "ground_truth": {
                    "company": "Example AS",
                    "url": "https://example.no/MISS-1"
                },
                "trace": {"query_generated": False},
                "learning_evidence_text": "Sluttlager med arbeidsklær selges.",
                "root_cause": "QUERY_GAP",
                "learning_status": "DIAGNOSED",
                "repeat_miss": False,
                "learned_patterns": []
            }
        ]
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_runtime_persists_recovered_memory_overlay_history_and_runtime_copy(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox.json"
    write_inbox(inbox)
    learning_dir = tmp_path / "inputs" / "learning"
    report_path = tmp_path / "output" / "daily-learning.json"
    runtime_overlay = tmp_path / "runtime" / "active-keyword-overlay.json"

    def search(term: str, market: str):
        if term == "sluttlager":
            return [
                {"url": "https://example.no/MISS-1", "verified_relevant": True},
                {"url": "https://noise.example/1"},
            ]
        return []

    report = run_daily_learning_runtime(
        learning_dir=learning_dir,
        inbox_path=inbox,
        active_query_config=tmp_path / "missing-config.json",
        report_path=report_path,
        runtime_overlay_path=runtime_overlay,
        environment={},
        policy=DailyLearningPolicy(max_candidates_per_run=2),
        results_per_candidate=5,
        search_override=search,
        observed_at=datetime(2026, 8, 22, 8, 0, tzinfo=timezone.utc),
    )

    assert report["learning_search_requests"] >= 1
    assert report["proven_term_count_this_run"] >= 1
    assert report_path.exists()
    assert (learning_dir / "keyword-learning-history.json").exists()
    assert runtime_overlay.exists()
    overlay = load_learned_query_overlay(runtime_overlay)
    assert any(
        row["term"] == "sluttlager"
        for row in overlay["markets"]["NO"]
    )
    memory = load_missed_opportunity_memory(learning_dir / "missed-opportunities.json")
    learned = next(item for item in memory if item.case_id == "MISS-1")
    assert learned.learning_status == "RECOVERED"
    assert "sluttlager" in learned.learned_patterns


def test_runtime_without_api_key_does_not_spend_learning_requests(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox.json"
    write_inbox(inbox)

    report = run_daily_learning_runtime(
        learning_dir=tmp_path / "learning",
        inbox_path=inbox,
        active_query_config=tmp_path / "missing.json",
        environment={},
        policy=DailyLearningPolicy(max_candidates_per_run=2),
    )

    assert report["candidate_count"] >= 1
    assert report["learning_search_requests"] == 0
    assert report["search_status"] == "SKIPPED_NO_API_KEY"


def test_empty_inbox_creates_durable_empty_state_without_search(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox.json"
    inbox.write_text(
        json.dumps({"schema_version": "missed-opportunity-inbox-1.0", "cases": []}),
        encoding="utf-8",
    )
    calls: list[tuple[str, str]] = []

    report = run_daily_learning_runtime(
        learning_dir=tmp_path / "learning",
        inbox_path=inbox,
        active_query_config=tmp_path / "missing.json",
        environment={},
        search_override=lambda term, market: calls.append((term, market)) or [],
    )

    assert calls == []
    assert report["search_status"] == "NO_CANDIDATES"
    assert (tmp_path / "learning" / "missed-opportunities.json").exists()
    assert (tmp_path / "learning" / "active-keyword-overlay.json").exists()
