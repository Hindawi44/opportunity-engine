"""Deterministic Business DNA stage for ODS alpha.

The BDNA plugin consumes the highest-ranked opportunity and converts it into a
structured business blueprint. It does not validate assumptions or create an
execution plan.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import ODSSession, OpportunityCandidate, Stage, StageResult, Status
from .ranking import RankedOpportunity


@dataclass(frozen=True)
class BusinessBlueprint:
    """Structured output of the BDNA stage."""

    opportunity: OpportunityCandidate
    ranking_score: float
    business_dna: tuple[str, ...]
    core_asset: str
    revenue_models: tuple[str, ...]
    moat: tuple[str, ...]
    growth_path: tuple[str, ...]
    risks: tuple[str, ...]
    hypotheses: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.business_dna:
            raise ValueError("business_dna must not be empty")
        if not self.core_asset.strip():
            raise ValueError("core_asset must not be empty")
        if not self.revenue_models:
            raise ValueError("revenue_models must not be empty")
        if not self.hypotheses:
            raise ValueError("hypotheses must not be empty")


@dataclass(frozen=True)
class _BDNAProfile:
    dna: tuple[str, ...]
    core_asset: str
    revenue_models: tuple[str, ...]
    moat: tuple[str, ...]
    growth_path: tuple[str, ...]
    risks: tuple[str, ...]
    hypotheses: tuple[str, ...]


_CATEGORY_PROFILES: dict[str, _BDNAProfile] = {
    "inventory": _BDNAProfile(
        dna=("aggregation", "inventory visibility", "matching", "fast rotation"),
        core_asset="Cross-store inventory and demand network",
        revenue_models=("transaction fee", "store subscription"),
        moat=("liquidity density", "historical sell-through data", "store relationships"),
        growth_path=("pilot with local stores", "regional exchange", "supplier integration"),
        risks=("insufficient store participation", "logistics complexity", "poor product data"),
        hypotheses=(
            "Stores will share selected slow-moving inventory",
            "Transferred stock will recover more margin than deep discounting",
            "Enough regional demand differences exist to support matching",
        ),
    ),
    "fit_data": _BDNAProfile(
        dna=("structured feedback", "data loop", "benchmarking", "supplier intelligence"),
        core_asset="Anonymized size, fit, and alteration knowledge graph",
        revenue_models=("store subscription", "brand data subscription", "analytics reports"),
        moat=("proprietary fit dataset", "cross-store benchmarks", "workflow integration"),
        growth_path=("capture store feedback", "add alteration partners", "sell supplier insights"),
        risks=("inconsistent data entry", "privacy concerns", "slow supplier adoption"),
        hypotheses=(
            "Stores will consistently record fit feedback",
            "Fit insights will reduce returns or save sales",
            "Brands and suppliers will pay for aggregated insights",
        ),
    ),
    "returns": _BDNAProfile(
        dna=("decision support", "workflow standardization", "margin recovery", "service routing"),
        core_asset="Returns outcomes and recovery decision dataset",
        revenue_models=("store subscription", "per-item service fee", "recovery commission"),
        moat=("outcome history", "repair and resale network", "store workflow adoption"),
        growth_path=("single-store pilot", "tailor network", "multi-channel recovery routing"),
        risks=("staff workflow resistance", "low item value", "partner service inconsistency"),
        hypotheses=(
            "Store staff need a repeatable returns decision workflow",
            "Repair or resale can recover meaningful value from selected returns",
            "Stores will pay for measured margin recovery",
        ),
    ),
    "circular_economy": _BDNAProfile(
        dna=("reverse logistics", "classification", "routing", "value recovery"),
        core_asset="Recovery partner network and garment outcome data",
        revenue_models=("routing fee", "recovery commission", "compliance reporting subscription"),
        moat=("partner coverage", "recovery performance data", "operational rules engine"),
        growth_path=("repair routing", "resale and donation channels", "national recovery network"),
        risks=("transport costs", "uneven recovery economics", "partner capacity"),
        hypotheses=(
            "Businesses have enough recoverable garments to justify routing",
            "A routing layer improves value recovery compared with ad hoc decisions",
            "Partners will accept standardized intake and status reporting",
        ),
    ),
}

_DEFAULT_PROFILE = _BDNAProfile(
    dna=("specialization", "repeatable workflow", "data capture", "customer trust"),
    core_asset="Operational knowledge and customer relationship dataset",
    revenue_models=("subscription", "service fee"),
    moat=("workflow integration", "accumulated operating data", "customer relationships"),
    growth_path=("manual pilot", "repeatable service", "software-assisted scale"),
    risks=("unclear willingness to pay", "weak differentiation", "operational complexity"),
    hypotheses=(
        "The target customer experiences the stated problem frequently",
        "The proposed workflow creates measurable economic value",
        "Customers will pay for a repeatable solution",
    ),
)


class BDNAPlugin:
    """Builds one business blueprint from the top-ranked opportunity."""

    name = "bdna_engine"
    stage = Stage.BDNA

    def run(self, session: ODSSession) -> StageResult:
        ranking_result = session.results.get(Stage.RANKING)
        if ranking_result is None:
            return self._failure("bdna requires a completed ranking result")
        if ranking_result.status is not Status.COMPLETED:
            return self._failure("bdna requires ranking status completed")

        payload = ranking_result.payload
        if not isinstance(payload, (tuple, list)) or not payload:
            return self._failure("bdna requires a non-empty ranked shortlist")
        if not all(isinstance(item, RankedOpportunity) for item in payload):
            return self._failure("ranking payload contains invalid ranked opportunities")

        top = min(payload, key=lambda item: item.rank)
        if top.rank != 1:
            return self._failure("bdna requires a rank-1 opportunity")

        profile = _CATEGORY_PROFILES.get(top.opportunity.category, _DEFAULT_PROFILE)
        blueprint = BusinessBlueprint(
            opportunity=top.opportunity,
            ranking_score=top.final_score,
            business_dna=profile.dna,
            core_asset=profile.core_asset,
            revenue_models=profile.revenue_models,
            moat=profile.moat,
            growth_path=profile.growth_path,
            risks=profile.risks,
            hypotheses=profile.hypotheses,
        )
        return StageResult(
            stage=self.stage,
            status=Status.COMPLETED,
            payload=blueprint,
            evidence=[
                f"bdna_source_opportunity:{top.opportunity.opportunity_id}",
                f"bdna_source_rank:{top.rank}",
                f"bdna_profile:{top.opportunity.category}",
                "bdna_method:deterministic-alpha",
            ],
        )

    def _failure(self, message: str) -> StageResult:
        return StageResult(
            stage=self.stage,
            status=Status.FAILED,
            errors=[message],
        )
