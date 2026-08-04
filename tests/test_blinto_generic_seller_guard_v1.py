from pathlib import Path

from opportunity_engine.discovery.blinto_generic_seller_guard import (
    generic_seller_classification,
    sanitize_blinto_seller_identity_report,
)


ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = ROOT / "scripts/build_domain_market_intelligence_feed.py"


def _report(
    company_name: str | None,
    *,
    status: str = "PARTIAL_RETRIEVAL",
    organisation_number: str | None = None,
) -> dict:
    return {
        "status": status,
        "accepted_identity_count": 1,
        "explicit_company_name_count": int(bool(company_name)),
        "organisation_number_count": int(bool(organisation_number)),
        "seller_classification_count": 0,
        "seller_evidence_count": 1,
        "seller_evidence": [
            {
                "company_name": company_name,
                "organisationsnummer": organisation_number,
                "seller_type": None,
                "source_url": (
                    "https://blinto.se/auction/"
                    "LBrador-Blaklader-232831-148712"
                ),
                "evidence_lines": [
                    "Säljs på uppdrag av återförsäljare."
                ],
                "verified_public_page": True,
            }
        ],
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def test_live_generic_reseller_label_is_not_a_company_identity() -> None:
    source = _report("återförsäljare.")

    result = sanitize_blinto_seller_identity_report(source)

    assert source["seller_evidence"][0]["company_name"] == "återförsäljare."
    assert result["status"] == "PARTIAL_RETRIEVAL"
    assert result["accepted_identity_count"] == 0
    assert result["explicit_company_name_count"] == 0
    assert result["organisation_number_count"] == 0
    assert result["seller_classification_count"] == 1
    assert result["generic_identity_rejection_count"] == 1
    assert result["seller_evidence"][0]["company_name"] is None
    assert (
        result["seller_evidence"][0]["seller_type"]
        == "RESELLER_OR_DEALER"
    )
    assert result["seller_evidence"][0]["evidence_lines"] == [
        "Säljs på uppdrag av återförsäljare."
    ]


def test_generic_role_punctuation_and_ascii_variants_are_rejected() -> None:
    for value in (
        "återförsäljare.",
        "ÅTERFÖRSÄLJARE!",
        "(reseller)",
        "aterforsaljaren,",
        "distributör;",
        "supplier",
    ):
        assert generic_seller_classification(value) is not None


def test_specific_company_name_is_preserved() -> None:
    source = _report("Nordic Workwear AB")

    result = sanitize_blinto_seller_identity_report(source)

    assert result["accepted_identity_count"] == 1
    assert result["explicit_company_name_count"] == 1
    assert result["seller_classification_count"] == 0
    assert result["generic_identity_rejection_count"] == 0
    assert result["seller_evidence"][0]["company_name"] == "Nordic Workwear AB"
    assert result["seller_evidence"][0]["seller_type"] is None


def test_validated_organisation_number_remains_an_identity() -> None:
    source = _report(
        "återförsäljare.",
        organisation_number="5565492690",
    )

    result = sanitize_blinto_seller_identity_report(source)

    assert result["accepted_identity_count"] == 1
    assert result["explicit_company_name_count"] == 0
    assert result["organisation_number_count"] == 1
    assert result["seller_evidence"][0]["company_name"] is None
    assert result["seller_evidence"][0]["organisationsnummer"] == "5565492690"


def test_complete_generic_only_result_becomes_valid_zero() -> None:
    source = _report("återförsäljare.", status="SUCCESS")

    result = sanitize_blinto_seller_identity_report(source)

    assert result["status"] == "VALID_ZERO"
    assert result["accepted_identity_count"] == 0


def test_safety_flags_remain_false() -> None:
    result = sanitize_blinto_seller_identity_report(_report("återförsäljare."))

    for key in (
        "automatic_contact",
        "automatic_bid",
        "automatic_purchase",
        "automatic_payment",
    ):
        assert result[key] is False


def test_daily_builder_rewrites_sanitized_source_before_identity_bridge() -> None:
    text = BUILD_SCRIPT.read_text(encoding="utf-8")

    sanitize = text.index("sanitize_blinto_seller_identity_report")
    rewrite = text.index("_rewrite_source_artifact(blinto_seller_identity")
    bridge = text.index("resolve_sweden_artifact_company_identities(")

    assert sanitize < rewrite < bridge
