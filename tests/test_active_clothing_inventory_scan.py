import json

from scripts.run_active_clothing_inventory_scan import (
    build_live_scan_report,
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


def test_all_ended_page_returns_structured_no_active_candidate() -> None:
    report = build_live_scan_report(
        html=ALL_ENDED_PAGE,
        observed_at="2026-07-27T09:30:00Z",
    )

    assert report["scan_outcome"] == "NO_ACTIVE_CANDIDATE"
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
    assert report["selected_listing_id"] == "13002"
    assert report["selected_listing_status"] == "ACTIVE"
    assert report["final_outcome"] == "EVIDENCE_REQUIRED"
    assert report["dossier"]["confirmed_facts"]["location"] == "Namsos"
    assert report["automatic_purchase_decision"] is False


def test_no_active_scan_writes_report_and_operator_summary(tmp_path) -> None:
    report = build_live_scan_report(
        html=ALL_ENDED_PAGE,
        observed_at="2026-07-27T09:40:00Z",
    )
    paths = write_scan_outputs(report, tmp_path)

    assert set(paths) == {"report", "summary"}
    stored = json.loads(paths["report"].read_text(encoding="utf-8"))
    summary = paths["summary"].read_text(encoding="utf-8")

    assert stored["scan_outcome"] == "NO_ACTIVE_CANDIDATE"
    assert stored["final_decision"] == "NO_DECISION"
    assert "Scan outcome: NO_ACTIVE_CANDIDATE" in summary
    assert "Ended clothing listings: 2" in summary
    assert "Analysis invoked: false" in summary
    assert "Automatic purchase/bid/contact/payment: false" in summary
