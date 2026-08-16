"""Verify Italy follow-up search leads against the original public sale page.

ITALY_EXACT_LOT_VERIFICATION_V1 is deliberately conservative. A Brave/search
hit is never treated as proof. The verifier fetches only bounded public HTTPS
pages already surfaced by the Italy follow-up case, then requires source-page
evidence for all of the following before a lead is considered commercially
verified:

* the remembered company/entity is present on the page;
* clothing/bridal inventory is explicit;
* a concrete lot/stock/warehouse signal is explicit;
* a sale/auction signal is explicit;
* the sale is explicitly active.

An ended sale, generic article, entity mismatch, unsupported URL, fetch failure,
or unknown sale status stays signal-only. Even a verified active exact lot is not
promoted to an opportunity here. No contact, bid, reservation, purchase, or
payment is ever performed.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
import ipaddress
import re
from typing import Any, Callable, Mapping
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from opportunity_engine.discovery.signal_follow_up_engine import (
    DECISION_OWNER,
    _canonical_url,
    _normalise,
    _significant_tokens,
)


SCHEMA_VERSION = "italy-exact-lot-verification-1.0"
ENGINE_VERSION = "ITALY_EXACT_LOT_VERIFICATION_V1"
DEFAULT_MAX_VERIFICATION_PAGES = 4
MAX_VERIFICATION_PAGES = 8
MAX_RESPONSE_BYTES = 1_000_000

_CLOTHING_TERMS = (
    "abbigliamento",
    "capi",
    "vestiti",
    "abiti",
    "abiti da sposa",
    "calzature",
    "scarpe",
    "tessile",
    "tessili",
    "stock moda",
    "campionario sposa",
)
_LOT_TERMS = (
    "lotto",
    "lotti",
    "stock",
    "rimanenze",
    "rimanenze di magazzino",
    "magazzino",
    "partita",
    "campionario",
)
_SALE_TERMS = (
    "asta",
    "asta giudiziaria",
    "vendita",
    "vendita giudiziaria",
    "vendita fallimentare",
    "in vendita",
    "svendita",
    "prezzo base",
    "offerta minima",
    "disponibile",
    "disponibili",
)
_ACTIVE_TERMS = (
    "asta in corso",
    "in vendita",
    "disponibile",
    "disponibili",
    "prezzo base",
    "offerta minima",
    "presenta offerta",
    "partecipa all'asta",
    "partecipa alla vendita",
    "scadenza",
    "termine offerte",
)
_ENDED_TERMS = (
    "asta conclusa",
    "asta chiusa",
    "vendita conclusa",
    "vendita chiusa",
    "venduto",
    "venduta",
    "aggiudicato",
    "aggiudicata",
    "terminata",
    "terminato",
    "scaduta",
    "scaduto",
)
_ENTITY_GENERIC_TOKENS = {
    "moda",
    "fashion",
    "italia",
    "italy",
    "societa",
    "società",
}

PageFetcher = Callable[[str], "ItalyPublicPage"]


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _utc(value: datetime | None = None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc)


def _term_present(text: str, term: str) -> bool:
    normalized_text = _normalise(text)
    normalized_term = _normalise(term)
    if not normalized_term:
        return False
    return re.search(
        rf"(?<!\w){re.escape(normalized_term)}(?!\w)",
        normalized_text,
        flags=re.UNICODE,
    ) is not None


def _matched(text: str, terms: tuple[str, ...]) -> list[str]:
    return sorted({term for term in terms if _term_present(text, term)})


def _approved_public_https_url(value: object) -> str | None:
    canonical = _canonical_url(value)
    if not canonical:
        return None
    parsed = urlsplit(canonical)
    host = (parsed.hostname or "").casefold().rstrip(".")
    if not host or host == "localhost" or host.endswith(".local"):
        return None
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        return None
    if "." not in host and address is None:
        return None
    return canonical


class _PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self._in_title = False
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered = tag.casefold()
        if lowered in {"script", "style", "noscript"}:
            self._ignored_depth += 1
        if lowered == "title":
            self._in_title = True
        if lowered == "meta":
            values = {key.casefold(): value or "" for key, value in attrs}
            key = values.get("property") or values.get("name")
            content = values.get("content")
            if key and content:
                self.meta[key.casefold()] = content

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.casefold()
        if lowered == "title":
            self._in_title = False
        if lowered in {"script", "style", "noscript"} and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        text = _compact(data)
        if not text:
            return
        if self._in_title:
            self.title_parts.append(text)
        if not self._ignored_depth:
            self.text_parts.append(text)


@dataclass(frozen=True, slots=True)
class ItalyPublicPage:
    requested_url: str
    final_url: str
    status_code: int
    content_type: str
    response_bytes: int
    sha256: str
    html: str


def fetch_italy_public_page(url: str) -> ItalyPublicPage:
    """Fetch one already-discovered public HTTPS page with a strict byte bound."""
    canonical = _approved_public_https_url(url)
    if canonical is None:
        raise ValueError("Italy exact-lot verification requires a public HTTPS URL")
    request = Request(
        canonical,
        headers={
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": "opportunity-engine-italy-exact-lot/1.0",
        },
    )
    with urlopen(request, timeout=30) as response:  # noqa: S310 - URL is public HTTPS gated above
        final_url = _approved_public_https_url(response.geturl())
        if final_url is None:
            raise ValueError("Redirect left the approved public HTTPS surface")
        content_type = _compact(response.headers.get("Content-Type")).casefold()
        if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
            raise ValueError(f"Unsupported content type: {content_type or 'missing'}")
        payload = response.read(MAX_RESPONSE_BYTES + 1)
        if len(payload) > MAX_RESPONSE_BYTES:
            raise ValueError("Italy exact-lot page exceeded bounded response size")
        charset = response.headers.get_content_charset() or "utf-8"
        html_text = payload.decode(charset, errors="replace")
        return ItalyPublicPage(
            requested_url=canonical,
            final_url=final_url,
            status_code=int(getattr(response, "status", 200) or 200),
            content_type=content_type,
            response_bytes=len(payload),
            sha256=sha256(payload).hexdigest(),
            html=html_text,
        )


def _entity_tokens(target_label: object) -> list[str]:
    tokens = [
        token
        for token in _significant_tokens(target_label)
        if token not in _ENTITY_GENERIC_TOKENS
    ]
    return tokens or _significant_tokens(target_label)


def _parse_number(value: str) -> float | None:
    raw = value.strip().replace(" ", "")
    if not raw:
        return None
    if "," in raw and "." in raw:
        if raw.rfind(",") > raw.rfind("."):
            raw = raw.replace(".", "").replace(",", ".")
        else:
            raw = raw.replace(",", "")
    elif "," in raw:
        tail = raw.rsplit(",", 1)[-1]
        raw = raw.replace(".", "")
        raw = raw.replace(",", "." if len(tail) <= 2 else "")
    else:
        parts = raw.split(".")
        if len(parts) > 1 and all(len(part) == 3 for part in parts[1:]):
            raw = "".join(parts)
    try:
        return float(raw)
    except ValueError:
        return None


def _extract_quantity(text: str) -> int | None:
    patterns = (
        r"\b(?:lotto\s+(?:di\s+)?)?(\d{1,7})\s+(?:capi|pezzi|articoli|paia|abiti|vestiti|calzature)\b",
        r"\bquantit[aà]\s*[:\-]?\s*(\d{1,7})\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def _extract_price_eur(text: str) -> float | None:
    patterns = (
        r"\b(?:prezzo\s+base|offerta\s+minima|base\s+d['’]asta|prezzo)\s*[:\-]?\s*(?:€\s*)?([0-9][0-9., ]{0,18})\s*(?:€|eur)?\b",
        r"€\s*([0-9][0-9., ]{0,18})",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            value = _parse_number(match.group(1))
            if value is not None:
                return value
    return None


def _extract_deadline(text: str) -> str | None:
    pattern = (
        r"\b(?:scadenza|termine(?:\s+delle)?\s+offerte|fine\s+asta)\s*[:\-]?\s*"
        r"(\d{1,2}[/.\-]\d{1,2}[/.\-]\d{4}(?:\s+(?:alle\s+)?\d{1,2}[:.]\d{2})?)"
    )
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return _compact(match.group(1)) if match else None


def _extract_location(text: str) -> str | None:
    pattern = r"\b(?:luogo|ubicazione|localit[aà]|sede)\s*[:\-]\s*([^|;]{2,100}?)(?=\s{2,}|\b(?:prezzo|asta|lotto|quantit[aà]|scadenza)\b|$)"
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return None
    value = _compact(match.group(1)).strip(" -–—,.;")
    return value[:100] or None


def parse_italy_exact_lot_page(
    page: ItalyPublicPage,
    *,
    target_label: object,
) -> dict[str, Any]:
    """Extract bounded evidence and classify one original Italy sale page."""
    parser = _PageParser()
    parser.feed(page.html)
    title = _compact(" ".join(parser.title_parts))
    if not title:
        title = _compact(parser.meta.get("og:title"))
    description = _compact(
        parser.meta.get("description") or parser.meta.get("og:description")
    )
    visible_text = _compact(" ".join(parser.text_parts))[:250_000]
    corpus = _compact(" ".join(value for value in (title, description, visible_text) if value))
    normalized = _normalise(corpus)

    clothing = _matched(corpus, _CLOTHING_TERMS)
    lot_terms = _matched(corpus, _LOT_TERMS)
    sale_terms = _matched(corpus, _SALE_TERMS)
    active_terms = _matched(corpus, _ACTIVE_TERMS)
    ended_terms = _matched(corpus, _ENDED_TERMS)

    target_tokens = _entity_tokens(target_label)
    matched_tokens = [token for token in target_tokens if token in normalized]
    entity_match = bool(target_tokens) and len(matched_tokens) == len(target_tokens)
    exact_lot_evidence = bool(clothing and lot_terms and sale_terms)

    if ended_terms:
        sale_status = "ENDED"
    elif active_terms:
        sale_status = "ACTIVE"
    else:
        sale_status = "UNKNOWN"

    quantity = _extract_quantity(corpus)
    price_eur = _extract_price_eur(corpus)
    deadline = _extract_deadline(corpus)
    location = _extract_location(corpus)
    detail_count = sum(value is not None for value in (quantity, price_eur, deadline, location))
    commercial_lead_verified = bool(
        entity_match and exact_lot_evidence and sale_status == "ACTIVE"
    )

    if not entity_match:
        verification_status = "SOURCE_PAGE_VERIFIED_ENTITY_NOT_CONFIRMED"
    elif not exact_lot_evidence:
        verification_status = "SOURCE_PAGE_VERIFIED_NOT_EXACT_CLOTHING_LOT"
    elif sale_status == "ENDED":
        verification_status = "SOURCE_PAGE_VERIFIED_ENDED_LOT"
    elif sale_status != "ACTIVE":
        verification_status = "SOURCE_PAGE_VERIFIED_SALE_STATUS_UNCONFIRMED"
    else:
        verification_status = "VERIFIED_ACTIVE_EXACT_LOT_LEAD"

    return {
        "title": title or None,
        "meta_description": description or None,
        "canonical_source_url": _approved_public_https_url(page.final_url),
        "response_bytes": page.response_bytes,
        "response_sha256": page.sha256,
        "target_tokens": target_tokens,
        "source_page_matched_target_tokens": matched_tokens,
        "entity_link_verified": entity_match,
        "clothing_terms": clothing,
        "lot_terms": lot_terms,
        "sale_terms": sale_terms,
        "active_sale_terms": active_terms,
        "ended_sale_terms": ended_terms,
        "exact_lot_evidence": exact_lot_evidence,
        "sale_status": sale_status,
        "quantity": quantity,
        "source_price_eur": price_eur,
        "currency": "EUR" if price_eur is not None else None,
        "sale_deadline_text": deadline,
        "location": location,
        "commercial_detail_count": detail_count,
        "commercial_facts_confirmed": commercial_lead_verified,
        "commercial_lead_verified": commercial_lead_verified,
        "source_page_verification_status": verification_status,
    }


def _lead_rows(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw_case in report.get("cases") or []:
        if not isinstance(raw_case, Mapping):
            continue
        country = _compact(raw_case.get("country")).upper()
        if country != "IT":
            continue
        for raw_lead in raw_case.get("leads") or []:
            if not isinstance(raw_lead, Mapping):
                continue
            if _compact(raw_lead.get("verification_status")) != "UNVERIFIED_PUBLIC_WEB_SEARCH_HIT":
                continue
            rows.append(
                {
                    "case_id": raw_case.get("case_id"),
                    "case_title": raw_case.get("case_title"),
                    "target_label": raw_case.get("target_label") or raw_case.get("case_title"),
                    "follow_up_stage": raw_case.get("follow_up_stage"),
                    "lead": dict(raw_lead),
                }
            )
    rows.sort(
        key=lambda row: (
            -int(row["lead"].get("follow_up_relevance_score") or 0),
            int(row["lead"].get("search_rank") or 999),
            _compact(row["lead"].get("source_url")),
        )
    )
    return rows


def _base_row(context: Mapping[str, Any], canonical_url: str | None) -> dict[str, Any]:
    lead = context["lead"]
    stable = _compact(lead.get("lead_id")) or _compact(lead.get("source_url"))
    return {
        "verification_id": "italy-exact-lot:"
        + sha256(f"{context.get('case_id')}|{stable}".encode("utf-8")).hexdigest()[:24],
        "case_id": context.get("case_id"),
        "case_title": context.get("case_title"),
        "target_label": context.get("target_label"),
        "follow_up_stage": context.get("follow_up_stage"),
        "lead_id": lead.get("lead_id"),
        "lead_kind": lead.get("lead_kind"),
        "search_result_title": lead.get("title"),
        "source_url": lead.get("source_url"),
        "canonical_source_url": canonical_url,
        "source_kind": "ITALY_PUBLIC_EXACT_LOT_PAGE",
        "source_page_verified": False,
        "entity_link_verified": False,
        "exact_lot_evidence": False,
        "sale_status": "UNKNOWN",
        "commercial_facts_confirmed": False,
        "commercial_lead_verified": False,
        "promotion_to_opportunity_allowed": False,
        "top5_eligible": False,
        "analysis_eligible": False,
        "decision_owner": DECISION_OWNER,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def run_italy_exact_lot_verification(
    follow_up_report: Mapping[str, Any],
    *,
    observed_at: datetime | None = None,
    max_verification_pages: int = DEFAULT_MAX_VERIFICATION_PAGES,
    page_fetcher: PageFetcher | None = None,
) -> dict[str, Any]:
    """Verify bounded Italy follow-up leads against their original source pages."""
    bounded = max(0, min(MAX_VERIFICATION_PAGES, int(max_verification_pages)))
    fetcher = page_fetcher or fetch_italy_public_page
    now = _utc(observed_at)
    input_rows = _lead_rows(follow_up_report)

    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    requests = verified_pages = failed = unsupported = budget_skipped = 0

    for context in input_rows:
        lead = context["lead"]
        canonical = _approved_public_https_url(lead.get("source_url"))
        dedupe_key = canonical or _compact(lead.get("source_url"))
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        row = _base_row(context, canonical)

        if canonical is None:
            unsupported += 1
            row["source_page_verification_status"] = "UNSUPPORTED_OR_NON_PUBLIC_HTTPS_URL"
            row["reason"] = "Only the original bounded public HTTPS lead URL may be fetched"
            results.append(row)
            continue
        if requests >= bounded:
            budget_skipped += 1
            row["source_page_verification_status"] = "SKIPPED_BOUNDED_VERIFICATION_BUDGET"
            row["reason"] = f"bounded page budget exhausted at {bounded}"
            results.append(row)
            continue

        requests += 1
        try:
            page = fetcher(canonical)
            details = parse_italy_exact_lot_page(
                page,
                target_label=context.get("target_label"),
            )
            row.update(details)
            row["source_page_verified"] = True
            verified_pages += 1
        except Exception as exc:
            failed += 1
            row["source_page_verification_status"] = "SOURCE_PAGE_VERIFICATION_FAILED"
            row["error_type"] = type(exc).__name__
            row["error"] = _compact(exc)[:500]
            row["reason"] = "source failure retained; no bypass, guessed facts, or promotion"
        results.append(row)

    commercially_verified = sum(bool(row.get("commercial_lead_verified")) for row in results)
    ended = sum(row.get("sale_status") == "ENDED" for row in results)
    unknown = sum(
        row.get("source_page_verified") is True and row.get("sale_status") == "UNKNOWN"
        for row in results
    )
    with_quantity = sum(row.get("quantity") is not None for row in results)
    with_price = sum(row.get("source_price_eur") is not None for row in results)
    with_deadline = sum(bool(row.get("sale_deadline_text")) for row in results)
    with_location = sum(bool(row.get("location")) for row in results)

    if not input_rows:
        status = "VALID_ZERO_NO_ITALY_FOLLOW_UP_LEADS"
    elif requests == 0:
        status = "VALID_ZERO_NO_FETCHABLE_PUBLIC_URLS"
    elif failed and verified_pages:
        status = "PARTIAL_SUCCESS"
    elif failed:
        status = "FAILED"
    else:
        status = "SUCCESS"

    return {
        "schema_version": SCHEMA_VERSION,
        "engine_version": ENGINE_VERSION,
        "generated_at": now.isoformat(),
        "status": status,
        "purpose": "VERIFY_ITALY_FOLLOW_UP_LEADS_ON_ORIGINAL_PUBLIC_EXACT_LOT_PAGES",
        "candidate_lead_count": len(input_rows),
        "deduplicated_lead_count": len(results),
        "verification_request_count": requests,
        "source_page_verified_count": verified_pages,
        "source_page_failed_count": failed,
        "unsupported_url_count": unsupported,
        "budget_skipped_count": budget_skipped,
        "verified_active_exact_lot_lead_count": commercially_verified,
        "ended_lot_count": ended,
        "sale_status_unknown_count": unknown,
        "verified_with_quantity_count": with_quantity,
        "verified_with_price_count": with_price,
        "verified_with_deadline_count": with_deadline,
        "verified_with_location_count": with_location,
        "verifications": results,
        "search_hit_alone_is_never_proof": True,
        "source_page_verification_required": True,
        "promotion_to_opportunity_allowed": False,
        "top5_eligible": False,
        "analysis_eligible": False,
        "decision_owner": DECISION_OWNER,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }
