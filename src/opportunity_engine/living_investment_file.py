"""Living Investment File domain model for Opportunity Engine v2.5.

This module deliberately separates confirmed facts, assumptions, evidence,
missing information, monetisation paths and update history.  It uses only the
Python standard library so it can be adopted without changing dependencies.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4


def utc_now() -> str:
    """Return an ISO-8601 UTC timestamp."""

    return datetime.now(timezone.utc).isoformat()


class OpportunityStatus(str, Enum):
    DISCOVERED = "discovered"
    RESEARCHING = "researching"
    VALIDATING = "validating"
    ACTIONABLE = "actionable"
    PAUSED = "paused"
    CLOSED = "closed"


class Confidence(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RevenuePathType(str, Enum):
    PURCHASE = "purchase"
    BROKERAGE = "brokerage"
    PARTNERSHIP = "partnership"
    LOT_SPLIT = "lot_split"
    PRE_SALE = "pre_sale"
    LIQUIDATION_MANAGEMENT = "liquidation_management"
    OTHER = "other"


@dataclass(slots=True)
class Evidence:
    evidence_id: str
    statement: str
    source_url: str | None
    observed_at: str
    confidence: Confidence
    source_name: str | None = None
    notes: str | None = None

    @classmethod
    def create(
        cls,
        statement: str,
        *,
        source_url: str | None = None,
        source_name: str | None = None,
        confidence: Confidence = Confidence.MEDIUM,
        notes: str | None = None,
    ) -> "Evidence":
        if not statement.strip():
            raise ValueError("Evidence statement cannot be empty")
        return cls(
            evidence_id=f"ev_{uuid4().hex}",
            statement=statement.strip(),
            source_url=source_url,
            source_name=source_name,
            observed_at=utc_now(),
            confidence=confidence,
            notes=notes,
        )


@dataclass(slots=True)
class Fact:
    fact_id: str
    statement: str
    evidence_ids: list[str]
    confidence: Confidence


@dataclass(slots=True)
class Assumption:
    assumption_id: str
    statement: str
    validation_method: str
    status: str = "unverified"


@dataclass(slots=True)
class MissingInformation:
    item_id: str
    question: str
    why_it_matters: str
    acquisition_method: str
    priority: str = "medium"
    resolved: bool = False


@dataclass(slots=True)
class RevenuePath:
    path_id: str
    path_type: RevenuePathType
    title: str
    description: str
    requirements: list[str] = field(default_factory=list)
    estimated_cost_nok: float | None = None
    estimated_revenue_nok: float | None = None
    duration_days: int | None = None
    risks: list[str] = field(default_factory=list)
    first_step: str | None = None
    evidence_ids: list[str] = field(default_factory=list)

    @property
    def estimated_profit_nok(self) -> float | None:
        if self.estimated_cost_nok is None or self.estimated_revenue_nok is None:
            return None
        return self.estimated_revenue_nok - self.estimated_cost_nok


@dataclass(slots=True)
class SmallTest:
    hypothesis: str
    action: str
    max_cost_nok: float | None
    success_metric: str
    stop_condition: str
    status: str = "planned"


@dataclass(slots=True)
class UpdateEvent:
    timestamp: str
    event_type: str
    summary: str
    changed_fields: list[str] = field(default_factory=list)


@dataclass(slots=True)
class LivingInvestmentFile:
    opportunity_id: str
    title: str
    source_url: str | None
    source_name: str | None
    discovered_at: str
    updated_at: str
    status: OpportunityStatus = OpportunityStatus.DISCOVERED
    summary: str = ""
    location: str | None = None
    asking_price_nok: float | None = None
    facts: list[Fact] = field(default_factory=list)
    assumptions: list[Assumption] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    missing_information: list[MissingInformation] = field(default_factory=list)
    potential_buyers: list[str] = field(default_factory=list)
    revenue_paths: list[RevenuePath] = field(default_factory=list)
    small_test: SmallTest | None = None
    best_current_path_id: str | None = None
    next_action: str | None = None
    internal_score: float | None = None
    internal_signal: str | None = None
    update_history: list[UpdateEvent] = field(default_factory=list)
    schema_version: str = "2.5.0"

    @classmethod
    def create(
        cls,
        title: str,
        *,
        source_url: str | None = None,
        source_name: str | None = None,
        location: str | None = None,
        asking_price_nok: float | None = None,
        summary: str = "",
        opportunity_id: str | None = None,
    ) -> "LivingInvestmentFile":
        if not title.strip():
            raise ValueError("Opportunity title cannot be empty")
        if asking_price_nok is not None and asking_price_nok < 0:
            raise ValueError("asking_price_nok cannot be negative")
        now = utc_now()
        file = cls(
            opportunity_id=opportunity_id or f"opp_{uuid4().hex}",
            title=title.strip(),
            source_url=source_url,
            source_name=source_name,
            location=location,
            asking_price_nok=asking_price_nok,
            summary=summary.strip(),
            discovered_at=now,
            updated_at=now,
        )
        file._record("created", "Living investment file created")
        return file

    def add_evidence(self, item: Evidence) -> None:
        if any(existing.evidence_id == item.evidence_id for existing in self.evidence):
            raise ValueError(f"Duplicate evidence id: {item.evidence_id}")
        self.evidence.append(item)
        self._touch("evidence_added", item.statement, ["evidence"])

    def add_fact(
        self,
        statement: str,
        *,
        evidence_ids: Iterable[str],
        confidence: Confidence = Confidence.MEDIUM,
    ) -> Fact:
        ids = list(dict.fromkeys(evidence_ids))
        known = {item.evidence_id for item in self.evidence}
        unknown = [item_id for item_id in ids if item_id not in known]
        if unknown:
            raise ValueError(f"Unknown evidence ids: {', '.join(unknown)}")
        if not ids:
            raise ValueError("A confirmed fact must reference at least one evidence item")
        fact = Fact(f"fact_{uuid4().hex}", statement.strip(), ids, confidence)
        self.facts.append(fact)
        self._touch("fact_added", fact.statement, ["facts"])
        return fact

    def add_assumption(self, statement: str, validation_method: str) -> Assumption:
        if not statement.strip() or not validation_method.strip():
            raise ValueError("Assumption and validation method are required")
        item = Assumption(
            f"asm_{uuid4().hex}", statement.strip(), validation_method.strip()
        )
        self.assumptions.append(item)
        self._touch("assumption_added", item.statement, ["assumptions"])
        return item

    def add_missing_information(
        self,
        question: str,
        why_it_matters: str,
        acquisition_method: str,
        *,
        priority: str = "medium",
    ) -> MissingInformation:
        item = MissingInformation(
            f"missing_{uuid4().hex}",
            question.strip(),
            why_it_matters.strip(),
            acquisition_method.strip(),
            priority,
        )
        self.missing_information.append(item)
        self._touch("missing_information_added", item.question, ["missing_information"])
        return item

    def add_revenue_path(self, path: RevenuePath) -> None:
        if any(existing.path_id == path.path_id for existing in self.revenue_paths):
            raise ValueError(f"Duplicate revenue path id: {path.path_id}")
        for value_name, value in (
            ("estimated_cost_nok", path.estimated_cost_nok),
            ("estimated_revenue_nok", path.estimated_revenue_nok),
        ):
            if value is not None and value < 0:
                raise ValueError(f"{value_name} cannot be negative")
        self.revenue_paths.append(path)
        self._touch("revenue_path_added", path.title, ["revenue_paths"])

    def select_best_path(self, path_id: str, next_action: str) -> None:
        if path_id not in {item.path_id for item in self.revenue_paths}:
            raise ValueError(f"Unknown revenue path id: {path_id}")
        self.best_current_path_id = path_id
        self.next_action = next_action.strip()
        self._touch(
            "best_path_selected",
            f"Selected {path_id} as current best path",
            ["best_current_path_id", "next_action"],
        )

    def set_status(self, status: OpportunityStatus, summary: str) -> None:
        self.status = status
        self._touch("status_changed", summary, ["status"])

    def merge_discovery_update(self, incoming: dict[str, Any]) -> list[str]:
        """Apply changed discovery fields while preserving the research record.

        Missing values remain ``None``; they are never converted to zero.
        Only explicitly supplied supported fields are considered.
        """

        supported = {
            "title",
            "source_url",
            "source_name",
            "summary",
            "location",
            "asking_price_nok",
        }
        changed: list[str] = []
        for key in supported.intersection(incoming):
            value = incoming[key]
            if key == "asking_price_nok" and value is not None and value < 0:
                raise ValueError("asking_price_nok cannot be negative")
            if value != getattr(self, key):
                setattr(self, key, value)
                changed.append(key)
        if changed:
            self._touch(
                "discovery_updated",
                f"Updated discovery fields: {', '.join(sorted(changed))}",
                changed,
            )
        return changed

    def readiness_gaps(self) -> list[str]:
        gaps: list[str] = []
        if not self.summary:
            gaps.append("summary")
        if not self.facts:
            gaps.append("facts")
        if not self.evidence:
            gaps.append("evidence")
        if len(self.revenue_paths) < 2:
            gaps.append("multiple_revenue_paths")
        if self.small_test is None:
            gaps.append("small_test")
        if not self.next_action:
            gaps.append("next_action")
        return gaps

    @property
    def is_v250_complete(self) -> bool:
        return not self.readiness_gaps()

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["status"] = self.status.value
        for item in payload["evidence"]:
            item["confidence"] = item["confidence"].value
        for item in payload["facts"]:
            item["confidence"] = item["confidence"].value
        for item in payload["revenue_paths"]:
            item["path_type"] = item["path_type"].value
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "LivingInvestmentFile":
        data = deepcopy(payload)
        data["status"] = OpportunityStatus(data.get("status", "discovered"))
        data["evidence"] = [
            Evidence(**{**item, "confidence": Confidence(item["confidence"])})
            for item in data.get("evidence", [])
        ]
        data["facts"] = [
            Fact(**{**item, "confidence": Confidence(item["confidence"])})
            for item in data.get("facts", [])
        ]
        data["assumptions"] = [Assumption(**item) for item in data.get("assumptions", [])]
        data["missing_information"] = [
            MissingInformation(**item) for item in data.get("missing_information", [])
        ]
        data["revenue_paths"] = [
            RevenuePath(**{**item, "path_type": RevenuePathType(item["path_type"])})
            for item in data.get("revenue_paths", [])
        ]
        if data.get("small_test") is not None:
            data["small_test"] = SmallTest(**data["small_test"])
        data["update_history"] = [
            UpdateEvent(**item) for item in data.get("update_history", [])
        ]
        return cls(**data)

    def _touch(self, event_type: str, summary: str, changed_fields: list[str]) -> None:
        self.updated_at = utc_now()
        self._record(event_type, summary, changed_fields)

    def _record(
        self,
        event_type: str,
        summary: str,
        changed_fields: list[str] | None = None,
    ) -> None:
        self.update_history.append(
            UpdateEvent(utc_now(), event_type, summary, changed_fields or [])
        )


class LivingInvestmentFileRepository:
    """Atomic JSON persistence with one file per opportunity."""

    def __init__(self, root: str | Path = "data/investment_files") -> None:
        self.root = Path(root)

    def save(self, item: LivingInvestmentFile) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        destination = self.root / f"{item.opportunity_id}.json"
        temporary = destination.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(item.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(destination)
        return destination

    def load(self, opportunity_id: str) -> LivingInvestmentFile:
        path = self.root / f"{opportunity_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"Investment file not found: {opportunity_id}")
        return LivingInvestmentFile.from_dict(
            json.loads(path.read_text(encoding="utf-8"))
        )

    def list_ids(self) -> list[str]:
        if not self.root.exists():
            return []
        return sorted(path.stem for path in self.root.glob("opp_*.json"))
