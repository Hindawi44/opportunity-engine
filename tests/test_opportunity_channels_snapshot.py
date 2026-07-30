import importlib.util
import json
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/build_opportunity_channels_report.py"
SPEC = importlib.util.spec_from_file_location("opportunity_channels_snapshot", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_channel_builder_reuses_persisted_bankruptcy_records(tmp_path) -> None:
    snapshot = tmp_path / "today.json"
    snapshot.write_text(
        json.dumps(
            {
                "bankruptcy_discovery_records": [
                    {
                        "document_id": "konkurs-app-1",
                        "source_name": "Konkurs.app",
                        "source_type": "bankruptcy_discovery_lead",
                        "title": "Butikk AS",
                        "text": "Varelager og klær",
                        "url": "https://konkurs.app/konkursbo/1",
                        "published_at": None,
                        "country": "Norway",
                        "metadata": {
                            "city": "Trondheim",
                            "industry_description": "Butikkhandel med klær",
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    documents = MODULE._load_snapshot_documents(snapshot)
    payload = MODULE.build_payload({"top_opportunities": []}, documents, limit=5)

    assert len(documents) == 1
    assert payload["schema_version"] == 2
    assert payload["bankruptcy_leads"]["fetched_count"] == 1
    assert payload["bankruptcy_leads"]["items"][0]["lead_id"] == "konkurs-app-1"
    assert payload["automatic_contact"] is False
