"""Public runner for the first usable ODS alpha flow.

The runner wires together only the stages that are implemented today:
discovery, ranking, and BDNA. It provides one stable entry point for user
interfaces and future APIs without exposing plugin orchestration details.
"""

from __future__ import annotations

from dataclasses import dataclass

from .bdna import BDNAPlugin, BusinessBlueprint
from .discovery import FashionDiscoveryPlugin
from .models import ODSRequest, ODSSession, Stage, Status
from .plugins import PluginRegistry
from .ranking import OpportunityRankingPlugin, RankedOpportunity
from .workflow import WorkflowEngine


USABLE_ALPHA_WORKFLOW: tuple[Stage, ...] = (
    Stage.DISCOVERY,
    Stage.RANKING,
    Stage.BDNA,
)


@dataclass(frozen=True)
class ODSAnalysisResult:
    """Convenient, validated view of a completed ODS alpha session."""

    session: ODSSession
    ranked_opportunities: tuple[RankedOpportunity, ...]
    blueprint: BusinessBlueprint

    @property
    def discovered_count(self) -> int:
        discovery = self.session.results[Stage.DISCOVERY].payload
        return len(discovery)


def build_alpha_engine(
    *,
    shortlist_size: int = 5,
    minimum_score: float = 0.0,
) -> WorkflowEngine:
    """Build the currently supported ODS engine.

    Fashion remains the only user-facing reference sector in this alpha.
    Additional sector discovery plugins can be registered in later releases.
    """

    registry = PluginRegistry(
        (
            FashionDiscoveryPlugin(),
            OpportunityRankingPlugin(
                shortlist_size=shortlist_size,
                minimum_score=minimum_score,
            ),
            BDNAPlugin(),
        )
    )
    return WorkflowEngine(registry, workflow=USABLE_ALPHA_WORKFLOW)


def run_ods(
    subject: str,
    *,
    country: str | None = "Norway",
    constraints: tuple[str, ...] = (),
    shortlist_size: int = 5,
    minimum_score: float = 0.0,
) -> ODSAnalysisResult:
    """Run Discovery → Ranking → BDNA and return a validated result.

    Raises:
        RuntimeError: if any workflow stage fails or returns an invalid payload.
    """

    request = ODSRequest(
        subject=subject,
        country=country,
        constraints=constraints,
    )
    engine = build_alpha_engine(
        shortlist_size=shortlist_size,
        minimum_score=minimum_score,
    )
    session = engine.run(request)

    if session.status is not Status.COMPLETED:
        detail = session.audit_log[-1] if session.audit_log else "unknown failure"
        raise RuntimeError(f"ODS analysis failed: {detail}")

    ranking_payload = session.results[Stage.RANKING].payload
    blueprint_payload = session.results[Stage.BDNA].payload
    if not isinstance(ranking_payload, tuple) or not all(
        isinstance(item, RankedOpportunity) for item in ranking_payload
    ):
        raise RuntimeError("ODS ranking stage returned an invalid payload")
    if not ranking_payload:
        raise RuntimeError("ODS ranking stage returned an empty shortlist")
    if not isinstance(blueprint_payload, BusinessBlueprint):
        raise RuntimeError("ODS BDNA stage returned an invalid payload")

    return ODSAnalysisResult(
        session=session,
        ranked_opportunities=ranking_payload,
        blueprint=blueprint_payload,
    )
