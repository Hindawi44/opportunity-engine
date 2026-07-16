from opportunity_engine.ods import ODSRequest, SSBClient, SSBConnector


def _transport(url: str, timeout: float):
    assert timeout == 5.0
    if "/tables?" in url:
        return {"tables": [{"id": "05810", "label": "Population"}]}
    if "/tables/05810/data?" in url:
        return {
            "class": "dataset",
            "label": "Population",
            "value": [100, 101, 102],
            "dimension": {},
        }
    if "/tables/05810/metadata?" in url:
        return {"class": "dataset", "dimension": {}}
    if "/tables/05810?" in url:
        return {
            "id": "05810",
            "label": "Population by sex and age",
            "firstPeriod": "1986",
            "lastPeriod": "2026",
            "variableNames": ["Sex", "Age", "Contents", "Year"],
        }
    raise AssertionError(f"unexpected URL: {url}")


def test_client_searches_official_v2_tables_endpoint() -> None:
    client = SSBClient(language="en", timeout=5.0, transport=_transport)

    tables = client.search_tables("population", page_size=5)

    assert tables[0]["id"] == "05810"


def test_connector_normalizes_ssb_json_stat2_into_source_document() -> None:
    client = SSBClient(language="en", timeout=5.0, transport=_transport)
    connector = SSBConnector(table_ids=("05810",), client=client)

    documents = connector.fetch(ODSRequest(subject="Demography", country="Norway"))

    assert len(documents) == 1
    document = documents[0]
    assert document.document_id == "ssb-table-05810"
    assert document.source_name == "Statistics Norway (SSB)"
    assert document.source_type == "official_statistics"
    assert document.country == "Norway"
    assert "3 values" in document.text
    assert document.metadata["api_version"] == "PxWebApi v2"
    assert document.metadata["json_stat2"]["value"] == [100, 101, 102]


def test_connector_can_fetch_metadata_only_without_data_request() -> None:
    calls: list[str] = []

    def transport(url: str, timeout: float):
        calls.append(url)
        return {
            "label": "Retail sales",
            "firstPeriod": "2000",
            "lastPeriod": "2026",
            "variableNames": ["Industry", "Time"],
        }

    connector = SSBConnector(
        table_ids=("12345",),
        client=SSBClient(timeout=5.0, transport=transport),
        include_data=False,
    )

    document = connector.fetch(ODSRequest(subject="Retail", country="Norway"))[0]

    assert len(calls) == 1
    assert "/tables/12345?" in calls[0]
    assert document.metadata["json_stat2"] is None


def test_ssb_client_rejects_invalid_table_id() -> None:
    client = SSBClient(timeout=5.0, transport=_transport)

    try:
        client.get_table_info("abc")
    except ValueError as exc:
        assert "five digits" in str(exc)
    else:
        raise AssertionError("invalid table id was accepted")
