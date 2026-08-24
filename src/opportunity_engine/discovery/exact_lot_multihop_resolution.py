"""Bounded multi-hop commercial navigation toward strict clothing Exact-Lots.

Some search results are useful commercial gateways but are more than one link
away from a concrete product. This resolver permits a small, same-origin,
commercially-scoped breadth-first walk. It is deliberately not a general
crawler: only public HTTPS links on the same origin and in a bounded commercial
URL role are considered, and only strict item pages may receive Exact-Lot
credit.
"""
from __future__ import annotations

from collections import deque
import re
from typing import Any
from urllib.parse import urldefrag, urljoin, urlsplit

from opportunity_engine.discovery.exact_lot_child_link_resolution import (
    AggregateHtmlFetcher,
    _AnchorParser,
    _classify_child_page,
    _compact,
    _eligible_parent,
    fetch_public_html,
)
from opportunity_engine.discovery.exa_shadow_page_verification import (
    EXACT_LOT_CANDIDATE,
    FETCH_FAILED,
    INFO_OR_LEGAL_ONLY,
    PageFetcher,
    _looks_item_specific_url,
    fetch_public_page,
)
from opportunity_engine.discovery.keyword_shadow_verification import _public_https_url
from opportunity_engine.project_domain_boundary import (
    CLOTHING_INVENTORY,
    OUT_OF_DOMAIN,
    classify_project_domain,
)

SCHEMA_VERSION = "exact-lot-multihop-resolution-1.0"
LAB_FAMILY = "EXACT_LOT_MULTIHOP_RESOLUTION_V1"
SUPPORTED_PROVIDERS = frozenset({"exa", "brave"})
MAX_ROOT_PARENTS = 6
MAX_NAVIGATION_DEPTH = 4
MAX_LINKS_PER_PAGE = 20
MAX_NAVIGATION_PAGE_FETCHES = 30

_EXCLUDED_PATH_PREFIXES = (
    "/blog", "/blogs", "/faq", "/contact", "/about", "/policies", "/policy",
    "/legal", "/terms", "/privacy", "/account", "/cart", "/checkout", "/search",
    "/pages/contact", "/pages/about",
)

_COMMERCIAL_PAGE_SLUG_MARKERS = (
    "lot", "stock", "wholesale", "grossiste", "revendeur", "revente", "reseller",
    "destock", "déstock", "liquidation", "vetement", "vêtement", "clothing",
    "apparel", "fashion", "mode", "friperie", "kleding", "kleidung", "abbigliamento",
)

# Generic marketplace detail shape: a short listing-kind token, a numeric record
# id and a meaningful slug. Domain and commercial evidence are still checked on
# the fetched page, so this URL shape alone can never create an opportunity.
_MARKETPLACE_ID_SLUG_RE = re.compile(
    r"(?:^|/)(?:c|listing|annonce|annuncio)-\d{2,}-[^/?#]+(?:\.html?)?(?:/|$)",
    re.IGNORECASE,
)


def _host(url: str) -> str:
    try:
        return (urlsplit(_compact(url)).hostname or "").casefold()
    except ValueError:
        return ""


def _path(url: str) -> str:
    try:
        return (urlsplit(_compact(url)).path or "/").casefold()
    except ValueError:
        return "/"


def _commercial_url_role(url: str) -> str | None:
    """Return one bounded navigable commercial role, never a general-web role."""
    path = _path(url).rstrip("/") or "/"
    if any(path == prefix or path.startswith(prefix + "/") for prefix in _EXCLUDED_PATH_PREFIXES):
        return None

    # Use the canonical item-specific guard for singular /product/, /lot/, etc.
    # Also recognize a generic numeric listing-id + slug detail shape. Neither
    # path form bypasses the downstream clothing/evidence gates.
    if _looks_item_specific_url(url) or _MARKETPLACE_ID_SLUG_RE.search(path):
        return "PRODUCT_DETAIL"
    if path.startswith("/collections/") or path.startswith("/collection/"):
        return "COLLECTION"
    if path.startswith("/categories/") or path.startswith("/category/"):
        return "CATEGORY"
    if path.startswith("/catalog/") or path.startswith("/catalogue/"):
        return "CATALOG"
    if path.startswith("/pages/"):
        slug = path.rsplit("/", 1)[-1].replace("-", " ").replace("_", " ")
        if any(marker in slug for marker in _COMMERCIAL_PAGE_SLUG_MARKERS):
            return "COMMERCIAL_HUB"
    return None


def _extract_navigation_links(
    *, page_url: str, root_host: str, html_text: str, max_links: int
) -> list[str]:
    if not _public_https_url(page_url) or not root_host:
        return []
    parser = _AnchorParser()
    try:
        parser.feed(str(html_text or ""))
    except (TypeError, ValueError):
        return []

    role_priority = {
        "PRODUCT_DETAIL": 0,
        "COLLECTION": 1,
        "CATEGORY": 2,
        "CATALOG": 3,
        "COMMERCIAL_HUB": 4,
    }
    current = urldefrag(page_url).url
    candidates: list[tuple[int, int, str]] = []
    seen: set[str] = set()
    for position, href in enumerate(parser.hrefs):
        try:
            candidate = urldefrag(urljoin(page_url, href)).url
            parts = urlsplit(candidate)
        except ValueError:
            continue
        if parts.scheme.casefold() != "https":
            continue
        if (parts.hostname or "").casefold() != root_host:
            continue
        if candidate == current or candidate in seen:
            continue
        role = _commercial_url_role(candidate)
        if role is None:
            continue
        seen.add(candidate)
        candidates.append((role_priority[role], position, candidate))
    candidates.sort(key=lambda item: (item[0], item[1]))
    return [item[2] for item in candidates[:max_links]]


def _strict_exact(classification: str, evidence: dict[str, Any]) -> bool:
    return bool(
        classification == EXACT_LOT_CANDIDATE
        and evidence.get("project_domain") == CLOTHING_INVENTORY
        and evidence.get("page_subject_domain") == CLOTHING_INVENTORY
        and evidence.get("item_specific_url_evidence") is True
        and evidence.get("inventory_evidence") is True
        and evidence.get("direct_sale_evidence") is True
        and evidence.get("price_evidence") is True
        and evidence.get("quantity_evidence") is True
    )


def _gateway_eligible(*, url: str, classification: str, evidence: dict[str, Any]) -> bool:
    if _commercial_url_role(url) == "PRODUCT_DETAIL":
        return False
    if classification in {OUT_OF_DOMAIN, FETCH_FAILED}:
        return False
    return bool(
        _commercial_url_role(url) is not None
        and evidence.get("project_domain") == CLOTHING_INVENTORY
        and evidence.get("page_subject_domain") == CLOTHING_INVENTORY
        and evidence.get("inventory_evidence") is True
        and evidence.get("direct_sale_evidence") is True
        and (evidence.get("price_evidence") is True or evidence.get("quantity_evidence") is True)
    )


def _root_subject_domain(page: dict[str, Any], url: str) -> str:
    path_words = _path(url).replace("-", " ").replace("_", " ").replace("/", " ")
    return classify_project_domain(text=_compact(f"{page.get('title') or ''} {path_words}"))


def _eligible_multihop_root(page: dict[str, Any]) -> bool:
    if _eligible_parent(page):
        return True
    url = _compact(page.get("final_url") or page.get("url"))
    evidence = page.get("evidence") or {}
    return bool(
        page.get("fetch_ok") is True
        and page.get("classification") == INFO_OR_LEGAL_ONLY
        and page.get("tool_learning_useful") is not True
        and _commercial_url_role(url) == "COMMERCIAL_HUB"
        and _root_subject_domain(page, url) == CLOTHING_INVENTORY
        and evidence.get("project_domain") == CLOTHING_INVENTORY
        and evidence.get("inventory_evidence") is True
        and evidence.get("direct_sale_evidence") is True
        and (evidence.get("price_evidence") is True or evidence.get("quantity_evidence") is True)
    )


def _root_priority(page: dict[str, Any]) -> int:
    url = _compact(page.get("final_url") or page.get("url"))
    return 0 if _commercial_url_role(url) == "COMMERCIAL_HUB" else 1


def _base(
    *, provider: str, max_root_parents: int, max_navigation_depth: int,
    max_links_per_page: int, max_navigation_page_fetches: int,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "lab_family": LAB_FAMILY,
        "provider": provider,
        "shadow_only": True,
        "required_project_domain": CLOTHING_INVENTORY,
        "project_domain_gate_enforced": True,
        "commercial_specificity_gate_enforced": True,
        "child_subject_domain_gate_enforced": True,
        "commercial_hub_navigation_only": True,
        "same_origin_only": True,
        "bounded_multi_hop": True,
        "exact_lot_acceptance_only": True,
        "max_root_parents": max_root_parents,
        "max_navigation_depth": max_navigation_depth,
        "max_links_per_page": max_links_per_page,
        "max_navigation_page_fetches": max_navigation_page_fetches,
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
        "eligible_root_parent_count": 0,
        "root_results": [],
        "navigation_results": [],
        "gateway_pages": [],
        "gateway_page_count": 0,
        "exact_lots": [],
        "exact_lot_candidate_count": 0,
        "navigation_page_fetches_attempted": 0,
        "navigation_page_fetches_succeeded": 0,
        "depth_budget_exhausted_count": 0,
        "page_budget_exhausted_count": 0,
    }


def resolve_exact_lot_multihop(
    provider_verification: dict[str, Any],
    *,
    aggregate_fetcher: AggregateHtmlFetcher = fetch_public_html,
    page_fetcher: PageFetcher = fetch_public_page,
    max_root_parents: int = 3,
    max_navigation_depth: int = 3,
    max_links_per_page: int = 12,
    max_navigation_page_fetches: int = 18,
) -> dict[str, Any]:
    """Walk bounded same-origin commercial gateways toward strict Exact-Lots."""
    if not 1 <= max_root_parents <= MAX_ROOT_PARENTS:
        raise ValueError(f"max_root_parents must be between 1 and {MAX_ROOT_PARENTS}")
    if not 1 <= max_navigation_depth <= MAX_NAVIGATION_DEPTH:
        raise ValueError(f"max_navigation_depth must be between 1 and {MAX_NAVIGATION_DEPTH}")
    if not 1 <= max_links_per_page <= MAX_LINKS_PER_PAGE:
        raise ValueError(f"max_links_per_page must be between 1 and {MAX_LINKS_PER_PAGE}")
    if not 1 <= max_navigation_page_fetches <= MAX_NAVIGATION_PAGE_FETCHES:
        raise ValueError(
            f"max_navigation_page_fetches must be between 1 and {MAX_NAVIGATION_PAGE_FETCHES}"
        )

    provider = _compact(provider_verification.get("provider")).casefold()
    base = _base(
        provider=provider,
        max_root_parents=max_root_parents,
        max_navigation_depth=max_navigation_depth,
        max_links_per_page=max_links_per_page,
        max_navigation_page_fetches=max_navigation_page_fetches,
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
    if provider_verification.get("project_domain_gate_enforced") is not True:
        return _blocked(base, "PROJECT_DOMAIN_GATE_NOT_ENFORCED")
    if _compact(provider_verification.get("required_project_domain")) != CLOTHING_INVENTORY:
        return _blocked(base, "INPUT_NOT_CLOTHING_DOMAIN_GATED")

    roots: list[dict[str, Any]] = []
    seen_root_urls: set[str] = set()
    for page in provider_verification.get("verified_pages") or []:
        if not isinstance(page, dict) or not _eligible_multihop_root(page):
            continue
        root_url = _compact(page.get("final_url") or page.get("url"))
        if not root_url or root_url in seen_root_urls:
            continue
        seen_root_urls.add(root_url)
        roots.append(page)
    roots.sort(key=_root_priority)
    roots = roots[:max_root_parents]

    root_results: list[dict[str, Any]] = []
    navigation_results: list[dict[str, Any]] = []
    gateway_pages: list[dict[str, Any]] = []
    exact_lots: list[dict[str, Any]] = []
    seen_navigation_urls: set[str] = set()
    page_attempted = 0
    page_succeeded = 0
    depth_exhausted = 0
    page_budget_exhausted = 0

    for root in roots:
        root_url = _compact(root.get("final_url") or root.get("url"))
        root_host = _host(root_url)
        if not root_host or not _public_https_url(root_url):
            root_results.append({
                "root_url": root_url,
                "root_classification": root.get("classification"),
                "root_navigation_role": _commercial_url_role(root_url),
                "root_exact_lot_accepted": False,
                "fetch_ok": False,
                "fetch_error": "UNSAFE_ROOT_URL",
            })
            continue

        fetched_root = aggregate_fetcher(root_url)
        if not fetched_root.ok or _host(fetched_root.final_url or root_url) != root_host:
            root_results.append({
                "root_url": root_url,
                "root_classification": root.get("classification"),
                "root_navigation_role": _commercial_url_role(root_url),
                "root_exact_lot_accepted": False,
                "fetch_ok": False,
                "status_code": fetched_root.status_code,
                "final_url": fetched_root.final_url,
                "fetch_error": fetched_root.error or "ROOT_REDIRECT_LEFT_ORIGIN",
            })
            continue

        resolved_root = fetched_root.final_url or root_url
        first_links = _extract_navigation_links(
            page_url=resolved_root,
            root_host=root_host,
            html_text=fetched_root.html,
            max_links=max_links_per_page,
        )
        root_results.append({
            "root_url": root_url,
            "root_classification": root.get("classification"),
            "root_navigation_role": _commercial_url_role(root_url),
            "root_exact_lot_accepted": False,
            "fetch_ok": True,
            "status_code": fetched_root.status_code,
            "final_url": resolved_root,
            "navigation_link_count": len(first_links),
            "navigation_links": first_links,
        })

        queue: deque[dict[str, Any]] = deque()
        for link in first_links:
            if link in seen_navigation_urls:
                continue
            seen_navigation_urls.add(link)
            queue.append({
                "url": link,
                "depth": 1,
                "chain": [resolved_root, link],
                "root_url": resolved_root,
                "market_code": _compact(root.get("market_code")).upper(),
                "query": _compact(root.get("query")),
            })

        while queue:
            node = queue.popleft()
            if page_attempted >= max_navigation_page_fetches:
                page_budget_exhausted += 1
                continue
            page_attempted += 1
            fetched = page_fetcher(node["url"])
            if not fetched.ok:
                navigation_results.append({
                    **node,
                    "classification": FETCH_FAILED,
                    "fetch_ok": False,
                    "status_code": fetched.status_code,
                    "final_url": fetched.final_url,
                    "fetch_error": fetched.error,
                    "evidence": {},
                })
                continue

            final_url = fetched.final_url or node["url"]
            role = _commercial_url_role(final_url)
            if _host(final_url) != root_host or role is None:
                navigation_results.append({
                    **node,
                    "classification": "NAVIGATION_SCOPE_REJECTED",
                    "fetch_ok": True,
                    "status_code": fetched.status_code,
                    "final_url": final_url,
                    "fetch_error": None,
                    "evidence": {},
                })
                continue

            page_succeeded += 1
            classification, evidence = _classify_child_page(
                title=fetched.title,
                text=fetched.text,
                url=final_url,
            )
            row = {
                **node,
                "url": final_url,
                "classification": classification,
                "fetch_ok": True,
                "status_code": fetched.status_code,
                "final_url": final_url,
                "fetch_error": None,
                "truncated": fetched.truncated,
                "navigation_role": role,
                "navigation_depth": node["depth"],
                "navigation_chain": [*node["chain"][:-1], final_url],
                "evidence": evidence,
            }
            navigation_results.append(row)

            if _strict_exact(classification, evidence):
                exact_lots.append({
                    **row,
                    "provider": provider,
                    "parent_url": node["root_url"],
                    "exact_lot_accepted": True,
                })
                continue

            if not _gateway_eligible(url=final_url, classification=classification, evidence=evidence):
                continue
            gateway_pages.append({
                **row,
                "provider": provider,
                "parent_url": node["root_url"],
                "exact_lot_accepted": False,
            })
            if node["depth"] >= max_navigation_depth:
                depth_exhausted += 1
                continue

            fetched_html = aggregate_fetcher(final_url)
            if not fetched_html.ok or _host(fetched_html.final_url or final_url) != root_host:
                continue
            html_url = fetched_html.final_url or final_url
            next_links = _extract_navigation_links(
                page_url=html_url,
                root_host=root_host,
                html_text=fetched_html.html,
                max_links=max_links_per_page,
            )
            for link in next_links:
                if link in seen_navigation_urls:
                    continue
                seen_navigation_urls.add(link)
                queue.append({
                    "url": link,
                    "depth": node["depth"] + 1,
                    "chain": [*row["navigation_chain"], link],
                    "root_url": node["root_url"],
                    "market_code": node["market_code"],
                    "query": node["query"],
                })

    return {
        **base,
        "status": "SUCCESS",
        "block_reason": None,
        "eligible_root_parent_count": len(roots),
        "root_results": root_results,
        "navigation_page_fetches_attempted": page_attempted,
        "navigation_page_fetches_succeeded": page_succeeded,
        "depth_budget_exhausted_count": depth_exhausted,
        "page_budget_exhausted_count": page_budget_exhausted,
        "navigation_results": navigation_results,
        "gateway_page_count": len(gateway_pages),
        "gateway_pages": gateway_pages,
        "exact_lot_candidate_count": len(exact_lots),
        "exact_lots": exact_lots,
        "interpretation_guard": (
            "Commercial hubs and gateway pages are navigation evidence only. Exact-Lot credit is reserved for directly fetched strict clothing item/lot pages. Multi-hop navigation stays same-origin and bounded by explicit URL roles, depth and page budgets."
        ),
    }
