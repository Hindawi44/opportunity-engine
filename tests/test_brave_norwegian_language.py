from __future__ import annotations

import json
from pathlib import Path
import sys

from scripts import collect_brave_search_results
from scripts import collect_market_price_candidates


ROOT = Path(__file__).resolve().parents[1]


def test_automated_search_config_uses_supported_bokmal_language() -> None:
    config = json.loads(
        (ROOT / "config" / "brave_search_queries.json").read_text(encoding="utf-8")
    )

    assert config["search_lang"] == "nb"


def test_web_search_fallback_uses_supported_bokmal_language(
    monkeypatch, tmp_path
) -> None:
    config_path = tmp_path / "brave-search.json"
    config_path.write_text(
        json.dumps(
            {
                "country": "NO",
                "queries": ["varelager konkursbo Norge"],
                "max_queries_per_run": 1,
                "results_per_query": 1,
            }
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "web-search-results.json"
    calls: list[tuple[str, str]] = []

    class RecordingClient:
        def __init__(self, api_key: str) -> None:
            assert api_key == "secret"

        def search(
            self, query: str, *, count: int, country: str, search_lang: str
        ) -> list[dict[str, object]]:
            calls.append((country, search_lang))
            return []

    monkeypatch.setenv("BRAVE_API_KEY", "secret")
    monkeypatch.setattr(
        collect_brave_search_results, "BraveSearchClient", RecordingClient
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "collect_brave_search_results.py",
            "--config",
            str(config_path),
            "--output",
            str(output_path),
        ],
    )

    assert collect_brave_search_results.main() == 0
    assert calls == [("NO", "nb")]


def test_market_price_search_uses_supported_bokmal_language(
    monkeypatch, tmp_path
) -> None:
    queue_path = tmp_path / "review-queue.json"
    queue_path.write_text(
        json.dumps(
            {
                "queue": [
                    {
                        "opportunity_id": "test-opportunity",
                        "title": "4 stk lagerreoler",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "market-price-candidates.json"
    languages: list[str] = []

    class RecordingClient:
        def __init__(self, api_key: str) -> None:
            assert api_key == "secret"

        def search(
            self, query: str, *, count: int, country: str, search_lang: str
        ) -> list[dict[str, object]]:
            languages.append(search_lang)
            return []

    monkeypatch.setenv("BRAVE_API_KEY", "secret")
    monkeypatch.setattr(
        collect_market_price_candidates, "BraveSearchClient", RecordingClient
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "collect_market_price_candidates.py",
            "--queue",
            str(queue_path),
            "--output",
            str(output_path),
            "--limit",
            "1",
            "--results-per-query",
            "1",
        ],
    )

    assert collect_market_price_candidates.main() == 0
    assert languages
    assert set(languages) == {"nb"}
