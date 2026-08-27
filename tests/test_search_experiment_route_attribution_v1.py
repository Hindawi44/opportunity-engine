from opportunity_engine.discovery.keyword_shadow_verification import PageFetchResult
from opportunity_engine.search_experiment_route_attribution_v1 import (
    apply_route_attribution_gate,
)


def _result(slot_id: str, *, project_domain: str = "CLOTHING_INVENTORY"):
    return {
        "schema_version": "search-experiment-execution-bridge-1.1",
        "status": "SUCCESS",
        "spec": {
            "market_code": "FR",
            "project_domain": project_domain,
            "slot_id": slot_id,
            "provider": "exa",
            "query": (
                "France liquidation judiciaire vêtements stock lot à vendre "
                "vente aux enchères prix quantité pièces disponible"
            ),
        },
        "outcome": "VERIFIED_ROUTE_SUCCESS",
        "successful_route": True,
        "successful_result_count": 1,
        "verified_result_urls": ["https://example.fr/lot-1"],
        "verified_result_domains": ["example.fr"],
        "automatic_provider_activation": False,
        "production_mutation": False,
    }


def _page(*, title: str, text: str, url: str = "https://example.fr/lot-1"):
    return PageFetchResult(
        requested_url=url,
        final_url=url,
        ok=True,
        status_code=200,
        title=title,
        text=text,
        error=None,
    )


def test_liquidation_query_cannot_turn_wholesale_page_into_liquidation_route():
    report = apply_route_attribution_gate(
        _result("LIQUIDATION_BANKRUPTCY"),
        page_fetcher=lambda _url: _page(
            title="Lot de vestes et costumes",
            text=(
                "Grossiste B2B de vêtements. Lot disponible à la vente, "
                "500 pièces, prix 8 EUR par pièce."
            ),
        ),
    )

    assert report["route_attribution_gate_enforced"] is True
    assert report["route_attribution_query_is_evidence"] is False
    assert report["search_requests_added_by_route_attribution"] == 0
    assert report["successful_route"] is False
    assert report["outcome"] == "NO_VERIFIED_ROUTE"
    assert report["successful_result_count"] == 0
    assert report["verified_result_urls"] == []
    assert report["route_attribution_rejection_reason_counts"] == {
        "ROUTE_FAMILY_MISMATCH:WHOLESALE_STOCK_LOTS": 1
    }
    assert report["route_attribution_audit"][0]["detected_route_family"] == "WHOLESALE_STOCK_LOTS"


def test_page_native_liquidation_evidence_can_prove_liquidation_route():
    report = apply_route_attribution_gate(
        _result("LIQUIDATION_BANKRUPTCY"),
        page_fetcher=lambda _url: _page(
            title="Liquidation judiciaire - stock prêt-à-porter",
            text=(
                "Liquidation judiciaire de la société. Stock de 640 vêtements "
                "à vendre, prix du lot 12 000 EUR."
            ),
        ),
    )

    assert report["successful_route"] is True
    assert report["outcome"] == "VERIFIED_ROUTE_SUCCESS"
    assert report["successful_result_count"] == 1
    assert report["verified_result_urls"] == ["https://example.fr/lot-1"]
    assert report["route_attribution_gate_status"] == "PASS"
    assert report["route_attribution_audit"][0]["detected_route_family"] == "LIQUIDATION_BANKRUPTCY"


def test_judicial_auction_counts_only_as_auction_not_two_route_families():
    page = _page(
        title="Vente aux enchères - liquidation judiciaire",
        text=(
            "Vente judiciaire aux enchères du stock de vêtements après "
            "liquidation judiciaire. 300 pièces, estimation 4 000 EUR."
        ),
    )

    auction = apply_route_attribution_gate(
        _result("AUCTION"),
        page_fetcher=lambda _url: page,
    )
    liquidation = apply_route_attribution_gate(
        _result("LIQUIDATION_BANKRUPTCY"),
        page_fetcher=lambda _url: page,
    )

    assert auction["successful_route"] is True
    assert auction["route_attribution_audit"][0]["detected_route_family"] == "AUCTION"
    assert liquidation["successful_route"] is False
    assert liquidation["route_attribution_rejection_reason_counts"] == {
        "ROUTE_FAMILY_MISMATCH:AUCTION": 1
    }


def test_plain_exact_lot_is_direct_inventory_when_no_other_route_family_is_proven():
    report = apply_route_attribution_gate(
        _result("DIRECT_INVENTORY"),
        page_fetcher=lambda _url: _page(
            title="Stock de 250 manteaux à vendre",
            text="250 manteaux disponibles. Prix du lot 5 000 EUR. Contact vendeur.",
        ),
    )

    assert report["successful_route"] is True
    assert report["route_attribution_audit"][0]["detected_route_family"] == "DIRECT_INVENTORY"


def test_fabric_experiment_keeps_existing_evidence_contract_without_extra_fetch():
    calls = []
    original = _result("FABRIC_PROCUREMENT", project_domain="FABRIC_PROCUREMENT")
    report = apply_route_attribution_gate(
        original,
        page_fetcher=lambda url: calls.append(url),
    )

    assert calls == []
    assert report["successful_route"] is True
    assert report["successful_result_count"] == 1
    assert report["route_attribution_gate_enforced"] is False
    assert report["route_attribution_gate_status"] == "NOT_REQUIRED"
    assert report["search_requests_added_by_route_attribution"] == 0
