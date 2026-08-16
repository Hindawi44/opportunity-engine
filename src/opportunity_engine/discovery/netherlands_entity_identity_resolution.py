"""Resolve Dutch company identity before durable memory is allowed.

A Netherlands discovery hit can describe a real insolvency without naming the
legal entity in the search snippet. This resolver performs a bounded second look
using public search evidence. It never invents a company name: a candidate must
first emerge from the discovery context and then be corroborated either by an
official Rechtspraak result or by at least two independent public domains.

Resolved identity is still signal-only evidence. It may seed ENTITY_SCENT memory,
but it never promotes an opportunity, contacts a seller, bids, reserves, buys,
or pays.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import re
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlsplit

from opportunity_engine.discovery.brave_search import BraveSearchProvider
from opportunity_engine.discovery.netherlands_market_discovery import FEED_FAMILY, MARKET_CODE
from opportunity_engine.discovery.search_provider import SearchHit, SearchProvider


SCHEMA_VERSION = "netherlands-entity-identity-resolution-1.0"
ENGINE_VERSION = "NETHERLANDS_ENTITY_IDENTITY_RESOLUTION_V1"
DEFAULT_MAX_SIGNALS = 5
MAX_SIGNALS = 10
DEFAULT_RESULTS_PER_QUERY = 6
MAX_RESULTS_PER_QUERY = 10
MAX_CANDIDATES_PER_SIGNAL = 2

ProviderFactory = Callable[[str, str], SearchProvider]

_OFFICIAL_RECHTSPRAAK_HOSTS = {
    "insolventies.rechtspraak.nl",
    "rechtspraak.nl",
    "www.rechtspraak.nl",
    "uitspraken.rechtspraak.nl",
    "webservice.rechtspraak.nl",
}
_INSOLVENCY_TERMS = (
    "faillissement",
    "failliet",
    "curator",
    "insolventie",
    "surseance",
)
_GENERIC_ENTITY_TOKENS = {
    "bedrijf",
    "fashion",
    "kleding",
    "kledingwinkel",
    "mall",
    "mode",
    "netherlands",
    "nederland",
    "onderneming",
    "outlet",
    "winkel",
}
_LEGAL_FORM = r"(?:b\.?\s*v\.?|n\.?\s*v\.?|v\.?\s*o\.?\s*f\.?|c\.?\s*v\.?)"
_LEGAL_ENTITY_RE = re.compile(
    rf"(?P<label>[A-ZÀ-ÖØ-Þ0-9][\wÀ-ÿ&'’.-]*(?:\s+[A-ZÀ-ÖØ-Þ0-9][\wÀ-ÿ&'’.-]*){{0,7}}\s+{_LEGAL_FORM})(?!\w)",
    flags=re.IGNORECASE | re.UNICODE,
)
_CLOTHING_OWNER_RE = re.compile(
    r"\b(?:kledingwinkel|modewinkel|bruidswinkel|schoenenwinkel|winkel)\s+van\s+"
    r"(?P<label>[A-Z0-9][\wÀ-ÿ&'’.-]*(?:\s+(?!(?:in|te|uit|bij|met|voor|onder|van)\b)"
    r"[A-Z0-9][\wÀ-ÿ&'’.-]*){1,5})",
    flags=re.UNICODE,
)
_KVK_RE = re.compile(r"\bkvk(?:-nummer| nummer)?\s*[:#]?\s*(?P<kvk>\d{8})\b", re.IGNORECASE)
_INSOLVENCY_ID_RE = re.compile(r"\bF\.\d{2}/\d{2}/\d{1,4}\b", re.IGNORECASE)


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _utc(value: datetime | None = None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc)


def _metadata(signal: Mapping[str, Any]) -> dict[str, Any]:
    raw = signal.get("metadata")
    return dict(raw) if isinstance(raw, Mapping) else {}


def _host(url: object) -> str:
    try:
        return (urlsplit(_compact(url)).hostname or "").casefold().rstrip(".")
    except ValueError:
        return ""


def _normalise(value: object) -> str:
    text = _compact(value).casefold()
    text = re.sub(_LEGAL_FORM, " ", text, flags=re.IGNORECASE)
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9à-öø-ÿ]+", " ", text)
    return " ".join(text.split())


def _plausible_candidate(label: str) -> bool:
    key = _normalise(label)
    tokens = [token for token in key.split() if len(token) >= 2]
    if len(tokens) < 2 or len(key) > 100:
        return False
    return any(token not in _GENERIC_ENTITY_TOKENS for token in tokens)


def _insolvency_context(text: str) -> bool:
    folded = text.casefold()
    return any(term in folded for term in _INSOLVENCY_TERMS)


def _core_title(signal: Mapping[str, Any]) -> str:
    title = _compact(signal.get("title"))
    title = re.sub(r"\s+-\s+[^-]{2,80}$", "", title).strip()
    return title[:220]


def _context_query(signal: Mapping[str, Any]) -> str:
    title = _core_title(signal).replace('"', "")
    return f'"{title}" faillissement bedrijfsnaam' if title else ""


def _candidate_rows(hit: SearchHit) -> list[dict[str, Any]]:
    title = _compact(hit.title)
    description = _compact(hit.description)
    combined = f"{title} {description}".strip()
    rows: dict[str, dict[str, Any]] = {}

    for match in _CLOTHING_OWNER_RE.finditer(combined):
        label = _compact(match.group("label")).strip(" -–—|:,.;")
        if not _plausible_candidate(label):
            continue
        key = _normalise(label)
        rows[key] = {
            "label": label,
            "key": key,
            "shape": "CLOTHING_OWNER_PHRASE",
            "context_score": 95,
        }

    for match in _LEGAL_ENTITY_RE.finditer(combined):
        label = _compact(match.group("label")).strip(" -–—|:,.;")
        if not _plausible_candidate(label):
            continue
        key = _normalise(label)
        score = 88 if _normalise(label) in _normalise(title) else 78
        existing = rows.get(key)
        if existing is None or score > int(existing.get("context_score") or 0):
            rows[key] = {
                "label": label,
                "key": key,
                "shape": "DUTCH_LEGAL_ENTITY",
                "context_score": score,
            }
    return list(rows.values())


def _kvk(text: str) -> str | None:
    match = _KVK_RE.search(text)
    return match.group("kvk") if match else None


def _insolvency_id(text: str) -> str | None:
    match = _INSOLVENCY_ID_RE.search(text)
    return match.group(0).upper() if match else None


def _default_provider_factory(market_code: str, api_key: str) -> SearchProvider:
    return BraveSearchProvider(
        api_key,
        freshness=None,
        extra_snippets=True,
        operators=True,
        country=market_code,
    )


def _confirm_candidate(
    provider: SearchProvider,
    candidate: Mapping[str, Any],
    *,
    results_per_query: int,
    context_evidence: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    label = _compact(candidate.get("label"))
    key = _compact(candidate.get("key"))
    query = f'"{label.replace(chr(34), "")}" faillissement'
    hits = provider.search(query, count=results_per_query)

    evidence: list[dict[str, Any]] = [dict(item) for item in context_evidence]
    legal_labels: list[str] = []
    kvk_numbers: set[str] = set()
    insolvency_ids: set[str] = set()
    confirmation_domains: set[str] = set()
    official_domains: set[str] = set()

    for rank, hit in enumerate(hits, start=1):
        if not isinstance(hit, SearchHit):
            continue
        title = _compact(hit.title)
        description = _compact(hit.description)
        combined = f"{title} {description}".strip()
        if key not in _normalise(combined) or not _insolvency_context(combined):
            continue
        host = _host(hit.url)
        if not host:
            continue
        legal_matches = [
            _compact(match.group("label")).strip(" -–—|:,.;")
            for match in _LEGAL_ENTITY_RE.finditer(combined)
        ]
        exact_legal = [name for name in legal_matches if _normalise(name) == key]
        if exact_legal:
            legal_labels.extend(exact_legal)
        found_kvk = _kvk(combined)
        found_case = _insolvency_id(combined)
        if found_kvk:
            kvk_numbers.add(found_kvk)
        if found_case:
            insolvency_ids.add(found_case)
        confirmation_domains.add(host)
        if host in _OFFICIAL_RECHTSPRAAK_HOSTS:
            official_domains.add(host)
        evidence.append(
            {
                "evidence_role": "IDENTITY_CONFIRMATION",
                "rank": rank,
                "title": title,
                "source_url": _compact(hit.url),
                "source_domain": host,
                "official_rechtspraak": host in _OFFICIAL_RECHTSPRAAK_HOSTS,
                "kvk_number": found_kvk,
                "insolvency_id": found_case,
            }
        )

    context_domains = {
        _compact(item.get("source_domain"))
        for item in context_evidence
        if _compact(item.get("source_domain"))
    }
    independent_domains = context_domains | confirmation_domains
    official = bool(official_domains)
    corroborated = bool(confirmation_domains) and len(independent_domains) >= 2
    resolved = official or corroborated
    status = (
        "RESOLVED_OFFICIAL_REGISTER"
        if official
        else ("RESOLVED_CORROBORATED_PUBLIC" if corroborated else "UNRESOLVED_INSUFFICIENT_CORROBORATION")
    )
    canonical_label = max(legal_labels, key=len) if legal_labels else label
    return {
        "resolved": resolved,
        "status": status,
        "candidate_label": label,
        "canonical_company_name": canonical_label if resolved else None,
        "entity_key": key,
        "context_score": int(candidate.get("context_score") or 0),
        "candidate_shape": candidate.get("shape"),
        "confirmation_query": query,
        "independent_domain_count": len(independent_domains),
        "confirmation_domain_count": len(confirmation_domains),
        "official_rechtspraak_confirmed": official,
        "official_domains": sorted(official_domains),
        "kvk_numbers": sorted(kvk_numbers),
        "insolvency_ids": sorted(insolvency_ids),
        "evidence": evidence,
    }


def resolve_netherlands_entity_identities(
    signals: Sequence[Mapping[str, Any]],
    *,
    environment: Mapping[str, str] | None = None,
    provider_factory: ProviderFactory = _default_provider_factory,
    observed_at: datetime | None = None,
    max_signals: int = DEFAULT_MAX_SIGNALS,
    results_per_query: int = DEFAULT_RESULTS_PER_QUERY,
) -> dict[str, Any]:
    """Resolve missing NL company identities with bounded corroborating search."""
    if not 0 <= max_signals <= MAX_SIGNALS:
        raise ValueError(f"max_signals must be between 0 and {MAX_SIGNALS}")
    if not 1 <= results_per_query <= MAX_RESULTS_PER_QUERY:
        raise ValueError(
            f"results_per_query must be between 1 and {MAX_RESULTS_PER_QUERY}"
        )

    now = _utc(observed_at)
    env = environment or {}
    api_key = _compact(env.get("BRAVE_SEARCH_API_KEY") or env.get("BRAVE_API_KEY"))
    base = {
        "schema_version": SCHEMA_VERSION,
        "engine_version": ENGINE_VERSION,
        "generated_at": now.isoformat(),
        "source_country": MARKET_CODE,
        "input_signal_count": len(signals),
        "processed_signal_count": 0,
        "resolved_identity_count": 0,
        "officially_confirmed_identity_count": 0,
        "corroborated_public_identity_count": 0,
        "unresolved_identity_count": 0,
        "search_request_count": 0,
        "search_error_count": 0,
        "resolutions": [],
        "enriched_signals": [deepcopy(dict(item)) for item in signals if isinstance(item, Mapping)],
        "identity_required_before_memory": True,
        "promotion_to_opportunity_allowed": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }
    if not api_key:
        return {**base, "status": "SKIPPED_NO_API_KEY", "block_reason": "BRAVE_SEARCH_API_KEY_MISSING"}

    try:
        provider = provider_factory(MARKET_CODE, api_key)
    except Exception as exc:
        return {
            **base,
            "status": "BLOCKED_RETRIEVAL",
            "block_reason": "PROVIDER_INITIALIZATION_FAILED",
            "search_error_count": 1,
            "errors": [f"{type(exc).__name__}: {_compact(exc)[:300]}"],
        }

    enriched = [deepcopy(dict(item)) for item in signals if isinstance(item, Mapping)]
    resolutions: list[dict[str, Any]] = []
    errors: list[str] = []
    search_requests = search_errors = processed = 0
    resolved_count = official_count = public_count = unresolved_count = 0

    for index, signal in enumerate(enriched):
        if processed >= max_signals:
            break
        metadata = _metadata(signal)
        if _compact(signal.get("source_country")).upper() != MARKET_CODE:
            continue
        if _compact(metadata.get("feed_family")) != FEED_FAMILY:
            continue
        if _compact(signal.get("company_name") or signal.get("seller_name")):
            resolutions.append(
                {
                    "signal_id": signal.get("signal_id"),
                    "status": "SKIPPED_ALREADY_IDENTIFIED",
                    "company_name": signal.get("company_name") or signal.get("seller_name"),
                    "search_request_count": 0,
                }
            )
            continue

        processed += 1
        query = _context_query(signal)
        resolution: dict[str, Any] = {
            "signal_id": signal.get("signal_id"),
            "source_url": signal.get("source_url"),
            "context_query": query,
            "status": "UNRESOLVED_NO_CANDIDATE",
            "search_request_count": 0,
            "candidates_considered": [],
        }
        if not query:
            unresolved_count += 1
            resolutions.append(resolution)
            continue

        try:
            hits = provider.search(query, count=results_per_query)
            search_requests += 1
            resolution["search_request_count"] += 1
        except Exception as exc:
            search_errors += 1
            errors.append(f"{signal.get('signal_id')}: context: {type(exc).__name__}: {_compact(exc)[:300]}")
            resolution["status"] = "UNRESOLVED_SEARCH_FAILED"
            unresolved_count += 1
            resolutions.append(resolution)
            continue

        candidates: dict[str, dict[str, Any]] = {}
        context_evidence_by_key: dict[str, list[dict[str, Any]]] = {}
        for rank, hit in enumerate(hits, start=1):
            if not isinstance(hit, SearchHit):
                continue
            for candidate in _candidate_rows(hit):
                key = _compact(candidate.get("key"))
                if not key:
                    continue
                current = candidates.get(key)
                if current is None or int(candidate.get("context_score") or 0) > int(current.get("context_score") or 0):
                    candidates[key] = candidate
                context_evidence_by_key.setdefault(key, []).append(
                    {
                        "evidence_role": "DISCOVERY_CONTEXT_IDENTITY_HINT",
                        "rank": rank,
                        "title": _compact(hit.title),
                        "source_url": _compact(hit.url),
                        "source_domain": _host(hit.url),
                        "candidate_shape": candidate.get("shape"),
                    }
                )

        ranked = sorted(
            candidates.values(),
            key=lambda item: (-int(item.get("context_score") or 0), _compact(item.get("key"))),
        )[:MAX_CANDIDATES_PER_SIGNAL]
        if not ranked:
            unresolved_count += 1
            resolutions.append(resolution)
            continue

        confirmed: list[dict[str, Any]] = []
        for candidate in ranked:
            key = _compact(candidate.get("key"))
            try:
                result = _confirm_candidate(
                    provider,
                    candidate,
                    results_per_query=results_per_query,
                    context_evidence=context_evidence_by_key.get(key, ()),
                )
                search_requests += 1
                resolution["search_request_count"] += 1
                confirmed.append(result)
            except Exception as exc:
                search_errors += 1
                errors.append(f"{signal.get('signal_id')}: confirm {key}: {type(exc).__name__}: {_compact(exc)[:300]}")

        resolution["candidates_considered"] = confirmed
        viable = [item for item in confirmed if item.get("resolved") is True]
        if not viable:
            resolution["status"] = "UNRESOLVED_INSUFFICIENT_CORROBORATION"
            unresolved_count += 1
            resolutions.append(resolution)
            continue

        viable.sort(
            key=lambda item: (
                -int(bool(item.get("official_rechtspraak_confirmed"))),
                -int(item.get("independent_domain_count") or 0),
                -int(item.get("context_score") or 0),
                _compact(item.get("entity_key")),
            )
        )
        winner = viable[0]
        company_name = _compact(winner.get("canonical_company_name"))
        signal["company_name"] = company_name
        identity_meta = _metadata(signal)
        identity_meta.update(
            {
                "netherlands_entity_identity_resolution": ENGINE_VERSION,
                "entity_identity_resolution_status": winner.get("status"),
                "resolved_company_name": company_name,
                "resolved_entity_key": winner.get("entity_key"),
                "identity_independent_domain_count": winner.get("independent_domain_count"),
                "identity_official_rechtspraak_confirmed": winner.get("official_rechtspraak_confirmed"),
                "identity_kvk_numbers": list(winner.get("kvk_numbers") or []),
                "identity_insolvency_ids": list(winner.get("insolvency_ids") or []),
                "identity_evidence_urls": [
                    item.get("source_url")
                    for item in winner.get("evidence") or []
                    if item.get("source_url")
                ],
                "identity_resolution_is_not_commercial_proof": True,
                "promotion_to_opportunity_allowed": False,
                "top5_eligible": False,
                "automatic_contact": False,
                "automatic_bid": False,
                "automatic_reservation": False,
                "automatic_purchase": False,
                "automatic_payment": False,
            }
        )
        signal["metadata"] = identity_meta
        resolution.update(
            {
                "status": winner.get("status"),
                "company_name": company_name,
                "entity_key": winner.get("entity_key"),
                "independent_domain_count": winner.get("independent_domain_count"),
                "official_rechtspraak_confirmed": winner.get("official_rechtspraak_confirmed"),
                "kvk_numbers": list(winner.get("kvk_numbers") or []),
                "insolvency_ids": list(winner.get("insolvency_ids") or []),
            }
        )
        resolved_count += 1
        if winner.get("official_rechtspraak_confirmed"):
            official_count += 1
        else:
            public_count += 1
        resolutions.append(resolution)

    status = "SUCCESS" if resolved_count else (
        "PARTIAL_RETRIEVAL" if search_errors and search_requests else "VALID_ZERO_NO_IDENTITIES_RESOLVED"
    )
    return {
        **base,
        "status": status,
        "block_reason": None,
        "processed_signal_count": processed,
        "resolved_identity_count": resolved_count,
        "officially_confirmed_identity_count": official_count,
        "corroborated_public_identity_count": public_count,
        "unresolved_identity_count": unresolved_count,
        "search_request_count": search_requests,
        "search_error_count": search_errors,
        "resolutions": resolutions,
        "enriched_signals": enriched,
        "errors": errors,
    }
