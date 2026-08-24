from __future__ import annotations

from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.project_domain_boundary import CLOTHING_INVENTORY, FABRIC_PROCUREMENT
from opportunity_engine.query_family_shadow import run_query_family_shadow


def _hit(domain: str, slug: str) -> SearchHit:
    return SearchHit(
        title=slug,
        url=f"https://{domain}/{slug}",
        description="commercial result",
        provider="exa",
    )


def _accepted(hit: SearchHit):
    return {
        "url": hit.url,
        "final_url": hit.url,
        "fetch_ok": True,
        "verification_decision": "ACCEPT",
        "rejection_reason": None,
    }


def test_generic_core_runs_same_path_for_fr_fabric():
    query = "France tissus grossiste stock rouleaux"
    hits = [_hit("fabric-a.fr", "one"), _hit("fabric-b.fr", "two")]
    calls = []

    report = run_query_family_shadow(
        market_code="FR",
        project_domain=FABRIC_PROCUREMENT,
        provider_name="exa",
        search=lambda q, count: calls.append((q, count)) or hits[:count],
        verify_hit=_accepted,
        query_family=(("fr-stock-wholesale", query),),
        results_per_query=2,
    )

    assert calls == [(query, 2)]
    assert report["market_code"] == "FR"
    assert report["project_domain"] == FABRIC_PROCUREMENT
    assert report["ranking"][0]["accepted_domain_count"] == 2
    assert report["automatic_query_promotion"] is False
    assert report["production_query_mutation"] is False


def test_generic_core_runs_same_path_for_de_clothing():
    query = "Deutschland Kleidung Mode Restposten Warenlager Verkauf"
    hits = [_hit("apparel-a.de", "lot"), _hit("apparel-b.de", "stock")]

    report = run_query_family_shadow(
        market_code="DE",
        project_domain=CLOTHING_INVENTORY,
        provider_name="exa",
        search=lambda _q, count: hits[:count],
        verify_hit=_accepted,
        query_family=(("de-clothing-stock", query),),
        results_per_query=2,
    )

    assert report["market_code"] == "DE"
    assert report["project_domain"] == CLOTHING_INVENTORY
    assert report["union_accepted_domain_count"] == 2
    assert report["shadow_only"] is True


def test_generic_core_rejects_market_and_domain_escape():
    try:
        run_query_family_shadow(
            market_code="FR",
            project_domain=FABRIC_PROCUREMENT,
            provider_name="exa",
            search=lambda _q, _count: [],
            verify_hit=_accepted,
            query_family=(("wrong-market", "Nederland stoffen groothandel voorraad"),),
        )
    except ValueError as exc:
        assert "FR-anchored" in str(exc)
    else:
        raise AssertionError("expected market gate failure")

    try:
        run_query_family_shadow(
            market_code="DE",
            project_domain=CLOTHING_INVENTORY,
            provider_name="exa",
            search=lambda _q, _count: [],
            verify_hit=_accepted,
            query_family=(("wrong-domain", "Deutschland Stoffballen Textil wholesale stock"),),
        )
    except ValueError as exc:
        assert "CLOTHING_INVENTORY" in str(exc)
    else:
        raise AssertionError("expected project-domain gate failure")
