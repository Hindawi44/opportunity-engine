"""Conservative enrichment of PS Auction candidates from public search snippets.

The enrichment extracts only facts explicitly visible in Brave snippets. It never
uses reference values as current sale prices and never changes an unresolved
listing into an active or Top-5 eligible opportunity.
"""
from __future__ import annotations

import html
import re
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Iterable, Mapping
from urllib.parse import urlsplit, urlunsplit


_TAG_RE = re.compile(r"<[^>]+>")
_NUMBER = r"(?P<number>\d{1,3}(?:[ .]\d{3})+|\d{1,7})"
_CONTAINER_RE = re.compile(
    rf"\b(?:ca\s*)?{_NUMBER}\s*(?P<unit>pall|kartonger?|krt)\b",
    re.I,
)
_ITEM_RE = re.compile(
    rf"\b(?P<prefix>ca|cirka|över|uppskattat(?:vis)?(?:\s+till)?\s+ca)?\s*"
    rf"{_NUMBER}\s*(?P<plus>\+)?\s*(?P<unit>plagg|artiklar|st|par)\b",
    re.I,
)
_HUNDREDS_RE = re.compile(r"\b100\s*tals?\s*(?P<unit>artiklar|plagg)\b", re.I)
_PER_CARTON_RE = re.compile(
    r"(?P<low>\d{1,4})\s*[-–]\s*(?P<high>\d{1,4})\s*plagg\s*/\s*kartong",
    re.I,
)
_RETAIL_VALUE_RE = re.compile(
    rf"\b(?:uppskattat\s+)?butikspris(?:et)?(?:\s+på|\s+om)?\s*{_NUMBER}",
    re.I,
)
_PURCHASE_VALUE_RE = re.compile(
    rf"\binköpsvärd(?:e|et)(?:\s+uppgår\s+till)?\s*{_NUMBER}",
    re.I,
)


@dataclass(frozen=True, slots=True)
class PSAuctionSnippetFacts:
    inventory_type: str | None = None
    quantity: int | None = None
    quantity_unit: str | None = None
    quantity_qualifier: str | None = None
    estimated_piece_count_min: int | None = None
    estimated_piece_count_max: int | None = None
    reference_value_sek: int | None = None
    reference_value_kind: str | None = None

    @property
    def has_quantity(self) -> bool:
        return self.quantity is not None or self.estimated_piece_count_min is not None

    @property
    def has_any_fact(self) -> bool:
        return bool(
            self.inventory_type
            or self.has_quantity
            or self.reference_value_sek is not None
        )


def _clean(value: str) -> str:
    value = html.unescape(value or "")
    value = _TAG_RE.sub(" ", value)
    return " ".join(value.casefold().split())


def _number(value: str) -> int:
    return int(re.sub(r"[^0-9]", "", value))


def _canonical_url(value: str) -> str:
    parts = urlsplit(value.strip())
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.casefold(), parts.netloc.casefold(), path, "", ""))


def _inventory_type(text: str) -> str | None:
    if "secondhand" in text and "damkläder" in text:
        return "sorted_second_hand_womens_clothing"
    if "mc kläder" in text or "mc-kläder" in text or "skoteroverall" in text:
        return "motorcycle_and_snowmobile_clothing"
    if "damkläder" in text or "masai" in text:
        return "womens_clothing"
    if "träningsutrustning" in text or "träningskläder" in text:
        return "training_clothing_and_accessories"
    if "sportbutik" in text or "sportkläder" in text:
        return "sportswear"
    if "arbetskläder" in text or "arbetsskor" in text:
        return "workwear_and_work_shoes"
    if "jeans" in text and "skor" in text:
        return "mixed_clothing_and_footwear"
    if any(term in text for term in ("kläder", "plagg", "textil")):
        return "mixed_clothing_inventory"
    if "skor" in text:
        return "footwear_inventory"
    return None


def extract_psauction_snippet_facts(value: str) -> PSAuctionSnippetFacts:
    """Extract explicit commercial facts without inferring an active sale."""
    text = _clean(value)
    inventory_type = _inventory_type(text)

    quantity: int | None = None
    quantity_unit: str | None = None
    qualifier: str | None = None
    estimated_min: int | None = None
    estimated_max: int | None = None

    container = _CONTAINER_RE.search(text)
    if container:
        quantity = _number(container.group("number"))
        raw_unit = container.group("unit").casefold()
        quantity_unit = "pallets" if raw_unit == "pall" else "cartons"
        qualifier = "approximate" if "ca " in container.group(0).casefold() else "explicit"
        per_carton = _PER_CARTON_RE.search(text)
        if quantity_unit == "cartons" and per_carton:
            low = int(per_carton.group("low"))
            high = int(per_carton.group("high"))
            estimated_min = quantity * low
            estimated_max = quantity * high
    else:
        hundreds = _HUNDREDS_RE.search(text)
        if hundreds:
            quantity = 100
            quantity_unit = "articles" if "artiklar" in hundreds.group("unit") else "garments"
            qualifier = "minimum"
        else:
            item = _ITEM_RE.search(text)
            if item:
                quantity = _number(item.group("number"))
                raw_unit = item.group("unit").casefold()
                if raw_unit == "plagg":
                    quantity_unit = "garments"
                elif raw_unit == "artiklar":
                    quantity_unit = "articles"
                elif raw_unit == "par":
                    quantity_unit = "pairs"
                else:
                    quantity_unit = "items"
                prefix = (item.group("prefix") or "").casefold()
                qualifier = "minimum" if item.group("plus") or "över" in prefix else (
                    "approximate" if prefix else "explicit"
                )

    reference_value: int | None = None
    reference_kind: str | None = None
    retail = _RETAIL_VALUE_RE.search(text)
    purchase = _PURCHASE_VALUE_RE.search(text)
    if retail:
        reference_value = _number(retail.group("number"))
        reference_kind = "estimated_retail_value"
    elif purchase:
        reference_value = _number(purchase.group("number"))
        reference_kind = "original_purchase_value"

    return PSAuctionSnippetFacts(
        inventory_type=inventory_type,
        quantity=quantity,
        quantity_unit=quantity_unit,
        quantity_qualifier=qualifier,
        estimated_piece_count_min=estimated_min,
        estimated_piece_count_max=estimated_max,
        reference_value_sek=reference_value,
        reference_value_kind=reference_kind,
    )


def _fact_text(facts: PSAuctionSnippetFacts) -> list[str]:
    values: list[str] = []
    if facts.quantity is not None and facts.quantity_unit:
        qualifier = f" ({facts.quantity_qualifier})" if facts.quantity_qualifier else ""
        values.append(
            f"search snippet quantity: {facts.quantity} {facts.quantity_unit}{qualifier}"
        )
    if facts.estimated_piece_count_min is not None:
        if facts.estimated_piece_count_max is not None:
            values.append(
                "search snippet estimated garment range: "
                f"{facts.estimated_piece_count_min}-{facts.estimated_piece_count_max}"
            )
        else:
            values.append(
                "search snippet estimated garment minimum: "
                f"{facts.estimated_piece_count_min}"
            )
    if facts.reference_value_sek is not None and facts.reference_value_kind:
        values.append(
            "search snippet reference value: "
            f"{facts.reference_value_sek} SEK ({facts.reference_value_kind}; not current sale price)"
        )
    return values


def _enrich_candidate(
    candidate: dict[str, Any],
    samples_by_url: Mapping[str, list[Mapping[str, Any]]],
) -> tuple[bool, bool, bool, bool]:
    matched_samples: list[Mapping[str, Any]] = []
    for url in candidate.get("source_urls") or ():
        matched_samples.extend(samples_by_url.get(_canonical_url(str(url)), ()))
    if not matched_samples:
        return False, False, False, False

    combined = " ".join(
        str(value)
        for sample in matched_samples
        for value in (sample.get("title"), sample.get("description"))
        if value
    )
    facts = extract_psauction_snippet_facts(combined)
    if not facts.has_any_fact:
        return False, False, False, False

    if facts.inventory_type and not candidate.get("inventory_type"):
        candidate["inventory_type"] = facts.inventory_type
    if facts.quantity is not None and candidate.get("quantity") is None:
        candidate["quantity"] = facts.quantity
    if facts.quantity_unit:
        candidate["quantity_unit"] = facts.quantity_unit
    if facts.quantity_qualifier:
        candidate["quantity_qualifier"] = facts.quantity_qualifier
    if facts.estimated_piece_count_min is not None:
        candidate["estimated_piece_count_min"] = facts.estimated_piece_count_min
    if facts.estimated_piece_count_max is not None:
        candidate["estimated_piece_count_max"] = facts.estimated_piece_count_max
    if facts.reference_value_sek is not None:
        candidate["reference_value_sek"] = facts.reference_value_sek
        candidate["reference_value_kind"] = facts.reference_value_kind
        candidate["reference_value_is_current_sale_price"] = False

    missing = list(candidate.get("missing_information") or ())
    if facts.has_quantity:
        missing = [item for item in missing if item != "quantity"]
    candidate["missing_information"] = missing

    confirmed = list(candidate.get("confirmed_information") or ())
    for item in _fact_text(facts):
        if item not in confirmed:
            confirmed.append(item)
    candidate["confirmed_information"] = confirmed

    breakdown = dict(candidate.get("score_breakdown") or {})
    if facts.inventory_type:
        breakdown["clothing_inventory_clarity"] = max(
            20, int(breakdown.get("clothing_inventory_clarity", 0))
        )
    if facts.has_quantity or facts.reference_value_sek is not None:
        breakdown["price_or_quantity"] = max(
            5, int(breakdown.get("price_or_quantity", 0))
        )
    candidate["score_breakdown"] = breakdown
    candidate["discovery_score"] = min(100, sum(int(value) for value in breakdown.values()))

    duplicate_observations = max(0, len(matched_samples) - len({
        _canonical_url(str(sample.get("canonical_url") or sample.get("url") or ""))
        for sample in matched_samples
    }))
    query_duplicates = max(0, len(candidate.get("found_by_queries") or ()) - 1)
    old_duplicate_count = int(candidate.get("duplicate_count") or 0)
    corrected_duplicate_count = max(
        old_duplicate_count, duplicate_observations, query_duplicates
    )
    candidate["duplicate_count"] = corrected_duplicate_count

    return (
        True,
        facts.has_quantity,
        facts.reference_value_sek is not None,
        corrected_duplicate_count > old_duplicate_count,
    )


def enrich_psauction_discovery_result(
    result: Mapping[str, Any],
    accepted_samples: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Return an enriched result while preserving lifecycle and hard-gate fields."""
    enriched = deepcopy(dict(result))
    samples_by_url: dict[str, list[Mapping[str, Any]]] = {}
    for sample in accepted_samples:
        url = str(sample.get("canonical_url") or sample.get("url") or "").strip()
        if not url:
            continue
        samples_by_url.setdefault(_canonical_url(url), []).append(sample)

    candidates_enriched = 0
    quantities_extracted = 0
    reference_values_extracted = 0
    duplicate_counts_corrected = 0
    for key in ("all_discovered_candidates", "discovery_top5"):
        for candidate in enriched.get(key) or ():
            changed, quantity, reference, duplicate = _enrich_candidate(
                candidate, samples_by_url
            )
            candidates_enriched += int(changed and key == "all_discovered_candidates")
            quantities_extracted += int(quantity and key == "all_discovered_candidates")
            reference_values_extracted += int(reference and key == "all_discovered_candidates")
            duplicate_counts_corrected += int(duplicate and key == "all_discovered_candidates")

    report = enriched.get("search_run_report")
    if isinstance(report, dict):
        report["source_snippet_enrichment"] = {
            "source": "PS_AUCTION",
            "accepted_samples_used": sum(len(values) for values in samples_by_url.values()),
            "candidates_enriched": candidates_enriched,
            "quantities_extracted": quantities_extracted,
            "reference_values_extracted": reference_values_extracted,
            "duplicate_counts_corrected": duplicate_counts_corrected,
            "listing_status_changed": False,
            "top5_eligibility_changed": False,
            "reference_values_used_as_sale_prices": False,
        }
    return enriched
