"""Explicit, evidence-gated production activation for learned sources.

V1 activates only Stocklear. A source is allowed to fetch in production only when:
1) an exact domain decision is explicitly PROMOTED, and
2) the frozen promotion scorecard proves PROMOTE_CANDIDATE with no blockers.

Changing the decision to DISABLED closes the network path immediately.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import html as html_module
import json
from pathlib import Path
import re
from typing import Any, Callable, Mapping
from urllib.parse import urlsplit

import requests

from opportunity_engine.source_shadow_live_validation import (
    _detail_page_proves_opportunity,
    extract_shadow_candidates,
)

SCHEMA_VERSION = "promoted-source-production-feed-1.0"
PROMOTION_SCHEMA_VERSION = "source-promotion-gate-1.0"
FEED_FAMILY = "STOCKLEAR_PROMOTED_AUCTION_FEED_V1"
SOURCE_DOMAIN = "joblot.stocklear.eu"
SOURCE_NAME = "Stocklear"
ENTRYPOINT = "https://joblot.stocklear.eu/"
DEFAULT_PROMOTION_PATH = Path("config/learning/source_promotions.json")
DEFAULT_SCORECARD_PATH = Path("docs/benchmarks/stocklear-source-scorecard-2026-08-22-result.json")
DEFAULT_MAX_CANDIDATES = 8

FetchText = Callable[[str], str]

_CURRENCY_TOKEN = r"(?:EUR|€|GBP|£|USD|\$)"
_AMOUNT_TOKEN = r"\d[\d\s.,]*"
_MONEY_RE = re.compile(
    rf"(?:starting\s+price|last\s+bid|current\s+bid)\s*[:\-]?\s*"
    rf"(?:(?P<currency_before>{_CURRENCY_TOKEN})\s*)?"
    rf"(?P<amount>{_AMOUNT_TOKEN})\s*"
    rf"(?P<currency_after>{_CURRENCY_TOKEN})?",
    re.IGNORECASE,
)
_RRP_RE = re.compile(
    rf"\bRRP\s*[:\-]?\s*(?:(?P<currency_before>{_CURRENCY_TOKEN})\s*)?"
    rf"(?P<amount>{_AMOUNT_TOKEN})\s*(?P<currency_after>{_CURRENCY_TOKEN})?",
    re.IGNORECASE,
)
_UNITS_RE = re.compile(r"\b(?P<amount>\d[\d\s.,]*)\s+units?\b", re.IGNORECASE)
_PALLETS_RE = re.compile(r"number\s+of\s+pallets?\s*[:\-]?\s*(?P<amount>\d[\d\s.,]*)", re.IGNORECASE)
_QUALITY_RE = re.compile(r"quality\s*[:\-]?\s*(?P<value>[^|\n]{3,120})", re.IGNORECASE)
_TITLE_RE = re.compile(r"<title[^>]*>(?P<title>.*?)</title>", re.IGNORECASE | re.DOTALL)
_SCRIPT_STYLE_RE = re.compile(
    r"<(?:script|style)\b[^>]*>.*?</(?:script|style)>",
    re.IGNORECASE | re.DOTALL,
)
_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")


def _compact(value: object) -> str:
    return _SPACE_RE.sub(" ", str(value or "")).strip()


def _number(value: str | None) -> float | None:
    text = _compact(value).replace(" ", "")
    if not text:
        return None
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        parts = text.split(",")
        text = text.replace(",", "") if len(parts[-1]) == 3 else text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _currency(value: str | None) -> str | None:
    token = _compact(value).upper()
    return {"€": "EUR", "£": "GBP", "$": "USD"}.get(token, token or None)


def _plain_text(html: str) -> str:
    cleaned = _SCRIPT_STYLE_RE.sub(" ", str(html or ""))
    return _compact(html_module.unescape(_TAG_RE.sub(" ", cleaned)))


def _title(html: str, fallback: str) -> str:
    match = _TITLE_RE.search(str(html or ""))
    if not match:
        return _compact(fallback)
    return _compact(html_module.unescape(_TAG_RE.sub(" ", match.group("title")))) or _compact(fallback)


def _decision_rows(promotions: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    if promotions.get("schema_version") != PROMOTION_SCHEMA_VERSION:
        return []
    rows = promotions.get("decisions")
    return [row for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def select_promoted_source_domains(
    promotions: Mapping[str, Any],
    scorecard: Mapping[str, Any],
) -> set[str]:
    """Return exact proven domains with an explicit PROMOTED decision."""
    proven_domain = _compact(scorecard.get("source_domain")).casefold().rstrip(".")
    if not proven_domain:
        return set()
    if scorecard.get("decision") != "PROMOTE_CANDIDATE":
        return set()
    if float(scorecard.get("promotion_readiness_score") or 0) < 85:
        return set()
    if list(scorecard.get("blocking_reasons") or []):
        return set()
    if scorecard.get("automatic_promotion") is not False:
        return set()

    promoted: set[str] = set()
    for row in _decision_rows(promotions):
        domain = _compact(row.get("source_domain")).casefold().rstrip(".")
        if domain != proven_domain or row.get("status") != "PROMOTED":
            continue
        if not _compact(row.get("reason")) or not _compact(row.get("approved_at")):
            continue
        promoted.add(domain)
    return promoted


class PublicHttpFetcher:
    def __init__(self, *, timeout_seconds: float = 20.0, max_bytes: int = 2_000_000) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_bytes = max_bytes
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "OpportunityEngine/1.0 (+public promoted-source collector)",
                "Accept": "text/html,application/xhtml+xml",
            }
        )

    def __call__(self, url: str) -> str:
        response = self.session.get(url, timeout=self.timeout_seconds, allow_redirects=True)
        response.raise_for_status()
        final_host = (urlsplit(response.url).hostname or "").casefold().rstrip(".")
        if final_host != SOURCE_DOMAIN:
            raise ValueError(f"cross-domain redirect blocked: {final_host}")
        content = response.content[: self.max_bytes]
        return content.decode(response.encoding or "utf-8", errors="replace")


def _money(pattern: re.Pattern[str], text: str) -> tuple[float | None, str | None]:
    match = pattern.search(text)
    if not match:
        return None, None
    currency = match.groupdict().get("currency_before") or match.groupdict().get("currency_after")
    return _number(match.group("amount")), _currency(currency)


def _candidate_from_detail(url: str, html: str, title_hint: str, observed_at: str) -> dict[str, Any] | None:
    if not _detail_page_proves_opportunity(SOURCE_DOMAIN, html):
        return None
    text = _plain_text(html)
    total_price, currency = _money(_MONEY_RE, text)
    rrp, rrp_currency = _money(_RRP_RE, text)
    units_match = _UNITS_RE.search(text)
    pallets_match = _PALLETS_RE.search(text)
    quality_match = _QUALITY_RE.search(text)
    quantity = _number(units_match.group("amount")) if units_match else None
    pallets = _number(pallets_match.group("amount")) if pallets_match else None
    condition = _compact(quality_match.group("value"))[:160] if quality_match else None
    reference = urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1]
    title = _title(html, title_hint or f"Stocklear auction {reference}")
    candidate_id = "stocklear-promoted:" + sha256(url.encode("utf-8")).hexdigest()[:24]
    return {
        "candidate_id": candidate_id,
        "feed_family": FEED_FAMILY,
        "source_name": SOURCE_NAME,
        "source_region": "EU",
        "source_country": None,
        "official_domain": SOURCE_DOMAIN,
        "source_url": url,
        "source_reference": reference,
        "title": title[:1000],
        "description": text[:1500],
        "observed_at": observed_at,
        "page_role": "SPECIFIC_AUCTION_LOT",
        "listing_status": "ACTIVE_REQUIRES_VERIFICATION_OF_END_TIME",
        "sale_mode": "AUCTION",
        "inventory_focus": "GENERAL_MERCHANDISE_STOCKLOT",
        "quantity": quantity,
        "quantity_unit": "units" if quantity is not None else None,
        "lot_units": pallets,
        "lot_unit_type": "pallets" if pallets is not None else None,
        "total_price": total_price,
        "current_bid": total_price,
        "currency": currency,
        "estimated_retail_value": rrp,
        "estimated_retail_currency": rrp_currency,
        "condition_terms": [condition] if condition else [],
        "verification_status": "SOURCE_PAGE_VERIFIED",
        "source_page_verified": True,
        "opportunity_state": "VERIFIED_B2B_AUCTION_LOT",
        "score": 95,
        "missing_information": [
            field
            for field, present in (
                ("VISIBLE_PRICE", total_price is not None),
                ("QUANTITY", quantity is not None),
                ("PALLET_COUNT", pallets is not None),
            )
            if not present
        ],
        "evidence": [
            {
                "field": "SOURCE_PAGE_VERIFICATION",
                "source_url": url,
                "verified": True,
                "captured_at": observed_at,
                "value": "Exact public Stocklear auction page independently proved a commercial stock lot.",
            }
        ],
        "promotion_status": "PROMOTED",
        "activation_source": "EXPLICIT_SOURCE_PROMOTION",
        "decision_owner": "HUMAN_OPERATOR",
    }


def build_promoted_stocklear_feed(
    promotions: Mapping[str, Any],
    scorecard: Mapping[str, Any],
    *,
    fetcher: FetchText,
    max_candidates: int = DEFAULT_MAX_CANDIDATES,
    observed_at: str | None = None,
) -> dict[str, Any]:
    if not 1 <= max_candidates <= 12:
        raise ValueError("max_candidates must be between 1 and 12")
    promoted = select_promoted_source_domains(promotions, scorecard)
    now = observed_at or datetime.now(timezone.utc).isoformat()
    base = {
        "schema_version": SCHEMA_VERSION,
        "feed_family": FEED_FAMILY,
        "source_name": SOURCE_NAME,
        "source_domain": SOURCE_DOMAIN,
        "generated_at": now,
        "explicit_promotion_required": True,
        "automatic_promotion": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }
    if SOURCE_DOMAIN not in promoted:
        return {
            **base,
            "status": "DISABLED",
            "production_source_active": False,
            "candidate_count": 0,
            "candidates": [],
            "network_request_count": 0,
        }

    index_html = fetcher(ENTRYPOINT)
    network_requests = 1
    discovered = extract_shadow_candidates(
        source_domain=SOURCE_DOMAIN,
        source_name=SOURCE_NAME,
        page_url=ENTRYPOINT,
        html=index_html,
        teaching_urls=set(),
    )[:max_candidates]

    candidates: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for raw in discovered:
        url = _compact(raw.get("source_url"))
        if not url:
            continue
        try:
            page = fetcher(url)
            network_requests += 1
        except Exception as exc:
            network_requests += 1
            failures.append({"source_url": url, "error": f"{type(exc).__name__}: {exc}"})
            continue
        candidate = _candidate_from_detail(url, page, _compact(raw.get("title")), now)
        if candidate is not None:
            candidates.append(candidate)

    return {
        **base,
        "status": "ACTIVE",
        "production_source_active": True,
        "promotion_gate_enforced": True,
        "promotion_score": float(scorecard.get("promotion_readiness_score") or 0),
        "candidate_count": len(candidates),
        "discovered_link_count": len(discovered),
        "source_page_failed_count": len(failures),
        "failures": failures,
        "candidates": candidates,
        "network_request_count": network_requests,
    }


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def write_promoted_stocklear_feed(
    output_dir: str | Path,
    *,
    promotion_path: str | Path = DEFAULT_PROMOTION_PATH,
    scorecard_path: str | Path = DEFAULT_SCORECARD_PATH,
    fetcher: FetchText | None = None,
    max_candidates: int = DEFAULT_MAX_CANDIDATES,
) -> dict[str, Any]:
    """Write the production Stocklear feed only when explicit promotion is proven."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    promotions = _load_json(Path(promotion_path))
    scorecard = _load_json(Path(scorecard_path))
    report = build_promoted_stocklear_feed(
        promotions,
        scorecard,
        fetcher=fetcher or PublicHttpFetcher(),
        max_candidates=max_candidates,
    )
    target = output / "stocklear-promoted-source-feed.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report
