import json
import subprocess
import sys
from pathlib import Path


def test_builds_search_tasks_without_inventing_prices(tmp_path: Path) -> None:
    queue = tmp_path / "queue.json"
    output = tmp_path / "discovery.json"
    queue.write_text(
        json.dumps(
            {
                "queue": [
                    {
                        "opportunity_id": "opp-1",
                        "title": "Butikkinnredning med hyller",
                        "url": "https://example.test/auction",
                        "asking_price_nok": 4000,
                        "market_search_query": "butikkinventar hyller brukt",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            "scripts/build_market_evidence_discovery_queue.py",
            "--queue",
            str(queue),
            "--output",
            str(output),
        ],
        check=True,
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["task_count"] == 1
    task = payload["tasks"][0]
    assert task["status"] == "SEARCH_REQUIRED"
    assert task["required_verified_comparables"] == 3
    assert len(task["candidate_sources"]) == 3
    assert all("price_nok" not in source for source in task["candidate_sources"])
    assert "butikkinventar+hyller+brukt" in task["candidate_sources"][0]["search_url"]


def test_missing_query_does_not_create_search_links(tmp_path: Path) -> None:
    queue = tmp_path / "queue.json"
    output = tmp_path / "discovery.json"
    queue.write_text(
        json.dumps({"queue": [{"opportunity_id": "opp-2", "title": ""}]}),
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            "scripts/build_market_evidence_discovery_queue.py",
            "--queue",
            str(queue),
            "--output",
            str(output),
        ],
        check=True,
    )

    task = json.loads(output.read_text(encoding="utf-8"))["tasks"][0]
    assert task["status"] == "QUERY_REQUIRED"
    assert task["candidate_sources"] == []
