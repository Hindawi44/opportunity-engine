from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from opportunity_engine.discovery.blinto_seller_identity_extraction import (
    OUTPUT_FILENAME,
    collect_blinto_seller_identity_evidence,
    extract_blinto_seller_identity,
    write_blinto_seller_identity_evidence,
)
from opportunity_engine.discovery.sweden_organisation_discovery_bridge import (
    discover_sweden_artifact_company_names,
)
from opportunity_engine.discovery.sweden_valuable_datasets_status_feed import (
    discover_tracked_sweden_organisation_numbers,
)


NOW = datetime(2026, 8, 4, 9, 0, tzinfo=timezone.utc)
URL = "https://blinto.se/auction/Parti-med-arbetsklader-157419-61520"


def _manifest(tmp_path: Path) -> dict[str, Any]:
    return {
        "sources": [
            {
                "market_code": "SE",
                "source_name": "Blinto",
                "artifact_dir": str(tmp_path / "se-blinto"),
            }
        ]
    }


def _write_candidate(tmp_path: Path, urls: list[str] | None = None) -> Path:
    artifact_dir = tmp_path / "se-blinto"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    path = artifact_dir / "all-discovered-candidates.json"
    path.write_text(
        json.dumps(
            {
                "all_discovered_candidates": [
                    {
                        "title": "Parti med arbetskläder",
                        "source_urls": urls or [URL],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return path


def _company_html() -> str:
    return """
    <html>
      <body>
        <h1>Parti med arbetskläder</h1>
        <section>
          <h2>Säljare</h2>
          <p>Nordic Workwear AB</p>
          <p>Organisationsnummer: 559123-4561</p>
        </section>
        <form>
          <h3>Finansiering</h3>
          <label>Organisationsnummer (det är ej möjligt att söka finansiering som privatperson)</label>
          <input>
          <label>Företagsnamn</label>
          <input>
        </form>
      </body>
    </html>
    """


def test_extracts_explicit_company_and_valid_org_number() -> None:
    evidence = extract_blinto_seller_identity(_company_html(), source_url=URL)

    assert evidence.company_name == "Nordic Workwear AB"
    assert evidence.organisationsnummer == "5591234561"
    assert evidence.has_identity is True
    assert evidence.source_url == URL
    assert any("Säljare" in line for line in evidence.evidence_lines)
    assert any("559123-4561" in line for line in evidence.evidence_lines)


def test_natural_assignment_phrase_extracts_company_without_using_title() -> None:
    html = """
    <html><body>
      <h1>Parti med kläder</h1>
      <p>Objektet säljs på uppdrag av Nordic Workwear AB</p>
    </body></html>
    """

    evidence = extract_blinto_seller_identity(html, source_url=URL)

    assert evidence.company_name == "Nordic Workwear AB"
    assert evidence.organisationsnummer is None


def test_generic_private_seller_is_classification_not_company_identity() -> None:
    html = """
    <html><body>
      <p>Objektet säljs på uppdrag av privatperson eller annan ej momspliktig säljare</p>
    </body></html>
    """

    evidence = extract_blinto_seller_identity(html, source_url=URL)

    assert evidence.company_name is None
    assert evidence.organisationsnummer is None
    assert evidence.seller_type == "PRIVATE_OR_NON_VAT_SELLER"
    assert evidence.has_identity is False


def test_financing_form_and_blinto_footer_do_not_create_false_identity() -> None:
    html = """
    <html><body>
      <h1>Parti med arbetskläder</h1>
      <form>
        <label>Organisationsnummer</label>
        <input value="559123-4561">
        <label>Företagsnamn</label>
        <input value="Nordic Workwear AB">
      </form>
      <footer>
        <p>Blinto AB</p>
        <p>Organisationsnummer: 556549-2690</p>
      </footer>
    </body></html>
    """

    evidence = extract_blinto_seller_identity(html, source_url=URL)

    assert evidence.company_name is None
    assert evidence.organisationsnummer is None
    assert evidence.has_identity is False


def test_invalid_luhn_number_is_rejected() -> None:
    html = """
    <html><body>
      <p>Säljare: Nordic Workwear AB</p>
      <p>Organisationsnummer: 559123-4567</p>
    </body></html>
    """

    evidence = extract_blinto_seller_identity(html, source_url=URL)

    assert evidence.company_name == "Nordic Workwear AB"
    assert evidence.organisationsnummer is None


def test_written_artifact_feeds_existing_company_and_org_discovery(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    _write_candidate(tmp_path)

    def html_get(url: str, timeout: float) -> tuple[str, str]:
        assert url.startswith("https://www.blinto.se/auction/")
        assert timeout > 0
        return (
            "https://www.blinto.se/auction/Parti-med-arbetsklader-157419-61520/",
            _company_html(),
        )

    report = write_blinto_seller_identity_evidence(
        manifest,
        root=".",
        observed_at=NOW,
        html_get=html_get,
    )

    assert report["status"] == "SUCCESS"
    assert report["retrieval_complete"] is True
    assert report["candidate_page_url_count"] == 1
    assert report["pages_fetched"] == 1
    assert report["accepted_identity_count"] == 1
    assert report["explicit_company_name_count"] == 1
    assert report["organisation_number_count"] == 1
    output = tmp_path / "se-blinto" / OUTPUT_FILENAME
    assert output.exists()

    names, name_diagnostics = discover_sweden_artifact_company_names(
        manifest,
        root=".",
    )
    assert [item["artifact_company_name"] for item in names] == [
        "Nordic Workwear AB"
    ]
    assert name_diagnostics["artifact_company_name_count"] == 1

    numbers, org_diagnostics = discover_tracked_sweden_organisation_numbers(
        manifest,
        root=".",
        seed=None,
    )
    assert numbers == ["5591234561"]
    assert org_diagnostics["artifact_organisation_count"] == 1


def test_no_identity_is_valid_zero_and_preserves_seller_classification(
    tmp_path: Path,
) -> None:
    manifest = _manifest(tmp_path)
    _write_candidate(tmp_path)

    def html_get(url: str, timeout: float) -> tuple[str, str]:
        return (
            url,
            """
            <html><body>
              <p>Objektet säljs på uppdrag av privatperson eller annan ej momspliktig säljare</p>
            </body></html>
            """,
        )

    report = collect_blinto_seller_identity_evidence(
        manifest,
        root=".",
        observed_at=NOW,
        html_get=html_get,
    )

    assert report["status"] == "VALID_ZERO"
    assert report["accepted_identity_count"] == 0
    assert report["seller_classification_count"] == 1
    assert report["seller_evidence"][0]["company_name"] is None
    assert (
        report["seller_evidence"][0]["seller_type"]
        == "PRIVATE_OR_NON_VAT_SELLER"
    )


def test_page_limit_reports_partial_truth(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    _write_candidate(
        tmp_path,
        [
            URL,
            "https://blinto.se/auction/Parti-med-klader-157420-61521",
        ],
    )

    def html_get(url: str, timeout: float) -> tuple[str, str]:
        return (url, _company_html())

    report = collect_blinto_seller_identity_evidence(
        manifest,
        root=".",
        observed_at=NOW,
        page_limit=1,
        html_get=html_get,
    )

    assert report["status"] == "PARTIAL_RETRIEVAL"
    assert report["retrieval_complete"] is False
    assert report["page_limit_reached"] is True
    assert report["selected_page_url_count"] == 1


def test_network_failure_is_truthful_and_all_automatic_actions_remain_disabled(
    tmp_path: Path,
) -> None:
    manifest = _manifest(tmp_path)
    _write_candidate(tmp_path)

    def html_get(url: str, timeout: float) -> tuple[str, str]:
        raise RuntimeError("temporary public-page failure")

    report = collect_blinto_seller_identity_evidence(
        manifest,
        root=".",
        observed_at=NOW,
        html_get=html_get,
    )

    assert report["status"] == "BLOCKED_DIRECT_ACCESS"
    assert report["retrieval_complete"] is False
    assert report["pages_fetched"] == 0
    assert len(report["errors"]) == 1
    assert "temporary public-page failure" in report["errors"][0]
    for key in (
        "automatic_contact",
        "automatic_bid",
        "automatic_purchase",
        "automatic_payment",
    ):
        assert report[key] is False
