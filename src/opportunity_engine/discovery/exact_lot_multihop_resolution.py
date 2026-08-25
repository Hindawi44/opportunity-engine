"""Bounded multi-hop commercial navigation toward strict clothing Exact-Lots.

Some search results are useful commercial gateways but are more than one link
away from a concrete product. This resolver permits a small, same-origin,
commercially-scoped walk. It is deliberately not a general crawler: only
public HTTPS links on the same origin and in a bounded commercial URL role are
considered, and only strict item pages may receive Exact-Lot credit.

Navigation is root-fair: eligible commercial roots share the fixed page budget
in round-robin order so one large catalogue cannot starve other search results.
Within each root, bounded URL-subject priority spends earlier fetches on links
whose own path already names clothing, without filtering neutral links or
turning URL priority into qualification evidence. Aggregate catalog pagination
keeps a bounded continuity reserve so product-detail links cannot erase the
path to adjacent stock pages. After a fair probe, a zero-yield root may be
deferred only while another root has already produced a strict Exact-Lot and
still has queued work. The total navigation budget, provider gates, domain gates
and Exact-Lot gates remain unchanged.
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
    ACTIVE_STOCK_SIGNAL,
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

SCHEMA_VERSION = "exact-lot-multihop-resolution-1.5"
LAB_FAMILY = "EXACT_LOT_MULTIHOP_RESOLUTION_V1"
SUPPORTED_PROVIDERS = frozenset({"exa", "brave"})
MAX_ROOT_PARENTS = 6
MAX_NAVIGATION_DEPTH = 4
MAX_LINKS_PER_PAGE = 20
MAX_NAVIGATION_PAGE_FETCHES = 30
MAX_PAGINATION_CONTINUITY_LINKS_PER_PAGE = 2
FAIR_PROBE_FETCHES_PER_ROOT = 3

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

_AGGREGATE_NAVIGATION_ROLES = frozenset({"COLLECTION", "CATEGORY", "CATALOG"})
_PAGINATION_PATH_RE = re.compile(
    r"^(?P<base>.*?)/page/(?P<number>\d+)$",
    re.IGNORECASE,
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


def _link_subject_priority(url: str) -> int:
    """Prefer proven clothing words in a URL path, but never reject neutral links."""
    path_words = _path(url).replace("-", " ").replace("_", " ").replace("/", " ")
    return 0 if classify_project_domain(text=path_words) == CLOTHING_INVENTORY else 1


def _commercial_url_role(url: str) -> str | None:
    """Return one bounded navigable commercial role, never a general-web role."""
    path = _path(url).rstrip("/") or "/"
    if any(path == prefix or path.startswith(prefix + "/") for prefix in _EXCLUDED_PATH_PREFIXES):
        return None

    # German clothing wholesalers may expose an aggregate hierarchy below
    # /products/bekleidung/ while reserving singular /product/<slug> for actual
    # item pages. Treat the hierarchy as navigation only before the generic
    # item-specific guard can mistake a nested category for a product detail.
    if path == "/products/bekleidung" or path.startswith("/products/bekleidung/"):
        return "CATEGORY"

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


def _pagination_continuity_distance(page_url: str, candidate_url: str) -> int | None:
    """Return adjacent aggregate-page distance, never commercial qualification evidence."""
    if _commercial_url_role(page_url) not in _AGGREGATE_NAVIGATION_ROLES:
        return None
    if _commercial_url_role(candidate_url) not in _AGGREGATE_NAVIGATION_ROLES:
        return None

    current_path = _path(page_url).rstrip("/") or "/"
    candidate_path = _path(candidate_url).rstrip("/") or "/"
    current_match = _PAGINATION_PATH_RE.fullmatch(current_path)
    candidate_match = _PAGINATION_PATH_RE.fullmatch(candidate_path)

    if current_match:
        current_base = (current_match.group("base") or "/").rstrip("/") or "/"
        current_number = int(current_match.group("number"))
    else:
        current_base = current_path
        current_number = 1

    if candidate_match:
        candidate_base = (candidate_match.group("base") or "/").rstrip("/") or "/"
        candidate_number = int(candidate_match.group("number"))
    elif current_match and candidate_path == current_base:
        candidate_base = candidate_path
        candidate_number = 1
    else:
        return None

    if candidate_base != current_base or candidate_number == current_number:
        return None
    return abs(candidate_number - current_number)


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
    current_path = _path(page_url).rstrip("/") or "/"
    candidates: list[tuple[int, int, int, int, str, int | None]] = []
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

        candidate_path = (parts.path or "/").casefold().rstrip("/") or "/"
        if current_path != "/" and candidate_path.startswith(current_path + "/"):
            scope_priority = 0
        elif candidate_path.startswith("/product/"):
            scope_priority = 1
        else:
            scope_priority = 2 if current_path != "/" else 0

        seen.add(candidate)
        candidates.append(
            (
                scope_priority,
                role_priority[role],
                _link_subject_priority(candidate),
                position,
                candidate,
                _pagination_continuity_distance(page_url, candidate),
            )
        )
    candidates.sort(key=lambda item: (item[0], item[1], item[2], item[3]))

    pagination_candidates = [item for item in candidates if item[5] is not None]
    if pagination_candidates and max_links > 1:
        pagination_candidates.sort(key=lambda item: (item[5], item[3]))
        reserve = min(
            MAX_PAGINATION_CONTINUITY_LINKS_PER_PAGE,
            len(pagination_candidates),
            max_links,
        )
        reserved_urls = {item[4] for item in pagination_candidates[:reserve]}
        regular = [item for item in candidates if item[4] not in reserved_urls]
        selected = regular[: max_links - reserve] + pagination_candidates[:reserve]
        if len(selected) < max_links:
            selected_urls = {item[4] for item in selected}
            for item in candidates:
                if item[4] in selected_urls:
                    continue
                selected.append(item)
                selected_urls.add(item[4])
                if len(selected) >= max_links:
                    break
        return [item[4] for item in selected[:max_links]]

    return [item[4] for item in candidates[:max_links]]


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
    role = _commercial_url_role(url)
    if role == "PRODUCT_DETAIL":
        return False
    if classification in {OUT_OF_DOMAIN, FETCH_FAILED}:
        return False

    # Aggregate category pages are navigation evidence only. Some legitimate
    # wholesale category pages expose stock cards with price + quantity without
    # a page-level sale verb. That is enough to follow same-origin product links,
    # but never enough for Exact-Lot credit, which remains strict in _strict_exact.
    navigation_commercial_evidence = bool(
        evidence.get("direct_sale_evidence") is True
        or (
            role == "CATEGORY"
            and evidence.get("inventory_evidence") is True
            and evidence.get("price_evidence") is True
            and evidence.get("quantity_evidence") is True
        )
    )
    return bool(
        role is not None
        and evidence.get("project_domain") == CLOTHING_INVENTORY
        and evidence.get("page_subject_domain") == CLOTHING_INVENTORY
        and evidence.get("inventory_evidence") is True
        and navigation_commercial_evidence
        and (evidence.get("price_evidence") is True or evidence.get("quantity_evidence") is True)
    )


def _root_subject_domain(page: dict[str, Any], url: str) -> str:
    path_words = _path(url).replace("-", " ").replace("_", " ").replace("/", " ")
    return classify_project_domain(text=_compact(f"{page.get('title') or ''} {path_words}"))


def _aggregate_navigation_root_eligible(
    *, url: str, page: dict[str, Any], evidence: dict[str, Any]
) -> bool:
    """Rescue proven aggregate clothing pages for navigation only, never credit."""
    role = _commercial_url_role(url)
    return bool(
        page.get("fetch_ok") is True
        and page.get("classification") == ACTIVE_STOCK_SIGNAL
        and role in {"COLLECTION", "CATEGORY", "CATALOG"}
        and _root_subject_domain(page, url) == CLOTHING_INVENTORY
        and evidence.get("project_domain") == CLOTHING_INVENTORY
        and evidence.get("inventory_evidence") is True
        and evidence.get("direct_sale_evidence") is True
        and (evidence.get("price_evidence") is True or evidence.get("quantity_evidence") is True)
    )


def _eligible_multihop_root(page: dict[str, Any]) -> bool:
    if _eligible_parent(page):
        return True
    url = _compact(page.get("final_url") or page.get("url"))
    evidence = page.get("evidence") or {}
    if _aggregate_navigation_root_eligible(url=url, page=page, evidence=evidence):
        return True
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
    role = _commercial_url_role(url)
    if role == "COMMERCIAL_HUB":
        return 0
    if role in {"COLLECTION", "CATEGORY", "CATALOG"}:
        return 1
    return 2


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
        "aggregate_role_root_navigation_only": True,
        "aggregate_role_root_is_qualification_evidence": False,
        "same_origin_only": True,
        "bounded_multi_hop": True,
        "root_fair_navigation": True,
        "navigation_scheduling": "ROUND_ROBIN_ROOT_FAIR_V1",
        "post_probe_scheduling": "PROVEN_YIELD_PRESERVATION_V1",
        "fair_probe_fetches_per_root": FAIR_PROBE_FETCHES_PER_ROOT,
        "yield_stall_requires_proven_alternative": True,
        "yield_stall_is_qualification_evidence": False,
        "pagination_continuity_preserved": True,
        "pagination_continuity_reserve_per_page": MAX_PAGINATION_CONTINUITY_LINKS_PER_PAGE,
        "pagination_continuity_is_qualification_evidence": False,
        "within_root_link_priority": "ROLE_THEN_CLOTHING_SUBJECT_V1",
        "link_priority_is_qualification_evidence": False,
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
        "root_navigation_fetch_counts": {},
        "root_exact_lot_counts": {},
        "root_yield_stall_counts": {},
        "yield_stalled_root_count": 0,
        "navigation_results": [],
        "gateway_pages": [],
        "gateway_page_count": 0,
        "exact_lots": [],
        "exact_lot_candidate_count": 0,
        "exact_lot_yield_per_fetch": 0.0,
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
    root_states: list[dict[str, Any]] = []
    page_attempted = 0
    page_succeeded = 0
    depth_exhausted = 0

    # Phase 1: fetch every eligible root and seed one independent queue. No root
    # is allowed to consume navigation page budget before the other roots are
    # represented in the scheduler.
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
        if queue:
            root_states.append(
                {
                    "root_url": resolved_root,
                    "root_host": root_host,
                    "queue": queue,
                    "fetch_count": 0,
                    "exact_lot_count": 0,
                    "yield_stall_count": 0,
                }
            )

    # Phase 2 starts root-fair. Once every zero-yield root has had a bounded fair
    # probe, it may be deferred only if another root has already yielded a strict
    # Exact-Lot and still has queued work. Deferred roots are restored if proven
    # roots run out of work before the global page budget is exhausted.
    active: deque[dict[str, Any]] = deque(root_states)
    deferred_zero_yield: deque[dict[str, Any]] = deque()
    while (active or deferred_zero_yield) and page_attempted < max_navigation_page_fetches:
        if not active:
            while deferred_zero_yield:
                active.append(deferred_zero_yield.popleft())

        state = active.popleft()
        queue = state["queue"]
        if not queue:
            continue

        proven_alternative_has_work = any(
            other is not state
            and other["exact_lot_count"] > 0
            and bool(other["queue"])
            for other in root_states
        )
        if (
            state["fetch_count"] >= FAIR_PROBE_FETCHES_PER_ROOT
            and state["exact_lot_count"] == 0
            and proven_alternative_has_work
        ):
            state["yield_stall_count"] += 1
            deferred_zero_yield.append(state)
            continue

        node = queue.popleft()
        root_host = state["root_host"]
        page_attempted += 1
        state["fetch_count"] += 1

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
        else:
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
            else:
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
                    state["exact_lot_count"] += 1
                    exact_lots.append({
                        **row,
                        "provider": provider,
                        "parent_url": node["root_url"],
                        "exact_lot_accepted": True,
                    })
                elif _gateway_eligible(
                    url=final_url,
                    classification=classification,
                    evidence=evidence,
                ):
                    gateway_pages.append({
                        **row,
                        "provider": provider,
                        "parent_url": node["root_url"],
                        "exact_lot_accepted": False,
                    })
                    if node["depth"] >= max_navigation_depth:
                        depth_exhausted += 1
                    else:
                        fetched_html = aggregate_fetcher(final_url)
                        if (
                            fetched_html.ok
                            and _host(fetched_html.final_url or final_url) == root_host
                        ):
                            html_url = fetched_html.final_url or final_url
                            next_links = _extract_navigation_links(
                                page_url=html_url,
                                root_host=root_host,
                                html_text=fetched_html.html,
                                max_links=max_links_per_page,
                            )
                            # Child links are ranked by bounded URL role and clothing
                            # subject before DOM position. A tiny aggregate-pagination
                            # reserve keeps catalog continuity without granting any
                            # qualification credit. Fresh links stay ahead of older
                            # siblings inside the same root; root-level fairness and
                            # the unchanged global page budget still apply.
                            fresh_nodes: list[dict[str, Any]] = []
                            for link in next_links:
                                if link in seen_navigation_urls:
                                    continue
                                seen_navigation_urls.add(link)
                                fresh_nodes.append({
                                    "url": link,
                                    "depth": node["depth"] + 1,
                                    "chain": [*row["navigation_chain"], link],
                                    "root_url": node["root_url"],
                                    "market_code": node["market_code"],
                                    "query": node["query"],
                                })
                            for fresh in reversed(fresh_nodes):
                                queue.appendleft(fresh)

        if queue:
            active.append(state)

    page_budget_exhausted = sum(len(state["queue"]) for state in root_states)
    root_navigation_fetch_counts = {
        state["root_url"]: state["fetch_count"] for state in root_states
    }
    root_exact_lot_counts = {
        state["root_url"]: state["exact_lot_count"] for state in root_states
    }
    root_yield_stall_counts = {
        state["root_url"]: state["yield_stall_count"] for state in root_states
    }
    yield_stalled_root_count = sum(
        1 for state in root_states if state["yield_stall_count"] > 0
    )
    exact_lot_yield_per_fetch = (
        round(len(exact_lots) / page_attempted, 4) if page_attempted else 0.0
    )

    return {
        **base,
        "status": "SUCCESS",
        "block_reason": None,
        "eligible_root_parent_count": len(roots),
        "root_results": root_results,
        "root_navigation_fetch_counts": root_navigation_fetch_counts,
        "root_exact_lot_counts": root_exact_lot_counts,
        "root_yield_stall_counts": root_yield_stall_counts,
        "yield_stalled_root_count": yield_stalled_root_count,
        "navigation_page_fetches_attempted": page_attempted,
        "navigation_page_fetches_succeeded": page_succeeded,
        "depth_budget_exhausted_count": depth_exhausted,
        "page_budget_exhausted_count": page_budget_exhausted,
        "navigation_results": navigation_results,
        "gateway_page_count": len(gateway_pages),
        "gateway_pages": gateway_pages,
        "exact_lot_candidate_count": len(exact_lots),
        "exact_lot_yield_per_fetch": exact_lot_yield_per_fetch,
        "exact_lots": exact_lots,
        "interpretation_guard": (
            "Commercial hubs, aggregate categories, pagination and gateway pages are navigation evidence only. Exact-Lot credit is reserved for directly fetched strict clothing item/lot pages. Smart link priority and proven-yield scheduling change navigation order only and are never qualification evidence. Multi-hop navigation stays same-origin, root-fair through a bounded probe and bounded by explicit URL roles, depth and the unchanged global page budget."
        ),
    }