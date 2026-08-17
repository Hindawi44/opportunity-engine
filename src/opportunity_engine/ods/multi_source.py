"""Merge normalized source evidence into canonical facts without hiding conflicts."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import re
from typing import Any, Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .unified_opportunity import UnifiedOpportunity


class MultiSourceFactConflictError(ValueError):
    """Raised when duplicate evidence disagrees on a material canonical fact."""


@dataclass(frozen=True)
class MultiSourceMergeResult:
    opportunities: tuple[UnifiedOpportunity, ...]
    input_count: int
    output_count: int
    duplicate_count: int
    groups_merged: int


class UnifiedMultiSourceEngine:
    """Consolidate evidence while keeping canonical facts conflict-free and auditable."""

    TRACKING_QUERY_KEYS = frozenset({
        "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
        "fbclid", "gclid", "ref", "source",
    })
    MATERIAL_FACT_FIELDS = (
        "current_price_nok",
        "city",
        "ends_at",
        "mva_status",
    )
    PROVENANCE_FIELDS = MATERIAL_FACT_FIELDS + ("fee_text",)

    def merge(self, opportunities: Iterable[UnifiedOpportunity]) -> MultiSourceMergeResult:
        items = tuple(opportunities)
        groups: dict[str, list[UnifiedOpportunity]] = {}
        for item in items:
            groups.setdefault(self._group_key(item), []).append(item)

        merged: list[UnifiedOpportunity] = []
        groups_merged = 0
        for group_key, group in groups.items():
            self._validate_fact_conflicts(group)
            if len(group) == 1:
                merged.append(self._annotate_single(group[0], group_key))
                continue
            groups_merged += 1
            merged.append(self._merge_group(group, group_key))

        merged.sort(key=lambda item: (item.source_name.casefold(), item.title.casefold(), item.opportunity_id))
        return MultiSourceMergeResult(
            opportunities=tuple(merged),
            input_count=len(items),
            output_count=len(merged),
            duplicate_count=len(items) - len(merged),
            groups_merged=groups_merged,
        )

    def _group_key(self, item: UnifiedOpportunity) -> str:
        canonical_url = self._canonical_url(item.url)
        if canonical_url:
            return f"url:{canonical_url}"

        title = self._normalize_text(item.title)
        city = self._normalize_text(item.city or "")
        price = "" if item.current_price_nok is None else str(round(item.current_price_nok, 0))
        if title and city and price:
            return f"fingerprint:{title}|{city}|{price}"
        return f"id:{item.opportunity_id}"

    def _annotate_single(
        self,
        item: UnifiedOpportunity,
        group_key: str,
    ) -> UnifiedOpportunity:
        metadata = dict(item.raw_metadata)
        metadata.update(
            {
                "canonical_fact_identity": group_key,
                "source_opportunity_ids": (item.opportunity_id,),
                "fact_provenance": self._fact_provenance([item]),
            }
        )
        return replace(item, raw_metadata=metadata)

    def _merge_group(
        self,
        group: list[UnifiedOpportunity],
        group_key: str,
    ) -> UnifiedOpportunity:
        ranked = sorted(group, key=self._completeness_score, reverse=True)
        primary = ranked[0]

        source_names = tuple(dict.fromkeys(item.source_name for item in ranked))
        source_document_ids = tuple(dict.fromkeys(item.source_document_id for item in ranked))
        source_opportunity_ids = tuple(sorted({item.opportunity_id for item in group}))
        canonical_alias = source_opportunity_ids[0]
        urls = tuple(dict.fromkeys(item.url for item in ranked if item.url))
        image_urls = tuple(dict.fromkeys(url for item in ranked for url in item.image_urls))

        raw_metadata = dict(primary.raw_metadata)
        raw_metadata.update({
            "merged_source_names": source_names,
            "merged_source_document_ids": source_document_ids,
            "merged_urls": urls,
            "merged_record_count": len(group),
            "canonical_fact_identity": group_key,
            "source_opportunity_ids": source_opportunity_ids,
            "fact_provenance": self._fact_provenance(group),
        })

        return replace(
            primary,
            opportunity_id=canonical_alias,
            description=self._first_nonempty(ranked, "description") or primary.description,
            current_price_nok=self._first_not_none(ranked, "current_price_nok"),
            city=self._first_nonempty(ranked, "city"),
            ends_at=self._first_not_none(ranked, "ends_at"),
            fee_text=self._first_nonempty(ranked, "fee_text"),
            mva_status=self._best_mva_status(ranked),
            image_urls=image_urls,
            missing_fields=self._recalculate_missing(ranked),
            raw_metadata=raw_metadata,
        )

    def _validate_fact_conflicts(self, group: list[UnifiedOpportunity]) -> None:
        for field in self.MATERIAL_FACT_FIELDS:
            observed: dict[object, list[str]] = {}
            for item in group:
                value = getattr(item, field)
                if not self._is_known_fact(field, value):
                    continue
                key = self._fact_equivalence_key(field, value)
                observed.setdefault(key, []).append(self._source_ref(item))
            if len(observed) > 1:
                evidence = "; ".join(
                    f"{key!r} from {', '.join(refs)}"
                    for key, refs in observed.items()
                )
                raise MultiSourceFactConflictError(
                    f"conflicting canonical fact {field}: {evidence}"
                )

    def _fact_provenance(
        self,
        items: list[UnifiedOpportunity],
    ) -> dict[str, tuple[str, ...]]:
        ordered = sorted(
            items,
            key=lambda item: (
                item.source_name.casefold(),
                item.source_document_id,
                item.opportunity_id,
            ),
        )
        provenance: dict[str, tuple[str, ...]] = {}
        for field in self.PROVENANCE_FIELDS:
            refs = tuple(
                self._source_ref(item)
                for item in ordered
                if self._is_known_fact(field, getattr(item, field))
            )
            if refs:
                provenance[field] = tuple(dict.fromkeys(refs))
        return provenance

    @staticmethod
    def _source_ref(item: UnifiedOpportunity) -> str:
        return f"{item.source_name}:{item.source_document_id}"

    @classmethod
    def _is_known_fact(cls, field: str, value: Any) -> bool:
        if value is None or value == "" or value == ():
            return False
        if field == "mva_status" and str(value).casefold() == "unknown":
            return False
        return True

    @classmethod
    def _fact_equivalence_key(cls, field: str, value: Any) -> object:
        if field == "current_price_nok":
            return round(float(value), 2)
        if field == "city":
            return re.sub(r"\s+", " ", str(value)).strip().casefold()
        if field == "mva_status":
            return str(value).strip().casefold()
        if field == "ends_at" and isinstance(value, datetime):
            if value.tzinfo is not None:
                return value.astimezone(timezone.utc).isoformat()
            return value.isoformat()
        return value

    @staticmethod
    def _completeness_score(item: UnifiedOpportunity) -> tuple[int, int, int]:
        populated = sum(
            value not in (None, "", (), "unknown")
            for value in (
                item.current_price_nok,
                item.city,
                item.ends_at,
                item.fee_text,
                item.mva_status,
                item.image_urls,
                item.description,
            )
        )
        return populated, -len(item.missing_fields), len(item.description)

    @staticmethod
    def _first_nonempty(items: list[UnifiedOpportunity], field: str):
        for item in items:
            value = getattr(item, field)
            if value not in (None, "", ()):
                return value
        return None

    @staticmethod
    def _first_not_none(items: list[UnifiedOpportunity], field: str):
        for item in items:
            value = getattr(item, field)
            if value is not None:
                return value
        return None

    @staticmethod
    def _best_mva_status(items: list[UnifiedOpportunity]) -> str:
        for item in items:
            if item.mva_status != "unknown":
                return item.mva_status
        return "unknown"

    @classmethod
    def _recalculate_missing(cls, items: list[UnifiedOpportunity]) -> tuple[str, ...]:
        missing: list[str] = []
        if cls._first_not_none(items, "current_price_nok") is None:
            missing.append("current_price_nok")
        if cls._first_nonempty(items, "city") is None:
            missing.append("city")
        if cls._first_not_none(items, "ends_at") is None:
            missing.append("ends_at")
        if cls._first_nonempty(items, "fee_text") is None:
            missing.append("fee_text")
        if cls._best_mva_status(items) == "unknown":
            missing.append("mva_status")
        return tuple(missing)

    @classmethod
    def _canonical_url(cls, value: str) -> str:
        if not value:
            return ""
        parts = urlsplit(value.strip())
        if parts.scheme not in {"http", "https"} or not parts.netloc:
            return ""
        query = [
            (key, val) for key, val in parse_qsl(parts.query, keep_blank_values=True)
            if key.casefold() not in cls.TRACKING_QUERY_KEYS
        ]
        path = re.sub(r"/+", "/", parts.path).rstrip("/") or "/"
        return urlunsplit(("https", parts.netloc.casefold(), path, urlencode(sorted(query)), ""))

    @staticmethod
    def _normalize_text(value: str) -> str:
        return re.sub(r"[^a-z0-9æøå]+", " ", value.casefold()).strip()
