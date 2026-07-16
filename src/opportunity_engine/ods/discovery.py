"""Deterministic first discovery plugin for the ODS fashion reference case.

The alpha plugin intentionally uses a small curated knowledge map instead of live
web research. Its purpose is to prove the ODS plugin contract, scanner composition,
normalization, deduplication, and auditable output before adding external data
connectors.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata

from .models import ODSSession, OpportunityCandidate, Stage, StageResult, Status


_FASHION_ALIASES = {
    "fashion",
    "apparel",
    "clothing",
    "clothes",
    "garments",
    "ازياء",
    "الأزياء",
    "ملابس",
    "الملابس",
    "ثياب",
}


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
    """Small deterministic scanner used by the alpha discovery plugin."""

    name: str
    seeds: tuple[OpportunitySeed, ...]

    def scan(self, country: str | None) -> list[OpportunityCandidate]:
        market = country.strip() if country and country.strip() else "the target market"
        candidates: list[OpportunityCandidate] = []
        for seed in self.seeds:
            slug = _slugify(seed.title)
            candidates.append(
                OpportunityCandidate(
                    opportunity_id=f"fashion-{self.name}-{slug}",
                    title=seed.title,
                    description=seed.description.format(market=market),
                    category=seed.category,
                    evidence=seed.evidence,
                    confidence=seed.confidence,
                    source_plugin=f"fashion_discovery:{self.name}",
                )
            )
        return candidates


SCANNERS: tuple[Scanner, ...] = (
    Scanner(
        name="industry",
        seeds=(
            OpportunitySeed(
                title="Independent fashion store operations service",
                description=(
                    "A shared operational service for independent apparel stores in {market}, "
                    "covering product data, campaign preparation, and routine back-office work."
                ),
                category="industry_structure",
                evidence=(
                    "knowledge-map:independent stores have repeated operational tasks",
                    "pattern:shared-services",
                ),
                confidence=0.68,
            ),
            OpportunitySeed(
                title="Fashion supplier onboarding hub",
                description=(
                    "A standardized onboarding channel that helps stores in {market} receive "
                    "clean product, price, size, and delivery information from suppliers."
                ),
                category="supplier_enablement",
                evidence=(
                    "knowledge-map:product information passes through many fragmented parties",
                    "pattern:standardization",
                ),
                confidence=0.72,
            ),
        ),
    ),
    Scanner(
        name="value_chain",
        seeds=(
            OpportunitySeed(
                title="Multi-store slow inventory exchange",
                description=(
                    "A B2B exchange that moves slow-selling clothing between stores or regions "
                    "before deep discounting in {market}."
                ),
                category="inventory",
                evidence=(
                    "value-chain:unsold inventory traps working capital",
                    "pattern:aggregation",
                ),
                confidence=0.78,
            ),
            OpportunitySeed(
                title="Circular recovery routing for apparel",
                description=(
                    "A routing service that directs returned, damaged, or aged garments to the "
                    "best recovery path: resale, repair, donation, or recycling in {market}."
                ),
                category="circular_economy",
                evidence=(
                    "value-chain:garments retain different forms of residual value",
                    "pattern:reverse-logistics",
                ),
                confidence=0.76,
            ),
        ),
    ),
    Scanner(
        name="problem",
        seeds=(
            OpportunitySeed(
                title="Size and fit feedback exchange",
                description=(
                    "A structured feedback layer through which stores in {market} record recurring "
                    "fit problems and share anonymized insights with brands and suppliers."
                ),
                category="fit_data",
                evidence=(
                    "problem:fit knowledge is often informal and lost",
                    "pattern:data-feedback-loop",
                ),
                confidence=0.70,
            ),
            OpportunitySeed(
                title="Fashion returns disposition assistant",
                description=(
                    "A workflow that helps store staff choose the most valuable next action for "
                    "each returned item without replacing the store's existing POS."
                ),
                category="returns",
                evidence=(
                    "problem:return decisions are repetitive and inconsistent",
                    "pattern:decision-support",
                ),
                confidence=0.69,
            ),
        ),
    ),
    Scanner(
        name="trend",
        seeds=(
            OpportunitySeed(
                title="Digital product passport readiness service",
                description=(
                    "A staged data-readiness service that helps apparel businesses in {market} "
                    "organize composition, origin, care, repair, and lifecycle information."
                ),
                category="compliance_data",
                evidence=(
                    "trend:greater product traceability requirements",
                    "pattern:compliance-as-a-service",
                ),
                confidence=0.66,
            ),
            OpportunitySeed(
                title="Local fashion resale infrastructure",
                description=(
                    "A service layer that lets local stores in {market} intake, authenticate, price, "
                    "and relist pre-owned apparel through existing marketplaces."
                ),
                category="resale",
                evidence=(
                    "trend:growing reuse and second-life commerce",
                    "pattern:infrastructure-layer",
                ),
                confidence=0.74,
            ),
        ),
    ),
    Scanner(
        name="pattern",
        seeds=(
            OpportunitySeed(
                title="Shared fashion service membership",
                description=(
                    "A membership that bundles recurring services for small apparel stores in "
                    "{market}, such as content, product-data cleanup, and campaign support."
                ),
                category="membership",
                evidence=(
                    "pattern:subscription bundles fragmented recurring needs",
                    "pattern:shared-services",
                ),
                confidence=0.64,
            ),
            OpportunitySeed(
                title="Fashion micro-fulfilment cooperative",
                description=(
                    "A cooperative logistics layer through which independent stores in {market} "
                    "share selected storage, pickup, packing, and local delivery capacity."
                ),
                category="logistics",
                evidence=(
                    "pattern:shared infrastructure lowers unit cost",
                    "pattern:cooperative-network",
                ),
                confidence=0.65,
            ),
        ),
    ),
)


class FashionDiscoveryPlugin:
    """First ODS discovery-stage plugin, scoped to the fashion reference case."""

    name = "fashion_discovery"
    stage = Stage.DISCOVERY

    def run(self, session: ODSSession) -> StageResult:
        if not _is_fashion_subject(session.request.subject):
            return StageResult(
                stage=self.stage,
                status=Status.FAILED,
                errors=[
                    "fashion_discovery supports only fashion/apparel subjects in this alpha"
                ],
            )

        candidates: list[OpportunityCandidate] = []
        for scanner in SCANNERS:
            candidates.extend(scanner.scan(session.request.country))

        deduplicated = _deduplicate(candidates)
        return StageResult(
            stage=self.stage,
            status=Status.COMPLETED,
            payload=tuple(deduplicated),
            evidence=[
                f"scanner_completed:{scanner.name}:{len(scanner.seeds)}"
                for scanner in SCANNERS
            ],
        )


def _is_fashion_subject(subject: str) -> bool:
    normalized = unicodedata.normalize("NFKC", subject).strip().casefold()
    return normalized in {alias.casefold() for alias in _FASHION_ALIASES}


def _deduplicate(
    candidates: list[OpportunityCandidate],
) -> list[OpportunityCandidate]:
    unique: dict[str, OpportunityCandidate] = {}
    for candidate in candidates:
        key = _slugify(candidate.title)
        existing = unique.get(key)
        if existing is None or candidate.confidence > existing.confidence:
            unique[key] = candidate
    return list(unique.values())


def _slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.casefold()).strip("-")
    if not slug:
        raise ValueError("value cannot be converted to a stable slug")
    return slug
