from opportunity_engine.ods import (
    LiveDataPipeline,
    ODSRequest,
    OpportunityExtractor,
    SourceDocument,
    StaticDataConnector,
)


def _documents() -> tuple[SourceDocument, ...]:
    return (
        SourceDocument(
            document_id="report-1",
            source_name="industry-report",
            source_type="report",
            title="Retailers struggle with unsold stock",
            text="Fashion stores report slow-moving inventory and deep discounting.",
            url="https://example.test/report-1",
            country="Norway",
        ),
        SourceDocument(
            document_id="report-2",
            source_name="returns-study",
            source_type="study",
            title="Online clothing returns",
            text="Wrong size and fit issue remain frequent reasons for returns.",
            url="https://example.test/report-2",
            country="Norway",
        ),
    )


def test_pipeline_collects_and_extracts_evidence_backed_opportunities() -> None:
    connector = StaticDataConnector(name="fixture", documents=_documents())
    result = LiveDataPipeline((connector,)).run(
        ODSRequest(subject="Fashion", country="Norway")
    )

    assert len(result.documents) == 2
    assert result.connector_names == ("fixture",)
    assert {item.category for item in result.opportunities} == {"inventory", "returns"}
    assert all(item.source_plugin == "live_data_extractor" for item in result.opportunities)
    assert all(item.evidence for item in result.opportunities)


def test_pipeline_deduplicates_documents_by_document_id() -> None:
    documents = _documents()
    first = StaticDataConnector(name="first", documents=documents)
    second = StaticDataConnector(name="second", documents=(documents[0],))

    result = LiveDataPipeline((first, second)).run(
        ODSRequest(subject="Fashion", country="Norway")
    )

    assert len(result.documents) == 2


def test_extractor_does_not_invent_opportunities_without_signals() -> None:
    neutral = SourceDocument(
        document_id="neutral",
        source_name="neutral-source",
        source_type="article",
        title="Store opening",
        text="A clothing store opened on Monday.",
        country="Norway",
    )

    opportunities = OpportunityExtractor().extract(
        (neutral,), ODSRequest(subject="Fashion", country="Norway")
    )

    assert opportunities == ()


def test_static_connector_filters_explicit_other_country_documents() -> None:
    connector = StaticDataConnector(
        name="fixture",
        documents=(
            *_documents(),
            SourceDocument(
                document_id="sweden-1",
                source_name="source",
                source_type="report",
                title="Swedish resale",
                text="Circular resale demand is growing.",
                country="Sweden",
            ),
        ),
    )

    documents = connector.fetch(ODSRequest(subject="Fashion", country="Norway"))

    assert all(document.country == "Norway" for document in documents)
