"""Bounded Brave radar for early clothing-market signals in NO, SE, and DE.

This module supplements the existing direct collectors and official-register
adapters.  It searches the public web for early closure, liquidation,
insolvency, warehouse-surplus, and auction signals, but it never promotes a
search result into an opportunity.  Accepted results are written as standalone
``MarketSignalRecord`` objects and flow through the existing SQLite signal
persistence and daily bulletin.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import parse_qs, parse_qsl, urlencode, urlsplit, urlunsplit

from opportunity_engine.discovery.brave_search import BraveSearchProvider
from opportunity_engine.discovery.search_provider import SearchHit, SearchProvider
from opportunity_engine.market_intelligence import (
    MarketSignalRecord,
    MarketSignalStatus,
    MarketSignalType,
)
from opportunity_engine.unified_models import Evidence


SCHEMA_VERSION = "brave-market-signal-radar-1.0"
SUPPORTED_MARKETS = ("NO", "SE", "DE")
DEFAULT_QUERIES_PER_MARKET = 2
DEFAULT_RESULTS_PER_QUERY = 10
DEFAULT_FRESHNESS = "pm"
MAX_QUERIES_PER_MARKET = 2
MAX_RESULTS_PER_QUERY = 10


@dataclass(frozen=True, slots=True)
class MarketRadarQuery:
    query_id: str
    query: str
    source_scope: str | None = None


MARKET_QUERIES: dict[str, tuple[MarketRadarQuery, ...]] = {
    "NO": (
        MarketRadarQuery(
            "no-closure-insolvency",
            '("opphørssalg" OR "avviklingssalg" OR "konkurssalg" OR konkurs OR nedleggelse) '
            '(klær OR klesbutikk OR tekstil OR arbeidsklær OR vernesko)',
        ),
        MarketRadarQuery(
            "no-surplus-auction",
            '("restlager" OR "varelager" OR "parti klær" OR lageroverskudd OR "lagersalg") '
            '(selges OR salg OR auksjon OR avvikling OR konkurs)',
        ),
    ),
    "SE": (
        MarketRadarQuery(
            "se-closure-insolvency",
            '("utförsäljning" OR "avvecklingsförsäljning" OR konkurs OR '
            'butiksstängning) (kläder OR klädbutik OR textil OR arbetskläder)',
        ),
        MarketRadarQuery(
            "se-surplus-auction",
            '(restlager OR varulager OR "parti kläder" OR lageröverskott) '
            '(säljes OR auktion OR avveckling)',
        ),
    ),
    "DE": (
        MarketRadarQuery(
            "de-closure-insolvency",
            '(Geschäftsauflösung OR Ladenauflösung OR Insolvenz OR '
            'Geschäftsaufgabe) (Bekleidung OR Modegeschäft OR Textilien OR '
            'Arbeitskleidung)',
        ),
        MarketRadarQuery(
            "de-surplus-auction",
            '(Restposten OR Warenbestand OR "Lagerbestand Kleidung" OR '
            'Lagerauflösung) (Verkauf OR Auktion OR Insolvenz)',
        ),
    ),
}

_NO_KONKSALG_SCOPE = "NO_KONKSALG_PUBLIC_POST"
_NO_CLEARANCE_MARKETPLACE_SCOPE = "NO_CLEARANCE_MARKETPLACE_PUBLIC_SALE"

# Two Norway-only source-focus requests supplement the six generic radar
# requests.  They remain signal-only and are intentionally separate so that
# Facebook indexing cannot crowd out FINN or Norsk Avvikling results.
SOURCE_FOCUS_QUERIES: dict[str, tuple[MarketRadarQuery, ...]] = {
    "NO": (
        MarketRadarQuery(
            "no-konksalg-public-clearance",
            'site:facebook.com/konksalg/posts '
            '("konkurssalg" OR "alt må bort" OR "alle varer" OR "få dager igjen") '
            '(arbeidsklær OR arbeidstøy OR klær OR tekstil OR vernesko OR bekledning)',
            source_scope=_NO_KONKSALG_SCOPE,
        ),
        MarketRadarQuery(
            "no-finn-norskavvikling-public-clearance",
            '(site:finn.no/recommerce/forsale/item OR '
            'site:norskavvikling.no/aktive-salg OR '
            'site:norskavvikling.no/produkt) '
            '("konkurssalg" OR "alt må bort" OR restlager OR varelager OR vareparti) '
            '(arbeidsklær OR arbeidstøy OR klær OR tekstil OR vernesko OR bekledning)',
            source_scope=_NO_CLEARANCE_MARKETPLACE_SCOPE,
        ),
    ),
    "SE": (),
    "DE": (),
}

_CLOTHING_TERMS: dict[str, tuple[str, ...]] = {
    "NO": (
        "klær",
        "klaer",
        "klesbutikk",
        "tekstil",
        "arbeidsklær",
        "arbeidsklaer",
        "arbeidstøy",
        "arbeidstoy",
        "vernesko",
        "sikkerhetssko",
        "bekledning",
        "mote",
    ),
    "SE": (
        "kläder",
        "klader",
        "klädbutik",
        "kladbutik",
        "textil",
        "arbetskläder",
        "arbetsklader",
        "mode",
    ),
    "DE": (
        "bekleidung",
        "modegeschäft",
        "modegeschaft",
        "textilien",
        "arbeitskleidung",
        "kleidung",
        "textil",
        "mode",
    ),
}

_INSOLVENCY_TERMS: dict[str, tuple[str, ...]] = {
    "NO": (
        "konkurs",
        "konkursbo",
        "konkurssalg",
        "insolvens",
        "tvangsavvikling",
        "likvidasjon",
    ),
    "SE": ("konkurs", "insolvens", "likvidation", "rekonstruktion"),
    "DE": ("insolvenz", "insolvenzverfahren", "liquidation", "konkurs"),
}
_CLOSURE_TERMS: dict[str, tuple[str, ...]] = {
    "NO": (
        "opphørssalg",
        "avviklingssalg",
        "lagersalg",
        "tømmesalg",
        "nedleggelse",
        "avvikling",
    ),
    "SE": (
        "utförsäljning",
        "utforsaljning",
        "avvecklingsförsäljning",
        "avvecklingsforsaljning",
        "butiksstängning",
        "butiksstangning",
        "avveckling",
    ),
    "DE": (
        "geschäftsauflösung",
        "geschaftsauflosung",
        "ladenauflösung",
        "ladenauflosung",
        "geschäftsaufgabe",
        "geschaftsaufgabe",
        "betriebsauflösung",
        "betriebsauflosung",
    ),
}
_SURPLUS_TERMS: dict[str, tuple[str, ...]] = {
    "NO": (
        "restlager",
        "varelager",
        "lagerbeholdning",
        "parti klær",
        "lageroverskudd",
        "lagersalg",
    ),
    "SE": ("restlager", "varulager", "parti kläder", "lageröverskott"),
    "DE": (
        "restposten",
        "warenbestand",
        "lagerbestand kleidung",
        "lagerauflösung",
        "lageraufloesung",
    ),
}
_AUCTION_TERMS: dict[str, tuple[str, ...]] = {
    "NO": ("auksjon", "tvangssalg"),
    "SE": ("auktion", "exekutiv försäljning", "exekutiv forsaljning"),
    "DE": ("auktion", "versteigerung", "zwangsversteigerung"),
}
_TRACKING_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ref",
    "source",
}

_NO_SOURCE_FOCUS_CLEARANCE_TERMS = (
    "alt må bort",
    "alle varer",
)
_FACEBOOK_KONKSALG_POST_PATH = re.compile(
    r"^/konksalg/posts/(?:[^/]+/)?(?:\d+|pfbid[a-z0-9_-]+)$",
    re.I,
)
_FINN_ITEM_PATH = re.compile(r"^/recommerce/forsale/item/\d+$", re.I)
_FINN_LEGACY_ITEM_PATH = re.compile(r"^/bap/forsale/ad\.html$", re.I)
_NORSK_AVVIKLING_PRODUCT_PATH = re.compile(r"^/produkt/[^/]+$", re.I)

_SOURCE_SCOPE_CHANNELS = {
    _NO_KONKSALG_SCOPE: frozenset({"KONKSALG_FACEBOOK"}),
    _NO_CLEARANCE_MARKETPLACE_SCOPE: frozenset(
        {"FINN_PUBLIC_ITEM", "NORSK_AVVIKLING_PUBLIC_SALE"}
    ),
}

ProviderFactory = Callable[[str, str, str | None], SearchProvider]


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _fold(value: object) -> str:
    return _compact(value).casefold()


def _iso_utc(value: datetime) -> str:
    normalized = value
    if normalized.tzinfo is None or normalized.utcoffset() is None:
        normalized = normalized.replace(tzinfo=timezone.utc)
    return normalized.astimezone(timezone.utc).isoformat()


def _safety_payload() -> dict[str, bool]:
    return {
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def _canonical_url(raw_url: str) -> str:
    parsed = urlsplit(raw_url)
    if parsed.scheme.casefold() != "https" or not parsed.netloc:
        raise ValueError("Brave radar accepts HTTPS result URLs only")
    filtered_query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.casefold().startswith("utm_")
        and key.casefold() not in _TRACKING_QUERY_KEYS
    ]
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit(
        (
            "https",
            parsed.netloc.casefold(),
            path,
            urlencode(filtered_query, doseq=True),
            "",
        )
    )


def _normalized_host(raw_host: str | None) -> str:
    host = (raw_host or "").casefold()
    for prefix in ("www.", "m."):
        if host.startswith(prefix):
            return host[len(prefix) :]
    return host


def _public_clearance_source_channel(canonical_url: str) -> str | None:
    """Identify only bounded public pages from the Norway source-focus lane."""
    parsed = urlsplit(canonical_url)
    host = _normalized_host(parsed.hostname)
    path = parsed.path or "/"

    if host == "facebook.com" and _FACEBOOK_KONKSALG_POST_PATH.fullmatch(path):
        return "KONKSALG_FACEBOOK"

    if host == "finn.no":
        if _FINN_ITEM_PATH.fullmatch(path):
            return "FINN_PUBLIC_ITEM"
        if _FINN_LEGACY_ITEM_PATH.fullmatch(path):
            finnkode = parse_qs(parsed.query).get("finnkode", ())
            if finnkode and finnkode[0].isdigit():
                return "FINN_PUBLIC_ITEM"
        return None

    if host == "norskavvikling.no":
        folded_path = path.casefold()
        if (
            folded_path in {"/aktive-salg", "/butikk"}
            or folded_path.startswith("/aktive-salg/")
            or _NORSK_AVVIKLING_PRODUCT_PATH.fullmatch(path)
        ):
            return "NORSK_AVVIKLING_PUBLIC_SALE"
    return None


def _selected_market_queries(
    market_code: str,
    queries_per_market: int,
) -> tuple[MarketRadarQuery, ...]:
    market = market_code.upper()
    return (
        *MARKET_QUERIES[market][:queries_per_market],
        *SOURCE_FOCUS_QUERIES.get(market, ()),
    )


def radar_query_budget_total(queries_per_market: int) -> int:
    """Return the exact generic plus source-focus request ceiling."""
    return sum(
        len(_selected_market_queries(market, queries_per_market))
        for market in SUPPORTED_MARKETS
    )


def _matched_terms(text: str, terms: Sequence[str]) -> list[str]:
    folded = text.casefold()
    return [term for term in terms if term.casefold() in folded]


def _classify_signal(
    market_code: str,
    text: str,
) -> tuple[MarketSignalType | None, list[str], list[str]]:
    clothing = _matched_terms(text, _CLOTHING_TERMS[market_code])
    if not clothing:
        return None, [], []

    categories = (
        (MarketSignalType.INSOLVENCY_OR_LIQUIDATION, _INSOLVENCY_TERMS[market_code]),
        (MarketSignalType.BUSINESS_CLOSURE, _CLOSURE_TERMS[market_code]),
        (MarketSignalType.WAREHOUSE_SURPLUS, _SURPLUS_TERMS[market_code]),
        (MarketSignalType.AUCTION_EVENT, _AUCTION_TERMS[market_code]),
    )
    for signal_type, terms in categories:
        matched = _matched_terms(text, terms)
        if matched:
            return signal_type, clothing, matched
    return None, clothing, []


def _confidence(
    *,
    title: str,
    market_code: str,
    clothing_terms: Sequence[str],
    event_terms: Sequence[str],
) -> float:
    title_folded = title.casefold()
    score = 0.55
    if any(term.casefold() in title_folded for term in clothing_terms):
        score += 0.05
    if any(term.casefold() in title_folded for term in event_terms):
        score += 0.05
    if len(set(event_terms)) > 1:
        score += 0.05
    if market_code in SUPPORTED_MARKETS:
        score += 0.02
    return min(0.72, score)


def market_signal_from_brave_hit(
    hit: SearchHit,
    *,
    market_code: str,
    query: MarketRadarQuery,
    rank: int,
    observed_at: datetime,
) -> MarketSignalRecord | None:
    """Convert one strict early-signal hit; ordinary listings remain rejected."""
    market = market_code.upper()
    if market not in SUPPORTED_MARKETS:
        raise ValueError(f"unsupported market: {market}")
    title = _compact(hit.title)
    description = _compact(hit.description)
    if not title:
        return None
    combined = f"{title} {description}".strip()
    signal_type, clothing_terms, event_terms = _classify_signal(market, combined)
    if signal_type is None and query.source_scope in _SOURCE_SCOPE_CHANNELS:
        # Source-focused public clearance pages may use the terse wording seen
        # in the Nærbø miss ("ALT MÅ BORT / ALLE VARER") without spelling out
        # insolvency in the indexed snippet. Clothing evidence is still
        # mandatory, so ordinary cross-category promotions remain rejected.
        clothing_terms = _matched_terms(combined, _CLOTHING_TERMS[market])
        event_terms = _matched_terms(combined, _NO_SOURCE_FOCUS_CLEARANCE_TERMS)
        if clothing_terms and event_terms:
            signal_type = MarketSignalType.WAREHOUSE_SURPLUS
    if signal_type is None:
        return None

    canonical_url = _canonical_url(_compact(hit.url))
    source_channel = _public_clearance_source_channel(canonical_url)
    if query.source_scope:
        allowed_channels = _SOURCE_SCOPE_CHANNELS.get(query.source_scope, frozenset())
        if source_channel not in allowed_channels:
            return None
    signal_id = (
        f"brave-radar:{market.casefold()}:"
        f"{sha256(canonical_url.encode('utf-8')).hexdigest()[:24]}"
    )
    value = description or title
    value = value[:500]
    evidence_value = combined[:4000]
    evidence_metadata: dict[str, Any] = {
        "query_id": query.query_id,
        "source_rank": rank,
        "provider": _compact(hit.provider) or "Brave Search",
        "verification_status": "UNVERIFIED_PUBLIC_WEB",
    }
    if source_channel:
        evidence_metadata["source_channel"] = source_channel
    evidence = Evidence(
        evidence_type="BRAVE_SEARCH_RESULT",
        value=evidence_value,
        source_url=canonical_url,
        captured_at=observed_at,
        verified=False,
        metadata=evidence_metadata,
    )
    return MarketSignalRecord(
        signal_id=signal_id,
        signal_type=signal_type,
        value=value,
        source="Brave Search market signal radar",
        observed_at=observed_at,
        confidence=_confidence(
            title=title,
            market_code=market,
            clothing_terms=clothing_terms,
            event_terms=event_terms,
        ),
        source_country=market,
        source_url=canonical_url,
        title=title[:1000],
        company_name=None,
        seller_name=None,
        location=None,
        first_observed_at=observed_at,
        latest_observed_at=observed_at,
        event_date=None,
        evidence=[evidence],
        related_opportunity_id=None,
        status=MarketSignalStatus.WATCH,
        metadata={
            "signal_only": True,
            "not_an_opportunity": True,
            "discovery_transport": "BRAVE_SEARCH",
            "verification_status": "UNVERIFIED_PUBLIC_WEB",
            "query_id": query.query_id,
            "query": query.query,
            "source_rank": rank,
            "clothing_terms": sorted(set(clothing_terms)),
            "event_terms": sorted(set(event_terms)),
            "canonical_url": canonical_url,
            **({"source_scope": query.source_scope} if query.source_scope else {}),
            **({"source_channel": source_channel} if source_channel else {}),
        },
    )


def _default_provider_factory(
    market_code: str,
    api_key: str,
    freshness: str | None,
) -> SearchProvider:
    return BraveSearchProvider(
        api_key,
        freshness=freshness,
        extra_snippets=True,
        operators=True,
        country=market_code,
    )


def _target_spec(
    manifest: Mapping[str, Any],
    market_code: str,
) -> Mapping[str, Any] | None:
    for item in manifest.get("sources") or []:
        if not isinstance(item, Mapping):
            continue
        if _compact(item.get("market_code")).upper() != market_code:
            continue
        if _compact(item.get("artifact_dir")):
            return item
    return None


def _existing_report(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(payload) if isinstance(payload, Mapping) else {}


def _write_merged_market_signal_report(
    path: Path,
    *,
    market_code: str,
    signals: Sequence[Mapping[str, Any]],
    observed_at: datetime,
) -> int:
    payload = _existing_report(path)
    merged: dict[str, dict[str, Any]] = {}
    existing = payload.get("signals")
    if isinstance(existing, Sequence) and not isinstance(existing, (str, bytes)):
        for item in existing:
            if not isinstance(item, Mapping):
                continue
            signal_id = _compact(item.get("signal_id"))
            if signal_id:
                merged[signal_id] = dict(item)
    for item in signals:
        signal_id = _compact(item.get("signal_id"))
        if signal_id:
            merged[signal_id] = dict(item)

    payload.update(
        {
            "schema_version": payload.get("schema_version")
            or "market-signal-report-1.0",
            "generated_at": _iso_utc(observed_at),
            "source_country": market_code,
            "signal_count": len(merged),
            "signals": [merged[key] for key in sorted(merged)],
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
    return len(merged)


def collect_manifest_brave_market_signals(
    manifest: Mapping[str, Any],
    *,
    root: str | Path = ".",
    observed_at: datetime | None = None,
    environment: Mapping[str, str] | None = None,
    provider_factory: ProviderFactory = _default_provider_factory,
    queries_per_market: int = DEFAULT_QUERIES_PER_MARKET,
    results_per_query: int = DEFAULT_RESULTS_PER_QUERY,
    freshness: str | None = DEFAULT_FRESHNESS,
) -> dict[str, Any]:
    """Search bounded generic and source-focus queries and merge signals."""
    if not 1 <= queries_per_market <= MAX_QUERIES_PER_MARKET:
        raise ValueError(
            f"queries_per_market must be between 1 and {MAX_QUERIES_PER_MARKET}"
        )
    if not 1 <= results_per_query <= MAX_RESULTS_PER_QUERY:
        raise ValueError(
            f"results_per_query must be between 1 and {MAX_RESULTS_PER_QUERY}"
        )

    now = observed_at or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    env = environment if environment is not None else os.environ
    api_key = _compact(env.get("BRAVE_SEARCH_API_KEY")) or _compact(
        env.get("BRAVE_API_KEY")
    )
    root_path = Path(root)
    market_reports: list[dict[str, Any]] = []
    request_count = 0

    for market_code in SUPPORTED_MARKETS:
        target = _target_spec(manifest, market_code)
        selected_queries = _selected_market_queries(
            market_code,
            queries_per_market,
        )
        generic_query_budget = len(MARKET_QUERIES[market_code][:queries_per_market])
        source_focus_query_budget = len(SOURCE_FOCUS_QUERIES.get(market_code, ()))
        common: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "source": "Brave Search market signal radar",
            "source_country": market_code,
            "freshness": freshness,
            "query_budget": len(selected_queries),
            "generic_query_budget": generic_query_budget,
            "source_focus_query_budget": source_focus_query_budget,
            "results_per_query": results_per_query,
            "queries_attempted": 0,
            "queries_succeeded": 0,
            "accepted_signal_count": 0,
            "rejected_result_count": 0,
            "duplicate_result_count": 0,
            "signals": [],
            "errors": [],
            **_safety_payload(),
        }
        if target is None:
            common["status"] = "BLOCKED_CONFIGURATION"
            common["block_reason"] = "MARKET_ARTIFACT_DIRECTORY_MISSING"
            market_reports.append(common)
            continue
        if not api_key:
            common["status"] = "BLOCKED_CONFIGURATION"
            common["block_reason"] = "BRAVE_SEARCH_API_KEY_MISSING"
            market_reports.append(common)
            continue

        try:
            provider = provider_factory(market_code, api_key, freshness)
        except Exception as exc:
            common["status"] = "BLOCKED_RETRIEVAL"
            common["block_reason"] = "PROVIDER_INITIALIZATION_FAILED"
            common["errors"] = [f"{type(exc).__name__}: {_compact(exc)[:300]}"]
            market_reports.append(common)
            continue

        accepted: dict[str, dict[str, Any]] = {}
        seen_urls: set[str] = set()
        errors: list[str] = []
        rejected = 0
        duplicates = 0
        succeeded = 0
        for query in selected_queries:
            common["queries_attempted"] = int(common["queries_attempted"]) + 1
            request_count += 1
            try:
                hits = provider.search(query.query, count=results_per_query)
                succeeded += 1
            except Exception as exc:
                errors.append(
                    f"{query.query_id}: {type(exc).__name__}: {_compact(exc)[:300]}"
                )
                continue
            for rank, hit in enumerate(hits, start=1):
                if not isinstance(hit, SearchHit):
                    rejected += 1
                    continue
                try:
                    canonical_url = _canonical_url(_compact(hit.url))
                except ValueError:
                    rejected += 1
                    continue
                if canonical_url in seen_urls:
                    duplicates += 1
                    continue
                signal = market_signal_from_brave_hit(
                    hit,
                    market_code=market_code,
                    query=query,
                    rank=rank,
                    observed_at=now,
                )
                if signal is None:
                    rejected += 1
                    continue
                seen_urls.add(canonical_url)
                accepted[signal.signal_id] = signal.model_dump(mode="json")

        common["queries_succeeded"] = succeeded
        common["accepted_signal_count"] = len(accepted)
        common["rejected_result_count"] = rejected
        common["duplicate_result_count"] = duplicates
        common["signals"] = [accepted[key] for key in sorted(accepted)]
        common["errors"] = errors
        if errors:
            common["status"] = "PARTIAL_RETRIEVAL" if succeeded else "BLOCKED_RETRIEVAL"
        else:
            common["status"] = "SUCCESS" if accepted else "VALID_ZERO"
        common["block_reason"] = None

        artifact_dir = root_path / _compact(target.get("artifact_dir"))
        report_path = artifact_dir / _compact(
            target.get("market_signal_report_file") or "market-signal-report.json"
        )
        common["stored_signal_count"] = _write_merged_market_signal_report(
            report_path,
            market_code=market_code,
            signals=common["signals"],
            observed_at=now,
        )
        common["artifact_path"] = report_path.relative_to(root_path).as_posix()
        market_reports.append(common)

    status_counts: dict[str, int] = {}
    for report in market_reports:
        status = _compact(report.get("status")).upper() or "UNKNOWN"
        status_counts[status] = status_counts.get(status, 0) + 1

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _iso_utc(now),
        "retrieval_transport": "BRAVE_SEARCH",
        "market_coverage": list(SUPPORTED_MARKETS),
        "market_count": len(market_reports),
        "query_budget_total": radar_query_budget_total(queries_per_market),
        "source_focus_query_budget_total": sum(
            len(SOURCE_FOCUS_QUERIES.get(market, ()))
            for market in SUPPORTED_MARKETS
        ),
        "requests_made": request_count,
        "results_per_query": results_per_query,
        "freshness": freshness,
        "status_counts": status_counts,
        "sources": market_reports,
        "signal_count": sum(
            int(report.get("accepted_signal_count") or 0)
            for report in market_reports
        ),
        **_safety_payload(),
    }
