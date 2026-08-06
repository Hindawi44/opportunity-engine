"""Conservative policy corrections for comparable target hydration."""
from __future__ import annotations

from typing import Any, Mapping

from opportunity_engine.discovery import market_comparables_target_hydration as implementation

_INSTALLED = False
_ORIGINAL_INFER_BRANDS = implementation._infer_brands
_ORIGINAL_SPECIFIC_TARGET = implementation._specific_product_target


def _safe_infer_brands(title: object) -> list[str]:
    raw_tokens = {
        token.casefold()
        for token in implementation.benchmark._TOKEN_RE.findall(
            implementation.benchmark._compact(title)
        )
    }
    quantity, _ = implementation._infer_quantity(title)
    if not (raw_tokens & implementation._PRODUCT_TERMS) and quantity is None:
        return []
    return _ORIGINAL_INFER_BRANDS(title)


def _safe_specific_product_target(item: Mapping[str, Any]) -> bool:
    title = implementation.benchmark._compact(item.get("title"))
    raw_tokens = {
        token.casefold()
        for token in implementation.benchmark._TOKEN_RE.findall(title)
    }
    details = implementation.benchmark._details(item)
    has_product = bool(raw_tokens & implementation._PRODUCT_TERMS)
    has_unit = bool(
        implementation._normalise_unit(details.get("unit_hint"))
        or implementation._normalise_unit(details.get("quantity_unit"))
        or implementation._normalise_unit(details.get("minimum_order_unit"))
    )
    if raw_tokens & implementation._GENERIC_COMPANY_TOKENS and not has_product and not has_unit:
        return False
    return _ORIGINAL_SPECIFIC_TARGET(item)


def install_target_hydration_policy() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    implementation._infer_brands = _safe_infer_brands
    implementation._specific_product_target = _safe_specific_product_target
    _INSTALLED = True


install_target_hydration_policy()

FEED_FAMILY = implementation.FEED_FAMILY
hydrate_items_report = implementation.hydrate_items_report
load_local_source_records = implementation.load_local_source_records
quality_query_core = implementation.quality_query_core
safe_target_price = implementation.safe_target_price
select_quality_benchmark_targets = implementation.select_quality_benchmark_targets
write_hydrated_market_comparables_benchmark = (
    implementation.write_hydrated_market_comparables_benchmark
)
