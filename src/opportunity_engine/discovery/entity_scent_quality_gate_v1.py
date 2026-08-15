"""Entity-first quality gate for cross-source market scents.

The cross-source search can discover both genuine company events and generic market
pages. This gate identifies a concrete company/brand identity, clusters multiple
pieces of evidence about the same entity, and keeps generic source-intelligence
pages out of the scarce follow-up request budget.

The gate is deliberately advisory. It never promotes a signal to an opportunity.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from urllib.parse import urlparse
import re
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "entity-scent-quality-gate-v1-1.0"
ENGINE_VERSION = "ENTITY_SCENT_QUALITY_GATE_V1"
MIN_QUALIFIED_ENTITY_SCORE = 55

_LEGAL_MARKERS = {
    "DE": ("GmbH", "AG", "KG", "UG", "GmbH & Co. KG", "e.K."),
    "SE": ("AB",),
}

_GENERIC_PREFIX_PATTERNS = (
    r"firmeninsolvenz",
    r"insolvenz(?:verfahren)?(?:\s+der|\s+von)?",
    r"konkurs(?:bo)?(?:\s+för)?",
    r"handel",
    r"modekette",
    r"modehaus",
    r"fashion",
    r"news",
)

_GENERIC_PAGE_PREFIXES = (
    "ankauf ",
    "ankauf von ",
    "insolvenzware ",
    "restposten ",
    "restlager ",
    "warenbestand ",
    "warenarten ",
    "was sind ",
    "was ist ",
    "wie ",
    "verkauf von ",
    "utförsäljning ",
    "utforsaljning ",
    "lagerrensning ",
)

_GENERIC_PAGE_TERMS = (
    "aufkäufer",
    "aufkaeufer",
    "restposten verkaufen",
    "insolvenzware ankauf",
    "einfach erklärt",
    "einfach erklaert",
    "warenarten",
    "ankauf von marken-schuhen",
)

_EVENT_SUFFIXES = {
    "DE": (
        "insolvenz",
        "insolvent",
        "insolvenzverfahren",
        "geschäftsaufgabe",
        "geschaeftsaufgabe",
        "lagerauflösung",
        "lageraufloesung",
        "räumungsverkauf",
        "raeumungsverkauf",
        "versteigerung",
        "auktion",
    ),
    "SE": (
        "i konkurs",
        "konkurs",
        "konkursbo",
        "avveckling",
        "likvidation",
        "utförsäljning",
        "utforsaljning",
        "auktion",
    ),
}


@dataclass(frozen=True, slots=True)
class EntityAssessment:
    market_code: str
    entity_label: str | None
    entity_key: str | None
    is_concrete_entity: bool
    entity_shape: str
    rejection_reason: str | None


def _compact(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _normalize_label(value: str) -> str:
    text = _compact(value)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" -–—|:,.;")


def _strip_leading_context(text: str) -> str:
    value = text
    # News sites often prepend a section label before the actual company name.
    value = re.sub(
        r"^(?:handel|wirtschaft|news|fashion|mode)\s*:\s*",
        "",
        value,
        flags=re.IGNORECASE,
    )
    prefix_union = "|".join(_GENERIC_PREFIX_PATTERNS)
    while True:
        cleaned = re.sub(
            rf"^(?:{prefix_union})\s*[:\-–—]?\s*",
            "",
            value,
            count=1,
            flags=re.IGNORECASE,
        )
        if cleaned == value:
            break
        value = cleaned
    return _normalize_label(value)


def _strip_event_suffix(text: str, market_code: str) -> str:
    value = text
    suffixes = sorted(_EVENT_SUFFIXES[market_code], key=len, reverse=True)
    union = "|".join(re.escape(item) for item in suffixes)
    value = re.sub(
        rf"\s*(?:[.:\-–—]\s*)?(?:{union})\b.*$",
        "",
        value,
        flags=re.IGNORECASE,
    )
    return _normalize_label(value)


def _looks_generic(value: str) -> bool:
    folded = _compact(value).casefold()
    if not folded:
        return True
    if any(folded.startswith(prefix) for prefix in _GENERIC_PAGE_PREFIXES):
        return True
    if any(term in folded for term in _GENERIC_PAGE_TERMS):
        return True
    if folded in {"handel", "mode", "fashion", "textil", "bekleidung", "kläder", "klader", "skor"}:
        return True
    return False


def _entity_key(label: str) -> str:
    folded = label.casefold()
    folded = folded.replace("&amp;", "&")
    folded = re.sub(r"\b(?:gmbh|ag|kg|ug|ab|e\.?k\.?)\b", " ", folded)
    folded = re.sub(r"[^a-z0-9äöüåæøéèáàíìóòúùß&]+", " ", folded)
    folded = re.sub(r"\s+", " ", folded).strip()
    return folded


def _legal_marker_candidate(text: str, market_code: str) -> str | None:
    markers = sorted(_LEGAL_MARKERS[market_code], key=len, reverse=True)
    union = "|".join(re.escape(marker) for marker in markers)
    # Bound the left side so a whole article headline is not swallowed.
    match = re.search(
        rf"([A-ZÄÖÜÅÆØÉÈÁÀÍÌÓÒÚÙ][^|–—:!?]{{1,85}}?\b(?:{union})\b)",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    return _normalize_label(_strip_leading_context(match.group(1)))


def _ampersand_company_candidate(text: str) -> str | None:
    match = re.search(
        r"([A-ZÄÖÜÅÆØÉÈÁÀÍÌÓÒÚÙ][A-Za-zÀ-ÖØ-öø-ÿ0-9.'’\-]*(?:\s+[A-ZÄÖÜÅÆØÉÈÁÀÍÌÓÒÚÙ][A-Za-zÀ-ÖØ-öø-ÿ0-9.'’\-]*){0,4}\s+&\s+Co\.?)",
        text,
        flags=re.IGNORECASE,
    )
    return _normalize_label(match.group(1)) if match else None


def extract_entity_label(title: str, market_code: str) -> EntityAssessment:
    market = market_code.upper()
    if market not in _LEGAL_MARKERS:
        raise ValueError(f"Unsupported market: {market_code}")

    text = _normalize_label(title)
    if not text:
        return EntityAssessment(market, None, None, False, "NONE", "EMPTY_TITLE")

    contextual = _strip_leading_context(text)
    candidate = _legal_marker_candidate(contextual, market)
    entity_shape = "LEGAL_MARKER" if candidate else "NONE"

    if candidate is None:
        candidate = _ampersand_company_candidate(contextual)
        if candidate:
            entity_shape = "AMPERSAND_COMPANY"

    if candidate is None:
        # Fall back to the headline segment before the event phrase. This allows
        # brands without a legal suffix while the generic-page guard stays strict.
        first_segment = re.split(r"\s+[|–—]\s+", contextual, maxsplit=1)[0]
        candidate = _strip_event_suffix(first_segment, market)
        candidate = _strip_leading_context(candidate)
        if candidate:
            entity_shape = "HEADLINE_ENTITY"

    candidate = _normalize_label(candidate or "")
    candidate = _strip_event_suffix(candidate, market)
    candidate = _strip_leading_context(candidate)

    if not candidate:
        return EntityAssessment(market, None, None, False, entity_shape, "NO_ENTITY_LABEL")
    if len(candidate) < 2 or len(candidate) > 100:
        return EntityAssessment(market, None, None, False, entity_shape, "IMPLAUSIBLE_ENTITY_LENGTH")
    if _looks_generic(candidate):
        return EntityAssessment(market, None, None, False, entity_shape, "GENERIC_SOURCE_INTELLIGENCE")

    key = _entity_key(candidate)
    if len(key) < 2:
        return EntityAssessment(market, None, None, False, entity_shape, "EMPTY_ENTITY_KEY")

    return EntityAssessment(market, candidate, key, True, entity_shape, None)


def _domain(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").casefold().removeprefix("www.")
    except Exception:
        return ""


def build_entity_scent_quality_gate(
    candidates: Sequence[Mapping[str, Any]],
    *,
    min_qualified_score: int = MIN_QUALIFIED_ENTITY_SCORE,
) -> dict[str, Any]:
    """Classify and cluster raw scent candidates around concrete entities."""
    clusters: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    source_intelligence: list[dict[str, Any]] = []

    for raw in candidates:
        market = _compact(raw.get("market_code")).upper()
        title = _compact(raw.get("source_title")) or _compact(raw.get("label"))
        assessment = extract_entity_label(title, market)
        payload = dict(raw)
        payload.update(
            {
                "entity_label": assessment.entity_label,
                "entity_key": assessment.entity_key,
                "entity_shape": assessment.entity_shape,
                "entity_quality_gate": ENGINE_VERSION,
            }
        )
        if not assessment.is_concrete_entity or not assessment.entity_key:
            payload["classification"] = "SOURCE_INTELLIGENCE"
            payload["rejection_reason"] = assessment.rejection_reason
            source_intelligence.append(payload)
            continue
        payload["classification"] = "ENTITY_SCENT"
        clusters[(market, assessment.entity_key)].append(payload)

    entity_scents: list[dict[str, Any]] = []
    for (market, key), evidence in clusters.items():
        evidence = sorted(
            evidence,
            key=lambda item: (-int(item.get("score") or 0), _compact(item.get("source_url"))),
        )
        best = evidence[0]
        labels = [_compact(item.get("entity_label")) for item in evidence if _compact(item.get("entity_label"))]
        label = min(labels, key=len) if labels else _compact(best.get("label"))
        domains = {_domain(_compact(item.get("source_url"))) for item in evidence}
        domains.discard("")
        base_score = max(int(item.get("score") or 0) for item in evidence)
        shape_bonus = 10 if any(item.get("entity_shape") in {"LEGAL_MARKER", "AMPERSAND_COMPANY"} for item in evidence) else 5
        evidence_bonus = min(30, max(0, len(evidence) - 1) * 10)
        domain_bonus = min(15, max(0, len(domains) - 1) * 5)
        entity_score = min(100, base_score + shape_bonus + evidence_bonus + domain_bonus)
        entity_scents.append(
            {
                "market_code": market,
                "label": label,
                "entity_key": key,
                "score": entity_score,
                "base_score": base_score,
                "entity_shape": best.get("entity_shape"),
                "evidence_count": len(evidence),
                "independent_source_count": len(domains),
                "source_url": best.get("source_url"),
                "source_title": best.get("source_title"),
                "parent_query_id": best.get("parent_query_id"),
                "evidence": [
                    {
                        "source_url": item.get("source_url"),
                        "source_title": item.get("source_title"),
                        "parent_query_id": item.get("parent_query_id"),
                        "raw_score": int(item.get("score") or 0),
                    }
                    for item in evidence
                ],
                "qualified_for_follow_up": entity_score >= min_qualified_score,
                "entity_quality_gate": ENGINE_VERSION,
            }
        )

    entity_scents.sort(
        key=lambda item: (
            not bool(item["qualified_for_follow_up"]),
            -int(item["score"]),
            -int(item["independent_source_count"]),
            0 if item["market_code"] == "DE" else 1,
            _compact(item["label"]).casefold(),
        )
    )
    qualified = [item for item in entity_scents if item["qualified_for_follow_up"]]

    return {
        "schema_version": SCHEMA_VERSION,
        "engine_version": ENGINE_VERSION,
        "candidate_count": len(candidates),
        "entity_cluster_count": len(entity_scents),
        "qualified_entity_count": len(qualified),
        "source_intelligence_count": len(source_intelligence),
        "entity_scents": entity_scents,
        "qualified_entity_scents": qualified,
        "source_intelligence": source_intelligence,
        "promotion_to_opportunity_allowed": False,
        "top5_eligible": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }
