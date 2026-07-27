import json

from scripts.run_active_clothing_inventory_scan import (
    build_live_scan_report,
    build_scan_summary,
    write_scan_outputs,
)


ALL_ENDED_PAGE = """
<html>
  <body>
    <a href="/auksjoner/12001/arbeidsjakker">
      Parti med arbeidsjakker Avsluttet Høyeste bud 1 000 NOK
    </a>
    <a href="/auksjoner/12002/arbeidsbukser">
      Parti med arbeidsbukser Avsluttet Høyeste bud 1 500 NOK
    </a>
    <a href="/auksjoner/12003/kontormobler">
      Kontormøbler Avsluttet Høyeste bud 2 000 NOK
    </a>
  </body>
</html>
"""

ACTIVE_PAGE = """
<html>
  <head>
    <script type="application/ld+json">
      {
        "@context": "https://schema.org",
        "@graph": [
          {
            "name": "Parti med avsluttede arbeidsjakker",
            "url": "https://www.auksjonen.no/auksjoner/13001",
            "offers": {
              "price": 1800,
              "availability": "https://schema.org/SoldOut"
            }
          },
          {
            "name": "Parti med aktive arbeidsjakker og bukser",
            "url": "https://www.auksjonen.no/auksjoner/13002",
            "offers": {
              "price": 2400,
              "availability": "https://schema.org/InStock"
            },
            "location": {"name": "Namsos"}
          }
        ]
      }
    </script>
  </head>
</html>
"""

DUPLICATE_PAGE = """
<html>
  <body>
    <a href="/auksjoner/15001/arbeidsjakker">
      Parti med arbeidsjakker Avsluttet Høyeste bud 1 000 NOK
    </a>
    <a href="/auksjoner/15001/arbeidsjakker">
      Parti med arbeidsjakker Avsluttet Høyeste bud 1 000 NOK
    </a>
  </body>
</html>
"""


def test_all_ended_page_returns_structured_no_active_candidate() -> None:
    report = build_live_scan_report(
        html=ALL_ENDED_PAGE,
        observed_at="2026-07-27T09:30:00Z",
    )

    assert report["scan_outcome"] == "NO_ACTIVE_CANDIDATE"
    assert report["source_extraction_status"] == "VERIFIED_LISTINGS"
    assert report["final_outcome"] == "NO_ACTIVE_CANDIDATE"
    assert report["final_decision"] == "NO_DECISION"
    assert report["live_listings_extracted"] == 3
    assert report["clothing_listings_extracted"] == 2
    assert report["active_clothing_listings"] == 0
    assert report["ended_clothing_listings"] == 2
    assert {item["listing_id"] for item in report["ended_clothing_candidates"]} == {
        "12001",
        "12002",
    }
    assert report["analysis_invoked"] is False
    assert report["decision_invoked"] is False
    assert report["automatic_purchase_decision"] is False
    assert report["automatic_bid"] is False
    assert report["automatic_contact"] is False
    assert report["automatic_payment"] is False


def test_active_page_reuses_existing_single_case_path() -> None:
    report = build_live_scan_report(
        html=ACTIVE_PAGE,
        observed_at="2026-07-27T09:35:00Z",
    )

    assert report["scan_outcome"] == "ACTIVE_CANDIDATE_SELECTED"
    assert report["source_extraction_status"] == "VERIFIED_LISTINGS"
    assert report["selected_listing_id"] == "13002"
    assert report["selected_listing_status"] == "ACTIVE"
    assert report["final_outcome"] == "EVIDENCE_REQUIRED"
    assert report["dossier"]["confirmed_facts"]["location"] == "Namsos"
    assert report["automatic_purchase_decision"] is False


def test_explicit_empty_page_returns_verified_no_active_candidate() -> None:
    report = build_live_scan_report(
        html="<html><body><p>Ingen auksjoner funnet</p></body></html>",
        observed_at="2026-07-27T09:37:00Z",
    )

    assert report["source_extraction_status"] == "VERIFIED_EMPTY"
    assert report["scan_outcome"] == "NO_ACTIVE_CANDIDATE"
    assert report["final_decision"] == "NO_DECISION"
    assert report["live_listings_extracted"] == 0
    assert report["analysis_invoked"] is False
    assert report["decision_invoked"] is False
    assert report["automatic_purchase_decision"] is False


def test_unverified_zero_page_does_not_claim_no_active_candidate() -> None:
    html = """
    <html>
      <head><title>Vareparti og konkursbo</title></head>
      <body><div id="__NEXT_DATA__"></div></body>
    </html>
    """
    report = build_live_scan_report(
        html=html,
        observed_at="2026-07-27T09:38:00Z",
        final_url="https://www.auksjonen.no/auksjoner/vareparti_konkursbo",
        http_status=200,
        content_type="text/html; charset=utf-8",
        response_byte_count=len(html.encode("utf-8")),
    )

    assert report["source_extraction_status"] == "UNVERIFIED_ZERO"
    assert report["scan_outcome"] == "SOURCE_EXTRACTION_UNVERIFIED"
    assert report["final_outcome"] == "SOURCE_EXTRACTION_UNVERIFIED"
    assert report["final_decision"] == "NO_DECISION"
    assert report["analysis_invoked"] is False
    assert report["decision_invoked"] is False
    assert report["automatic_purchase_decision"] is False
    assert report["automatic_bid"] is False
    assert report["automatic_contact"] is False
    assert report["automatic_payment"] is False
    assert report["source_diagnostics"]["http_status"] == 200
    assert report["source_diagnostics"]["hydration_container_present"] is True

    summary = build_scan_summary(report)
    assert "Scan outcome: SOURCE_EXTRACTION_UNVERIFIED" in summary
    assert "Source extraction: UNVERIFIED_ZERO" in summary
    assert "Analysis invoked: false" in summary


def test_no_active_scan_writes_report_summary_and_listing_review(tmp_path) -> None:
    report = build_live_scan_report(
        html=ALL_ENDED_PAGE,
        observed_at="2026-07-27T09:40:00Z",
    )
    paths = write_scan_outputs(report, tmp_path)

    assert set(paths) == {"report", "summary", "listings_review"}
    stored = json.loads(paths["report"].read_text(encoding="utf-8"))
    summary = paths["summary"].read_text(encoding="utf-8")
    review = json.loads(paths["listings_review"].read_text(encoding="utf-8"))

    assert stored["scan_outcome"] == "NO_ACTIVE_CANDIDATE"
    assert stored["source_extraction_status"] == "VERIFIED_LISTINGS"
    assert stored["final_decision"] == "NO_DECISION"
    assert "_extracted_listing_review_evidence" not in stored
    assert "Scan outcome: NO_ACTIVE_CANDIDATE" in summary
    assert "Source extraction: VERIFIED_LISTINGS" in summary
    assert "Ended clothing listings: 2" in summary
    assert "Analysis invoked: false" in summary
    assert "Automatic purchase/bid/contact/payment: false" in summary

    assert review["schema_version"] == "extracted-listing-review-v1"
    assert review["source_extraction_status"] == "VERIFIED_LISTINGS"
    assert review["scan_observed_at"] == "2026-07-27T09:40:00Z"
    assert review["listing_count"] == 3
    assert len(review["listings"]) == 3
    by_id = {item["listing_id"]: item for item in review["listings"]}
    assert set(by_id) == {"12001", "12002", "12003"}

    jackets = by_id["12001"]
    assert jackets["title"] == "Parti med arbeidsjakker"
    assert jackets["url"].endswith("/auksjoner/12001/arbeidsjakker")
    assert jackets["asking_price_nok"] == 1000
    assert jackets["location"] is None
    assert jackets["listing_status"] == "ENDED"
    assert jackets["clothing_match"] is True
    assert jackets["matched_clothing_terms"] == ["jakke"]

    furniture = by_id["12003"]
    assert furniture["title"] == "Kontormøbler"
    assert furniture["clothing_match"] is False
    assert furniture["matched_clothing_terms"] == []


def test_duplicate_source_listing_appears_once_in_review(tmp_path) -> None:
    report = build_live_scan_report(
        html=DUPLICATE_PAGE,
        observed_at="2026-07-27T09:41:00Z",
    )
    paths = write_scan_outputs(report, tmp_path)
    review = json.loads(paths["listings_review"].read_text(encoding="utf-8"))

    assert report["live_listings_extracted"] == 1
    assert review["listing_count"] == 1
    assert [item["listing_id"] for item in review["listings"]] == ["15001"]


def test_verified_empty_writes_truthful_empty_listing_review(tmp_path) -> None:
    report = build_live_scan_report(
        html="<html><body><p>Ingen auksjoner funnet</p></body></html>",
        observed_at="2026-07-27T09:42:00Z",
    )
    paths = write_scan_outputs(report, tmp_path)
    review = json.loads(paths["listings_review"].read_text(encoding="utf-8"))

    assert review["source_extraction_status"] == "VERIFIED_EMPTY"
    assert review["listing_count"] == 0
    assert review["listings"] == []
    assert report["scan_outcome"] == "NO_ACTIVE_CANDIDATE"
    assert report["analysis_invoked"] is False
    assert report["decision_invoked"] is False


def test_unverified_zero_writes_truthful_empty_listing_review(tmp_path) -> None:
    html = """
    <html>
      <head><title>Vareparti og konkursbo</title></head>
      <body><div id="__NEXT_DATA__"></div></body>
    </html>
    """
    report = build_live_scan_report(
        html=html,
        observed_at="2026-07-27T09:43:00Z",
    )
    paths = write_scan_outputs(report, tmp_path)
    review = json.loads(paths["listings_review"].read_text(encoding="utf-8"))

    assert review["source_extraction_status"] == "UNVERIFIED_ZERO"
    assert review["listing_count"] == 0
    assert review["listings"] == []
    assert report["scan_outcome"] == "SOURCE_EXTRACTION_UNVERIFIED"
    assert report["analysis_invoked"] is False
    assert report["decision_invoked"] is False


def test_active_scan_writes_listing_review_without_changing_selection(tmp_path) -> None:
    report = build_live_scan_report(
        html=ACTIVE_PAGE,
        observed_at="2026-07-27T09:44:00Z",
    )
    paths = write_scan_outputs(report, tmp_path)

    assert set(paths) == {"dossier", "report", "summary", "listings_review"}
    stored = json.loads(paths["report"].read_text(encoding="utf-8"))
    review = json.loads(paths["listings_review"].read_text(encoding="utf-8"))

    assert stored["scan_outcome"] == "ACTIVE_CANDIDATE_SELECTED"
    assert stored["selected_listing_id"] == "13002"
    assert stored["selected_listing_status"] == "ACTIVE"
    assert stored["automatic_purchase_decision"] is False
    assert "_extracted_listing_review_evidence" not in stored
    assert review["source_extraction_status"] == "VERIFIED_LISTINGS"
    assert review["listing_count"] == 2
    assert {item["listing_id"] for item in review["listings"]} == {"13001", "13002"}
    assert all(item["clothing_match"] is True for item in review["listings"])
