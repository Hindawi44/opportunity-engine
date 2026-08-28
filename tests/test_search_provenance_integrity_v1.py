from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

from opportunity_engine.discovery import search_provenance_integrity_v1 as provenance


DIRECT_URL = "https://example.test/product/direct-100-jackets"
RECOVERY_URL = "https://example.test/product/recovered-200-jackets"
MULTIHOP_URL = "https://example.test/product/multihop-300-jackets"
CROSS_BORDER_URL = "https://example.eu/product/shared-400-jackets"


def _candidate(url: str, reason: str) -> dict:
    return {
        "canonical_urls": [url],
        "source_urls": [url],
        "reason": reason,
        "verification": [{"url": url, "verified": True}],
    }


def test_verified_page_keeps_original_query_and_recovery_gets_no_query_credit(
    monkeypatch,
) -> None:
    provenance._QUERY_BY_MARKET_URL.clear()
    provenance._RECOVERY_MARKET_URLS.clear()
    provenance._QUERY_BY_MARKET_URL[("DE", DIRECT_URL)] = (
        "Deutschland Restposten Bekleidung Großhandel Lager"
    )

    def fake_verify(*_args, **_kwargs):
        return {
            "verified_pages": [
                {
                    "market_code": "DE",
                    "url": DIRECT_URL,
                    "final_url": DIRECT_URL,
                    "provider": "exa",
                    "query": "joined primary | recall | anchor",
                },
                {
                    "market_code": "DE",
                    "url": RECOVERY_URL,
                    "final_url": RECOVERY_URL,
                    "provider": "proven_route_recovery",
                    "query": "joined primary | recall | anchor",
                },
            ]
        }

    monkeypatch.setattr(provenance, "_ORIGINAL_VERIFY", fake_verify)
    report = provenance._verify_with_query_and_recovery_provenance({})

    direct, recovery = report["verified_pages"]
    assert direct["query"] == "Deutschland Restposten Bekleidung Großhandel Lager"
    assert direct["query_provenance_source"] == "ORIGINAL_EXA_RESULT_QUERY"
    assert direct["retrieval_provenance"] == "DIRECT_SEARCH_RESULT"

    assert recovery["query"] == ""
    assert recovery["route_memory_search_context"] == "joined primary | recall | anchor"
    assert recovery["query_provenance_source"] == "ROUTE_MEMORY_REVERIFICATION"
    assert recovery["retrieval_provenance"] == "PROVEN_ROUTE_RECOVERY"
    assert recovery["route_memory_is_qualification_evidence"] is False
    assert ("DE", RECOVERY_URL) in provenance._RECOVERY_MARKET_URLS
    assert report["provenance_scope"] == "MARKET_PLUS_URL"
    assert report["recovery_query_credit_blocked"] is True
    assert report["search_requests_added_by_provenance_integrity"] == 0
    assert report["page_fetches_added_by_provenance_integrity"] == 0


def test_same_cross_border_url_keeps_independent_query_provenance_per_market(monkeypatch) -> None:
    provenance._QUERY_BY_MARKET_URL.clear()

    monkeypatch.setattr(
        provenance,
        "_ORIGINAL_EXA_SEARCH",
        lambda _self, _query, *, count=10: [SimpleNamespace(url=CROSS_BORDER_URL)][:count],
    )

    provider = object()
    de_query = "Deutschland Restposten Bekleidung Großhandel Lager"
    fr_query = "France déstockage vêtements grossiste stock lot"
    provenance._query_preserving_search(provider, de_query, count=5)
    provenance._query_preserving_search(provider, fr_query, count=5)

    assert provenance._QUERY_BY_MARKET_URL[("DE", CROSS_BORDER_URL)] == de_query
    assert provenance._QUERY_BY_MARKET_URL[("FR", CROSS_BORDER_URL)] == fr_query


def test_recovery_state_in_one_market_does_not_contaminate_same_url_in_another(
    monkeypatch,
) -> None:
    provenance._RECOVERY_MARKET_URLS.clear()
    provenance._RECOVERY_MARKET_URLS.add(("FR", CROSS_BORDER_URL))

    fr_candidate = _candidate(
        CROSS_BORDER_URL,
        "Exa DIRECT_SEARCH_RESULT passed the strict clothing Exact-Lot gate.",
    )
    de_candidate = deepcopy(fr_candidate)

    monkeypatch.setattr(provenance, "_ORIGINAL_TOP5_GATE", lambda result: result)

    fr = provenance._top5_with_truthful_provenance(
        {
            "all_discovered_candidates": [fr_candidate],
            "discovery_top5": [deepcopy(fr_candidate)],
            "search_run_report": {
                "market_code": "FR",
                "strict_exact_lot_count": 1,
                "top5_count": 1,
            },
        }
    )
    de = provenance._top5_with_truthful_provenance(
        {
            "all_discovered_candidates": [de_candidate],
            "discovery_top5": [deepcopy(de_candidate)],
            "search_run_report": {
                "market_code": "DE",
                "strict_exact_lot_count": 1,
                "top5_count": 1,
            },
        }
    )

    assert fr["all_discovered_candidates"][0]["retrieval_provenance"] == "PROVEN_ROUTE_RECOVERY"
    assert de["all_discovered_candidates"][0]["retrieval_provenance"] == "DIRECT_SEARCH_RESULT"
    assert fr["search_run_report"]["freshly_reverified_recovery_exact_lot_count"] == 1
    assert de["search_run_report"]["freshly_reverified_recovery_exact_lot_count"] == 0


def test_top5_selection_is_preserved_while_counts_separate_recovery(monkeypatch) -> None:
    provenance._RECOVERY_MARKET_URLS.clear()
    provenance._RECOVERY_MARKET_URLS.add(("DE", RECOVERY_URL))

    direct = _candidate(DIRECT_URL, "Exa DIRECT_SEARCH_RESULT passed the strict clothing Exact-Lot gate.")
    recovery = _candidate(
        RECOVERY_URL,
        "Exa DIRECT_SEARCH_RESULT passed the strict clothing Exact-Lot gate.",
    )
    multihop = _candidate(
        MULTIHOP_URL,
        "Exa MULTI_HOP passed the strict clothing Exact-Lot gate.",
    )
    original = {
        "all_discovered_candidates": [direct, recovery, multihop],
        # Deliberately select only the third candidate. Provenance must not
        # rebuild Top5 from candidates[:5] or change hard-gate eligibility.
        "discovery_top5": [deepcopy(multihop)],
        "search_run_report": {
            "market_code": "DE",
            "strict_exact_lot_count": 3,
            "top5_count": 1,
        },
    }

    monkeypatch.setattr(provenance, "_ORIGINAL_TOP5_GATE", lambda result: result)
    result = provenance._top5_with_truthful_provenance(original)

    assert len(result["discovery_top5"]) == 1
    assert result["discovery_top5"][0]["canonical_urls"] == [MULTIHOP_URL]
    assert result["discovery_top5"][0]["retrieval_provenance"] == "MULTI_HOP"
    assert recovery["retrieval_provenance"] == "PROVEN_ROUTE_RECOVERY"
    assert recovery["route_memory_reverified"] is True

    report = result["search_run_report"]
    assert report["strict_exact_lot_count"] == 3
    assert report["current_exa_discovery_strict_exact_lot_count"] == 2
    assert report["freshly_reverified_recovery_exact_lot_count"] == 1
    assert report["strict_exact_lot_count_includes_reverified_recovery"] is True
    assert report["provenance_scope"] == "MARKET_PLUS_URL"
    assert report["exact_lot_provenance_counts"] == {
        "DIRECT_SEARCH_RESULT": 1,
        "MULTI_HOP": 1,
        "PROVEN_ROUTE_RECOVERY": 1,
    }


def test_anchor_route_index_does_not_call_recovery_a_direct_search_result() -> None:
    resolution = {
        "verification": {
            "verified_pages": [
                {
                    "url": DIRECT_URL,
                    "final_url": DIRECT_URL,
                    "provider": "exa",
                    "retrieval_provenance": "DIRECT_SEARCH_RESULT",
                },
                {
                    "url": RECOVERY_URL,
                    "final_url": RECOVERY_URL,
                    "provider": "proven_route_recovery",
                    "retrieval_provenance": "PROVEN_ROUTE_RECOVERY",
                },
            ]
        },
        "multihop": {
            "exact_lots": [
                {"url": MULTIHOP_URL, "final_url": MULTIHOP_URL},
            ]
        },
    }

    routes = provenance._route_index_with_recovery_truth(resolution)

    assert routes[DIRECT_URL] == "DIRECT_SEARCH_RESULT"
    assert routes[RECOVERY_URL] == "PROVEN_ROUTE_RECOVERY"
    assert routes[MULTIHOP_URL] == "MULTI_HOP"


def test_cost_guard_skip_survives_six_market_reporting(monkeypatch) -> None:
    ledger = {
        "markets": [
            {
                "market_code": "SE",
                "stages": [
                    {
                        "stage": "DISCOVERY",
                        "status": "UNKNOWN",
                        "source_execution_counts": {"SKIPPED_COST_GUARD": 4},
                    },
                    {"stage": "OPPORTUNITY_DECISION", "status": "NOT_READY"},
                ],
            }
        ]
    }
    monkeypatch.setattr(
        provenance,
        "_ORIGINAL_SIX_MARKET_BUILD",
        lambda *_args, **_kwargs: deepcopy(ledger),
    )

    result = provenance._six_market_build_with_cost_guard_truth()
    stages = {row["stage"]: row for row in result["markets"][0]["stages"]}

    assert stages["DISCOVERY"]["status"] == "SKIPPED_COST_GUARD"
    assert stages["DISCOVERY"]["cost_guard_skipped_source_count"] == 4
    assert stages["OPPORTUNITY_DECISION"]["status"] == "NOT_RUN_COST_GUARD"
    assert result["cost_guard_truth_preserved"] is True


def test_provenance_layer_is_budget_neutral() -> None:
    assert provenance.SEARCH_REQUESTS_ADDED == 0
    assert provenance.PAGE_FETCHES_ADDED == 0
