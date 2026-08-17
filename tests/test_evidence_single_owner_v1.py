import pytest

from opportunity_engine.ods.live_data import (
    LiveDataPipeline,
    SourceDocument,
    SourceEvidenceConflictError,
    StaticDataConnector,
)
from opportunity_engine.ods.models import ODSRequest
from opportunity_engine.ods.unified_opportunity import UnifiedOpportunityExtractor


def _evidence(
    *,
    source_name: str,
    document_id: str = "shared-1",
    title: str = "Varelager",
    text: str = "Varelager til salgs",
    url: str = "https://example.test/item/1",
    source_type: str = "public_auction_listing",
    price: float | None = 1000,
) -> SourceDocument:
    return SourceDocument(
        document_id=document_id,
        source_name=source_name,
        source_type=source_type,
        title=title,
        text=text,
        url=url,
        country="Norway",
        metadata={"current_price_nok": price},
    )


def test_cross_source_document_id_collision_keeps_both_evidence_items() -> None:
    first = _evidence(source_name="Source A", url="https://a.example/item/1")
    second = _evidence(source_name="Source B", url="https://b.example/item/1")

    result = LiveDataPipeline(
        (
            StaticDataConnector(name="a", documents=(first,)),
            StaticDataConnector(name="b", documents=(second,)),
        )
    ).run(ODSRequest(subject="Fashion", country="Norway"))

    assert len(result.documents) == 2
    assert {item.source_name for item in result.documents} == {"Source A", "Source B"}


def test_same_source_same_id_conflict_fails_closed() -> None:
    first = _evidence(source_name="Source A", text="Pris 1000", price=1000)
    conflicting = _evidence(source_name="Source A", text="Pris 2000", price=2000)

    pipeline = LiveDataPipeline(
        (
            StaticDataConnector(name="first", documents=(first,)),
            StaticDataConnector(name="second", documents=(conflicting,)),
        )
    )

    with pytest.raises(SourceEvidenceConflictError, match="Source A.*shared-1"):
        pipeline.run(ODSRequest(subject="Fashion", country="Norway"))


def test_exact_same_source_duplicate_collapses_safely() -> None:
    item = _evidence(source_name="Source A")
    result = LiveDataPipeline(
        (
            StaticDataConnector(name="first", documents=(item,)),
            StaticDataConnector(name="second", documents=(item,)),
        )
    ).run(ODSRequest(subject="Fashion", country="Norway"))

    assert result.documents == (item,)


def test_unified_extractor_namespaces_only_real_cross_source_id_collisions() -> None:
    first = _evidence(source_name="Source A", url="https://a.example/item/1")
    second = _evidence(source_name="Source B", url="https://b.example/item/1")

    opportunities = UnifiedOpportunityExtractor().extract((first, second))

    assert len(opportunities) == 2
    assert opportunities[0].opportunity_id != opportunities[1].opportunity_id
    assert {item.source_name for item in opportunities} == {"Source A", "Source B"}


def test_unified_extractor_uses_same_evidence_conflict_contract() -> None:
    first = _evidence(source_name="Source A", text="Pris 1000", price=1000)
    conflicting = _evidence(source_name="Source A", text="Pris 2000", price=2000)

    with pytest.raises(SourceEvidenceConflictError, match="Source A.*shared-1"):
        UnifiedOpportunityExtractor().extract((first, conflicting))
