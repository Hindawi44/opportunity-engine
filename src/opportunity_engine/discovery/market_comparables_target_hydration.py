"""Hydrate and quality-gate public market-comparable targets.

This layer enriches only the benchmark projection from already-produced local
source artifacts. It performs no network retrieval beyond the bounded search
requests owned by MARKET_COMPARABLES_BENCHMARK_V1.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urlsplit

from opportunity_engine.discovery import market_comparables_benchmark as benchmark

SCHEMA_VERSION = "market-comparables-target-hydration-1.0"
FEED_FAMILY = "MARKET_COMPARABLES_TARGET_HYDRATION_AND_QUERY_QUALITY_V1"

_SOURCE_REPORT_FILES = (
    "auksjonen-live-clothing-listings.json",
    "all-discovered-candidates.json",
    "unified-opportunity-report.json",
    "finn-email-intake.json",
)
_RECORD_LIST_KEYS = {
    "listings", "candidates", "opportunities", "leads", "items", "top5",
    "direct_opportunities", "current_direct_opportunities",
}
_PRODUCT_TERMS = {
    "jacket", "jackets", "coat", "coats", "workwear", "coverall", "coveralls",
    "trousers", "pants", "dress", "dresses", "gown", "gowns", "shirt", "shirts",
    "shoe", "shoes", "footwear", "clothing", "apparel", "lace", "tulle", "fabric",
    "jakke", "jakker", "arbeidsklær", "arbeidsklaer", "arbeidsplagg", "kjeledress",
    "kjeledresser", "bukse", "bukser", "kjole", "kjoler", "varselklær",
    "varselklaer", "varselgensere", "skjorter", "t-skjorter", "kläder", "jacka",
    "arbetskläder", "bekleidung", "jacke", "arbeitskleidung", "kleidung",
}
_QUERY_NOISE = {
    "parti", "pakke", "batch", "assorted", "assortment", "mix", "grade",
    "str", "size", "sizes", "inkl", "including", "plus", "premium",
    "stk", "pcs", "piece", "pieces", "items", "item", "kg", "lot", "pallet",
}
_GENERIC_COMPANY_TOKENS = {
    "as", "asa", "ab", "gmbh", "ltd", "limited", "company", "co", "auksjonen",
    "parti", "str", "inkl",
}
_SIZE_TOKEN_RE = re.compile(r"^(?:\d{1,3}|[xsml]{1,4}|\d{1,2}xl)$", re.IGNORECASE)
_EXPLICIT_QTY_RE = re.compile(
    r"\b(?P<n>\d{1,7})\s*(?P<u>stk|st\.?|pcs?|pieces?|items?)\b",
    re.IGNORECASE,
)
_CAPITALISED_RE = re.compile(r"\b[A-ZÆØÅÄÖÜ][A-Za-zÆØÅæøåÄÖäöÜü0-9&.-]{2,}\b")


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _canonical_url(value: object) -> str | None:
    return benchmark._canonical_url(value)


def _artifact_candidates(output_dir: Path, raw_dir: object) -> list[Path]:
    raw = Path(str(raw_dir or "").strip())
    if not raw.parts:
        return []
    candidates = [raw, Path.cwd() / raw]
    try:
        candidates.append(output_dir.resolve().parents[1] / raw)
    except IndexError:
        pass
    if raw.parts and raw.parts[0] == "artifacts":
        candidates.append(output_dir.parent / Path(*raw.parts[1:]))
    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique


def _iter_records(value: object, *, depth: int = 0) -> Iterable[Mapping[str, Any]]:
    if depth > 6:
        return
    if isinstance(value, list):
        for entry in value:
            yield from _iter_records(entry, depth=depth + 1)
        return
    if not isinstance(value, Mapping):
        return
    if any(value.get(key) for key in ("url", "source_url", "canonical_url", "listing_id", "object_id")):
        yield value
    for key, nested in value.items():
        if key in _RECORD_LIST_KEYS or isinstance(nested, (list, Mapping)):
            yield from _iter_records(nested, depth=depth + 1)


def load_local_source_records(output_dir: Path) -> list[dict[str, Any]]:
    """Load a bounded set of source reports named by the checkpoint manifest."""
    manifest = _load_json(output_dir / "input-manifest.json")
    sources = manifest.get("sources") if isinstance(manifest.get("sources"), list) else []
    records: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for source in sources:
        if not isinstance(source, Mapping):
            continue
        source_dir = next(
            (candidate for candidate in _artifact_candidates(output_dir, source.get("artifact_dir")) if candidate.is_dir()),
            None,
        )
        if source_dir is None:
            continue
        names = [benchmark._compact(source.get("report_file")), *_SOURCE_REPORT_FILES]
        for name in dict.fromkeys(value for value in names if value):
            path = source_dir / name
            if not path.is_file():
                continue
            payload = _load_json(path)
            for raw in _iter_records(payload):
                record = dict(raw)
                url = _canonical_url(
                    record.get("source_url") or record.get("url") or record.get("canonical_url")
                )
                identity = benchmark._compact(
                    record.get("listing_id") or record.get("object_id")
                    or record.get("opportunity_identity") or record.get("candidate_id")
                )
                key = (url or identity, str(path))
                if not key[0] or key in seen:
                    continue
                seen.add(key)
                record["_hydration_artifact"] = str(path)
                record["_hydration_currency"] = benchmark._compact(source.get("currency")).upper() or None
                records.append(record)
    return records


def _record_url(record: Mapping[str, Any]) -> str | None:
    return _canonical_url(record.get("source_url") or record.get("url") or record.get("canonical_url"))


def _url_identifier(url: object) -> str | None:
    canonical = _canonical_url(url)
    if not canonical:
        return None
    segment = urlsplit(canonical).path.rstrip("/").rsplit("/", 1)[-1]
    match = re.search(r"\d{5,}", segment)
    return match.group(0) if match else None


def _matching_records(item: Mapping[str, Any], records: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    item_url = _canonical_url(item.get("source_url"))
    item_identifier = _url_identifier(item_url)
    matches: list[Mapping[str, Any]] = []
    for record in records:
        record_url = _record_url(record)
        record_identifier = benchmark._compact(record.get("listing_id") or record.get("object_id"))
        if item_url and record_url == item_url:
            matches.append(record)
        elif item_identifier and record_identifier == item_identifier:
            matches.append(record)
    return matches


def _infer_quantity(title: object) -> tuple[float | None, str | None]:
    match = _EXPLICIT_QTY_RE.search(benchmark._compact(title))
    if not match:
        return None, None
    return float(match.group("n")), "items"


def _infer_brands(title: object) -> list[str]:
    value = benchmark._compact(title)
    brands: list[str] = []
    for token in _CAPITALISED_RE.findall(value):
        folded = token.casefold().strip(".")
        if folded in _GENERIC_COMPANY_TOKENS or folded in _PRODUCT_TERMS:
            continue
        if _SIZE_TOKEN_RE.fullmatch(token):
            continue
        if token not in brands:
            brands.append(token)
    return brands[:5]


def _normalise_unit(value: object) -> str | None:
    unit = benchmark._compact(value).casefold().rstrip(".")
    if unit in {"unit", "units"}:
        return "items"
    if unit in {"pc", "pcs", "piece", "pieces", "item", "items", "stk", "st"}:
        return "items"
    if unit in {"kg", "kilogram", "kilograms"}:
        return "kg"
    if unit in {"m", "metre", "metres", "meter", "meters"}:
        return "m"
    return None


def _first_number(records: Sequence[Mapping[str, Any]], *fields: str) -> tuple[float | None, str | None]:
    for record in records:
        for field in fields:
            value = benchmark._number(record.get(field))
            if value is not None:
                return value, field
    return None, None


def hydrate_items_report(
    items_report: Mapping[str, Any],
    source_records: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    hydrated = deepcopy(dict(items_report))
    items = hydrated.get("items") if isinstance(hydrated.get("items"), list) else []
    provenance: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        item_id = benchmark._compact(item.get("intelligence_id"))
        details = dict(item.get("details") or {}) if isinstance(item.get("details"), Mapping) else {}
        matches = _matching_records(item, source_records)
        fields_added: list[str] = []

        current_bid, current_bid_field = _first_number(
            matches, "current_bid", "current_bid_nok", "bid_price_nok"
        )
        if current_bid is not None and benchmark._number(details.get("current_bid")) is None:
            details["current_bid"] = current_bid
            fields_added.append("current_bid")

        unit_price, unit_price_field = _first_number(matches, "unit_price", "unit_price_nok")
        if unit_price is not None and benchmark._number(details.get("unit_price")) is None:
            details["unit_price"] = unit_price
            fields_added.append("unit_price")

        price, price_field = _first_number(
            matches, "price", "price_nok", "advertised_price_nok", "total_price", "total_price_nok"
        )
        if price is not None and not any(
            benchmark._number(details.get(field)) is not None
            for field in ("price", "total_price", "current_bid", "unit_price")
        ):
            details["price"] = price
            fields_added.append("price")

        quantity, _ = _first_number(matches, "quantity", "item_count", "total_quantity")
        quantity_unit = next(
            (
                _normalise_unit(record.get("quantity_unit") or record.get("unit"))
                for record in matches
                if _normalise_unit(record.get("quantity_unit") or record.get("unit"))
            ),
            None,
        )
        if quantity is None:
            quantity, inferred_unit = _infer_quantity(item.get("title"))
            quantity_unit = quantity_unit or inferred_unit
        if quantity is not None and benchmark._number(details.get("quantity")) is None:
            details["quantity"] = quantity
            fields_added.append("quantity")
        if quantity_unit and not details.get("quantity_unit"):
            details["quantity_unit"] = quantity_unit
            fields_added.append("quantity_unit")

        existing_hint = _normalise_unit(details.get("unit_hint") or details.get("minimum_order_unit"))
        if existing_hint and existing_hint != details.get("unit_hint"):
            details["unit_hint"] = existing_hint
            fields_added.append("unit_hint")

        raw_title_tokens = {
            token.casefold() for token in benchmark._TOKEN_RE.findall(benchmark._compact(item.get("title")))
        }
        if not details.get("unit_hint") and benchmark._compact(item.get("record_kind")).upper() == "FABRIC_PROCUREMENT_ITEM":
            details["unit_hint"] = "m"
            details["comparison_unit_inferred_from_product_type"] = True
            fields_added.append("unit_hint")
        elif not details.get("unit_hint") and raw_title_tokens & _PRODUCT_TERMS:
            details["unit_hint"] = "items"
            details["comparison_unit_inferred_from_product_type"] = True
            fields_added.append("unit_hint")

        if not details.get("currency"):
            nok_fields = {current_bid_field, unit_price_field, price_field}
            if any(field and field.endswith("_nok") for field in nok_fields):
                details["currency"] = "NOK"
                fields_added.append("currency")
            else:
                source_currency = next(
                    (
                        benchmark._compact(record.get("_hydration_currency")).upper()
                        for record in matches
                        if benchmark._compact(record.get("_hydration_currency"))
                    ),
                    "",
                )
                if source_currency:
                    details["currency"] = source_currency
                    fields_added.append("currency")

        if not details.get("auction_end_text"):
            ends_at = next(
                (
                    benchmark._compact(record.get("ends_at") or record.get("auction_end_text"))
                    for record in matches
                    if benchmark._compact(record.get("ends_at") or record.get("auction_end_text"))
                ),
                "",
            )
            if ends_at:
                details["auction_end_text"] = ends_at
                fields_added.append("auction_end_text")

        if not details.get("brands"):
            brands = next(
                (
                    [benchmark._compact(value) for value in record.get("brands") if benchmark._compact(value)]
                    for record in matches
                    if isinstance(record.get("brands"), list) and record.get("brands")
                ),
                [],
            ) or _infer_brands(item.get("title"))
            if brands:
                details["brands"] = brands
                fields_added.append("brands")

        item["details"] = details
        if item_id:
            provenance[item_id] = {
                "status": "HYDRATED" if fields_added else "NO_ADDITIONAL_FIELDS",
                "fields_added": sorted(set(fields_added)),
                "source_artifacts": sorted(
                    {
                        benchmark._compact(record.get("_hydration_artifact"))
                        for record in matches
                        if benchmark._compact(record.get("_hydration_artifact"))
                    }
                ),
                "matched_source_record_count": len(matches),
            }
    return hydrated, provenance


def _specific_product_target(item: Mapping[str, Any]) -> bool:
    title = benchmark._compact(item.get("title"))
    url = _canonical_url(item.get("source_url"))
    if not title or not url:
        return False
    path = urlsplit(url).path.casefold()
    if any(marker in path for marker in ("/collections/", "/category/", "/categories/", "/shop")):
        return False
    raw_tokens = {token.casefold() for token in benchmark._TOKEN_RE.findall(title)}
    details = benchmark._details(item)
    has_product = bool(raw_tokens & _PRODUCT_TERMS)
    has_brand = bool(details.get("brands"))
    has_unit = bool(
        _normalise_unit(details.get("unit_hint"))
        or _normalise_unit(details.get("quantity_unit"))
        or _normalise_unit(details.get("minimum_order_unit"))
    )
    company_like = (
        bool(raw_tokens & _GENERIC_COMPANY_TOKENS)
        and not has_product
        and not has_brand
        and not has_unit
    )
    return not company_like and (has_product or has_brand or has_unit)


def select_quality_benchmark_targets(
    brief: Mapping[str, Any],
    cases_report: Mapping[str, Any],
    items_report: Mapping[str, Any],
    *,
    max_targets: int = benchmark.MAX_TARGETS,
) -> list[dict[str, Any]]:
    cards = brief.get("actionable_now") if isinstance(brief.get("actionable_now"), list) else []
    cases = cases_report.get("cases") if isinstance(cases_report.get("cases"), list) else []
    items = items_report.get("items") if isinstance(items_report.get("items"), list) else []
    case_by_id = {
        benchmark._compact(case.get("case_id")): case
        for case in cases
        if isinstance(case, Mapping) and benchmark._compact(case.get("case_id"))
    }
    item_by_id = {
        benchmark._compact(item.get("intelligence_id")): item
        for item in items
        if isinstance(item, Mapping) and benchmark._compact(item.get("intelligence_id"))
    }
    targets: list[dict[str, Any]] = []
    seen: set[str] = set()
    for card in cards:
        if not isinstance(card, Mapping):
            continue
        case_id = benchmark._compact(card.get("case_id"))
        case = case_by_id.get(case_id, {})
        item_ids = case.get("item_ids") if isinstance(case.get("item_ids"), list) else []
        candidates = [item_by_id.get(benchmark._compact(item_id)) for item_id in item_ids]
        candidates = [
            item for item in candidates
            if isinstance(item, Mapping) and _specific_product_target(item)
        ]
        if not candidates:
            continue
        chosen = max(candidates, key=benchmark._item_richness)
        item_id = benchmark._compact(chosen.get("intelligence_id"))
        if not item_id or item_id in seen:
            continue
        seen.add(item_id)
        details = dict(benchmark._details(chosen))
        targets.append(
            {
                "rank": len(targets) + 1,
                "case_id": case_id,
                "intelligence_id": item_id,
                "title": benchmark._compact(chosen.get("title") or card.get("headline")),
                "record_kind": benchmark._compact(chosen.get("record_kind")).upper(),
                "source_name": benchmark._compact(chosen.get("source_name")),
                "source_country": benchmark._compact(chosen.get("source_country")).upper() or "NO",
                "source_url": _canonical_url(chosen.get("source_url")),
                "seller_name": benchmark._compact(chosen.get("seller_name")) or None,
                "brands": [
                    benchmark._compact(value)
                    for value in (details.get("brands") or [])
                    if benchmark._compact(value)
                ][:10],
                "details": details,
                "actionability_score": card.get("actionability_score"),
                "priority_class": card.get("priority_class"),
            }
        )
        if len(targets) >= max_targets:
            break
    return targets


def quality_query_core(target: Mapping[str, Any]) -> str:
    title = benchmark._compact(target.get("title"))
    brands = [benchmark._compact(value) for value in target.get("brands") or [] if benchmark._compact(value)]
    brand_tokens = {
        token.casefold()
        for brand in brands
        for token in benchmark._TOKEN_RE.findall(brand)
    }
    words: list[str] = []
    for raw in benchmark._TOKEN_RE.findall(title):
        folded = raw.casefold()
        if (
            folded in benchmark._STOPWORDS
            or folded in _QUERY_NOISE
            or folded in brand_tokens
            or _SIZE_TOKEN_RE.fullmatch(raw)
        ):
            continue
        if raw not in words:
            words.append(raw)
    selected = words[:5]
    prefix = f'"{brands[0]}" ' if brands else ""
    core = benchmark._compact(f"{prefix}{' '.join(selected) or title}")
    source_url = _canonical_url(target.get("source_url"))
    exclusion = f" -site:{urlsplit(source_url).hostname}" if source_url else ""
    return benchmark._compact(f"{core}{exclusion}")


def safe_target_price(item: Mapping[str, Any], fx: Mapping[str, float]) -> dict[str, Any]:
    details = benchmark._details(item)
    country = benchmark._compact(item.get("source_country")).upper()
    currency = benchmark._currency(details.get("currency"), country) or benchmark._COUNTRY_CURRENCY.get(country)
    basis = benchmark._target_basis(item)
    unit_amount = benchmark._number(details.get("unit_price"))
    source_field = "UNIT_PRICE" if unit_amount is not None else None
    quantity = benchmark._number(details.get("quantity"))
    total_amount = None
    total_field = None
    if unit_amount is None:
        for field in ("total_price", "current_bid", "price"):
            value = benchmark._number(details.get(field))
            if value is None:
                continue
            total_amount = value
            total_field = field.upper()
            if quantity and quantity > 0 and basis in {"PER_ITEM", "PER_KG", "PER_METRE"}:
                unit_amount = value / quantity
                source_field = total_field
            break
    nok = unit_amount * fx[currency] if unit_amount is not None and currency in fx else None
    return {
        "amount": round(unit_amount, 4) if unit_amount is not None else None,
        "currency": currency,
        "basis": basis,
        "amount_nok": round(nok, 4) if nok is not None else None,
        "source_field": source_field,
        "visible_total_amount": round(total_amount, 4) if total_amount is not None else None,
        "visible_total_field": total_field,
        "unit_price_requires_quantity": bool(total_amount is not None and unit_amount is None),
        "final_purchase_price": False,
    }


def _generic_actionable_count(
    brief: Mapping[str, Any],
    cases_report: Mapping[str, Any],
    items_report: Mapping[str, Any],
) -> int:
    cards = brief.get("actionable_now") if isinstance(brief.get("actionable_now"), list) else []
    cases = {
        benchmark._compact(case.get("case_id")): case
        for case in (cases_report.get("cases") or [])
        if isinstance(case, Mapping)
    }
    items = {
        benchmark._compact(item.get("intelligence_id")): item
        for item in (items_report.get("items") or [])
        if isinstance(item, Mapping)
    }
    count = 0
    for card in cards:
        if not isinstance(card, Mapping):
            continue
        case = cases.get(benchmark._compact(card.get("case_id")), {})
        ids = case.get("item_ids") if isinstance(case.get("item_ids"), list) else []
        candidates = [items.get(benchmark._compact(item_id)) for item_id in ids]
        candidates = [item for item in candidates if isinstance(item, Mapping)]
        if candidates and not any(_specific_product_target(item) for item in candidates):
            count += 1
    return count


def write_hydrated_market_comparables_benchmark(
    output_dir: Path,
    *,
    environment: Mapping[str, str] | None = None,
    provider_factory=benchmark._default_provider_factory,
    fx_rates_to_nok: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    """Run the existing writer with locally hydrated, quality-gated targets."""
    items_path = output_dir / "unified-intelligence-items.json"
    brief_path = output_dir / "unified-daily-decision-brief.json"
    cases_path = output_dir / "unified-market-cases.json"
    source_records = load_local_source_records(output_dir)
    original_items = _load_json(items_path)
    hydrated_items, provenance = hydrate_items_report(original_items, source_records)
    brief = _load_json(brief_path)
    cases = _load_json(cases_path)
    generic_skipped = _generic_actionable_count(brief, cases, hydrated_items)

    original_build = benchmark.build_market_comparables_benchmark
    original_select = benchmark.select_benchmark_targets
    original_query_core = benchmark._query_core
    original_target_price = benchmark._target_price

    def patched_build(**kwargs):
        kwargs["items_report"] = hydrated_items
        benchmark.select_benchmark_targets = select_quality_benchmark_targets
        benchmark._query_core = quality_query_core
        benchmark._target_price = safe_target_price
        try:
            report = original_build(**kwargs)
        finally:
            benchmark.select_benchmark_targets = original_select
            benchmark._query_core = original_query_core
            benchmark._target_price = original_target_price
        report["target_hydration_schema_version"] = SCHEMA_VERSION
        report["target_hydration_feed_family"] = FEED_FAMILY
        report["local_source_record_count"] = len(source_records)
        report["generic_actionable_targets_skipped"] = generic_skipped
        report["hydrated_item_count"] = sum(
            1 for value in provenance.values() if value.get("status") == "HYDRATED"
        )
        selected = {
            value.get("intelligence_id"): value
            for value in select_quality_benchmark_targets(
                brief, cases, hydrated_items, max_targets=benchmark.MAX_TARGETS
            )
        }
        for target in report.get("target_benchmarks") or []:
            if not isinstance(target, dict):
                continue
            item_id = benchmark._compact(target.get("intelligence_id"))
            target["target_hydration"] = provenance.get(
                item_id,
                {
                    "status": "NO_ADDITIONAL_FIELDS",
                    "fields_added": [],
                    "source_artifacts": [],
                    "matched_source_record_count": 0,
                },
            )
            target["query_quality"] = {
                "query_core": quality_query_core(selected.get(item_id, target)),
                "generic_company_title_rejected": False,
            }
        return report

    benchmark.build_market_comparables_benchmark = patched_build
    try:
        return benchmark.write_market_comparables_benchmark(
            output_dir,
            environment=environment,
            provider_factory=provider_factory,
            fx_rates_to_nok=fx_rates_to_nok,
        )
    finally:
        benchmark.build_market_comparables_benchmark = original_build
        benchmark.select_benchmark_targets = original_select
        benchmark._query_core = original_query_core
        benchmark._target_price = original_target_price
