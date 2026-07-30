"""Exact source-record accounting for the daily opportunity pipeline.

The helpers in this module persist the identities of fetched source documents and
record the concrete pipeline stage that excluded each document from the published
audit channels. No exclusion is inferred later from a count difference alone.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Iterable

from .live_data import SourceDocument
from .unified_opportunity import UnifiedOpportunity, UnifiedOpportunityExtractor


MISSING_URL_REASON = "missing_url"
UNSUPPORTED_SOURCE_TYPE_REASON = "unsupported_source_type_for_sale_pipeline"
EXTRACTOR_DUPLICATE_REASON = "duplicate_source_document_id_during_extraction"
CROSS_SOURCE_DUPLICATE_REASON = "cross_source_duplicate_merged"
REPORT_LIMIT_REASON = "daily_report_limit"


def serialize_source_document(document: SourceDocument) -> dict[str, object]:
    """Serialize one source document for reuse by later offline pipeline stages."""
    return {
        "document_id": document.document_id,
        "source_name": document.source_name,
        "source_type": document.source_type,
        "title": document.title,
        "text": document.text,
        "url": document.url,
        "published_at": (
            document.published_at.isoformat() if document.published_at else None
        ),
        "country": document.country,
        "metadata": dict(document.metadata),
    }


def deserialize_source_document(payload: dict[str, object]) -> SourceDocument:
    """Restore a source document previously written by ``serialize_source_document``."""
    published_at = payload.get("published_at")
    parsed_published_at = None
    if isinstance(published_at, str) and published_at.strip():
        parsed_published_at = datetime.fromisoformat(
            published_at.strip().replace("Z", "+00:00")
        )
    metadata = payload.get("metadata")
    return SourceDocument(
        document_id=str(payload.get("document_id") or "").strip(),
        source_name=str(payload.get("source_name") or "").strip(),
        source_type=str(payload.get("source_type") or "").strip(),
        title=str(payload.get("title") or "").strip(),
        text=str(payload.get("text") or "").strip(),
        url=str(payload.get("url") or "").strip() or None,
        published_at=parsed_published_at,
        country=str(payload.get("country") or "").strip() or None,
        metadata=dict(metadata) if isinstance(metadata, dict) else {},
    )


def serialize_bankruptcy_discovery_records(
    documents: Iterable[SourceDocument],
) -> list[dict[str, object]]:
    return [
        serialize_source_document(document)
        for document in documents
        if document.source_type == "bankruptcy_discovery_lead"
    ]


def _merged_document_ids(opportunity: UnifiedOpportunity) -> tuple[str, ...]:
    value = opportunity.raw_metadata.get("merged_source_document_ids")
    if isinstance(value, (list, tuple)):
        values = tuple(str(item).strip() for item in value if str(item).strip())
        if values:
            return values
    return (opportunity.source_document_id,)


def build_source_record_accounting(
    source_documents: Iterable[SourceDocument],
    extracted: Iterable[UnifiedOpportunity],
    merged: Iterable[UnifiedOpportunity],
    published_opportunity_ids: Iterable[str],
) -> dict[str, object]:
    """Build exact fetched/published/excluded accounting by source.

    Published records retain both the raw source-document id and the normalized
    opportunity id used by downstream audit channels. This mapping lets the final
    verifier distinguish a daily Auksjonen record from an unrelated Auksjonen hit
    discovered through another channel.
    """
    documents = tuple(source_documents)
    extracted_items = tuple(extracted)
    merged_items = tuple(merged)
    published_ids = {str(item).strip() for item in published_opportunity_ids}

    extracted_keys = {
        (item.source_name, item.source_document_id) for item in extracted_items
    }
    source_by_document_id = {
        item.source_document_id: item.source_name for item in extracted_items
    }

    secondary_merged_keys: set[tuple[str, str]] = set()
    for opportunity in merged_items:
        primary = (opportunity.source_name, opportunity.source_document_id)
        for document_id in _merged_document_ids(opportunity):
            source_name = source_by_document_id.get(document_id)
            if source_name is None:
                continue
            key = (source_name, document_id)
            if key != primary:
                secondary_merged_keys.add(key)

    published_items = [
        item for item in merged_items if item.opportunity_id in published_ids
    ]
    published_primary_keys = {
        (item.source_name, item.source_document_id) for item in published_items
    }

    exclusions_by_source: dict[str, list[dict[str, str]]] = {}
    exclusion_keys: set[tuple[str, str]] = set()

    def add_exclusion(source: str, record_id: str, reason: str, stage: str) -> None:
        key = (source, record_id)
        if key in exclusion_keys:
            return
        exclusion_keys.add(key)
        exclusions_by_source.setdefault(source, []).append(
            {"record_id": record_id, "reason": reason, "stage": stage}
        )

    for document in documents:
        key = (document.source_name, document.document_id)
        if not document.url:
            add_exclusion(
                document.source_name,
                document.document_id,
                MISSING_URL_REASON,
                "extraction",
            )
        elif document.source_type not in UnifiedOpportunityExtractor.supported_source_types:
            add_exclusion(
                document.source_name,
                document.document_id,
                UNSUPPORTED_SOURCE_TYPE_REASON,
                "extraction",
            )
        elif key not in extracted_keys:
            add_exclusion(
                document.source_name,
                document.document_id,
                EXTRACTOR_DUPLICATE_REASON,
                "extraction",
            )

    for source_name, document_id in sorted(secondary_merged_keys):
        add_exclusion(
            source_name,
            document_id,
            CROSS_SOURCE_DUPLICATE_REASON,
            "cross_source_merge",
        )

    for opportunity in merged_items:
        primary = (opportunity.source_name, opportunity.source_document_id)
        if primary not in published_primary_keys:
            add_exclusion(
                opportunity.source_name,
                opportunity.source_document_id,
                REPORT_LIMIT_REASON,
                "daily_report",
            )

    fetched_by_source: dict[str, list[str]] = {}
    for document in documents:
        fetched_by_source.setdefault(document.source_name, []).append(
            document.document_id
        )

    published_records_by_source: dict[str, list[dict[str, str]]] = {}
    for item in sorted(
        published_items,
        key=lambda value: (
            value.source_name,
            value.source_document_id,
            value.opportunity_id,
        ),
    ):
        published_records_by_source.setdefault(item.source_name, []).append(
            {
                "record_id": item.source_document_id,
                "opportunity_id": item.opportunity_id,
            }
        )

    sources: dict[str, dict[str, object]] = {}
    valid = True
    for source_name in sorted(fetched_by_source):
        fetched_ids = fetched_by_source[source_name]
        published_records = published_records_by_source.get(source_name, [])
        published_record_ids = [item["record_id"] for item in published_records]
        published_opportunity_ids_for_source = [
            item["opportunity_id"] for item in published_records
        ]
        exclusions = exclusions_by_source.get(source_name, [])
        reason_counts = Counter(item["reason"] for item in exclusions)
        accounted_total = len(published_record_ids) + len(exclusions)
        source_valid = len(fetched_ids) == accounted_total
        valid = valid and source_valid
        sources[source_name] = {
            "fetched_count": len(fetched_ids),
            "fetched_record_ids": fetched_ids,
            "published_audit_record_count": len(published_record_ids),
            "published_audit_record_ids": published_record_ids,
            "published_audit_opportunity_ids": published_opportunity_ids_for_source,
            "published_audit_records": published_records,
            "excluded_record_count": len(exclusions),
            "excluded_records_by_reason": dict(sorted(reason_counts.items())),
            "excluded_records": exclusions,
            "accounted_total": accounted_total,
            "valid": source_valid,
        }

    return {
        "schema_version": 2,
        "valid": valid,
        "sources": sources,
    }
