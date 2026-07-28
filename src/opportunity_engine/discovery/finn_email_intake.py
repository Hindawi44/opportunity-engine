"""FINN saved-search email intake for Clothing Inventory discovery.

This adapter parses messages that FINN already delivered to an operator-owned
mailbox.  It never connects to FINN, follows tracking links, opens advert pages,
or promotes email claims to verified commercial evidence.

The normalized leads are passed through the existing Clothing Inventory
Discovery Engine.  They remain ``STRONG_LEAD_REQUIRES_VERIFICATION`` with
``analysis_eligible=false`` until the existing manual verification boundary
confirms a specific active sale.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from email import policy
from email.message import Message
from email.parser import BytesParser, Parser
from email.utils import parseaddr
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import parse_qs, unquote, urlparse

from opportunity_engine.discovery.clothing_inventory_search import (
    DiscoveryQuery,
    normalize_public_url,
    run_clothing_inventory_discovery,
    write_discovery_artifacts,
)
from opportunity_engine.discovery.early_opportunity_gate import (
    apply_early_opportunity_gate,
)
from opportunity_engine.discovery.search_provider import SearchHit

FINN_EMAIL_SENDER = "agent@finn.no"
COLLECTION_MODE = "FINN_SAVED_SEARCH_EMAIL"
SCHEMA_VERSION = "finn-saved-search-email-intake-1.0"
_BATCH_SIZE = 20
_FINN_HOSTS = {"finn.no", "www.finn.no"}
_CLICK_HOST = "click.mailsvc.finn.no"
_SUBJECT_PREFIX = "nye annonser:"
_SYMBOLIC_PRICE_TERMS = (
    "send melding",
    "gi bud",
    "pris på forespørsel",
    "pris etter avtale",
)
_GENERIC_LINK_LABELS = (
    "se annonsene",
    "stopp e-postvarsling",
    "endre søket",
    "hjelp",
    "finn.no",
)
_URL_RE = re.compile(r"https://[^\s<>\]\[\"']+", re.IGNORECASE)
_MARKDOWN_LINK_RE = re.compile(
    r"\[([^\]]+)\]\((https://[^)\s]+)\)",
    re.IGNORECASE,
)
_PRICE_RE = re.compile(
    r"(?<!\d)(\d[\d\s.\u00a0]*)(?:\s*)(?:kr|nok)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class FinnEmailMessage:
    """One normalized mailbox message supplied by a trusted mailbox reader."""

    sender: str
    subject: str
    body: str
    received_at: str | None = None
    message_id: str | None = None


@dataclass(frozen=True, slots=True)
class FinnEmailLead:
    """One FINN advert reference extracted without opening the advert page."""

    listing_id: str
    title: str
    url: str
    description: str
    advertised_price_nok: float | None
    advertised_location: str | None
    symbolic_price_detected: bool
    received_at: str | None
    saved_search_name: str
    message_fingerprint: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "listing_id": self.listing_id,
            "title": self.title,
            "url": self.url,
            "advertised_price_nok": self.advertised_price_nok,
            "advertised_location": self.advertised_location,
            "symbolic_price_detected": self.symbolic_price_detected,
            "received_at": self.received_at,
            "saved_search_name": self.saved_search_name,
            "message_fingerprint": self.message_fingerprint,
            "source": "FINN.no",
            "evidence_channel": "FINN_SAVED_SEARCH_EMAIL",
            "commercial_values_verified": False,
            "page_opened": False,
        }


@dataclass(frozen=True, slots=True)
class FinnEmailCollection:
    """Sanitized intake result retained separately from commercial analysis."""

    ingested_at: str
    messages_received: int
    messages_accepted: int
    leads: tuple[FinnEmailLead, ...]
    rejected_messages: tuple[dict[str, str], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "domain": "CLOTHING_INVENTORY",
            "source": "FINN.no",
            "collection_mode": COLLECTION_MODE,
            "ingested_at": self.ingested_at,
            "messages_received": self.messages_received,
            "messages_accepted": self.messages_accepted,
            "leads": [lead.to_dict() for lead in self.leads],
            "rejected_messages": list(self.rejected_messages),
            "network_pages_visited": 0,
            "links_followed": 0,
            "automatic_contact": False,
            "automatic_purchase_decision": False,
            "automatic_bid": False,
            "automatic_reservation": False,
            "automatic_payment": False,
        }


class _AnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.anchors: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag.casefold() != "a":
            return
        values = {key.casefold(): value for key, value in attrs}
        href = str(values.get("href") or "").strip()
        if href:
            self._href = href
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "a" and self._href is not None:
            title = " ".join(" ".join(self._text).split())
            self.anchors.append((self._href, title))
            self._href = None
            self._text = []


@dataclass(frozen=True, slots=True)
class _LinkObservation:
    raw_url: str
    title: str
    position: int


class _FinnEmailProvider:
    name = "FINN Saved-Search Email"

    def __init__(self, batches: Mapping[str, Sequence[SearchHit]]) -> None:
        self._batches = dict(batches)

    def search(
        self,
        query: str,
        *,
        count: int = _BATCH_SIZE,
    ) -> Sequence[SearchHit]:
        return self._batches.get(query, ())[:count]


def message_from_mapping(payload: Mapping[str, Any]) -> FinnEmailMessage:
    """Normalize the small message shape returned by mailbox connectors."""
    sender = str(
        payload.get("sender")
        or payload.get("from_")
        or payload.get("from")
        or ""
    ).strip()
    subject = str(payload.get("subject") or "").strip()
    body = str(
        payload.get("body")
        or payload.get("text")
        or payload.get("snippet")
        or ""
    )
    received_at = _text_or_none(
        payload.get("received_at")
        or payload.get("email_ts")
        or payload.get("date")
    )
    message_id = _text_or_none(
        payload.get("message_id")
        or payload.get("id")
    )
    return FinnEmailMessage(
        sender=sender,
        subject=subject,
        body=body,
        received_at=received_at,
        message_id=message_id,
    )


def message_from_rfc822(payload: bytes | str) -> FinnEmailMessage:
    """Read one RFC822 message using only its decoded text/plain body."""
    parsed = (
        BytesParser(policy=policy.default).parsebytes(payload)
        if isinstance(payload, bytes)
        else Parser(policy=policy.default).parsestr(payload)
    )
    return FinnEmailMessage(
        sender=str(parsed.get("From") or "").strip(),
        subject=str(parsed.get("Subject") or "").strip(),
        body=_plain_message_body(parsed),
        received_at=_text_or_none(parsed.get("Date")),
        message_id=_text_or_none(parsed.get("Message-ID")),
    )


def _plain_message_body(message: Message) -> str:
    if not message.is_multipart():
        content = message.get_content()
        return content if isinstance(content, str) else ""

    plain_parts: list[str] = []
    for part in message.walk():
        if part.get_content_disposition() == "attachment":
            continue
        if part.get_content_type() != "text/plain":
            continue
        content = part.get_content()
        if isinstance(content, str):
            plain_parts.append(content)
    return "\n".join(plain_parts)


def _message_fingerprint(message: FinnEmailMessage) -> str:
    material = message.message_id or "\n".join((
        message.sender,
        message.subject,
        message.received_at or "",
        message.body,
    ))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:20]


def _validate_message(message: FinnEmailMessage) -> str:
    sender = parseaddr(message.sender)[1].casefold()
    if sender != FINN_EMAIL_SENDER:
        raise ValueError("message sender is not FINN saved-search alerts")
    if not message.subject.casefold().startswith(_SUBJECT_PREFIX):
        raise ValueError("message subject is not a FINN new-advert alert")
    if not message.body.strip():
        raise ValueError("message body is empty")
    return message.subject.split(":", 1)[1].strip()


def _decode_tracking_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.netloc.casefold() != _CLICK_HOST:
        return url.strip()
    marker = "/CL0/"
    if not parsed.path.startswith(marker):
        return ""
    encoded_target = parsed.path[len(marker):].split("/", 1)[0]
    target = unquote(encoded_target)
    return target if target.startswith("https://") else ""


def _canonical_finn_item_url(raw_url: str) -> tuple[str, str] | None:
    decoded = _decode_tracking_url(raw_url.rstrip(".,);|"))
    parsed = urlparse(decoded)
    if parsed.scheme.casefold() != "https" or parsed.netloc.casefold() not in _FINN_HOSTS:
        return None

    path = parsed.path.rstrip("/")
    listing_id: str | None = None
    root_match = re.fullmatch(r"/(\d{6,})", path)
    item_match = re.search(r"/recommerce/forsale/item/(\d+)(?:/|$)", path)
    if root_match:
        listing_id = root_match.group(1)
    elif item_match:
        listing_id = item_match.group(1)
    elif path.casefold() == "/bap/forsale/ad.html":
        candidate = (parse_qs(parsed.query).get("finnkode") or [""])[0]
        listing_id = candidate if candidate.isdigit() else None

    if not listing_id:
        return None
    return listing_id, f"https://www.finn.no/{listing_id}"


def _link_observations(body: str) -> list[_LinkObservation]:
    observations: list[_LinkObservation] = []
    claimed_spans: list[tuple[int, int]] = []

    for match in _MARKDOWN_LINK_RE.finditer(body):
        observations.append(_LinkObservation(
            raw_url=match.group(2),
            title=_clean_link_title(match.group(1)),
            position=match.end(),
        ))
        claimed_spans.append(match.span(2))

    parser = _AnchorParser()
    parser.feed(body)
    for href, title in parser.anchors:
        position = body.find(href)
        observations.append(_LinkObservation(
            raw_url=href,
            title=_clean_link_title(title),
            position=max(0, position + len(href)),
        ))

    for match in _URL_RE.finditer(body):
        if any(start <= match.start() < end for start, end in claimed_spans):
            continue
        observations.append(_LinkObservation(
            raw_url=match.group(0),
            title=_title_before_url(body, match.start()),
            position=match.start(),
        ))
    return observations


def _clean_link_title(value: str) -> str:
    title = " ".join(value.split())
    if any(term in title.casefold() for term in _GENERIC_LINK_LABELS):
        return ""
    return title


def _title_before_url(body: str, position: int) -> str:
    prefix = body[:position]
    lines = prefix.splitlines()
    for raw_line in reversed(lines[-8:]):
        line = " ".join(raw_line.strip(" ,|-").split())
        normalized = line.casefold()
        if not line:
            continue
        if normalized.startswith("flere detaljer"):
            continue
        if set(line) <= {"-", "_"}:
            continue
        if _PRICE_RE.search(line) or normalized.startswith(("privat", "forhandler")):
            continue
        if normalized.startswith(("se annonsene", "for å ", "hilsen")):
            continue
        return line[:300]
    return ""


def _context_around(body: str, position: int) -> str:
    start = max(0, position - 300)
    end = min(len(body), position + 500)
    lines = (" ".join(line.split()) for line in body[start:end].splitlines())
    return "\n".join(line for line in lines if line)[:800]


def _advertised_price(context: str) -> float | None:
    match = _PRICE_RE.search(context)
    if not match:
        return None
    digits = re.sub(r"\D", "", match.group(1))
    return float(digits) if digits else None


def _nearest_price_context(body: str, position: int) -> str:
    matches = list(_PRICE_RE.finditer(body))
    if not matches:
        return ""
    nearest = min(
        matches,
        key=lambda match: min(
            abs(match.start() - position),
            abs(match.end() - position),
        ),
    )
    distance = min(
        abs(nearest.start() - position),
        abs(nearest.end() - position),
    )
    if distance > 500:
        return ""
    start = max(0, nearest.start() - 120)
    end = min(len(body), nearest.end() + 120)
    lines = (" ".join(line.split()) for line in body[start:end].splitlines())
    return "\n".join(line for line in lines if line)


def _advertised_location(context: str) -> str | None:
    after = re.search(
        r"(?:kr|nok)\s+([A-ZÆØÅ][A-Za-zÆØÅæøå -]{1,40})(?:\n|Privat|Forhandler|$)",
        context,
    )
    if after:
        return " ".join(after.group(1).split())
    before = re.search(
        r"(?:Privat|Forhandler),\s*([A-ZÆØÅ][A-Za-zÆØÅæøå -]{1,40}?)\s+\d[\d\s.\u00a0]*\s*(?:kr|nok)",
        context,
    )
    return " ".join(before.group(1).split()) if before else None


def _symbolic_price(context: str, price_nok: float | None) -> bool:
    normalized = context.casefold()
    return bool(
        (price_nok is not None and price_nok <= 1)
        or any(term in normalized for term in _SYMBOLIC_PRICE_TERMS)
    )


def parse_finn_saved_search_message(
    message: FinnEmailMessage | Mapping[str, Any],
) -> tuple[FinnEmailLead, ...]:
    """Extract item references from one FINN alert without following links."""
    normalized = (
        message
        if isinstance(message, FinnEmailMessage)
        else message_from_mapping(message)
    )
    saved_search_name = _validate_message(normalized)
    fingerprint = _message_fingerprint(normalized)
    leads: dict[str, FinnEmailLead] = {}

    for observation in _link_observations(normalized.body):
        identity = _canonical_finn_item_url(observation.raw_url)
        if identity is None:
            continue
        listing_id, url = identity
        if listing_id in leads:
            continue
        context = _context_around(normalized.body, observation.position)
        claim_context = _nearest_price_context(
            normalized.body,
            observation.position,
        )
        title = observation.title or f"FINN advert {listing_id}"
        price_nok = _advertised_price(claim_context)
        leads[listing_id] = FinnEmailLead(
            listing_id=listing_id,
            title=title,
            url=url,
            description=" ".join((
                title,
                saved_search_name,
                context,
            ))[:2000],
            advertised_price_nok=price_nok,
            advertised_location=_advertised_location(claim_context),
            symbolic_price_detected=_symbolic_price(
                f"{context}\n{claim_context}",
                price_nok,
            ),
            received_at=normalized.received_at,
            saved_search_name=saved_search_name,
            message_fingerprint=fingerprint,
        )
    if not leads:
        raise ValueError("message contains no stable FINN advert links")
    return tuple(leads.values())


def collect_finn_saved_search_messages(
    messages: Iterable[FinnEmailMessage | Mapping[str, Any]],
    *,
    ingested_at: str | None = None,
) -> FinnEmailCollection:
    """Parse multiple supplied messages and deduplicate stable FINN IDs."""
    values = list(messages)
    accepted = 0
    rejected: list[dict[str, str]] = []
    leads: dict[str, FinnEmailLead] = {}
    for value in values:
        normalized = (
            value
            if isinstance(value, FinnEmailMessage)
            else message_from_mapping(value)
        )
        try:
            parsed = parse_finn_saved_search_message(normalized)
        except ValueError as exc:
            rejected.append({
                "message_fingerprint": _message_fingerprint(normalized),
                "reason": str(exc),
            })
            continue
        accepted += 1
        for lead in parsed:
            leads.setdefault(lead.listing_id, lead)

    return FinnEmailCollection(
        ingested_at=ingested_at or datetime.now(timezone.utc).isoformat(),
        messages_received=len(values),
        messages_accepted=accepted,
        leads=tuple(leads.values()),
        rejected_messages=tuple(rejected),
    )


def _build_batches(
    collection: FinnEmailCollection,
) -> tuple[_FinnEmailProvider, tuple[DiscoveryQuery, ...]]:
    batches: dict[str, tuple[SearchHit, ...]] = {}
    queries: list[DiscoveryQuery] = []
    for offset in range(0, len(collection.leads), _BATCH_SIZE):
        batch_number = (offset // _BATCH_SIZE) + 1
        query_text = f"finn-saved-search-email-batch-{batch_number}"
        batch = collection.leads[offset: offset + _BATCH_SIZE]
        batches[query_text] = tuple(
            SearchHit(
                title=lead.title,
                url=lead.url,
                description=lead.description,
                provider="FINN Saved-Search Email",
            )
            for lead in batch
        )
        queries.append(DiscoveryQuery(
            query_id=f"finn-email-{batch_number:02d}",
            scenario="LARGE_LOT_SALE",
            intent="SALE_INTENT",
            asset_scope="CLOTHING_INVENTORY",
            query=query_text,
            rotation_group="EMAIL_INTAKE",
        ))
    return _FinnEmailProvider(batches), tuple(queries)


def _attach_email_evidence(
    result: dict[str, Any],
    collection: FinnEmailCollection,
) -> None:
    by_url = {
        normalize_public_url(lead.url): lead
        for lead in collection.leads
    }
    for output_name in ("all_discovered_candidates", "discovery_top5"):
        for candidate in result[output_name]:
            matched = [
                by_url[normalize_public_url(url)]
                for url in candidate.get("source_urls") or ()
                if normalize_public_url(url) in by_url
            ]
            candidate["source_capture"] = [
                {
                    "provider": "FINN Saved-Search Email",
                    "listing_id": lead.listing_id,
                    "received_at": lead.received_at,
                    "saved_search_name": lead.saved_search_name,
                    "message_fingerprint": lead.message_fingerprint,
                    "advertised_price_nok": lead.advertised_price_nok,
                    "advertised_location": lead.advertised_location,
                    "symbolic_price_detected": lead.symbolic_price_detected,
                    "commercial_values_verified": False,
                    "page_opened": False,
                }
                for lead in matched
            ]


def run_finn_email_intake(
    collection: FinnEmailCollection,
) -> dict[str, Any]:
    """Pass supplied email leads through the existing Discovery Engine."""
    provider, queries = _build_batches(collection)
    raw_result = run_clothing_inventory_discovery(
        provider,
        queries=queries,
        discovered_at=collection.ingested_at,
        results_per_query=_BATCH_SIZE,
        verifier=None,
        verification_limit=0,
    )
    result = apply_early_opportunity_gate(raw_result)
    _attach_email_evidence(result, collection)
    report = result["search_run_report"]
    report.update({
        "collection_mode": COLLECTION_MODE,
        "collection_schema_version": SCHEMA_VERSION,
        "email_messages_received": collection.messages_received,
        "email_messages_accepted": collection.messages_accepted,
        "email_leads_extracted": len(collection.leads),
        "email_messages_rejected": len(collection.rejected_messages),
        "network_pages_visited": 0,
        "links_followed": 0,
        "commercial_values_verified": False,
        "automatic_contact": False,
        "automatic_purchase_decision": False,
        "financial_ranking_used": False,
    })
    return result


def write_finn_email_intake_artifacts(
    result: Mapping[str, Any],
    collection: FinnEmailCollection,
    output_dir: str | Path,
) -> dict[str, Path]:
    """Write Discovery artifacts plus a sanitized raw-intake artifact."""
    paths = write_discovery_artifacts(result, output_dir)
    collection_path = Path(output_dir) / "finn-email-intake.json"
    collection_path.write_text(
        json.dumps(collection.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    paths["finn_email_intake"] = collection_path
    return paths


def _text_or_none(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None
