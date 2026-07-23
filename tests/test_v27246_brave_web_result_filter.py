from urllib.parse import parse_qs, urlparse

from opportunity_engine.ods.brave_search import BraveSearchClient


def test_search_forces_web_result_filter(tmp_path):
    captured = {}

    def transport(url, timeout, headers):
        captured["url"] = url
        captured["timeout"] = timeout
        captured["headers"] = headers
        return b'{"type":"search","query":{"original":"test"},"web":{"results":[]}}'

    client = BraveSearchClient(
        api_key="secret",
        transport=transport,
        cache_dir=str(tmp_path / "cache"),
        usage_log_path=str(tmp_path / "usage.jsonl"),
        cache_ttl_hours=0,
    )

    assert client.search("test", use_cache=False) == []
    params = parse_qs(urlparse(captured["url"]).query)
    assert params["result_filter"] == ["web"]
    assert params["q"] == ["test"]
    assert captured["headers"]["Accept"] == "application/json"


def test_parser_extracts_official_web_results_shape(tmp_path):
    def transport(url, timeout, headers):
        return b'{"type":"search","query":{"original":"machine"},"web":{"results":[{"title":"Used machine","url":"https://example.test/item","description":"Market listing"}]}}'

    client = BraveSearchClient(
        api_key="secret",
        transport=transport,
        cache_dir=str(tmp_path / "cache"),
        usage_log_path=str(tmp_path / "usage.jsonl"),
        cache_ttl_hours=0,
    )

    results = client.search("machine", use_cache=False)
    assert len(results) == 1
    assert results[0]["title"] == "Used machine"
    assert results[0]["url"] == "https://example.test/item"
