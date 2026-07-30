from opportunity_engine.ods.live_data import SourceDocument
from opportunity_engine.ods.multi_source import UnifiedMultiSourceEngine
from opportunity_engine.ods.source_record_accounting import (
    build_source_record_accounting,
    deserialize_source_document,
    serialize_bankruptcy_discovery_records,
)
from opportunity_engine.ods.unified_opportunity import UnifiedOpportunityExtractor


def _sale(index: int) -> SourceDocument:
    return SourceDocument(
        document_id=f"auksjonen-{index}",
        source_name="Auksjonen.no",
        source_type="public_auction_listing",
        title=f"Butikkinnredning {index}",
        text=f"Butikkinnredning {index}",
        url=f"https://www.auksjonen.no/auksjon/{index}",
        country="Norway",
        metadata={"current_price_nok": 1000 + index},
    )


def _bankruptcy(index: int) -> SourceDocument:
    return SourceDocument(
        document_id=f"konkurs-app-{index}",
        source_name="Konkurs.app",
        source_type="bankruptcy_discovery_lead",
        title=f"Butikk AS {index}",
        text="Konkursåpning for klesbutikk",
        url=f"https://konkurs.app/konkursbo/{index}",
        country="Norway",
        metadata={"industry_description": "Butikkhandel med klær"},
    )


def test_exact_accounting_records_report_limit_and_unsupported_leads() -> None:
    documents = (_sale(1), _sale(2), _sale(3), _bankruptcy(1))
    extracted = UnifiedOpportunityExtractor().extract(documents)
    merged = UnifiedMultiSourceEngine().merge(extracted).opportunities
    published_ids = [item.opportunity_id for item in merged[:2]]

    accounting = build_source_record_accounting(
        documents,
        extracted,
        merged,
        published_ids,
    )

    auksjonen = accounting["sources"]["Auksjonen.no"]
    konkurs = accounting["sources"]["Konkurs.app"]
    assert accounting["valid"] is True
    assert auksjonen["fetched_count"] == 3
    assert auksjonen["published_audit_record_count"] == 2
    assert auksjonen["excluded_records_by_reason"] == {"daily_report_limit": 1}
    assert konkurs["fetched_count"] == 1
    assert konkurs["published_audit_record_count"] == 0
    assert konkurs["excluded_records_by_reason"] == {
        "unsupported_source_type_for_sale_pipeline": 1
    }


def test_bankruptcy_records_round_trip_for_offline_channel_building() -> None:
    records = serialize_bankruptcy_discovery_records((_sale(1), _bankruptcy(2)))

    assert len(records) == 1
    restored = deserialize_source_document(records[0])
    assert restored.document_id == "konkurs-app-2"
    assert restored.source_name == "Konkurs.app"
    assert restored.source_type == "bankruptcy_discovery_lead"
    assert restored.metadata["industry_description"] == "Butikkhandel med klær"
