"""Targeted public-web search for sale listings and liquidation channels.

The search starts from one manually selected, already-enriched bankruptcy estate.
It uses exact company identities to find candidate pages that may disclose an
inventory sale, auction, liquidator, or sale agent. Search snippets are candidate
evidence only; they never confirm a sale or liquidation mandate.

FINN results are retained for manual review only and are never opened here. No
login, contact, bid, purchase, reservation, payment, or automatic investment
decision is performed.
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import urlparse

from opportunity_engine.discovery.estate_manager_enrichment_pilot import (
    EstateManagerEnrichment,
)
from opportunity_engine.discovery.search_provider import SearchHit, SearchProvider

MAX_QUERY_COUNT = 5
DEFAULT_RESULTS_PER_QUERY = 10
MAX_RESULTS_PER_QUERY = 20

_RESTRICTED_MANUAL_DOMAINS = frozenset({"finn.no", "www.finn.no"})
_KNOWN_SALE_CHANNEL_DOMAINS = frozenset(
    {
        "auksjonen.no",
        "ny.auksjonen.no",
        "vareauksjonen.no",
        "www.vareauksjonen.no",
        "auksjoner.no",
        "www.auksjoner.no",
        "bjaroy.no",
        "www.bjaroy.no",
        "cupo.no",
        "www.cupo.no",
        "miko-trading.no",
        "www.miko-trading.no",
        "altpasalg.no",
        "www.altpasalg.no",
        "norskavvikling.no",
        "www.norskavvikling.no",
    }
)
_SALE_SIGNAL = re.compile(
    r"\b(auksjon|auksjoner|selges|salg|bud|budrunde|vareparti|restlager|"
    r"varelager|lagerbeholdning|opphørssalg|avviklingssalg|tømmesalg|"
    r"parti\s+med\s+klær|kleslager)\b",
    re.I,
)
_LIQUIDATION_SIGNAL = re.compile(
    r"\b(bostyrer|bobestyrer|boet|konkursbo|avvikling|avviklingsselskap|"
    r"på\s+vegne\s+av|oppdrag\s+for|realiseres|realisation|liquidator|"
    r"tvangssalg)\b",
    re.I,
)
_LEGAL_SUFFIX_PATTERN = re.compile(
    r"\b(?:AS|ASA|KONKURSBO|TVANGSAVVIKLINGSBO|BOET|KONKURS)\b",
    re.I,
)


def _compact(value: object) -> str:
    return " ".join(str(value or "").split())


def _digits(value: object) -> str:
    return re.sub(r"\D", "", str(value or ""))


def normalize_entity_name(value: object) -> str:
    text = unicodedata.normalize("NFKD", _compact(value)).encode(
        "ascii", "ignore"
    ).decode("ascii")
    text = _LEGAL_SUFFIX_PATTERN.sub(" ", text)
    text = re.sub(r"[^A-Za-z0-9]+", " ", text).upper()
    return " ".join(text.split())


def _quoted(value: str) -> str:
    return f'"{_compact(value).replace(chr(34), "")}"'


def build_sale_channel_queries(
    enrichment: EstateManagerEnrichment,
) -> tuple[str, ...]:
    """Build five exact-identity queries for one reviewed estate."""
    debtor = _quoted(enrichment.debtor_name)
    estate = _quoted(enrichment.estate_name)
    debtor_orgnr = _quoted(enrichment.debtor_orgnr)
    estate_orgnr = _quoted(enrichment.estate_orgnr)
    return (
        f"{debtor} (konkursbo OR varelager OR vareparti OR restlager OR "
        "auksjon OR selges)",
        f"{estate} (salg OR auksjon OR vareparti OR varelager)",
        f"{debtor_orgnr} OR {estate_orgnr}",
        f'{debtor} (bostyrer OR boet OR avvikling OR "på vegne av")',
        f"{debtor} (site:auksjonen.no OR site:vareauksjonen.no OR "
        "site:auksjoner.no OR site:finn.no)",
    )


def _hostname(url: str) -> str | None:
    parsed = urlparse(_compact(url))
    if parsed.scheme != "https" or not parsed.hostname:
        return None
    return parsed.hostname.casefold()


def _identity_match(
    corpus: str,
    enrichment: EstateManagerEnrichment,
) -> tuple[bool, str]:
    digits = _digits(corpus)
    if enrichment.estate_orgnr in digits or enrichment.debtor_orgnr in digits:
        return True, "EXACT_ORGANISATION_NUMBER"

    normalized = normalize_entity_name(corpus)
    names = {
        normalize_entity_name(enrichment.debtor_name),
        normalize_entity_name(enrichment.estate_name),
    }
    names.discard("")
    if any(name in normalized for name in names):
        return True, "EXACT_NORMALIZED_COMPANY_NAME"
    return False, "NONE"


@dataclass(frozen=True, slots=True)
class SaleChannelCandidate:
    title: str
    url: str
    description: str
    provider: str
    query: str
    hostname: str
    identity_match_method: str
    sale_signal: bool
    liquidation_signal: bool
    known_sale_channel_domain: bool
    manual_only_restricted_source: bool
    candidate_state: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "description": self.description,
            "provider": self.provider,
            "query": self.query,
            "hostname": self.hostname,
            "identity_match_method": self.identity_match_method,
            "sale_signal": self.sale_signal,
            "liquidation_signal": self.liquidation_signal,
            "known_sale_channel_domain": self.known_sale_channel_domain,
            "manual_only_restricted_source": self.manual_only_restricted_source,
            "collection_mode": (
                "MANUAL_REVIEW_ONLY"
                if self.manual_only_restricted_source
                else "PUBLIC_PAGE_VERIFICATION_REQUIRED"
            ),
            "candidate_state": self.candidate_state,
            "page_verified": False,
            "public_sale_found": False,
            "inventory_sale_verified": False,
            "liquidation_channel_verified": False,
            "listing_status": "UNKNOWN",
            "top5_eligible": False,
            "analysis_eligible": False,
            "automatic_page_open": False,
            "automatic_contact": False,
            "automatic_bid": False,
            "automatic_purchase_decision": False,
            "automatic_payment": False,
        }


@dataclass(frozen=True, slots=True)
class SaleChannelSearchResult:
    captured_at: str
    estate: EstateManagerEnrichment
    queries: tuple[str, ...]
    requests_made: int
    raw_hits: int
    candidates: tuple[SaleChannelCandidate, ...]
    errors: tuple[dict[str, str], ...] = ()

    @property
    def sale_listing_candidates(self) -> tuple[SaleChannelCandidate, ...]:
        return tuple(
            item
            for item in self.candidates
            if item.candidate_state
            == "SALE_LISTING_CANDIDATE_REQUIRES_PAGE_VERIFICATION"
        )

    @property
    def liquidation_channel_candidates(self) -> tuple[SaleChannelCandidate, ...]:
        return tuple(
            item
            for item in self.candidates
            if item.candidate_state
            == "LIQUIDATION_CHANNEL_CANDIDATE_REQUIRES_PAGE_VERIFICATION"
        )

    @property
    def scan_complete(self) -> bool:
        return not self.errors and self.requests_made == len(self.queries)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "pre-market-sale-channel-search-1.0",
            "captured_at": self.captured_at,
            "estate": self.estate.to_dict(),
            "queries": list(self.queries),
            "requests_made": self.requests_made,
            "raw_hits": self.raw_hits,
            "candidate_count": len(self.candidates),
            "sale_listing_candidate_count": len(self.sale_listing_candidates),
            "liquidation_channel_candidate_count": len(
                self.liquidation_channel_candidates
            ),
            "scan_complete": self.scan_complete,
            "candidates": [item.to_dict() for item in self.candidates],
            "errors": list(self.errors),
            "search_snippets_confirm_sale": False,
            "public_sale_found": False,
            "inventory_sale_verified": False,
            "liquidation_channel_verified": False,
            "commercial_top5_count": 0,
            "automatic_contact": False,
            "automatic_bid": False,
            "automatic_purchase_decision": False,
            "automatic_payment": False,
        }


def classify_search_hit(
    hit: SearchHit,
    *,
    query: str,
    enrichment: EstateManagerEnrichment,
) -> SaleChannelCandidate | None:
    hostname = _hostname(hit.url)
    if hostname is None:
        return None

    identity_corpus = _compact(f"{hit.title} {hit.description} {hit.url}")
    matched, method = _identity_match(identity_corpus, enrichment)
    if not matched:
        return None

    signal_corpus = _compact(f"{hit.title} {hit.description}")
    sale_signal = bool(_SALE_SIGNAL.search(signal_corpus))
    liquidation_signal = bool(_LIQUIDATION_SIGNAL.search(signal_corpus))
    known_channel = hostname in _KNOWN_SALE_CHANNEL_DOMAINS
    restricted = hostname in _RESTRICTED_MANUAL_DOMAINS

    if sale_signal or known_channel or restricted:
        state = "SALE_LISTING_CANDIDATE_REQUIRES_PAGE_VERIFICATION"
    elif liquidation_signal:
        state = "LIQUIDATION_CHANNEL_CANDIDATE_REQUIRES_PAGE_VERIFICATION"
    else:
        state = "IDENTITY_REFERENCE_ONLY"

    return SaleChannelCandidate(
        title=_compact(hit.title),
        url=_compact(hit.url),
        description=_compact(hit.description),
        provider=_compact(hit.provider),
        query=query,
        hostname=hostname,
        identity_match_method=method,
        sale_signal=sale_signal,
        liquidation_signal=liquidation_signal,
        known_sale_channel_domain=known_channel,
        manual_only_restricted_source=restricted,
        candidate_state=state,
    )


def run_sale_channel_search(
    enrichment: EstateManagerEnrichment,
    provider: SearchProvider,
    *,
    results_per_query: int = DEFAULT_RESULTS_PER_QUERY,
) -> SaleChannelSearchResult:
    if not 1 <= results_per_query <= MAX_RESULTS_PER_QUERY:
        raise ValueError(
            f"results_per_query must be between 1 and {MAX_RESULTS_PER_QUERY}"
        )

    queries = build_sale_channel_queries(enrichment)
    if len(queries) > MAX_QUERY_COUNT:
        raise RuntimeError("query pack exceeds the approved request budget")

    errors: list[dict[str, str]] = []
    by_url: dict[str, SaleChannelCandidate] = {}
    requests_made = 0
    raw_hits = 0

    for query in queries:
        try:
            hits: Sequence[SearchHit] = provider.search(
                query,
                count=results_per_query,
            )
            requests_made += 1
            raw_hits += len(hits)
            for hit in hits:
                candidate = classify_search_hit(
                    hit,
                    query=query,
                    enrichment=enrichment,
                )
                if candidate is None:
                    continue
                existing = by_url.get(candidate.url)
                if existing is None or (
                    existing.candidate_state == "IDENTITY_REFERENCE_ONLY"
                    and candidate.candidate_state != "IDENTITY_REFERENCE_ONLY"
                ):
                    by_url[candidate.url] = candidate
        except Exception as exc:
            errors.append({"query": query, "error": str(exc)})

    rank = {
        "SALE_LISTING_CANDIDATE_REQUIRES_PAGE_VERIFICATION": 0,
        "LIQUIDATION_CHANNEL_CANDIDATE_REQUIRES_PAGE_VERIFICATION": 1,
        "IDENTITY_REFERENCE_ONLY": 2,
    }
    candidates = tuple(
        sorted(
            by_url.values(),
            key=lambda item: (
                rank[item.candidate_state],
                0
                if item.identity_match_method == "EXACT_ORGANISATION_NUMBER"
                else 1,
                item.hostname,
                item.url,
            ),
        )
    )
    return SaleChannelSearchResult(
        captured_at=datetime.now(timezone.utc).isoformat(),
        estate=enrichment,
        queries=queries,
        requests_made=requests_made,
        raw_hits=raw_hits,
        candidates=candidates,
        errors=tuple(errors),
    )


def write_sale_channel_artifacts(
    result: SaleChannelSearchResult,
    output_dir: str | Path,
) -> dict[str, Path]:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    report_path = target / "sale-channel-search.json"
    sale_path = target / "sale-listing-candidates.json"
    liquidator_path = target / "liquidation-channel-candidates.json"
    commercial_path = target / "live-clothing-top5.json"
    summary_path = target / "operator-summary.txt"

    report_path.write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    sale_path.write_text(
        json.dumps(
            [item.to_dict() for item in result.sale_listing_candidates],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    liquidator_path.write_text(
        json.dumps(
            [item.to_dict() for item in result.liquidation_channel_candidates],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    commercial_path.write_text("[]\n", encoding="utf-8")

    lines = [
        "Pre-market sale listing and liquidation-channel search",
        f"Estate: {result.estate.estate_name} ({result.estate.estate_orgnr})",
        f"Debtor: {result.estate.debtor_name} ({result.estate.debtor_orgnr})",
        f"Queries: {len(result.queries)}",
        f"Requests made: {result.requests_made}",
        f"Raw hits: {result.raw_hits}",
        f"Identity-matched candidates: {len(result.candidates)}",
        f"Sale-listing candidates: {len(result.sale_listing_candidates)}",
        "Liquidation-channel candidates: "
        f"{len(result.liquidation_channel_candidates)}",
        f"Scan complete: {result.scan_complete}",
        f"Errors: {len(result.errors)}",
        "Search snippets confirm a sale: false",
        "Public sale found: false",
        "Verified inventory sale: false",
        "Commercial Top 5 count: 0",
        "Automatic page open/contact/bid/purchase/payment: false",
        "",
    ]
    review = (
        *result.sale_listing_candidates,
        *result.liquidation_channel_candidates,
    )
    if review:
        lines.append("Highest-priority candidates requiring page verification:")
        for item in review[:10]:
            lines.append(
                f"- {item.candidate_state} | {item.title} | "
                f"{item.hostname} | {item.url}"
            )
    else:
        lines.append("No sale-listing or liquidation-channel candidate was found.")

    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "report": report_path,
        "sale_candidates": sale_path,
        "liquidation_candidates": liquidator_path,
        "commercial_top5": commercial_path,
        "summary": summary_path,
    }
