"""Conservative enrichment of PS Auction candidates from public search snippets.

The enrichment extracts only facts explicitly visible in Brave snippets. It never
uses reference values as current sale prices and never changes an unresolved
listing into an active or Top-5 eligible opportunity. Source-wide PS Auction
boilerplate is excluded from event classification so generic references to
bankruptcy auctions cannot turn every retained item into a bankruptcy lead.
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
    rf"\b(?P<prefix>ca|cirka|över|uppskattningsvis|uppskattat(?:\s+till)?\s+ca)?\s*"
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

_GENERIC_SEGMENT_TERMS = (
    "auktionsexperter med fokus på konkurser",
    "nätauktioner varje dag",
    "fynd & förnuft",
    "hållbar konsumtion",
    "om auktionen avslutas utan att reservationspriset uppnåtts",
    "buden är bindande och serviceavgiften debiteras på alla objekt",
    "klimatavtrycket för ett motsvarande nyproducerat objekt",
)
_BANKRUPTCY_PHRASES = (
    "tillhör ett konkursbo",
    "objektet tillhör ett konkursbo",
    "tvångsförsäljning då objektet tillhör ett konkursbo",
    "säljes i uppdrag av konkursförvaltare",
    "säljs i uppdrag av konkursförvaltare",
    "på uppdrag av konkursförvaltare",
)
_EVENT_SCORES = {
    "COMPANY_BANKRUPTCY": 25,
    "STORE_CLOSING": 23,
    "INVENTORY_LIQUIDATION": 22,
    "WAREHOUSE_SURPLUS": 18,
    "LARGE_LOT_SALE": 16,
}
_UNSCOPED_SOURCE_SIGNALS = {
    "konkursbo",
    "konkurs",
    "auksjon",
    "nettauksjon",
    "opphørssalg",
    "selges",
    "restlager",
    "overskuddslager",
    "vareparti",
    "klesparti",
}
_EVENT_SIGNALS = {
    "COMPANY_BANKRUPTCY": ("konkursbo", "konkurs"),
    "STORE_CLOSING": ("butikk stenger",),
    "INVENTORY_LIQUIDATION": ("lageravvikling",),
    "WAREHOUSE_SURPLUS": ("restlager",),
    "LARGE_LOT_SALE": ("vareparti",),
}


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


@dataclass(frozen=True, slots=True)
class _CandidateEnrichment:
    changed: bool = False
    quantity_extracted: bool = False
    reference_value_extracted: bool = False
    duplicate_count_corrected: bool = False
    scenario_corrected: bool = False
    inventory_type_corrected: bool = False
    source_signals_cleaned: bool = False


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


def _item_title(value: str) -> str:
    title = _clean(value)
    for marker in (
        " - auktioner online",
        " | ps auction",
    ):
        if marker in title:
            title = title.split(marker, 1)[0]
    return title


def _source_scoped_text(samples: Iterable[Mapping[str, Any]]) -> str:
    """Keep item title and item-specific snippet segments, not site boilerplate."""
    values: list[str] = []
    for sample in samples:
        title = _item_title(str(sample.get("title") or ""))
        if title:
            values.append(title)
        description = html.unescape(str(sample.get("description") or ""))
        for raw_segment in description.split("|"):
            segment = _clean(raw_segment)
            if not segment:
                continue
            if any(term in segment for term in _GENERIC_SEGMENT_TERMS):
                continue
            values.append(segment)
    return " ".join(dict.fromkeys(values))


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
    if "jeans" in text and ("skor" in text or "arbetsskor" in text):
        return "mixed_clothing_and_footwear"
    if "arbetskläder" in text or "arbetsskor" in text:
        return "workwear_and_work_shoes"
    if any(term in text for term in ("kläder", "plagg", "textil")):
        return "mixed_clothing_inventory"
    if "skor" in text:
        return "footwear_inventory"
    return None


def _source_scenario(text: str) -> str:
    if any(phrase in text for phrase in _BANKRUPTCY_PHRASES):
        return "COMPANY_BANKRUPTCY"
    if any(
        phrase in text
        for phrase in ("butik stänger", "butiken stänger", "läggs ned")
    ):
        return "STORE_CLOSING"
    if any(
        phrase in text
        for phrase in ("lager rensas", "lageravveckling", "likvidation")
    ):
        return "INVENTORY_LIQUIDATION"
    if any(
        phrase in text
        for phrase in ("restparti", "restlager", "överskottslager")
    ):
        return "WAREHOUSE_SURPLUS"
    return "LARGE_LOT_SALE"


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


def _replace_event_reason(values: Iterable[str], scenario: str) -> list[str]:
    replacement = f"source-scoped commercial event detected: {scenario}"
    result = [
        value
        for value in values
        if not value.startswith("commercial event detected:")
        and not value.startswith("source-scoped commercial event detected:")
    ]
    return [replacement, *result]


def _enrich_candidate(
    candidate: dict[str, Any],
    samples_by_url: Mapping[str, list[Mapping[str, Any]]],
) -> _CandidateEnrichment:
    matched_samples: list[Mapping[str, Any]] = []
    for url in candidate.get("source_urls") or ():
        matched_samples.extend(samples_by_url.get(_canonical_url(str(url)), ()))
    if not matched_samples:
        return _CandidateEnrichment()

    scoped_text = _source_scoped_text(matched_samples)
    facts = extract_psauction_snippet_facts(scoped_text)
    scenario = _source_scenario(scoped_text)
    if not facts.has_any_fact:
        return _CandidateEnrichment()

    old_inventory_type = candidate.get("inventory_type")
    inventory_type_corrected = bool(
        facts.inventory_type and facts.inventory_type != old_inventory_type
    )
    if facts.inventory_type:
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

    confirmed = [
        item
        for item in (candidate.get("confirmed_information") or ())
        if not str(item).startswith("source-scoped commercial event:")
    ]
    for item in _fact_text(facts):
        if item not in confirmed:
            confirmed.append(item)
    confirmed.append(f"source-scoped commercial event: {scenario}")
    candidate["confirmed_information"] = confirmed

    old_scenario = str(candidate.get("scenario") or "")
    scenario_corrected = old_scenario != scenario
    candidate["scenario"] = scenario
    candidate["why_opportunity"] = _replace_event_reason(
        [str(item) for item in candidate.get("why_opportunity") or ()],
        scenario,
    )

    old_signals = [str(item) for item in candidate.get("evidence_signals") or ()]
    cleaned_signals = [
        item for item in old_signals if item not in _UNSCOPED_SOURCE_SIGNALS
    ]
    for signal in _EVENT_SIGNALS[scenario]:
        if signal not in cleaned_signals:
            cleaned_signals.append(signal)
    if "säljes" in scoped_text and "selges" not in cleaned_signals:
        cleaned_signals.append("selges")
    source_signals_cleaned = cleaned_signals != old_signals
    candidate["evidence_signals"] = cleaned_signals

    breakdown = dict(candidate.get("score_breakdown") or {})
    breakdown["commercial_event_strength"] = _EVENT_SCORES[scenario]
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
    candidate["discovery_band"] = (
        "HIGH" if candidate["discovery_score"] >= 80
        else "REVIEW" if candidate["discovery_score"] >= 55
        else "LOW"
    )

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

    return _CandidateEnrichment(
        changed=True,
        quantity_extracted=facts.has_quantity,
        reference_value_extracted=facts.reference_value_sek is not None,
        duplicate_count_corrected=corrected_duplicate_count > old_duplicate_count,
        scenario_corrected=scenario_corrected,
        inventory_type_corrected=inventory_type_corrected,
        source_signals_cleaned=source_signals_cleaned,
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

    counters = {
        "candidates_enriched": 0,
        "quantities_extracted": 0,
        "reference_values_extracted": 0,
        "duplicate_counts_corrected": 0,
        "scenarios_corrected": 0,
        "inventory_types_corrected": 0,
        "source_event_signals_cleaned": 0,
    }
    for key in ("all_discovered_candidates", "discovery_top5"):
        for candidate in enriched.get(key) or ():
            outcome = _enrich_candidate(candidate, samples_by_url)
            if key != "all_discovered_candidates":
                continue
            counters["candidates_enriched"] += int(outcome.changed)
            counters["quantities_extracted"] += int(outcome.quantity_extracted)
            counters["reference_values_extracted"] += int(
                outcome.reference_value_extracted
            )
            counters["duplicate_counts_corrected"] += int(
                outcome.duplicate_count_corrected
            )
            counters["scenarios_corrected"] += int(outcome.scenario_corrected)
            counters["inventory_types_corrected"] += int(
                outcome.inventory_type_corrected
            )
            counters["source_event_signals_cleaned"] += int(
                outcome.source_signals_cleaned
            )

    report = enriched.get("search_run_report")
    if isinstance(report, dict):
        report["source_snippet_enrichment"] = {
            "source": "PS_AUCTION",
            "accepted_samples_used": sum(len(values) for values in samples_by_url.values()),
            **counters,
            "event_classification_scope": "item_title_and_item_specific_snippet_only",
            "source_boilerplate_used_for_event_classification": False,
            "listing_status_changed": False,
            "top5_eligibility_changed": False,
            "reference_values_used_as_sale_prices": False,
        }
    return enriched
