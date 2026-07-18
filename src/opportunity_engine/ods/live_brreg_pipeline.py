"""Live Brreg status-signal path backed by official public records."""
from __future__ import annotations

from dataclasses import dataclass

from .brreg import BrregConnector
from .decision import ExecutiveDecisionReport
from .live_data import SourceDocument
from .models import LifecycleState, ODSRequest, OpportunityCandidate
from .ranking import RankedOpportunity
from .scanner import ConnectorRegistry, ScanSnapshot, UniversalOpportunityScanner


class BrregStatusOpportunityExtractor:
    """Create SIGNAL items only from explicit official status flags."""

    def extract(
        self,
        documents: tuple[SourceDocument, ...],
        request: ODSRequest,
    ) -> tuple[OpportunityCandidate, ...]:
        signals: list[OpportunityCandidate] = []
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
            signals.append(
                OpportunityCandidate(
                    opportunity_id=f"brreg-status-{orgnr}",
                    title=f"Investigate official company status: {document.title}",
                    description=(
                        f"Official Brreg data marks {document.title} ({orgnr}) as under {status}. "
                        "This is a lifecycle signal for manual investigation only. The record "
                        "does not prove that assets are available or that a commercial opportunity exists."
                    ),
                    category="company_status",
                    evidence=evidence,
                    confidence=0.72 if bankrupt else 0.66,
                    source_plugin="brreg_status_extractor",
                    lifecycle_state=LifecycleState.SIGNAL,
                )
            )
        return tuple(signals)


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
    """Collect Brreg documents and expose status signals without ranking or decision."""
    _ = shortlist_size
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
    return LiveBrregAnalysis(request, scan, (), None)
