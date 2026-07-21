import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_daily_pipeline.py"

spec = importlib.util.spec_from_file_location("run_daily_pipeline", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)

TargetedAuksjonenClient = module.TargetedAuksjonenClient
DEFAULT_QUERIES = module.DEFAULT_AUKSJONEN_DISCOVERY_QUERIES


def test_default_discovery_uses_targeted_queries_and_deduplicates() -> None:
    calls: list[str] = []

    def transport(url: str, timeout: float, headers: dict[str, str]) -> str:
        calls.append(url)
        return """
        <html><body>
          <a href="/auksjon/torget/Butikkinnredning/123456">
            Butikkinnredning med hyller Høyeste bud 1 000,-
          </a>
        </body></html>
        """

    client = TargetedAuksjonenClient(transport=transport)
    documents = client.search()

    assert len(documents) == 1
    assert documents[0].document_id == "auksjonen-123456"
    assert len(calls) == len(DEFAULT_QUERIES)
    assert all("?q=" in url for url in calls)
    assert not any(url.endswith("/auksjoner/") for url in calls)


def test_explicit_keyword_keeps_single_search_behavior() -> None:
    calls: list[str] = []

    def transport(url: str, timeout: float, headers: dict[str, str]) -> str:
        calls.append(url)
        return "<html></html>"

    client = TargetedAuksjonenClient(transport=transport)
    assert client.search(keyword="brudekjole") == ()
    assert calls == ["https://www.auksjonen.no/auksjoner/?q=brudekjole"]
