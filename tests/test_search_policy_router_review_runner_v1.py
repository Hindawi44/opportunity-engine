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
    assert "Market | Query Family | Provider/Path" in text
    assert "FABRIC_PROCUREMENT" not in text
