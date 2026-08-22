"""Bounded live shadow validation for learned source candidates.

This module is deliberately outside production discovery. It may inspect a source
only after repeated external SOURCE_GAP evidence validated that source for
shadow evaluation. Teaching URLs are excluded before candidate verification, and
an exact candidate page must independently prove a stock/lot opportunity before
the run can claim recovery.

V1 supports only the two source shapes proven by the first real benchmark:
WorldWiseUSA's stock-offer feed and Stocklear's auction catalog. Unknown learned
sources remain unsupported rather than silently receiving a generic crawler.
"""
from __future__ import annotations

from html.parser import HTMLParser
import html as html_module
import re
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urljoin, urlsplit, urlunsplit

SCHEMA_VERSION = "source-shadow-live-validation-1.0"

FetchText = Callable[[str], str]

_SOURCE_ENTRYPOINTS = {
    "www.worldwiseusa.com": "https://www.worldwiseusa.com/latest-stock-lot-offers/",
    "joblot.stocklear.eu": "https://joblot.stocklear.eu/",
}

_WORLDWISE_BLOCKED_PREFIXES = (
    "/category/",
    "/tag/",
    "/author/",
    "/wp-",
    "/feed",
)
_WORLDWISE_BLOCKED_PATHS = {
    "/",
    "/latest-stock-lot-offers/",
    "/about-us/",
    "/contact-us/",
    "/request-a-quote/",
    "/privacy-policy/",
    "/terms-and-conditions/",
}
_STOCKLEAR_AUCTION_PATH_RE = re.compile(r"^/auction/\d+/?$")
_SPACE_RE = re.compile(r"\s+")


class _AnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._href: str | None = None
        self._text: list[str] = []
        self.anchors: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() != "a" or self._href is not None:
            return
        href = next((value for key, value in attrs if key.casefold() == "href"), None)
        if href:
            self._href = href
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() != "a" or self._href is None:
            return
        text = _compact(" ".join(self._text))
        self.anchors.append((self._href, text))
        self._href = None
        self._text = []


def _compact(value: object) -> str:
    return _SPACE_RE.sub(" ", str(value or "")).strip()


def _canonical_url(value: object) -> str:
    raw = _compact(value)
    if not raw:
        return ""
    try:
        parts = urlsplit(raw)
    except ValueError:
        return ""
    if parts.scheme.casefold() not in {"http", "https"} or not parts.hostname:
        return ""
    path = parts.path.rstrip("/") + "/" if parts.path not in {"", "/"} else "/"
    return urlunsplit((parts.scheme.casefold(), parts.netloc.casefold(), path, parts.query, ""))


def _domain(value: object) -> str:
    try:
        return (urlsplit(_compact(value)).hostname or "").casefold().rstrip(".")
    except ValueError:
        return ""


def _path(value: str) -> str:
    try:
        path = urlsplit(value).path or "/"
    except ValueError:
        return "/"
    return path.rstrip("/") + "/" if path != "/" else "/"


def _eligible_source_rows(source_candidates: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = source_candidates.get("source_candidates") or []
    if not isinstance(rows, list):
        return []
    eligible: list[Mapping[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        if _compact(row.get("status")) != "VALIDATED_SOURCE":
            continue
        if row.get("shadow_eligible") is not True:
            continue
        if row.get("production_active") is not False:
            continue
        domain = _compact(row.get("source_domain")).casefold().rstrip(".")
        if domain not in _SOURCE_ENTRYPOINTS:
            continue
        eligible.append(row)
    return eligible


def _looks_like_candidate(source_domain: str, url: str) -> bool:
    path = _path(url)
    if source_domain == "joblot.stocklear.eu":
        return bool(_STOCKLEAR_AUCTION_PATH_RE.fullmatch(path.rstrip("/")))
    if source_domain == "www.worldwiseusa.com":
        if path in _WORLDWISE_BLOCKED_PATHS:
            return False
        if any(path.startswith(prefix) for prefix in _WORLDWISE_BLOCKED_PREFIXES):
            return False
        segments = [segment for segment in path.split("/") if segment]
        return len(segments) == 1 and len(segments[0]) >= 8
    return False


def extract_shadow_candidates(
    *,
    source_domain: str,
    source_name: str,
    page_url: str,
    html: str,
    teaching_urls: set[str] | Sequence[str],
) -> list[dict[str, Any]]:
    """Extract same-domain novel opportunity links from one validated source page."""
    domain = _compact(source_domain).casefold().rstrip(".")
    if domain not in _SOURCE_ENTRYPOINTS:
        return []
    blocked = {_canonical_url(url) for url in teaching_urls if _canonical_url(url)}
    parser = _AnchorParser()
    parser.feed(str(html or ""))

    by_url: dict[str, dict[str, Any]] = {}
    for href, title in parser.anchors:
        absolute = _canonical_url(urljoin(page_url, href))
        if not absolute or _domain(absolute) != domain:
            continue
        if absolute in blocked or not _looks_like_candidate(domain, absolute):
            continue
        if absolute in by_url:
            current = by_url[absolute]
            if len(title) > len(str(current.get("title") or "")):
                current["title"] = title
            continue
        by_url[absolute] = {
            "source_name": _compact(source_name),
            "source_domain": domain,
            "source_url": absolute,
            "title": title or _path(absolute).strip("/").replace("-", " "),
            "candidate_origin": "LEARNED_VALIDATED_SOURCE_SHADOW_SCAN",
            "teaching_url": False,
            "shadow_only": True,
            "production_active": False,
            "source_page_verification_required": True,
        }
    return list(by_url.values())


def validate_shadow_sources(
    source_candidates: Mapping[str, Any],
    *,
    fetcher: FetchText,
    max_candidates_per_source: int = 5,
) -> dict[str, Any]:
    """Fetch only validated shadow source entrypoints and extract novel links."""
    if not 1 <= max_candidates_per_source <= 20:
        raise ValueError("max_candidates_per_source must be between 1 and 20")
    eligible = _eligible_source_rows(source_candidates)
    source_results: list[dict[str, Any]] = []
    network_requests = 0

    for row in eligible:
        domain = _compact(row.get("source_domain")).casefold().rstrip(".")
        name = _compact(row.get("source_name")) or domain
        entrypoint = _SOURCE_ENTRYPOINTS[domain]
        teaching_urls = {
            _canonical_url(value)
            for value in (row.get("evidence_urls") or [])
            if _canonical_url(value)
        }
        try:
            page = fetcher(entrypoint)
            network_requests += 1
            candidates = extract_shadow_candidates(
                source_domain=domain,
                source_name=name,
                page_url=entrypoint,
                html=page,
                teaching_urls=teaching_urls,
            )[:max_candidates_per_source]
            status = "SUCCESS"
            error = None
        except Exception as exc:  # isolated source failure must remain visible
            network_requests += 1
            candidates = []
            status = "FAILED"
            error = f"{type(exc).__name__}: {exc}"
        source_results.append(
            {
                "source_name": name,
                "source_domain": domain,
                "entrypoint": entrypoint,
                "status": status,
                "error": error,
                "teaching_url_count": len(teaching_urls),
                "novel_candidate_count": len(candidates),
                "novel_candidates": candidates,
                "shadow_only": True,
                "production_active": False,
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "phase": "DISCOVERY",
        "eligible_source_count": len(eligible),
        "source_results": source_results,
        "novel_candidate_count": sum(row["novel_candidate_count"] for row in source_results),
        "network_request_count": network_requests,
        "max_candidates_per_source": max_candidates_per_source,
        "teaching_urls_excluded": True,
        "automatic_promotion": False,
        "production_mutation": False,
        "automatic_source_addition": False,
    }


def _plain_text(html: str) -> str:
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", str(html or ""), flags=re.I | re.S)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return _compact(html_module.unescape(text)).casefold()


def _detail_page_proves_opportunity(source_domain: str, html: str) -> bool:
    text = _plain_text(html)
    if not text:
        return False
    if source_domain == "joblot.stocklear.eu":
        commercial = any(term in text for term in ("starting price", "last bid", "end of the auction"))
        lot = any(term in text for term in ("number of pallets", " units", "weight ", "lot of "))
        condition = any(term in text for term in ("quality", "customer return", "new in original packaging", "non functional", "not tested"))
        return commercial and lot and condition
    if source_domain == "www.worldwiseusa.com":
        availability = any(
            term in text
            for term in (
                "stock lot",
                "stocklot",
                "load now",
                "ready to load",
                "available now",
                "liquidation",
                "inventory report",
                "container sale",
            )
        )
        scale = any(
            term in text
            for term in (
                "container",
                "pallet",
                "pieces",
                "units",
                "rolls",
                "truckload",
                "load",
                "ft lengths",
            )
        )
        return availability and scale
    return False


def verify_shadow_candidates(
    discovery_report: Mapping[str, Any],
    *,
    fetcher: FetchText,
    max_detail_requests: int = 6,
) -> dict[str, Any]:
    """Verify novel shadow links on their exact source pages under a hard request cap."""
    if not 0 <= max_detail_requests <= 20:
        raise ValueError("max_detail_requests must be between 0 and 20")
    verified: list[dict[str, Any]] = []
    attempted = 0
    failed = 0

    source_results = discovery_report.get("source_results") or []
    if not isinstance(source_results, list):
        source_results = []
    for source in source_results:
        if not isinstance(source, Mapping):
            continue
        domain = _compact(source.get("source_domain")).casefold().rstrip(".")
        name = _compact(source.get("source_name")) or domain
        candidates = source.get("novel_candidates") or []
        if not isinstance(candidates, list):
            continue
        for raw in candidates:
            if attempted >= max_detail_requests:
                break
            if not isinstance(raw, Mapping):
                continue
            url = _canonical_url(raw.get("source_url"))
            if not url or _domain(url) != domain or raw.get("teaching_url") is True:
                continue
            attempted += 1
            try:
                page = fetcher(url)
            except Exception:
                failed += 1
                continue
            if not _detail_page_proves_opportunity(domain, page):
                continue
            verified.append(
                {
                    "source_name": name,
                    "source_domain": domain,
                    "source_url": url,
                    "title": _compact(raw.get("title")),
                    "verification_status": "SHADOW_RECOVERED_OPPORTUNITY",
                    "source_page_verified": True,
                    "teaching_url": False,
                    "shadow_only": True,
                    "production_active": False,
                }
            )
        if attempted >= max_detail_requests:
            break

    return {
        "schema_version": SCHEMA_VERSION,
        "phase": "EXACT_PAGE_VERIFICATION",
        "detail_verification_request_count": attempted,
        "detail_verification_failure_count": failed,
        "verified_new_opportunity_count": len(verified),
        "verified_new_opportunities": verified,
        "max_detail_requests": max_detail_requests,
        "automatic_promotion": False,
        "production_mutation": False,
    }


def run_shadow_source_validation(
    source_candidates: Mapping[str, Any],
    *,
    fetcher: FetchText,
    max_candidates_per_source: int = 5,
    max_detail_requests: int = 6,
) -> dict[str, Any]:
    """Run bounded source discovery + exact-page proof without production effects."""
    discovery = validate_shadow_sources(
        source_candidates,
        fetcher=fetcher,
        max_candidates_per_source=max_candidates_per_source,
    )
    verification = verify_shadow_candidates(
        discovery,
        fetcher=fetcher,
        max_detail_requests=max_detail_requests,
    )
    verified = list(verification["verified_new_opportunities"])
    production_active_source_count = sum(
        1
        for row in (source_candidates.get("source_candidates") or [])
        if isinstance(row, Mapping) and row.get("production_active") is True
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "verdict": (
            "SHADOW_RECOVERED_NEW_OPPORTUNITIES"
            if verified
            else "NO_VERIFIED_NEW_SHADOW_OPPORTUNITY"
        ),
        "eligible_source_count": discovery["eligible_source_count"],
        "novel_candidate_count": discovery["novel_candidate_count"],
        "verified_new_opportunity_count": len(verified),
        "verified_new_opportunities": verified,
        "teaching_url_recovery_count": sum(1 for row in verified if row.get("teaching_url") is True),
        "network_request_count": discovery["network_request_count"]
        + verification["detail_verification_request_count"],
        "source_discovery_request_count": discovery["network_request_count"],
        "detail_verification_request_count": verification["detail_verification_request_count"],
        "max_candidates_per_source": max_candidates_per_source,
        "max_detail_requests": max_detail_requests,
        "production_active_source_count": production_active_source_count,
        "teaching_urls_excluded": True,
        "automatic_promotion": False,
        "automatic_source_addition": False,
        "production_mutation": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
        "discovery": discovery,
        "verification": verification,
    }
