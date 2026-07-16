"""Reusable deterministic discovery framework for ODS sector plugins."""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata

from .models import ODSSession, OpportunityCandidate, Stage, StageResult, Status


@dataclass(frozen=True)
class OpportunitySeed:
    """One curated opportunity emitted by a scanner."""

    title: str
    description: str
    category: str
    evidence: tuple[str, ...]
    confidence: float


@dataclass(frozen=True)
class Scanner:
    """Deterministic scanner composed from curated opportunity seeds."""

    name: str
    seeds: tuple[OpportunitySeed, ...]

    def scan(
        self,
        *,
        sector_key: str,
        plugin_name: str,
        country: str | None,
    ) -> list[OpportunityCandidate]:
        market = country.strip() if country and country.strip() else "the target market"
        candidates: list[OpportunityCandidate] = []
        for seed in self.seeds:
            description = seed.description.format(market=market)
            if market not in description:
                description = f"{description} Market: {market}."
            candidates.append(
                OpportunityCandidate(
                    opportunity_id=(
                        f"{sector_key}-{self.name}-{stable_slug(seed.title)}"
                    ),
                    title=seed.title,
                    description=description,
                    category=seed.category,
                    evidence=seed.evidence,
                    confidence=seed.confidence,
                    source_plugin=f"{plugin_name}:{self.name}",
                )
            )
        return candidates


class CuratedDiscoveryPlugin:
    """Base implementation for a deterministic sector discovery plugin."""

    stage = Stage.DISCOVERY
    name: str
    sector_key: str
    aliases: frozenset[str]
    scanners: tuple[Scanner, ...]

    def run(self, session: ODSSession) -> StageResult:
        if not self.supports(session.request.subject):
            return StageResult(
                stage=self.stage,
                status=Status.FAILED,
                errors=[
                    f"{self.name} does not support subject: {session.request.subject}"
                ],
            )

        candidates: list[OpportunityCandidate] = []
        for scanner in self.scanners:
            candidates.extend(
                scanner.scan(
                    sector_key=self.sector_key,
                    plugin_name=self.name,
                    country=session.request.country,
                )
            )

        deduplicated = deduplicate_candidates(candidates)
        return StageResult(
            stage=self.stage,
            status=Status.COMPLETED,
            payload=tuple(deduplicated),
            evidence=[
                f"scanner_completed:{scanner.name}:{len(scanner.seeds)}"
                for scanner in self.scanners
            ],
        )

    def supports(self, subject: str) -> bool:
        normalized = normalize_subject(subject)
        return normalized in {normalize_subject(alias) for alias in self.aliases}


def normalize_subject(value: str) -> str:
    """Normalize multilingual user input without discarding non-Latin scripts."""

    return unicodedata.normalize("NFKC", value).strip().casefold()


def deduplicate_candidates(
    candidates: list[OpportunityCandidate],
) -> list[OpportunityCandidate]:
    """Keep the highest-confidence candidate for each normalized title."""

    unique: dict[str, OpportunityCandidate] = {}
    for candidate in candidates:
        key = stable_slug(candidate.title)
        existing = unique.get(key)
        if existing is None or candidate.confidence > existing.confidence:
            unique[key] = candidate
    return list(unique.values())


def stable_slug(value: str) -> str:
    """Create a stable ASCII identifier from a candidate title."""

    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.casefold()).strip("-")
    if not slug:
        raise ValueError("value cannot be converted to a stable slug")
    return slug
