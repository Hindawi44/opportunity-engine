"""Universal connector scanner for repeatable ODS evidence collection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from typing import Iterable

from .live_data import DataConnector, OpportunityExtractor, SourceDocument
from .models import ODSRequest, OpportunityCandidate


@dataclass(frozen=True)
class ConnectorScanStatus:
    connector_name: str
    status: str
    document_count: int
    error: str | None = None

    def __post_init__(self) -> None:
        if self.status not in {"completed", "failed"}:
            raise ValueError("status must be completed or failed")
        if self.document_count < 0:
            raise ValueError("document_count must not be negative")


@dataclass(frozen=True)
class ScanSnapshot:
    scan_id: str
    started_at: datetime
    completed_at: datetime
    documents: tuple[SourceDocument, ...]
    opportunities: tuple[OpportunityCandidate, ...]
    connector_statuses: tuple[ConnectorScanStatus, ...]
    duplicate_count: int

    @property
    def successful_connectors(self) -> int:
        return sum(item.status == "completed" for item in self.connector_statuses)

    @property
    def failed_connectors(self) -> int:
        return sum(item.status == "failed" for item in self.connector_statuses)


class ConnectorRegistry:
    """Keeps connector registration explicit and prevents duplicate names."""

    def __init__(self, connectors: Iterable[DataConnector] = ()) -> None:
        self._connectors: dict[str, DataConnector] = {}
        for connector in connectors:
            self.register(connector)

    def register(self, connector: DataConnector) -> None:
        name = connector.name.strip()
        if not name:
            raise ValueError("connector name must not be empty")
        if name in self._connectors:
            raise ValueError(f"connector already registered: {name}")
        self._connectors[name] = connector

    def all(self) -> tuple[DataConnector, ...]:
        return tuple(self._connectors.values())

    def names(self) -> tuple[str, ...]:
        return tuple(self._connectors)


class UniversalOpportunityScanner:
    """Runs connectors independently, deduplicates evidence, and extracts candidates."""

    def __init__(
        self,
        registry: ConnectorRegistry,
        extractor: OpportunityExtractor | None = None,
    ) -> None:
        if not registry.all():
            raise ValueError("scanner requires at least one registered connector")
        self.registry = registry
        self.extractor = extractor or OpportunityExtractor()

    def scan(self, request: ODSRequest) -> ScanSnapshot:
        started_at = datetime.now(timezone.utc)
        statuses: list[ConnectorScanStatus] = []
        documents: list[SourceDocument] = []

        for connector in self.registry.all():
            try:
                fetched = tuple(connector.fetch(request))
            except (ValueError, RuntimeError, OSError) as exc:
                statuses.append(
                    ConnectorScanStatus(
                        connector_name=connector.name,
                        status="failed",
                        document_count=0,
                        error=str(exc),
                    )
                )
                continue
            documents.extend(fetched)
            statuses.append(
                ConnectorScanStatus(
                    connector_name=connector.name,
                    status="completed",
                    document_count=len(fetched),
                )
            )

        unique_documents, duplicate_count = _deduplicate_documents(documents)
        opportunities = self.extractor.extract(unique_documents, request)
        completed_at = datetime.now(timezone.utc)
        scan_id = _build_scan_id(request, started_at, statuses)
        return ScanSnapshot(
            scan_id=scan_id,
            started_at=started_at,
            completed_at=completed_at,
            documents=unique_documents,
            opportunities=opportunities,
            connector_statuses=tuple(statuses),
            duplicate_count=duplicate_count,
        )


def _deduplicate_documents(
    documents: Iterable[SourceDocument],
) -> tuple[tuple[SourceDocument, ...], int]:
    unique: dict[str, SourceDocument] = {}
    duplicate_count = 0
    for document in documents:
        fingerprint = _document_fingerprint(document)
        if fingerprint in unique:
            duplicate_count += 1
            continue
        unique[fingerprint] = document
    return tuple(unique.values()), duplicate_count


def _document_fingerprint(document: SourceDocument) -> str:
    canonical_url = (document.url or "").strip().casefold()
    if canonical_url:
        return f"url:{canonical_url}"
    normalized = "|".join(
        (
            document.source_type.strip().casefold(),
            document.title.strip().casefold(),
            " ".join(document.text.split()).casefold(),
        )
    )
    return "content:" + sha256(normalized.encode("utf-8")).hexdigest()


def _build_scan_id(
    request: ODSRequest,
    started_at: datetime,
    statuses: Iterable[ConnectorScanStatus],
) -> str:
    material = "|".join(
        (
            request.subject.strip().casefold(),
            (request.country or "").strip().casefold(),
            started_at.isoformat(),
            ",".join(item.connector_name for item in statuses),
        )
    )
    return "scan-" + sha256(material.encode("utf-8")).hexdigest()[:16]
