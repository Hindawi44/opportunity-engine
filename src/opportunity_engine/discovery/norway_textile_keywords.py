"""Bounded Norwegian keyword pack for textile and sewing opportunity discovery.

The pack converts the expanded taxonomy into a small, traceable query matrix.
Every query combines a commercial event, a business-sector signal, and an
inventory or equipment signal. It does not rank, qualify, contact, bid, or buy.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace

from opportunity_engine.discovery.textile_taxonomy import OpportunityCategory


SCHEMA_VERSION = "norway-textile-keyword-pack-v1"
DOMAIN = "TEXTILE_AND_SEWING"


@dataclass(frozen=True, slots=True)
class NorwayTextileKeywordQuery:
    query_id: str
    scenario: str
    intent: str
    category: str
    event_term: str
    sector_term: str
    asset_term: str
    query: str
    rotation_group: str = "PRIMARY"
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


_BASE_SPECS: tuple[NorwayTextileKeywordQuery, ...] = (
    NorwayTextileKeywordQuery(
        "sale-01", "INVENTORY_LIQUIDATION", "SALE_INTENT",
        OpportunityCategory.CLOTHING_INVENTORY.value,
        "selges", "klesbutikk", "varelager",
        "klesbutikk varelager selges {country}",
    ),
    NorwayTextileKeywordQuery(
        "sale-02", "WAREHOUSE_SURPLUS", "SALE_INTENT",
        OpportunityCategory.FABRIC_TEXTILE_STOCK.value,
        "restlager", "stoff", "stoffruller",
        "stoffruller restlager selges {country}",
    ),
    NorwayTextileKeywordQuery(
        "sale-03", "AUCTION", "SALE_INTENT",
        OpportunityCategory.SEWING_MACHINERY.value,
        "auksjon", "tekstilbedrift", "industrisymaskiner",
        "industrisymaskiner tekstilbedrift auksjon {country}",
    ),
    NorwayTextileKeywordQuery(
        "sale-04", "WAREHOUSE_SURPLUS", "SALE_INTENT",
        OpportunityCategory.HABERDASHERY_AND_NOTIONS.value,
        "restlager", "sybutikk", "sytilbehør",
        "sytilbehør sybutikk restlager {country}",
    ),
    NorwayTextileKeywordQuery(
        "sale-05", "COMPANY_BANKRUPTCY", "SALE_INTENT",
        OpportunityCategory.TAILOR_WORKSHOP_LIQUIDATION.value,
        "konkursbo", "skredderverksted", "utstyr",
        "skredderverksted utstyr konkursbo {country}",
    ),
    NorwayTextileKeywordQuery(
        "sale-06", "STORE_CLOSING", "SALE_INTENT",
        OpportunityCategory.SMALL_CLOTHING_STORE_LIQUIDATION.value,
        "opphørssalg", "klesbutikk", "hele lageret",
        "opphørssalg klesbutikk hele lageret {country}",
    ),
    NorwayTextileKeywordQuery(
        "lead-01", "BRANCH_CLOSURE", "EVENT_LEAD",
        OpportunityCategory.CLOTHING_CHAIN_OR_BRANCH_CLOSURE.value,
        "filial stenger", "kleskjede", "varelager",
        "kleskjede filial stenger varelager {country}",
    ),
    NorwayTextileKeywordQuery(
        "lead-02", "STORE_CLOSING", "EVENT_LEAD",
        OpportunityCategory.SEWING_ATELIER_LIQUIDATION.value,
        "avvikling", "systue", "utstyr",
        "systue avvikling utstyr {country}",
    ),
    NorwayTextileKeywordQuery(
        "lead-03", "COMPANY_BANKRUPTCY", "EVENT_LEAD",
        OpportunityCategory.SEWING_FACTORY_LIQUIDATION.value,
        "konkurs", "klesproduksjon", "produksjonsutstyr",
        "klesproduksjon konkurs produksjonsutstyr {country}",
    ),
    NorwayTextileKeywordQuery(
        "lead-04", "WAREHOUSE_SURPLUS", "EVENT_LEAD",
        OpportunityCategory.BRAND_INVENTORY_LIQUIDATION.value,
        "restlager", "klesmerke", "merkevarer",
        "klesmerke merkevarer restlager {country}",
    ),
    NorwayTextileKeywordQuery(
        "lead-05", "STORE_CLOSING", "EVENT_LEAD",
        OpportunityCategory.SHOES_BAGS_ACCESSORIES_INVENTORY.value,
        "opphør", "skobutikk", "varelager",
        "skobutikk opphør varelager {country}",
    ),
    NorwayTextileKeywordQuery(
        "lead-06", "STORE_CLOSING", "EVENT_LEAD",
        OpportunityCategory.FABRIC_TEXTILE_STOCK.value,
        "opphør", "stoffbutikk", "stofflager",
        "stoffbutikk opphør stofflager {country}",
    ),
    NorwayTextileKeywordQuery(
        "special-01", "INVENTORY_LIQUIDATION", "SPECIALIZED",
        OpportunityCategory.CLOTHING_INVENTORY.value,
        "samlet salg", "klær", "hele varelageret",
        '"hele varelageret" klær samlet salg {country}',
        "SECONDARY",
    ),
    NorwayTextileKeywordQuery(
        "special-02", "AUCTION", "SPECIALIZED",
        OpportunityCategory.FABRIC_TEXTILE_STOCK.value,
        "auksjon", "tekstil", "stoffruller",
        "stoffruller tekstil auksjon {country}",
        "SECONDARY",
    ),
    NorwayTextileKeywordQuery(
        "special-03", "LARGE_LOT_SALE", "SPECIALIZED",
        OpportunityCategory.SEWING_MACHINERY.value,
        "selges", "systue", "overlock",
        "overlock systue selges {country}",
        "SECONDARY",
    ),
    NorwayTextileKeywordQuery(
        "special-04", "LARGE_LOT_SALE", "SPECIALIZED",
        OpportunityCategory.CLOTHING_STORE_FIXTURES.value,
        "selges", "klesbutikk", "butikkinnredning",
        "butikkinnredning klesbutikk selges {country}",
        "SECONDARY",
    ),
)


def build_norway_textile_keyword_queries(
    *,
    country: str = "Norge",
) -> tuple[NorwayTextileKeywordQuery, ...]:
    """Render and validate the bounded Norwegian query pack."""
    normalized_country = " ".join(country.split())
    if not normalized_country:
        raise ValueError("country must be a non-empty string")

    rendered = tuple(
        replace(spec, query=spec.query.format(country=normalized_country))
        for spec in _BASE_SPECS
    )
    query_ids = [spec.query_id for spec in rendered]
    if len(set(query_ids)) != len(query_ids):
        raise ValueError("Norway textile keyword query IDs must be unique")

    allowed_categories = {category.value for category in OpportunityCategory}
    normalized_queries: set[str] = set()
    for spec in rendered:
        if spec.category not in allowed_categories:
            raise ValueError(f"unsupported opportunity category: {spec.category}")
        query_text = " ".join(spec.query.casefold().replace('"', "").split())
        for field_name, value in (
            ("event_term", spec.event_term),
            ("sector_term", spec.sector_term),
            ("asset_term", spec.asset_term),
        ):
            normalized_value = " ".join(value.casefold().split())
            if normalized_value not in query_text:
                raise ValueError(
                    f"{spec.query_id} query must contain {field_name}: {value}"
                )
        if query_text in normalized_queries:
            raise ValueError("Norway textile keyword queries must be unique")
        normalized_queries.add(query_text)

    return rendered


NORWAY_TEXTILE_QUERY_IDS = tuple(spec.query_id for spec in _BASE_SPECS)
NORWAY_TEXTILE_CATEGORIES = frozenset(spec.category for spec in _BASE_SPECS)
