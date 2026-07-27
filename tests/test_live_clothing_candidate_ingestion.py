import json

from scripts.run_clothing_inventory_single_case import (
    build_live_final_report,
    write_report_outputs,
)


LIVE_PAGE = """
<html>
  <head>
    <script type="application/ld+json">
      {
        "@context": "https://schema.org",
        "@graph": [
          {
            "name": "Kontormøbler fra lager",
            "url": "https://www.auksjonen.no/auksjoner/10001",
            "offers": {"price": 1500}
          },
          {
            "name": "Parti med arbeidsjakker og bukser",
            "url": "https://www.auksjonen.no/auksjoner/10002",
            "offers": {"price": 2400},
            "location": {"name": "Namsos"}
          }
        ]
      }
    </script>
  </head>
</html>
"""


def test_live_page_selects_exactly_one_clothing_candidate() -> None:
    report = build_live_final_report(
        html=LIVE_PAGE,
        observed_at="2026-07-26T21:30:00Z",
    )

    confirmed = report["dossier"]["confirmed_facts"]
    claims = report["dossier"]["seller_claims"]

    assert report["execution_mode"] == "LIVE_SOURCE"
    assert report["live_listings_extracted"] == 2
    assert report["selected_listing_id"] == "10002"
    assert confirmed["source_name"] == "AUKSJONEN_NO_LIVE_LISTING"
    assert confirmed["source_url"] == "https://www.auksjonen.no/auksjoner/10002"
    assert confirmed["source_title"] == "Parti med arbeidsjakker og bukser"
    assert confirmed["location"] == "Namsos"
    assert claims["asking_price_nok"] == 2400.0


def test_live_candidate_preserves_unknowns_and_blocks_analysis() -> None:
    report = build_live_final_report(
        html=LIVE_PAGE,
        observed_at="2026-07-26T21:30:00Z",
    )

    dossier = report["dossier"]
    eligibility = report["eligibility"]

    assert "quantity" in dossier["unknown_fields"]
    assert "public_contact" in dossier["unknown_fields"]
    assert eligibility["eligible_for_analysis"] is False
    assert "verified quantity" in eligibility["missing_requirements"]
    assert "verified market comparables" in eligibility["missing_requirements"]
    assert report["final_outcome"] == "EVIDENCE_REQUIRED"
    assert report["analysis_invoked"] is False
    assert report["automatic_purchase_decision"] is False
    assert report["automatic_bid"] is False
    assert report["automatic_contact"] is False
    assert report["automatic_payment"] is False


def test_live_report_writes_deterministic_operator_outputs(tmp_path) -> None:
    report = build_live_final_report(
        html=LIVE_PAGE,
        observed_at="2026-07-26T21:30:00Z",
    )
    paths = write_report_outputs(report, tmp_path)

    stored_report = json.loads(paths["report"].read_text(encoding="utf-8"))
    stored_dossier = json.loads(paths["dossier"].read_text(encoding="utf-8"))
    summary = paths["summary"].read_text(encoding="utf-8")

    assert stored_report["selected_listing_id"] == "10002"
    assert stored_report["final_outcome"] == "EVIDENCE_REQUIRED"
    assert stored_dossier["domain"] == "CLOTHING_INVENTORY"
    assert "Mode: LIVE_SOURCE" in summary
    assert "Outcome: EVIDENCE_REQUIRED" in summary
    assert "Automatic purchase/bid/contact/payment: false" in summary
