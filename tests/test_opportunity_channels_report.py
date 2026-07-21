import importlib.util
from pathlib import Path

from opportunity_engine.ods.live_data import SourceDocument


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_opportunity_channels_report.py"
spec = importlib.util.spec_from_file_location("opportunity_channels", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def _lead(title: str = "Butikk AS", description: str = "Varelager og butikkinnredning") -> SourceDocument:
    return SourceDocument(
        document_id="konkurs-app-1",
        source_name="Konkurs.app",
        source_type="bankruptcy_discovery_lead",
        title=title,
        text=description,
        url="https://konkurs.app/konkursbo/999888777",
        country="Norway",
        metadata={
            "description": description,
            "city": "Trondheim",
            "organization_number": "999888777",
            "bankruptcy_date": "2026-07-21T08:00:00+00:00",
            "industry_description": "Butikkhandel med klær",
            "trustee": "Advokat Eksempel",
        },
    )


def test_bankruptcy_leads_do_not_compete_with_actionable_sales():
    actionable = {
        "candidate_count": 3,
        "top_opportunities": [{"opportunity_id": "sale-1", "opportunity_score": 60}],
    }
    payload = module.build_payload(actionable, (_lead(),), limit=5)

    assert payload["actionable_opportunities"]["top_count"] == 1
    assert payload["bankruptcy_leads"]["top_count"] == 1
    lead = payload["bankruptcy_leads"]["items"][0]
    assert lead["channel"] == "bankruptcy_lead"
    assert lead["status"] == "FOLLOW_UP_LEAD"
    assert lead["asking_price_nok"] is None
    assert lead["expected_profit_nok"] is None
    assert lead["roi_percent"] is None


def test_non_lead_documents_are_not_added_to_bankruptcy_channel():
    sale = SourceDocument(
        document_id="auksjonen-1",
        source_name="Auksjonen.no",
        source_type="public_auction_listing",
        title="Lagerreol",
        text="Lagerreol",
        url="https://www.auksjonen.no/auksjon/1",
        country="Norway",
        metadata={},
    )
    payload = module.build_payload({"top_opportunities": []}, (sale,), limit=5)
    assert payload["bankruptcy_leads"]["fetched_count"] == 0
    assert payload["bankruptcy_leads"]["items"] == []
