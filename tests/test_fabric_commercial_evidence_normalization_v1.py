from __future__ import annotations

from opportunity_engine.discovery.keyword_shadow_verification import PageFetchResult
from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.discovery import unified_search_runtime_cli_hook as runtime
from opportunity_engine.discovery.fabric_route_commercial_evidence_normalization_v1 import (
    normalize_fabric_commercial_evidence,
)


def test_molton_shape_skips_zero_cart_price_and_extracts_total_price_and_linear_length() -> None:
    evidence = normalize_fabric_commercial_evidence(
        "0,00 € cart. Dekomolton Stoffballen auf Lager. "
        "319,00 € brutto, 3,54 € pro m². Länge am Stück: 30 lfm, entspricht 90m² pro Ballen.",
        market="DE",
    )

    assert evidence["price"] == 319.0
    assert evidence["price_text"] == "319,00 €"
    assert evidence["currency"] == "EUR"
    assert evidence["quantity"] == 30.0
    assert evidence["quantity_unit"] == "lfm"
    assert evidence["commercial_evidence_complete"] is True


def test_area_and_weight_are_not_misread_as_procurement_quantity() -> None:
    evidence = normalize_fabric_commercial_evidence(
        "Fabric roll 180 g/m², width 300 cm, area 90m². Price 319 EUR.",
        market="DE",
    )

    assert evidence["price"] == 319.0
    assert evidence["quantity"] is None
    assert evidence["quantity_unit"] is None
    assert evidence["commercial_evidence_complete"] is False


def test_verified_page_is_reused_once_and_runtime_candidate_becomes_analysis_eligible() -> None:
    calls: list[str] = []

    def fetch_once(url: str) -> PageFetchResult:
        calls.append(url)
        return PageFetchResult(
            requested_url=url,
            final_url=url,
            ok=True,
            status_code=200,
            title="Fabric textile deadstock stock roll",
            text=(
                "Fabric textile deadstock stock rolls for wholesale. "
                "0,00 € cart. 319,00 € brutto. Length 30 lfm."
            ),
            error=None,
        )

    hit = SearchHit(
        title="Fabric stock roll",
        url="https://example.test/fabric-roll",
        description="wholesale fabric stock",
        provider="exa",
    )

    audited = runtime._fabric_page_candidate(hit, page_fetcher=fetch_once)
    candidate = runtime._fabric_candidate(market="DE", row=audited)

    assert calls == ["https://example.test/fabric-roll"]
    assert audited["commercial_fabric_page"] is True
    assert audited["normalized_price"] == 319.0
    assert audited["normalized_quantity"] == 30.0
    assert candidate["price"] == 319.0
    assert candidate["currency"] == "EUR"
    assert candidate["quantity"] == 30.0
    assert candidate["quantity_unit"] == "lfm"
    assert candidate["analysis_eligible"] is True
    assert candidate["top5_eligible"] is False
    assert candidate["automatic_purchase"] is False
    assert candidate["automatic_contact"] is False


def test_market_currency_fallback_is_correct_when_no_price_is_present() -> None:
    row = {
        "url": "https://example.test/no-price",
        "final_url": "https://example.test/no-price",
        "title": "Verified fabric commercial page",
        "normalized_price": None,
        "normalized_price_text": None,
        "normalized_currency": None,
        "normalized_quantity": 50.0,
        "normalized_quantity_unit": "meter",
        "commercial_evidence_normalized": True,
        "commercial_evidence_source": "VERIFIED_PAGE_TEXT",
    }

    no_candidate = runtime._fabric_candidate(market="NO", row=row)
    se_candidate = runtime._fabric_candidate(market="SE", row=row)

    assert no_candidate["currency"] == "NOK"
    assert se_candidate["currency"] == "SEK"
    assert no_candidate["analysis_eligible"] is False
    assert se_candidate["analysis_eligible"] is False
