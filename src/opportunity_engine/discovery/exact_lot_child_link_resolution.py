"""Bounded child-link resolution for verified aggregate clothing-stock pages.

Aggregate/category pages never become opportunities. This layer may use a page
only as a navigation parent after the symmetric provider verifier has already
proved clothing-inventory + direct-sale evidence and rejected the page from
item-specific Tool Learning credit.

Child links are restricted to HTTPS, same-origin descendant paths. A child is
accepted only when the strict commercial classifier proves an item-specific
clothing lot with direct sale, price and quantity. Child classification adds
conservative protections that are intentionally scoped to this layer:

* prices such as ``4 €`` and ``1000€`` are normalized to ``EUR`` before the
  existing price parser runs;
* an item-specific child must prove the clothing domain from its own title/URL
  subject;
* explicit e-commerce controls such as ``Ajouter au panier`` prove direct sale
  only on item-specific canonical ``/product/<slug>`` or ``/products/<slug>``
  detail routes. Site-wide cart controls on hubs or collections cannot create
  exact-lot credit.

The layer is read-only and cannot contact, bid, reserve, buy or pay.
"""
from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
import re
from typing import Any, Callable
from urllib.parse import urldefrag, unquote, urljoin, urlsplit

import requests

from opportunity_engine.discovery.exa_shadow_page_verification import (
    ACTIVE_STOCK_SIGNAL,
    EXACT_LOT_CANDIDATE,
    FETCH_FAILED,
    PageFetcher,
    _classify_page,
    _looks_item_specific_url,
    fetch_public_page,
)
from opportunity_engine.discovery.keyword_shadow_verification import _public_https_url
from opportunity_engine.project_domain_boundary import (
    CLOTHING_INVENTORY,
    OUT_OF_DOMAIN,
    classify_project_domain,
)

SCHEMA_VERSION = "exact-lot-child-link-resolution-1.2"
LAB_FAMILY = "EXACT_LOT_CHILD_LINK_RESOLUTION_V1"
SUPPORTED_PROVIDERS = frozenset({"exa", "brave"})
MAX_PARENT_FETCHES = 12
MAX_CHILD_LINKS_PER_PARENT = 20
MAX_CHILD_PAGE_FETCHES = 30
MAX_RESPONSE_BYTES = 800_000

_EURO_AFTER_NUMBER_RE = re.compile(r"(?<=\d)\s*€")
# Some legacy pages expose a CP1252 euro byte decoded as C1 \x80.
# Normalize only when it directly precedes a numeric price.
_MISDECODED_EURO_BEFORE_NUMBER_RE = re.compile(r"\x80\s*(?=\d)")
_CANONICAL_PRODUCT_DETAIL_RE = re.compile(
    r"(?:^|/)products?/(?P<slug>[^/?#]+)/*$",
    re.IGNORECASE,
)
_EXPLICIT_PURCHASE_MARKERS = (
    "add to cart",
    "buy now",
    "ajouter au panier",
    "acheter maintenant",
    "in den warenkorb",
    "jetzt kaufen",
    "aggiungi al carrello",
    "acquista ora",
    "in winkelwagen",
    "nu kopen",
    "lägg i varukorg",
    "lagg i varukorg",
    "köp nu",
    "kop nu",
    "legg i handlekurv",
    "kjøp nå",
    "kjop na",
)
_MIXED_SUBJECT_MARKERS = (
    "blandet",
    "blandat",
    "mixed",
    "mixed lot",
    "mix lot",
    "gemischt",
    "gemischte",
    "lot mixte",
    "misto",
)
_OUT_OF_SCOPE_SUBJECT_MARKERS = (
    "elektro",
    "elektronikk",
    "electronics",
    "verktøy",
    "verktoy",
    "tools",
    "husholdning",
    "household",
    "hvitevarer",
    "appliances",
    "møbler",
    "mobler",
    "furniture",
    "bygg",
    "building",
)


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


@dataclass(frozen=True, slots=True)
class AggregateHtmlFetchResult:
    requested_url: str
    final_url: str
    ok: bool
    status_code: int | None
    html: str
    error: str | None = None
    truncated: bool = False


AggregateHtmlFetcher = Callable[[str], AggregateHtmlFetchResult]


def fetch_public_html(url: str) -> AggregateHtmlFetchResult:
    """Fetch one bounded public HTTPS HTML page for link extraction only."""
    requested = _compact(url)
    if not _public_https_url(requested):
        return AggregateHtmlFetchResult(
            requested_url=requested,
            final_url=requested,
            ok=False,
            status_code=None,
            html="",
            error="UNSAFE_OR_UNSUPPORTED_URL",
        )
    try:
        with requests.get(
            requested,
            timeout=(5, 12),
            allow_redirects=True,
            stream=True,
            headers={
                "User-Agent": "opportunity-engine-exact-lot-child-link-resolver/1.2",
                "Accept": "text/html,application/xhtml+xml",
            },
        ) as response:
            final_url = str(response.url or requested)
            if not _public_https_url(final_url):
                return AggregateHtmlFetchResult(
                    requested, final_url, False, response.status_code, "", "UNSAFE_REDIRECT_TARGET"
                )
            if not 200 <= response.status_code < 300:
                return AggregateHtmlFetchResult(
                    requested, final_url, False, response.status_code, "", f"HTTP_{response.status_code}"
                )
            content_type = str(response.headers.get("Content-Type") or "").casefold()
            if "html" not in content_type:
                return AggregateHtmlFetchResult(
                    requested, final_url, False, response.status_code, "", "NON_HTML_CONTENT"
                )

            chunks: list[bytes] = []
            total = 0
            truncated = False
            for chunk in response.iter_content(chunk_size=16_384):
                if not chunk:
                    continue
                remaining = MAX_RESPONSE_BYTES - total
                if remaining <= 0:
                    truncated = True
                    break
                if len(chunk) > remaining:
                    chunks.append(chunk[:remaining])
                    truncated = True
                    break
                chunks.append(chunk)
                total += len(chunk)
            body = b"".join(chunks)
            encoding = response.encoding or "utf-8"
            try:
                html = body.decode(encoding, errors="replace")
            except LookupError:
                html = body.decode("utf-8", errors="replace")
            if not html.strip():
                return AggregateHtmlFetchResult(
                    requested, final_url, False, response.status_code, "", "EMPTY_HTML", truncated
                )
            return AggregateHtmlFetchResult(
                requested, final_url, True, response.status_code, html, None, truncated
            )
    except requests.RequestException as exc:
        return AggregateHtmlFetchResult(
            requested_url=requested,
            final_url=requested,
            ok=False,
            status_code=None,
            html="",
            error=f"{type(exc).__name__}: {str(exc)[:200]}",
        )


class _AnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() != "a":
            return
        for key, value in attrs:
            if key.casefold() == "href" and value:
                self.hrefs.append(value.strip())
                return


def _extract_candidate_child_links(*, parent_url: str, html_text: str) -> list[str]:
    """Return conservative same-origin descendant item/detail URLs in document order."""
    parent = _compact(parent_url)
    if not _public_https_url(parent):
        return []
    try:
        parent_parts = urlsplit(parent)
    except ValueError:
        return []
    parent_host = (parent_parts.hostname or "").casefold()
    parent_prefix = (parent_parts.path or "/").rstrip("/") + "/"
    parent_defragged = urldefrag(parent).url

    parser = _AnchorParser()
    try:
        parser.feed(str(html_text or ""))
    except (TypeError, ValueError):
        return []

    output: list[str] = []
    seen: set[str] = set()
    for href in parser.hrefs:
        try:
            candidate = urldefrag(urljoin(parent, href)).url
            parts = urlsplit(candidate)
        except ValueError:
            continue
        if parts.scheme.casefold() != "https":
            continue
        if (parts.hostname or "").casefold() != parent_host:
            continue
        if candidate == parent_defragged:
            continue
        if not (parts.path or "/").startswith(parent_prefix):
            continue
        if not _looks_item_specific_url(candidate):
            continue
        if candidate in seen:
            continue
        seen.add(candidate)
        output.append(candidate)
    return output


def _subject_context(*, title: str, url: str) -> str:
    try:
        path = unquote(urlsplit(url).path or "")
    except ValueError:
        path = ""
    path_words = path.replace("-", " ").replace("_", " ").replace("/", " ")
    return _compact(f"{title} {path_words}")


def _mixed_general_merchandise_subject(subject: str) -> bool:
    normalized = _compact(subject).casefold()
    return bool(
        any(marker in normalized for marker in _MIXED_SUBJECT_MARKERS)
        and any(marker in normalized for marker in _OUT_OF_SCOPE_SUBJECT_MARKERS)
    )


def _normalize_child_price_text(text: str) -> str:
    """Normalize number-followed-by-euro-symbol prices without inventing values."""
    normalized = _EURO_AFTER_NUMBER_RE.sub(" EUR", str(text or ""))
    return _MISDECODED_EURO_BEFORE_NUMBER_RE.sub("€ ", normalized)


def _looks_canonical_product_detail_url(url: str) -> bool:
    try:
        path = (urlsplit(_compact(url)).path or "").casefold().rstrip("/")
    except ValueError:
        return False
    match = _CANONICAL_PRODUCT_DETAIL_RE.search(path)
    if not match:
        return False
    return bool(_looks_item_specific_url(url))


def _has_explicit_purchase_control(text: str) -> bool:
    normalized = _compact(text).casefold()
    return any(marker in normalized for marker in _EXPLICIT_PURCHASE_MARKERS)


def _classify_child_page(*, title: str, text: str, url: str) -> tuple[str, dict[str, Any]]:
    """Classify one item-specific child with local-subject domain evidence.

    The existing classifier supplies the base commercial evidence. This layer
    adds local subject-domain protection and one narrow e-commerce rule: an
    explicit purchase control can prove direct sale only on an item-specific
    canonical product detail URL, never on a hub/collection page where cart
    text may be global UI.
    """
    normalized_text = _normalize_child_price_text(text)
    classification, evidence = _classify_page(
        title=title,
        text=normalized_text,
        url=url,
    )
    evidence = dict(evidence)
    full_page_domain = evidence.get("project_domain")
    subject_context = _subject_context(title=title, url=url)
    mixed_general_merchandise = _mixed_general_merchandise_subject(subject_context)
    subject_domain = (
        OUT_OF_DOMAIN
        if mixed_general_merchandise
        else classify_project_domain(text=subject_context)
    )
    canonical_product = _looks_canonical_product_detail_url(url)
    purchase_control = bool(canonical_product and _has_explicit_purchase_control(normalized_text))

    evidence["full_page_project_domain"] = full_page_domain
    evidence["page_subject_domain"] = subject_domain
    evidence["mixed_general_merchandise_subject_evidence"] = mixed_general_merchandise
    evidence["child_price_symbol_normalization"] = normalized_text != str(text or "")
    evidence["canonical_product_detail_url_evidence"] = canonical_product
    evidence["explicit_purchase_evidence"] = purchase_control

    if purchase_control:
        evidence["direct_sale_evidence"] = True

    if evidence.get("item_specific_url_evidence") is True and subject_domain != CLOTHING_INVENTORY:
        evidence["project_domain"] = OUT_OF_DOMAIN
        evidence["domain_evidence"] = False
        if classification in {EXACT_LOT_CANDIDATE, ACTIVE_STOCK_SIGNAL} or purchase_control:
            classification = OUT_OF_DOMAIN
    elif subject_domain == CLOTHING_INVENTORY:
        evidence["project_domain"] = CLOTHING_INVENTORY
        evidence["domain_evidence"] = True
        strict_product_shape = bool(
            canonical_product
            and purchase_control
            and evidence.get("inventory_evidence") is True
            and evidence.get("price_evidence") is True
            and evidence.get("quantity_evidence") is True
            and evidence.get("item_specific_url_evidence") is True
            and evidence.get("info_or_legal_evidence") is not True
        )
        if strict_product_shape:
            classification = EXACT_LOT_CANDIDATE

    return classification, evidence


def _eligible_parent(page: dict[str, Any]) -> bool:
    evidence = page.get("evidence") or {}
    return bool(
        page.get("fetch_ok") is True
        and page.get("classification") == ACTIVE_STOCK_SIGNAL
        and page.get("tool_learning_useful") is not True
        and evidence.get("project_domain") == CLOTHING_INVENTORY
        and evidence.get("inventory_evidence") is True
        and evidence.get("direct_sale_evidence") is True
        and evidence.get("item_specific_url_evidence") is False
    )


def _base(*, provider: str, max_parent_fetches: int, max_child_page_fetches: int) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "lab_family": LAB_FAMILY,
        "provider": provider,
        "shadow_only": True,
        "required_project_domain": CLOTHING_INVENTORY,
        "project_domain_gate_enforced": True,
        "commercial_specificity_gate_enforced": True,
        "child_subject_domain_gate_enforced": True,
        "same_origin_child_links_only": True,
        "descendant_path_child_links_only": True,
        "exact_lot_acceptance_only": True,
        "max_parent_fetches": max_parent_fetches,
        "max_child_page_fetches": max_child_page_fetches,
        "production_provider_activation": False,
        "promotion_to_live_engine_enabled": False,
        "production_mutation": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def _blocked(base: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        **base,
        "status": "BLOCKED_INPUT",
        "block_reason": reason,
        "eligible_parent_count": 0,
        "parent_results": [],
        "child_results": [],
        "exact_lots": [],
        "exact_lot_candidate_count": 0,
    }


def resolve_exact_lot_child_links(
    provider_verification: dict[str, Any],
    *,
    aggregate_fetcher: AggregateHtmlFetcher = fetch_public_html,
    child_page_fetcher: PageFetcher = fetch_public_page,
    max_parent_fetches: int = 6,
    max_child_links_per_parent: int = 10,
    max_child_page_fetches: int = 20,
) -> dict[str, Any]:
    """Resolve strict exact-lot children from verified non-specific sale parents."""
    if not 1 <= max_parent_fetches <= MAX_PARENT_FETCHES:
        raise ValueError(f"max_parent_fetches must be between 1 and {MAX_PARENT_FETCHES}")
    if not 1 <= max_child_links_per_parent <= MAX_CHILD_LINKS_PER_PARENT:
        raise ValueError(
            f"max_child_links_per_parent must be between 1 and {MAX_CHILD_LINKS_PER_PARENT}"
        )
    if not 1 <= max_child_page_fetches <= MAX_CHILD_PAGE_FETCHES:
        raise ValueError(
            f"max_child_page_fetches must be between 1 and {MAX_CHILD_PAGE_FETCHES}"
        )

    provider = _compact(provider_verification.get("provider")).casefold()
    base = _base(
        provider=provider,
        max_parent_fetches=max_parent_fetches,
        max_child_page_fetches=max_child_page_fetches,
    )
    if provider_verification.get("status") != "SUCCESS":
        return _blocked(base, "VERIFICATION_NOT_SUCCESSFUL")
    if provider not in SUPPORTED_PROVIDERS:
        return _blocked(base, "UNSUPPORTED_PROVIDER")
    if provider_verification.get("shadow_only") is not True:
        return _blocked(base, "INPUT_NOT_SHADOW_ONLY")
    if provider_verification.get("symmetric_provider_verification") is not True:
        return _blocked(base, "INPUT_NOT_SYMMETRIC_PROVIDER_VERIFICATION")
    if provider_verification.get("commercial_specificity_gate_enforced") is not True:
        return _blocked(base, "COMMERCIAL_SPECIFICITY_GATE_NOT_ENFORCED")
    if provider_verification.get("project_domain_gate_enforced") is not True or _compact(
        provider_verification.get("required_project_domain")
    ) != CLOTHING_INVENTORY:
        return _blocked(base, "INPUT_NOT_CLOTHING_DOMAIN_GATED")

    eligible: list[dict[str, Any]] = []
    seen_parents: set[str] = set()
    for page in provider_verification.get("verified_pages") or []:
        if not isinstance(page, dict) or not _eligible_parent(page):
            continue
        parent_url = _compact(page.get("final_url") or page.get("url"))
        if not parent_url or parent_url in seen_parents:
            continue
        seen_parents.add(parent_url)
        eligible.append(page)

    parent_results: list[dict[str, Any]] = []
    child_candidates: list[dict[str, Any]] = []
    seen_children: set[str] = set()
    parent_attempted = 0
    parent_succeeded = 0

    for page in eligible:
        parent_url = _compact(page.get("final_url") or page.get("url"))
        if parent_attempted >= max_parent_fetches:
            parent_results.append(
                {
                    "parent_url": parent_url,
                    "fetch_ok": False,
                    "fetch_error": "PARENT_BUDGET_EXHAUSTED",
                    "child_url_count": 0,
                }
            )
            continue
        parent_attempted += 1
        fetched = aggregate_fetcher(parent_url)
        if not fetched.ok:
            parent_results.append(
                {
                    "parent_url": parent_url,
                    "fetch_ok": False,
                    "status_code": fetched.status_code,
                    "final_url": fetched.final_url,
                    "fetch_error": fetched.error,
                    "child_url_count": 0,
                }
            )
            continue

        parent_succeeded += 1
        resolved_parent = fetched.final_url or parent_url
        links = _extract_candidate_child_links(
            parent_url=resolved_parent,
            html_text=fetched.html,
        )[:max_child_links_per_parent]
        parent_results.append(
            {
                "parent_url": parent_url,
                "fetch_ok": True,
                "status_code": fetched.status_code,
                "final_url": resolved_parent,
                "fetch_error": None,
                "truncated": fetched.truncated,
                "child_url_count": len(links),
                "child_urls": links,
            }
        )
        for child_url in links:
            if child_url in seen_children:
                continue
            seen_children.add(child_url)
            child_candidates.append(
                {
                    "url": child_url,
                    "parent_url": resolved_parent,
                    "market_code": _compact(page.get("market_code")).upper(),
                    "query": _compact(page.get("query")),
                    "provider": provider,
                }
            )

    child_results: list[dict[str, Any]] = []
    exact_lots: list[dict[str, Any]] = []
    child_attempted = 0
    child_succeeded = 0
    child_budget_exhausted = 0

    for candidate in child_candidates:
        if child_attempted >= max_child_page_fetches:
            child_budget_exhausted += 1
            child_results.append(
                {
                    **candidate,
                    "classification": "NOT_FETCHED_BUDGET",
                    "fetch_ok": False,
                    "fetch_error": "CHILD_PAGE_BUDGET_EXHAUSTED",
                    "exact_lot_accepted": False,
                    "evidence": {},
                }
            )
            continue

        child_attempted += 1
        fetched = child_page_fetcher(candidate["url"])
        if not fetched.ok:
            child_results.append(
                {
                    **candidate,
                    "classification": FETCH_FAILED,
                    "fetch_ok": False,
                    "status_code": fetched.status_code,
                    "final_url": fetched.final_url,
                    "fetch_error": fetched.error,
                    "exact_lot_accepted": False,
                    "evidence": {},
                }
            )
            continue

        child_succeeded += 1
        final_url = fetched.final_url or candidate["url"]
        classification, evidence = _classify_child_page(
            title=fetched.title,
            text=fetched.text,
            url=final_url,
        )
        accepted = bool(
            classification == EXACT_LOT_CANDIDATE
            and evidence.get("project_domain") == CLOTHING_INVENTORY
            and evidence.get("page_subject_domain") == CLOTHING_INVENTORY
            and evidence.get("item_specific_url_evidence") is True
            and evidence.get("inventory_evidence") is True
            and evidence.get("direct_sale_evidence") is True
            and evidence.get("price_evidence") is True
            and evidence.get("quantity_evidence") is True
        )
        row = {
            **candidate,
            "classification": classification,
            "fetch_ok": True,
            "status_code": fetched.status_code,
            "final_url": final_url,
            "fetch_error": None,
            "truncated": fetched.truncated,
            "exact_lot_accepted": accepted,
            "evidence": evidence,
        }
        child_results.append(row)
        if accepted:
            exact_lots.append(row)

    return {
        **base,
        "status": "SUCCESS",
        "block_reason": None,
        "eligible_parent_count": len(eligible),
        "parent_fetches_attempted": parent_attempted,
        "parent_fetches_succeeded": parent_succeeded,
        "parent_results": parent_results,
        "candidate_child_url_count": len(child_candidates),
        "child_page_fetches_attempted": child_attempted,
        "child_page_fetches_succeeded": child_succeeded,
        "child_budget_exhausted_count": child_budget_exhausted,
        "exact_lot_candidate_count": len(exact_lots),
        "child_results": child_results,
        "exact_lots": exact_lots,
        "interpretation_guard": (
            "Aggregate parents remain non-opportunities. A child must be a directly fetched same-origin descendant item page whose own subject proves clothing and whose page proves direct sale, price and quantity. Explicit cart/buy controls count only on item-specific canonical product-detail URLs."
        ),
    }