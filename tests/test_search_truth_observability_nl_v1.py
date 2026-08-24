from opportunity_engine.discovery.keyword_shadow_verification import PageFetchResult
from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.learning_layer import build_learning_layer_review
from opportunity_engine.search_experiment_execution_bridge_v1 import (
    build_experiment_spine,
    execute_search_experiment_spec,
    merge_experiment_result_into_memory,
    select_search_experiment_spec,
)


def _task():
    return {
        "task_id": "ai-slot:nl-fabric",
        "execution_mode": "AI_TEACHING",
        "task_kind": "RESOLVE_ROUTE_GAP",
        "context": {
            "market_code": "NL",
            "project_domain": "FABRIC_PROCUREMENT",
            "slot_id": "FABRIC_PROCUREMENT",
        },
    }


def _creative(query):
    return {
        "ideas": [
            {
                "idea_id": "nl-fabric",
                "title": "NL fabric route",
                "core_mechanism": f'SEARCH_TEST_V1 provider=exa; query="{query}"',
            }
        ]
    }


def _rank():
    return {"ranking": [{"idea_id": "nl-fabric"}]}


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


def _page(url, text, *, ok=True, title="Nederland stoffen groothandel"):
    return PageFetchResult(
        requested_url=url,
        final_url=url,
        ok=ok,
        status_code=200 if ok else 503,
        title=title,
        text=text,
        error=None if ok else "blocked",
    )


def test_internal_domain_label_is_removed_from_public_query():
    spec = select_search_experiment_spec(
        teaching_task=_task(),
        creative_result=_creative(
            "Nederland textiel restpartijen groothandel FABRIC_PROCUREMENT"
        ),
        final_rank=_rank(),
    )
    assert spec["status"] == "READY"
    assert "FABRIC_PROCUREMENT" not in spec["query"]
    assert "fabric textile" in spec["query"]
    assert spec["raw_query"].endswith("FABRIC_PROCUREMENT")
    assert spec["query_internal_labels_removed"] == ["FABRIC_PROCUREMENT"]


def test_nl_commercial_vocabulary_can_verify_a_real_fabric_stock_shape():
    hit = SearchHit(
        title="Restpartijen stoffen",
        url="https://example.nl/restpartijen",
        description="",
        provider="Exa",
    )
    client, factory = _provider_factory([hit])
    spec = select_search_experiment_spec(
        teaching_task=_task(),
        creative_result=_creative("Nederland stoffen textiel groothandel restpartijen"),
        final_rank=_rank(),
    )
    result = execute_search_experiment_spec(
        spec,
        exa_api_key="test",
        run_id="run-1",
        provider_factory=factory,
        page_fetcher=lambda url: _page(
            url,
            "Stoffen op voorraad. Restpartijen en partijgoederen voor B2B groothandel, verkoop per rol.",
        ),
    )
    assert client.calls == [(spec["query"], 5)]
    assert result["successful_result_count"] == 1
    assert result["rejected_result_count"] == 0
    assert result["search_hit_audit"][0]["verification_decision"] == "ACCEPT"
    assert result["search_hit_audit"][0]["rejection_reason"] is None


def test_every_rejected_fabric_hit_has_exact_reason_and_enters_spine():
    hits = [
        SearchHit(title="Fabric article", url="https://a.nl/fabric", description="", provider="Exa"),
        SearchHit(title="Fabric shop", url="https://b.nl/fabric", description="", provider="Exa"),
        SearchHit(title="Blocked", url="https://c.nl/fabric", description="", provider="Exa"),
    ]
    _, factory = _provider_factory(hits)
    pages = {
        "https://a.nl/fabric": _page(
            "https://a.nl/fabric",
            "Stoffen en textiel voor inspiratie.",
        ),
        "https://b.nl/fabric": _page(
            "https://b.nl/fabric",
            "Stoffen op voorraad en restpartijen voor consumenten.",
            title="Nederland stoffen voorraad",
        ),
        "https://c.nl/fabric": _page("https://c.nl/fabric", "", ok=False),
    }
    spec = select_search_experiment_spec(
        teaching_task=_task(),
        creative_result=_creative("Nederland stoffen textiel groothandel restpartijen"),
        final_rank=_rank(),
    )
    result = execute_search_experiment_spec(
        spec,
        exa_api_key="test",
        run_id="run-reject",
        provider_factory=factory,
        page_fetcher=lambda url: pages[url],
    )

    assert result["successful_result_count"] == 0
    assert result["rejected_result_count"] == 3
    assert result["rejection_reason_counts"] == {
        "FETCH_FAILED": 1,
        "MISSING_INVENTORY_SIGNAL": 1,
        "MISSING_TRADE_OR_PRICE_SIGNAL": 1,
    }
    assert all(row["verification_decision"] == "REJECT" for row in result["search_hit_audit"])
    assert all(row["rejection_reason"] for row in result["search_hit_audit"])

    spine = build_experiment_spine(result)
    rejections = [
        row for row in spine["records"]
        if row.get("result_type") == "SEARCH_RESULT_REJECTION"
    ]
    assert len(rejections) == 3
    assert {row["miss_reason"] for row in rejections} == {
        "FETCH_FAILED",
        "MISSING_INVENTORY_SIGNAL",
        "MISSING_TRADE_OR_PRICE_SIGNAL",
    }


def test_search_rejections_survive_memory_and_are_visible_as_learning_failures():
    hit = SearchHit(
        title="Fabric page",
        url="https://reject.nl/fabric",
        description="",
        provider="Exa",
    )
    _, factory = _provider_factory([hit])
    spec = select_search_experiment_spec(
        teaching_task=_task(),
        creative_result=_creative("Nederland stoffen textiel groothandel restpartijen"),
        final_rank=_rank(),
    )
    result = execute_search_experiment_spec(
        spec,
        exa_api_key="test",
        run_id="origin-1",
        provider_factory=factory,
        page_fetcher=lambda url: _page(
            url,
            "Stoffen en textiel voor inspiratie.",
        ),
    )
    memory = merge_experiment_result_into_memory(
        existing_memory={}, result=result, checkpoint_run_id="checkpoint-1"
    )
    rejection_rows = [
        row for row in memory["evidence_memory"]
        if row.get("result_type") == "SEARCH_RESULT_REJECTION"
    ]
    assert len(rejection_rows) == 1
    assert rejection_rows[0]["latest_miss_reason"] == "MISSING_INVENTORY_SIGNAL"

    review = build_learning_layer_review(
        search_success_memory={},
        root_cause_feedback={},
        daily_learning={},
        unified_memory=memory,
    )
    assert review["search_experiment_rejection_count"] == 1
    assert review["what_failed_count"] == 1
    assert review["what_failed"][0]["root_cause"] == "MISSING_INVENTORY_SIGNAL"
    assert review["what_failed"][0]["url"] == "https://reject.nl/fabric"
    assert review["automatic_query_activation"] is False
    assert review["production_mutation"] is False
