"""Live-data foundation for ODS.

This module defines auditable source documents, connector contracts, and a
conservative deterministic extractor. It does not perform network access by
itself; real HTTP/API connectors can implement ``DataConnector`` later.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from .models import ODSRequest, OpportunityCandidate


@dataclass(frozen=True)
class SourceDocument:
    """Normalized evidence item collected from an external data source."""

    document_id: str
    source_name: str
    source_type: str
    title: str
    text: str
    url: str | None = None
    published_at: datetime | None = None
    country: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("document_id", "source_name", "source_type", "title", "text"):
            if not getattr(self, field_name).strip():
                raise ValueError(f"{field_name} must not be empty")


class DataConnector(Protocol):
    """Contract implemented by future web, API, file, and database connectors."""

    name: str

    def fetch(self, request: ODSRequest) -> tuple[SourceDocument, ...]: ...


@dataclass(frozen=True)
class StaticDataConnector:
    """Deterministic connector for tests, demos, and supplied source documents."""

    name: str
    documents: tuple[SourceDocument, ...]

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("connector name must not be empty")

    def fetch(self, request: ODSRequest) -> tuple[SourceDocument, ...]:
        country = (request.country or "").casefold()
        if not country:
            return self.documents
        return tuple(
            document
            for document in self.documents
            if document.country is None or document.country.casefold() == country
        )


@dataclass(frozen=True)
class ExtractionRule:
    """Transparent rule mapping source-language signals to an opportunity."""

    rule_id: str
    keywords: tuple[str, ...]
    title: str
    category: str
    description_template: str
    base_confidence: float = 0.55

    def __post_init__(self) -> None:
        if not self.rule_id.strip() or not self.keywords:
            raise ValueError("extraction rule requires an id and keywords")
        if not 0.0 <= self.base_confidence <= 1.0:
            raise ValueError("base_confidence must be between 0.0 and 1.0")


DEFAULT_EXTRACTION_RULES: tuple[ExtractionRule, ...] = (
    ExtractionRule(
        rule_id="slow_inventory",
        keywords=("slow-moving inventory", "unsold stock", "overstock", "deadstock"),
        title="Evidence-backed slow inventory recovery service",
        category="inventory",
        description_template=(
            "A service in {country} that helps fashion businesses recover value "
            "from slow or unsold inventory identified in external evidence."
        ),
        base_confidence=0.62,
    ),
    ExtractionRule(
        rule_id="returns_fit",
        keywords=("returns", "size issue", "fit issue", "wrong size"),
        title="Evidence-backed returns and fit intelligence",
        category="returns",
        description_template=(
            "A workflow in {country} that converts recurring returns and fit signals "
            "into alteration, product, and supplier decisions."
        ),
        base_confidence=0.60,
    ),
    ExtractionRule(
        rule_id="repair_reuse",
        keywords=("repair", "reuse", "resale", "textile waste", "circular"),
        title="Evidence-backed circular garment recovery network",
        category="circular_economy",
        description_template=(
            "A recovery network in {country} that routes garments to repair, reuse, "
            "resale, or responsible end-of-life channels."
        ),
        base_confidence=0.58,
    ),
)


class OpportunityExtractor:
    """Conservatively extracts candidates only when explicit signals are present."""

    name = "live_data_extractor"

    def __init__(self, rules: tuple[ExtractionRule, ...] = DEFAULT_EXTRACTION_RULES) -> None:
        if not rules:
            raise ValueError("extractor requires at least one rule")
        self.rules = rules

    def extract(
        self,
        documents: tuple[SourceDocument, ...],
        request: ODSRequest,
    ) -> tuple[OpportunityCandidate, ...]:
        candidates: list[OpportunityCandidate] = []
        country = request.country or "the target market"

        for rule in self.rules:
            matched = [
                document
                for document in documents
                if any(
                    keyword.casefold() in f"{document.title} {document.text}".casefold()
                    for keyword in rule.keywords
                )
            ]
            if not matched:
                continue

            evidence = tuple(self._evidence_label(document) for document in matched)
            confidence = min(0.95, rule.base_confidence + 0.05 * (len(matched) - 1))
            candidates.append(
                OpportunityCandidate(
                    opportunity_id=f"live-{rule.rule_id}",
                    title=rule.title,
                    description=rule.description_template.format(country=country),
                    category=rule.category,
                    evidence=evidence,
                    confidence=round(confidence, 2),
                    source_plugin=self.name,
                )
            )

        return tuple(candidates)

    @staticmethod
    def _evidence_label(document: SourceDocument) -> str:
        location = document.url or f"document:{document.document_id}"
        return f"{document.source_name}:{document.title}:{location}"


@dataclass(frozen=True)
class LiveDataResult:
    """Auditable output of one connector-and-extractor run."""

    documents: tuple[SourceDocument, ...]
    opportunities: tuple[OpportunityCandidate, ...]
    connector_names: tuple[str, ...]


class LiveDataPipeline:
    """Collects documents, removes duplicates, and extracts opportunities."""

    def __init__(
        self,
        connectors: tuple[DataConnector, ...],
        extractor: OpportunityExtractor | None = None,
    ) -> None:
        if not connectors:
            raise ValueError("live data pipeline requires at least one connector")
        self.connectors = connectors
        self.extractor = extractor or OpportunityExtractor()

    def run(self, request: ODSRequest) -> LiveDataResult:
        documents_by_id: dict[str, SourceDocument] = {}
        for connector in self.connectors:
            for document in connector.fetch(request):
                documents_by_id.setdefault(document.document_id, document)

        documents = tuple(documents_by_id.values())
        opportunities = self.extractor.extract(documents, request)
        return LiveDataResult(
            documents=documents,
            opportunities=opportunities,
            connector_names=tuple(connector.name for connector in self.connectors),
        )
