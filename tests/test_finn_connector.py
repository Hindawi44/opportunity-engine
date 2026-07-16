from opportunity_engine.ods import FinnApiClient, FinnConnector, ODSRequest, parse_finn_atom_feed


ATOM = b'''<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>urn:finn:ad:123456789</id>
    <title>Butikkinventar og overskuddslager</title>
    <updated>2026-07-16T17:30:00Z</updated>
    <summary>&lt;p&gt;Unsold stock and shop fixtures available.&lt;/p&gt;</summary>
    <link rel="self" href="https://api.finn.no/iad/ad/bap/123456789" />
  </entry>
</feed>'''


def test_parse_finn_atom_feed_normalizes_advert():
    documents = parse_finn_atom_feed(ATOM)

    assert len(documents) == 1
    document = documents[0]
    assert document.document_id == "finn-123456789"
    assert document.source_name == "FINN.no"
    assert document.source_type == "authorized_classified_ad"
    assert document.title == "Butikkinventar og overskuddslager"
    assert document.text == "Unsold stock and shop fixtures available."
    assert document.url.endswith("123456789")
    assert document.published_at.isoformat() == "2026-07-16T17:30:00+00:00"
    assert document.metadata["access_mode"] == "authorized_api"


def test_client_uses_api_key_org_id_and_keyword():
    calls = []

    def transport(url: str, timeout: float, headers: dict[str, str]) -> bytes:
        calls.append((url, timeout, headers))
        return ATOM

    client = FinnApiClient(
        api_key="secret",
        org_id="partner-42",
        market="bap/forsale",
        transport=transport,
    )
    documents = client.search(keyword="butikk", rows=25)

    assert len(documents) == 1
    assert "orgId=partner-42" in calls[0][0]
    assert "rows=25" in calls[0][0]
    assert "q=butikk" in calls[0][0]
    assert calls[0][2]["x-FINN-apikey"] == "secret"
    assert "secret" not in calls[0][0]


def test_connector_uses_request_subject():
    keywords = []

    class Client:
        def search(self, *, keyword=None, rows=30):
            keywords.append((keyword, rows))
            return ()

    connector = FinnConnector(client=Client(), rows=10)
    assert connector.fetch(ODSRequest(subject="butikkinnredning", country="Norway")) == ()
    assert keywords == [("butikkinnredning", 10)]


def test_client_rejects_missing_authorization_and_invalid_limits():
    try:
        FinnApiClient(api_key="", org_id="123")
    except ValueError as exc:
        assert "api_key" in str(exc)
    else:
        raise AssertionError("expected missing key to fail")

    client = FinnApiClient(api_key="key", org_id="123", transport=lambda *_: ATOM)
    try:
        client.search(rows=1001)
    except ValueError as exc:
        assert "between 1 and 1000" in str(exc)
    else:
        raise AssertionError("expected invalid rows to fail")


def test_invalid_atom_payload_fails_clearly():
    try:
        parse_finn_atom_feed(b"not xml")
    except RuntimeError as exc:
        assert "invalid Atom XML" in str(exc)
    else:
        raise AssertionError("expected invalid XML to fail")
