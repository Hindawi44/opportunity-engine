from datetime import datetime, timezone

from opportunity_engine.ods.live_data import SourceDocument
from opportunity_engine.ods.unified_opportunity import UnifiedOpportunityExtractor


def _document(**metadata):
    return SourceDocument(
        document_id="auksjonen-123",
        source_name="Auksjonen.no",
        source_type="public_auction_listing",
        title="Butikkinnredning",
        text="Butikkinnredning | Salær: 15 % | eks. mva",
        url="https://www.auksjonen.no/auksjon/123",
        country="Norway",
        metadata=metadata,
    )


def test_extracts_analysis_ready_record() -> None:
    extractor = UnifiedOpportunityExtractor()
    document = _document(
        current_price_nok=12500,
        city="Trondheim",
        ends_at="2026-07-31T18:00:00+02:00",
        description="Komplett innredning med hyller",
        image_urls=["https://images.example/1.jpg", "http://unsafe.example/2.jpg"],
    )

    result = extractor.extract((document,))

    assert len(result) == 1
    opportunity = result[0]
    assert opportunity.opportunity_id == "unified-auksjonen-123"
    assert opportunity.current_price_nok == 12500.0
    assert opportunity.city == "Trondheim"
    expected_end = datetime.fromisoformat("2026-07-31T18:00:00+02:00")
    assert opportunity.ends_at == expected_end
    assert opportunity.ends_at.astimezone(timezone.utc) == datetime(
        2026, 7, 31, 16, 0, tzinfo=timezone.utc
    )
    assert opportunity.description == "Komplett innredning med hyller"
    assert opportunity.fee_text == "Salær: 15 %"
    assert opportunity.mva_status == "excluded"
    assert opportunity.image_urls == ("https://images.example/1.jpg",)
    assert opportunity.missing_fields == ()


def test_missing_values_are_reported_not_invented() -> None:
    opportunity = UnifiedOpportunityExtractor().extract((_document(),))[0]

    assert opportunity.current_price_nok is None
    assert opportunity.city is None
    assert opportunity.ends_at is None
    assert set(opportunity.missing_fields) == {"current_price_nok", "city", "ends_at"}


def test_unsupported_documents_and_duplicates_are_skipped() -> None:
    supported = _document(current_price_nok=1)
    duplicate = _document(current_price_nok=2)
    unsupported = SourceDocument(
        document_id="ssb-1",
        source_name="SSB",
        source_type="statistics",
        title="Retail data",
        text="data",
        url="https://example.test/data",
    )

    result = UnifiedOpportunityExtractor().extract((supported, duplicate, unsupported))

    assert len(result) == 1
    assert result[0].current_price_nok == 1.0


def test_mva_included_and_not_applicable_are_detected() -> None:
    included = _document(mva_status="included")
    not_applicable = SourceDocument(
        document_id="auksjonen-456",
        source_name="Auksjonen.no",
        source_type="public_auction_listing",
        title="Varelager",
        text="Varelager uten mva",
        url="https://www.auksjonen.no/auksjon/456",
    )

    result = UnifiedOpportunityExtractor().extract((included, not_applicable))

    assert result[0].mva_status == "included"
    assert result[1].mva_status == "not_applicable"
