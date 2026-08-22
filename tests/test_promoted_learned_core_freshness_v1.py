from __future__ import annotations

import opportunity_engine.promoted_learned_core_discovery as promoted_core


def test_promoted_core_exact_query_has_no_monthly_freshness_filter(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class Provider:
        def __init__(self, api_key: str, **kwargs):
            captured["api_key"] = api_key
            captured.update(kwargs)

        def search(self, query: str, *, count: int = 10):
            captured["query"] = query
            captured["count"] = count
            return []

    monkeypatch.setattr(promoted_core, "BraveSearchProvider", Provider)

    search = promoted_core._default_search("test-key", results_per_query=10)
    search('"avviklingssalg"')

    assert captured["country"] == "NO"
    assert captured["freshness"] is None
    assert captured["query"] == '"avviklingssalg"'
    assert captured["count"] == 10
