import json

import pytest

from opportunity_engine.ods.brave_search import BraveSearchClient, parse_brave_results


def test_client_builds_authorized_bounded_request_without_exposing_key(tmp_path):
    captured = {}

    def transport(url, timeout, headers):
        captured["url"] = url
        captured["headers"] = headers
        return json.dumps({"web": {"results": []}}).encode("utf-8")

    client = BraveSearchClient(
        api_key="secret-value",
        transport=transport,
        cache_dir=str(tmp_path / "cache"),
        usage_log_path=str(tmp_path / "usage.jsonl"),
    )
    assert client.search("butikkinnredning", count=5) == []
    assert "q=butikkinnredning" in captured["url"]
    assert "count=5" in captured["url"]
    assert "country=NO" in captured["url"]
    assert "secret-value" not in captured["url"]
    assert captured["headers"]["X-Subscription-Token"] == "secret-value"


def test_parse_results_preserves_direct_fields_and_removes_duplicates():
    payload = {
        "web": {
            "results": [
                {
                    "id": "direct-1",
                    "title": "Butikkinnredning selges",
                    "url": "https://example.no/ad/1",
                    "description": "Komplett inventar",
                    "page_age": "2026-07-22T08:00:00Z",
                    "language": "no",
                    "extra_snippets": ["Ti hyller"],
                },
                {"title": "Duplicate", "url": "https://example.no/ad/1"},
                {"title": "Unsafe", "url": "http://example.no/ad/2"},
                {"title": "Missing URL"},
            ]
        }
    }
    results = parse_brave_results(json.dumps(payload))
    assert len(results) == 1
    assert results[0]["id"] == "direct-1"
    assert results[0]["title"] == "Butikkinnredning selges"
    assert results[0]["url"] == "https://example.no/ad/1"
    assert results[0]["snippet"] == "Komplett inventar"
    assert results[0]["extra_snippets"] == ["Ti hyller"]
    assert results[0]["source"] == "Brave Search"
    assert results[0]["published_at"] == "2026-07-22T08:00:00Z"
    assert results[0]["language"] == "no"
    assert results[0]["source_rank"] == 1


def test_invalid_configuration_and_payload_are_rejected(tmp_path):
    with pytest.raises(ValueError):
        BraveSearchClient(api_key="")
    client = BraveSearchClient(
        api_key="x",
        cache_dir=str(tmp_path / "cache"),
        usage_log_path=str(tmp_path / "usage.jsonl"),
    )
    with pytest.raises(ValueError):
        client.search("", count=1)
    with pytest.raises(ValueError):
        client.search("query", count=21)
    with pytest.raises(ValueError):
        client.search("word " * 51)
    with pytest.raises(RuntimeError):
        parse_brave_results("not-json")


def test_repeated_query_uses_cache_and_does_not_spend_second_request(tmp_path):
    calls = 0

    def transport(url, timeout, headers):
        nonlocal calls
        calls += 1
        return json.dumps(
            {"web": {"results": [{"title": "A", "url": "https://example.no/a"}]}}
        ).encode("utf-8")

    client = BraveSearchClient(
        api_key="x",
        transport=transport,
        cache_dir=str(tmp_path / "cache"),
        usage_log_path=str(tmp_path / "usage.jsonl"),
    )

    assert client.search("same query") == client.search("same   query")
    assert calls == 1
    assert client.request_count == 1
    assert client.cache_hits == 1


def test_per_run_budget_blocks_extra_uncached_requests(tmp_path):
    client = BraveSearchClient(
        api_key="x",
        transport=lambda url, timeout, headers: json.dumps({"web": {"results": []}}).encode(),
        cache_dir=str(tmp_path / "cache"),
        usage_log_path=str(tmp_path / "usage.jsonl"),
        cache_ttl_hours=0,
        max_requests_per_run=1,
    )

    client.search("first", use_cache=False)
    with pytest.raises(RuntimeError, match="request budget"):
        client.search("second", use_cache=False)


def test_usage_log_hashes_query_and_never_stores_api_key(tmp_path):
    usage = tmp_path / "usage.jsonl"
    client = BraveSearchClient(
        api_key="top-secret",
        transport=lambda url, timeout, headers: json.dumps({"web": {"results": []}}).encode(),
        cache_dir=str(tmp_path / "cache"),
        usage_log_path=str(usage),
        cache_ttl_hours=0,
    )

    client.search("sensitive commercial query", use_cache=False)
    text = usage.read_text(encoding="utf-8")
    assert "sensitive commercial query" not in text
    assert "top-secret" not in text
    assert '"status": "success"' in text


def test_environment_configuration_accepts_existing_project_key(monkeypatch):
    monkeypatch.setenv("BRAVE_API_KEY", "env-secret")
    monkeypatch.setenv("BRAVE_MAX_REQUESTS_PER_RUN", "4")
    client = BraveSearchClient.from_environment()
    assert client.api_key == "env-secret"
    assert client.max_requests_per_run == 4
