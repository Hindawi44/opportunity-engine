from pathlib import Path

from opportunity_engine.source_ingestion.auksjonen import (
    AUKSJONEN_CATEGORY_URL,
    build_snapshot,
    inspect_public_page,
    parse_public_listings,
)
from scripts.run_v33_auksjonen_ingestion import run_refresh


def _fixture() -> str:
    return Path("tests/fixtures/v33_auksjonen_page.html").read_text(encoding="utf-8")


def _current_fixture() -> str:
    return Path("tests/fixtures/v33_auksjonen_current_page.html").read_text(
        encoding="utf-8"
    )


def test_auksjonen_adapter_extracts_only_public_positive_nok_listings():
    listings = parse_public_listings(_fixture())

    assert len(listings) == 3
    assert [item.listing_id for item in listings] == ["123456", "123457", "123458"]
    assert [item.asking_price_nok for item in listings] == [10000.0, 25000.0, 15000.0]
    assert all(item.url.startswith("https://www.auksjonen.no/auksjoner/") for item in listings)

    snapshot = build_snapshot(
        listings,
        captured_at="2026-07-24T12:00:00+02:00",
    )
    assert snapshot["schema_version"] == "3.3"
    assert snapshot["source_page"] == AUKSJONEN_CATEGORY_URL
    assert len(snapshot["opportunities"]) == 3
    assert all(item["source"]["listing_status"] == "ACTIVE" for item in snapshot["opportunities"])
    assert all(item["verified_cost_evidence"]["auction_price_nok"] > 0 for item in snapshot["opportunities"])


def test_current_public_card_format_and_dash_prices_are_supported():
    listings = parse_public_listings(_current_fixture())

    assert [(item.listing_id, item.asking_price_nok) for item in listings] == [
        ("587485", 800.0),
        ("587486", 1000.0),
    ]
    assert [item.title for item in listings] == [
        "27 stk Diverse Hi-vis bukser og T-skjorter",
        "Vareparti - Bøttehatter (120 stk.)",
    ]
    assert [item.listing_status for item in listings] == ["ACTIVE", "ENDED"]
    assert [item.location for item in listings] == ["STRØMMEN", "STRØMMEN"]
    assert listings[0].url.endswith("/587485")

    extraction = inspect_public_page(_current_fixture())
    assert extraction.source_extraction_status == "VERIFIED_LISTINGS"
    assert extraction.diagnostics["html_title"] == "Vareparti og konkursbo"
    assert extraction.diagnostics["anchor_count"] == 5
    assert extraction.diagnostics["explicit_empty_state_present"] is False


def test_embedded_public_json_rejects_external_and_priceless_records():
    html = """
    <html><body>
      <script type="application/json">
        {
          "items": [
            {
              "title": "Internt vareparti",
              "url": "/auksjon/overskuddsvarer/internt/600001",
              "price": "2 500,-",
              "status": "Avsluttes"
            },
            {
              "title": "Eksternt vareparti",
              "url": "https://example.com/auksjon/600002",
              "price": "3 000,-"
            },
            {
              "title": "Uten pris",
              "url": "/auksjon/overskuddsvarer/uten-pris/600003"
            }
          ]
        }
      </script>
    </body></html>
    """
    listings = parse_public_listings(html)

    assert [(item.listing_id, item.title, item.asking_price_nok) for item in listings] == [
        ("600001", "Internt vareparti", 2500.0)
    ]


def test_auksjonen_adapter_preserves_explicit_active_and_ended_status():
    html = """
    <html><body>
      <a href="/auksjoner/20001/arbeidsjakker">
        Parti arbeidsjakker Avsluttet Høyeste bud 500 NOK
      </a>
      <a href="/auksjoner/20002/arbeidsbukser">
        Parti arbeidsbukser Avsluttes 30.07.2026 Høyeste bud 700 NOK
      </a>
    </body></html>
    """

    listings = parse_public_listings(html)
    assert [(item.listing_id, item.listing_status) for item in listings] == [
        ("20001", "ENDED"),
        ("20002", "ACTIVE"),
    ]

    snapshot = build_snapshot(listings, captured_at="2026-07-27T08:00:00Z")
    assert [item["source"]["listing_status"] for item in snapshot["opportunities"]] == [
        "ENDED",
        "ACTIVE",
    ]


def test_refresh_passes_snapshot_to_v32_and_deduplicates_second_run():
    first_report, first_snapshot, first_state = run_refresh(
        html=_fixture(),
        state_payload={},
        captured_at="2026-07-24T12:00:00+02:00",
    )

    assert first_report["schema_version"] == "3.3"
    assert first_report["source"] == "Auksjonen.no"
    assert first_report["source_page"] == AUKSJONEN_CATEGORY_URL
    assert first_report["source_extraction_status"] == "VERIFIED_LISTINGS"
    assert first_report["listings_extracted"] == 3
    assert first_report["snapshot_written"] is True
    assert first_report["new_opportunities_detected"] == 3
    assert first_report["ready_for_financial_review"] == 0
    assert first_report["automatic_purchase_decision"] is False
    assert first_report["monitoring_status"] == "NEW_OPPORTUNITIES_EVALUATED"
    assert first_report["errors"] == []
    assert first_report["status"] == "PASS"
    assert len(first_snapshot["opportunities"]) == 3
    assert len(first_state["seen_fingerprints"]) == 3

    second_report, second_snapshot, second_state = run_refresh(
        html=_fixture(),
        state_payload=first_state,
        captured_at="2026-07-24T13:00:00+02:00",
    )
    assert second_report["listings_extracted"] == 3
    assert second_report["new_opportunities_detected"] == 0
    assert second_report["monitoring_status"] == "NO_NEW_OPPORTUNITIES"
    assert second_report["automatic_purchase_decision"] is False
    assert len(second_snapshot["opportunities"]) == 3
    assert second_state["seen_fingerprints"] == first_state["seen_fingerprints"]


def test_explicit_empty_page_is_verified_and_may_write_empty_snapshot():
    html = """
    <html>
      <head><title>Vareparti og konkursbo</title></head>
      <body><p>Ingen auksjoner funnet</p></body>
    </html>
    """
    report, snapshot, state = run_refresh(
        html=html,
        state_payload={"seen_fingerprints": ["preserved"]},
        captured_at="2026-07-27T10:00:00Z",
    )

    assert report["source_extraction_status"] == "VERIFIED_EMPTY"
    assert report["status"] == "SOURCE_EMPTY"
    assert report["snapshot_written"] is True
    assert report["listings_extracted"] == 0
    assert snapshot["opportunities"] == []
    assert state["seen_fingerprints"] == ["preserved"]


def test_unrecognized_zero_page_is_unverified_and_does_not_update_state():
    html = """
    <html>
      <head><title>Vareparti og konkursbo</title></head>
      <body><div id="__NEXT_DATA__"></div></body>
    </html>
    """
    prior_state = {"seen_fingerprints": ["preserved"]}
    report, snapshot, state = run_refresh(
        html=html,
        state_payload=prior_state,
        captured_at="2026-07-27T10:05:00Z",
    )

    assert report["source_extraction_status"] == "UNVERIFIED_ZERO"
    assert report["status"] == "SOURCE_EXTRACTION_UNVERIFIED"
    assert report["snapshot_written"] is False
    assert report["monitoring_status"] == "NOT_INVOKED"
    assert report["automatic_purchase_decision"] is False
    assert report["source_diagnostics"]["hydration_container_present"] is True
    assert snapshot["opportunities"] == []
    assert state == prior_state
