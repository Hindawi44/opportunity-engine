"""Complete missing canonical artifacts for bounded checkpoint sources.

The adapter is intentionally source-agnostic at the persistence boundary. Any
checkpoint source that already emits ``all-discovered-candidates.json`` can be
moved through the existing canonical opportunity report and SQLite repository
without changing discovery, scoring, or the human-review boundary. FINN saved-
search email additionally emits a durable market-signal report because the email
is an observation channel, not verified commercial evidence.
"""
from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from opportunity_engine.discovery.unified_opportunity_report import (
    write_unified_opportunity_report,
)
from opportunity_engine.market_intelligence import (
    MarketSignalRecord,
    MarketSignalStatus,
    MarketSignalType,
)
from opportunity_engine.persistence.live_unified_persistence import (
    persist_unified_report_with_artifacts,
)


CONTINUITY_SCHEMA_VERSION = "source-artifact-continuity-1.0"
FINN_SIGNAL_REPORT_SCHEMA_VERSION = "finn-email-market-signal-report-1.0"
_MARKET_CURRENCIES = {"NO": "NOK", "SE": "SEK", "DE": "EUR"}


class SourceArtifactContinuityError(ValueError):
    """Raised when completed source artifacts contradict their contracts."""


def _compact(value: object) -> str:
    return " ".join(str(value or "").split())


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SourceArtifactContinuityError(f"Missing source artifact: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SourceArtifactContinuityError(f"Invalid JSON source artifact: {path}") from exc


def _write_json(path: Path, payload: Mapping[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _timestamp(value: object, *, fallback: datetime | None = None) -> datetime:
    text = _compact(value)
    if text:
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            try:
                parsed = parsedate_to_datetime(text)
            except (TypeError, ValueError) as exc:
                raise SourceArtifactContinuityError(
                    f"Invalid source timestamp: {text}"
                ) from exc
    else:
        parsed = fallback or datetime.now(timezone.utc)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _market_code(output_dir: Path, report: Mapping[str, Any]) -> str:
    explicit = _compact(report.get("market_code")).upper()
    if explicit in _MARKET_CURRENCIES:
        return explicit
    market = _compact(report.get("market")).upper()
    if market[:2] in _MARKET_CURRENCIES:
        return market[:2]
    prefix = output_dir.name.split("-", 1)[0].upper()
    if prefix in _MARKET_CURRENCIES:
        return prefix
    raise SourceArtifactContinuityError(
        f"Cannot infer market code for source artifact directory: {output_dir}"
    )


def _candidate_urls(candidate: Mapping[str, Any]) -> list[str]:
    raw = candidate.get("source_urls")
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        return []
    return [_compact(value) for value in raw if _compact(value)]


def _first_capture(candidate: Mapping[str, Any]) -> Mapping[str, Any]:
    raw = candidate.get("source_capture")
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        return {}
    return next((item for item in raw if isinstance(item, Mapping)), {})


def _finn_signal(
    candidate: Mapping[str, Any],
    *,
    generated_at: datetime,
    market_code: str,
) -> MarketSignalRecord:
    urls = _candidate_urls(candidate)
    if not urls:
        raise SourceArtifactContinuityError("FINN candidate has no source URL")
    capture = _first_capture(candidate)
    listing_id = _compact(capture.get("listing_id"))
    if not listing_id:
        listing_id = urls[0].rstrip("/").rsplit("/", 1)[-1]
    if not listing_id.isdigit():
        raise SourceArtifactContinuityError("FINN candidate has no stable numeric listing ID")

    title = _compact(candidate.get("title")) or f"FINN advert {listing_id}"
    received_at = _timestamp(capture.get("received_at"), fallback=generated_at)
    price = capture.get("advertised_price_nok")
    if isinstance(price, bool) or not isinstance(price, (int, float)):
        price = None
    location = _compact(capture.get("advertised_location")) or None

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
        first_observed_at=received_at,
        latest_observed_at=generated_at,
        event_date=None,
        evidence=[
            {
                "evidence_type": "SAVED_SEARCH_EMAIL_REFERENCE",
                "value": f"FINN saved-search email referenced listing {listing_id}",
                "source_url": urls[0],
                "captured_at": None,
                "verified": False,
                "metadata": {"channel": "FINN_SAVED_SEARCH_EMAIL"},
            }
        ],
        related_opportunity_id=None,
        status=MarketSignalStatus.WATCH,
        metadata={
            "signal_only": True,
            "collection_mode": "FINN_SAVED_SEARCH_EMAIL",
            "listing_id": listing_id,
            "listing_status": _compact(candidate.get("listing_status")).upper() or "UNKNOWN",
            "advertised_price_nok": float(price) if price is not None else None,
            "advertised_location": location,
            "symbolic_price_detected": capture.get("symbolic_price_detected") is True,
            "commercial_values_verified": False,
            "page_opened": False,
        },
    )


def _write_finn_signal_report(
    output_dir: Path,
    candidates: Sequence[Mapping[str, Any]],
    *,
    generated_at: datetime,
    market_code: str,
) -> tuple[Path | None, int]:
    intake_path = output_dir / "finn-email-intake.json"
    if not intake_path.exists():
        return None, 0
    intake = _load_json(intake_path)
    if not isinstance(intake, Mapping):
        raise SourceArtifactContinuityError(