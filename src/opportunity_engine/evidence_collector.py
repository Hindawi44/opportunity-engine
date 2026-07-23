"""Collect structured evidence from Opportunity Engine's existing pipeline outputs.

This first collector intentionally performs no external web search. It converts only
explicit, already-observed pipeline fields into ResearchEvidence records, persists them,
and mirrors concise evidence into the Living Investment File for later scenario analysis.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .evidence_store import (
    EvidenceConfidence,
    EvidenceDirection,
    EvidenceRepository,
    EvidenceType,
    ResearchEvidence,
)
from .living_investment_file import Confidence, Evidence, LivingInvestmentFile


@dataclass(frozen=True, slots=True)
class EvidenceCollectionResult:
    opportunity_id: str
    extracted_count: int
    created_count: int
    updated_count: int
    linked_count: int
    evidence_ids: tuple[str, ...]


class ExistingSourceEvidenceCollector:
    """Extract auditable evidence from current normalized pipeline data."""

    def __init__(self, repository: EvidenceRepository | None = None) -> None:
        self.repository = repository or EvidenceRepository()

    def collect(
        self,
        investment_file: LivingInvestmentFile,
        row: dict[str, Any],
        *,
        intelligence: dict[str, Any] | None = None,
        discovery: dict[str, Any] | None = None,
    ) -> EvidenceCollectionResult:
        opportunity_id = investment_file.opportunity_id
        candidates = list(self._extract(opportunity_id, row, intelligence or {}, discovery or {}))
        created = 0
        updated = 0
        linked = 0
        stored_ids: list[str] = []

        for candidate in candidates:
            result = self.repository.upsert(candidate)
            stored = result.evidence
            stored_ids.append(stored.evidence_id)
            if result.created:
                created += 1
            elif result.observation_added:
                updated += 1

            if self._link_to_investment_file(investment_file, stored):
                linked += 1

        return EvidenceCollectionResult(
            opportunity_id=opportunity_id,
            extracted_count=len(candidates),
            created_count=created,
            updated_count=updated,
            linked_count=linked,
            evidence_ids=tuple(stored_ids),
        )

    def _extract(
        self,
        opportunity_id: str,
        row: dict[str, Any],
        intelligence: dict[str, Any],
        discovery: dict[str, Any],
    ) -> Iterable[ResearchEvidence]:
        source_name = str(row.get("source_name") or row.get("source") or "Opportunity pipeline")
        source_url = row.get("url")

        asking_price = _non_negative_number(row.get("asking_price_nok"))
        if asking_price is not None:
            yield ResearchEvidence.create(
                opportunity_id=opportunity_id,
                evidence_type=EvidenceType.MARKET_PRICE,
                statement="The source listing reports the current asking price.",
                source_name=source_name,
                source_url=source_url,
                confidence=EvidenceConfidence.HIGH,
                direction=EvidenceDirection.NEUTRAL,
                numeric_value=asking_price,
                currency="NOK",
                metadata={"field": "asking_price_nok", "origin": "pipeline"},
            )

        market_value = _non_negative_number(row.get("market_value_nok"))
        market_verified = bool(row.get("market_is_verified"))
        comparable_count = _non_negative_int(row.get("market_comparable_count"))
        if market_verified and market_value is not None:
            yield ResearchEvidence.create(
                opportunity_id=opportunity_id,
                evidence_type=EvidenceType.MARKET_PRICE,
                statement="The market verification engine produced a conservative market value.",
                source_name="Opportunity Engine market verification",
                source_url=source_url,
                confidence=EvidenceConfidence.HIGH if comparable_count >= 3 else EvidenceConfidence.MEDIUM,
                direction=EvidenceDirection.SUPPORTS,
                numeric_value=market_value,
                currency="NOK",
                notes=f"Comparable count: {comparable_count}",
                metadata={"field": "market_value_nok", "comparable_count": comparable_count},
            )

        seller_verified = bool(row.get("seller_is_verified"))
        seller_name = _text(row.get("seller_name"))
        seller_score = _non_negative_number(row.get("seller_score"))
        if seller_verified or seller_name:
            statement = "Seller identity or reliability information is present in the pipeline."
            yield ResearchEvidence.create(
                opportunity_id=opportunity_id,
                evidence_type=EvidenceType.SELLER,
                statement=statement,
                source_name=source_name,
                source_url=source_url,
                confidence=EvidenceConfidence.HIGH if seller_verified else EvidenceConfidence.MEDIUM,
                direction=EvidenceDirection.SUPPORTS if seller_verified else EvidenceDirection.NEUTRAL,
                numeric_value=seller_score,
                notes=seller_name,
                metadata={"seller_verified": seller_verified, "seller_name": seller_name},
            )

        city = _text(row.get("city"))
        if city:
            yield ResearchEvidence.create(
                opportunity_id=opportunity_id,
                evidence_type=EvidenceType.LOGISTICS,
                statement=f"The opportunity is located in {city}.",
                source_name=source_name,
                source_url=source_url,
                confidence=EvidenceConfidence.HIGH,
                direction=EvidenceDirection.NEUTRAL,
                metadata={"city": city},
            )

        for container, origin in ((intelligence, "intelligence"), (discovery, "discovery")):
            for key in ("reasons", "warnings", "blockers", "signals", "opportunities"):
                values = container.get(key)
                if not isinstance(values, (list, tuple)):
                    continue
                for value in values:
                    text = _text(value)
                    if not text:
                        continue
                    direction = EvidenceDirection.WEAKENS if key in {"warnings", "blockers"} else EvidenceDirection.SUPPORTS
                    yield ResearchEvidence.create(
                        opportunity_id=opportunity_id,
                        evidence_type=EvidenceType.OTHER,
                        statement=text,
                        source_name=f"Opportunity Engine {origin}",
                        source_url=source_url,
                        confidence=EvidenceConfidence.MEDIUM,
                        direction=direction,
                        metadata={"origin": origin, "field": key},
                    )

    @staticmethod
    def _link_to_investment_file(item: LivingInvestmentFile, evidence: ResearchEvidence) -> bool:
        source_key = f"research:{evidence.evidence_id}"
        if any(existing.notes == source_key for existing in item.evidence):
            return False
        confidence = {
            EvidenceConfidence.LOW: Confidence.LOW,
            EvidenceConfidence.MEDIUM: Confidence.MEDIUM,
            EvidenceConfidence.HIGH: Confidence.HIGH,
        }[evidence.confidence]
        item.add_evidence(
            Evidence.create(
                evidence.statement,
                source_url=evidence.source_url,
                source_name=evidence.source_name,
                confidence=confidence,
                notes=source_key,
            )
        )
        return True


def _non_negative_number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _non_negative_int(value: Any) -> int:
    number = _non_negative_number(value)
    return int(number) if number is not None else 0


def _text(value: Any) -> str | None:
    text = " ".join(str(value or "").split()).strip()
    return text or None
