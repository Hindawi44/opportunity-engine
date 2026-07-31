from opportunity_engine.discovery.classifier import (
    classify_candidate,
    to_canonical_opportunity,
)
from opportunity_engine.discovery.models import DiscoveryCandidate
from opportunity_engine.discovery.norway_textile_keywords import (
    DOMAIN,
    NORWAY_TEXTILE_CATEGORIES,
    NORWAY_TEXTILE_QUERY_IDS,
    SCHEMA_VERSION,
    build_norway_textile_keyword_queries,
)
from opportunity_engine.discovery.result_filter import evaluate_candidate
from opportunity_engine.discovery.textile_taxonomy import OpportunityCategory


def _candidate(title: str, text: str = "") -> DiscoveryCandidate:
    return DiscoveryCandidate(
        title=title,
        text=text,
        url="https://example.no/listing/12345",
        source="test",
        discovered_at="2026-07-31T00:00:00+00:00",
    )


def test_pack_is_bounded_traceable_and_covers_every_taxonomy_category() -> None:
    queries = build_norway_textile_keyword_queries()

    assert len(queries) == 16
    assert tuple(query.query_id for query in queries) == NORWAY_TEXTILE_QUERY_IDS
    assert len(set(NORWAY_TEXTILE_QUERY_IDS)) == 16
    assert NORWAY_TEXTILE_CATEGORIES == {
        category.value for category in OpportunityCategory
    }
    assert all(query.schema_version == SCHEMA_VERSION for query in queries)
    assert all(query.query.endswith("Norge") for query in queries)
    assert {query.intent for query in queries} == {
        "SALE_INTENT",
        "EVENT_LEAD",
        "SPECIALIZED",
    }


def test_country_is_rendered_without_changing_the_signal_contract() -> None:
    queries = build_norway_textile_keyword_queries(country="Sverige")

    assert all(query.query.endswith("Sverige") for query in queries)
    assert all(query.event_term in query.query for query in queries)
    assert all(query.sector_term in query.query for query in queries)
    assert all(query.asset_term in query.query for query in queries)


def test_fabric_stock_sale_is_kept_and_classified() -> None:
    candidate = _candidate(
        "Stoffruller og metervare fra restlager selges",
        "Samlet parti tekstiler til salgs fra nedlagt stoffbutikk.",
    )

    assert evaluate_candidate(candidate).keep is True
    result = classify_candidate(candidate)

    assert result.status == "SALE_CONFIRMED"
    assert result.category == OpportunityCategory.FABRIC_TEXTILE_STOCK.value
    assert result.scenario == "STORE_CLOSING"
    assert f"CATEGORY:{result.category}" in result.evidence


def test_tailor_and_atelier_closures_remain_early_signals_without_fake_sale() -> None:
    tailor = classify_candidate(
        _candidate("Skredderverksted avvikles", "Utstyr og lager skal kartlegges.")
    )
    atelier = classify_candidate(
        _candidate("Systue legges ned", "Informasjon om eiendeler kommer senere.")
    )

    assert tailor.status == "CONTACT_REQUIRED"
    assert tailor.category == OpportunityCategory.TAILOR_WORKSHOP_LIQUIDATION.value
    assert atelier.status == "CONTACT_REQUIRED"
    assert atelier.category == OpportunityCategory.SEWING_ATELIER_LIQUIDATION.value


def test_industrial_sewing_machine_sale_is_in_scope() -> None:
    candidate = _candidate(
        "Industrisymaskiner og overlock selges",
        "Utstyr fra sømverksted til salgs samlet.",
    )

    result = classify_candidate(candidate)

    assert evaluate_candidate(candidate).keep is True
    assert result.status == "SALE_CONFIRMED"
    assert result.category == OpportunityCategory.SEWING_MACHINERY.value


def test_chain_closure_is_an_early_signal_until_sale_channel_exists() -> None:
    candidate = _candidate(
        "Kleskjede stenger filial",
        "Varelageret er omtalt, men salgsform er ikke publisert.",
    )

    result = classify_candidate(candidate)

    assert evaluate_candidate(candidate).keep is True
    assert result.status == "CONTACT_REQUIRED"
    assert result.scenario == "BRANCH_CLOSURE"
    assert result.category == OpportunityCategory.CLOTHING_CHAIN_OR_BRANCH_CLOSURE.value


def test_unrelated_kitchen_inventory_remains_rejected() -> None:
    candidate = _candidate(
        "Komplett kjøkkenlager selges",
        "Møbelplater og kjøkkenproduksjon fra avvikling.",
    )

    assert evaluate_candidate(candidate).keep is False
    result = classify_candidate(candidate)
    assert result.status == "REJECTED"
    assert result.category is None


def test_generic_fixtures_require_explicit_clothing_context() -> None:
    generic = classify_candidate(
        _candidate("Lagerreoler selges", "Generelt lagerutstyr til salgs.")
    )
    clothing = classify_candidate(
        _candidate(
            "Butikkinnredning fra klesbutikk selges",
            "Klesstativer, mannekenger og displaybord til salgs.",
        )
    )

    assert generic.status == "REJECTED"
    assert clothing.category == OpportunityCategory.CLOTHING_STORE_FIXTURES.value
    assert clothing.status == "SALE_CONFIRMED"


def test_canonical_output_preserves_category_and_blocks_automatic_purchase() -> None:
    result = classify_candidate(
        _candidate(
            "Sytilbehør og kortvarer fra restlager selges",
            "Glidelåser, knapper og sytråd til salgs.",
        )
    )
    canonical = to_canonical_opportunity(result)

    assert canonical is not None
    assert canonical["discovery"]["domain"] == DOMAIN
    assert canonical["discovery"]["category"] == (
        OpportunityCategory.HABERDASHERY_AND_NOTIONS.value
    )
    assert canonical["automatic_purchase_decision"] is False
