from opportunity_engine.discovery.keyword_shadow_verification import PageFetchResult
from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.search_experiment_execution_bridge_v1 import (
    build_experiment_spine,
    execute_search_experiment_spec,
    merge_experiment_result_into_memory,
    replay_or_ingest_pending_experiment,
    select_search_experiment_spec,
)


def _task():
    return {
        "task_id": "ai-slot:fabric-it",
        "execution_mode": "AI_TEACHING",
        "task_kind": "DISCOVER_NEW_ROUTE",
        "requires_paid_ai": True,
        "context": {
            "market_code": "IT",
            "project_domain": "FABRIC_PROCUREMENT",
            "slot_id": "FABRIC_PROCUREMENT",
            "route_status": "GAP",
        },
    }


def _creative(query='Italia tessuti deadstock ingrosso rotoli prezzo EUR'):
    return {
        "ideas": [
            {
                "idea_id": "idea-bad",
                "title": "Narrative only",
                "core_mechanism": "Search around textile districts but without an executable contract.",
            },
            {
                "idea_id": "idea-good",
                "title": "Italian deadstock route",
                "core_mechanism": f'SEARCH_TEST_V1 provider=exa; query="{query}"',
            },
        ]
    }


def _rank():
    return {"ranking": [{"idea_id": "idea-bad"}, {"idea_id": "idea-good"}]}


class _FakeExa:
    def __init__(self, hits):
        self.hits = hits
        self.calls = []

    def search(self, query, *, count=10):
        self.calls.append((query, count))
        return list(self.hits)


def _provider_factory(hits):
    client = _FakeExa(hits)
    return client, lambda _key: client


def _fabric_page(url):
    return PageFetchResult(
        requested_url=url,
        final_url=url,
        ok=True,
        status_code=200,
        title="Tessuti deadstock a stock",
        text=(
            "Tessuti deadstock disponibili. Stock di rotoli per ingrosso B2B. "
            "Prezzo 12 EUR al metro, quantità disponibile."
        ),
        error=None,
    )


def _spec():
    return select_search_experiment_spec(
        teaching_task=_task(),
        creative_result=_creative(),
        final_rank=_rank(),
    )


def test_selects_highest_ranked_idea_that_satisfies_executable_search_contract():
    spec = _spec()
    assert spec["status"] == "READY"
    assert spec["selected_idea_id"] == "idea-good"
    assert spec["selected_idea_rank"] == 2
    assert spec["provider"] == "exa"
    assert spec["market_code"] == "IT"
    assert spec["project_domain"] == "FABRIC_PROCUREMENT"
    assert spec["route"] == "SEARCH_TO_FABRIC_COMMERCIAL_PAGE"
    assert spec["automatic_query_activation"] is False
    assert spec["production_mutation"] is False


def test_rejects_query_that_escapes_task_domain():
    spec = select_search_experiment_spec(
        teaching_task=_task(),
        creative_result=_creative(
            query="Italia abbigliamento moda stock vestiti ingrosso"
        ),
        final_rank=_rank(),
    )
    assert spec["status"] == "NO_EXECUTABLE_SEARCH_IDEA"
    assert any(
        item["reason"].startswith("QUERY_DOMAIN_MISMATCH")
        for item in spec["rejected_ideas"]
    )


def test_fabric_execution_requires_original_page_domain_and_commercial_signals():
    hits = [
        SearchHit(
            title="Tessuti stock",
            url="https://example.it/stock/tessuti-123",
            description="Tessuti a stock",
            provider="Exa",
        )
    ]
    client, factory = _provider_factory(hits)
    result = execute_search_experiment_spec(
        _spec(),
        exa_api_key="test-key",
        run_id="mind-forge-1",
        provider_factory=factory,
        page_fetcher=_fabric_page,
    )

    assert client.calls == [
        ("Italia tessuti deadstock ingrosso rotoli prezzo EUR", 5)
    ]
    assert result["status"] == "SUCCESS"
    assert result["successful_route"] is True
    assert result["successful_result_count"] == 1
    assert result["verified_result_domains"] == ["example.it"]
    assert result["automatic_provider_activation"] is False
    assert result["automatic_purchase"] is False

    spine = build_experiment_spine(result)
    kinds = [row["evidence_kind"] for row in spine["records"]]
    assert kinds == ["MARKET_OBSERVATION", "SEARCH_ROUTE_SUCCESS"]
    route = spine["records"][1]
    assert route["source_identity"] == "search-experiment:fabric_procurement"
    assert route["outcome"] == "CANDIDATE"


def test_same_origin_is_idempotent_and_does_not_fake_an_independent_run():
    hits = [
        SearchHit(
            title="Tessuti stock",
            url="https://example.it/stock/tessuti-123",
            description="Tessuti a stock",
            provider="Exa",
        )
    ]
    _, factory = _provider_factory(hits)
    result = execute_search_experiment_spec(
        _spec(),
        exa_api_key="test-key",
        run_id="mind-forge-1",
        provider_factory=factory,
        page_fetcher=_fabric_page,
    )
    first = merge_experiment_result_into_memory(
        existing_memory={},
        result=result,
        checkpoint_run_id="checkpoint-1",
    )
    second = merge_experiment_result_into_memory(
        existing_memory=first,
        result=result,
        checkpoint_run_id="checkpoint-2",
    )

    assert second == first
    assert first["memory_run_count"] == 1
    assert first["repeated_success_route_count"] == 0
    route_patterns = [
        row for row in first["patterns"] if row["pattern_type"] == "ROUTE_SUCCESS"
    ]
    assert len(route_patterns) == 1
    assert route_patterns[0]["pattern_status"] == "CANDIDATE"


def test_seen_pending_candidate_is_reexecuted_but_proven_route_is_skipped():
    hits = [
        SearchHit(
            title="Tessuti stock",
            url="https://example.it/stock/tessuti-123",
            description="Tessuti a stock",
            provider="Exa",
        )
    ]
    _, factory = _provider_factory(hits)
    pending = execute_search_experiment_spec(
        _spec(),
        exa_api_key="test-key",
        run_id="mind-forge-1",
        provider_factory=factory,
        page_fetcher=_fabric_page,
    )
    memory = merge_experiment_result_into_memory(
        existing_memory={},
        result=pending,
        checkpoint_run_id="checkpoint-1",
    )

    rerun = replay_or_ingest_pending_experiment(
        pending_result=pending,
        existing_memory=memory,
        checkpoint_run_id="checkpoint-2",
        exa_api_key="test-key",
        provider_factory=factory,
        page_fetcher=_fabric_page,
    )
    assert rerun["status"] == "REEXECUTED_AND_INGESTED"
    assert rerun["network_search_executed"] is True
    assert rerun["execution_count"] == 2

    proven_memory = dict(memory)
    proven_memory["patterns"] = [dict(row) for row in memory["patterns"]]
    for row in proven_memory["patterns"]:
        if row.get("pattern_type") == "ROUTE_SUCCESS":
            row["pattern_status"] = "PROVEN"

    stopped = replay_or_ingest_pending_experiment(
        pending_result=pending,
        existing_memory=proven_memory,
        checkpoint_run_id="checkpoint-3",
        exa_api_key="test-key",
        provider_factory=factory,
        page_fetcher=_fabric_page,
    )
    assert stopped["status"] == "SKIPPED_ALREADY_PROVEN"
    assert stopped["network_search_executed"] is False
