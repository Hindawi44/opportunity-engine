"""Merge normalized opportunities from multiple sources without losing evidence."""

from __future__ import annotations

from dataclasses import dataclass, replace
import re
from typing import Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .unified_opportunity import UnifiedOpportunity


@dataclass(frozen=True)
class MultiSourceMergeResult:
    opportunities: tuple[UnifiedOpportunity, ...]
    input_count: int
    output_count: int
    duplicate_count: int
    groups_merged: int


class UnifiedMultiSourceEngine:
    """Deduplicate cross-source records and retain the most complete version."""

    TRACKING_QUERY_KEYS = frozenset({
        "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
        "fbclid", "gclid", "ref", "source",
    })

    def merge(self, opportunities: Iterable[UnifiedOpportunity]) -> MultiSourceMergeResult:
        items = tuple(opportunities)
        groups: dict[str, list[UnifiedOpportunity]] = {}
        for item in items:
            groups.setdefault(self._group_key(item), []).append(item)

        merged: list[UnifiedOpportunity] = []
        groups_merged = 0
        for group in groups.values():
            if len(group) == 1:
                merged.append(group[0])
                continue
            groups_merged += 1
            merged.append(self._merge_group(group))

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

    def _merge_group(self, group: list[UnifiedOpportunity]) -> UnifiedOpportunity:
        ranked = sorted(group, key=self._completeness_score, reverse=True)
        primary = ranked[0]

        source_names = tuple(dict.fromkeys(item.source_name for item in ranked))
        source_document_ids = tuple(dict.fromkeys(item.source_document_id for item in ranked))
        urls = tuple(dict.fromkeys(item.url for item in ranked if item.url))
        image_urls = tuple(dict.fromkeys(url for item in ranked for url in item.image_urls))

        raw_metadata = dict(primary.raw_metadata)
        raw_metadata.update({
            "merged_source_names": source_names,
            "merged_source_document_ids": source_document_ids,
            "merged_urls": urls,
            "merged_record_count": len(group),
        })

        return replace(
            primary,
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
        fields = ("current_price_nok", "city", "ends_at", "fee_text")
        missing = [
            field for field in fields
            if cls._first_not_none(items, field) is None
        ]
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
