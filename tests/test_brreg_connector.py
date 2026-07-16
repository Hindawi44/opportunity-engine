from opportunity_engine.ods import BrregClient, BrregConnector, ODSRequest


def _entity_payload() -> dict:
    return {
        "organisasjonsnummer": "123456789",
        "navn": "NAMSOS FASHION AS",
        "organisasjonsform": {"beskrivelse": "Aksjeselskap"},
        "naeringskode1": {"kode": "47.710", "beskrivelse": "Retail sale of clothing"},
        "forretningsadresse": {"kommune": "NAMSOS"},
        "registreringsdatoEnhetsregisteret": "2024-01-15",
        "konkurs": False,
        "underAvvikling": False,
    }


def test_client_searches_entities_with_filters() -> None:
    calls = []

    def transport(url: str, timeout: float, headers: dict[str, str]):
        calls.append((url, timeout, headers))
        return {"_embedded": {"enheter": [_entity_payload()]}}

    client = BrregClient(transport=transport)
    result = client.search_entities(
        name="fashion", municipality="NAMSOS", industry_code="47.710", page_size=10
    )

    assert len(result) == 1
    assert "navn=fashion" in calls[0][0]
    assert "forretningsadresse.kommune=NAMSOS" in calls[0][0]
    assert "naeringskode=47.710" in calls[0][0]
    assert calls[0][2]["Accept"].endswith("enhet.v2+json")


def test_connector_normalizes_entities_to_source_documents() -> None:
    def transport(url: str, timeout: float, headers: dict[str, str]):
        return {"_embedded": {"enheter": [_entity_payload()]}}

    connector = BrregConnector(client=BrregClient(transport=transport), municipality="NAMSOS")
    documents = connector.fetch(ODSRequest(subject="Fashion", country="Norway"))

    assert len(documents) == 1
    document = documents[0]
    assert document.document_id == "brreg-entity-123456789"
    assert document.source_type == "official_business_register"
    assert document.country == "Norway"
    assert document.metadata["industry_code"] == "47.710"
    assert document.metadata["municipality"] == "NAMSOS"
    assert document.metadata["bankrupt"] is False
    assert "Bankruptcy flag: False" in document.text


def test_client_validates_organisation_number() -> None:
    client = BrregClient(transport=lambda *_: {})

    try:
        client.get_entity("123")
    except ValueError as exc:
        assert "nine digits" in str(exc)
    else:
        raise AssertionError("expected invalid organisation number to fail")


def test_client_rejects_invalid_search_payload() -> None:
    client = BrregClient(transport=lambda *_: {"_embedded": {"enheter": "invalid"}})

    try:
        client.search_entities(name="fashion")
    except RuntimeError as exc:
        assert "invalid entity data" in str(exc)
    else:
        raise AssertionError("expected invalid Brreg payload to fail")
