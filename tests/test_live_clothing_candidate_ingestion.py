import json

import pytest

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
            "name": "Parti med avsluttede arbeidsjakker",
            "url": "https://www.auksjonen.no/auksjoner/10001",
            "offers": {
              "price": 1800,
              "availability": "https://schema.org/SoldOut"
            }
          },
          {
            "name": "Parti med arbeidsjakker og bukser",
            "url": "https://www.auksjonen.no/auksjoner/10002",
            "offers": {
              "price": 2400,
              "availability": "https://schema.org/InStock"
            },
            "location": {"name": "Namsos"}
          },
          {
            "name": "Kontormøbler fra lager",
            "url": "https://www.auksjonen.no/auksjoner/10003",
            "offers": {
              "price": 1500,
              "availability": "https://schema.org/InStock"
            }
          }
        ]
      }
    </script>
  </head>
</html>
"""

ALL_ENDED_PAGE = """
<html>
  <body>
    <a href="/auksjoner/11001/arbeidsjakker">
      Parti med arbeidsjakker Avsluttet Høyeste bud 1 000 NOK
    </a>
    <a href="/auksjoner/11002/arbeidsbukser">
      Parti med arbeidsbukser Avsluttet Høyeste bud 1 500 NOK
    </a>
  </body>
</html>
"""


def test_live_page_selects_exactly_one_active_clothing_candidate() -> None:
    report = build_live_final_report(
        html=LIVE_PAGE,
        observed_at="2026-07-26T21:30:00Z",
    )

    confirmed = report["dossier"]["confirmed_facts"]
    claims = report["dossier"]["seller_claims"]

    assert report["execution_mode"] == "LIVE_SOURCE"
    assert report["live_listings_extracted"] == 3
    assert report["active_clothing_listings"] == 1
    assert report["selected_listing_id"] == "10002"
    assert report["selected_listing_status"] == "ACTIVE"
    assert confirmed["source_name"] == "AUKSJONEN_NO_LIVE_LISTING"
    assert confirmed["source_url"] == "https://www.auksjonen.no/auksjoner/10002"
    assert confirmed["source_title"] == "Parti med arbeidsjakker og bukser"
    assert confirmed["location"] == "Namsos"
    assert claims["asking_price_nok"] == 2400.0


def test_live_page_refuses_to_promote_ended_clothing_listings() -> None:
    with pytest.raises(
        ValueError,
        match="No active clothing-related Auksjonen listing was found",
    ):
        build_live_final_report(
            html=ALL_ENDED_PAGE,
            observed_at="2026-07-27T08:00:00Z",
        )


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
    assert stored_report["selected_listing_status"] == "ACTIVE"
    assert stored_report["final_outcome"] == "EVIDENCE_REQUIRED"
    assert stored_dossier["domain"] == "CLOTHING_INVENTORY"
    assert "Mode: LIVE_SOURCE" in summary
    assert "Outcome: EVIDENCE_REQUIRED" in summary
    assert "Automatic purchase/bid/contact/payment: false" in summary
