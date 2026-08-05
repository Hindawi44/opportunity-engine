"""Create durable, unverified market signals from FINN saved-search email."""
from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from opportunity_engine.market_intelligence import (
    MarketSignalRecord,
    MarketSignalStatus,
    MarketSignalType,
)

SCHEMA_VERSION = "finn-email-market-signal-report-1.0"


def _text(value: object) -> str:
    return " ".join(str(value or "").split())


def _time(value: object, fallback: datetime) -> datetime:
    text = _text(value)
    if not text:
        result = fallback
    else:
        try:
            result = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            result = parsedate_to_datetime(text)
    if result.tzinfo is None or result.utcoffset() is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


def _urls(candidate: Mapping[str, Any]) -> list[str]:
    values = candidate.get("source_urls")
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        return []
    return [_text(value) for value in values if _text(value)]


def _capture(candidate: Mapping[str, Any]) -> Mapping[str, Any]:
    values = candidate.get("source_capture")
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        return {}
    return next((value for value in values if isinstance(value, Mapping)), {})


def _signal(
    candidate: Mapping[str, Any], generated_at: datetime, market_code: str
) -> MarketSignalRecord:
    urls = _urls(candidate)
    if not urls:
        raise ValueError("FINN candidate has no source URL")
    capture = _capture(candidate)
    listing_id = _text(capture.get("listing_id")) or urls[0].rstrip("/").rsplit("/", 1)[-1]
    if not listing_id.isdigit():
        raise ValueError("FINN candidate has no stable numeric listing ID")
    title = _text(candidate.get("title")) or f"FINN advert {listing_id}"
    price = capture.get("advertised_price_nok")
    if isinstance(price, bool) or not isinstance(price, (int, float)):
        price = None
    location = _text(capture.get("advertised_location")) or None
    return MarketSignalRecord(
        signal_id=f"finn-listing:{listing_id}",
        signal_type=MarketSignalType.ITEM_LISTING,
        value=title[:500],
        source="FINN saved-search email",
        observed_at=generated_at,
        confidence=None,
        source_country=market_code,
        source_url=urls[0],
        title=title,
        company_name=None,
        seller_name=None,
        location=location,
        first_observed_at=_time(capture.get("received_at"), generated_at),
        latest_observed_at=generated_at,
        event_date=None,
        evidence=[{
            "evidence_type": "SAVED_SEARCH_EMAIL_REFERENCE",
            "value": f"FINN saved-search email referenced listing {listing_id}",
            "source_url": urls[0],
            "captured_at": None,
            "verified": False,
            "metadata": {"channel": "FINN_SAVED_SEARCH_EMAIL"},
        }],
        related_opportunity_id=None,
        status=MarketSignalStatus.WATCH,
        metadata={
            "signal_only": True,
            "collection_mode": "FINN_SAVED_SEARCH_EMAIL",
            "listing_id": listing_id,
            "listing_status": _text(candidate.get("listing_status")).upper() or "UNKNOWN",
            "advertised_price_nok": float(price) if price is not None else None,
            "advertised_location": location,
            "symbolic_price_detected": capture.get("symbolic_price_detected") is True,
            "commercial_values_verified": False,
            "page_opened": False,
        },
    )


def write_finn_market_signal_report(
    directory: Path,
    candidates: Sequence[Mapping[str, Any]],
    *,
    generated_at: datetime,
    market_code: str,
) -> tuple[Path | None, int]:
    intake_path = directory / "finn-email-intake.json"
    if not intake_path.exists():
        return None, 0
    intake = json.loads(intake_path.read_text(encoding="utf-8"))
    if not isinstance(intake, Mapping) or _text(intake.get("collection_mode")) != "FINN_SAVED_SEARCH_EMAIL":
        raise ValueError("Invalid FINN email intake contract")
    signals: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        if candidate.get("top5_eligible") is True:
            item = _signal(candidate, generated_at, market_code)
            signals[item.signal_id] = item.model_dump(mode="json")
    path = directory / "market-signal-report.json"
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at.isoformat(),
        "market_code": market_code,
        "source_name": "FINN saved-search email",
        "signal_count": len(signals),
        "signals": [signals[key] for key in sorted(signals)],
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path, len(signals)
