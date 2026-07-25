"""Controlled end-to-end checkpoint for the Clothing Inventory MVP.

This module proves the first safe vertical slice from a discovery candidate to an
honest evidence-required outcome. It deliberately stops before financial analysis
when required evidence is absent; it never invents price, quantity, costs, or a
purchase decision.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from opportunity_engine.discovery.classifier import classify_candidate, to_canonical_opportunity
from opportunity_engine.discovery.models import DiscoveryCandidate, DiscoveryResult


@dataclass(frozen=True, slots=True)
class OpportunityDossier:
    """Traceable evidence package between Discovery and Analysis."""

    opportunity_id: str
    domain: str
    primary_scenario: str
    qualification_status: str
    confirmed_facts: dict[str, Any]
    seller_claims: dict[str, Any]
    supported_inferences: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    unknown_fields: tuple[str, ...] = field(default_factory=tuple)
    missing_evidence: tuple[str, ...] = field(default_factory=tuple)
    seller_questions: tuple[str, ...] = field(default_factory=tuple)
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["supported_inferences"] = list(self.supported_inferences)
        payload["unknown_fields"] = list(self.unknown_fields)
        payload["missing_evidence"] = list(self.missing_evidence)
        payload["seller_questions"] = list(self.seller_questions)
        return payload


@dataclass(frozen=True, slots=True)
class EligibilityDecision:
    eligible_for_analysis: bool
    reason: str
    missing_requirements: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class CheckpointOutcome:
    outcome_type: str
    discovery_result: DiscoveryResult
    dossier: OpportunityDossier
    eligibility: EligibilityDecision
    canonical_opportunity: dict[str, Any] | None
    analysis_invoked: bool
    automatic_purchase_decision: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome_type": self.outcome_type,
            "discovery_result": self.discovery_result.to_dict(),
            "dossier": self.dossier.to_dict(),
            "eligibility": asdict(self.eligibility),
            "canonical_opportunity": self.canonical_opportunity,
            "analysis_invoked": self.analysis_invoked,
            "automatic_purchase_decision": self.automatic_purchase_decision,
        }


def build_opportunity_dossier(result: DiscoveryResult) -> OpportunityDossier:
    """Build a dossier without converting unknown values into estimates."""
    candidate = result.candidate
    canonical = to_canonical_opportunity(result)
    opportunity_id = (
        canonical["opportunity_id"] if canonical is not None else f"lead:{candidate.url}"
    )

    confirmed_facts: dict[str, Any] = {
        "source_url": candidate.url,
        "source_title": candidate.title,
        "source_name": candidate.source,
        "source_text": candidate.text,
        "discovered_at": candidate.discovered_at,
        "scenario": result.scenario,
        "record_type": result.record_type,
        "status": result.status,
    }
    if candidate.location is not None:
        confirmed_facts["location"] = candidate.location
    if candidate.contact is not None:
        confirmed_facts["public_contact"] = candidate.contact

    seller_claims: dict[str, Any] = {}
    if candidate.quantity is not None:
        seller_claims["quantity"] = candidate.quantity
    if candidate.price_nok is not None:
        seller_claims["asking_price_nok"] = candidate.price_nok

    unknown_fields: list[str] = []
    if candidate.quantity is None:
        unknown_fields.append("quantity")
    if candidate.price_nok is None:
        unknown_fields.append("asking_price_nok")
    if candidate.location is None:
        unknown_fields.append("location")
    if candidate.contact is None:
        unknown_fields.append("public_contact")

    missing_evidence = [
        "verified inventory list",
        "current dated images of the complete lot",
        "VAT treatment",
        "transport and collection terms",
        "market comparable evidence",
    ]
    if candidate.quantity is None:
        missing_evidence.append("verified item quantity")
    if candidate.price_nok is None:
        missing_evidence.append("confirmed asking price or bid basis")

    seller_questions = [
        "What exact quantity and product categories are included?",
        "What is the total asking price and is VAT included?",
        "Can you provide a dated inventory list and current images?",
        "Where is the inventory located and what are the collection terms?",
        "Are any items damaged, returned, counterfeit, or restricted from resale?",
    ]

    return OpportunityDossier(
        opportunity_id=opportunity_id,
        domain="CLOTHING_INVENTORY",
        primary_scenario=result.scenario,
        qualification_status=result.status,
        confirmed_facts=confirmed_facts,
        seller_claims=seller_claims,
        supported_inferences=(),
        unknown_fields=tuple(unknown_fields),
        missing_evidence=tuple(missing_evidence),
        seller_questions=tuple(seller_questions),
        provenance={
            "text": {"source_url": candidate.url, "source": candidate.source},
            "classification": {
                "signals": list(result.evidence),
                "reason": result.reason,
            },
            "images": [],
            "attachments": [],
            "company_records": [],
        },
    )


def evaluate_analysis_eligibility(
    result: DiscoveryResult,
    dossier: OpportunityDossier,
) -> EligibilityDecision:
    """Allow only sufficiently evidenced confirmed sales into Analysis."""
    missing: list[str] = []
    candidate = result.candidate

    if result.status != "SALE_CONFIRMED":
        missing.append("confirmed public sale")
    if not candidate.url.startswith("https://"):
        missing.append("traceable HTTPS source")
    if candidate.price_nok is None:
        missing.append("confirmed acquisition price")
    if candidate.quantity is None:
        missing.append("verified quantity")
    if "market comparable evidence" in dossier.missing_evidence:
        missing.append("verified market comparables")

    if missing:
        return EligibilityDecision(
            eligible_for_analysis=False,
            reason="Key evidence is missing; preserve the opportunity for evidence collection.",
            missing_requirements=tuple(missing),
        )
    return EligibilityDecision(
        eligible_for_analysis=True,
        reason="Confirmed sale has the minimum traceability and decision evidence.",
    )


def controlled_clothing_inventory_candidate() -> DiscoveryCandidate:
    """Controlled fixture representing a promising but incomplete sale listing."""
    return DiscoveryCandidate(
        title="Varelager til salgs etter lageravvikling",
        url="https://example.invalid/controlled/clothing-inventory-001",
        source="CONTROLLED_FIXTURE",
        discovered_at="2026-07-25T12:00:00Z",
        text=(
            "Varelager til salgs. Parti med klær selges samlet etter lageravvikling klær. "
            "Kontakt selger for pris, antall og hentebetingelser."
        ),
        location="Trøndelag",
        quantity=None,
        price_nok=None,
        contact=None,
    )


def run_controlled_clothing_inventory_checkpoint() -> CheckpointOutcome:
    """Run the controlled candidate through Discovery, Dossier, and eligibility."""
    candidate = controlled_clothing_inventory_candidate()
    result = classify_candidate(candidate)
    dossier = build_opportunity_dossier(result)
    eligibility = evaluate_analysis_eligibility(result, dossier)
    canonical = to_canonical_opportunity(result)

    if eligibility.eligible_for_analysis:
        # The downstream Analysis Engine is intentionally not rebuilt here. A later
        # eligible fixture must call its existing public orchestration boundary.
        outcome_type = "ANALYSIS_READY"
        analysis_invoked = False
    else:
        outcome_type = "EVIDENCE_REQUIRED"
        analysis_invoked = False

    return CheckpointOutcome(
        outcome_type=outcome_type,
        discovery_result=result,
        dossier=dossier,
        eligibility=eligibility,
        canonical_opportunity=canonical,
        analysis_invoked=analysis_invoked,
        automatic_purchase_decision=False,
    )
