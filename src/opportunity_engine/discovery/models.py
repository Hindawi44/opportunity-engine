"""Data contracts for Discovery Engine V1."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class DiscoveryCandidate:
    title: str
    url: str
    source: str
    discovered_at: str
    text: str = ""
    location: str | None = None
    quantity: int | None = None
    price_nok: float | None = None
    contact: str | None = None


@dataclass(frozen=True, slots=True)
class DiscoveryResult:
    candidate: DiscoveryCandidate
    scenario: str
    record_type: str
    status: str
    reason: str
    evidence: tuple[str, ...] = field(default_factory=tuple)
    category: str | None = None
    taxonomy_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["evidence"] = list(self.evidence)
        return payload
