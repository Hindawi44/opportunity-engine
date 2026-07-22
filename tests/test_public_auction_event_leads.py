from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "build_public_auction_event_leads.py"
SPEC = spec_from_file_location("build_public_auction_event_leads", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_parse_explicit_official_auction_links_deduplicates():
    html = """
    <html><body>
      <a href="/aktuelt/nyheter/2025/04/22/hittegodsauksjon-i-bergen/">Hittegodsauksjon i Bergen</a>
      <a href="/aktuelt/nyheter/2025/04/22/hittegodsauksjon-i-bergen/">Samme auksjon</a>
      <a href="https://example.com/auction">Ekstern auksjon</a>
    </body></html>
    """
    leads = MODULE.parse_auction_leads(html)
    assert len(leads) == 1
    assert leads[0]["source"] == "Politiet.no"
    assert leads[0]["channel"] == "public_auction_event_lead"
    assert leads[0]["asking_price_nok"] is None
    assert leads[0]["url"].startswith("https://www.politiet.no/")


def test_parse_returns_directory_when_no_specific_event_is_linked():
    leads = MODULE.parse_auction_leads("<html><body><p>Ingen aktive arrangementer.</p></body></html>")
    assert len(leads) == 1
    assert leads[0]["lead_id"] == "politiet-auction-directory"
    assert leads[0]["status"] == "SOURCE_DIRECTORY"


def test_official_host_validation_rejects_external_source():
    try:
        MODULE.fetch_html("https://example.com/auction")
    except ValueError as exc:
        assert "official HTTPS politiet.no" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
