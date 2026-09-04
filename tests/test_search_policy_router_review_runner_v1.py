from __future__ import annotations

import json
from pathlib import Path

from scripts.run_search_policy_router_review import write_router_review
from tests.test_search_policy_router_v1 import _memory


def test_runner_writes_review_only_json_and_text(tmp_path: Path) -> None:
    memory = _memory()
    memory["query_memory"].append(
        {
            "market_code": "NL",
            "provider": "exa",
            "query": "FABRIC_PROCUREMENT Nederland stoffen groothandel leveranciers catalogus",
        }
    )

    paths = write_router_review(memory, tmp_path)
    report = json.loads(paths["json"].read_text(encoding="utf-8"))
    text = paths["text"].read_text(encoding="utf-8")

    assert report["mode"] == "REVIEW_ONLY"
    assert report["production_mutation"] is False
    assert report["request_slots_added"] == 0
    assert report["excluded_out_of_domain_query_count"] == 1
    assert report["bounded_query_challenges"]["DE"]["status"] == "HUMAN_DECISION_APPLIED"
    assert report["bounded_query_challenges"]["NO"]["status"] == "HUMAN_DECISION_APPLIED"
    assert report["bounded_query_challenges"]["DE"]["finalized_decision"] == "KEEP_CHALLENGER"
    assert report["bounded_query_challenges"]["NO"]["finalized_decision"] == "REVERT_INCUMBENT"
    assert report["bounded_query_challenges"]["DE"]["request_slots_added"] == 0
    assert report["bounded_query_challenges"]["NO"]["request_slots_added"] == 0
    assert "DE: HUMAN_DECISION_APPLIED" in text
    assert "NO: HUMAN_DECISION_APPLIED" in text
    assert "Market | Query Family | Provider/Path" in text
    assert "FABRIC_PROCUREMENT" not in text
