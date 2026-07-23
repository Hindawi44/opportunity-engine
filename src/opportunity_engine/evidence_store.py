"""Evidence data model and persistent repository for Opportunity Engine v2.5.2.

The repository is append/update oriented, preserves observation history, rejects
invalid financial values, and deduplicates evidence using a stable fingerprint.
Only explicitly supplied facts are stored; missing values remain missing.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class EvidenceType(str, Enum):
    MARKET_PRICE = "market_price"
    BUYER = "buyer"
    COST = "cost"
    DEMAND = "demand"
    LEGAL = "legal"
    SELLER = "seller"
    LOGISTICS = "logistics"
    OTHER = "other"


class EvidenceDirection(str, Enum):
    SUPPORTS = "supports"
    WEAKENS = "weakens"
    NEUTRAL = "neutral"


class EvidenceConfidence(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(slots=True)
class EvidenceObservation:
    observed_at: str
    statement: str
    numeric_value: float | None = None
    currency: str | None = None
    notes: str | None = None

    def __post_init__(self) -> None:
        if not self.statement.strip():
            raise ValueError("Evidence observation statement cannot be empty")
        if self.numeric_value is not None and self.numeric_value < 0:
            raise ValueError("numeric_value cannot be negative")
        if self.currency is not None:
            self.currency = self.currency.strip().upper() or None


@dataclass(slots=True)
class ResearchEvidence:
    evidence_id: str
    opportunity_id: str
    evidence_type: EvidenceType
    statement: str
    source_name: str
    source_url: str | None
    confidence: EvidenceConfidence
    direction: EvidenceDirection = EvidenceDirection.NEUTRAL
    scenario_ids: list[str] = field(default_factory=list)
    collected_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    observations: list[EvidenceObservation] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    fingerprint: str = ""

    def __post_init__(self) -> None:
        for field_name, value in (
            ("opportunity_id", self.opportunity_id),
            ("statement", self.statement),
            ("source_name", self.source_name),
        ):
            if not value.strip():
                raise ValueError(f"{field_name} cannot be empty")
        if self.source_url is not None and not self.source_url.startswith("https://"):
            raise ValueError("source_url must use HTTPS")
        self.scenario_ids = list(dict.fromkeys(item.strip() for item in self.scenario_ids if item.strip()))
        if not self.fingerprint:
            self.fingerprint = self.build_fingerprint(
                self.opportunity_id,
                self.evidence_type,
                self.statement,
                self.source_url,
                self.source_name,
            )

    @classmethod
    def create(
        cls,
        *,
        opportunity_id: str,
        evidence_type: EvidenceType,
        statement: str,
        source_name: str,
        source_url: str | None = None,
        confidence: EvidenceConfidence = EvidenceConfidence.MEDIUM,
        direction: EvidenceDirection = EvidenceDirection.NEUTRAL,
        scenario_ids: Iterable[str] = (),
        numeric_value: float | None = None,
        currency: str | None = None,
        notes: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "ResearchEvidence":
        now = utc_now()
        observation = EvidenceObservation(
            observed_at=now,
            statement=statement.strip(),
            numeric_value=numeric_value,
            currency=currency,
            notes=notes,
        )
        return cls(
            evidence_id=f"rev_{uuid4().hex}",
            opportunity_id=opportunity_id.strip(),
            evidence_type=evidence_type,
            statement=statement.strip(),
            source_name=source_name.strip(),
            source_url=source_url,
            confidence=confidence,
            direction=direction,
            scenario_ids=list(scenario_ids),
            collected_at=now,
            updated_at=now,
            observations=[observation],
            metadata=dict(metadata or {}),
        )

    @staticmethod
    def build_fingerprint(
        opportunity_id: str,
        evidence_type: EvidenceType,
        statement: str,
        source_url: str | None,
        source_name: str,
    ) -> str:
        normalized = "|".join(
            (
                opportunity_id.strip().casefold(),
                evidence_type.value,
                " ".join(statement.split()).casefold(),
                (source_url or "").strip().casefold(),
                source_name.strip().casefold(),
            )
        )
        return sha256(normalized.encode("utf-8")).hexdigest()

    def add_observation(
        self,
        *,
        statement: str,
        numeric_value: float | None = None,
        currency: str | None = None,
        notes: str | None = None,
        observed_at: str | None = None,
    ) -> None:
        observation = EvidenceObservation(
            observed_at=observed_at or utc_now(),
            statement=statement.strip(),
            numeric_value=numeric_value,
            currency=currency,
            notes=notes,
        )
        duplicate = any(
            item.statement == observation.statement
            and item.numeric_value == observation.numeric_value
            and item.currency == observation.currency
            and item.notes == observation.notes
            for item in self.observations
        )
        if duplicate:
            return
        self.observations.append(observation)
        self.updated_at = utc_now()

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["evidence_type"] = self.evidence_type.value
        payload["confidence"] = self.confidence.value
        payload["direction"] = self.direction.value
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ResearchEvidence":
        data = dict(payload)
        data["evidence_type"] = EvidenceType(data["evidence_type"])
        data["confidence"] = EvidenceConfidence(data["confidence"])
        data["direction"] = EvidenceDirection(data.get("direction", "neutral"))
        data["observations"] = [EvidenceObservation(**item) for item in data.get("observations", [])]
        return cls(**data)


@dataclass(frozen=True, slots=True)
class EvidenceUpsertResult:
    evidence: ResearchEvidence
    created: bool
    observation_added: bool


class EvidenceRepository:
    """Atomic JSON evidence store grouped by opportunity."""

    def __init__(self, root: str | Path = "data/evidence") -> None:
        self.root = Path(root)

    def upsert(self, incoming: ResearchEvidence) -> EvidenceUpsertResult:
        existing = self.find_by_fingerprint(incoming.opportunity_id, incoming.fingerprint)
        if existing is None:
            self._save(incoming)
            return EvidenceUpsertResult(incoming, created=True, observation_added=True)

        before = len(existing.observations)
        for observation in incoming.observations:
            existing.add_observation(
                statement=observation.statement,
                numeric_value=observation.numeric_value,
                currency=observation.currency,
                notes=observation.notes,
                observed_at=observation.observed_at,
            )
        existing.confidence = incoming.confidence
        existing.direction = incoming.direction
        existing.scenario_ids = list(dict.fromkeys(existing.scenario_ids + incoming.scenario_ids))
        existing.metadata.update(incoming.metadata)
        existing.updated_at = utc_now()
        self._save(existing)
        return EvidenceUpsertResult(
            existing,
            created=False,
            observation_added=len(existing.observations) > before,
        )

    def load(self, opportunity_id: str, evidence_id: str) -> ResearchEvidence:
        path = self._opportunity_dir(opportunity_id) / f"{evidence_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"Evidence not found: {opportunity_id}/{evidence_id}")
        return ResearchEvidence.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def list_for_opportunity(self, opportunity_id: str) -> list[ResearchEvidence]:
        directory = self._opportunity_dir(opportunity_id)
        if not directory.exists():
            return []
        return [
            ResearchEvidence.from_dict(json.loads(path.read_text(encoding="utf-8")))
            for path in sorted(directory.glob("rev_*.json"))
        ]

    def find_by_fingerprint(self, opportunity_id: str, fingerprint: str) -> ResearchEvidence | None:
        for item in self.list_for_opportunity(opportunity_id):
            if item.fingerprint == fingerprint:
                return item
        return None

    def _save(self, item: ResearchEvidence) -> Path:
        directory = self._opportunity_dir(item.opportunity_id)
        directory.mkdir(parents=True, exist_ok=True)
        destination = directory / f"{item.evidence_id}.json"
        temporary = destination.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(item.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(destination)
        return destination

    def _opportunity_dir(self, opportunity_id: str) -> Path:
        safe = opportunity_id.strip()
        if not safe or "/" in safe or "\\" in safe or safe in {".", ".."}:
            raise ValueError("Invalid opportunity_id")
        return self.root / safe
