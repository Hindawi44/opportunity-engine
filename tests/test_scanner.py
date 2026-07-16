from opportunity_engine.ods import (
    ConnectorRegistry,
    ODSRequest,
    SourceDocument,
    StaticDataConnector,
    UniversalOpportunityScanner,
)


class FailingConnector:
    name = "failing"

    def fetch(self, request):
        raise RuntimeError("temporary source failure")


def _document(document_id: str, *, url: str | None = None) -> SourceDocument:
    return SourceDocument(
        document_id=document_id,
        source_name="test",
        source_type="market",
        title="Unsold stock signal",
        text="Retailers report unsold stock and overstock.",
        url=url,
        country="Norway",
    )


def test_registry_rejects_duplicate_connector_names():
    connector = StaticDataConnector(name="static", documents=())
    registry = ConnectorRegistry((connector,))

    try:
        registry.register(connector)
    except ValueError as exc:
        assert "already registered" in str(exc)
    else:
        raise AssertionError("expected duplicate connector failure")


def test_scanner_continues_after_connector_failure():
    working = StaticDataConnector(name="working", documents=(_document("1"),))
    scanner = UniversalOpportunityScanner(ConnectorRegistry((FailingConnector(), working)))

    snapshot = scanner.scan(ODSRequest(subject="fashion", country="Norway"))

    assert snapshot.successful_connectors == 1
    assert snapshot.failed_connectors == 1
    assert len(snapshot.documents) == 1
    assert len(snapshot.opportunities) == 1
    assert snapshot.connector_statuses[0].error == "temporary source failure"


def test_scanner_deduplicates_documents_by_url():
    first = StaticDataConnector(
        name="first",
        documents=(_document("1", url="https://example.test/deal"),),
    )
    second = StaticDataConnector(
        name="second",
        documents=(_document("2", url="https://example.test/deal"),),
    )
    scanner = UniversalOpportunityScanner(ConnectorRegistry((first, second)))

    snapshot = scanner.scan(ODSRequest(subject="fashion", country="Norway"))

    assert len(snapshot.documents) == 1
    assert snapshot.duplicate_count == 1
    assert snapshot.scan_id.startswith("scan-")


def test_scanner_requires_registered_connector():
    try:
        UniversalOpportunityScanner(ConnectorRegistry())
    except ValueError as exc:
        assert "at least one" in str(exc)
    else:
        raise AssertionError("expected empty registry failure")
