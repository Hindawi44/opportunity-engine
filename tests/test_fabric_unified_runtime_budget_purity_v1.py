from __future__ import annotations

import json
from pathlib import Path

from opportunity_engine.discovery import six_market_fabric_coverage_rotation_v1 as coverage
from opportunity_engine.discovery import unified_search_runtime_cli_hook as runtime


def test_daily_legacy_fabric_watch_is_zero_request_placeholder(tmp_path: Path) -> None:
    report = coverage._legacy_daily_watch_deferred(
        tmp_path,
        environment={"BRAVE_SEARCH_API_KEY": "would-have-been-used"},
    )

    assert report["legacy_official_watch_retired"] is True
    assert report["query_budget_total"] == 0
    assert report["requests_made"] == 0
    assert report["candidate_count"] == 0
    assert report["site_pinning_used"] is False
    assert report["candidates"] == []

    artifact = json.loads(
        (tmp_path / runtime.FABRIC_FILENAME).read_text(encoding="utf-8")
    )
    assert artifact["requests_made"] == 0
    assert artifact["legacy_site_pinned_query_budget"] == 0
    assert "site:" not in json.dumps(artifact, ensure_ascii=False).casefold()


def test_final_fabric_report_discards_legacy_watch_and_uses_only_unified_exa_budget(
    tmp_path: Path,
) -> None:
    (tmp_path / runtime.FABRIC_FILENAME).write_text(
        json.dumps(
            {
                "query_budget_total": 7,
                "requests_made": 7,
                "provider_modes": ["legacy_official_watch"],
                "sources": [
                    {
                        "query": "site:legacy.example fabric stock",
                        "status": "BLOCKED_RETRIEVAL",
                    }
                ],
                "candidates": [
                    {
                        "source_url": "https://legacy.example/fabric",
                        "source_country": "IT",
                        "source_kind": "LEGACY_SITE_PINNED",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    exa_report = {
        "market_coverage": ["NO", "SE", "DE"],
        "scheduled_market_coverage": ["NO", "SE", "DE"],
        "coverage_scheduler_version": coverage.VERSION,
        "query_budget_total": 3,
        "requests_made": 3,
        "status_counts": {"SUCCESS": 3},
        "candidate_count": 1,
        "candidates": [
            {
                "source_url": "https://exa.example/fabric-roll",
                "source_country": "DE",
                "source_kind": "EXA_VERIFIED_FABRIC_ROUTE",
                "top5_eligible": False,
            }
        ],
    }

    merged = runtime._merge_fabric_report(tmp_path, exa_report)

    assert merged["provider_modes"] == ["exa"]
    assert merged["query_budget_total"] == 3
    assert merged["requests_made"] == 3
    assert merged["legacy_official_watch_retired"] is True
    assert merged["legacy_search_requests_made"] == 0
    assert merged["site_pinning_used"] is False
    assert merged["source_count"] == 0
    assert merged["sources"] == []
    assert merged["approved_official_domains"] == []
    assert [item["source_url"] for item in merged["candidates"]] == [
        "https://exa.example/fabric-roll"
    ]
    assert all(
        item.get("source_kind") == "EXA_VERIFIED_FABRIC_ROUTE"
        for item in merged["candidates"]
    )
    assert "site:" not in json.dumps(merged, ensure_ascii=False).casefold()
