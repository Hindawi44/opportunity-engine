"""Unify existing market-intelligence artifacts into one decision river.

The river is a read-only projection over artifacts already produced by the
established collectors. It does not fetch pages, mutate persistence, promote
signals into opportunities, or perform any commercial action.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from enum import StrEnum
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urlsplit, urlunsplit

SCHEMA_VERSION = "unified-market-intelligence-river-1.0"
ITEMS_SCHEMA_VERSION = "unified-intelligence-items-1.0"
CASES_SCHEMA_VERSION = "unified-market-cases-1.0"
BRIEF_SCHEMA_VERSION = "unified-daily-decision-brief-1.0"
DECISION_OWNER = "HUMAN_OPERATOR"

ITEMS_FILENAME = "unified-intelligence-items.json"
CASES_FILENAME = "unified-market-cases.json"
BRIEF_FILENAME = "unified-daily-decision-brief.json"

INPUT_ARTIFACTS = (
    "domain-market-intelligence-brief.json",
    "brave-market-signal-radar.json",
    "bridal-liquidation-feed.json",
    "fabric-procurement-watch.json",
    "merkandi-b2b-liquidation-feed.json",
    "fashion-stock-netherlands-feed.json",
    "stockhurt-b2b-feed.json",
    "stockhurt-official-catalog-enrichment.json",
    "jobalots-clothing-auction-feed.json",
    "jobalots-official-page-enrichment.json",
    "jobalots-official-catalog-discovery.json",
)


class IntelligenceRecordKind(StrEnum):
    MARKET_SIGNAL = "MARKET_SIGNAL"
    BUSINESS_EVENT_SIGNAL = "BUSINESS_EVENT_SIGNAL"
    B2B_STOCK_OFFER = "B2B_STOCK_OFFER"
    AUCTION_LOT = "AUCTION_LOT"
    BRIDAL_LIQUIDATION_SIGNAL = "BRIDAL_LIQUIDATION_SIGNAL"
    FABRIC_PROCUREMENT_ITEM = "FABRIC_PROCUREMENT_ITEM"
    CANONICAL_OPPORTUNITY = "CANONICAL_OPPORTUNITY"
    HISTORICAL_EVIDENCE = "HISTORICAL_EVIDENCE"


class MarketCaseType(StrEnum):
    COMPANY_LIQUIDATION = "COMPANY_LIQUIDATION"
    B2B_INVENTORY = "B2B_INVENTORY"
    AUCTION_INVENTORY = "AUCTION_INVENTORY"
    BRIDAL_LIQUIDATION = "BRIDAL_LIQUIDATION"
    FABRIC_PROCUREMENT = "FABRIC_PROCUREMENT"
    DIRECT_OPPORTUNITY = "DIRECT_OPPORTUNITY"
    MARKET_SIGNAL_WATCH = "MARKET_SIGNAL_WATCH"
    HISTORICAL_MARKET_EVIDENCE = "HISTORICAL_MARKET_EVIDENCE"


class RelationshipType(StrEnum):
    SUPPORTS = "SUPPORTS"
    SAME_ORGANISATION_NUMBER = "SAME_ORGANISATION_NUMBER"
    SAME_COMPANY = "SAME_COMPANY"
    SAME_SELLER = "SAME_SELLER"
    SAME_AUCTION = "SAME_AUCTION"
    SAME_MARKET_CASE = "SAME_MARKET_CASE"


_SIGNAL_EVENT_TYPES = {
    "BUSINESS_CLOSURE",
    "INSOLVENCY_OR_LIQUIDATION",
}
_HISTORICAL_LISTING_STATUSES = {
    "ENDED",
    "SOLD",
    "UNAVAILABLE",
    "OUT_OF_STOCK",
    "CLOSED",
}
_B2B_FEED_FAMILIES = {
    "MERKANDI_B2B_LIQUIDATION_FEED_V1",
    "FASHION_STOCK_NETHERLANDS_FEED_V1",
    "STOCK_HURT_B2B_FEED_V1",
    "STOCKHURT_OFFICIAL_CATALOG_ENRICHMENT_V1",
}
_AUCTION_FEED_FAMILIES = {
    "JOBALOTS_CLOTHING_LIQUIDATION_AUCTION_FEED_V1",
    "B2B_OFFICIAL_PAGE_ENRICHMENT_V1",
    "JOBALOTS_OFFICIAL_CATALOG_DISCOVERY_V1",
}


def _compact(value: object) -> str:
    return " ".join(str(value or "").split())


def _normalise_token(value: object) -> str:
    compact = _compact(value).casefold()
    compact = re.sub(r"[^a-z0-9à-öø-ÿ]+", "-", compact)
    return compact.strip("-")


def _hash(prefix: str, value: str) -> str:
    return f"{prefix}:{sha256(value.encode('utf-8')).hexdigest()[:24]}"


def _canonical_url(value: object) -> str | None:
    raw = _compact(value)
    if not raw:
        return None
    try:
        parts = urlsplit(raw)
    except ValueError:
        return None
    if parts.scheme.casefold() not in {"http", "https"} or not parts.hostname:
        return None
    host = parts.hostname.casefold().rstrip(".")
    try:
        port = parts.port
    except ValueError:
        return None
    netloc = host if port is None else f"{host}:{port}"
    path = re.sub(r"/{2,}", "/", parts.path or "/")
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit((parts.scheme.casefold(), netloc, path, "", ""))


def _iso(value: object, *, fallback: datetime | None = None) -> str:
    text = _compact(value)
    if text:
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if parsed.tzinfo is None or parsed.utcoffset() is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc).isoformat()
        except ValueError:
            pass
    current = fallback or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc).isoformat()


def _number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _score(*values: object) -> float:
    for value in values:
        number = _number(value)
        if number is not None:
            return max(0.0, min(100.0, number * 100.0 if 0 <= number <= 1 else number))
    return 0.0


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        if isinstance(item, Mapping):
            text = _compact(item.get("field_name") or item.get("field") or item.get("name"))
        else:
            text = _compact(item)
        if text:
            result.append(text.upper())
    return sorted(set(result))


def _evidence(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, Mapping):
            continue
        source_url = _canonical_url(item.get("source_url"))
        field = _compact(item.get("field") or item.get("evidence_type") or "SOURCE_EVIDENCE")
        page_hash = _compact(item.get("page_sha256"))
        key = json.dumps([field, source_url, page_hash, item.get("value")], sort_keys=True, default=str)
        if key in seen:
            continue
        seen.add(key)
        result.append(
            {
                "evidence_type": field,
                "source_url": source_url,
                "page_sha256": page_hash or None,
                "verified": item.get("verified") is True,
                "captured_at": item.get("captured_at"),
                "value": _compact(item.get("value"))[:2000] or None,
                "metadata": dict(item.get("metadata") or {}) if isinstance(item.get("metadata"), Mapping) else {},
            }
        )
    return result


def _selected_details(record: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "signal_type",
        "event_date",
        "related_opportunity_id",
        "opportunity_identity",
        "related_signal_id",
        "feed_family",
        "source_reference",
        "page_role",
        "sale_mode",
        "inventory_focus",
        "quantity",
        "quantity_unit",
        "lot_units",
        "lot_unit_type",
        "lot_size_band",
        "minimum_order",
        "minimum_order_unit",
        "unit_hint",
        "unit_price",
        "total_price",
        "current_bid",
        "price",
        "price_text",
        "price_basis",
        "currency",
        "estimated_retail_value",
        "estimated_retail_currency",
        "reserve_price",
        "reserve_currency",
        "weight_kg",
        "grade",
        "brands",
        "fabric_terms",
        "bridal_terms",
        "manifest_available",
        "manifest_urls",
        "stock_location",
        "auction_end_text",
        "organisation_number",
        "recommended_operator_action",
        "verification_status",
        "discovery_method",
        "catalog_scope",
        "source_kind",
        "inventory_type",
    )
    details = {key: record.get(key) for key in keys if record.get(key) is not None}
    metadata = record.get("metadata")
    if isinstance(metadata, Mapping):
        details["metadata"] = dict(metadata)
    description = _compact(record.get("description") or record.get("value"))
    if description:
        details["description"] = description[:2000]
    return details


def _organisation_number(record: Mapping[str, Any]) -> str | None:
    candidates: list[object] = [record.get("organisation_number")]
    metadata = record.get("metadata")
    if isinstance(metadata, Mapping):
        candidates.extend(
            [metadata.get("organisation_number"), metadata.get("organization_number")]
        )
    details = record.get("details")
    if isinstance(details, Mapping):
        candidates.append(details.get("organisation_number"))
        nested = details.get("metadata")
        if isinstance(nested, Mapping):
            candidates.extend(
                [nested.get("organisation_number"), nested.get("organization_number")]
            )
    for value in candidates:
        token = re.sub(r"\D", "", _compact(value))
        if 6 <= len(token) <= 15:
            return token
    return None


def _signal_kind(signal: Mapping[str, Any]) -> IntelligenceRecordKind:
    signal_type = _compact(signal.get("signal_type")).upper()
    metadata = signal.get("metadata") if isinstance(signal.get("metadata"), Mapping) else {}
    if _compact(metadata.get("inventory_domain")).upper() == "BRIDAL" or _compact(
        metadata.get("feed_family")
    ).upper() == "BRIDAL_LIQUIDATION_FEED_V1":
        return IntelligenceRecordKind.BRIDAL_LIQUIDATION_SIGNAL
    if signal_type in _SIGNAL_EVENT_TYPES:
        return IntelligenceRecordKind.BUSINESS_EVENT_SIGNAL
    if _compact(signal.get("status")).upper() == "CLOSED":
        return IntelligenceRecordKind.HISTORICAL_EVIDENCE
    return IntelligenceRecordKind.MARKET_SIGNAL


def _candidate_kind(report: Mapping[str, Any], candidate: Mapping[str, Any]) -> IntelligenceRecordKind:
    family = _compact(candidate.get("feed_family") or report.get("feed_family")).upper()
    listing = _compact(candidate.get("listing_status")).upper()
    if listing in _HISTORICAL_LISTING_STATUSES:
        return IntelligenceRecordKind.HISTORICAL_EVIDENCE
    if family == "FABRIC_DEADSTOCK_PROCUREMENT_FEED_V1":
        return IntelligenceRecordKind.FABRIC_PROCUREMENT_ITEM
    if family in _AUCTION_FEED_FAMILIES or _compact(candidate.get("sale_mode")).upper() == "AUCTION":
        return IntelligenceRecordKind.AUCTION_LOT
    if family in _B2B_FEED_FAMILIES or "B2B" in family or "STOCK" in family:
        return IntelligenceRecordKind.B2B_STOCK_OFFER
    return IntelligenceRecordKind.MARKET_SIGNAL


def _item_id(kind: IntelligenceRecordKind, stable_identity: str) -> str:
    return _hash("intelligence-item", f"{kind.value}|{stable_identity}")


def _observation(
    *,
    artifact: str,
    raw_identity: str,
    item: Mapping[str, Any],
    index: int,
) -> dict[str, Any]:
    return {
        "observation_id": _hash("source-observation", f"{artifact}|{raw_identity}|{index}"),
        "source_artifact": artifact,
        "raw_identity": raw_identity,
        "normalised_item_id": item["intelligence_id"],
        "record_kind": item["record_kind"],
        "observed_at": item["latest_seen"],
        "source_url": item.get("source_url"),
        "title": item.get("title"),
    }


def _adapt_signal(
    signal: Mapping[str, Any],
    *,
    artifact: str,
    generated_at: datetime,
) -> dict[str, Any] | None:
    source_url = _canonical_url(signal.get("source_url"))
    signal_id = _compact(signal.get("signal_id"))
    title = _compact(signal.get("title"))
    if not signal_id and not source_url:
        return None
    if not title:
        title = signal_id or source_url or "Untitled signal"
    stable = f"signal:{signal_id}" if signal_id else f"url:{source_url}"
    kind = _signal_kind(signal)
    observed = _iso(
        signal.get("latest_observed_at") or signal.get("observed_at"),
        fallback=generated_at,
    )
    first_seen = _iso(signal.get("first_observed_at"), fallback=generated_at)
    metadata = signal.get("metadata") if isinstance(signal.get("metadata"), Mapping) else {}
    item = {
        "intelligence_id": _item_id(kind, stable),
        "stable_identity": stable,
        "record_kind": kind.value,
        "source_name": _compact(signal.get("source")) or "UNKNOWN_SOURCE",
        "source_country": _compact(signal.get("source_country")).upper() or None,
        "source_url": source_url,
        "title": title,
        "company_name": _compact(signal.get("company_name")) or None,
        "seller_name": _compact(signal.get("seller_name")) or None,
        "location": _compact(signal.get("location")) or None,
        "first_seen": first_seen,
        "latest_seen": observed,
        "lifecycle_status": _compact(signal.get("status")).upper() or "WATCH",
        "commercial_state": "EARLY_SIGNAL",
        "score": _score(signal.get("confidence")),
        "decision_owner": DECISION_OWNER,
        "evidence": _evidence(signal.get("evidence")),
        "missing_information": _string_list(signal.get("missing_information")),
        "source_artifacts": [artifact],
        "details": _selected_details(signal),
        "input_observation_count": 1,
    }
    if metadata:
        item["details"].setdefault("metadata", dict(metadata))
    return item


def _adapt_direct_opportunity(
    opportunity: Mapping[str, Any],
    *,
    artifact: str,
    generated_at: datetime,
) -> dict[str, Any] | None:
    identity = _compact(opportunity.get("opportunity_identity") or opportunity.get("opportunity_id"))
    source_url = _canonical_url(opportunity.get("source_url") or opportunity.get("canonical_url"))
    if not identity and not source_url:
        return None
    stable = f"opportunity:{identity}" if identity else f"url:{source_url}"
    kind = IntelligenceRecordKind.CANONICAL_OPPORTUNITY
    title = _compact(opportunity.get("title")) or identity or source_url or "Untitled opportunity"
    observed = _iso(opportunity.get("latest_seen"), fallback=generated_at)
    return {
        "intelligence_id": _item_id(kind, stable),
        "stable_identity": stable,
        "record_kind": kind.value,
        "source_name": _compact(opportunity.get("source_name")) or "UNKNOWN_SOURCE",
        "source_country": _compact(opportunity.get("market_code")).upper() or None,
        "source_url": source_url,
        "title": title,
        "company_name": _compact(opportunity.get("company_name")) or None,
        "seller_name": _compact(opportunity.get("seller_name")) or None,
        "location": _compact(opportunity.get("location")) or None,
        "first_seen": observed,
        "latest_seen": observed,
        "lifecycle_status": _compact(opportunity.get("listing_status")).upper() or "UNKNOWN",
        "commercial_state": _compact(opportunity.get("workflow_status")).upper() or "REQUIRES_VERIFICATION",
        "score": _score(opportunity.get("discovery_score")),
        "decision_owner": DECISION_OWNER,
        "evidence": _evidence(opportunity.get("evidence")),
        "missing_information": _string_list(
            opportunity.get("missing_information") or opportunity.get("missing_evidence")
        ),
        "source_artifacts": [artifact],
        "details": _selected_details(opportunity),
        "input_observation_count": 1,
    }


def _adapt_candidate(
    candidate: Mapping[str, Any],
    *,
    report: Mapping[str, Any],
    artifact: str,
    generated_at: datetime,
) -> dict[str, Any] | None:
    source_url = _canonical_url(candidate.get("source_url") or candidate.get("final_product_url"))
    explicit = _compact(candidate.get("candidate_id") or candidate.get("source_reference"))
    if not source_url and not explicit:
        return None
    kind = _candidate_kind(report, candidate)
    stable = f"url:{source_url}" if source_url else f"candidate:{explicit}"
    title = _compact(candidate.get("title")) or explicit or source_url or "Untitled candidate"
    observed = _iso(candidate.get("observed_at") or report.get("generated_at"), fallback=generated_at)
    evidence = _evidence(candidate.get("source_evidence") or candidate.get("evidence"))
    page_hash = _compact(candidate.get("page_sha256"))
    if page_hash and not any(entry.get("page_sha256") == page_hash for entry in evidence):
        evidence.append(
            {
                "evidence_type": "OFFICIAL_PAGE_HASH",
                "source_url": source_url,
                "page_sha256": page_hash,
                "verified": False,
                "captured_at": observed,
                "value": None,
                "metadata": {},
            }
        )
    listing_status = _compact(candidate.get("listing_status")).upper() or "REQUIRES_VERIFICATION"
    score = _score(
        candidate.get("b2b_relevance_score"),
        candidate.get("procurement_relevance_score"),
        candidate.get("discovery_score"),
        candidate.get("confidence"),
    )
    return {
        "intelligence_id": _item_id(kind, stable),
        "stable_identity": stable,
        "record_kind": kind.value,
        "source_name": _compact(candidate.get("source_name"))
        or _compact(report.get("source_name"))
        or _compact(report.get("feed_family"))
        or "UNKNOWN_SOURCE",
        "source_country": _compact(candidate.get("source_country")).upper() or None,
        "source_url": source_url,
        "title": title,
        "company_name": _compact(candidate.get("company_name")) or None,
        "seller_name": _compact(candidate.get("seller_name")) or None,
        "location": _compact(candidate.get("stock_location") or candidate.get("location")) or None,
        "first_seen": observed,
        "latest_seen": observed,
        "lifecycle_status": listing_status,
        "commercial_state": _compact(
            candidate.get("opportunity_state") or candidate.get("verification_status")
        ).upper()
        or "REQUIRES_VERIFICATION",
        "score": score,
        "decision_owner": DECISION_OWNER,
        "evidence": evidence,
        "missing_information": _string_list(candidate.get("missing_information")),
        "source_artifacts": [artifact],
        "details": _selected_details({**dict(candidate), "feed_family": candidate.get("feed_family") or report.get("feed_family")}),
        "input_observation_count": 1,
    }


def _iter_nested_signals(payload: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    direct = payload.get("signals")
    if isinstance(direct, list):
        yield from (item for item in direct if isinstance(item, Mapping))
    sources = payload.get("sources")
    if isinstance(sources, list):
        for source in sources:
            if not isinstance(source, Mapping):
                continue
            nested = source.get("signals")
            if isinstance(nested, list):
                yield from (item for item in nested if isinstance(item, Mapping))
    for key in ("local_language_report", "english_market_report"):
        nested_report = payload.get(key)
        if isinstance(nested_report, Mapping):
            yield from _iter_nested_signals(nested_report)


def _artifact_status(filename: str, payload: Mapping[str, Any] | None, error: str | None) -> dict[str, Any]:
    if error:
        return {"artifact": filename, "status": "INVALID", "error": error}
    if payload is None:
        return {"artifact": filename, "status": "MISSING_OPTIONAL"}
    statuses = payload.get("status_counts") if isinstance(payload.get("status_counts"), Mapping) else {}
    return {
        "artifact": filename,
        "status": "AVAILABLE",
        "schema_version": payload.get("schema_version"),
        "feed_family": payload.get("feed_family"),
        "status_counts": dict(statuses),
        "candidate_count": payload.get("candidate_count"),
        "signal_count": payload.get("signal_count"),
    }


def _richness(item: Mapping[str, Any]) -> tuple[int, float, int]:
    details = item.get("details") if isinstance(item.get("details"), Mapping) else {}
    commercial_fields = (
        "quantity",
        "minimum_order",
        "unit_price",
        "total_price",
        "current_bid",
        "currency",
        "manifest_available",
        "brands",
        "grade",
        "auction_end_text",
        "organisation_number",
    )
    populated = sum(details.get(key) not in (None, "", [], {}) for key in commercial_fields)
    official = int(any(entry.get("page_sha256") for entry in item.get("evidence") or [] if isinstance(entry, Mapping)))
    return (populated + official * 3 + len(item.get("evidence") or []), float(item.get("score") or 0.0), -len(item.get("missing_information") or []))


def _merge_items(existing: dict[str, Any], incoming: Mapping[str, Any]) -> dict[str, Any]:
    winner, other = (existing, incoming) if _richness(existing) >= _richness(incoming) else (dict(incoming), existing)
    merged = dict(winner)
    merged["source_artifacts"] = sorted(
        set(existing.get("source_artifacts") or []) | set(incoming.get("source_artifacts") or [])
    )
    merged["input_observation_count"] = int(existing.get("input_observation_count") or 1) + int(
        incoming.get("input_observation_count") or 1
    )
    merged["first_seen"] = min(_compact(existing.get("first_seen")), _compact(incoming.get("first_seen")))
    merged["latest_seen"] = max(_compact(existing.get("latest_seen")), _compact(incoming.get("latest_seen")))
    merged["score"] = max(float(existing.get("score") or 0.0), float(incoming.get("score") or 0.0))
    evidence = _evidence([*(existing.get("evidence") or []), *(incoming.get("evidence") or [])])
    merged["evidence"] = evidence
    details = dict(other.get("details") or {})
    details.update(dict(winner.get("details") or {}))
    merged["details"] = details
    return merged


def _deduplicate(items: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    by_id: dict[str, dict[str, Any]] = {}
    duplicate_count = 0
    for raw in items:
        item = dict(raw)
        item_id = _compact(item.get("intelligence_id"))
        if not item_id:
            continue
        if item_id in by_id:
            duplicate_count += 1
            by_id[item_id] = _merge_items(by_id[item_id], item)
        else:
            by_id[item_id] = item
    return [by_id[key] for key in sorted(by_id)], duplicate_count


def _case_group(item: Mapping[str, Any]) -> tuple[str, str, str]:
    country = _compact(item.get("source_country")).upper() or "XX"
    org = _organisation_number(item)
    if org:
        return "ORGANISATION", f"{country}:{org}", RelationshipType.SAME_ORGANISATION_NUMBER.value
    company = _normalise_token(item.get("company_name"))
    if company:
        return "COMPANY", f"{country}:{company}", RelationshipType.SAME_COMPANY.value
    kind = _compact(item.get("record_kind")).upper()
    seller = _normalise_token(item.get("seller_name"))
    if seller and kind in {
        IntelligenceRecordKind.B2B_STOCK_OFFER.value,
        IntelligenceRecordKind.AUCTION_LOT.value,
        IntelligenceRecordKind.FABRIC_PROCUREMENT_ITEM.value,
    }:
        return "SELLER", f"{country}:{seller}", RelationshipType.SAME_SELLER.value
    if kind in {
        IntelligenceRecordKind.B2B_STOCK_OFFER.value,
        IntelligenceRecordKind.FABRIC_PROCUREMENT_ITEM.value,
    }:
        source = _normalise_token(item.get("source_name"))
        if source:
            return "SELLER", f"{country}:{source}", RelationshipType.SAME_SELLER.value
    return "ITEM", _compact(item.get("intelligence_id")), RelationshipType.SAME_MARKET_CASE.value


def _case_type(items: Sequence[Mapping[str, Any]]) -> MarketCaseType:
    kinds = {_compact(item.get("record_kind")).upper() for item in items}
    signal_types = {
        _compact((item.get("details") or {}).get("signal_type")).upper()
        for item in items
        if isinstance(item.get("details"), Mapping)
    }
    if signal_types & _SIGNAL_EVENT_TYPES:
        return MarketCaseType.COMPANY_LIQUIDATION
    if IntelligenceRecordKind.AUCTION_LOT.value in kinds:
        return MarketCaseType.AUCTION_INVENTORY
    if IntelligenceRecordKind.BRIDAL_LIQUIDATION_SIGNAL.value in kinds:
        return MarketCaseType.BRIDAL_LIQUIDATION
    if IntelligenceRecordKind.FABRIC_PROCUREMENT_ITEM.value in kinds:
        return MarketCaseType.FABRIC_PROCUREMENT
    if IntelligenceRecordKind.B2B_STOCK_OFFER.value in kinds:
        return MarketCaseType.B2B_INVENTORY
    if IntelligenceRecordKind.CANONICAL_OPPORTUNITY.value in kinds:
        return MarketCaseType.DIRECT_OPPORTUNITY
    if kinds == {IntelligenceRecordKind.HISTORICAL_EVIDENCE.value}:
        return MarketCaseType.HISTORICAL_MARKET_EVIDENCE
    return MarketCaseType.MARKET_SIGNAL_WATCH


def _case_status(items: Sequence[Mapping[str, Any]]) -> str:
    commercial = {_compact(item.get("commercial_state")).upper() for item in items}
    lifecycle = {_compact(item.get("lifecycle_status")).upper() for item in items}
    if "QUALIFIED_OPPORTUNITY" in commercial:
        return "QUALIFIED_OPPORTUNITY"
    if commercial & {"ACTIVE_OPPORTUNITY", "B2B_LEAD_REQUIRES_VERIFICATION"}:
        return "ACTIVE_REQUIRES_VERIFICATION"
    if lifecycle and lifecycle <= _HISTORICAL_LISTING_STATUSES:
        return "HISTORICAL_ONLY"
    return "WATCH"


def _action(case_type: MarketCaseType) -> str:
    return {
        MarketCaseType.COMPANY_LIQUIDATION: "MONITOR_INVENTORY_RELEASE_AND_LINK_NEW_OFFERS",
        MarketCaseType.B2B_INVENTORY: "REVIEW_PRICE_QUANTITY_MANIFEST_AUTHENTICITY_AND_SHIPPING",
        MarketCaseType.AUCTION_INVENTORY: "REVIEW_LOT_MANIFEST_END_TIME_FEES_AND_SHIPPING",
        MarketCaseType.BRIDAL_LIQUIDATION: "VERIFY_BUSINESS_EVENT_AND_AVAILABLE_BRIDAL_STOCK",
        MarketCaseType.FABRIC_PROCUREMENT: "REVIEW_SAMPLE_PRICE_MOQ_AND_SHIPPING",
        MarketCaseType.DIRECT_OPPORTUNITY: "REVIEW_CURRENT_OPPORTUNITY_AND_MISSING_EVIDENCE",
        MarketCaseType.HISTORICAL_MARKET_EVIDENCE: "RETAIN_AS_HISTORICAL_EVIDENCE",
        MarketCaseType.MARKET_SIGNAL_WATCH: "VERIFY_MARKET_SIGNAL",
    }[case_type]


def _case_title(group_type: str, items: Sequence[Mapping[str, Any]], case_type: MarketCaseType) -> str:
    first = items[0]
    if group_type == "ORGANISATION" or group_type == "COMPANY":
        return _compact(first.get("company_name")) or _compact(first.get("title"))
    if group_type == "SELLER":
        seller = _compact(first.get("seller_name") or first.get("source_name"))
        suffix = {
            MarketCaseType.FABRIC_PROCUREMENT: "fabric procurement",
            MarketCaseType.AUCTION_INVENTORY: "auction inventory",
            MarketCaseType.B2B_INVENTORY: "B2B inventory",
        }.get(case_type, "market intelligence")
        return f"{seller} — {suffix}"
    return _compact(first.get("title"))


def _prices(items: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[Any, Any, Any]] = set()
    for item in items:
        details = item.get("details") if isinstance(item.get("details"), Mapping) else {}
        currency = details.get("currency")
        for field in ("unit_price", "total_price", "current_bid", "price", "reserve_price"):
            value = _number(details.get(field))
            key = (field, value, currency)
            if value is None or key in seen:
                continue
            seen.add(key)
            result.append({"amount": value, "currency": currency, "basis": field.upper(), "item_id": item.get("intelligence_id")})
    return result[:20]


def _quantities(items: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in items:
        details = item.get("details") if isinstance(item.get("details"), Mapping) else {}
        quantity = _number(details.get("quantity"))
        if quantity is not None:
            result.append(
                {
                    "quantity": quantity,
                    "unit": details.get("quantity_unit"),
                    "item_id": item.get("intelligence_id"),
                }
            )
    return result[:20]


def _risk_flags(missing: Sequence[str]) -> list[str]:
    flags: set[str] = set()
    joined = " ".join(missing)
    if "PRICE" in joined or "BID" in joined:
        flags.add("PRICE_NOT_CONFIRMED")
    if "QUANTITY" in joined or "MINIMUM_ORDER" in joined:
        flags.add("QUANTITY_OR_MOQ_NOT_CONFIRMED")
    if "MANIFEST" in joined or "PACKING" in joined or "CONTENTS" in joined:
        flags.add("CONTENTS_NOT_CONFIRMED")
    if "AUTHENTICITY" in joined:
        flags.add("BRAND_AUTHENTICITY_NOT_CONFIRMED")
    if "SHIPPING" in joined:
        flags.add("SHIPPING_TO_NORWAY_NOT_CONFIRMED")
    return sorted(flags)


def _build_cases(items: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for item in items:
        group_type, group_key, relation = _case_group(item)
        grouped[(group_type, group_key, relation)].append(item)

    cases: list[dict[str, Any]] = []
    relationships: list[dict[str, Any]] = []
    item_by_stable = {_compact(item.get("stable_identity")): item for item in items}

    for (group_type, group_key, relation_type), raw_items in sorted(grouped.items()):
        case_items = sorted(raw_items, key=lambda item: _compact(item.get("intelligence_id")))
        case_type = _case_type(case_items)
        case_id = _hash("market-case", f"{group_type}|{group_key}")
        missing = sorted({value for item in case_items for value in (item.get("missing_information") or [])})
        score = min(
            100.0,
            max((float(item.get("score") or 0.0) for item in case_items), default=0.0)
            + min(15.0, max(0, len(case_items) - 1) * 3.0),
        )
        countries = sorted({_compact(item.get("source_country")).upper() for item in case_items if _compact(item.get("source_country"))})
        source_urls = list(dict.fromkeys(item.get("source_url") for item in case_items if item.get("source_url")))
        case = {
            "case_id": case_id,
            "case_type": case_type.value,
            "case_title": _case_title(group_type, case_items, case_type),
            "grouping_basis": group_type,
            "grouping_key": group_key,
            "countries": countries,
            "first_seen": min(_compact(item.get("first_seen")) for item in case_items),
            "last_seen": max(_compact(item.get("latest_seen")) for item in case_items),
            "case_status": _case_status(case_items),
            "commercial_strength": round(score, 2),
            "item_count": len(case_items),
            "item_ids": [item["intelligence_id"] for item in case_items],
            "record_kind_counts": dict(sorted(Counter(item["record_kind"] for item in case_items).items())),
            "source_names": sorted({_compact(item.get("source_name")) for item in case_items if _compact(item.get("source_name"))}),
            "source_urls": source_urls[:20],
            "evidence_count": sum(len(item.get("evidence") or []) for item in case_items),
            "missing_information": missing,
            "commercial_snapshot": {
                "quantities": _quantities(case_items),
                "prices": _prices(case_items),
                "brands": sorted(
                    {
                        _compact(brand)
                        for item in case_items
                        for brand in ((item.get("details") or {}).get("brands") or [])
                        if _compact(brand)
                    }
                )[:30],
            },
            "risk_flags": _risk_flags(missing),
            "recommended_next_action": _action(case_type),
            "decision_owner": DECISION_OWNER,
            "automatic_contact": False,
            "automatic_bid": False,
            "automatic_purchase": False,
            "automatic_payment": False,
        }
        cases.append(case)
        if len(case_items) > 1:
            anchor = case_items[0]["intelligence_id"]
            for item in case_items[1:]:
                relationships.append(
                    {
                        "relationship_id": _hash("relationship", f"{anchor}|{relation_type}|{item['intelligence_id']}"),
                        "from_item_id": anchor,
                        "to_item_id": item["intelligence_id"],
                        "relationship_type": relation_type,
                        "case_id": case_id,
                    }
                )

    for item in items:
        details = item.get("details") if isinstance(item.get("details"), Mapping) else {}
        related_signal_id = _compact(details.get("related_signal_id"))
        if not related_signal_id:
            continue
        target_item = item_by_stable.get(f"signal:{related_signal_id}")
        if target_item:
            relationships.append(
                {
                    "relationship_id": _hash(
                        "relationship",
                        f"{target_item['intelligence_id']}|SUPPORTS|{item['intelligence_id']}",
                    ),
                    "from_item_id": target_item["intelligence_id"],
                    "to_item_id": item["intelligence_id"],
                    "relationship_type": RelationshipType.SUPPORTS.value,
                    "case_id": None,
                }
            )

    relationships = [
        dict(value)
        for _, value in sorted(
            {relationship["relationship_id"]: relationship for relationship in relationships}.items()
        )
    ]
    return sorted(cases, key=lambda case: (-float(case["commercial_strength"]), case["case_id"])), relationships


def _decision_card(case: Mapping[str, Any]) -> dict[str, Any]:
    kinds = case.get("record_kind_counts") or {}
    return {
        "case_id": case.get("case_id"),
        "headline": case.get("case_title"),
        "case_type": case.get("case_type"),
        "case_status": case.get("case_status"),
        "commercial_strength": case.get("commercial_strength"),
        "why_now": f"{case.get('item_count', 0)} linked intelligence item(s); last seen {case.get('last_seen')}",
        "signal_count": sum(value for key, value in kinds.items() if "SIGNAL" in key),
        "direct_opportunity_count": int(kinds.get(IntelligenceRecordKind.CANONICAL_OPPORTUNITY.value, 0)),
        "offer_count": sum(
            int(kinds.get(key, 0))
            for key in (
                IntelligenceRecordKind.B2B_STOCK_OFFER.value,
                IntelligenceRecordKind.AUCTION_LOT.value,
                IntelligenceRecordKind.FABRIC_PROCUREMENT_ITEM.value,
            )
        ),
        "commercial_snapshot": case.get("commercial_snapshot"),
        "missing_information": case.get("missing_information"),
        "risk_flags": case.get("risk_flags"),
        "recommended_next_action": case.get("recommended_next_action"),
        "source_urls": case.get("source_urls"),
        "decision_owner": DECISION_OWNER,
    }


def build_unified_market_intelligence_river(
    artifacts: Mapping[str, Mapping[str, Any]],
    *,
    generated_at: datetime | None = None,
    artifact_statuses: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Build observations, deduplicated items, cases, and decision cards."""
    now = generated_at or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)

    raw_items: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []

    for artifact in sorted(artifacts):
        payload = artifacts[artifact]
        if not isinstance(payload, Mapping):
            continue
        generated = now
        generated_text = payload.get("generated_at")
        if generated_text:
            try:
                generated = datetime.fromisoformat(_iso(generated_text))
            except ValueError:
                generated = now
        adapted: list[dict[str, Any]] = []
        if artifact == "domain-market-intelligence-brief.json":
            for opportunity in payload.get("current_direct_opportunities") or []:
                if isinstance(opportunity, Mapping):
                    item = _adapt_direct_opportunity(opportunity, artifact=artifact, generated_at=generated)
                    if item:
                        adapted.append(item)
            for signal in payload.get("early_signals_to_watch") or []:
                if isinstance(signal, Mapping):
                    item = _adapt_signal(signal, artifact=artifact, generated_at=generated)
                    if item:
                        adapted.append(item)
        else:
            for signal in _iter_nested_signals(payload):
                item = _adapt_signal(signal, artifact=artifact, generated_at=generated)
                if item:
                    adapted.append(item)
            candidates = payload.get("candidates")
            if isinstance(candidates, list):
                for candidate in candidates:
                    if isinstance(candidate, Mapping):
                        item = _adapt_candidate(candidate, report=payload, artifact=artifact, generated_at=generated)
                        if item:
                            adapted.append(item)
        for index, item in enumerate(adapted):
            raw_items.append(item)
            observations.append(
                _observation(
                    artifact=artifact,
                    raw_identity=item["stable_identity"],
                    item=item,
                    index=index,
                )
            )

    items, duplicate_count = _deduplicate(raw_items)
    cases, relationships = _build_cases(items)
    cards = [_decision_card(case) for case in cases]
    statuses = list(artifact_statuses or [])
    invalid = [entry for entry in statuses if entry.get("status") == "INVALID"]
    available = [entry for entry in statuses if entry.get("status") == "AVAILABLE"]
    river_status = (
        "PARTIAL_SUCCESS_WITH_INPUT_ERRORS"
        if invalid and items
        else "FAILED_INPUTS"
        if invalid and not items
        else "SUCCESS"
        if items
        else "VALID_ZERO"
    )
    generated_iso = now.isoformat()
    common_safety = {
        "decision_owner": DECISION_OWNER,
        "quantity_size_rejection_enabled": False,
        "promotion_to_opportunity_allowed": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }
    item_counts = dict(sorted(Counter(item["record_kind"] for item in items).items()))
    case_counts = dict(sorted(Counter(case["case_type"] for case in cases).items()))
    items_report = {
        "schema_version": ITEMS_SCHEMA_VERSION,
        "river_schema_version": SCHEMA_VERSION,
        "generated_at": generated_iso,
        "status": river_status,
        "source_artifact_count": len(available),
        "input_artifact_statuses": statuses,
        "source_observation_count": len(observations),
        "input_record_count": len(raw_items),
        "deduplicated_item_count": len(items),
        "duplicate_observation_count": duplicate_count,
        "record_kind_counts": item_counts,
        "source_observations": observations,
        "items": items,
        "relationships": relationships,
        **common_safety,
    }
    cases_report = {
        "schema_version": CASES_SCHEMA_VERSION,
        "river_schema_version": SCHEMA_VERSION,
        "generated_at": generated_iso,
        "status": river_status,
        "case_count": len(cases),
        "case_type_counts": case_counts,
        "relationship_count": len(relationships),
        "cases": cases,
        "relationships": relationships,
        **common_safety,
    }
    brief = {
        "schema_version": BRIEF_SCHEMA_VERSION,
        "river_schema_version": SCHEMA_VERSION,
        "generated_at": generated_iso,
        "status": river_status,
        "counts": {
            "source_artifacts_available": len(available),
            "source_observations": len(observations),
            "deduplicated_items": len(items),
            "duplicates_merged": duplicate_count,
            "market_cases": len(cases),
            "relationships": len(relationships),
        },
        "record_kind_counts": item_counts,
        "case_type_counts": case_counts,
        "decision_cards": cards,
        "top_decision_card": cards[0] if cards else None,
        "truthful_zero_result": not items,
        "input_artifact_statuses": statuses,
        "output_files": [ITEMS_FILENAME, CASES_FILENAME, BRIEF_FILENAME],
        **common_safety,
    }
    return {"items": items_report, "cases": cases_report, "brief": brief}


def _read_artifacts(output_dir: Path) -> tuple[dict[str, Mapping[str, Any]], list[dict[str, Any]]]:
    artifacts: dict[str, Mapping[str, Any]] = {}
    statuses: list[dict[str, Any]] = []
    for filename in INPUT_ARTIFACTS:
        path = output_dir / filename
        if not path.exists():
            statuses.append(_artifact_status(filename, None, None))
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            statuses.append(_artifact_status(filename, None, f"{type(exc).__name__}: {exc}"))
            continue
        if not isinstance(payload, Mapping):
            statuses.append(_artifact_status(filename, None, "artifact root must be an object"))
            continue
        artifacts[filename] = payload
        statuses.append(_artifact_status(filename, payload, None))
    return artifacts, statuses


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _attach_to_existing_brief(output_dir: Path, brief: Mapping[str, Any]) -> None:
    path = output_dir / "domain-market-intelligence-brief.json"
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = None
        if isinstance(payload, dict):
            payload["unified_market_intelligence_river"] = {
                "schema_version": brief.get("schema_version"),
                "status": brief.get("status"),
                "counts": brief.get("counts"),
                "record_kind_counts": brief.get("record_kind_counts"),
                "case_type_counts": brief.get("case_type_counts"),
                "top_decision_card": brief.get("top_decision_card"),
                "output_files": brief.get("output_files"),
                "decision_owner": DECISION_OWNER,
                "automatic_purchase": False,
            }
            _write_json(path, payload)
    text_path = output_dir / "domain-market-intelligence-brief.txt"
    if text_path.exists():
        counts = brief.get("counts") or {}
        top = brief.get("top_decision_card") or {}
        with text_path.open("a", encoding="utf-8") as handle:
            handle.write(
                "\nUNIFIED MARKET INTELLIGENCE RIVER\n"
                f"status: {brief.get('status')}\n"
                f"source_observations: {counts.get('source_observations', 0)}\n"
                f"deduplicated_items: {counts.get('deduplicated_items', 0)}\n"
                f"market_cases: {counts.get('market_cases', 0)}\n"
                f"top_case: {top.get('headline') or 'NONE'}\n"
                "decision_owner: HUMAN_OPERATOR\n"
                "automatic_purchase: false\n"
            )


def write_unified_market_intelligence_river(output_dir: str | Path) -> dict[str, Any]:
    """Read established artifacts and write the three river projections."""
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    artifacts, statuses = _read_artifacts(directory)
    generated = None
    base = artifacts.get("domain-market-intelligence-brief.json")
    if isinstance(base, Mapping) and base.get("generated_at"):
        try:
            generated = datetime.fromisoformat(_iso(base.get("generated_at")))
        except ValueError:
            generated = None
    result = build_unified_market_intelligence_river(
        artifacts,
        generated_at=generated,
        artifact_statuses=statuses,
    )
    _write_json(directory / ITEMS_FILENAME, result["items"])
    _write_json(directory / CASES_FILENAME, result["cases"])
    _write_json(directory / BRIEF_FILENAME, result["brief"])
    _attach_to_existing_brief(directory, result["brief"])
    return result["brief"]
