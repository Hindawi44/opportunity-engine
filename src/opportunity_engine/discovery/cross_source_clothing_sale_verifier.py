"""Strict cross-source verifier for clothing bankruptcy inventory sales.

The verifier joins two bounded public evidence channels:

* Konkurs.app active clothing-industry bankruptcy records.
* Auksjonen active clothing listings with explicit inventory-lot wording.

A bankruptcy record is never a sale. An Auksjonen lot is never linked to a
bankruptcy estate merely because names look similar. Commercial verification
requires an exact nine-digit organisation-number match in the public item-page
evidence. An exact normalized company-name match is retained only as a human
review lead and remains ineligible for analysis and commercial Top 5.

No paid search, AI API, login, contact, bid, purchase, reservation, or payment is
performed.
"""
from __future__ import annotations

import html
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from opportunity_engine.discovery.auksjonen_multi_category_adapter import (
    AuksjonenMultiCategoryCollector,
    AuksjonenMultiCategoryResult,
)
from opportunity_engine.discovery.auksjonen_public_api_adapter import (
    AuksjonenLiveClothingListing,
)
from opportunity_engine.discovery.konkurs_app_clothing_adapter import (
    CLOTHING_NACE_CODES,
    DEFAULT_LOOKBACK_DAYS,
    DEFAULT_PAGE_SIZE,
    KonkursAppClothingLead,
    build_api_endpoint,
    is_approved_api_endpoint,
    normalize_api_record,
)

MAX_BANKRUPTCY_LEADS = 100
MAX_DETAIL_PAGES = 5
_GENERIC_SELLER_LABELS = frozenset(
    {
        "PRIVATPERSON IKKE AV AUKSJONEN NO",
        "NAERINGSVIRKSOMHET IKKE AV AUKSJONEN NO",
        "NÆRINGSVIRKSOMHET IKKE AV AUKSJONEN NO",
        "AUKSJONEN NO AS",
    }
)
_ENTITY_PATTERNS = (
    re.compile(r"\bselges\s+på\s+vegne\s+av\s+([^\r\n.·;]{2,160})", re.I),
    re.compile(r"\bsalg\s+på\s+vegne\s+av\s+([^\r\n.·;]{2,160})", re.I),
    re.compile(r"\boppdragsgiver\s*[:\-]?\s*([^\r\n.·;]{2,160})", re.I),
    re.compile(r"\bselges\s+av\s+([^\r\n.·;]{2,160})", re.I),
)
_ORGNR_LABELLED_PATTERN = re.compile(
    r"(?:organisasjonsnummer|org\.?\s*nr\.?|orgnr)\s*[:#-]?\s*"
    r"(\d{3}[\s.]?\d{3}[\s.]?\d{3})",
    re.I,
)
_LEGAL_SUFFIX_PATTERN = re.compile(
    r"\b(?:KONKURSBO|TVANGSAVVIKLINGSBO|DØDSBO|BOET|KONKURS)\b",
    re.I,
)


def _compact(value: object) -> str:
    return " ".join(str(value or "").split())


def _valid_orgnr(value: object) -> str | None:
    digits = re.sub(r"\D", "", str(value or ""))
    return digits if len(digits) == 9 else None


def normalize_entity_name(value: object) -> str:
    """Normalize an entity name for exact, not fuzzy, comparison."""
    text = unicodedata.normalize("NFKD", _compact(value)).encode(
        "ascii", "ignore"
    ).decode("ascii")
    text = _LEGAL_SUFFIX_PATTERN.sub(" ", text)
    text = re.sub(r"\([^)]*ikke\s+av\s+Auksjonen\.no[^)]*\)", " ", text, flags=re.I)
    text = re.sub(r"[^A-Za-z0-9]+", " ", text).upper()
    return " ".join(text.split())


@dataclass(frozen=True, slots=True)
class BankruptcyIdentityLead:
    lead: KonkursAppClothingLead
    debtor_orgnr: str | None

    def to_dict(self) -> dict[str, Any]:
        value = self.lead.to_dict()
        value["debtor_orgnr"] = self.debtor_orgnr
        return value


class _ItemPageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.scripts: dict[str, str] = {}
        self._script_id: str | None = None
        self._script_parts: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        values = {key.casefold(): value or "" for key, value in attrs}
        if tag.casefold() == "meta":
            key = values.get("property") or values.get("name")
            content = values.get("content")
            if key and content:
                self.meta[key.casefold()] = content
        elif tag.casefold() == "script":
            script_id = values.get("id")
            if script_id:
                self._script_id = script_id
                self._script_parts = []

    def handle_data(self, data: str) -> None:
        if self._script_id is not None:
            self._script_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "script" and self._script_id is not None:
            self.scripts[self._script_id] = "".join(self._script_parts)
            self._script_id = None
            self._script_parts = []


@dataclass(frozen=True, slots=True)
class AuksjonenItemIdentityEvidence:
    item_url: str
    object_id: int
    seller_label: str | None
    project_auction_text: str | None
    meta_description: str | None
    entity_names: tuple[str, ...]
    organisation_numbers: tuple[str, ...]
    source_status: str
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_url": self.item_url,
            "object_id": self.object_id,
            "seller_label": self.seller_label,
            "project_auction_text": self.project_auction_text,
            "meta_description": self.meta_description,
            "entity_names": list(self.entity_names),
            "organisation_numbers": list(self.organisation_numbers),
            "source_status": self.source_status,
            "error": self.error,
            "contact_data_retained": False,
        }


def is_approved_auksjonen_item_url(url: str) -> bool:
    parsed = urlparse(_compact(url))
    parts = [part for part in parsed.path.split("/") if part]
    return (
        parsed.scheme == "https"
        and parsed.hostname == "ny.auksjonen.no"
        and len(parts) >= 4
        and parts[0] == "auksjon"
        and parts[1] == "torget"
        and parts[-1].isdigit()
    )


def _decode_json_script(text: str) -> Mapping[str, Any] | None:
    if not text.strip():
        return None
    try:
        value = json.loads(html.unescape(text))
    except (json.JSONDecodeError, TypeError):
        return None
    return value if isinstance(value, Mapping) else None


def _nested_mapping(value: object, *keys: str) -> Mapping[str, Any] | None:
    current: object = value
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current if isinstance(current, Mapping) else None


def _extract_entities(corpus: Sequence[str]) -> tuple[str, ...]:
    names: list[str] = []
    for text in corpus:
        for pattern in _ENTITY_PATTERNS:
            for match in pattern.finditer(text):
                candidate = _compact(match.group(1)).strip(" :-–—")
                normalized = normalize_entity_name(candidate)
                if (
                    len(normalized) < 3
                    or normalized in _GENERIC_SELLER_LABELS
                    or normalized.startswith("AUKSJONEN NO")
                ):
                    continue
                if candidate not in names:
                    names.append(candidate)
    return tuple(names)


def _extract_orgnrs(corpus: Sequence[str]) -> tuple[str, ...]:
    numbers: list[str] = []
    for text in corpus:
        for match in _ORGNR_LABELLED_PATTERN.finditer(text):
            value = _valid_orgnr(match.group(1))
            if value and value not in numbers:
                numbers.append(value)
    return tuple(numbers)


def parse_auksjonen_item_identity(
    html_text: str,
    *,
    item_url: str,
    object_id: int,
) -> AuksjonenItemIdentityEvidence:
    """Extract only public seller/company identity evidence from one item page."""
    parser = _ItemPageParser()
    parser.feed(html_text)

    structured = _decode_json_script(parser.scripts.get("structured-data-product", ""))
    ng_state = _decode_json_script(parser.scripts.get("ng-state", ""))
    auction_state: Mapping[str, Any] = {}
    if ng_state is not None:
        candidate = ng_state.get(f"auction-{object_id}")
        if isinstance(candidate, Mapping):
            auction_state = candidate

    seller_label: str | None = None
    offers = _nested_mapping(structured, "offers") if structured else None
    seller = _nested_mapping(offers, "seller") if offers else None
    if seller:
        seller_label = _compact(seller.get("name")) or None

    project_text = _compact(auction_state.get("projectAuctionText")) or None
    meta_description = (
        _compact(parser.meta.get("description"))
        or _compact(parser.meta.get("og:description"))
        or None
    )
    corpus = tuple(
        text
        for text in (
            project_text,
            meta_description,
            seller_label,
            _compact(auction_state.get("description")) or None,
        )
        if text
    )
    entities = list(_extract_entities(corpus))
    if seller_label:
        normalized_seller = normalize_entity_name(seller_label)
        if (
            normalized_seller
            and normalized_seller not in _GENERIC_SELLER_LABELS
            and not normalized_seller.startswith("AUKSJONEN NO")
            and seller_label not in entities
        ):
            entities.append(seller_label)

    return AuksjonenItemIdentityEvidence(
        item_url=item_url,
        object_id=object_id,
        seller_label=seller_label,
        project_auction_text=project_text,
        meta_description=meta_description,
        entity_names=tuple(entities),
        organisation_numbers=_extract_orgnrs(corpus),
        source_status="PARSED",
    )


@dataclass(frozen=True, slots=True)
class CrossSourceVerificationRecord:
    listing: AuksjonenLiveClothingListing
    evidence: AuksjonenItemIdentityEvidence
    matched_lead: BankruptcyIdentityLead | None
    match_method: str
    verification_state: str
    inventory_sale_verified: bool
    requires_human_verification: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "listing": self.listing.to_dict(),
            "evidence": self.evidence.to_dict(),
            "matched_bankruptcy_lead": (
                self.matched_lead.to_dict() if self.matched_lead else None
            ),
            "match_method": self.match_method,
            "verification_state": self.verification_state,
            "inventory_sale_verified": self.inventory_sale_verified,
            "inventory_quantity_verified": self.listing.inventory_lot_signal,
            "top5_eligible": self.inventory_sale_verified,
            "analysis_eligible": self.inventory_sale_verified,
            "requires_human_verification": self.requires_human_verification,
            "automatic_contact": False,
            "automatic_bid": False,
            "automatic_purchase_decision": False,
            "automatic_payment": False,
        }


def match_listing_to_bankruptcy_leads(
    listing: AuksjonenLiveClothingListing,
    evidence: AuksjonenItemIdentityEvidence,
    leads: Sequence[BankruptcyIdentityLead],
) -> CrossSourceVerificationRecord:
    """Apply exact organisation-number, then exact normalized-name matching."""
    if listing.listing_status != "ACTIVE" or not listing.inventory_lot_signal:
        return CrossSourceVerificationRecord(
            listing=listing,
            evidence=evidence,
            matched_lead=None,
            match_method="NONE",
            verification_state="NOT_AN_ACTIVE_INVENTORY_LOT",
            inventory_sale_verified=False,
            requires_human_verification=False,
        )

    evidence_orgnrs = set(evidence.organisation_numbers)
    for identity_lead in leads:
        candidate_orgnrs = {
            value
            for value in (
                identity_lead.debtor_orgnr,
                identity_lead.lead.estate_orgnr,
            )
            if value
        }
        if evidence_orgnrs.intersection(candidate_orgnrs):
            return CrossSourceVerificationRecord(
                listing=listing,
                evidence=evidence,
                matched_lead=identity_lead,
                match_method="EXACT_ORGANISATION_NUMBER",
                verification_state="VERIFIED_ACTIVE_INVENTORY_SALE",
                inventory_sale_verified=True,
                requires_human_verification=False,
            )

    evidence_names = {
        normalize_entity_name(name)
        for name in evidence.entity_names
        if normalize_entity_name(name)
    }
    for identity_lead in leads:
        candidate_names = {
            normalize_entity_name(identity_lead.lead.debtor_name),
            normalize_entity_name(identity_lead.lead.estate_name),
        }
        candidate_names.discard("")
        if evidence_names.intersection(candidate_names):
            return CrossSourceVerificationRecord(
                listing=listing,
                evidence=evidence,
                matched_lead=identity_lead,
                match_method="EXACT_NORMALIZED_COMPANY_NAME",
                verification_state="SALE_LISTING_REQUIRES_IDENTITY_VERIFICATION",
                inventory_sale_verified=False,
                requires_human_verification=True,
            )

    return CrossSourceVerificationRecord(
        listing=listing,
        evidence=evidence,
        matched_lead=None,
        match_method="NONE",
        verification_state="NO_BANKRUPTCY_IDENTITY_MATCH",
        inventory_sale_verified=False,
        requires_human_verification=False,
    )


@dataclass(frozen=True, slots=True)
class CrossSourceVerificationResult:
    captured_at: str
    bankruptcy_from_date: str
    bankruptcy_requests: int
    bankruptcy_items_received: int
    bankruptcy_leads: tuple[BankruptcyIdentityLead, ...]
    auksjonen_result: AuksjonenMultiCategoryResult
    records: tuple[CrossSourceVerificationRecord, ...]
    detail_pages_requested: int
    scan_complete: bool
    errors: tuple[dict[str, str], ...] = ()

    @property
    def verified_sales(self) -> tuple[CrossSourceVerificationRecord, ...]:
        return tuple(record for record in self.records if record.inventory_sale_verified)

    @property
    def review_leads(self) -> tuple[CrossSourceVerificationRecord, ...]:
        return tuple(
            record for record in self.records if record.requires_human_verification
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "cross-source-clothing-sale-verifier-1.0",
            "captured_at": self.captured_at,
            "bankruptcy_from_date": self.bankruptcy_from_date,
            "bankruptcy_requests": self.bankruptcy_requests,
            "bankruptcy_items_received": self.bankruptcy_items_received,
            "bankruptcy_lead_count": len(self.bankruptcy_leads),
            "auksjonen_scan": self.auksjonen_result.to_dict(),
            "active_inventory_lots_checked": len(self.records),
            "detail_pages_requested": self.detail_pages_requested,
            "verified_inventory_sales": len(self.verified_sales),
            "review_lead_count": len(self.review_leads),
            "commercial_top5_count": min(5, len(self.verified_sales)),
            "scan_complete": self.scan_complete,
            "records": [record.to_dict() for record in self.records],
            "errors": list(self.errors),
            "paid_search_used": False,
            "openai_api_used": False,
            "automatic_contact": False,
            "automatic_bid": False,
            "automatic_purchase_decision": False,
            "automatic_payment": False,
        }


class CrossSourceClothingSaleVerifier:
    """Read bounded public evidence and enforce the strict cross-source gate."""

    def __init__(
        self,
        *,
        lookback_days: int = DEFAULT_LOOKBACK_DAYS,
        bankruptcy_page_size: int = DEFAULT_PAGE_SIZE,
        max_bankruptcy_leads: int = MAX_BANKRUPTCY_LEADS,
        max_detail_pages: int = MAX_DETAIL_PAGES,
        timeout_seconds: float = 30.0,
        today: date | None = None,
        fetch_json: Callable[[str], Mapping[str, Any]] | None = None,
        fetch_html: Callable[[str], str] | None = None,
        auksjonen_collector: AuksjonenMultiCategoryCollector | None = None,
    ) -> None:
        if not 1 <= lookback_days <= 730:
            raise ValueError("lookback_days must be between 1 and 730")
        if not 1 <= bankruptcy_page_size <= 50:
            raise ValueError("bankruptcy_page_size must be between 1 and 50")
        if not 1 <= max_bankruptcy_leads <= MAX_BANKRUPTCY_LEADS:
            raise ValueError(
                f"max_bankruptcy_leads must be between 1 and {MAX_BANKRUPTCY_LEADS}"
            )
        if not 1 <= max_detail_pages <= MAX_DETAIL_PAGES:
            raise ValueError(
                f"max_detail_pages must be between 1 and {MAX_DETAIL_PAGES}"
            )
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.lookback_days = lookback_days
        self.bankruptcy_page_size = bankruptcy_page_size
        self.max_bankruptcy_leads = max_bankruptcy_leads
        self.max_detail_pages = max_detail_pages
        self.timeout_seconds = timeout_seconds
        self.today = today or datetime.now(timezone.utc).date()
        self.fetch_json = fetch_json or self._fetch_json
        self.fetch_html = fetch_html or self._fetch_html
        self.auksjonen_collector = (
            auksjonen_collector or AuksjonenMultiCategoryCollector()
        )

    def _fetch_json(self, url: str) -> Mapping[str, Any]:
        if not is_approved_api_endpoint(url):
            raise ValueError("endpoint is outside the approved Konkurs.app scope")
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "OpportunityEngine/Cross-Source-Clothing-Verifier-1.0",
            },
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310
            if int(response.status) != 200:
                raise RuntimeError(f"Konkurs.app API returned HTTP {response.status}")
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, Mapping):
            raise RuntimeError("Konkurs.app API response is not a JSON object")
        return payload

    def _fetch_html(self, url: str) -> str:
        if not is_approved_auksjonen_item_url(url):
            raise ValueError("URL is outside the approved Auksjonen item scope")
        request = Request(
            url,
            headers={
                "Accept": "text/html,application/xhtml+xml",
                "User-Agent": "OpportunityEngine/Cross-Source-Clothing-Verifier-1.0",
            },
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310
            if int(response.status) != 200:
                raise RuntimeError(f"Auksjonen item page returned HTTP {response.status}")
            return response.read().decode("utf-8", errors="replace")

    def _collect_bankruptcy_leads(
        self,
    ) -> tuple[str, int, int, tuple[BankruptcyIdentityLead, ...], list[dict[str, str]]]:
        from_date = (self.today - timedelta(days=self.lookback_days)).isoformat()
        errors: list[dict[str, str]] = []
        received = 0
        by_estate_orgnr: dict[str, BankruptcyIdentityLead] = {}
        endpoints = [
            build_api_endpoint(
                code,
                from_date=from_date,
                page_size=self.bankruptcy_page_size,
            )
            for code in CLOTHING_NACE_CODES
        ]
        for endpoint in endpoints:
            try:
                payload = self.fetch_json(endpoint)
                raw_data = payload.get("data")
                if not isinstance(raw_data, Sequence) or isinstance(
                    raw_data, (str, bytes)
                ):
                    raise RuntimeError("Konkurs.app API response lacks a data array")
                received += len(raw_data)
                for record in raw_data:
                    if not isinstance(record, Mapping):
                        continue
                    lead = normalize_api_record(record, today=self.today)
                    if lead is None:
                        continue
                    by_estate_orgnr.setdefault(
                        lead.estate_orgnr,
                        BankruptcyIdentityLead(
                            lead=lead,
                            debtor_orgnr=_valid_orgnr(record.get("debitor_orgnr")),
                        ),
                    )
            except Exception as exc:
                errors.append({"url": endpoint, "stage": "bankruptcy", "error": str(exc)})
        leads = sorted(
            by_estate_orgnr.values(),
            key=lambda item: (
                -item.lead.priority_score,
                item.lead.opened_date or "",
                item.lead.estate_orgnr,
            ),
        )[: self.max_bankruptcy_leads]
        return from_date, len(endpoints), received, tuple(leads), errors

    def collect(self) -> CrossSourceVerificationResult:
        captured_at = datetime.now(timezone.utc).isoformat()
        from_date, request_count, received, leads, errors = (
            self._collect_bankruptcy_leads()
        )
        auksjonen_result = self.auksjonen_collector.collect()
        combined = auksjonen_result.combined
        lots = combined.inventory_opportunities[: self.max_detail_pages]
        records: list[CrossSourceVerificationRecord] = []

        for listing in lots:
            try:
                page_html = self.fetch_html(listing.url)
                evidence = parse_auksjonen_item_identity(
                    page_html,
                    item_url=listing.url,
                    object_id=listing.object_id,
                )
                records.append(match_listing_to_bankruptcy_leads(listing, evidence, leads))
            except Exception as exc:
                errors.append(
                    {
                        "url": listing.url,
                        "stage": "item_identity",
                        "error": str(exc),
                    }
                )
                evidence = AuksjonenItemIdentityEvidence(
                    item_url=listing.url,
                    object_id=listing.object_id,
                    seller_label=None,
                    project_auction_text=None,
                    meta_description=None,
                    entity_names=(),
                    organisation_numbers=(),
                    source_status="ERROR",
                    error=str(exc),
                )
                records.append(
                    CrossSourceVerificationRecord(
                        listing=listing,
                        evidence=evidence,
                        matched_lead=None,
                        match_method="NONE",
                        verification_state="ITEM_IDENTITY_READ_FAILED",
                        inventory_sale_verified=False,
                        requires_human_verification=False,
                    )
                )

        scan_complete = (
            not errors
            and auksjonen_result.scan_complete
            and len(lots) == len(combined.inventory_opportunities[: self.max_detail_pages])
        )
        return CrossSourceVerificationResult(
            captured_at=captured_at,
            bankruptcy_from_date=from_date,
            bankruptcy_requests=request_count,
            bankruptcy_items_received=received,
            bankruptcy_leads=leads,
            auksjonen_result=auksjonen_result,
            records=tuple(records),
            detail_pages_requested=len(lots),
            scan_complete=scan_complete,
            errors=tuple(errors),
        )


def write_cross_source_artifacts(
    result: CrossSourceVerificationResult,
    output_dir: str | Path,
) -> dict[str, Path]:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    report_path = target / "cross-source-verification.json"
    review_path = target / "cross-source-review-top5.json"
    commercial_path = target / "live-clothing-top5.json"
    summary_path = target / "operator-summary.txt"

    report_path.write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    review_path.write_text(
        json.dumps(
            [record.to_dict() for record in result.review_leads[:5]],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    commercial_path.write_text(
        json.dumps(
            [record.to_dict() for record in result.verified_sales[:5]],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    lines = [
        "Cross-source clothing inventory sale verifier",
        f"Konkurs.app API requests: {result.bankruptcy_requests}",
        f"Bankruptcy records received: {result.bankruptcy_items_received}",
        f"Bankruptcy leads retained: {len(result.bankruptcy_leads)}",
        f"Auksjonen categories scanned: {len(result.auksjonen_result.scans)}",
        f"Active Auksjonen inventory lots checked: {len(result.records)}",
        f"Auksjonen detail pages requested: {result.detail_pages_requested}",
        f"Exact-name review leads: {len(result.review_leads)}",
        f"Exact-orgnr verified inventory sales: {len(result.verified_sales)}",
        f"Commercial Top 5 count: {min(5, len(result.verified_sales))}",
        f"Scan complete: {result.scan_complete}",
        f"Errors: {len(result.errors)}",
        "Paid Brave/OpenAI calls: 0",
        "Automatic contact/bid/purchase/payment: false",
    ]
    if result.verified_sales:
        lines.extend(("", "Verified inventory sales:"))
        for record in result.verified_sales[:5]:
            lines.append(
                f"- {record.listing.title} | {record.listing.city or 'unknown'} | "
                f"{record.listing.url}"
            )
    elif result.review_leads:
        lines.extend(("", "Identity matches requiring human verification:"))
        for record in result.review_leads[:5]:
            company = (
                record.matched_lead.lead.debtor_name
                if record.matched_lead
                else "unknown"
            )
            lines.append(f"- {company} -> {record.listing.title} | {record.listing.url}")
    else:
        lines.extend(("", "No bankruptcy-linked active inventory sale was verified."))
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return {
        "report": report_path,
        "review_top5": review_path,
        "commercial_top5": commercial_path,
        "summary": summary_path,
    }
