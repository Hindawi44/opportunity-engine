from datetime import datetime, timezone

import pytest

from opportunity_engine.ods.multi_source import (
    MultiSourceFactConflictError,
    UnifiedMultiSourceEngine,
)
from opportunity_engine.ods.unified_opportunity import UnifiedOpportunity


def _opportunity(**overrides) -> UnifiedOpportunity:
    values = {
        "opportunity_id": "unified-source-a",
        "source_name": "Auksjonen.no",
        "source_document_id": "a",
        "title": "Butikkinnredning",
        "url": "https://example.no/item/42?utm_source=a",
        "description": "Butikkinnredning",
        "current_price_nok": 10_000.0,
        "city": "Trondheim",
        "ends_at": datetime(2026, 8, 20, 12, tzinfo=timezone.utc),
        "fee_text": None,
        "mva_status": "included",
        "image_urls": (),
        "missing_fields": ("fee_text",),
        "raw_metadata": {},
    }
    values.update(overrides)
    return UnifiedOpportunity(**values)


def test_conflicting_price_cannot_be_silently_promoted_to_fact() -> None:
    first = _opportunity()
    second = _opportunity(
        opportunity_id="unified-source-b",
        source_name="Konkurskupp",
        source_document_id="b",
        url="https://example.no/item/42",
        current_price_nok=12_000.0,
    )

    with pytest.raises(MultiSourceFactConflictError, match="current_price_nok"):
        UnifiedMultiSourceEngine().merge((first, second))


def test_conflicting_mva_status_cannot_be_silently_promoted_to_fact() -> None:
    first = _opportunity(mva_status="included")
    second = _opportunity(
        opportunity_id="unified-source-b",
        source_name="Konkurskupp",
        source_document_id="b",
        url="https://example.no/item/42",
        mva_status="excluded",
    )

    with pytest.raises(MultiSourceFactConflictError, match="mva_status"):
        UnifiedMultiSourceEngine().merge((first, second))


def test_conflicting_end_time_cannot_be_silently_promoted_to_fact() -> None:
    first = _opportunity()
    second = _opportunity(
        opportunity_id="unified-source-b",
        source_name="Konkurskupp",
        source_document_id="b",
        url="https://example.no/item/42",
        ends_at=datetime(2026, 8, 21, 12, tzinfo=timezone.utc),
    )

    with pytest.raises(MultiSourceFactConflictError, match="ends_at"):
        UnifiedMultiSourceEngine().merge((first, second))


def test_compatible_evidence_merges_with_fact_provenance() -> None:
    first = _opportunity(fee_text=None, missing_fields=("fee_text",))
    second = _opportunity(
        opportunity_id="unified-source-b",
        source_name="Konkurskupp",
        source_document_id="b",
        url="https://example.no/item/42",
        fee_text="Salær 10 %",
        missing_fields=(),
    )

    merged = UnifiedMultiSourceEngine().merge((first, second)).opportunities[0]
    provenance = merged.raw_metadata["fact_provenance"]

    assert merged.current_price_nok == 10_000.0
    assert merged.mva_status == "included"
    assert merged.ends_at == datetime(2026, 8, 20, 12, tzinfo=timezone.utc)
    assert provenance["current_price_nok"] == (
        "Auksjonen.no:a",
        "Konkurskupp:b",
    )
    assert provenance["mva_status"] == (
        "Auksjonen.no:a",
        "Konkurskupp:b",
    )
    assert provenance["fee_text"] == ("Konkurskupp:b",)


def test_equivalent_city_formatting_is_not_a_fact_conflict() -> None:
    first = _opportunity(city=" Trondheim ")
    second = _opportunity(
        opportunity_id="unified-source-b",
        source_name="Konkurskupp",
        source_document_id="b",
        url="https://example.no/item/42",
        city="trondheim",
    )

    merged = UnifiedMultiSourceEngine().merge((first, second)).opportunities[0]

    assert merged.city.casefold().strip() == "trondheim"


def test_canonical_fact_identity_does_not_depend_on_completeness_ranking() -> None:
    sparse_a = _opportunity(
        opportunity_id="z-source-id",
        source_name="Auksjonen.no",
        source_document_id="a",
        description="Kort",
        fee_text=None,
        missing_fields=("fee_text",),
    )
    rich_b = _opportunity(
        opportunity_id="a-source-id",
        source_name="Konkurskupp",
        source_document_id="b",
        url="https://example.no/item/42",
        description="Lang og komplett beskrivelse",
        fee_text="Salær 10 %",
        missing_fields=(),
    )
    first_merge = UnifiedMultiSourceEngine().merge((sparse_a, rich_b)).opportunities[0]

    rich_a = _opportunity(
        opportunity_id="z-source-id",
        source_name="Auksjonen.no",
        source_document_id="a",
        description="Nå er A den mest komplette kilden",
        fee_text="Salær 10 %",
        missing_fields=(),
    )
    sparse_b = _opportunity(
        opportunity_id="a-source-id",
        source_name="Konkurskupp",
        source_document_id="b",
        url="https://example.no/item/42",
        description="Kort",
        fee_text=None,
        missing_fields=("fee_text",),
    )
    second_merge = UnifiedMultiSourceEngine().merge((rich_a, sparse_b)).opportunities[0]

    assert first_merge.opportunity_id == second_merge.opportunity_id == "a-source-id"
    assert (
        first_merge.raw_metadata["canonical_fact_identity"]
        == second_merge.raw_metadata["canonical_fact_identity"]
        == "url:https://example.no/item/42"
    )
    assert first_merge.raw_metadata["source_opportunity_ids"] == (
        "a-source-id",
        "z-source-id",
    )
