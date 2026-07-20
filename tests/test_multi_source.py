from datetime import datetime, timezone

from opportunity_engine.ods.multi_source import UnifiedMultiSourceEngine
from opportunity_engine.ods.unified_opportunity import UnifiedOpportunity


def _opportunity(**overrides):
    values = {
        "opportunity_id": "unified-a",
        "source_name": "Auksjonen.no",
        "source_document_id": "a",
        "title": "Butikkinnredning",
        "url": "https://example.no/item/42?utm_source=test",
        "description": "Butikkinnredning",
        "current_price_nok": 10000.0,
        "city": "Trondheim",
        "ends_at": None,
        "fee_text": None,
        "mva_status": "unknown",
        "image_urls": (),
        "missing_fields": ("ends_at", "fee_text", "mva_status"),
        "raw_metadata": {},
    }
    values.update(overrides)
    return UnifiedOpportunity(**values)


def test_exact_cross_source_url_duplicates_are_merged() -> None:
    richer = _opportunity(
        opportunity_id="unified-b",
        source_name="Konkurskupp",
        source_document_id="b",
        url="http://example.no/item/42",
        description="Komplett butikkinnredning med hyller",
        ends_at=datetime(2026, 8, 1, 12, tzinfo=timezone.utc),
        fee_text="Salær 10 %",
        mva_status="included",
        image_urls=("https://images.example/1.jpg",),
        missing_fields=(),
    )

    result = UnifiedMultiSourceEngine().merge((_opportunity(), richer))

    assert result.input_count == 2
    assert result.output_count == 1
    assert result.duplicate_count == 1
    assert result.groups_merged == 1
    merged = result.opportunities[0]
    assert merged.source_name == "Konkurskupp"
    assert merged.raw_metadata["merged_source_names"] == ("Konkurskupp", "Auksjonen.no")
    assert merged.mva_status == "included"
    assert merged.missing_fields == ()


def test_distinct_urls_are_not_merged() -> None:
    first = _opportunity(url="https://example.no/item/1")
    second = _opportunity(
        opportunity_id="unified-b",
        source_document_id="b",
        url="https://example.no/item/2",
    )

    result = UnifiedMultiSourceEngine().merge((first, second))

    assert result.output_count == 2
    assert result.duplicate_count == 0


def test_same_source_duplicates_also_collapse_safely() -> None:
    first = _opportunity()
    second = _opportunity(opportunity_id="unified-b", source_document_id="b")

    result = UnifiedMultiSourceEngine().merge((first, second))

    assert result.output_count == 1
    assert result.opportunities[0].raw_metadata["merged_record_count"] == 2
