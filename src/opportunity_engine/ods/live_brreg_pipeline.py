"""End-to-end live opportunity path backed by public Brreg records.

This module closes the first real ODS loop:
public source -> normalized evidence -> grounded opportunity -> ranking -> decision.
It only emits an opportunity when an official record explicitly carries a
bankruptcy or liquidation flag. It does not infer that assets are available.
"""
from __future__ import annotations

from dataclasses import dataclass

from .brreg import BrregConnector
from .decision import DecisionInputs, ExecutiveDecisionReport, build_executive_decision
from .models import ODSRequest, ODSSession, OpportunityCandidate, Stage, StageResult, Status
from .ranking import OpportunityRankingPlugin, RankedOpportunity
from .scanner import ConnectorRegistry, ScanSnapshot, UniversalOpportunityScanner
from .live_data import SourceDocument


class BrregStatusOpportunityExtractor:
    """Create follow-up opportunities only from explicit official status flags."""

    def extract(
        self,
        documents: tuple[SourceDocument, ...],
        request: ODSRequest,
    ) -> tuple[OpportunityCandidate, ...]:
        candidates: list[OpportunityCandidate] = []
        for document in documents:
            bankrupt = bool(document.metadata.get("bankrupt"))
            liquidation = bool(document.metadata.get("under_liquidation"))
            if not bankrupt and not liquidation:
                continue

            orgnr = str(document.metadata.get("organisation_number") or document.document_id)
            status = "bankruptcy" if bankrupt else "liquidation"
            municipality = document.metadata.get("municipality") or "unknown municipality"
            evidence = tuple(
                item
                for item in (
                    f"official-status:{status}",
                    f"organisation-number:{orgnr}",
                    f"municipality:{municipality}",
                    document.url or None,
                )
                if item
            )
            candidates.append(
                OpportunityCandidate(
                    opportunity_id=f"brreg-status-{orgnr}",
                    title=f"Verify potential business assets or service needs: {document.title}",
                    description=(
                        f"Official Brreg data marks {document.title} ({orgnr}) as under {status}. "
                        "This is a verified lead for manual follow-up with the estate administrator "
                        "or company contact. The record alone does not prove that assets are for sale."
                    ),
                    category="liquidation_assets",
                    evidence=evidence,
                    confidence=0.72 if bankrupt else 0.66,
                    source_plugin="brreg_status_extractor",
                )
            )
        return tuple(candidates)


@dataclass(frozen=True)
class LiveBrregAnalysis:
    request: ODSRequest
    scan: ScanSnapshot
    ranked_opportunities: tuple[RankedOpportunity, ...]
    decision: ExecutiveDecisionReport | None


def run_live_brreg_analysis(
    subject: str,
    *,
    country: str = "Norway",
    municipality: str | None = None,
    industry_code: str | None = None,
    page_size: int = 50,
    shortlist_size: int = 10,
    connector: BrregConnector | None = None,
) -> LiveBrregAnalysis:
    """Run the first live public-source ODS path.

    Empty results are valid: they mean the sampled official records contained no
    explicit bankruptcy/liquidation signal, not that no such entities exist.
    """
    request = ODSRequest(subject=subject, country=country)
    active_connector = connector or BrregConnector(
        municipality=municipality,
        industry_code=industry_code,
        page_size=page_size,
    )
    scanner = UniversalOpportunityScanner(
        ConnectorRegistry((active_connector,)),
        extractor=BrregStatusOpportunityExtractor(),
    )
    scan = scanner.scan(request)
    if not scan.opportunities:
        return LiveBrregAnalysis(request, scan, (), None)

    session = ODSSession(request=request, status=Status.RUNNING)
    session.results[Stage.DISCOVERY] = StageResult(
        stage=Stage.DISCOVERY,
        status=Status.COMPLETED,
        payload=scan.opportunities,
        evidence=[f"live_scan:{scan.scan_id}"],
    )
    ranking_result = OpportunityRankingPlugin(shortlist_size=shortlist_size).run(session)
    if ranking_result.status is not Status.COMPLETED:
        raise RuntimeError("live Brreg ranking failed: " + "; ".join(ranking_result.errors))
    ranked = ranking_result.payload
    if not isinstance(ranked, tuple):
        raise RuntimeError("live Brreg ranking returned an invalid payload")

    top = ranked[0]
    decision = build_executive_decision(
        DecisionInputs(
            opportunity_confidence=top.final_score,
            validation_readiness=40.0,
            evidence_quality=90.0,
            market_health=None,
            financial_report=None,
        )
    )
    return LiveBrregAnalysis(request, scan, ranked, decision)
