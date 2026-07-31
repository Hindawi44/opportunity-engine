import json
from pathlib import Path

from opportunity_engine.ods.brave_search import BraveSearchClient


CONFIG = Path("config/brave_search_queries.json")


def _load_config() -> dict[str, object]:
    value = json.loads(CONFIG.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_configured_queries_fit_default_brave_budget() -> None:
    config = _load_config()
    queries = config["queries"]
    max_queries = int(config["max_queries_per_run"])
    client = BraveSearchClient(api_key="test-key")

    assert isinstance(queries, list)
    assert len(queries) == max_queries
    assert max_queries <= client.max_requests_per_run


def test_clothing_inventory_queries_are_prioritized() -> None:
    config = _load_config()
    queries = [str(query).casefold() for query in config["queries"]]

    assert any("tekstil" in query for query in queries)
    assert any("opphørssalg" in query for query in queries)
    assert any("varelager konkursbo" in query for query in queries)
    assert any("butikkinnredning klesbutikk" in query for query in queries)
    assert any("klesstativ" in query and "utstillingsdukker" in query for query in queries)
