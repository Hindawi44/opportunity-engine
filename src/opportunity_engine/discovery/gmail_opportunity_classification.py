"""Deterministic, read-only classification of project-scoped Gmail messages."""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping
from urllib.parse import urlsplit

from opportunity_engine.discovery.finn_email_intake import FinnEmailMessage


SCHEMA_VERSION = "gmail-opportunity-classification-1.0"
CATEGORIES = (
    "FINN_OPPORTUNITY",
    "AUCTION_LIQUIDATION",
    "SUPPLIER_STOCK",
    "PRICE_STATUS_CHANGE",
    "SHIPPING_LOGISTICS",
    "IRRELEVANT",
    "NEEDS_REVIEW",
)
URL_RE = re.compile(r"https?://[^\s<>\]\)]+", re.IGNORECASE)
PRICE_RE = re.compile(
    r"(?P<amount>\d[\d\s.,]{0,14})\s*(?P<currency>NOK|SEK|EUR|kr|€)",
    re.IGNORECASE,
)
QUANTITY_RE = re.compile(
    r"\b(?P<quantity>\d[\d\s.]*)\s*(?:stk|st|pcs|pieces|plagg|par|varer|units?)\b",
    re.IGNORECASE,
)
COUNTRY_TERMS = {
    "NO": ("norge", "norway", "norsk", "finn.no", "auksjonen.no"),
    "SE": ("sverige", "sweden", "svensk", ".se/"),
    "DE": ("deutschland", "germany", "deutsch", ".de/"),
    "FR": ("france", "français", "francaise", ".fr/"),
    "IT": ("italia", "italy", "italiano", ".it/"),
    "NL": ("nederland", "netherlands", "dutch", ".nl/"),
}


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _sender_domain(sender: object) -> str:
    match = re.search(r"@([a-z0-9.-]+)", str(sender or ""), re.IGNORECASE)
    return match.group(1).casefold() if match else "unknown"


def _urls(text: str) -> list[str]:
    result: list[str] = []
    for raw in URL_RE.findall(text):
        value = raw.rstrip(".,;:'\"")
        if value and value not in result:
            result.append(value)
    return result[:10]


def _country(text: str) -> str | None:
    folded = text.casefold()
    matches = [code for code, terms in COUNTRY_TERMS.items() if any(term in folded for term in terms)]
    return matches[0] if len(matches) == 1 else None


def _price(text: str) -> dict[str, Any] | None:
    match = PRICE_RE.search(text)
    if not match:
        return None
    digits = re.sub(r"\D", "", match.group("amount"))
    if not digits:
        return None
    currency = match.group("currency").upper()
    if currency == "KR":
        currency = "UNRESOLVED_KR"
    elif currency == "€":
        currency = "EUR"
    return {"amount": int(digits), "currency": currency, "verified": False}


def _quantity(text: str) -> int | None:
    match = QUANTITY_RE.search(text)
    if not match:
        return None
    digits = re.sub(r"\D", "", match.group("quantity"))
    return int(digits) if digits else None


def classify_gmail_message(message: FinnEmailMessage) -> dict[str, Any]:
    """Classify one already-fetched message without mutating Gmail."""
    sender = _compact(message.sender)
    subject = _compact(message.subject)
    body = _compact(message.body)
    text = f"{sender} {subject} {body}".casefold()
    urls = _urls(message.body)
    reasons: list[str] = []

    if any(term in text for term in ("pris redusert", "price reduced", "solgt", "sold", "avsluttet", "ended", "utløpt", "status change")):
        category = "PRICE_STATUS_CHANGE"
        reasons.append("PRICE_OR_STATUS_LANGUAGE")
    elif any(term in text for term in ("mybring", "bring.no", "frakt", "shipping", "transport", "levering", "delivery", "pickup")):
        category = "SHIPPING_LOGISTICS"
        reasons.append("SHIPPING_LANGUAGE")
    elif "agent@finn.no" in text or any("finn.no" in urlsplit(url).netloc.casefold() for url in urls):
        category = "FINN_OPPORTUNITY"
        reasons.append("FINN_SENDER_OR_LINK")
    elif any(term in text for term in ("auksjon", "auction", "konkurs", "insolven", "liquidation", "avvikling", "tvangssalg")):
        category = "AUCTION_LIQUIDATION"
        reasons.append("AUCTION_OR_LIQUIDATION_LANGUAGE")
    elif any(term in text for term in ("vareparti", "restlager", "overskuddslager", "surplus", "wholesale", "grossist", "stock lot", "lagerparti")):
        category = "SUPPLIER_STOCK"
        reasons.append("SUPPLIER_OR_STOCK_LANGUAGE")
    elif urls or any(term in text for term in ("klær", "clothing", "bekleidung", "vêtements", "abbigliamento", "kleding")):
        category = "NEEDS_REVIEW"
        reasons.append("POSSIBLE_PROJECT_MESSAGE_UNCLEAR")
    else:
        category = "IRRELEVANT"
        reasons.append("NO_PROJECT_SIGNAL")

    fingerprint_basis = "|".join((sender.casefold(), subject.casefold(), _compact(message.received_at)))
    return {
        "message_fingerprint": sha256(fingerprint_basis.encode("utf-8")).hexdigest(),
        "received_at": _compact(message.received_at) or None,
        "sender_domain": _sender_domain(sender),
        "subject": subject[:300],
        "category": category,
        "classification_reasons": reasons,
        "country": _country(text),
        "advertised_price": _price(text),
        "advertised_quantity": _quantity(text),
        "urls": urls,
        "raw_body_stored": False,
        "message_id_stored": False,
        "requires_human_review": category == "NEEDS_REVIEW",
    }


def classify_gmail_messages(messages: Iterable[FinnEmailMessage]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for message in messages:
        row = classify_gmail_message(message)
        fingerprint = row["message_fingerprint"]
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        rows.append(row)
    counts = Counter(row["category"] for row in rows)
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS",
        "message_count": len(rows),
        "category_counts": {category: counts.get(category, 0) for category in CATEGORIES},
        "messages": rows,
        "gmail_mutations_made": 0,
        "automatic_reply": False,
        "automatic_delete": False,
        "automatic_move": False,
    }


def write_gmail_classification_artifacts(
    report: Mapping[str, Any], output_dir: str | Path
) -> dict[str, Path]:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / "gmail-message-classification.json"
    text_path = root / "gmail-message-classification.txt"
    json_path.write_text(
        json.dumps(dict(report), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    counts = report.get("category_counts") or {}
    lines = ["GMAIL OPPORTUNITY CLASSIFICATION", f"messages: {report.get('message_count', 0)}"]
    lines.extend(f"{category}: {counts.get(category, 0)}" for category in CATEGORIES)
    lines.extend(["gmail_mutations_made: 0", "automatic_reply: false"])
    text_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"gmail_classification": json_path, "gmail_classification_summary": text_path}
