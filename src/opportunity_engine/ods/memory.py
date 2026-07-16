"""Persistent opportunity memory for comparing scanner snapshots over time."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
from pathlib import Path
from typing import Iterable

from .models import OpportunityCandidate
from .scanner import ScanSnapshot


class OpportunityChangeType(str, Enum):
    NEW = "NEW"
    UPDATED = "UPDATED"
    UNCHANGED = "UNCHANGED"
    REMOVED = "REMOVED"


@dataclass(frozen=True)
class OpportunityMemoryRecord:
    opportunity_id: str
    title: str
    category: str
    country: str | None
    first_seen: str
    last_seen: str
    times_seen: int
    confidence: float
    evidence_fingerprint: str
    active: bool


@dataclass(frozen=True)
class OpportunityChange:
    opportunity_id: str
    title: str
    change_type: OpportunityChangeType
    previous_confidence: float | None
    current_confidence: float | None


@dataclass(frozen=True)
class MemoryRunResult:
    records: tuple[OpportunityMemoryRecord, ...]
    changes: tuple[OpportunityChange, ...]

    @property
    def new_count(self) -> int:
        return sum(item.change_type is OpportunityChangeType.NEW for item in self.changes)

    @property
    def updated_count(self) -> int:
        return sum(item.change_type is OpportunityChangeType.UPDATED for item in self.changes)

    @property
    def unchanged_count(self) -> int:
        return sum(item.change_type is OpportunityChangeType.UNCHANGED for item in self.changes)

    @property
    def removed_count(self) -> int:
        return sum(item.change_type is OpportunityChangeType.REMOVED for item in self.changes)


class OpportunityMemoryEngine:
    """Stores opportunity history in a small auditable JSON file."""

    def __init__(self, storage_path: str | Path) -> None:
        self.storage_path = Path(storage_path)

    def run(self, snapshot: ScanSnapshot, *, country: str | None = None) -> MemoryRunResult:
        now = snapshot.completed_at.astimezone(timezone.utc).isoformat()
        previous = self._load()
        current_by_id = {
            candidate.opportunity_id: candidate for candidate in snapshot.opportunities
        }
        records: dict[str, OpportunityMemoryRecord] = {}
        changes: list[OpportunityChange] = []

        for opportunity_id, candidate in current_by_id.items():
            fingerprint = _candidate_fingerprint(candidate)
            old = previous.get(opportunity_id)
            if old is None:
                record = OpportunityMemoryRecord(
                    opportunity_id=opportunity_id,
                    title=candidate.title,
                    category=candidate.category,
                    country=country,
                    first_seen=now,
                    last_seen=now,
                    times_seen=1,
                    confidence=candidate.confidence,
                    evidence_fingerprint=fingerprint,
                    active=True,
                )
                change_type = OpportunityChangeType.NEW
                previous_confidence = None
            else:
                changed = (
                    abs(old.confidence - candidate.confidence) > 1e-9
                    or old.evidence_fingerprint != fingerprint
                    or old.title != candidate.title
                    or old.category != candidate.category
                    or not old.active
                )
                record = OpportunityMemoryRecord(
                    opportunity_id=opportunity_id,
                    title=candidate.title,
                    category=candidate.category,
                    country=country or old.country,
                    first_seen=old.first_seen,
                    last_seen=now,
                    times_seen=old.times_seen + 1,
                    confidence=candidate.confidence,
                    evidence_fingerprint=fingerprint,
                    active=True,
                )
                change_type = (
                    OpportunityChangeType.UPDATED if changed else OpportunityChangeType.UNCHANGED
                )
                previous_confidence = old.confidence

            records[opportunity_id] = record
            changes.append(
                OpportunityChange(
                    opportunity_id=opportunity_id,
                    title=candidate.title,
                    change_type=change_type,
                    previous_confidence=previous_confidence,
                    current_confidence=candidate.confidence,
                )
            )

        for opportunity_id, old in previous.items():
            if opportunity_id in current_by_id:
                continue
            removed = OpportunityMemoryRecord(
                opportunity_id=old.opportunity_id,
                title=old.title,
                category=old.category,
                country=old.country,
                first_seen=old.first_seen,
                last_seen=old.last_seen,
                times_seen=old.times_seen,
                confidence=old.confidence,
                evidence_fingerprint=old.evidence_fingerprint,
                active=False,
            )
            records[opportunity_id] = removed
            if old.active:
                changes.append(
                    OpportunityChange(
                        opportunity_id=opportunity_id,
                        title=old.title,
                        change_type=OpportunityChangeType.REMOVED,
                        previous_confidence=old.confidence,
                        current_confidence=None,
                    )
                )

        ordered = tuple(sorted(records.values(), key=lambda item: item.opportunity_id))
        self._save(ordered)
        return MemoryRunResult(records=ordered, changes=tuple(changes))

    def _load(self) -> dict[str, OpportunityMemoryRecord]:
        if not self.storage_path.exists():
            return {}
        try:
            raw = json.loads(self.storage_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Unable to read opportunity memory: {exc}") from exc
        if not isinstance(raw, list):
            raise RuntimeError("Opportunity memory file must contain a JSON list")
        records: dict[str, OpportunityMemoryRecord] = {}
        for item in raw:
            if not isinstance(item, dict):
                raise RuntimeError("Opportunity memory contains an invalid record")
            record = OpportunityMemoryRecord(**item)
            records[record.opportunity_id] = record
        return records

    def _save(self, records: Iterable[OpportunityMemoryRecord]) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        payload = [asdict(record) for record in records]
        temporary = self.storage_path.with_suffix(self.storage_path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temporary.replace(self.storage_path)


def _candidate_fingerprint(candidate: OpportunityCandidate) -> str:
    material = "|".join(
        (
            candidate.title.strip().casefold(),
            candidate.category.strip().casefold(),
            candidate.description.strip().casefold(),
            "||".join(sorted(value.strip().casefold() for value in candidate.evidence)),
        )
    )
    return sha256(material.encode("utf-8")).hexdigest()
