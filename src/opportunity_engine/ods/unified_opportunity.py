"""Normalize auction source documents into analysis-ready opportunities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from typing import Any, Iterable

from .live_data import SourceDocument


@dataclass(frozen=True)
class UnifiedOpportunity:
    """Source-neutral opportunity record used by later pricing and cost stages."""

    opportunity_id: str
    source_name: str
    source_document_id: str
    title: str
    url: str
    description: str
    current_price_nok: float | None
    city: str | None
    ends_at: datetime | None
    fee_text: str | None
    mva_status: str
    image_urls: tuple[str, ...]
    missing_fields: tuple[str, ...]
    raw_metadata: dict[str, Any]


class UnifiedOpportunityExtractor:
    """Convert supported auction documents without inventing missing facts."""

    name = "unified_opportunity_extractor"
    supported_source_types = frozenset({"public_auction_listing", "authorized_classified_ad"})

    def extract(self, documents: Iterable[SourceDocument]) -> tuple[UnifiedOpportunity, ...]:
        opportunities: list[UnifiedOpportunity] = []
        seen: set[str] = set()
        for document in documents:
            if document.source_type not in self.supported_source_types or not document.url:
                continue
            opportunity = self._extract_one(document)
            if opportunity.opportunity_id in seen:
                continue
            seen.add(opportunity.opportunity_id)
            opportunities.append(opportunity)
        return tuple(opportunities)

    def _extract_one(self, document: SourceDocument) -> UnifiedOpportunity:
        metadata = dict(document.metadata)
        price = _as_non_negative_float(metadata.get("current_price_nok"))
        city = _clean_optional(metadata.get("city"))
        ends_at = _as_datetime(metadata.get("ends_at"))
        description = _description(document)
        fee_text = _fee_text(metadata, document.text)
        mva_status = _mva_status(metadata, document.text)
        image_urls = _image_urls(metadata)

        missing: list[str] = []
        for field_name, value in (
            ("current_price_nok", price),
            ("city", city),
            ("ends_at", ends_at),
            ("fee_text", fee_text),
        ):
            if value is None:
                missing.append(field_name)
        if mva_status == "unknown":
            missing.append("mva_status")

        return UnifiedOpportunity(
            opportunity_id=f"unified-{document.document_id}",
            source_name=document.source_name,
            source_document_id=document.document_id,
            title=document.title.strip(),
            url=document.url,
            description=description,
            current_price_nok=price,
            city=city,
            ends_at=ends_at,
            fee_text=fee_text,
            mva_status=mva_status,
            image_urls=image_urls,
            missing_fields=tuple(missing),
            raw_metadata=metadata,
        )


def _description(document: SourceDocument) -> str:
    explicit = _clean_optional(document.metadata.get("description"))
    if explicit:
        return explicit
    parts = [part.strip() for part in document.text.split("|")]
    useful = [part for part in parts if part and not _is_generated_summary(part, document.title)]
    return " | ".join(useful) or document.title.strip()


def _is_generated_summary(part: str, title: str) -> bool:
    lowered = part.casefold()
    return part == title or lowered.startswith(("current price:", "location:", "ends at:"))


def _fee_text(metadata: dict[str, Any], text: str) -> str | None:
    explicit = _clean_optional(metadata.get("fee_text") or metadata.get("fees"))
    if explicit:
        return explicit
    match = re.search(
        r"(?:sal[æa]r|gebyr|provisjon|auction fee|omkostninger)\s*[:|-]?\s*([^|.;]{1,80})",
        text,
        re.IGNORECASE,
    )
    return _clean_optional(match.group(0)) if match else None


def _mva_status(metadata: dict[str, Any], text: str) -> str:
    explicit = _clean_optional(metadata.get("mva_status"))
    if explicit in {"included", "excluded", "not_applicable", "unknown"}:
        return explicit
    normalized = text.casefold()
    if re.search(r"(?:inkl\.?|inkludert)\s*(?:mva|m\.v\.a)", normalized):
        return "included"
    if re.search(r"(?:eks\.?|ekskl\.?|pluss)\s*(?:mva|m\.v\.a)", normalized):
        return "excluded"
    if "mva-fri" in normalized or "uten mva" in normalized:
        return "not_applicable"
    return "unknown"


def _image_urls(metadata: dict[str, Any]) -> tuple[str, ...]:
    value = metadata.get("image_urls") or metadata.get("images") or ()
    if isinstance(value, str):
        value = (value,)
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(url.strip() for url in value if isinstance(url, str) and url.strip().startswith("https://"))


def _as_non_negative_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _as_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None


def _clean_optional(value: Any) -> str | None:
    cleaned = re.sub(r"\s+", " ", str(value or "")).strip()
    return cleaned or None
