#!/usr/bin/env python3
"""Chase Norwegian sale links from official bankruptcy events only.

The order is intentionally strict: an official Brønnøysund bankruptcy event
comes first, paid search follows that exact company, and a public page is kept
only when it independently contains bankruptcy language, the official company
identity and sale language. Liquidation-only, surplus-only, dealer, generic
marketplace and ended pages never become links for review.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlsplit, urlunsplit

import requests

from opportunity_engine.discovery.brave_search import BraveSearchProvider
from opportunity_engine.discovery.exa_search import ExaSearchProvider
from opportunity_engine.discovery.search_provider import SearchHit, SearchProvider


SCHEMA_VERSION = "norway-bankruptcy-link-hunt-1.0"
EVENT_SCHEMA = "norway-insolvency-event-sample-1"
EVENT_SCOPE = "NO_ONLY_OFFICIAL_BANKRUPTCY_ALL_SECTORS"
MAX_RESPONSE_BYTES = 1_500_000
MAX_REJECTED_HITS = 60

BANKRUPTCY = re.compile(
    r"\bkonkurs(?:bo(?:et|ets)?|salg|auksjon|rammet|behandling)?\b",
    re.IGNORECASE,
)
LIQUIDATION_OR_SURPLUS = re.compile(
    r"\b(?:avvikling|tvangsavvikling|tvangsoppl[øo]sning|opph[øo]rssalg|"
    r"t[øo]mmesalg|overskuddsvarer|overskuddslager|restlager)\b",
    re.IGNORECASE,
)
TRADER = re.compile(
    r"\b(?:grossist|engros|forhandler|partivarer|partihandel)\b",
    re.IGNORECASE,
)
SALE = re.compile(
    r"\b(?:auksjon(?:en|er)?|selges|salg|bud(?:runde|givning)?|gi\s+bud|"
    r"varelager|driftsmidler|inventar|eiendeler|maskiner|utstyr)\b",
    re.IGNORECASE,
)
ESTATE_SALE_RELATION = re.compile(
    r"(?:selges|auksjoneres|til\s+salg)\s+"
    r"(?:av|fra|p[åa]\s+vegne\s+av)\s+(?:(?:et|ett|denne)\s+)?konkursbo"
    r"|konkursbo(?:et|ets)?\s+(?:etter\s+.{0,120}?\s+)?"
    r"(?:selger|selges|auksjonerer|auksjoneres)"
    r"|boets\s+(?:eiendeler|driftsmidler|inventar|varelager)\s+"
    r"(?:selges|auksjoneres)",
    re.IGNORECASE,
)
ENDED = re.compile(
    r"\b(?:auksjonen\s+er\s+avsluttet|budrunden\s+er\s+avsluttet|"
    r"denne\s+auksjonen\s+er\s+n[åa]\s+ferdig|salget\s+er\s+avsluttet|"
    r"objektet\s+er\s+solgt|auksjon\s+avsluttet|utl[øo]pt|lukket|solgt)\b",
    re.IGNORECASE,
)

NON_SALE_HOSTS = frozenset(
    {
        "brreg.no",
        "proff.no",
        "purehelp.no",
        "gulesider.no",
        "firmalisten.no",
    }
)
KNOWN_SALE_HOSTS = frozenset(
    {
        "auksjonen.no",
        "vareauksjonen.no",
        "norskavvikling.no",
        "finn.no",
    }
)
GENERIC_INDEX_PATHS = frozenset(
    {
        "/",
        "/butikk/",
        "/auksjoner/torget/vareparti-og-konkursbo",
        "/auksjoner/torget/vareparti-og-konkursbo/",
    }
)


class _VisibleText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.title_parts: list[str] = []
        self._skip = 0
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip += 1
        if tag == "title":
            self._in_title = True

    def handle_data(self, value: str) -> None:
        if self._skip:
            return
        self.parts.append(value)
        if self._in_title:
            self.title_parts.append(value)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._skip:
            self._skip -= 1
        if tag == "title":
            self._in_title = False


@dataclass(frozen=True, slots=True)
class PageEvidence:
    title: str
    text: str


PageLoader = Callable[[str], str]


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _fold(value: object) -> str:
    text = _compact(value).casefold()
    for source, target in (
        ("å", "a"),
        ("ä", "a"),
        ("æ", "ae"),
        ("ö", "o"),
        ("ø", "o"),
        ("é", "e"),
    ):
        text = text.replace(source, target)
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _safe_norwegian_url(raw: object) -> str | None:
    if not isinstance(raw, str):
        return None
    try:
        parsed = urlsplit(raw.strip())
        host = (parsed.hostname or "").casefold().rstrip(".")
        port = parsed.port
    except ValueError:
        return None
    if (
        parsed.scheme.casefold() != "https"
        or not host.endswith(".no")
        or parsed.username
        or parsed.password
        or port not in (None, 443)
        or not parsed.path.startswith("/")
        or len(raw) > 2_000
    ):
        return None
    netloc = host if port is None else f"{host}:{port}"
    return urlunsplit(("https", netloc, parsed.path or "/", parsed.query, ""))


def _host_matches(host: str, domain: str) -> bool:
    return host == domain or host.endswith("." + domain)


def _public_dns(host: str) -> bool:
    """Reject hosts resolving to any non-public address before a page read."""
    try:
        addresses = {
            item[4][0]
            for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        }
    except OSError:
        return False
    if not addresses:
        return False
    try:
        return all(ipaddress.ip_address(address).is_global for address in addresses)
    except ValueError:
        return False


def fetch_public_html(url: str) -> str:
    safe = _safe_norwegian_url(url)
    if safe != url:
        raise ValueError("Only normalized Norwegian HTTPS URLs are allowed")
    host = (urlsplit(url).hostname or "").casefold()
    if not _public_dns(host):
        raise RuntimeError("Norwegian host did not resolve exclusively to public addresses")
    response = requests.get(
        url,
        timeout=15,
        allow_redirects=False,
        stream=True,
        headers={
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": "OpportunityEngine-Norway-Bankruptcy-Link-Hunt/1.0",
        },
    )
    try:
        response.raise_for_status()
        if response.is_redirect or 300 <= response.status_code < 400:
            raise RuntimeError("Redirects are not followed by the bounded verifier")
        content_type = response.headers.get("content-type", "").casefold()
        if "html" not in content_type:
            raise RuntimeError("Public result is not HTML")
        chunks: list[bytes] = []
        size = 0
        for chunk in response.iter_content(chunk_size=65_536):
            size += len(chunk)
            if size > MAX_RESPONSE_BYTES:
                raise RuntimeError("Public result exceeded the response-size cap")
            chunks.append(chunk)
        return b"".join(chunks).decode(response.encoding or "utf-8", errors="replace")
    finally:
        response.close()


def _page_evidence(html: str) -> PageEvidence:
    parser = _VisibleText()
    parser.feed(html[:MAX_RESPONSE_BYTES])
    return PageEvidence(
        title=_compact(" ".join(parser.title_parts))[:500],
        text=_compact(" ".join(parser.parts))[:120_000],
    )


def _event_identity(event: Mapping[str, Any]) -> tuple[str, str]:
    organisation_number = _compact(event.get("organisation_number"))
    company_name = _compact(event.get("company_name"))
    official_url = _compact(event.get("official_url"))
    if (
        event.get("source_country") != "NO"
        or event.get("event_kinds") != ["konkurs"]
        or len(organisation_number) != 9
        or not organisation_number.isascii()
        or not organisation_number.isdigit()
        or not company_name
        or official_url
        != "https://data.brreg.no/enhetsregisteret/api/enheter/"
        + organisation_number
    ):
        raise ValueError("Every search event must be one official Norwegian bankruptcy")
    return organisation_number, company_name


def _identity_method(text: str, organisation_number: str, company_name: str) -> str | None:
    digits = re.sub(r"\D", "", text)
    if organisation_number in digits:
        return "OFFICIAL_ORGANISATION_NUMBER_ON_PAGE"
    folded_text = _fold(text)
    full_name = _fold(company_name)
    if full_name and full_name in folded_text:
        return "OFFICIAL_COMPANY_NAME_ON_PAGE"
    core_name = re.sub(r"\s+(?:as|asa|enk|nuf|ans|da)$", "", full_name).strip()
    if len(core_name) >= 7 and core_name in folded_text:
        return "OFFICIAL_COMPANY_CORE_NAME_ON_PAGE"
    return None


def _url_precheck(url: str) -> str | None:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").casefold()
    if any(_host_matches(host, domain) for domain in NON_SALE_HOSTS):
        return "COMPANY_DIRECTORY_NOT_SALE_PAGE"
    if parsed.path.casefold() in GENERIC_INDEX_PATHS:
        return "GENERIC_INDEX_NOT_EXACT_SALE_PAGE"
    return None


def _known_sale_detail(url: str) -> bool:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").casefold()
    path = parsed.path
    if not any(_host_matches(host, domain) for domain in KNOWN_SALE_HOSTS):
        return False
    if _host_matches(host, "auksjonen.no"):
        return bool(
            re.fullmatch(
                r"/auksjon/(?:torget|overskuddsvarer)/[^/]+/\d{4,}/?",
                path,
                re.IGNORECASE,
            )
        )
    if _host_matches(host, "vareauksjonen.no"):
        return bool(
            re.fullmatch(
                r"/Event/(?:LotDetails|Details)/\d{4,}(?:/[a-z0-9_%.-]+){0,3}/?",
                path,
                re.IGNORECASE,
            )
        )
    if _host_matches(host, "norskavvikling.no"):
        return bool(re.fullmatch(r"/produkt/[a-z0-9-]+/?", path, re.IGNORECASE))
    if _host_matches(host, "finn.no"):
        return bool(
            re.fullmatch(
                r"/(?:recommerce/forsale/item/)?\d{6,}/?",
                path,
                re.IGNORECASE,
            )
        )
    return False


def _page_rejection(
    page: PageEvidence,
    *,
    hit: SearchHit,
    organisation_number: str,
    company_name: str,
) -> tuple[str | None, str | None]:
    page_text = _compact(f"{page.title} {page.text}")
    if not BANKRUPTCY.search(page_text):
        if LIQUIDATION_OR_SURPLUS.search(page_text) or TRADER.search(page_text):
            return "LIQUIDATION_SURPLUS_OR_TRADER_NOT_BANKRUPTCY", None
        return "NO_EXPLICIT_BANKRUPTCY_LANGUAGE_ON_PAGE", None
    identity_method = _identity_method(page_text, organisation_number, company_name)
    if identity_method is None:
        return "OFFICIAL_BANKRUPT_COMPANY_NOT_IDENTIFIED_ON_PAGE", None
    if not SALE.search(page_text):
        return "NO_ASSET_SALE_LANGUAGE_ON_PAGE", None
    if ENDED.search(page_text):
        return "SALE_PAGE_EXPLICITLY_ENDED", None
    if not ESTATE_SALE_RELATION.search(page_text):
        return "NO_EXPLICIT_BANKRUPTCY_ESTATE_SALE_RELATION", None
    if not _compact(hit.title):
        return "SEARCH_RESULT_WITHOUT_TITLE", None
    return None, identity_method


def _search_query(company_name: str) -> str:
    return (
        f'"{company_name}" konkursbo '
        "(auksjon OR selges OR varelager OR driftsmidler OR inventar)"
    )


def _provider_name(provider: SearchProvider) -> str:
    return _compact(getattr(provider, "name", "Search provider")) or "Search provider"


def hunt_bankruptcy_links(
    events_report: Mapping[str, Any],
    *,
    exa: SearchProvider | None,
    brave: SearchProvider | None,
    loader: PageLoader = fetch_public_html,
    max_events: int = 5,
    results_per_query: int = 5,
    max_page_reads: int = 15,
    now: datetime | None = None,
) -> dict[str, Any]:
    if events_report.get("schema_version") != EVENT_SCHEMA:
        raise ValueError("Official Norway bankruptcy event report is required")
    if events_report.get("scope") != EVENT_SCOPE:
        raise ValueError("Liquidation or mixed insolvency input is forbidden")
    if not 1 <= max_events <= 5:
        raise ValueError("max_events must be between 1 and 5")
    if not 1 <= results_per_query <= 5:
        raise ValueError("results_per_query must be between 1 and 5")
    if not 1 <= max_page_reads <= 15:
        raise ValueError("max_page_reads must be between 1 and 15")
    raw_events = events_report.get("events")
    if not isinstance(raw_events, list):
        raise ValueError("Official event report must contain an events list")

    events: list[dict[str, Any]] = []
    for raw_event in raw_events[:max_events]:
        if not isinstance(raw_event, Mapping):
            raise ValueError("Invalid official event row")
        _event_identity(raw_event)
        events.append(dict(raw_event))

    captured_at = (now or datetime.now(timezone.utc)).isoformat()
    links: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    provider_errors: list[dict[str, str]] = []
    request_counts: dict[str, int] = {"Exa": 0, "Brave Search": 0}
    seen_event_urls: set[tuple[str, str]] = set()
    page_reads = 0
    searched_events = 0

    def reject(*, event: Mapping[str, Any], hit: SearchHit, reason: str) -> None:
        if len(rejected) >= MAX_REJECTED_HITS:
            return
        rejected.append(
            {
                "organisation_number": event["organisation_number"],
                "company_name": event["company_name"],
                "url": hit.url,
                "provider": hit.provider or "UNKNOWN",
                "reason": reason,
            }
        )

    def inspect_hits(event: Mapping[str, Any], hits: Sequence[SearchHit]) -> int:
        nonlocal page_reads
        organisation_number, company_name = _event_identity(event)
        accepted_before = len(links)
        for hit in hits:
            if len(links) - accepted_before >= 2:
                break
            safe_url = _safe_norwegian_url(hit.url)
            if safe_url is None:
                reject(event=event, hit=hit, reason="NON_NORWEGIAN_OR_UNSAFE_URL")
                continue
            event_url = (organisation_number, safe_url)
            if event_url in seen_event_urls:
                reject(event=event, hit=hit, reason="DUPLICATE_URL")
                continue
            seen_event_urls.add(event_url)
            precheck = _url_precheck(safe_url)
            if precheck:
                reject(event=event, hit=hit, reason=precheck)
                continue
            snippet = _compact(f"{hit.title} {hit.description}")
            if not BANKRUPTCY.search(snippet) and not _known_sale_detail(safe_url):
                if LIQUIDATION_OR_SURPLUS.search(snippet) or TRADER.search(snippet):
                    reject(
                        event=event,
                        hit=hit,
                        reason="SEARCH_RESULT_IS_LIQUIDATION_SURPLUS_OR_TRADER",
                    )
                else:
                    reject(event=event, hit=hit, reason="SEARCH_RESULT_HAS_NO_BANKRUPTCY_SIGNAL")
                continue
            if page_reads >= max_page_reads:
                reject(event=event, hit=hit, reason="PAGE_READ_BUDGET_EXHAUSTED")
                continue
            page_reads += 1
            try:
                page = _page_evidence(loader(safe_url))
            except Exception as exc:
                reject(
                    event=event,
                    hit=hit,
                    reason=f"PAGE_READ_FAILED:{type(exc).__name__}",
                )
                continue
            reason, identity_method = _page_rejection(
                page,
                hit=hit,
                organisation_number=organisation_number,
                company_name=company_name,
            )
            if reason:
                reject(event=event, hit=hit, reason=reason)
                continue
            links.append(
                {
                    "classification": "OFFICIAL_BANKRUPTCY_LINKED_ASSET_SALE",
                    "company_name": company_name,
                    "organisation_number": organisation_number,
                    "event_kind": "KONKURS",
                    "event_date": event.get("event_date"),
                    "location": event.get("location"),
                    "official_bankruptcy_url": event.get("official_url"),
                    "sale_url": safe_url,
                    "sale_page_title": page.title or _compact(hit.title),
                    "search_provider": hit.provider or "UNKNOWN",
                    "identity_match_method": identity_method,
                    "bankruptcy_language_verified_on_page": True,
                    "sale_language_verified_on_page": True,
                    "bankruptcy_estate_sale_relationship_verified_on_page": True,
                    "liquidation_only": False,
                    "surplus_only": False,
                    "dealer_only": False,
                    "ended_marker_found": False,
                    "inventory_contents_verified": False,
                    "sale_availability_fully_verified": False,
                    "human_review_required": True,
                }
            )
        return len(links) - accepted_before

    for event in events:
        organisation_number, company_name = _event_identity(event)
        del organisation_number
        query = _search_query(company_name)
        accepted_for_event = 0
        if exa is not None:
            provider = _provider_name(exa)
            request_counts[provider] = request_counts.get(provider, 0) + 1
            searched_events += 1
            try:
                accepted_for_event += inspect_hits(
                    event,
                    list(exa.search(query, count=results_per_query)),
                )
            except Exception as exc:
                provider_errors.append(
                    {
                        "provider": provider,
                        "organisation_number": event["organisation_number"],
                        "error": f"{type(exc).__name__}: {_compact(exc)[:500]}",
                    }
                )
        if accepted_for_event == 0 and brave is not None and page_reads < max_page_reads:
            provider = _provider_name(brave)
            request_counts[provider] = request_counts.get(provider, 0) + 1
            if exa is None:
                searched_events += 1
            try:
                inspect_hits(
                    event,
                    list(brave.search(query, count=results_per_query)),
                )
            except Exception as exc:
                provider_errors.append(
                    {
                        "provider": provider,
                        "organisation_number": event["organisation_number"],
                        "error": f"{type(exc).__name__}: {_compact(exc)[:500]}",
                    }
                )

    provider_count = int(sum(request_counts.values()))
    if not exa and not brave:
        coverage = "SEARCH_PROVIDERS_UNAVAILABLE"
    elif provider_count == 0 and events:
        coverage = "SEARCH_NOT_RUN"
    elif provider_errors and provider_count == len(provider_errors):
        coverage = "SEARCH_PROVIDERS_FAILED"
    elif provider_errors:
        coverage = "PARTIAL_SEARCH_PROVIDER_FAILURE"
    else:
        coverage = "BOUNDED_BANKRUPTCY_LINK_HUNT"
    return {
        "schema_version": SCHEMA_VERSION,
        "scope": "NO_ONLY_OFFICIAL_BANKRUPTCY_LINK_CHASE",
        "captured_at": captured_at,
        "coverage": coverage,
        "event_input_count": len(raw_events),
        "events_searched": searched_events,
        "official_bankruptcy_events_considered": len(events),
        "provider_request_counts": request_counts,
        "paid_provider_requests": provider_count,
        "page_reads": page_reads,
        "page_read_limit": max_page_reads,
        "verified_bankruptcy_sale_link_count": len(links),
        "verified_bankruptcy_sale_links": links,
        "rejected_hit_count": len(rejected),
        "rejected_hits": rejected,
        "provider_errors": provider_errors,
        "policy": {
            "official_bankruptcy_event_required_first": True,
            "official_company_identity_required_on_sale_page": True,
            "bankruptcy_language_required_on_sale_page": True,
            "sale_language_required_on_sale_page": True,
            "bankruptcy_estate_sale_relationship_required_on_page": True,
            "liquidation_only_excluded": True,
            "forced_dissolution_excluded": True,
            "surplus_only_excluded": True,
            "dealer_only_excluded": True,
            "generic_auction_index_excluded": True,
            "ended_sales_excluded": True,
            "search_snippet_never_sufficient": True,
        },
        "openai_requests": 0,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def render_arabic(report: Mapping[str, Any]) -> str:
    lines = [
        "مطاردة روابط بيع التفليسات — النرويج فقط",
        f"التغطية: {report['coverage']}",
        (
            f"أحداث إفلاس رسمية مفحوصة: {report['official_bankruptcy_events_considered']} | "
            f"طلبات بحث مدفوعة: {report['paid_provider_requests']} | "
            f"صفحات مقروءة: {report['page_reads']} | "
            f"روابط بيع مرتبطة بالإفلاس: {report['verified_bankruptcy_sale_link_count']}"
        ),
        "القاعدة: إفلاس رسمي ← اسم/رقم الشركة نفسه على صفحة البيع ← لغة بيع واضحة.",
        "مستبعد: التاجر وحده، الفائض وحده، التصفية، صفحة المزاد العامة، والبيع المنتهي.",
    ]
    links = report.get("verified_bankruptcy_sale_links") or []
    if not links:
        lines.extend(
            [
                "",
                "لم يثبت رابط بيع تفليسة ضمن الفحص المحدود. لذلك لا يوجد رابط يُعرض كفرصة.",
            ]
        )
    for index, link in enumerate(links, 1):
        lines.extend(
            [
                "",
                f"{index}) إفلاس مثبت الربط: {link['company_name']} ({link['organisation_number']})",
                f"السجل الرسمي: {link['official_bankruptcy_url']}",
                f"رابط البيع: {link['sale_url']}",
                f"طريقة مطابقة الهوية: {link['identity_match_method']}",
                "المخزون والتوافر النهائي يحتاجان مراجعة بشرية؛ لا شراء أو مزايدة أو اتصال تلقائي.",
            ]
        )
    if report.get("provider_errors"):
        lines.extend(["", "أخطاء المصادر (لا تعني صفر فرص):"])
        for error in report["provider_errors"]:
            lines.append(
                f"- {error['provider']} / {error['organisation_number']}: {error['error']}"
            )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-events", type=int, default=5)
    parser.add_argument("--results-per-query", type=int, default=5)
    parser.add_argument("--max-page-reads", type=int, default=15)
    args = parser.parse_args()

    payload = json.loads(args.events.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        parser.error("Events report must be a JSON object")
    exa_key = _compact(os.environ.get("EXA_API_KEY"))
    brave_key = _compact(os.environ.get("BRAVE_SEARCH_API_KEY"))
    report = hunt_bankruptcy_links(
        payload,
        exa=ExaSearchProvider(exa_key) if exa_key else None,
        brave=(
            BraveSearchProvider(brave_key, country="NO", extra_snippets=True)
            if brave_key
            else None
        ),
        max_events=args.max_events,
        results_per_query=args.results_per_query,
        max_page_reads=args.max_page_reads,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "bankruptcy-link-hunt.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (args.output_dir / "bankruptcy-link-hunt-ar.txt").write_text(
        render_arabic(report), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "coverage",
                    "official_bankruptcy_events_considered",
                    "paid_provider_requests",
                    "page_reads",
                    "verified_bankruptcy_sale_link_count",
                )
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    if report["coverage"] in {
        "SEARCH_PROVIDERS_UNAVAILABLE",
        "SEARCH_NOT_RUN",
        "SEARCH_PROVIDERS_FAILED",
    } and report["official_bankruptcy_events_considered"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
